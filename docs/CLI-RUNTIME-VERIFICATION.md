# CLI runtime shorthand verification

Verified locally on 2026-09-11. Implementation is installed in
`/Users/doctorew/shuttlebay/nightshift-community-runtime` and retained in the
source checkout. The launcher symlink points to that installed runtime.
Changes are uncommitted; no remote branch, release, or deployment was published.

## Behavior

| Invocation | Factory selection |
| --- | --- |
| `nightshift prompt.md` | Configured runtime/model, otherwise Codex and its default model |
| `nightshift codex prompt.md` | Codex with its configured model default |
| `nightshift codex/qwen bd:bead-123` | Configured `qwen` alias: local Ollama, `qwen3-coder:30b` |
| `nightshift codex/devstral prompt.md` | Configured `devstral` alias: local Ollama, `devstral-small-2:24b` |
| `nightshift local/organization/model:tag prompt.md` | Literal Ollama model name |

Sources: `scripts/nightshift-factory.sh:66`,
`scripts/nightshift-factory.sh:123`, `scripts/nightshift-factory.sh:239`,
`nightshift.toml:17`.

Aliases are extensible in consumer/global TOML. Explicit flags override
shorthand. Project model settings take precedence over global settings, without
attaching a legacy model to a different provider. Sources:
`scripts/nightshift-factory.sh:231`, `scripts/nightshift-setup.py:51`.

The selected factory does not silently switch runtimes. Hosted runs retain the
subscription default and explicit per-run API opt-in. Local alias inference uses
Ollama; specialist/reviewer routing stays configured separately, so this is not
an assertion that the entire workflow is offline. Sources:
`scripts/nightshift-factory.sh:282`, `scripts/nightshift-factory.sh:333`,
`scripts/nightshift-agent.sh:198`.

## Checks completed

- PASS: CLI shorthand, configured defaults, project/global precedence, arbitrary
  aliases, both bundled local aliases, literal model names, file paths/spaces,
  ticket and batch inputs, malformed settings, and no factory fallback.
  `tests/test-factory-cli.sh:1` tests a temporary copy installation through its
  symlink and updater. Result: `/private/tmp/nightshift-final-cli-tests.log`.
- PASS: factory authentication and Claude dispatch/resume/exit-status fixtures.
  Source: `tests/test-factory-auth.sh:1`.
  Result: `/private/tmp/nightshift-final-auth-tests.log`.
- PASS: preflight admission and retained-state invariants.
  Source: `tests/test-factory-preflight.sh:1`.
  Result: `/private/tmp/nightshift-final-preflight-tests.log`.
- PASS: three setup tests (`tests/test-setup-ux.py:16`) and nine release/local-input
  tests (`tests/test-release-inputs.py:18`). Release result:
  `/private/tmp/nightshift-release-tests.log`.
- PASS: ShellCheck at warning severity on the changed shell files and
  `git diff --check`. Implementation files in source and installed runtime were
  compared byte-for-byte and matched.
- PASS: Qwen through real Codex/Ollama returned the requested sentinel, exit 0.
  Result: `/private/tmp/nightshift-qwen-smoke/response.txt` and `smoke.log`.
- PASS: Qwen executed a shell tool and returned an unpredictable file sentinel
  exactly under the default factory policy (approval never, danger-full-access).
  Result: `/private/tmp/nightshift-qwen-factory-policy-smoke/result.json`.
- PASS: both model downloads completed. Devstral also returned the requested
  sentinel through Ollama's local generation endpoint.
  Result: `/private/tmp/nightshift-devstral-generate.json`.
- PASS: Devstral executed one shell tool, returned the unpredictable file
  sentinel exactly, and exited 0 under the default factory policy.
  Result: `/private/tmp/nightshift-devstral-factory-policy-smoke/result.json`.

## Evidence limits

These are launcher integration tests and bounded local-model smoke tests, not a
completed end-to-end Nightshift ticket or a model-quality benchmark. The Qwen
smoke log includes Codex's warning that model metadata was unavailable and
fallback metadata was used. The response still succeeded; long-workflow context
behavior is not certified by this test.

Earlier standalone probes using read-only/workspace-write sandboxes failed:
the models requested escalation, which approval mode never rejected. The local
factory prompt now explicitly directs default tool permissions. Both models passed
with the factory's actual default sandbox policy; branch-none/restricted local
model tool use remains unverified. Sources:
`scripts/nightshift-factory.sh:331`,
`/private/tmp/nightshift-qwen-catalog-smoke/stderr.log`,
`/private/tmp/nightshift-devstral-default-permissions-smoke/stderr.log`.

Both models were installed and smoke-tested sequentially on a 64 GB Apple M3
Max using Codex CLI 0.154.0 and Ollama 0.33.3. The default local context observed
in Ollama was 262144 tokens; Devstral's load used about 59 GB and was partly
CPU-backed, so this is not a low-memory or latency benchmark. Test-loaded
models were stopped afterward without removing either downloaded model.

The MEX impact resolver reported a stale source corpus. Direct source inspection
was used; no refreshed graph grounding is claimed. MEX setup/context/pattern
updates are working-tree changes and require commit/push to share.
