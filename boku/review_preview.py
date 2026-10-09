"""Exact local layout previews and a spreadsheet data contract for human review.

The workbook consumes measurements; it does not implement a second word wrapper.
CSV edits come back through the lossless pilot and are measured again before use.
Workbook data is English-only; an explicitly shared Japanese reference column is
accepted on CSV import but never copied into translation files or review outputs.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html
import json
import sys
import tempfile
from functools import cache
from pathlib import Path

from boku import REPO_ROOT
from boku.archive import DEFAULT_DISC_DIR
from boku.build import load_edit_set
from boku.lint import DEFAULT_CELLS
from boku.review_pilot import (
    DEFAULT_SOURCE,
    PilotRefused,
    apply_review,
    fresh_output,
    review_document,
    validate,
    write_json,
)
from boku.script_store import load_store
from boku.sites import load
from boku.translation import SampleScenes

HEADERS = (
    "Line ID",
    "Speaker",
    "Upstream English",
    "Human English",
    "Review status",
    "Fit",
    "Pages",
    "Wrapped lines",
    "Widest line (px)",
    "Event",
    "Turn",
    "Boundary",
    "Event order",
    "Review notes",
    "Effective English",
)
REFERENCE_HEADERS = (*HEADERS[:2], "Original Japanese", *HEADERS[2:])


def entry_text(row: dict) -> str:
    separator = SampleScenes.OPTION if row["kind"] == "select" else SampleScenes.PAGE_BREAK
    return separator.join(segment["translation"] for segment in row["segments"])


def read_sheet(path: Path, manifest: dict) -> tuple[dict, dict[str, str]]:
    """Read a downloaded Translation Batch CSV by ID; never import formula fit results."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.reader(stream))
    header_positions = [
        (i, headers)
        for i, row in enumerate(records)
        for headers in (HEADERS, REFERENCE_HEADERS)
        if tuple(row[: len(headers)]) == headers
    ]
    if len(header_positions) != 1:
        raise PilotRefused("CSV needs one unchanged Translation Batch header row")
    header_position, headers = header_positions[0]
    edited = copy.deepcopy(manifest)
    wanted = {row["id"]: row for row in edited["rows"]}
    seen: set[str] = set()
    notes = {}
    for values in records[header_position + 1 :]:
        if not any(values):
            continue
        if headers == REFERENCE_HEADERS:
            # Reference text is not an editable translation field. Drop it before
            # interpreting columns so source data cannot leak into review outputs.
            values = values[:2] + values[3:]
        values += [""] * max(0, len(HEADERS) - len(values))
        line_id = values[0]
        if line_id not in wanted or line_id in seen:
            raise PilotRefused("CSV contains an unknown or duplicate line ID")
        seen.add(line_id)
        row = wanted[line_id]
        fixed = {
            1: row["speaker"],
            2: row["upstream_text"],
            9: row["event"],
            10: f"{row['turn_position']} / {row['turn_count']}",
            11: row["boundary"],
            12: str(row["file_event_order"]),
        }
        if any(values[index] != text for index, text in fixed.items()):
            raise PilotRefused(f"{line_id}: CSV context or upstream English changed")
        text = values[3] if values[3] else row["upstream_text"]
        separator = SampleScenes.OPTION if row["kind"] == "select" else SampleScenes.PAGE_BREAK
        parts = text.split(separator) if text else []
        if len(parts) != len(row["segments"]):
            raise PilotRefused(f"{line_id}: CSV changed the page/choice count")
        for segment, part in zip(row["segments"], parts, strict=True):
            segment["translation"] = part
        row["review_status"] = values[4]
        notes[line_id] = values[13]
    if seen != set(wanted):
        raise PilotRefused("CSV is missing review rows; download the complete tab")
    return edited, notes


