# Public development evidence repair

Actual coach development failures exposed a runtime diagnostic gap: observations retained completion hashes but discarded response text. This change stores bounded public development turn evidence, including actual student input, parsed completion, and per-assertion satisfaction. Final completion bodies and raw transport stdout remain absent from retained proof evidence.

Each artifact has a unique charged attempt name and a canonical JSON hash reference in its observation. Records preserve the original grading result. A failed evidence write reports an unavailable artifact without altering acceptance or budget accounting. Retained files are diagnostics, not a substitute for the authoritative ledger or independent semantic review.

A runtime update requires a fresh independent challenge and reseal. Runtime-only reseals preserve prior failure identities, require the unchanged prototype, and retain all original counters and observations. The next actual prompt edit consumes the normal repair budget. Historical missing completion bodies cannot be recovered or recreated.

## Evidence

The initial regression failed with two missing development evidence references: `public-evidence-red.log`. Initial 13-test retention/privacy regression passed: `public-evidence-green1.log`. Expanded 14-test regression, including runtime-only reseal accounting, passed: `public-evidence-green2.log`. Additional privacy sentinel and unknown-transport checks passed: `public-evidence-green3.log`. The existing 25 proof tests passed: `public-evidence-proof.log`. These are offline synthetic fixtures; no consumer model calls or consumer ledgers were changed.

## Independent review repair

The reviewer found that an initial broad failure-lineage lookup also allowed prior-engine successful observations into accepted cases. The dedicated regression reproduced incorrect acceptance in `public-evidence-review-red.log`. The repair limits accepted cases to the exact current seal. Failure lineage remains confined to failure reporting and retry guards. New tests require fresh launches after resealing a prior success, reject a simultaneous uncounted prototype change, and exercise evidence write failure without changing grading or counters.

Final validation: `public-evidence-green5.log` records all 18 tests passing in 32.776 seconds; `public-evidence-proof-final.log` records all 25 existing tests passing in 38.910 seconds. Independent review approved engine SHA-256 `751845451183ca1b72d6d3a075d6ea898905116afc5bc6b0a61114231d59b374`; see `PUBLIC-DEVELOPMENT-REVIEW-20260909.md`.
