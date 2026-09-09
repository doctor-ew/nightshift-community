# Independent test preparation and recovery

The implementation commits d2929e9 and 45bfecb precede issue 13 spec and RED seals.
Fixture API edits 2c51e26 and 8dfc146 also precede those seals. Preserve this history;
these commits are not evidence of test-first development. Recovery requires an
independent specification challenge, bootstrap acceptance, meaningful regression
failures against the existing implementation, and new explicit seals before further
implementation. Existing engine code is incomplete, not approved proof.

The initial metrics diagnostic failed on the sandbox's common-Git update lock.
The same diagnostic with approved filesystem permissions passed the existing
metrics assertions. This does not establish proof admission: the current dispatch
boundary accepts a syntactically valid task without checking its proof gate.
The new independent regression supplies a task but no proof and observes provider
launch, establishing a meaningful behavioral RED.

The shared test fixture builds an ordinary deterministic task, observes an actual
unittest assertion failure, uses existing spec/RED locks, and submits the normative
seal and record-red APIs. Existing dispatch and metrics assertions remain intact;
their setup now needs genuine development admission rather than only a task flag.
No production admission bypass is introduced by fixture adoption.

Retained external logs: nightshift-13-metrics-diagnosis.log,
nightshift-13-metrics-diagnosis-escalated.log, and
nightshift-13-engine-independent-red.log under the session's private temporary
artifact directory. Runtime provider calls remain prohibited until design and
bootstrap-prompt review are approved. Public and private bootstrap case bodies
remain outside this checkout; no manual result is imported as an engine receipt.
