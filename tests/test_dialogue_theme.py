"""Run the assembled shared glyph drawer: dialogue alone becomes single-pass white.

Needs the private import and armips; no game bytes or glyphs are fixtures in this file.
The interpreter enforces R3000 branch/load delays and executes the SDK primitive writers.
"""

from pathlib import Path

import pytest

from boku.archive import EXE_NAME
from boku.build import load_edit_set
from tests.mips import STOP, Machine
from tests.test_vwf_prototype import NEEDS_ARMIPS, prototype_arguments, vwf_prototype


@pytest.fixture(scope="module")
def themes(disc_dir: Path, archive, tmp_path_factory):
    if not vwf_prototype().DEFAULT_ARMIPS.exists():
        pytest.skip("needs armips")
    results = {}
    for theme in ("light", "dark"):
        out = tmp_path_factory.mktemp(f"theme-{theme}")
        tool = vwf_prototype()
        tool.build(
            prototype_arguments(
                tool, out, disc=str(disc_dir), edits_only=True, dialogue_theme=theme
            )
        )
        edits = load_edit_set(out / tool.EDITS_NAME)
        exe = bytearray(archive.exe)
        for edit in edits.edits:
            if edit.file == EXE_NAME:
                assert exe[edit.offset : edit.end] == edit.old
                exe[edit.offset : edit.end] = edit.new
        results[theme] = bytes(exe), edits
    return results


def glyph(exe, dialogue, light, rgb=(16, 32, 48)):
    m = Machine()
    m.load(0x80010000, exe[0x800:])
    # Machine normally stubs glyph_draw. Enter one instruction later and supply the
    # displaced move a3,a0 in the jal delay slot, so its real body runs here instead.
    caller = 0x8002BF54 if dialogue else 0x801E0000
    if dialogue:
        assert m.read(caller, 4) == 0x0C000000 | ((0x8002BA2C >> 2) & 0x3FFFFFF)
    m.write(caller, 4, 0x0C000000 | ((0x8002BA30 >> 2) & 0x3FFFFFF))
    m.write(caller + 4, 4, 0x00803821)  # move a3,a0
    m.write(caller + 8, 4, 0x08000000 | ((STOP >> 2) & 0x3FFFFFF))
    m.write(caller + 12, 4, 0)
    m.write(0x80028E3C, 4, 1)  # text OT layer
    m.write(0x8002593C, 4, 0x801C0000)  # ordering table
    m.write(0x800258F0, 4, 0x801D0000)  # primitive allocation head
    m.write(0x801C0004, 4, 0xFFFFFF)
    m.load(0x800359E0, bytes(rgb))
    m.write(0x800359E4, 4, 0x10 | (4 if light else 0))
    saved = {reg: 0x12340000 + reg for reg in (*range(16, 24), 30)}
    m.call(caller, 65, 24, 193, registers=saved)
    assert all(m.regs[reg] == value for reg, value in saved.items())
    assert m.regs[29] == 0x801FFF00
    assert bytes(m.ram[0x359E0:0x359E3]) == bytes(rgb)
    assert m.read(0x800359E4, 4) == 0x10 | (4 if light else 0)
    end = m.read(0x800258F0, 4)
    return bytes(m.ram[0x1D0000 : end - 0x80000000])


@NEEDS_ARMIPS
@pytest.mark.parametrize("light", [False, True])
def test_dialogue_is_white_without_changing_other_callers_or_shared_state(themes, light):
    plain, dark = themes["light"][0], themes["dark"][0]
    ordinary = glyph(plain, False, light)
    assert glyph(dark, False, light) == ordinary  # menu colours, shadows, UVs and OT links
    assert len(ordinary) == 3 * 20
    before = glyph(plain, True, light)
    after = glyph(dark, True, light)
    assert len(after) == 20  # exactly one sprite, no gray duplicates
    assert after[4:7] == b"\xff\xff\xff"
    assert after[7:] == before[7:20]  # same command, position, UVs, size, CLUT


def test_theme_preserves_font_metrics_and_translation_storage(themes):
    light, dark = (themes[name][1] for name in ("light", "dark"))
    assert light.encoder.cells == dark.encoder.cells
    assert light.select_row == dark.select_row
    assert light.array_regions == dark.array_regions
    assert light.sectors == dark.sectors
    assert [e for e in light.edits if e.file != EXE_NAME] == [
        e for e in dark.edits if e.file != EXE_NAME
    ]


@pytest.mark.parametrize(
    "visible,level", [(True, n) for n in range(7)] + [(False, n) for n in range(7)]
)
def test_panel_is_average_black_at_all_visible_levels_and_disappears(themes, visible, level):
    m = Machine()
    m.load(0x80010000, themes["dark"][0][0x800:])
    m.write(0x8002911E, 1, int(visible))
    m.write(0x80036541, 1, level)
    m.write(0x800258F0, 4, 0x801D0000)
    m.write(0x8002593C, 4, 0x801C0000)
    m.write(0x801C0008, 4, 0xFFFFFF)
    m.call(0x8002E964)
    expected_level = min(level + 1, 6) if visible else max(level - 1, 0)
    assert m.read(0x80036541, 1) == expected_level
    if expected_level == 0:
        assert m.read(0x800258F0, 4) == 0x801D0000
    else:
        assert m.read(0x801D0004, 4) == 0x62000000  # semitransparent black TILE
        assert m.read(0x801D0038, 4) == 0xE1000200  # draw mode, ABR 0
        assert [m.read(0x801D0008 + 2 * i, 2) for i in range(4)] == [0, 191, 330, 37]
