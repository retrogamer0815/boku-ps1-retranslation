"""Native Sheets pixel-preview formulas with repository layout parity fixtures.

This is a translator preview, not the translation linter or a build approval.
Only font advances and layout facts are exported, never glyph images or disc bytes.
Recheck native Sheets against layout.wrap whenever the font or formula profile changes.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import asdict

from boku import layout
from boku.glyphs import GlyphTable
from boku.script_store import original_bytes
from boku.translation import SampleScenes

METRICS = "_Font metrics"
ENTRIES = "_Live fit"
PAGES = "_Live pages"


def literal(text: str) -> str:
    """Quote a Sheets string literal, not a formula or an A1 address."""
    return '"' + text.replace('"', '""') + '"'


def profile(manifest: dict, store, encoder, select_box=layout.SELECT_ROW) -> dict:
    table = GlyphTable.load()
    message_encoder = layout.WithSheetSymbols(encoder)
    candidates = set(encoder.cells) | set(table.from_character)
    metrics = [
        [
            ord(char),
            char,
            message_encoder.advance(char),
            int(char.isalnum()),
            int(encoder.glyph(char) is not None),
        ]
        for char in sorted(candidates, key=ord)
        if message_encoder.glyph(char) is not None
    ]
    if any(row[2] <= 0 for row in metrics):
        raise ValueError("the live preview requires positive glyph advances")
    rows = []
    for row in manifest["rows"]:
        opening = closing = ""
        if row["kind"] == "message":
            marks = layout.original_marks(original_bytes(store.lines[row["id"]], table), table)
            if marks.problem:
                raise ValueError(marks.problem)
            name, unknown = layout.speaker_label(row["speaker"]) if marks.labelled else ("", [])
            if unknown:
                raise ValueError("unknown speaker label")
            opening, closing = name + marks.opening, marks.closing
        rows.append({**row, "opening": opening, "closing": closing})
    result = {
        "schema": "boku-live-sheet-v1",
        "metrics": metrics,
        "dialogue": asdict(layout.DIALOGUE_BAND),
        "choice": asdict(select_box),
        "fallback_advance": encoder.fixed_advance,
        "wrap_sha256": hashlib.sha256(inspect.getsource(layout.wrap).encode()).hexdigest(),
        "rows": rows,
    }
    result["profile_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True).encode()
    ).hexdigest()
    return result


def pixel_lambda(last_metric: int) -> str:
    return (
        "LAMBDA(run,IF(LEN(run)=0,0,SUM(MAP(SEQUENCE(LEN(run)),LAMBDA(pos,"
        f"IFNA(VLOOKUP(UNICODE(MID(run,pos,1)),'{METRICS}'!$A$2:$E${last_metric},"
        f"3,FALSE),'{METRICS}'!$G$7))))))"
    )


def pixel_formula(text: str, last_metric: int) -> str:
    return f"=LET(px,{pixel_lambda(last_metric)},px({text}))"


def wrap_formula(text: str, last_metric: int) -> str:
    """The single-paragraph layout.wrap loop as LET/REDUCE; inputs reject controls.

    State is (all wrapped text, current line width, current line number). The
    hyphen decision is made once per word at its starting line, just as Python
    does, including the transition from the second line to the narrower third.
    Code-point lookups avoid Sheets' case-insensitive text matching.
    """
    return (
        f"=LET(txt,{text},px,{pixel_lambda(last_metric)},"
        "alnum,LAMBDA(ch,IF(LEN(ch)=0,FALSE,IFNA(VLOOKUP(UNICODE(ch),"
        f"'{METRICS}'!$A$2:$E${last_metric},4,FALSE),0)=1)),"
        f"lim,LAMBDA(line,IF(AND('{METRICS}'!$G$4>0,line>='{METRICS}'!$G$4),"
        f"'{METRICS}'!$G$5,'{METRICS}'!$G$2)),"
        'IF(LEN(txt)=0,"",INDEX(REDUCE(HSTACK("",0,1),SPLIT(txt," ",FALSE,FALSE),'
        "LAMBDA(state,word,LET("
        "parts,IF(px(word)>lim(INDEX(state,1,3)),"
        'SPLIT(TEXTJOIN("",TRUE,MAP(SEQUENCE(LEN(word)),LAMBDA(pos,'
        'MID(word,pos,1)&IF(AND(MID(word,pos,1)="-",'
        'alnum(IF(pos>1,MID(word,pos-1,1),"")),alnum(MID(word,pos+1,1))),'
        'UNICHAR(57344),"")))),UNICHAR(57344),FALSE,FALSE),word),'
        "REDUCE(state,SEQUENCE(COLUMNS(parts)),LAMBDA(acc,partno,LET("
        "piece,INDEX(parts,1,partno),width,px(piece),"
        "current,INDEX(acc,1,2),lineno,INDEX(acc,1,3),"
        'space,IF(AND(partno=1,current>0)," ",""),'
        "candidate,current+px(space)+width,"
        "over,AND(current>0,candidate>lim(lineno)),"
        "HSTACK(INDEX(acc,1,1)&IF(over,CHAR(10),space)&piece,"
        "IF(over,width,candidate),lineno+IF(over,1,0))"
        ")))))),1,1)))"
    )


def width_list_formula(text: str, last_metric: int) -> str:
    return (
        f"=LET(txt,{text},px,{pixel_lambda(last_metric)},"
        'IF(LEN(txt)=0,"",TEXTJOIN(",",FALSE,MAP(SPLIT(txt,CHAR(10),FALSE,FALSE),'
        "LAMBDA(line,px(line))))))"
    )


def input_formula(text: str, kind: str, count: int, last_metric: int) -> str:
    """Reject structural changes before calculating a fit; no silent trimming."""
    if kind == "voice-only":
        return f'=IF(LEN({text})=0,"NO SUBTITLE","VOICE-ONLY ROW")'
    separator = SampleScenes.OPTION if kind == "select" else SampleScenes.PAGE_BREAK
    other = SampleScenes.PAGE_BREAK if kind == "select" else SampleScenes.OPTION
    count_error = "CHOICE COUNT ERROR" if kind == "select" else "PAGE COUNT ERROR"
    allowed = 5 if kind == "select" else 3
    return (
        f'=LET(txt,{text},IF(LEN(txt)=0,"EMPTY TEXT",'
        f"LET(parts,SPLIT(txt,{literal(separator)},FALSE,FALSE),"
        f"IF(COLUMNS(parts)<>{count},{literal(count_error)},"
        "IF(SUM(MAP(SEQUENCE(LEN(txt)),LAMBDA(pos,LET(code,UNICODE(MID(txt,pos,1)),"
        "IF(OR(code<32,code=127,code=133,code=8232,code=8233),1,0)))))>0,"
        '"REMOVE LINE BREAKS / CONTROLS",'
        "IF(SUM(MAP(parts,LAMBDA(part,IF(OR(LEN(part)=0,"
        'REGEXMATCH(part,"^\\s|\\s$")),1,0))))>0,"EMPTY / OUTER SPACES",'
        f'IF(ISNUMBER(FIND({literal(other)},txt)),"WRONG DELIMITER",'
        "IF(SUM(MAP(SEQUENCE(LEN(txt)),LAMBDA(pos,IF(IFNA(VLOOKUP("
        f"UNICODE(MID(txt,pos,1)),'{METRICS}'!$A$2:$E${last_metric},"
        f'{allowed},FALSE),0)>0,0,1))))>0,"UNSUPPORTED CHARACTER","OK"))))))))'
    )


def workbook_formulas(data: dict) -> dict:
    """Build finite matrices for an existing review Sheet with Japanese column C.

    No network writes. Callers must obtain authorization for private numerical
    metrics before publishing the result. Editable cells are never in the payload.
    The generated formulas depend only on the included, versioned layout profile.

    Write metrics/config as literal values (the character '=' is not a formula).
    In entries/pages, headers and the first seven/two columns are literal values;
    the remaining body cells and the two visible blocks are formula values.
    """
    last_metric = len(data["metrics"]) + 1
    last_entry = len(data["rows"]) + 1
    total_pages = sum(len(row["segments"]) for row in data["rows"])
    last_page = total_pages + 1
    metrics = [["Code point", "Character", "Advance px", "Alphanumeric", "Choice font"]]
    metrics += data["metrics"]
    config = [
        ["Profile SHA-256", data["profile_sha256"]],
        ["Dialogue width", data["dialogue"]["width"]],
        ["Dialogue lines", data["dialogue"]["lines"]],
        ["Guard starts at line", data["dialogue"]["guarded_from"]],
        ["Guarded width", data["dialogue"]["guarded_width"]],
        ["Choice width", data["choice"]["width"]],
        ["Fallback advance", data["fallback_advance"]],
    ]
    entries = [
        [
            "ID",
            "Kind",
            "Parts",
            "Speaker",
            "Upstream English",
            "Opening",
            "Closing",
            "Effective English",
            "Input status",
            "Pixel fit",
            "Pages",
            "Lines",
            "Widest px",
        ]
    ]
    pages = [
        [
            "ID",
            "Part",
            "Dressed text",
            "Wrapped text",
            "Line 1 px",
            "Line 2 px",
            "Line 3 px",
            "Lines",
            "Widest px",
            "Overflow px",
            "Fit",
            "All widths px",
        ]
    ]
    main = []
    preview = []
    for n, row in enumerate(data["rows"], 2):
        count = len(row["segments"])
        source_range = "'Translation Batch'!$A$7:$P$1000"
        id_range = "'Translation Batch'!$A$7:$A$1000"
        lookup = f"pos,MATCH(A{n},{id_range},0),src,LAMBDA(col,INDEX({source_range},pos,col))"
        fixed = {
            1: row["id"],
            2: row["speaker"],
            4: row["upstream_text"],
            11: row["event"],
            12: f"{row['turn_position']} / {row['turn_count']}",
            13: row["boundary"],
            14: str(row["file_event_order"]),
        }
        context = ",".join(
            f"EXACT(TO_TEXT(src({col})),{literal(value)})" for col, value in fixed.items()
        )
        gate = input_formula(f"H{n}", row["kind"], count, last_metric)[1:]
        context_gate = (
            f"=IFERROR(LET({lookup},IF(AND(COUNTIF({id_range},A{n})=1,"
            f"COUNTA({id_range})={len(data['rows'])},{context}),{gate},"
            '"CONTEXT ERROR")),"CONTEXT ERROR")'
        )
        first_page = len(pages) + 1
        for part_no, segment in enumerate(row["segments"], 1):
            p = len(pages) + 1
            ready = f"'{ENTRIES}'!I{n}=\"OK\""
            separator = SampleScenes.OPTION if row["kind"] == "select" else SampleScenes.PAGE_BREAK
            part = f"INDEX(SPLIT('{ENTRIES}'!H{n},{literal(separator)},FALSE,FALSE),1,{part_no})"
            dressed = (f"'{ENTRIES}'!F{n}&" if part_no == 1 else "") + part
            if part_no == count:
                dressed += f"&'{ENTRIES}'!G{n}"
            wrapped = f"C{p}" if row["kind"] == "select" else wrap_formula(f"C{p}", last_metric)[1:]
            widths = width_list_formula(f"D{p}", last_metric)[1:]
            limits = (
                f"'{METRICS}'!$G$6"
                if row["kind"] == "select"
                else (
                    f"IF(AND('{METRICS}'!$G$4>0,line>='{METRICS}'!$G$4),"
                    f"'{METRICS}'!$G$5,'{METRICS}'!$G$2)"
                )
            )
            max_lines = "1" if row["kind"] == "select" else f"'{METRICS}'!$G$3"
            pages.append(
                [
                    row["id"],
                    segment["slot"],
                    f'=IF({ready},{dressed},"")',
                    f'=IF({ready},{wrapped},"")',
                    *[
                        f'=IF({ready},IF(H{p}>={line},VALUE(INDEX(SPLIT(L{p},","),1,{line})),""),"")'
                        for line in range(1, 4)
                    ],
                    f'=IF({ready},1+LEN(D{p})-LEN(SUBSTITUTE(D{p},CHAR(10),"")),"")',
                    f'=IF({ready},MAX(ARRAYFORMULA(VALUE(SPLIT(L{p},",")))),"")',
                    f'=IF({ready},MAX(0,MAP(SEQUENCE(H{p}),LAMBDA(line,VALUE(INDEX(SPLIT(L{p},","),1,line))-{limits}))),"")',
                    f'=IF({ready},IF(OR(H{p}>{max_lines},J{p}>0),"OVERFLOW","FITS"),\'{ENTRIES}\'!I{n})',
                    f'=IF({ready},{widths},"")',
                ]
            )
            preview_box = layout.BoxSpec(
                **data["choice" if row["kind"] == "select" else "dialogue"]
            )
            preview.append(
                [
                    f"='{PAGES}'!D{p}",
                    *[f"='{PAGES}'!{col}{p}" for col in "EFG"],
                    *[
                        f"=IF(AND(ISNUMBER('{PAGES}'!H{p}),'{PAGES}'!H{p}>={line}),"
                        f'{preview_box.width_of_line(line)},"")'
                        for line in range(1, 4)
                    ],
                    f"='{PAGES}'!K{p}",
                ]
            )
        end_page = len(pages)
        status = f"=I{n}"
        page_count = line_count = widest = '=""'
        if count:
            status = (
                f'=IF(I{n}<>"OK",I{n},IF(COUNTIF('
                f'\'{PAGES}\'!K{first_page}:K{end_page},"FITS")={count},"FITS","OVERFLOW"))'
            )
            page_count = f'=IF(I{n}="OK",{1 if row["kind"] == "select" else count},"")'
            line_count = f'=IF(I{n}="OK",SUM(\'{PAGES}\'!H{first_page}:H{end_page}),"")'
            widest = f'=IF(I{n}="OK",MAX(\'{PAGES}\'!I{first_page}:I{end_page}),"")'
        entries.append(
            [
                row["id"],
                row["kind"],
                count,
                row["speaker"],
                row["upstream_text"],
                row["opening"],
                row["closing"],
                f'=IFERROR(LET({lookup},IF(LEN(src(5))=0,src(4),src(5))),"")',
                context_gate,
                status,
                page_count,
                line_count,
                widest,
            ]
        )
        main_row = n + 5
        main.append(
            [
                f"=IFERROR(INDEX('{ENTRIES}'!${col}$2:${col}${last_entry},"
                f"MATCH(A{main_row},'{ENTRIES}'!$A$2:$A${last_entry},0)),"
                f"{literal('CONTEXT ERROR' if col == 'J' else '')})"
                for col in "JKLM"
            ]
        )
    return {
        "metrics": metrics,
        "config": config,
        "entries": entries,
        "pages": pages,
        "main_g_to_j": main,
        "preview_c_to_j": preview,
        "entry_rows": last_entry,
        "page_rows": last_page,
    }
