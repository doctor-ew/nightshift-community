# Continue the coach — laptop handoff

Status: unfinished checkpoint, not a passing release. User authorized completing, reviewing, pushing and merging the coach and runtime repair; latest request is to transfer this work to another laptop. Do not restart the old blocked batch unchanged.

## Get both repositories

Both repositories use branch `handoff/coach-completion-20260909`:

- Coach: https://github.com/doctor-ew/gsu-hack-her-thon-2026/tree/handoff/coach-completion-20260909
- Runtime: https://github.com/doctor-ew/nightshift-community/tree/handoff/coach-completion-20260909

Clone both branches into any user-owned workspace on the laptop. No /root directory is involved; /root/coach_proof was an internal agent identifier. Original working copies were /tmp/hack-her-thon-coach-completion-20260909 and /tmp/nightshift-coach-runtime-repair-20260909. Do not rely on those paths on the laptop.

## Runtime state

Runtime PR https://github.com/doctor-ew/nightshift-community/pull/29 targets integration/nightshift. Commits e006f2b and e144360 add tool-free multi-turn transcript replay and prevent resampling failed turns after interruption. Commit 028a115 retains independent review. That PR had passing CI when inspected at handoff; it is not merged by this session.

The handoff branch also includes the subsequent structural-oracle extension in scripts/nightshift-behavior-proof.py, tests/test-behavior-multiturn.py and docs/BEHAVIOR-PROOF.md: json_field_length_at_most and json_field_nonempty. All 11 multi-turn/structural tests and all 25 existing proof tests passed locally. Independent review of this last extension remains pending. The earlier REVIEW.md does not approve this later delta. Review it, rerun the affected tests, then publish it to the runtime PR and check CI before merging. Runtime models remain configurable; subscription authentication only. The multi-turn profile replays actual responses, without tools or native session persistence.

## Coach state

Product authority: docs/AGENT-SPEC.md. The new bounded task is docs/coach-completion-20260909/SPEC.md. Preserve the older task and failed batch history. Coach files exist under coach/: canonical prompt, adapter, four templates, README, evaluation cases, and a portable standard-library Python evaluator coach/eval/run.py. Root README now links the coach. coach/examples/study-session.md is still a placeholder, not a finished worked example. coach/eval/RESULTS.md still describes the historical failure and must be updated only after new passing evidence.

All live work from this session is preserved in docs/coach-completion-20260909/live/ with MANIFEST.json hashes:
- attempt1: sandbox OAuth failures, not behavioral results.
- attempt2 and attempt3: ten live web-enabled responses each; research inaccuracies remained. Transport success is not PASS.
- final-tool-free: ten live baseline responses. Independent review-cases-output.json says REQUEST_CHANGES: case01 exceeds the focused-question limit through duplicated prose/list asks; case04 asserts named competitors as common workarounds without inspected source support. Eight other cases passed that review.
- conversation-final: four real persisted-session turns. Reached the student decision request; student approval and all four final deliverables were NOT executed. Earlier partial conversations are retained too.
- student-*.md: synthetic student inputs. All scenario counts are synthetic: estimated24, reachable8, contacted6, problem reports3, workaround users6, commitments2. Real fieldwork remains Unknown.

IMPORTANT: The planned concise rewrite of coach/PROMPT.md was interrupted before execution. The current file remains the longer prompt with targeted amendments. Next repair should remove duplicated instructions, put all questions in ONE numbered block, and prohibit unsupported named-product claims when no page or passage has been inspected. Keep the same approved product requirements. The proposed rewrite was not run or validated. Do not infer completion from an earlier chat message.

Research inspection: https://workspace.google.com/intl/en/products/forms/ was opened on 2026-09-09. Narrow supported paraphrase: Google describes collecting form responses, response charts, and export to Sheets. No inference about absent scheduling capabilities is justified by page silence. The conversation used a facilitator-supplied summary, not claimed coach browsing. Earlier exploratory references also inspected https://doodle.com/en/ and https://www.when2meet.com/; do not reuse unsourced pricing/app/feature claims.

## Proof state and portability

Read docs/coach-completion-20260909/PROOF-HANDOFF.md FIRST in the coach repository. The public scenarios are an unapproved draft; one public challenge failed and its ledger is preserved. No scope activation, spec-lock, seal, development run or final proof run occurred. proof-ledger-state.json is a byte-identical pre-seal state snapshot for careful restoration into the NEW clone's Git common directory, only if no state already exists. Keep all counters and failures; do not reset them.

Existing private heldouts became exposed when a process listing printed provider argv. They are ineligible and are deliberately NOT in Git. Have an independent agent create fresh private heldouts outside all checkouts, obtain independent review, and replace the public commitment before sealing. Preserve the exposure history. Credentials, native session caches, and private test bodies were not pushed. Authenticate independently on the laptop; do not copy keys or OAuth tokens.

Native Claude sessions are machine-local. Start a fresh conversation and retain actual new responses for any changed prompt hash; do not fabricate prior assistant turns. coach/eval/run.py computes repository paths relative to itself and supports cases/turn modes, output directory, optional model, and optional web case. Use --help. The archived live/review.py is a historical helper with old absolute paths: adapt its project path before reuse. Do not treat it as a portable launcher.

## Finish in this order

1. Inspect both branches and instructions; preserve dirty work. Check actual provider executable/version and subscription login on this laptop.
2. Review the structural-oracle delta, run tests/test-behavior-multiturn.sh and tests/test-behavior-proof.sh, and finish the runtime PR. Check CI before merge. Use the inspected runtime checkout directly for proof until installation is deliberately configured; do not accidentally run an older installed helper.
3. Repair and freeze the coach prompt. Preserve all previous failures. Prepare fresh independent private cases, revised reviewed public scenarios, and restore/reconcile the recorded pre-seal ledger. Complete classification/challenge, scope/spec locks, seal and development proof honestly.
4. Run all ten original synthetic cases against the frozen prompt and obtain independent semantic review, not keyword-only approval. Run a complete real multi-turn synthetic conversation through the human decision and all four populated deliverables. Inspect citations. A runtime result code alone is not acceptance.
5. Finish the worked example, adapter links, results, REVIEW.md, DRIFT.md, QA.md and publication notes. Run final heldout proof with current source bindings. Do not claim live Claude chat parity unless tested; the approved spec permits the selected Claude Code live runtime plus shared-prompt reference validation.
6. Commit, push, create/update a coach PR to main, inspect checks, merge verified work, then synchronize the user's local project without deleting untracked work or rewriting history. No production deployment is needed for this Markdown coach. Leave workshop slides/agenda as separate work.

## Prompt to paste into the next coding session

Continue the unfinished Hack-Her-Thon coach and Nightshift runtime repair. I authorize you to finish implementation, tests, independent review, push, PRs, merge verified changes, and sync my local checkout. Read docs/HANDOFF-COACH.md in both repositories on handoff/coach-completion-20260909, then the coach PROOF-HANDOFF.md and approved AGENT-SPEC.md. Preserve old failures and budgets. Runtime PR29 contains reviewed multi-turn support; the handoff adds tested structural assertions needing review. Coach still fails cases01/04 and lacks final conversation deliverables. The planned concise prompt rewrite was not executed. Fix and run the real evaluations; no invented passing evidence, no API billing fallback. Restore the pre-seal ledger carefully and replace exposed heldouts independently before proof. Carry the work through verified publication and merge without another handoff. Keep provider/model choice configurable.
