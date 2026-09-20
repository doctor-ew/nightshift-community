# Diagnose and repair from the dashboard

The ticket card offers Diagnose & repair with Configured routing, Claude, Codex, or Local model. Selection uses existing model configuration; provider policy and subscription authentication remain enforced. Local roles use the configured backend (including oMLX). A policy-restricted provider is rejected.

Each attempt diagnoses the retained failure, requests a minimal patch, independently reviews it using author-provider provenance, applies it only after review, then independently runs applicable checks and reproduces the failed operation. Only verified repair proceeds to retain-only cleanup and the original factory invocation. Factory process exit is not ticket completion. Prior failures remain visible as history.

The ticket exposes repair phase, changed files, evidence and a log. Stop repair terminates its owned work, preserving evidence and any applied patch. Duplicate clicks share the existing worker. Requests require the same-origin token and current saved-settings hash. API version 2 requires a refreshed dashboard server; old pages show an update notice.

Bounds: three repair attempts per ticket; 15 minutes for diagnosis/review/verification, at most 10 minutes per role; 2 MB patch limit. Provider token usage is observational, not a hard token cap. A resumed normal factory has its existing budgets. This feature does not authorize paid API calls, deletions, new files, renames, external/global configuration changes, budget resets, fabricated gate receipts, or production deployment. Repairs needing those changes stop with retained evidence for an operator. Failed verification retains the patch and does not auto-resume.

Validation: worker tests exercise patch traversal/symlink/structural rejection and prove verification failure prevents resume; action tests cover policy, duplicate clicks, stale settings and Stop; dashboard HTTP tests cover same-origin controls and evidence access. Browser rendering verified the repair button and all four provider options. No claim of universal successful autonomous repair is made.

Implementation: scripts/nightshift-console-actions.py, scripts/nightshift-console-repair.py, dashboard/server.py, dashboard/src/app.jsx.

Diagnosis and independent patch review use the read-only nightshift-repair-analyst role, with configurable routing. They do not require an implementation proof receipt. Engineer and architect dispatch still require development proof; repair never manufactures that receipt. Missing independently authored held-out evidence still needs the product evaluation workflow and cannot be fabricated by a repair patch.
