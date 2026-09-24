# Local evaluator investigation — after frontier run completes

Status: deferred by user; do not route this Jobs Night run to local models.

Determine which installed local model and serving configuration can perform each Nightshift role reliably, and why prior attempts failed. Use the retained public synthetic corpus under evaluator-calibration; never expose private final cases or count calibration as application proof.

Compare Qwen3-Coder-30B, Qwen3-Coder-Next, Qwen3.5-9B and Devstral against the passing frontier baseline. Record exact model/quantization, oMLX version, grammar support, reasoning settings, hardware/memory pressure, prompt/schema versions and warm/cold timings. Separate transport-format failures from incorrect semantic judgments. The retained Devstral run missed ownership inflation and a coaching request; QwenNext correctly identified ownership inflation but later emitted duplicate criterion IDs.

Acceptance: all 11 valid controls accepted, 63 established negatives and six gap probes rejected, with no unknowns. Repeat runs and add independently prepared paraphrase variants to measure stability rather than selecting a lucky result. Report false acceptance, false rejection, schema-valid first responses, latency, tokens and any repair calls. Preserve every failed attempt. Compare time and cost per independently passing completed ticket, including retries and server overhead; local availability alone is not savings.

Recommend role-specific routing only after those measurements. Keep Claude/Codex available for independent review and escalation; enable local routing explicitly through configuration after validation.
