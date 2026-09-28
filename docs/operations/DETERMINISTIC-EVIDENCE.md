# Deterministic evidence (recovery plan version 2)

Slice 1 of the semantic-review cascade proposed on #65: code proves what code can
before any reviewer is asked. Version 1 plans are unchanged.

## Generated artifacts are proven, not reviewed

A version 2 plan may declare files that a generator reproduces from committed
source:

```json
"generated": [{"path": "starter/instructions.js", "argv": ["python3", "starter/build.py"]}]
```

During verification, in the isolated copy of the bound workspace, Nightshift
removes each declared file, runs its generator, and requires that the file is
recreated byte for byte and that no tracked file changed (`git status
--porcelain --untracked-files=no` is empty). Generators run before the checks, so
the checks see exactly the committed bytes. A generator that fails, does not
write the file, writes different bytes, or changes another tracked file fails
verification and no check runs. Results are retained in `verify.json` under
`generated`.

A proven artifact is removed from the every-line review coverage requirement,
and citing it as review evidence is an error
(`recovery_decision_generated_not_evidence`). The declaration must match between
evidence collection and the plan, and the path must be a changed source file.

Why: one live ticket split a 94-line generated file into four review packets and
asked its single acceptance criterion fifteen times, although an existing check
already proved the file equal to its source.

## Every case is traceable to an assertion that names it

For each case a decision covers, at least one cited assertion span must contain
the case ID as a whole token (a test name, tag or comment such as `CASE-2`).
Otherwise the plan is rejected before any provider call
(`recovery_decision_case_untraced:<decision>:<case>`). A lookalike such as
`CASE-2-extra` does not match `CASE-2`.

Why: every blocked live run on the same ticket came from assertion spans that
pointed at unrelated tests (imports, a build check, report-writing code). An
independent reviewer caught each one, but only after paid calls. This rule makes
the mapping explicit in the tests and checks it deterministically. Whether the
named test is adequate remains a semantic question for review.

Validation: `tests/test-deterministic-evidence.py` (9 synthetic tests, run by
`tests/test-recovery-independent.sh`).
