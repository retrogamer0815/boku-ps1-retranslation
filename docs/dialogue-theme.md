# Dark dialogue appearance

The renderer can use the earlier experimental project's dark dialogue appearance:
single-pass white glyphs over a semi-transparent black panel. The implementation is
part of this fork's assembly renderer; it does not import the old patch engine.

Standard `./make.sh build-days` and release builds select the dark theme, starting with
the Day 1 prerelease `v0.0.2-day1.1`. The earlier `v0.0.1-testpilot.1` keeps its light
appearance. To build a separate dark candidate from an imported original disc:

```sh
uv run python tools/vwf/build_prototype.py --edits-only --dialogue-theme dark \
  --out work/dark-dialogue/vwf
uv run boku build disc/image.img --disc disc --vwf work/dark-dialogue/vwf/edits.json \
  --translation translation/days --textures translation/textures \
  --out work/dark-dialogue/build --name dark-dialogue
```

Open `work/dark-dialogue/build/image.cue` in the emulator. Cold boot the image; an existing
emulator save state may still hold the previous executable. A memory-card save after a
fresh boot is suitable. The commands leave previous builds and the imported disc alone.
Use the intended staged translation directory instead of `translation/days` when testing
unmerged spreadsheet edits.

For a light control build, use `--dialogue-theme light` in the first command, then build
with the resulting edit set. The low-level prototype tool still defaults to `light`
when that switch is omitted; the standard build entry point selects `dark` explicitly.

## Appearance and boundaries

The dark panel uses the PS1's average blend (ABR 0), with black as its foreground:
`(background + black) / 2`. It preserves the scene at half brightness. The panel retains
the current position and size, y=191 and height=37; it does not reinstate the older
project's taller box. This is a fixed hardware blend, not an arbitrary opacity slider.

The visibility clock, linger time and page timing are unchanged. At every visible level
the dark panel has the same opacity: the upstream additive fade becomes a fixed-opacity
appearance/disappearance. This prevents a pale flash during transitions. The theme
overrides the build's `--band-brightness` and `--band-blend` settings.

Only glyphs drawn by `dialog_draw` become single-pass white (RGB 255). This includes
ordinary dialogue, ant counts and voice-clip subtitles drawn in the dialogue band.
Shared menu glyphs retain their colours and shadows, and horizontal choices retain their
existing white-on-dark appearance. Movie subtitles use their existing renderer.

The font cells, advances, wrapping, three-line limit, pencil reservation, speaker labels,
page breaks, and translated text are unchanged. **The spreadsheet's fit results remain
valid, and removing the shadow does not grant extra text capacity.** Repository mockups
read the theme from the edit set and omit the dialogue shadow for dark builds. Their flat
background and overflow/pencil markings are diagnostic; emulator captures show the
actual scene beneath the panel.

```sh
uv run python tools/vwf/mockup.py translation/days/day01.txt \
  --edits work/dark-dialogue/vwf/edits.json --out work/dark-dialogue/mockup
uv run pytest tests/test_dialogue_theme.py tests/test_mockup.py tests/test_vwf_prototype.py
```

## Implementation checks

`asm/dialogue_theme.asm` patches the panel's fade entries and draw-mode argument.
`glyph_draw` checks its caller against `dialog_draw`'s return address before choosing
white ink and skipping the two shadow sprites. It leaves shared text globals untouched.
The two helpers occupy 100 bytes in the already reserved debug-font code island, bounded
by an assembler `.area`; translated-array relocation space is unchanged.

The original-code assembly pass validates every patch site against the private import.
The tests execute the assembled glyph and panel routines with R3000 branch and load
delays, check register/global preservation, compare non-dialogue primitive packets,
exercise all panel levels, and compare both themes' font metrics and relocation regions.
Both builds use the usual layout refusal and sector-integrity checks.

Disc images, BIOS files, font images and emulator captures remain local under ignored
directories. A distributable test package contains an xdelta patch and instructions.
