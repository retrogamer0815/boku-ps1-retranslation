"""A local, lossless review round trip for complete event blocks in one day file.

This deliberately stages a new file under work/. It never saves into translation/.
JSON is the pilot interchange; a Sheets adapter can later edit the same addressed fields.
All layout and lint decisions belong to the existing build and lint implementations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from boku import REPO_ROOT
from boku.archive import DEFAULT_DISC_DIR, ArchiveError
from boku.build import BuildRefused, lay_out, load_edit_set
from boku.layout import DIALOGUE_BAND, LayoutError
from boku.lint import DEFAULT_CELLS, Options, lint_rows, parse_text
from boku.packets import scene_line_ids
from boku.script_store import Store, StoreMissing, load_store, select_shape
from boku.sites import SiteError, load
from boku.translation import SampleScenes

SCHEMA = "boku-local-review-v1"
STATUSES = ("unreviewed", "draft", "human-reviewed", "needs-revision")
DEFAULT_SOURCE = REPO_ROOT / "translation" / "days" / "day01.txt"
DEFAULT_EVENTS = ("E0171", "E0184", "E0112")
HEADER = re.compile(r"^\s*# --- (E\d{4}):")


class PilotRefused(Exception):
    """A round trip that cannot preserve its source or address edits unambiguously."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Record:
    index: int
    line_id: str
    speaker: str
    text: str
    event: str


def read_records(data: bytes) -> tuple[list[bytes], list[Record]]:
    """Keep physical lines intact; parse only enough to address the English field."""
    lines = data.splitlines(keepends=True)
    records: list[Record] = []
    seen: set[str] = set()
    event = ""
    for index, raw in enumerate(lines):
        text = raw.decode("utf-8").removeprefix("\ufeff") if index == 0 else raw.decode("utf-8")
        text = text.rstrip("\r\n")
        if match := HEADER.match(text):
            event = match[1]
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        fields = text.split("\t")
        if len(fields) not in (2, 3):
            raise PilotRefused(f"source line {index + 1}: expected two or three tab fields")
        line_id, speaker = (field.strip() for field in fields[:2])
        english = fields[2].strip() if len(fields) == 3 else ""
        if not re.fullmatch(r"E\d{4}\.\d+", line_id) or line_id.split(".")[0] != event:
            raise PilotRefused(f"source line {index + 1}: expected an id in its event block")
        if line_id in seen:
            raise PilotRefused(f"source line {index + 1}: duplicate id")
        if not english and speaker != SampleScenes.VOICE_ONLY:
            raise PilotRefused(f"source line {index + 1}: only a voice-only row may be empty")
        seen.add(line_id)
        records.append(Record(index, line_id, speaker, english, event))
    return lines, records


def review_document(data: bytes, name: str, events: Sequence[str], store: Store) -> dict:
    """Immutable addressing/context plus explicitly editable translation and status."""
    _, records = read_records(data)
    wanted = set(events)
    if not wanted or len(wanted) != len(events):
        raise PilotRefused("select one or more distinct complete events")
    event_order = list(dict.fromkeys(row.event for row in records))
    if wanted - set(event_order):
        raise PilotRefused("a requested event is absent from the source file")
    for event in wanted:
        scene = store.scenes_by_event.get(event)
        if scene is None or set(scene_line_ids(scene)) != {
            row.line_id for row in records if row.event == event
        }:
            raise PilotRefused(
                f"{event}: source must contain the complete event, including voice rows"
            )
    rows = []
    for row in records:
        if row.event not in wanted:
            continue
        ids = scene_line_ids(store.scenes_by_event[row.event])
        turn = ids.index(row.line_id) + 1
        shape = select_shape(store.lines.get(row.line_id, {}))
        is_select = row.speaker == SampleScenes.SELECT
        if is_select != (shape is not None):
            raise PilotRefused(f"{row.line_id}: source and script disagree on the row kind")
        if is_select:
            fields = row.text.split(SampleScenes.OPTION)
            options, prompts = shape
            slots = [f"prompt:{i + 1}" for i in range(prompts)] + [
                f"option:{i + 1}" for i in range(options)
            ]
        else:
            fields = row.text.split(SampleScenes.PAGE_BREAK) if row.text else []
            slots = [f"page:{i + 1}" for i in range(len(fields))]
        if len(slots) != len(fields):
            raise PilotRefused(f"{row.line_id}: wrong choice field count")
        boundary = (
            "single"
            if len(ids) == 1
            else ("start" if turn == 1 else "end" if turn == len(ids) else "continue")
        )
        rows.append(
            {
                "id": row.line_id,
                "event": row.event,
                "source_line": row.index + 1,
                "speaker": row.speaker,
                "file_event_order": event_order.index(row.event) + 1,
                "turn_position": turn,
                "turn_count": len(ids),
                "boundary": boundary,
                "kind": "select"
                if is_select
                else ("voice-only" if row.speaker == SampleScenes.VOICE_ONLY else "message"),
                "upstream_text": row.text,
                "segments": [
                    {"slot": slot, "base": field.strip(), "translation": field.strip()}
                    for slot, field in zip(slots, fields, strict=True)
                ],
                "review_status": "unreviewed",
            }
        )
    return {
        "schema": SCHEMA,
        "source_name": name,
        "source_sha256": digest(data),
        "events": [event for event in event_order if event in wanted],
        "order_note": "File/message order; see context.json for conditional flow.",
        "rows": rows,
    }


