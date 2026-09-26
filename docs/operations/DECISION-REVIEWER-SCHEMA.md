# Packet-bound decision reviewer output

The decision reviewer receives a generated JSON schema whose evidence values are the exact reference IDs in its packet. The packet hash and reviewer identity each have a single allowed value. Evidence explanations belong in the top-level reason; annotated IDs remain invalid. The controller still checks every response and requires complete role coverage for a positive verdict. A schema is an output constraint, not an approval.

`scripts/nightshift-decision-render.py` renders the system prompt, user prompt, and provider JSON schema once for dispatch and read-only recovery preflight. Their combined UTF-8 argument content must fit 24,576 bytes. This count excludes executable names, other command arguments, CLI framing, network bytes, and provider tokenization. Oversized requests fail without truncation. Verified recovery assessment reports each packet's exact framing measurement; initial readiness uses bounded placeholder observations.

Independent and assisted reviewer reservations count their exact serialized input envelope separately. Input-envelope bytes are not total provider request bytes or token usage. No mode switches, extra allowances, retries, or model changes are authorized by rendering or schema validation.

Synthetic validation uses fictional reference IDs and disposable repositories. The actual launcher receives a synthetic provider executable that checks its schema and argument sizes. An intentionally noncompliant annotated response remains blocked; valid, negative, abstaining, and incomplete-coverage responses preserve their existing controller semantics.

The provider projection uses supported enums and retains `minItems: 1`; it omits unsupported uniqueness, maximum-item, and numeric-minimum constraints. Canonical contracts and deterministic result validation remain authoritative. See [Claude structured output schema limitations](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
