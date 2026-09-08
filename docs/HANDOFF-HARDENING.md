# Start here: Nightshift hardening handoff

Continue implementation, not merely planning. Work in this repository:
https://github.com/doctor-ew/nightshift-community

## Order

1. [#18](https://github.com/doctor-ew/nightshift-community/issues/18): provider-neutral roles, commands and project conventions.
2. [#19](https://github.com/doctor-ew/nightshift-community/issues/19): scoped branding and provider-coupling regression guards. Parallelize only independent work with explicit file ownership.
3. [#13](https://github.com/doctor-ew/nightshift-community/issues/13): behavioral proof before full implementation.
4. Idea Coach shakedown after those changes are verified and integrated.

## Included artifacts and baseline

- Integration baseline: bd47c2ab031d83e011e443c82611983614897935, including #8 via [PR #23](https://github.com/doctor-ew/nightshift-community/pull/23).
- Retry accounting: [PR #21](https://github.com/doctor-ew/nightshift-community/pull/21).
- #8 verification records: [review](8/REVIEW.md), [drift](8/DRIFT.md), [preflight](8/PREFLIGHT.md).
- #18/#19 preparation: [docs/18/PREPARATION.md](18/PREPARATION.md). Its inventory predates #8; re-ground the cited overlaps before editing.
- #13 design: [docs/13/DESIGN.md](13/DESIGN.md), originally [draft PR #22](https://github.com/doctor-ew/nightshift-community/pull/22). Design is not implementation or approval.

## Operating instructions

Read applicable AGENTS.md and canonical commands/nightshift-*.md first. Inspect current remote issues, PRs, receipts and processes before launching anything. Do not repeat completed #8 work or assume a previous worker is running.

Use isolated ticket worktrees. Preserve dirty work, ownership receipts and attempt history. Target integration/nightshift for delivery; do not promote to main or deploy production. Commit, push and open PRs; merge into integration only after required checks and independent review pass. Sync installations only between active runs and verify the installed revision.

Keep provider/model choice configurable. Frontier authentication must use subscriptions with no paid-API fallback. Local models are optional, not a workshop dependency. Keep legitimate provider-specific behavior in adapters; do not blindly replace all provider names.

Apply DRY/SOLID/ACID/Big-O/separation-of-concerns judgment. Use evidence-backed specs, verified citations, independent adversarial review, tests and drift checks. Preserve #8 pre-provider rejection and measurement behavior. Keep infrastructure retries separate from substantive repair budgets; never erase counters to manufacture a pass.

For #13, use risk-appropriate Given/When/Then scenarios, forbidden behavior and a minimal intended-runtime proof before full implementation. Reuse scenarios as acceptance tests; avoid adding ceremonial agent stages. Resolve the draft's open contracts before treating it as approved.

Report actual processes separately from historical dashboard observations. Provider success is not gate approval. Report evidence, PRs, integration/install revisions, blockers and next action honestly.

## Coach boundary

Coach repository: https://github.com/doctor-ew/gsu-hack-her-thon-2026

Keep Coach parked until #13 is ready. On the original Mac its project is under shuttlebay/_ATL_/GSU/Hack-Her-Thon and its retained sibling worktree is Hack-Her-Thon-worktrees/spec-fa7abd1282236c13. Inspect the actual tracker and failed evaluation evidence before reconciling/resuming. Those local artifacts are not included in this branch: do not assume another machine has them, reset their budgets or claim they were transferred.

Workshop choices: Claude chat, optional Claude Code, own accounts, public links or pasted research, and batches of 1–5 questions. Do not add a local-model dependency.

Start with a brief live status check, then execute #18/#19. Make routine reversible decisions autonomously. Ask only for genuinely blocking choices; permanent deletion or production deployment requires explicit confirmation.
