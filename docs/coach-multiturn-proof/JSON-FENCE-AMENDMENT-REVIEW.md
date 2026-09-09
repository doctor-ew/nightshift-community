# Independent runtime review — JSON wrapper and policy amendment

Date: 2026-09-09. Reviewer: primary coach implementation agent, independent of
the runtime change author. Decision: approve the runtime change for publication
after required GitHub checks. This is not approval of coach behavior.

Reviewed the complete changes to the behavior proof engine, retry policy bounds,
multi-turn regression tests, existing schema test, and behavior-proof guide.
Engine SHA-256: `9280ff1d4515976b9bd355488fa3ca1745730b9341bfde558028e36cb3984b57`.

The optional `response_normalization` field leaves strict parsing as the default.
Its full-response fence match removes only a complete outer wrapper before the
existing strict JSON parser. Multiple blocks, extra prose, malformed content,
duplicate keys, and nonfinite values cannot obtain a JSON-assertion pass.
Text and prohibited-content checks use the original text; retained evidence and
conversation replay likewise preserve it. Metadata and provider envelopes are
not normalized. Public/private runtime equality and seals bind this choice.

The policy amendment is a separate operation, with previous policy digest,
complete target policy, authorization file digest and independent review digest.
It permits only bounded cumulative limit increases and rejects pending attempts,
stale amendments, altered authorization and unreviewed evidence. It retains used
counts, attempts, observations, and old seals. Other operations still reject a
configuration changed without amendment. A fresh challenge and seal are required.
The strengthened reseal check prevents hiding a prompt edit inside migration;
policy-only reseals retain failed-prompt restrictions.

The regression suite covers strict-default rejection, opt-in acceptance, malformed
and ambiguous wrappers, original-text checks and replay, preserved failures and
exhausted counts, private final execution, and a cumulative cap increase with
two repairs retained and a subsequent repair charged as three. The author
reported 23 multi-turn tests and 25 existing proof tests passing; retained logs
are included beside this review. No new blocking issue found in the diff.

Authorization records and review identities are trusted workflow evidence, not
cryptographic identity authentication; the documentation states that limit.
No private coach case bodies were inspected during this review.