def workbook_data(review: dict, fit: dict, notes: dict[str, str]) -> dict:
    """English-only handoff to the workbook builder; no source text, glyphs or disc bytes."""
    profile = hashlib.sha256((fit["cells_sha256"] + fit["boku_code_sha256"]).encode()).hexdigest()
    layouts = {row["id"]: row for row in fit["layouts"]}
    rows, pages = [], []
    for row in review["rows"]:
        laid = layouts.get(row["id"])
        findings = [f for f in fit["findings"] if f["line_id"] == row["id"]]
        failed = any(f["severity"] == "ERROR" for f in findings) or bool(laid and laid["problems"])
        status = (
            "ERROR"
            if failed
            else "NO SUBTITLE"
            if not row["segments"]
            else "UNMEASURED"
            if laid is None
            else "FITS"
        )
        text = entry_text(row)
        rows.append(
            {
                "id": row["id"],
                "speaker": row["speaker"],
                "upstream": row["upstream_text"],
                "human": text if text != row["upstream_text"] else "",
                "effective": text,
                "review_status": row["review_status"],
                "fit": status,
                "pages": len(laid["pages"]) if laid else 0,
                "lines": sum(map(len, laid["pages"])) if laid else 0,
                "widest": max((n for p in laid["widths_px"] for n in p), default=0) if laid else 0,
                "event": row["event"],
                "turn": f"{row['turn_position']} / {row['turn_count']}",
                "boundary": row["boundary"],
                "event_order": row["file_event_order"],
                "notes": notes.get(row["id"], ""),
            }
        )
        if not laid:
            continue
        if row["kind"] == "select":
            for segment, line, width, limit in zip(
                row["segments"],
                laid["pages"][0],
                laid["widths_px"][0],
                laid["limits_px"][0],
                strict=True,
            ):
                pages.append(
                    {
                        "id": row["id"],
                        "part": segment["slot"],
                        "text": line,
                        "widths": [width],
                        "limits": [limit],
                    }
                )
        else:
            for number, (lines, widths, limits) in enumerate(
                zip(laid["pages"], laid["widths_px"], laid["limits_px"], strict=True), 1
            ):
                pages.append(
                    {
                        "id": row["id"],
                        "part": f"page:{number}",
                        "text": "\n".join(lines),
                        "widths": widths,
                        "limits": limits,
                    }
                )
    return {
        "schema": "boku-review-workbook-v1",
        "headers": HEADERS,
        "profile": profile,
        "source_sha256": review["source_sha256"],
        "text_sha256": fit["text_sha256"],
        "cells_sha256": fit["cells_sha256"],
        "boku_code_sha256": fit["boku_code_sha256"],
        "rows": rows,
        "pages": pages,
    }


def render_mockups(
    candidate: bytes, name: str, disc: Path, cells: Path, out: Path, events: list[str]
) -> None:
    """Call the upstream mockup drawing functions, including its font glyphs."""
    from tools.vwf import mockup

    archive, walk = load(disc)
    edits = load_edit_set(cells)
    glyphs = cache(mockup.font_sheet(archive, edits).get)
    layout = mockup.layout_of(edits)
    # Upstream draw_file currently uses the default select row. Refuse geometry it
    # cannot faithfully preview instead of displaying a subtly different choice box.
    from boku.layout import SELECT_ROW

    if edits.select_row != SELECT_ROW:
        raise PilotRefused("upstream mockup requires the default choice geometry for this preview")
    with tempfile.TemporaryDirectory(prefix="review-draw-", dir=REPO_ROOT / "work") as folder:
        path = Path(folder) / name
        path.write_bytes(candidate)
        mockup.draw_file(
            path, archive, walk, edits.encoder, glyphs, layout, out, frozenset(events), 2
        )