def apply_review(data: bytes, expected: dict, edited: dict) -> tuple[bytes, list[str]]:
    """Apply only changed English fields; JSON row sorting cannot reorder the script."""
    if not isinstance(edited, dict) or set(edited) != set(expected):
        raise PilotRefused("invalid review document")
    if digest(data) != expected["source_sha256"]:
        raise PilotRefused("source changed since export; export a fresh review")
    if any(edited[key] != value for key, value in expected.items() if key != "rows"):
        raise PilotRefused("source hash, schema, events or other immutable metadata changed")
    given = edited["rows"]
    if not isinstance(given, list) or any(not isinstance(row, dict) for row in given):
        raise PilotRefused("rows must be a list of review rows")
    if any(not isinstance(row.get("id"), str) for row in given):
        raise PilotRefused("every row needs a stable id")
    by_id = {row["id"]: row for row in given}
    if len(by_id) != len(given) or set(by_id) != {row["id"] for row in expected["rows"]}:
        raise PilotRefused("missing, extra or duplicate review ids")
    lines, records = read_records(data)
    locations = {row.line_id: row.index for row in records}
    changed = []
    for base in expected["rows"]:
        row = by_id[base["id"]]
        if set(row) != set(base) or any(
            row[key] != value
            for key, value in base.items()
            if key not in ("segments", "review_status")
        ):
            raise PilotRefused(f"{base['id']}: immutable row metadata changed")
        if row["review_status"] not in STATUSES:
            raise PilotRefused(f"{base['id']}: unknown review status")
        segments = row["segments"]
        if not isinstance(segments, list) or len(segments) != len(base["segments"]):
            raise PilotRefused(f"{base['id']}: page/choice count changed")
        for original, segment in zip(base["segments"], segments, strict=True):
            if (
                not isinstance(segment, dict)
                or set(segment) != set(original)
                or any(segment[key] != original[key] for key in ("slot", "base"))
            ):
                raise PilotRefused(f"{base['id']}: page/choice slots changed")
            text = segment["translation"]
            if not isinstance(text, str) or not text.strip() or text != text.strip():
                raise PilotRefused(f"{base['id']}: translation must be nonempty and trimmed")
            if any(ord(c) < 32 or c in "\x7f\x85\u2028\u2029" for c in text) or any(
                token in text for token in (SampleScenes.PAGE_BREAK, SampleScenes.OPTION)
            ):
                raise PilotRefused(f"{base['id']}: use the existing segment slots, not delimiters")
        if all(
            a["translation"] == b["translation"]
            for a, b in zip(base["segments"], segments, strict=True)
        ):
            continue
        separator = SampleScenes.OPTION if base["kind"] == "select" else SampleScenes.PAGE_BREAK
        replacement = separator.join(segment["translation"] for segment in segments)
        index = locations[base["id"]]
        physical = lines[index]
        body = physical.rstrip(b"\r\n")
        ending = physical[len(body) :]
        prefix, old = body.rsplit(b"\t", 1)
        # Preserve the English field's outer spaces, plus every byte outside that field.
        left = old[: len(old) - len(old.lstrip())]
        right = old[len(old.rstrip()) :]
        lines[index] = prefix + b"\t" + left + replacement.encode("utf-8") + right + ending
        changed.append(base["id"])
    return b"".join(lines), changed


def validate(data: bytes, source: Path, disc: Path, cells: Path, ids: set[str]) -> dict:
    """The build's actual wrapped pages and the linter's findings, with no second wrapper."""
    work = REPO_ROOT / "work"
    work.mkdir(exist_ok=True)
    # The lint deliberately rereads Row.path through the build loader and for notes.
    # Give both readers the full candidate, never the original or a filtered subset.
    with tempfile.TemporaryDirectory(prefix="review-check-", dir=work) as directory:
        candidate = Path(directory) / source.name
        candidate.write_bytes(data)
        return _validate_file(data, candidate, disc, cells, ids)


