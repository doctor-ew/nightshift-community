# Suggested talk paths

Both event decks have 49 slides; choose depth for a 20–40 minute slot.

| Slides | Topic |
|---|---|
| 1–19 | Framing, skills, harness, routing, retained demo and human boundaries |
| 20–24 | Memory bridge, architecture and security |
| 25–28 | Retrieval and MEX: explanation, actual setup, bounded handoff |
| 29–31 | Jev: purpose, shadow rubric and proposed evaluation |
| 32 | Cost measurement |
| 33–41 | Actual UI, illustrative HITL, skills, proof and continuation |
| 42–46 | DRY, SOLID, ACID, Big O and Convention over Configuration |
| 47–48 | Discussion and LinkedIn QR |
| 49 | Retained-demo checker appendix |

## Approximately 20 minutes

Use 1–4, 6, 8–11, 14, 18, 21–22, 26–27, 29–30, 33, 35–36, 42 and 47–48. Treat optional screenshots as brief evidence rather than reading each slide.

## Approximately 30 minutes

Add 15, 23–25, 28, 31–32, 38 and 43–46. Keep principles grounded in one example each.

## Approximately 40 minutes

Expand the remaining walkthrough and proof slides. Keep 49 available for questions. Jev remains offline in this demonstration.

## Presenter setup

- Completed rehearsal: http://127.0.0.1:8878 . New control-room candidate: http://127.0.0.1:8880 . Local addresses refer to the presenter laptop.
- From the community checkout, run `python3 scripts/nightshift-talk-check.py`. It checks the retained fixture and real tests and blocks new generation during the repeat.
- Open `skills/nightshift/SKILL.md`, `routing.json` and `docs/ARCHITECTURE.md` in the editor.
- Keep `.nightshift/133-fallback/completed-demo.webm` and `.nightshift/133-fallback/recorded-dashboard.html` available. Missing temporary fixture paths can be restored only from the verified backup into absent original paths; preserve all receipts and avoid archive metadata appearing as source.

Saturday: ATL Dev Con, Trust doesn't rust, 17 October 2026, FCS Innovation Academy, Alpharetta. Tuesday: Open Source Night, From Copilot to Autopilot, 20 October 2026, Tech Square ATL. Event windows are not confirmed speaking slots.

Measured result: the completed formatter cached repeat used zero additional generation calls. MEX/Jev savings are optimization hypotheses; the original self-hosted run has retained failures and an operator-directed merge. Do not claim an automatically completed six-green-stage run or an already published production release.
