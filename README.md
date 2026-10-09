# Boku no Natsuyasumi - human translation fork

This fork of [jeapostrophe/boku-ps1](https://github.com/jeapostrophe/boku-ps1) gradually
replaces the upstream AI-written English with a faithful translation reviewed by a
Japanese-fluent human. It retains the upstream proportional font, horizontal dialogue
and choices, relocation, page handling, and build/lint/mockup tools.

**Human review currently covers 13 entries in three Day 1 events: E0171, E0184 and E0112.**
Eleven entries have new wording; two were accepted unchanged. The remaining English is
inherited from upstream and has not yet received this fork's human review. The wordless
E0184.2 sound effect remains unsubtitled. Per-entry coverage is recorded in
[translation/human-review.tsv](translation/human-review.tsv).

The corrected pilot passed repository layout checks and Beetle PSX tests. The fork owner
also confirmed that it looks correct in DuckStation on 2026-10-09. The first planned
prerelease is `v0.0.1-testpilot.1`; it is not published yet.

Translators work in a review spreadsheet with original Japanese reference, conversation
context, and automatic previews of the actual font widths and wrapping. Repository lint
and game-font mockups remain the final authority. The contributor workflow is in
[translation/README.md](translation/README.md), under "Local human review pilot".

The game-wide features and historical decisions below describe the upstream foundation.

An English translation patch for the PlayStation original of *Boku no Natsuyasumi*
(ぼくのなつやすみ, SCEI / Millennium Kitchen, 2000, **SCPS-10088**): a nine-year-old boy spends
August at his uncle's house in the country — 31 days of catching bugs, flying kites and keeping
a picture diary.

* **Every conversation** of the 31 days, the menus, and the names of things.
* **The pictures with writing in them**: the picture diary, the insect and kite encyclopedias,
  the title menu, the buttons, the records and the signs.
* **Subtitles** for the narrated movies, the theme song, the five endings and the other
  voice-only lines. The voices stay Japanese, on purpose.

Nothing is cut to fit. It is a patch, not the game: you need your own copy of the Japanese disc.

Upstream foundation made by [Jay McCarthy](https://jeapostrophe.github.io/) with Claude —
[why](#why-i-made-this), and [how](#how-the-translation-is-made).

**[Get the patch](../../releases)** · [how to apply it](#getting-it) ·
[which version do I have?](#which-version-do-i-have)

## Screenshots

| | |
|---|---|
| <img src="docs/screenshots/title.png" width="320" alt="The title screen: the Japanese logo over a summer sky, and under it the menu in English — New Game, Continue, Summer Memories, Settings."><br>The title menu. The logo stays as it was drawn. | <img src="docs/screenshots/movie.png" width="320" alt="A frame of the opening movie: green vines against the sun and a summer sky, with two lines of English subtitle along the bottom."><br>The opening movie, with the narrator subtitled inside the picture. |
| <img src="docs/screenshots/conversation.png" width="320" alt="Boku's family arriving at the uncle's house, seen from above, with a line of dialogue in a band under the scene: Father, in Japanese quotation brackets, saying his son will be in their care over the summer vacation."><br>A conversation: English in a band under the scene, the speaker named as the original names him. | <img src="docs/screenshots/insect-book.png" width="320" alt="The insect encyclopedia open at the Musk Swallowtail: a photograph of the butterfly, its family, wingspan and food, and two columns of description, all in English."><br>The insect encyclopedia. |
| <img src="docs/screenshots/kite-book.png" width="320" alt="The kite encyclopedia open at the Square Kite, marked Beginner, with a paragraph in English on how it is built and flown."><br>The kite encyclopedia. | <img src="docs/screenshots/diary.png" width="320" alt="Boku's picture diary for August 1: his crayon drawing of himself daydreaming about the sea, a tree, a kite and watermelon, and under it four lines of his entry in English."><br>Boku's picture diary — one page for each day. |

Upstream screenshots of the patched game, running on Beetle PSX. They predate the human pilot.

## Video

[Watch the video](https://www.youtube.com/watch?v=m1jHBkPIDw4)

## Getting it

This fork's test patches will appear on its **[Releases page](../../releases)**. Each release
will state its human-review coverage, application instructions and checksums. The original
upstream patch is available from [jeapostrophe/boku-ps1 releases](https://github.com/jeapostrophe/boku-ps1/releases).

1. **Dump your own disc** of the Japanese game (SCPS-10088) to a raw image — a `.bin` with its
   `.cue`. If yours is a `.chd`, extract it with `chdman`.
2. **Check it**: the release gives the SHA-1 your image must have. If it differs, the patch is
   not for your file.
3. **Patch it** with `xdelta3` (or MultiPatch, on macOS).
4. **Play it**: open the `.cue` that comes with the patch in your emulator.

When a release also lists a PPF download, DuckStation can apply that as it loads your
unpatched disc instead; the release says how.

## Which version do I have?

Take the SHA-1 of your patched image — the `.img` the patch wrote, not the `.cue` or a `.chd`
made from it (`shasum -a 1`, `sha1sum`, or `certutil -hashfile <file> SHA1`) — and find it in
the right-hand column. The xdelta and the PPF of a version make the same image. The middle
column is the dump that version patches.

| version | your dump's SHA-1, before patching | the patched image's SHA-1 |
|---|---|---|
| v1 | `5959bf7d9835d0a60aeb0143e2d0fc564bfea9fa` | `3ab94dcb5338bd17a8cf848d931efc0476fc9aa4` |

`v1` is the upstream release. Fork versions are added from their release manifests before
publication; a version's release page states whether it is a prerelease.

## Where it is played

The upstream foundation is developed and played on Beetle PSX (the mednafen core, as in
RetroArch) and DuckStation. This fork's first human pilot passed exact-text checks and
visual inspection of all 19 dialogue pages in Beetle, including Yes/No cursor navigation
and the No continuation. The fork owner reported a successful DuckStation review on
2026-10-09. This pilot has not been tested on a real PlayStation.

## Who this is for, and what kind of translation it is

**A translation, not a localization** (Jay, 2026-09-20). The audience is the person who would
otherwise play this with Google Translate open, or screenshot a text box and ask Claude what it
says — someone who wants *this* game, overtly Japanese as it is, and needs the words. It is
not an attempt to bring the game to a wider audience. So Japanese-isms stay: Boku is called
"Boku" (English can't keep the word's you/I/little-boy ambiguity, but it can keep the name),
and the style guide decides the rest in that spirit. The voices stay Japanese for the same
reason — it is a choice, not a limitation: the intended experience is a film
with subtitles, not a dub, and that suits a work this rooted in its place.

Nothing is cut to fit. Older projects that found "the script does not fit" were hand-writing
assembler; if English outgrows its space, the answer here is engineering — relocation, the
disc's unused sectors, new packing or compression routines — not a shorter translation.

## Why the PS1 version

A PSP port exists, has a finished Spanish patch, and re-targeting that patch to English would
be the shorter road. This project takes the longer one on purpose (Jay, 2026-09-19): the PSP
port letterboxes and stretches the 4:3 painted backgrounds to 16:9, and the original's layering
of the character models over those backgrounds is better. The PS1 game is the one worth
playing, so it is the one worth translating.

## How the translation is made

**This fork uses Japanese-fluent human review to replace the inherited English gradually.**
The first batch covers 13 translatable entries across E0171, E0184 and E0112; 11 have new
wording. Its three typo corrections were approved by the fork owner. Review status is
separate from pixel fit, and neither the unreviewed remainder nor upstream's agent-review
statuses count as human approval. The reviewed entries are listed in
[translation/human-review.tsv](translation/human-review.tsv).

**The upstream English script was written by AI agents** — Claude, the strongest model available, under
Jay's direction — not a sentence-at-a-time machine translation. The game's event scripts were
decoded so that a translator sees a whole scene as the game plays it — which line follows
which, where the choices branch, who is speaking — after reading a story bible, a style guide
and a glossary written for this project. A second agent reviews every line against the
Japanese, Jay reads the script and rules on the questions it raises, and then it gets played.
The reverse engineering and the assembly patches that make room for English were done with
Claude too. The upstream project was made for Jay and his friends and published for anyone who wants it;
everything that produced the script is in the repository to inspect, and pull requests that
improve it are welcome.

## Why I made this

The following is upstream author Jay McCarthy's account, retained for attribution.

I've known about *Boku no Natsuyasumi* for about 15 years, since Ray Barnholt talked about it
on his podcast, [No More Whoppers](https://nomorewhoppers.libsyn.com/). Then I bought every issue of his magazine, SCROLL, as it came
out; [SCROLL 10](https://scroll.vg/issues/10/) (June 25, 2013) is all about the Boku games.

It has been on my list of things to play "once I learned Japanese well enough", but that never
happened. I tried to play it once with Google Translate, but it was too slow and miserable — it
was just not giving me the nostalgic feeling that I wanted.

Then I decided to choose a project to test Claude's multilingual and assembly understanding,
and went with this... and it worked out!

— Jay McCarthy, September 2026

## Related work and credit

This fork's renderer, reverse engineering, build pipeline and initial English come from
[Jay McCarthy's boku-ps1](https://github.com/jeapostrophe/boku-ps1), initially based on
commit `04d3387fcc07c1a268a3fb0bab509ea0d05171a2`. The first replacement batch was curated
by the fork owner's Japanese-fluent human collaborator. The upstream credits follow.

None of these target the PS1 original's text, and all of them made this project's first day
shorter. What each one knows is written up in
[research/related-projects.md](research/related-projects.md).

* [pleonex/Boku-no-Natsuyasumi](https://github.com/pleonex/Boku-no-Natsuyasumi) — PSP port
  extraction tools and a format wiki; its glyph table is what first decoded the PS1 script.
* [HilltopWorks/BokuNoNatsuyasumi2](https://github.com/HilltopWorks/BokuNoNatsuyasumi2) — the
  PS2 sequel's complete English patch toolchain.
* [GriffithVIII/Boku-no-Natsuyasumi-ESP](https://github.com/GriffithVIII/Boku-no-Natsuyasumi-ESP) —
  the PSP port's Spanish patch (TraduSquare).
* [psyouloveme/boku1-reversing](https://github.com/psyouloveme/boku1-reversing) — PS1 original:
  Ghidra scripts, a jPSXdec index of the disc, and a RAM map from speedrunning.
* [KendritPy/Boku_ESP_JP](https://github.com/KendritPy/Boku_ESP_JP) and
  [snake7594/boku-natsu-portable-kr-patch](https://github.com/snake7594/boku-natsu-portable-kr-patch) —
  PSP port: a precise dialogue-format spec, and a 2,020-code character table.

## Contributing

The whole project is in this repository — the tools, the format notes, the translation and
its history — and the game itself is not: you bring your own dump. [TECHNICAL.md](TECHNICAL.md) says
how the patch is built and how to build it yourself; the open work is [PLAN.md](PLAN.md). Pull
requests are welcome, and so are disagreements about style.

## Licence

Tools, scripts and assembly patches: [MIT](LICENSE). The English translation and the context
notes: [CC BY-SA 4.0](LICENSE-translation). *Boku no Natsuyasumi* is © Sony Interactive
Entertainment; this project distributes none of it but the screenshots on this page, and is
not affiliated with Sony or Millennium Kitchen.
