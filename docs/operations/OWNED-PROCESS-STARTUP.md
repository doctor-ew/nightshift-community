# Owned process startup cancellation

## Implementation

Cancellation handlers are installed before the owned command starts. Startup is
inside the cleanup scope. Cancellation, an absent parent or an expired deadline
observed before launch prevents command creation. Cancellation during launch
retains the command handle and uses the existing owned process-group cleanup.
Normal exit status and launch errors remain observable. Unrelated processes are
not targeted. This does not claim guaranteed cleanup after an uncatchable kill.

## Integration evidence

Code revision: `8af9fb50167c9b2eaa56dc533b6061fb3aec8f46`.
Nine independent disposable-process regressions pass on the committed revision.
Five regressions fail against the original helper, including both signal races
and admission after cancellation, parent loss or deadline expiration. The existing
supervisor regression also passes. Tests cover parent death after startup,
normal completion, missing commands, deadlines and unrelated-process survival.

The fix builds on the public acceptance prerequisite used by PR 98. It is a
focused prerequisite correction, not acceptance of all cancellation/reconciliation
behavior. Issue 71 remains open until the integrated controller meets acceptance.

## Certification boundary

There are zero provider calls and zero provider request bytes. Tests create only
disposable owned processes. No live providers, real tickets, installed runtime,
merge or deployment changed. Live certification remains unperformed.

## Repository verification checklist

- PASS: Existing runtime-neutral process ownership is reused.
- PASS: Independent review and negative controls exercise the actual startup race.
- PASS: No unrelated process is selected for cleanup.
- UNCHANGED: Provider routing and trajectory schema.
- UNVERIFIED: Full cancellation integration and live endpoint certification.
