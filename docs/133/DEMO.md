# Talk demonstration acceptance

## Current status

The original rehearsal is a retained failure, not a fallback success. Isolated candidate `36e4abc` passed all six stages. Candidate `201970d` also passes the identical invocation with zero additional provider calls and unchanged receipts and budget reservations. Final CI completion remains pending. A successful dashboard recording exists locally; Jev remains offline pending explicit payload approval.

## Demonstration sequence

1. Show `commands/nightshift-product.md` and `skills/nightshift/SKILL.md`: the core workflow is runtime-neutral; the skill is an adapter.
2. Show `routing.json`: author and reviewer routes are explicit. Local extraction checks installed inventory before using a generation call.
3. Open the controller ticket in the dashboard. Show stage, selected provider, blockers, artifacts and retained attempts. Explain unknown cost as unknown; subscription estimates are not charges.
4. Run the public duration-formatter acceptance example through Product, Adversarial, Implementation, Review, Drift and QA. Show actual test output and sealed behavioral proof. An absent application browser suite may be skipped; final behavioral proof remains required.
5. Repeat the identical invocation. Confirm accepted stages and receipts are reused without additional provider launches.
6. Use a recording only when it shows the same verified candidate and actual passing run. Retain screenshots and failure evidence separately.

## Acceptance evidence

Capture candidate commit, isolated installation audit, project baseline, controller state, stage receipt hashes, real tests, proof gates and measured usage. Preserve unknown pricing, interrupted reservations and all earlier failures. No production deployment, global runtime replacement or private downstream configuration is required.

## Optional models

Hermes is deferred for this delivery. Jev already has a shadow-only adapter. Assess it only after the core run passes, using explicitly supplied public evidence and a bounded call. It cannot approve gates or replace independent review. Credential presence is not evidence of successful service access, accuracy or savings.

## Local talk commands

Run these commands from this checkout. The wrapper uses an isolated pinned installation and the retained public project; it does not replace the default installation.

```bash
bash .nightshift/133-runtime/nightshift-talk.sh spec:brief.md --provider codex --model gpt-6.1-sol --auth subscription --branch auto --base main --gear 1 --dashboard off
NIGHTSHIFT_HOME="$PWD/.nightshift/133-runtime/runtime" bash .nightshift/133-runtime/runtime/scripts/nightshift-dashboard.sh --project /private/tmp/nightshift-certification-133 --serve --port 8878
```

Open `http://127.0.0.1:8878`. The current server already uses that port; start the second command only if it is stopped. Show the completed ticket and expand “Controller routing and receipts”. The retained failures explain recovery; they are not new failures of the last completed run.

Local fallback assets are `.nightshift/133-browser-success/` (desktop, mobile, ticket screenshot and actual recording), `.nightshift/133-fallback/dashboard.html` (standalone snapshot), and `.nightshift/133-fallback/public-project-and-worktree.tar.gz` (public project, common Git controller state and registered worktree). `.nightshift/133-fallback/SHA256SUMS` records the archive hash. These files are checkout-only and are not shared by the PR.

The archive retains absolute-path bindings. Restore only into the original missing paths under `/private/tmp`; never overwrite a newer project or claim that relocated evidence is still valid. Preserve the isolated installation under `.nightshift/133-runtime/` for the talks. Before travelling, open the recording and static snapshot and confirm the public project and registered worktree still exist.
