# Suggested talk paths

The user expects approximately 20–40 minutes. These are adjustable rehearsal cuts, not confirmed session timings. Both event decks have 18 slides and the same navigation targets.

## Events

| | Saturday | Tuesday |
|---|---|---|
| Event | ATL Dev Con | Open Source Night, joint Atlanta developer-community meetup |
| Date | 17 October 2026 | 20 October 2026 |
| Talk | Trust doesn't rust | Nightshift: From Copilot to Autopilot (Engineering Guardrails for AI Coding Agents) |
| Venue | FCS Innovation Academy, Alpharetta | Tech Square ATL |
| Audience framing | Developers considering trust and engineering discipline for agents | Developers with varied open-source contribution experience |
| Posted event window | 8 AM–5 PM | 6:30–8:30 PM |

Saturday begins with the scope of trust and the need for current evidence. Tuesday begins with an inspectable contribution and relates the same workflow to open source. Neither talk assumes that a successful provider process proves a change correct.

## About 20 minutes

Use slides **1, 2, 3, 4, 6, 7, 8, 10, 11, 13, 14, 15, 16**.

| Segment | Suggested time | Action |
|---|---|---|
| Event opening and engineering problem, slides 1–3 | 4 minutes | Explain the event-specific motivation and harness responsibilities |
| Skill, stages, small task and routing, slides 4/6/7/8 | 5 minutes | Show the skill file and configured versus recorded routes |
| Front end and retained demo, slides 10–11 | 5 minutes | Show six passing stages, source/tests and cached repeat |
| Evidence scope and human checkpoints, slides 13–15 | 3 minutes | Separate generation calls from login probes and policy from authority |
| Closing and questions, slide 16 | 3 minutes | Saturday: current evidence. Tuesday: a reviewable contribution |

Keep the demo to the preserved public task. The repeat shows current receipt reuse, not fresh model generation. Do not promise a new six-stage run within the slot.

## About 30 minutes

Add slide **5** for the repository instruction layout, slide **9** for admission and bounded context, and slide **12** for the retained RED/GREEN evidence. Budget roughly two minutes each. Use slide **17** before the closing for a four-minute explanation or execution of the guarded checker.

## About 40 minutes

Use the 30-minute path, then add slide **18** for SOLID/ACID review lenses and spend the remaining time walking an actual stage receipt and taking questions. Explain that ACID is a review lens for state-mutating code, not a certification of arbitrary generated applications.

## Demo preparation

1. From the community checkout, run `python3 scripts/nightshift-talk-check.py`.
2. Open the dashboard at http://127.0.0.1:8878 and the event deck's presenter view.
3. Keep `skills/nightshift/SKILL.md`, `commands/nightshift-product.md` and `routing.json` open in the editor.
4. Keep the formatter, real tests and accepted receipt links available through the dashboard and [testing guide](../docs/talks/TESTING.md).
5. Keep `.nightshift/133-fallback/completed-demo.webm` and `.nightshift/133-fallback/recorded-dashboard.html` available locally. Use the recorded passing dashboard if the live surface is unavailable.

The event decks' appendix replaces the obsolete PR-stack discussion. Check current merge status separately if someone asks about installation. The pinned demonstration remains distinct from whichever runtime an audience member has installed.
