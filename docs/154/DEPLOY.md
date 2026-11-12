# Deployment preparation — 154

**State:** prepared for branch publication and remote CI.
**Version:** `0.4.0`
**Release branch:** `nightshift/154-release`
**Engineering checkpoint branch:** `nightshift/154`
**Target:** community stable distribution through `.github/workflows/release.yml`.

Merging the version change into main is a production release action: successful main push CI causes the workflow to tag that exact revision `v0.4.0`. No production promotion has run. Branch publication and CI do not activate the existing private local installation.

Local preparation passes the canonical-default regression, setup tests (3), proof tests (28) and manifest validation. Prior six-stage and installed evidence remains historical and hash-bound; this preparation does not relabel it as a new live installed run.

See `PREFLIGHT.md` for scope, promotion, verification and rollback. Actual branch/PR publication and CI progress are retained by GitHub and the local task tracker.

Release follow-up: PR #156 is pushed. The first CI run exposed fixtures that still assumed implicit repair limits; those cases now either prove continued default repair or explicitly declare operator limits. The operation supervisor also contained a 64-transition cutoff, now removed and covered by a restart regression after 65 retained results. Updated CI must pass before production promotion.
