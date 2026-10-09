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
