# Community-first promotion policy

## Branch ownership

Community `integration/nightshift` is the canonical development branch for
shareable features. Feature PRs target integration, not main. Community main is
the stable release line. Private-only work stays in the private repository.

## Required sequence

1. Merge a reviewed feature PR into community integration with passing CI.
2. Record the candidate integration commit SHA and run the shakedown below.
3. Attach a redacted receipt to the upstream shakedown issue. An independent
   reviewer verifies the evidence and records approval. Missing evidence or
   missing reviewer access blocks promotion; mocks cannot stand in for live runs.
4. Open a promotion PR from community integration to community main, linking
   that receipt and approval. If the candidate advances, retest the new candidate.
5. Merge only after review and required CI pass. The release workflow tags the
   verified main revision after its push CI succeeds. Bump VERSION and plugin
   metadata together for a new release; never move or reuse a release tag.
6. Port the same reviewed public changes into a private topic branch and open
   a PR against private integration. Record the community release SHA, tag and
   source PR. Run private integration checks before merging.

The repositories deliberately have separate histories. Transfer public changes
using reviewed patches or cherry-picks as appropriate; do not merge unrelated
history or force a reset to align repositories. Resolve conflicts explicitly and
preserve private changes. Never push a private branch, mirror or bundle into the
community repository. Public sanitization remains a separate reviewed export step.

## Shakedown acceptance criteria

Initial release validation: [shakedown issue #2](https://github.com/doctor-ew/nightshift-community/issues/2).

- Fresh clone at the candidate SHA; installer uses isolated adapter/runtime/bin
  targets and does not replace the operator's existing installation.
- A small disposable practice Git repository supplies a local Markdown task.
  Verify both `spec:` and bare-path normalization, including a path with spaces.
- Run the actual ticket using subscription authentication and automatic worktree
  isolation. No paid-API fallback. Record the selected provider and model without
  recording credentials or personal paths.
- Preserve Sources and content digest, identifier verification, adversarial review,
  implementation diff, tests and terminal receipt. Independently review the result.
- Start the read-only dashboard on loopback. Verify HTTP response, displayed ticket
  evidence, refresh behavior and process cleanup. HTTP 200 alone is insufficient.
- Run the offline suite and update/lock regression tests. Verify the configured
  source/channel and show that an active terminal run defers update application.
- No merge, deployment, production credentials or unrelated project writes during
  the practice run. Distinguish live, mocked, skipped and failed checks in the receipt.

## Receipt fields

Candidate SHA; source PRs; OS/runtime versions; sanitized install command and result;
practice input digest; provider/model/auth mode; run identifier; evidence and test
results; dashboard observations; update-lock result; independent reviewer identity
and verdict; limitations; overall PASS/BLOCKED/FAIL; links to supporting artifacts.

Do not place raw provider transcripts, credentials, student information or personal
filesystem paths in public issues. Keep raw logs private and attach redacted evidence.

## Enforcement boundary

Main's GitHub rules enforce PRs and CI. The shakedown receipt and independent
approval are maintainer checks, not yet machine-enforced attestations. Do not
describe this document as an automated promotion gate.

Related implementation: [release workflow](../.github/workflows/release.yml),
[update behavior](UPDATES.md), [local inputs](LOCAL-INPUTS.md).
