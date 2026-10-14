# Nightshift talk deck

Editable Slidev core deck for the upcoming talks. The 18 slides contain 16 core slides and two presenter appendices. Speaker notes include source references, live-demo cues and fallback instructions.

The event names, audiences and speaking times have not been supplied. The current core assumes a technical audience and roughly 20 minutes including a four-minute walkthrough. Use the same core for Saturday and Tuesday until those details are confirmed. For a short slot, omit slides 5, 9, 12 and 15, and show the retained dashboard rather than a new provider run. For a longer slot, expand the editor walkthrough and questions. The appendices are optional.

## Present

Dependencies are already available locally. From this repository:

```bash
cd slides
npm run dev -- --port 3040
```

The current development server is already running at http://127.0.0.1:3040/. Presenter notes are at http://127.0.0.1:3040/presenter/. Use arrow keys or the clickable section rail. On a new checkout, run `npm ci` before starting the deck.

## Build and export

```bash
npm run build
npm run export -- --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --per-slide
```

The PDF is `nightshift-final.pdf`. The static build is `dist/` and uses hash routing. Serve it locally without internet:

```bash
python3 -m http.server 3042 --bind 127.0.0.1 --directory dist
```

Then open http://127.0.0.1:3042/#/1. A browser normally needs the local HTTP server for the static site; the PDF works as a standalone file. No slide site has been published. Generated PDFs, builds and dependencies are ignored by Git.

## Demo rehearsal

From the repository root:

```bash
python3 scripts/nightshift-talk-check.py
```

See [the testing guide](../docs/talks/TESTING.md) for a check without authentication, focused regression commands and the difference between cached reuse and a fresh provider run. The current pinned public demo remains independent of whether the integration branch has merged into `main`.

## Theme and sources

The supplied GSU Slidev reference provides the code-photo background, Source Code Pro fonts, dark/cream/terracotta palette, layouts and section rail. Its workshop content, speaker cards, sponsorship and credits are excluded. The original reference project is not edited.

See [SOURCES.md](SOURCES.md) for content and asset provenance. Event-specific variants can change the title and examples while retaining this shared visual theme.

The deck pins `floating-vue` to `5.2.2` to avoid the [reported tooltip compatibility issue](https://github.com/shikijs/shiki/issues/1329). This changes this deck’s dependency resolution, not the supplied reference project. The theme, Slidev version and native slide content remain intact.
