## Day 1 retranslation and dark dialogue

This prerelease expands the human translation from the earlier 13-entry pilot to the
full Day 1 chapter file: **85 translatable entries across 25 events, with 83 marked
human-reviewed and two still draft**. The reviewed English was prepared by a
Japanese-fluent contributor using the original Japanese as reference.

The batch covers the arrival and family introductions, Boku's room and futon,
conversations around the house and garden, dinner, and the evening conversations about
the collecting kit, model airplane and television. E0121.5 and E0121.6, in the laundry
conversation, remain drafts. The wordless E0184.2 entry remains unsubtitled.

Day 2's review workbook is prepared, but no Day 2 human revision is included yet. Later
days, shared interactions, menus, movies and illustrated text retain the upstream
translation unless listed in `translation/human-review.tsv`.

### Window and text design

Dialogue now uses **white proportional text over a translucent black window**. The
background remains visible at half brightness, and dialogue glyphs use one crisp white
pass without the previous shadow. The compact window keeps its existing position and
size. The visibility timing is unchanged; the window appears at a fixed opacity.

The proportional font, wrapping, page breaks, speaker labels and three-line capacity are
unchanged, so existing spreadsheet fit checks still apply. Horizontal choices retain
their white-on-dark design. Shared menus and movie subtitles keep their existing styling.

### Review status

All 122 Day 1 page/choice previews match the repository's wrapping and width checks.
The candidate passed build and image-readback checks and targeted Beetle PSX testing.
Full Day 1 emulator review and real-hardware testing remain pending. Seven non-blocking
wording warnings remain documented alongside the two drafts. This is a test prerelease
of an ongoing retranslation, not a fully human-reviewed translation of the whole game.

The download applies directly to the matching original Japanese image. An upstream v1
image or an earlier English patch is not required. A fresh emulator boot is recommended;
old save states can retain the previous executable and scripts.

## Build

An English translation patch for the PlayStation original of *Boku no Natsuyasumi*
(SCPS-10088, 2000). Version $version, built from commit `$commit` ($built_from).

The patch requires a legally obtained dump of the original Japanese disc. Game images and
BIOS files are not included.

## What is in English

$coverage These unit statuses describe the upstream workflow; human-review coverage is
recorded separately in `translation/human-review.tsv`. The original Japanese voices are
retained with English subtitles.

## Download

`$bundle` contains:

* `$xdelta` — the patch (xdelta3).
* `$cue` — the cue sheet for the patched image.
* `PATCH.json` and `README.txt` — patch metadata, checksums and application instructions.
* `RELEASE-NOTES.md` — the release notes included at publication.

## Requirements

A raw dump of the Japanese disc containing one MODE2/2352 track, matching Redump ($redump).
The original image must match the following checksums before patching:

$original_table

## How to apply it

1. **Extract** a CHD to a raw image ([chdman](https://docs.mamedev.org/tools/chdman.html)
   ships with MAME; `brew install rom-tools` on macOS):

   ```
   chdman extractcd -i "original.chd" -o "$base_stem.cue" -ob "$base_name"
   ```

   Here, `original.chd` is a placeholder for the source CHD filename. A BIN/CUE dump needs
   no extraction; use its `.bin`. The patch does not apply directly to a `.chd` or an `.iso`
   with 2048-byte sectors.

2. **Hash** the image and compare its SHA-1 with `$base_sha1`:

   ```
   # macOS
   shasum -a 1 "$base_name"
   # Linux
   sha1sum "$base_name"
   # Windows
   certutil -hashfile "$base_name" SHA1
   ```

3. **Patch** it with [xdelta3](https://github.com/jmacd/xdelta/releases) (`brew install xdelta`
   on macOS; [MultiPatch](https://github.com/Sappharad/MultiPatch) is a macOS app for the same
   job):

   ```
   xdelta3 -d -s "$base_name" "$xdelta" "$result_name"
   ```

   The browser patcher RomPatcher.js cannot apply this patch.

4. **Load the game**: put `$cue` beside `$result_name` and open the `.cue` in an emulator.
   Optional CHD compression: `chdman createcd -i "$cue" -o "patched.chd"`.
$ppf_section
## Patched image

The expected SHA-1 for v$version is **`$result_sha1`**. The project README lists
checksums for all published versions under "$versions_heading".

$result_table

`README.txt` in the download includes application instructions and explains the patch's
validation checks.

## Where it is played

$played

## How the translation was made

$how_made

## Credits

$credits

## Licence

The tools and patch source are licensed under MIT; the English script and its context notes
are licensed under CC BY-SA 4.0. Both licences are included in the source archive. The patch
was built from this release's tag using the repository's import and release tooling.
*Boku no Natsuyasumi* is © Sony
Interactive Entertainment; this project distributes none of it and is not affiliated with
Sony or Millennium Kitchen. Repository paths shown above refer to files in the source archive.
