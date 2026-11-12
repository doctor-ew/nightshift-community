# Preflight — 154 release

**Environment:** production distribution through GitHub Actions; branch push and PR validation precede promotion.
**Branch:** `nightshift/154-release` **Base:** `main` **Version:** `0.4.0`

## What ships

The verified issue 154 changes remove implicit work/repair ceilings, bind manual acceptance to recorded authority, pin selected runtime helpers, and add runtime inventory and evidence-validated recovery. The branch includes the existing 0.4.0 release preparation and talk baseline from PRs 141 and 145. Release preparation also aligns `.nightshift.toml` with the already-correct packaged defaults and replaces the deploy guide fixed CI-poll deadline with the native checks watcher.

## Gates

| Gate | Evidence | Status |
|---|---|---|
| Six engineering stages and both proof gates | `VALIDATION.md`, `VALIDATION.json` | Passed at engineering checkpoint |
| Installed real-provider run and repeat | `INSTALLED-ACCEPTANCE.md` | Passed for retained candidate |
| Canonical and packaged manifest defaults | `tests/test-default-manifests.sh` | Published-default RED reproduced; corrected defaults pass |
| Explicit operator limits | Same regression | Preserved |
| Setup and proof regressions | Setup 3; behavioral proof 28 | Passed |
| Manifest schema | `nightshift-manifest-validate.sh` | Passed |
| Remote CI | PR checks after branch push | Must pass before promotion |
| Production confirmation | `AGENTS.md` | Required immediately before production promotion |

## Deployment steps

1. Push the verified engineering branch and release-preparation branch without force.
2. Open the release-preparation PR against main and watch all CI to completion. Repair actionable failures without a default attempt or elapsed-time cutoff.
3. Present the exact PR, head revision and merge command for explicit production confirmation.
4. After confirmation, merge without deleting branches. Main push CI runs; the release workflow tags the exact successful revision `v0.4.0`.
5. Verify main CI, release-workflow success and the remote tag identity.

## Target and rollback

The target is the community repository stable release tag, not the placeholder application URL in the portable manifest. No database migration, new infrastructure, secret change or private installation replacement is required. A rollback is a reviewed revert or follow-up release; existing release tags are never moved and remote history is not rewritten. Executor and verifier are the current authorized operator/agent session; production promotion authority remains the operator under `AGENTS.md`.

## Verdict

Ready for branch push and PR validation. Production promotion remains blocked until remote CI passes and the exact promotion receives explicit confirmation.

Release follow-up: PR #156 is pushed. The first CI run exposed fixtures that still assumed implicit repair limits; those cases now either prove continued default repair or explicitly declare operator limits. The operation supervisor also contained a 64-transition cutoff, now removed and covered by a restart regression after 65 retained results. Updated CI must pass before production promotion.
