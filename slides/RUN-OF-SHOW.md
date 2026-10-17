# Suggested talk paths

Both event decks have 51 slides; choose depth for a 20–40 minute slot.

| Slides | Topic |
|---|---|
| 1–19 | Framing, skills, harness, routing, retained demo and human boundaries |
| 20–24 | Memory bridge, architecture and security |
| 25–30 | Retrieval and MEX: explanation, actual setup, bounded handoff, actual spec Sources and adversarial role |
| 31–33 | Jev: purpose, shadow rubric and proposed evaluation |
| 34 | Cost measurement |
| 35–43 | Actual UI, illustrative HITL, skills, proof and continuation |
| 44–48 | DRY, SOLID, ACID, Big O and Convention over Configuration |
| 49–50 | Discussion and slide/LinkedIn QRs |
| 51 | Retained-demo checker appendix |

## Approximately 20 minutes

Use 1–4, 6, 8–11, 14, 18, 21–22, 26–27, 29–31, 35, 37–38, 44 and 49–50. Treat optional screenshots as brief evidence rather than reading each slide.

## Approximately 30 minutes

Add 15, 23–25, 28, 33–34, 40 and 45–48. Keep principles grounded in one example each.

## Approximately 40 minutes

Expand the remaining walkthrough and proof slides. Keep 51 available for questions. Jev remains offline in this demonstration.

## Presenter setup

- Completed rehearsal: http://127.0.0.1:8878 . New control-room candidate: http://127.0.0.1:8880 . Local addresses refer to the presenter laptop.
- From the community checkout, run `python3 scripts/nightshift-talk-check.py`. It checks the retained fixture and real tests and blocks new generation during the repeat.
- Open `skills/nightshift/SKILL.md`, `routing.json` and `docs/ARCHITECTURE.md` in the editor.
- Keep `.nightshift/133-fallback/completed-demo.webm` and `.nightshift/133-fallback/recorded-dashboard.html` available. Missing temporary fixture paths can be restored only from the verified backup into absent original paths; preserve all receipts and avoid archive metadata appearing as source.

Saturday: ATL Dev Con, Trust doesn't rust, 17 October 2026, FCS Innovation Academy, Alpharetta. Tuesday: Open Source Night, From Copilot to Autopilot, 20 October 2026, Tech Square ATL. Event windows are not confirmed speaking slots.

Measured result: the completed formatter cached repeat used zero additional generation calls. MEX/Jev savings are optimization hypotheses; the original self-hosted run has retained failures and an operator-directed merge. Do not claim an automatically completed six-green-stage run or an already published production release.
