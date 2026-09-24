# Jobs Night evaluator calibration

This is public synthetic checker calibration, not application behavioral proof and not approval to skip Nightshift gates.

`calibrate.py` reads the retained JN-1 public scenarios and checker corpus. It derives source maps from supplied paragraph IDs (or the specified nonblank-line scheme), checks the whole-output contract and reciprocal citation/excerpt binding, and requests independent semantic judgments only after literal and structural checks pass. It never opens private heldout cases.

Acceptance requires all 11 good examples to pass, all 63 established wrong examples to fail, and all six gap probes to fail. Unknown is not rejection evidence: it stops calibration. `--only` supports diagnosis but a filtered result does not establish full-corpus acceptance. Real calls, usage, source/engine hashes, explicit model selection and verdicts are retained in the report. Calls here are calibration work, outside the Jobs Night ticket's proof counters.

The local provider is configured by the supplied routing file. `--model`, `--response-format` and `--normalization` are explicit calibration-only overrides, never automatic fallback. A passing combination must be recorded in the consumer configuration before proof. Structured-output availability varies by backend; JSON validation and exact evidence checks remain mandatory even when a backend accepts a response-format parameter.

Early retained attempts demonstrate local verdict-format and exact-quote failures. They are not successful proof. Do not overwrite those receipts or interpret model availability as evaluator correctness. The original public corpus is retained untouched in the JN-1 worktree.

The retained Devstral run uses explicit line references for evidence, response format `none`, and normalization `json-or-single-fence-v1`. The controller resolves references to exact completion lines and preserves both the raw transport and resolved verdict. Normalization only accepts a complete JSON object or a single enclosing JSON fence; it never repairs fields or changes a judgment. Read the report completion fields before treating this combination as calibrated.

## Current result

No configuration has passed the full live calibration yet. Devstral accepted 78/80 controls but missed both semantic negative probes. Qwen3-Coder-Next correctly rejected the ownership probe, but the complete line-ID run stopped on duplicate criterion IDs after three valid controls passed. These are retained failures, not application proof. The local server logs report structured output requires the missing xgrammar dependency; response_format alone is not currently enforced. The Jobs Night batch remains blocked, with original proof state and counters unchanged.

## Frontier harness repair

Commit 410a8cc adds the native Codex subscription evaluator and a configuration allowlist for Claude/Codex routing. Independent adapter and routing review passed; 30 evaluator tests, 125 dispatcher assertions, provider-policy tests and seven gear-router assertions passed.

The retained codex-frontier-results.json contains 80 evaluated public controls, 13 actual evaluator CLI invocations and no unknown verdicts. All 63 established negatives and all six gap probes were rejected. Five originally labeled good controls passed; six were rejected. These disagreements are retained, not relabeled or approved. Independent review confirmed the c1 fixture contradicts the prompt's AND-splitting requirement and omits frequency/maintenance distinctions. The other rejected controls require consumer review. Calibration is not application proof.

The harness transport is repaired. Consumer design/fixtures still need independent correction before implementation proof. User then asked about a fresh start; no application restart was launched pending reset scope. Local investigation remains deferred.
