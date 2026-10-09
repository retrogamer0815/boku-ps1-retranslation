
### Optional: the PPF, for DuckStation

While the release page lists it, `$ppf_bundle` provides the same patch in PPF format,
with its own `PATCH.json`, `README.txt` and cue sheet. DuckStation can apply it at load time
without modifying the disc image. Rename `$ppf` to match the CHD filename with a `.ppf`
extension (`Boku.chd` → `Boku.ppf`), place it beside the CHD, and enable
*Settings → CD-ROM → Apply Image Patches*, which is off by default. DuckStation does not
verify the source-image checksums. The hashes above describe the extracted image, so
steps 1 and 2 are required to verify a CHD dump.
