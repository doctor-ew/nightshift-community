# Independent review of public development evidence retention

Date: 2026-09-09

Decision: **Approve the reviewed runtime repair**. One blocking review finding
was repaired and independently retested. This approval covers the runtime delta,
not the coach's failed behavior or any proof-gate outcome.

## Reviewed source

Checkout: `/private/tmp/nightshift-coach-continuation-20260909`

| File | SHA-256 |
| --- | --- |
| `scripts/nightshift-behavior-proof.py` | `751845451183ca1b72d6d3a075d6ea898905116afc5bc6b0a61114231d59b374` |
| `tests/test-behavior-multiturn.py` | `43fda63fb7428b6a506ac84cdf889dec51d75e8876059d361457b000804db62e` |
| `docs/BEHAVIOR-PROOF.md` | `2f4909e542b35de3dcc8ff45399d00cdf6a4c885d37aa57b5b63c5f1bef4d830` |

The uncommitted delta and surrounding sealing, acceptance, grading, accounting,
and public-writing code were inspected. The checkout's `AGENTS.md` was read.
No consumer private heldout inputs or final completions were inspected.
Offline test fixtures are synthetic regression data.

## Finding and repair

The initial delta made `accepted_cases` use ancestor seal identities through
`failure_bound`. That would allow a successful observation made under an older
engine hash to satisfy the new engine's gate after a runtime-only reseal.
Retaining failure history must not carry forward successful proof under a
different engine. The author reproduced this finding in
`/private/tmp/runtime-public-evidence-review-red.log`; the regression expected
the resealed gate to reject old success and observed the incorrect success.

The repaired code requires the exact current seal in `accepted_cases`.
Ancestor seal identities are used only to retain failure retrieval and blocking.
The added regression requires new model launches after a successful old-engine
seal, and passes in the independently executed suite.

## Verified behavior and boundaries

Development-only branches persist parsed completion and current public student
input, assertion-satisfaction arrays, identifiers, and source hashes. Final runs
do not enter that write branch. The evaluator is reused for diagnostics without
changing its acceptance logic. The evidence size check uses the existing 4 MiB
bound; unavailable artifacts receive an explicit error marker without changing
grading or consuming another model launch.

Runtime-only resealing requires the same prototype and retains failed-seal
lineage and existing counters. A simultaneous prototype change is rejected;
the subsequent prototype revision consumes the ordinary repair budget. Prior
passes are not accepted under the new seal. These changes do not authorize
resampling a failed unchanged prompt or resetting earlier attempts.

Independent execution from the reviewed checkout:

```
python3 tests/test-behavior-multiturn.py
Ran 18 tests in 32.801s
OK
```

The suite covers public retention, final-body exclusion, failed development
retention without resampling, old-pass non-reuse, retained repair accounting,
simultaneous prompt/reseal rejection, evidence write failure, and existing
multi-turn behavior. `git diff --check` also passed. The reviewer did not execute
a live provider call, inspect consumer private fixtures, or claim real coach
behavior was repaired. The size-bound branch was inspected statically; this
review does not claim a dedicated size-limit regression was executed.
