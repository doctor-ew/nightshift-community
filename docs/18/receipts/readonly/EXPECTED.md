# Read-only legacy fixture correction

The earlier fixture failed before its test because its receipt write is forbidden
by the preserved Codex read-only sandbox. This correction removes that harness
write requirement. The single unittest still asserts the exact received arguments
and emits them to stdout. Actual execution must be established from the externally
retained Codex command tool event, not from the model's report.

Keep prior fixture attempts and reports unchanged. Use the normal dispatcher,
subscription authentication, configured model, and unchanged read-only sandbox.
Capture the real Codex CLI JSON event stream through an external wrapper that tees
stdout while preserving the process exit code. The wrapper must not synthesize or
rewrite events. Keep fixture hashes unchanged.

Acceptance: normalized SUCCESS report with one passed test, zero failed tests,
exact command/source-line provenance; a successful tool execution event for the
specified fixture command whose output contains the exact argv array and one-test
unittest success; unchanged fixture files. Provider narrative alone is insufficient.
