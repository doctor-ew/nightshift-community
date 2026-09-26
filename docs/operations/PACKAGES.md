# Versioned work-package contract

## Status

This is the contract-first slice of #67. It validates supplied graphs using the
existing decomposition validator and operation plans. It does not schedule
children, approve a decomposition, reserve allowances or report parent completion.
Graph execution, independent preparation/challenge admission, child integration,
restart accounting and parent behavioral acceptance remain required under #67.

## Inputs

`contracts/nightshift-package-plan.schema.json` describes version 1. A graph has:

- The existing versioned decomposition, including parent requirements, child
  references, dependencies and exactly one final integration child.
- Reusable versioned templates selecting the existing factory operations or the
  read-only integration sequence: rule resolution, adoption, Verify and Review.
- Each package's operation task, template, canonical reads and owned writes, and
  interface identifiers it provides or requires.
- A preparation task whose specification artifact is the exact graph JSON.
- An aggregate allowance covering preparation and every child allocation.

Each package consumes its existing operation plan. The declared specification
must equal the decomposition source reference. Scope files and verification
scripts must be declared reads. Missing reads require an explicit self/ancestor
output producer. Required interfaces must come from an ancestor package.

## Deterministic checks

`python3 scripts/nightshift-packages.py --project <repository> --plan <graph-file>`
returns structured validation. The path arguments are caller-supplied values.
This command reads files and launches no provider.

The validator rejects unsupported versions/recipes, duplicate identities, missing
requirements/dependencies, cycles, overlapping file writes, ancestor/descendant
file collisions, path aliases, control-artifact writes, undeclared source/interface
dependencies and allocations exceeding the parent ceiling. Integration owns no
writes. Child and preparation publication targets require separate authority.

Bindings include the supplied manifest, parent source, package operation plans,
read inputs and preparation plan/artifacts. Structural validity reports
`semantic_approval: false` and `authorized: false`; those boundaries are explicit.

## Scheduler constraints

The next slice must retain isolated child workspaces because operation evidence
binds the whole source corpus. It must pin the original parent deadline, partition
allowances before child authorization, retain unknown usage, and reuse durable
child identities. Combining passing children still requires parent Verify and
independent Review. Mixed author provenance must not be relabeled as human or
controller authorship. Unsupported nested graphs or concurrency must fail
explicitly until their authority and accounting are implemented.

## Verification

`tests/test-packages.py` and `tests/test-package-contract-review.py` contain
synthetic, model-free contract regressions. No installed runtime, real tickets,
live allowances, providers, merge or deployment are involved.

Independent design/code review approved validator SHA-256
`b46f8c20c1af5726ec805b99b45a13ba101ec046ae164825804e7e6d9b12f7a8`.
Seven author regressions and thirteen independent adversarial regressions pass.
The independent suite covers preparation/parent control writes, path aliases,
file-prefix conflicts, undeclared sibling inputs, missing sources, static budgets,
source binding and manifest/preparation disagreement. Provider calls and token
usage are not measured by contract validation because no provider is invoked;
no savings or semantic quality claim follows.

Verification checklist: names retain the installed prefix; no shared role or
provider policy changed; upstream references retain the existing decomposition
contract; relevant fixtures pass; no trajectory schema changed; scaffold claims
cite the implemented files; graph execution and live readiness remain unverified.
