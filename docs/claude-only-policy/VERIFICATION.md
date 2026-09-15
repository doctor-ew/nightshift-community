# Claude-only provider policy verification

## Scope

Explicit project or per-run provider restriction for the factory, role dispatcher,
automatic route selection and behavioral-review admission. Default cross-provider
review remains unchanged. Same-provider review requires a fresh dispatcher-owned
invocation and a policy-bound receipt. No Foundry adapter is included.

## Checks

- Dispatcher regressions: 117 assertions passed, including automatic local-route
  replacement, same-provider review provenance, fresh-session flags and missing-route
  rejection before provider launch, plus restricted copy/symlink installed calls.
- Factory authentication regressions passed, including Claude default selection and
  rejection of explicit Codex/local overrides under a restricted project policy.
- Behavioral-proof suite: 26 tests passed, including default-policy rejection of a
  same-provider challenge, explicit-policy acceptance and rejection of approval reuse
  after reverting to standard policy.
- Dedicated policy suite passed: project/global/inherited restrictions, invalid values,
  primary-checkout inheritance in a nested worktree and hosted extraction selection.
- Offline harness: 36 of 38 suites initially passed. The two failures were isolated
  fixture integration issues: the trajectory sandbox omitted the new helper, and the
  branding policy's exact dispatcher exception needed the fresh-session flag. Both
  failing suites passed after their narrow repairs. The new policy suite was added
  after harness discovery and passed separately.
- ShellCheck at warning severity and per-file Bash syntax checks passed.
- Live Claude subscription review returned SUCCESS with dispatcher-stamped Claude-only
  policy and fresh-session provenance; see live-review.json.

## Limits

The live call was a synthetic review, not a complete Jira ticket run. Provider
restrictions apply at managed Nightshift launch boundaries; they do not sandbox
arbitrary shell commands or independently started tools. Session independence does
not provide cross-provider diversity. Workplace network controls remain separate.

Independent Claude source review: SUCCESS with no blocking findings. The reviewer
inspected the implementation and did not execute the test suites; test results above
are from the controlling session. See independent-review.json.
