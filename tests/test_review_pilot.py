"""Lossless review addressing and refusal gates, using invented English only."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from boku import review_pilot as pilot
from boku.cli import build_parser
from boku.layout import SELECT_ROW
from boku.lint import _check_loader_agreement
from boku.script_store import Store


@pytest.fixture
def store(tmp_path):
    return Store(
        index={},
        lines={
            "E0001.0": {},
            "E0001.1": {"select": {"lines": 3, "prompt_lines": 1}},
            "E0002.0": {},
        },
        scenes=(
            {"event": "E0001", "lines": ["E0001.0", "E0001.1"], "nodes": [{"line": "E0001.2"}]},
            {"event": "E0002", "lines": ["E0002.0"], "nodes": []},
        ),
        root=tmp_path,
    )


@pytest.fixture
def source():
    # Mixed physical line endings, UTF-8, outer spacing and no final newline are intentional.
    return (
        "# Context: a made-up conversation.\r\n\r\n"
        "# --- E0001: test room\r\n"
        "E0001.0\t Boku \t  Hello. // Another page.  \r\n"
        "# NOTE E0001.0: preserve this comment.\n"
        "E0001.1\t[SEL]\tWhich way? | Left | Right\n"
        "E0001.2\t(voice only)\r\n"
        "\r\n# --- E0002: elsewhere\n"
        "E0002.0\tAunt\tCaf\u00e9."
    ).encode()


def document(source, store):
    return pilot.review_document(source, "day01.txt", ["E0001", "E0002"], store)


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_noop_preserves_every_byte_even_after_json_sorting(source, store, bom):
    source = bom + source
    base = document(source, store)
    edited = json.loads(json.dumps(base))
    edited["rows"].reverse()
    candidate, changed = pilot.apply_review(source, base, edited)
    assert candidate == source
    assert changed == []


def test_change_only_one_text_field_keep_other_pages_comments_and_spacing(source, store):
    base = document(source, store)
    edited = copy.deepcopy(base)
    edited["rows"][0]["segments"][1]["translation"] = "A revised page."
    edited["rows"][0]["review_status"] = "draft"
    candidate, changed = pilot.apply_review(source, base, edited)
    assert candidate == source.replace(b"Another page.", b"A revised page.")
    assert changed == ["E0001.0"]


def test_choices_separate_prompts_from_answers_and_preserve_order(source, store):
    base = document(source, store)
    edited = copy.deepcopy(base)
    choice = edited["rows"][1]
    assert [s["slot"] for s in choice["segments"]] == ["prompt:1", "option:1", "option:2"]
    choice["segments"][1]["translation"] = "West"
    candidate, changed = pilot.apply_review(source, base, edited)
    assert candidate == source.replace(b" | Left | ", b" | West | ")
    assert changed == ["E0001.1"]


def test_review_status_never_changes_translation_bytes(source, store):
    base = document(source, store)
    edited = copy.deepcopy(base)
    edited["rows"][0]["review_status"] = "needs-revision"
    assert pilot.apply_review(source, base, edited) == (source, [])
    assert [r["boundary"] for r in base["rows"]] == ["start", "continue", "end", "single"]
    assert all(r["review_status"] == "unreviewed" for r in base["rows"])
    assert base["rows"][2]["segments"] == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["rows"].pop(),
        lambda d: d["rows"].append(d["rows"][0]),
        lambda d: d["rows"][0].update(id="E0003.0"),
        lambda d: d["rows"][0].update(speaker="Uncle"),
        lambda d: d["rows"][0].update(upstream_text="Tampered"),
        lambda d: d["rows"][0].update(review_status="rendered"),
        lambda d: d["rows"][0]["segments"].pop(),
        lambda d: d["rows"][1]["segments"].reverse(),
        lambda d: d["rows"][0]["segments"][0].update(base="Tampered"),
        lambda d: d["rows"][2]["segments"].append({"slot": "page:1", "translation": "Voice"}),
        lambda d: d.update(events=["E0002"]),
        lambda d: d.update(source_name="../../outside.txt"),
        lambda d: d.update(schema="unknown"),
    ],
)
def test_immutable_shape_and_addressing_cannot_be_changed(source, store, mutation):
    base = document(source, store)
    edited = copy.deepcopy(base)
    mutation(edited)
    with pytest.raises(pilot.PilotRefused):
        pilot.apply_review(source, base, edited)


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        " padded",
        "text\tfield",
        "text\nrow",
        "a // b",
        "a | b",
        "text\u2028row",
        "nul\x00byte",
        None,
        12,
    ],
)
def test_unsafe_segment_content_is_refused(source, store, text):
    base = document(source, store)
    edited = copy.deepcopy(base)
    edited["rows"][0]["segments"][0]["translation"] = text
    with pytest.raises(pilot.PilotRefused):
        pilot.apply_review(source, base, edited)


def test_stale_source_and_incomplete_events_are_refused(source, store):
    base = document(source, store)
    with pytest.raises(pilot.PilotRefused, match="source changed"):
        pilot.apply_review(source + b"\n", base, base)
    with pytest.raises(pilot.PilotRefused, match="complete event"):
        document(source.replace(b"E0001.2\t(voice only)\r\n", b""), store)
    with pytest.raises(pilot.PilotRefused, match="duplicate id"):
        document(source.replace(b"E0001.2\t(voice only)", b"E0001.1\t(voice only)"), store)


def test_outputs_stay_in_fresh_local_work_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, "REPO_ROOT", tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    assert pilot.fresh_output(work / "new") == work / "new"
    for path in (work, tmp_path / "translation", work / ".." / "outside", work / "existing"):
        if path.name == "existing":
            path.mkdir()
        with pytest.raises(pilot.PilotRefused):
            pilot.fresh_output(path)


def test_cli_export_import_and_failed_validation_preserve_files(
    source, store, tmp_path, monkeypatch
):
    monkeypatch.setattr(pilot, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pilot, "load_store", lambda _: store)
    monkeypatch.setattr(pilot, "validate", lambda *args: {"has_errors": False})
    path = tmp_path / "day01.txt"
    path.write_bytes(source)
    bundle = tmp_path / "work" / "export"
    staged = tmp_path / "work" / "staged"
    common = ["--source", str(path), "--disc", str(tmp_path), "--cells", str(tmp_path / "cells")]
    parser = build_parser()

    def run(*args):
        parsed = parser.parse_args(["review-pilot", *args, *common])
        return parsed.run(parsed)

    assert run("export", "--events", "E0001", "E0002", "--out", str(bundle)) == 0
    assert run("import", str(bundle), "--out", str(staged)) == 0
    assert (staged / path.name).read_bytes() == source
    assert run("import", str(bundle), "--out", str(staged)) == 2
    assert (staged / path.name).read_bytes() == source

    edited = json.loads((bundle / "review.json").read_text())
    edited["rows"][0]["segments"][0]["translation"] = "Revised."
    (bundle / "review.json").write_text(json.dumps(edited))
    monkeypatch.setattr(pilot, "validate", lambda *args: {"has_errors": True})
    failed = tmp_path / "work" / "failed"
    assert run("import", str(bundle), "--out", str(failed)) == 1
    assert (failed / "fit.json").is_file()
    assert not (failed / path.name).exists()
    assert path.read_bytes() == source

    path.write_bytes(source + b"\n")
    stale = tmp_path / "work" / "stale"
    assert run("import", str(bundle), "--out", str(stale)) == 2
    assert not stale.exists()


def test_readonly_manifest_prevents_dropping_an_entire_event(source, store, tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pilot, "load_store", lambda _: store)
    monkeypatch.setattr(pilot, "validate", lambda *args: {"has_errors": False})
    source_path = tmp_path / "day01.txt"
    source_path.write_bytes(source)
    bundle = tmp_path / "work" / "bundle"
    bundle.mkdir(parents=True)
    manifest = document(source, store)
    pilot.write_json(bundle / "manifest.json", manifest)
    (bundle / "source.txt").write_bytes(source)
    manifest["events"].pop()
    manifest["rows"].pop()
    pilot.write_json(bundle / "review.json", manifest)
    output = tmp_path / "work" / "output"
    args = build_parser().parse_args(
        [
            "review-pilot",
            "import",
            str(bundle),
            "--source",
            str(source_path),
            "--disc",
            str(tmp_path),
            "--out",
            str(output),
        ]
    )
    assert args.run(args) == 2
    assert not output.exists()


def test_no_original_game_data_is_needed_for_round_trip(source, store):
    assert all("text" not in record for record in store.lines.values())
    base = document(source, store)
    assert pilot.apply_review(source, base, base)[0] == source


def test_lint_rereads_full_candidate_instead_of_original_or_selected_subset(
    source, store, tmp_path, monkeypatch
):
    monkeypatch.setattr(pilot, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pilot, "load_store", lambda _: store)
    monkeypatch.setattr(pilot, "load", lambda _: (None, None))
    monkeypatch.setattr(pilot, "lay_out", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        pilot,
        "load_edit_set",
        lambda _: SimpleNamespace(encoder=None, select_row=SELECT_ROW, voice_subtitles=False),
    )
    read_paths = []

    def lint(store, rows, options):
        assert {row.line_id for row in rows} == {"E0001.0", "E0001.1", "E0001.2", "E0002.0"}
        assert rows[0].text.startswith("Revised.")
        read_paths.append(rows[0].path)
        return list(_check_loader_agreement(rows))

    monkeypatch.setattr(pilot, "lint_rows", lint)
    path = tmp_path / "day01.txt"
    path.write_bytes(source)
    cells = tmp_path / "cells.json"
    cells.write_text("{}")
    result = pilot.validate(
        source.replace(b"Hello.", b"Revised."), path, tmp_path, cells, {"E0001.0"}
    )
    assert not result["has_errors"]
    assert result["findings"] == []
    assert path.read_bytes() == source
    assert read_paths and not read_paths[0].exists()
