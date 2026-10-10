# nightshift instructions for coding agents

`nightshift` is a source-agnostic engineering workflow. Its canonical stage
instructions live in `commands/nightshift-*.md`; reusable role instructions are in
`agents/`; supporting scripts are in `scripts/`. These are the runtime-neutral
core. Codex skills and Claude commands are adapters, not the product itself.

## Using the pipeline

- Start a factory run with `nightshift <ticket-ref>`. Runtime adapters may also expose
  the same core command as `$nightshift <ticket-ref>` or `/nightshift-eng <ref>`.
- `nightshift batch <tickets-or-query>` runs independent tickets autonomously. Use
  `--branch auto --push` to commit and push each verified ticket branch, and
  add `--pr` only when a pull request should be opened. These flags never merge
  or deploy production.
- Codex, Claude Code, and local-model runners must use the same artifacts,
  provider routing, and policy. No runtime is the canonical implementation.
- Keep `nightshift` checked out: a symlink install deliberately uses this
  checkout as the source of truth for upgrades.

## Autonomy and confirmation policy

Proceed without asking for confirmation for read-only work, searching, edits,
creating files, tests, commits, branches, worktrees, and other reversible
workspace changes that the user requested or that are a normal part of a
requested nightshift stage. Do not introduce approval stops for hypothetical risk.

Ask for explicit confirmation only immediately before permanently deleting or
removing data/files/branches (including a history rewrite that removes remote
history) or before a production deployment. Do not add a confirmation gate just
because an operation edits, commits, pushes, opens or merges a pull request, or
deploys to development/staging. A request to run `/nightshift-deploy` does not itself
authorize its production deploy; prepare and validate everything else first,
then present the exact production command and target for confirmation.

Unattended runtime modes may remove CLI permission prompts. That makes the
policy gateway planned in `docs/DARK-FACTORY-EPIC.md` essential: prompt text
alone is not a security boundary.

## Factory mode

When `NIGHTSHIFT_FACTORY_MODE=true`, a failed test, review, drift, QA, or CI gate is
not a reason to wait for an operator. Make the smallest in-scope repair and
retry that gate, recording each attempt. Limit automatic repair to three
attempts per gate. On exhaustion, leave a concrete failure receipt and stop
only that ticket; a batch continues with its other tickets.

## Project conventions

- Everything installed by nightshift must keep the `nightshift-` prefix.
- Beads is a local ledger, never the upstream ticket source of truth.
- Do not invoke gstack commands or agents from a nightshift workflow.
- Role prompts are runtime-neutral. Do not add provider-specific tools or a
  static `model:` key to `agents/nightshift-*.md`; routing belongs in `routing.json`.
- Prefer `scripts/nightshift-capability.sh --has <tool>` over ad-hoc capability checks.

<!-- mex-agent:skills:start -->
## MEX agent skills
- At the start of every session, read `.mex/AGENTS.md` and `.mex/ROUTER.md` before project work; follow `ROUTER.md` to load only the relevant context.
- Use `$mex-inbox` for durable governed Spec proposals and `$mex-relay` for durable team handoffs. Invoke them automatically when intent clearly matches; explicit invocation remains available.
- When MEX context materially influences an answer or implementation, include one concise acknowledgement: `MEX context used: <specific records/files/entities consulted>.`
- Do not claim an author, date, or historical event unless the retrieved data actually provides it.
- After a MEX write, say exactly what changed and its sharing boundary: a local draft is checkout-only and nothing is shared; a canonical artifact is written to the working tree and requires commit/push to share.
- Skill activation is not approval for canonical actions.
<!-- mex-agent:skills:end -->

## Work planning and verification

- For non-trivial work, record a plan with checkable steps in the existing task
  tracker before implementation. Include scope, acceptance criteria and verification.
  Follow the canonical stage artifacts rather than introducing a second ledger.
- When evidence invalidates the plan, pause the affected work, revise the plan and
  continue within scope. Preserve failed attempts and apply the factory repair limit.
- Track completed steps and record results, commands and relevant evidence in the
  task tracker. Completion depends on passed gates, not an elapsed-time target.
- Use focused delegation when independent research or analysis benefits from it;
  give each worker a clear task and integrate its evidence before proceeding.
- Prove the changed behavior before marking work complete. Inspect the relevant
  diff, run appropriate checks and assess whether the evidence supports acceptance.
- Prefer the simplest complete solution. Fix root causes, minimize unrelated changes
  and reconsider a complicated repair before presenting it.
- Resolve actionable bug reports and failing checks autonomously within authorized
  scope. Ask for clarification only when missing information prevents sound progress.
- After a user correction, record the reusable lesson in the existing task tracker
  and apply it to subsequent work. Review relevant lessons when resuming the task.

Model work has no default elapsed-time deadline. Record duration as telemetry;
completion requires evidence gates. An explicit operator timeout may bound a call.
Keep short availability probes and process cleanup bounded.

Plans and lessons do not add approval gates. The autonomy and confirmation policy
above remains authoritative.