def local_html(review: dict, fit: dict, store, source_name: str) -> str:
    """Private source context next to the exact upstream glyph mockups."""
    esc = html.escape
    layout = {row["id"]: row for row in fit["layouts"]}
    links, sections = [], []
    for event in review["events"]:
        links.append(f'<a href="#{event}">{event}</a>')
        rows = []
        for row in review["rows"]:
            if row["event"] != event:
                continue
            japanese = store.japanese.get(row["id"])
            original = japanese.plain() if japanese else "Voice only; no source text on disc."
            result = layout.get(row["id"])
            widths = json.dumps(result["widths_px"]) if result else "No subtitle"
            problems = "\n".join(result["problems"]) if result else ""
            rows.append(
                f'<article id="{row["id"]}"><h3>{row["id"]} · {esc(row["speaker"])}'
                f" · {row['turn_position']}/{row['turn_count']} · {row['boundary']}</h3>"
                f'<p class="source" lang="ja">{esc(original)}</p>'
                f"<p>{esc(entry_text(row))}</p>"
                f'<p class="meta">Review: {esc(row["review_status"])}. Widths (px): {widths}</p>'
                f'<p class="error">{esc(problems)}</p></article>'
            )
        graph = esc(json.dumps(store.scenes_by_event[event], ensure_ascii=False, indent=2))
        sections.append(
            f'<section id="{event}"><h2>{event}</h2><div class="columns"><div>{"".join(rows)}'
            f"<details><summary>Conditions, branches and occurrences</summary><pre>{graph}</pre>"
            f'</details></div><div><img alt="{event} upstream pixel mockup" '
            f'src="mockup/{Path(source_name).stem}/{event}.png"></div></div></section>'
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; img-src 'self' data:\">"
        "<title>Boku local translation review</title><style>"
        "body{font:16px/1.5 Arial,sans-serif;background:#f5f6f1;color:#24322b;margin:32px;"
        "max-width:1500px}h1{font-size:28px}h2{border-top:2px solid #9aad91;padding-top:22px}"
        "nav{display:flex;gap:24px}a{color:#365c38}.columns{display:grid;"
        "grid-template-columns:minmax(380px,1fr) minmax(380px,1fr);gap:28px}"
        "article{background:white;padding:16px;margin-bottom:14px;border-radius:6px}"
        "h3{font-size:16px;margin-top:0}.source{color:#435849;white-space:pre-wrap}"
        ".meta{font-size:13px;color:#546457}.error{color:#9d2525}img{max-width:100%;"
        "image-rendering:pixelated}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}"
        "@media(max-width:900px){.columns{grid-template-columns:1fr}body{margin:16px}}"
        "</style><h1>Boku translation review</h1>"
        "<p>Local source context and upstream pixel mockups. Page breaks are shown as //.</p>"
        "<p>Edit the workbook, download Translation Batch as CSV, then regenerate this preview. "
        "Branches may revisit or skip turns. Message positions are not a guaranteed route.</p>"
        f"<nav>{''.join(links)}</nav>{''.join(sections)}</html>"
    )


def run(args: argparse.Namespace) -> int:
    try:
        out = fresh_output(args.out)
        source = args.source.read_bytes()
        manifest = json.loads((args.bundle / "manifest.json").read_text(encoding="utf-8"))
        store = load_store(args.disc / "script")
        if (
            manifest != review_document(source, args.source.name, manifest["events"], store)
            or (args.bundle / "source.txt").read_bytes() != source
        ):
            raise PilotRefused("source or export manifest changed; export a new pilot first")
        if args.csv:
            reviewed, notes = read_sheet(args.csv, manifest)
        else:
            reviewed = json.loads(
                (args.review or args.bundle / "review.json").read_text(encoding="utf-8")
            )
            notes = {}
        candidate, changed = apply_review(source, manifest, reviewed)
        fit = validate(
            candidate, args.source, args.disc, args.cells, {row["id"] for row in reviewed["rows"]}
        )
        fit["changed_ids"] = changed
        data = workbook_data(reviewed, fit, notes)
        out.mkdir(parents=True)
        write_json(out / "review.json", reviewed)
        write_json(out / "review-notes.json", notes)
        write_json(out / "fit.json", fit)
        write_json(out / "workbook-data.json", data)
        render_mockups(
            candidate, args.source.name, args.disc, args.cells, out / "mockup", reviewed["events"]
        )
        (out / "index.html").write_text(
            local_html(reviewed, fit, store, args.source.name), encoding="utf-8"
        )
        print(f"review-preview: {len(data['rows'])} entries, {len(data['pages'])} page/choice rows")
        print(f"review-preview: local preview and spreadsheet data in {out}")
        return 1 if fit["has_errors"] else 0
    except (OSError, ValueError, KeyError, TypeError, PilotRefused) as error:
        print(f"review-preview: {error}", file=sys.stderr)
        return 2


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("bundle", type=Path, help="verified review-pilot export directory")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument(
        "--csv", type=Path, help="Translation Batch CSV downloaded from the workbook"
    )
    inputs.add_argument("--review", type=Path, help="edited pilot JSON instead")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--disc", type=Path, default=DEFAULT_DISC_DIR)
    parser.add_argument("--cells", type=Path, default=DEFAULT_CELLS)
    parser.add_argument("--out", type=Path, required=True, help="new directory inside work/")
    parser.set_defaults(run=run)