def _validate_file(data: bytes, source: Path, disc: Path, cells: Path, ids: set[str]) -> dict:
    store = load_store(disc / "script")
    rows, findings = parse_text(data.decode("utf-8"), source)
    selected = [row for row in rows if row.line_id in ids]
    edits = load_edit_set(cells)
    encoder = edits.encoder
    findings += lint_rows(store, rows, Options(encoder, select_row=edits.select_row))
    archive, walk = load(disc)
    results = lay_out(
        archive,
        walk,
        [row.entry for row in selected if row.has_english],
        encoder,
        DIALOGUE_BAND,
        voice_subtitles=edits.voice_subtitles,
        select_row=edits.select_row,
    )
    by_id = {row.line_id: row for row in selected}
    layouts = []
    for result in results:
        laid = result.laid_out
        box = edits.select_row if by_id[result.line_id].is_select else DIALOGUE_BAND
        layouts.append(
            {
                "id": result.line_id,
                "pages": laid.pages if laid else [],
                "widths_px": laid.widths if laid else [],
                "limits_px": [
                    [
                        box.width_of_line(1 if by_id[result.line_id].is_select else i + 1)
                        for i in range(len(page))
                    ]
                    for page in laid.pages
                ]
                if laid
                else [],
                "problems": result.problems,
            }
        )
    code = b"".join(path.read_bytes() for path in sorted((REPO_ROOT / "boku").glob("*.py")))
    return {
        "text_sha256": digest(data),
        "cells_sha256": digest(cells.read_bytes()),
        "boku_code_sha256": digest(code),
        "selected_ids": sorted(ids),
        "lint_scope": "Complete candidate file, including comments and unchanged events.",
        "has_errors": any(f.is_error for f in findings) or any(r.problems for r in results),
        "findings": [asdict(f) for f in findings],
        "layouts": layouts,
        "empty_voice_rows": [row.line_id for row in selected if not row.has_english],
        "human_review": "Not determined by fit checks.",
    }


def fresh_output(path: Path) -> Path:
    path = path.resolve()
    work = (REPO_ROOT / "work").resolve()
    if path == work or not path.is_relative_to(work):
        raise PilotRefused("pilot output must be a new directory inside this checkout's work/")
    if path.exists():
        raise PilotRefused("output already exists; choose a new directory to preserve it")
    return path


def write_json(path: Path, document: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, ensure_ascii=True, indent=2)
        stream.write("\n")


def run(args: argparse.Namespace) -> int:
    try:
        out = fresh_output(args.out)
        if args.source.suffix != ".txt":
            raise PilotRefused("source must be an event translation .txt file")
        data = args.source.read_bytes()
        store = load_store(args.disc / "script")
        if args.action == "export":
            document = review_document(data, args.source.name, args.events, store)
            report = validate(
                data, args.source, args.disc, args.cells, {row["id"] for row in document["rows"]}
            )
            context = {
                "notice": "Private original-game data. Keep under ignored work/; never upload.",
                "scenes": [store.scenes_by_event[event] for event in document["events"]],
                "original_lines": {
                    row["id"]: store.lines.get(row["id"]) for row in document["rows"]
                },
            }
            out.mkdir(parents=True)
            (out / "source.txt").write_bytes(data)
            write_json(out / "manifest.json", document)
            write_json(out / "review.json", document)
            write_json(out / "context.json", context)
            write_json(out / "fit.json", report)
            print(f"review-pilot: exported {len(document['rows'])} rows to {out}")
        else:
            manifest = json.loads((args.bundle / "manifest.json").read_text(encoding="utf-8"))
            edited = json.loads(
                (args.review or args.bundle / "review.json").read_text(encoding="utf-8")
            )
            if (
                not isinstance(manifest, dict)
                or not isinstance(manifest.get("events"), list)
                or any(not isinstance(event, str) for event in manifest["events"])
            ):
                raise PilotRefused("invalid export manifest or events")
            # Reconstruct immutable fields from the current source and store, not from
            # editable metadata in the exported JSON. Its source hash must still match.
            expected = review_document(data, args.source.name, manifest["events"], store)
            if expected != manifest or (args.bundle / "source.txt").read_bytes() != data:
                raise PilotRefused("source or export manifest changed; export a fresh review")
            candidate, changed = apply_review(data, expected, edited)
            report = validate(
                candidate,
                args.source,
                args.disc,
                args.cells,
                {row["id"] for row in expected["rows"]},
            )
            report["changed_ids"] = changed
            report["byte_identical"] = candidate == data
            out.mkdir(parents=True)
            write_json(out / "fit.json", report)
            write_json(out / "review.json", edited)
            if not report["has_errors"]:
                (out / args.source.name).write_bytes(candidate)
            print(f"review-pilot: {len(changed)} changed row(s); report in {out}")
        if report["has_errors"]:
            print("review-pilot: validation failed; inspect fit.json locally", file=sys.stderr)
            return 1
        return 0
    except (
        PilotRefused,
        StoreMissing,
        ArchiveError,
        BuildRefused,
        SiteError,
        LayoutError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"review-pilot: {error}", file=sys.stderr)
        return 2


def add_arguments(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("export", "import"):
        command = commands.add_parser(action)
        command.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
        command.add_argument("--disc", type=Path, default=DEFAULT_DISC_DIR)
        command.add_argument("--cells", type=Path, default=DEFAULT_CELLS)
        command.add_argument("--out", type=Path, required=True, help="new directory under work/")
        if action == "export":
            command.add_argument("--events", nargs="+", default=DEFAULT_EVENTS)
        else:
            command.add_argument("bundle", type=Path, help="directory from a local export")
            command.add_argument(
                "--review", type=Path, help="edited JSON (default: bundle/review.json)"
            )
        command.set_defaults(run=run)
