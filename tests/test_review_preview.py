"""Workbook imports retain context and use the pilot's structural gates."""

import copy
import csv
import json

import pytest

from boku.review_pilot import PilotRefused, apply_review
from boku.review_preview import HEADERS, REFERENCE_HEADERS, entry_text, read_sheet, workbook_data
from tests import test_review_pilot as fixtures
from tests.test_review_pilot import document


@pytest.fixture
def source():
    return fixtures.source.__wrapped__()


@pytest.fixture
def store(tmp_path):
    return fixtures.store.__wrapped__(tmp_path)


def sheet_rows(manifest):
    rows = []
    for row in manifest["rows"]:
        rows.append(
            [
                row["id"],
                row["speaker"],
                row["upstream_text"],
                "",
                row["review_status"],
                "FITS",
                "1",
                "1",
                "100",
                row["event"],
                f"{row['turn_position']} / {row['turn_count']}",
                row["boundary"],
                str(row["file_event_order"]),
                "",
                row["upstream_text"],
            ]
        )
    return rows


def write_csv(tmp_path, rows, headers=HEADERS):
    path = tmp_path / "sheet.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerows([["Boku review"], [], headers, *rows])
    return path


def test_sheet_noop_keeps_bytes_after_sorting(source, store, tmp_path):
    manifest = document(source, store)
    edited, notes = read_sheet(write_csv(tmp_path, sheet_rows(manifest)[::-1]), manifest)
    assert apply_review(source, manifest, edited) == (source, [])
    assert len(notes) == len(manifest["rows"])


@pytest.mark.parametrize("edit", [False, True])
def test_reference_column_never_enters_translation_or_notes(source, store, tmp_path, edit):
    manifest = document(source, store)
    rows = sheet_rows(manifest)
    if edit:
        rows[0][3] = "Revised. // Another page."
        rows[0][4] = "draft"
        rows[0][13] = "Human review note"
        rows[1][3] = "Which way? | West | East"
    reference = 'Synthetic reference, with "quotes".\nSecond line. // Another page. | Choice'
    rows = [[*row[:2], reference, *row[2:]] for row in rows[::-1]]
    edited, notes = read_sheet(write_csv(tmp_path, rows, REFERENCE_HEADERS), manifest)
    candidate, changed = apply_review(source, manifest, edited)
    if edit:
        assert candidate == source.replace(b"Hello.", b"Revised.").replace(
            b"Left | Right", b"West | East"
        )
        assert changed == ["E0001.0", "E0001.1"]
        assert notes["E0001.0"] == "Human review note"
        assert edited["rows"][0]["review_status"] == "draft"
    else:
        assert (candidate, changed) == (source, [])
    assert "Synthetic reference" not in json.dumps([edited, notes])


def test_reference_column_does_not_weaken_context_checks(source, store, tmp_path):
    manifest = document(source, store)
    rows = [[*row[:2], "Synthetic reference", *row[2:]] for row in sheet_rows(manifest)]
    rows[0][3] = "Changed upstream wording"
    with pytest.raises(PilotRefused, match="context"):
        read_sheet(write_csv(tmp_path, rows, REFERENCE_HEADERS), manifest)


def test_sheet_preserves_notes_and_ignores_forged_fit_cells(source, store, tmp_path):
    manifest = document(source, store)
    rows = sheet_rows(manifest)
    rows[0][3] = "Revised. // Another page."
    rows[0][4] = "draft"
    rows[0][5:9] = ["FITS", "999", "0", "0"]
    rows[0][13] = 'Review note with a comma, and "quotes".\nSecond line.'
    edited, notes = read_sheet(write_csv(tmp_path, rows), manifest)
    candidate, changed = apply_review(source, manifest, edited)
    assert candidate == source.replace(b"Hello.", b"Revised.")
    assert changed == ["E0001.0"]
    assert notes["E0001.0"] == rows[0][13]
    assert edited["rows"][0]["review_status"] == "draft"


@pytest.mark.parametrize("index", [1, 2, 9, 10, 11, 12])
def test_sheet_cannot_change_immutable_context(source, store, tmp_path, index):
    manifest = document(source, store)
    rows = sheet_rows(manifest)
    rows[0][index] = "changed"
    with pytest.raises(PilotRefused, match="context"):
        read_sheet(write_csv(tmp_path, rows), manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda rows: rows.pop(),
        lambda rows: rows.append(rows[0]),
        lambda rows: rows[0].__setitem__(0, "not-an-id"),
        lambda rows: rows[0].__setitem__(3, "Removed a page"),
        lambda rows: rows[1].__setitem__(3, "Question? | One answer"),
        lambda rows: rows[2].__setitem__(3, "New voice subtitle"),
    ],
)
def test_sheet_refuses_lost_rows_or_changed_page_and_choice_shape(
    source, store, tmp_path, mutation
):
    manifest = document(source, store)
    rows = sheet_rows(manifest)
    mutation(rows)
    with pytest.raises(PilotRefused):
        read_sheet(write_csv(tmp_path, rows), manifest)


def test_handling_spaces_and_delimiters_uses_existing_pilot(source, store, tmp_path):
    manifest = document(source, store)
    rows = sheet_rows(manifest)
    rows[0][3] = " Revised. // Another page."
    edited, _ = read_sheet(write_csv(tmp_path, rows), manifest)
    with pytest.raises(PilotRefused, match="trimmed"):
        apply_review(source, manifest, edited)


def test_workbook_uses_exact_report_widths_and_no_original_data(source, store):
    manifest = document(source, store)
    fit = {
        "cells_sha256": "font",
        "boku_code_sha256": "code",
        "text_sha256": "text",
        "findings": [],
        "layouts": [
            {
                "id": "E0001.0",
                "pages": [["Boku: Hello."], ["Another page."]],
                "widths_px": [[91], [101]],
                "limits_px": [[272], [272]],
                "problems": [],
            },
            {
                "id": "E0001.1",
                "pages": [["Which way?", "Left", "Right"]],
                "widths_px": [[73, 24, 31]],
                "limits_px": [[248, 248, 248]],
                "problems": [],
            },
        ],
        "private_original": "MUST NOT APPEAR IN WORKBOOK DATA",
    }
    result = workbook_data(manifest, fit, {})
    assert result["rows"][0]["widest"] == 101
    assert result["pages"][0]["widths"] == [91]
    assert [p["part"] for p in result["pages"]] == [
        "page:1",
        "page:2",
        "prompt:1",
        "option:1",
        "option:2",
    ]
    assert "MUST NOT APPEAR" not in json.dumps(result)
    changed_font = copy.deepcopy(fit)
    changed_font["cells_sha256"] = "new-font"
    assert workbook_data(manifest, changed_font, {})["profile"] != result["profile"]
    assert entry_text(manifest["rows"][1]) == "Which way? | Left | Right"


def test_bad_layout_never_gets_a_pass_status(source, store):
    manifest = document(source, store)
    fit = {
        "cells_sha256": "font",
        "boku_code_sha256": "code",
        "text_sha256": "text",
        "findings": [{"line_id": "E0001.0", "severity": "ERROR"}],
        "layouts": [],
    }
    assert workbook_data(manifest, fit, {})["rows"][0]["fit"] == "ERROR"
