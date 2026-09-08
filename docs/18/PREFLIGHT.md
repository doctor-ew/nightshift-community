# Preflight: ticket 18

Ready for integration PR, subject to CI. Target: integration/nightshift only.

- Full harness: 32/34 initially; existing factory-auth and state-dir suites passed
  after physical-root fixture setup corrections. Combined result: 34/34.
- New context suite: 15 methods, zero skips.
- Independent source review: APPROVE; runtime acceptance: PASS.
- Diff scope and whitespace: PASS; shell syntax: PASS.
- Temporary copy installation: PASS, including shared policy and legacy resolver.
- No active installation synchronization, Coach mutation, main merge or deployment.

Runtime models observed: Claude haiku for test cases, Claude sonnet for code review,
Codex gpt-6-astra for test cases. The repository-configured gpt-5.4 was rejected before
execution; fixture-only routing used a locally listed subscription model. Paid API
fallback was never enabled. Provider aliases are observed names, not immutable backend
revision claims. The shared runtime retains its existing read-only Codex role sandbox.
