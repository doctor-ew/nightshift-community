# Suggested talk paths

Both event decks have 42 slides. Approximate 20–40 minute slots remain unconfirmed.

## Module map

| Slides | Topic |
|---|---|
| 1–3 | Event framing and harness overview |
| 4–8 | Skills, six stages, acceptance example and recorded routing |
| 9–11 | Why route: cost, bias and trust |
| 12–15 | Admission, front end, copyable command and RED/GREEN |
| 16–19 | Evidence, self-hosted run and human checkpoints |
| 20–23 | First-talk bridge, runtime and security |
| 24–27 | Retrieval, MEX, Jev and cost measurement |
| 28–32 | Actual control room/Review, illustrative HITL and actual allowance |
| 33–36 | Skill source, role dispatch, actual proof and decision continuation |
| 37–39 | MEX retrieval, Jev shadow rubric and proposed evaluation |
| 40 | Closing and questions |
| 41–42 | Rehearsal checker and SOLID/ACID appendices |

## Approximately 20 minutes

Use 1, 2, 3, 4, 6, 8, 9, 10, 11, 14, 18, 22, 28, 30, 31, 33, 37, 38, 40. Keep the retained demonstration to two minutes; use the screenshots to avoid excessive window switching.

## Approximately 30 minutes

Add 15, 21, 23, 25, 26, 29, 32, 34 and 35 as useful. Explain retained failure history and the difference between saved decisions and passed gates.

## Approximately 40 minutes

Add 7, 12, 16, 17, 20, 24, 27, 36 and 39. Open the source and architecture map; keep 41–42 for questions. Jev remains offline in this demonstration.

## Presenter setup

- Completed rehearsal: http://127.0.0.1:8878 . New control-room candidate: http://127.0.0.1:8880 . Local addresses refer to the presenter laptop.
- From the community checkout, run `python3 scripts/nightshift-talk-check.py`. It checks the retained fixture and real tests and blocks new generation during the repeat.
- Open `skills/nightshift/SKILL.md`, `routing.json` and `docs/ARCHITECTURE.md` in the editor.
- Keep `.nightshift/133-fallback/completed-demo.webm` and `.nightshift/133-fallback/recorded-dashboard.html` available. Missing temporary fixture paths can be restored only from the verified backup into absent original paths; preserve all receipts and avoid archive metadata appearing as source.

Saturday: ATL Dev Con, Trust doesn't rust, 17 October 2026, FCS Innovation Academy, Alpharetta. Tuesday: Open Source Night, From Copilot to Autopilot, 20 October 2026, Tech Square ATL. Event windows are not confirmed speaking slots.

Measured result: the completed formatter cached repeat used zero additional generation calls. MEX/Jev savings are optimization hypotheses; the original self-hosted run has retained failures and an operator-directed merge. Do not claim an automatically completed six-green-stage run or an already published production release.
