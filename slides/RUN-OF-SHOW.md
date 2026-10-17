# Suggested talk paths

Both event decks have 43 slides. Approximate 20–40 minute slots remain unconfirmed.

## Module map

| Slides | Topic |
|---|---|
| 1–3 | Event framing and harness overview |
| 4–8 | Skills, six stages, acceptance example and recorded routing |
| 9–11 | Why route: cost, bias and trust |
| 12–15 | Admission, front end, copyable command and RED/GREEN |
| 16–19 | Evidence, self-hosted run and human checkpoints |
| 20–24 | First-talk bridge, two architecture diagrams and security |
| 25–28 | Retrieval, MEX, Jev and cost measurement |
| 29–33 | Actual control room/Review, illustrative HITL and actual allowance |
| 34–37 | Skill source, role dispatch, actual proof and decision continuation |
| 38–40 | MEX retrieval, Jev shadow rubric and proposed evaluation |
| 41 | Closing and questions |
| 42–43 | Rehearsal checker and SOLID/ACID appendices |

## Approximately 20 minutes

Use 1, 2, 3, 4, 6, 8, 9, 10, 11, 14, 18, 21, 22, 29, 31, 32, 34, 38, 39, 41. Keep the retained demonstration to two minutes; use screenshots to avoid excessive window switching.

## Approximately 30 minutes

Add 15, 23, 24, 26, 27, 30, 33, 35 and 36 as useful. Explain retained failure history and the difference between saved decisions and passed gates.

## Approximately 40 minutes

Add 7, 12, 16, 17, 20, 25, 28, 37 and 40. Open the source and architecture map; keep 42–43 for questions. Jev remains offline in this demonstration.

## Presenter setup

- Completed rehearsal: http://127.0.0.1:8878 . New control-room candidate: http://127.0.0.1:8880 . Local addresses refer to the presenter laptop.
- From the community checkout, run `python3 scripts/nightshift-talk-check.py`. It checks the retained fixture and real tests and blocks new generation during the repeat.
- Open `skills/nightshift/SKILL.md`, `routing.json` and `docs/ARCHITECTURE.md` in the editor.
- Keep `.nightshift/133-fallback/completed-demo.webm` and `.nightshift/133-fallback/recorded-dashboard.html` available. Missing temporary fixture paths can be restored only from the verified backup into absent original paths; preserve all receipts and avoid archive metadata appearing as source.

Saturday: ATL Dev Con, Trust doesn't rust, 17 October 2026, FCS Innovation Academy, Alpharetta. Tuesday: Open Source Night, From Copilot to Autopilot, 20 October 2026, Tech Square ATL. Event windows are not confirmed speaking slots.

Measured result: the completed formatter cached repeat used zero additional generation calls. MEX/Jev savings are optimization hypotheses; the original self-hosted run has retained failures and an operator-directed merge. Do not claim an automatically completed six-green-stage run or an already published production release.
