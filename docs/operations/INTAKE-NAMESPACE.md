# Intake namespace validation

## Implementation

A bare GitHub reference previously accepted a response from another repository when
its returned URL agreed with its returned repository. Intake now compares source
identity with the shared source normalizer's independently derived requested
identity. Explicit repository references still override the project origin. The
existing direct issue-number check remains in place. Missing origins fail closed
for bare references. Source resolution remains bounded and noninteractive.

This focused change builds on integration revision
`f870a83677e166b35ff2a00766293f238e000ea4`, preserving its context binding,
create-only file journal, mode checks, symlink protection and coordinated UI.
The broader alternative intake implementation is retained separately; it is not
the selected integration profile.

## Integration evidence

Code revision: `bfec18e06e94d4cff98f7d86ba5ccc713d5cb262`.
Independent review approved intake SHA-256
`937f56c0a55ca42ed6ff22793127ef265fe1075a97d035482e24b951a0834770`.
Nine independent namespace regressions and fifteen convergence regressions pass;
the existing six intake and eleven interface/review tests pass. The browser test
also holds requests open to check both directions of intake/operation exclusion.
Exact committed browser evidence is recorded in `INTAKE-NAMESPACE-VALIDATION.json`.

## Certification boundary

All provider execution uses synthetic fixtures and disposable repositories.
Provider authentication, live model quality, token usage, provider cache usage,
billing and fresh-machine certification remain unverified. No installed runtime
was changed. No merge or deployment was performed. Issue 69 remains open for
its full integrated acceptance and endpoint-specific certification under issue 2.

## Repository verification checklist

- PASS: Installed names retain the prefix; shared roles remain runtime-neutral.
- PASS: Requested upstream identity is independently checked; Beads is not authority.
- PASS: Existing and independent fixtures exercise the changed boundary.
- UNCHANGED: No trajectory evidence-schema change.
- PASS: Claims reference source and recorded fixture evidence; graph grounding is unavailable.
- PASS: Live readiness and unknown provider usage remain explicitly unverified.
