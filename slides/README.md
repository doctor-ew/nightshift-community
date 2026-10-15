# Nightshift talk deck

Editable Slidev core deck for the upcoming talks. The 18 slides contain 16 core slides and two presenter appendices. Speaker notes include source references, live-demo cues and fallback instructions.

Two event-specific versions share the theme and engineering core:

- `saturday.md`: **Trust doesn't rust**, ATL Dev Con, 17 October 2026, FCS Innovation Academy in Alpharetta.
- `tuesday.md`: **Nightshift: From Copilot to Autopilot (Engineering Guardrails for AI Coding Agents)**, Open Source Night, 20 October 2026, Tech Square ATL. This version connects the harness to open contribution and independent review for a mixed-experience meetup audience.

The user estimates a 20–40 minute speaking slot. Suggested 20-, 30- and 40-minute paths are in [RUN-OF-SHOW.md](RUN-OF-SHOW.md). Posted 8 AM–5 PM and 6:30–8:30 PM times are whole-event windows, not the duration of either talk.

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

## Event versions

From `slides/`:

```bash
npm run dev:saturday
npm run dev:tuesday
```

Open http://localhost:3044/ for Saturday and http://localhost:3045/ for Tuesday. Add `/presenter/` for speaker notes.

```bash
npm run build:saturday
npm run build:tuesday
npm run export:saturday -- --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
npm run export:tuesday -- --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

Event PDFs are `saturday-trust-doesnt-rust.pdf` and `tuesday-nightshift.pdf`. The builds are `dist-saturday/` and `dist-tuesday/`. The supplied code photograph is unchanged; lighter CSS overlays make it visible, with a stronger overlay on content slides to protect text.
