# Optional semantic assistance in retained-ticket recovery

## Implementation

A committed recovery plan may explicitly select `semantic_mode: "independent"`.
The default remains `jev`. Selection is part of the assessment digest and requires
its own explicit bounded recovery authorization; a plan file grants no authority.
Independent mode uses the configured tool-free independent reviewer for each
bounded obligation and does not require Jev configuration or credentials. It does
not fall back to another mode after dispatch or recover an exhausted allowance.
The existing independent transport supports Claude subscription review; other
provider routes remain explicitly unavailable for this transport.

Both modes retain deterministic verification, complete evidence mapping, exact
source binding, controller locking and manual acceptance. Independent mode keeps
separate mode/route/authority cache identities. Each new review reserves one call
before dispatch. Pending, blocked and cached decisions never trigger a replacement
call. Changed source, observations, mode or authority invalidate affected evidence.

The retained independent input envelope uses the exact same UTF-8 serialization
as its reservation and byte limit. The maximum envelope is 24,576 bytes, with
4,096 bytes of observation headroom during preflight. This metric excludes CLI
role/schema framing and provider tokens; unknown usage must remain unknown.
Responses must bind the exact packet, reviewer identity and supporting evidence.
Retained artifacts are revalidated before reuse or gate approval.

Failed deterministic checks remain visible in read-only assessment output instead
of being replaced by a semantic-packet validation error. Manual-only acceptance
criteria cannot be approved by automated decision rows; they remain bound to the
scenario document and exact manual-case list. Successful recovery still ends at
pending manual acceptance.

## Integration and certification

Synthetic regression suites cover independent dispatch, exact input byte/hash
accounting, default assisted-mode compatibility, cache and artifact invalidation,
unknown reservations, exhaustion, explicit mode changes, failed verification and
manual acceptance boundaries. The offline harness includes these suites through
`tests/test-recovery-independent.sh`.

Independent design and code review approved the implementation. All 71 focused
and regression tests pass (27 independent recovery, nine assisted recovery,
20 decision-engine and 15 legacy controller tests). The actual dispatcher fixture
made four synthetic calls with exact input envelopes of 5,029, 3,025, 3,060 and
3,018 bytes (14,132 total), reused one receipt across five gate evaluations, and
made zero additional calls for a duplicate. No real provider was invoked; token
and billing usage and CLI framing remain unknown.

Full hosted
CI is evaluated on the published revision separately. No live provider invocation,
allowance grant, retained-ticket restart, installed-runtime activation, merge or
deployment is part of these tests. A concrete endpoint-specific proposal must name
the source/runtime revisions, assessment digest, payload scope, reviewer route,
request bounds, total allowance and remaining manual acceptance.
