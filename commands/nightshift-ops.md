# Nightshift engineering operations

Run an independently authorized operation or an explicit recipe using the shared
controller. Pass the supplied arguments unchanged to the terminal entrypoint:

```text
nightshift ops <view|assess|authorize|run|chain|migrate> TASK [OPERATION] [options]
```

Use the checked-out `scripts/nightshift-factory.sh` when the entrypoint is not
installed. Read `docs/operations/README.md` for the versioned plan and attestation
format. `view` and `assess` are read-only. A missing prerequisite is a blocker;
never invoke an upstream stage implicitly to satisfy it.

An explicit authorization binds operator identity, current assessed artifacts,
selected operations and bounded limits. Execute only that recorded scope. Reuse
the returned grant ID and the invocation ID on restart. Do not ask again for an
unchanged stored authorization. Never replace an exhausted allowance or relaunch
an unknown invocation. Workers return findings and patches; only the controller
can reserve calls, integrate changes or advance operation state.

The Groom suboperations are independently callable. The factory recipe composes
the same operations and stops before manual acceptance. External adoption records
provenance and still requires deterministic verification and independent review.
Publication requires a separate exact authorization and never merges or deploys.
A successful process launch or exit is not a passing operation.
