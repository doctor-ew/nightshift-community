# Release and development updates

The terminal launcher defaults to community stable releases from
https://github.com/doctor-ew/nightshift-community.git. It selects the highest
semantic `vMAJOR.MINOR.PATCH` tag and checks that its VERSION agrees.
The release workflow creates an immutable tag only after successful main push CI.
Maintainers bump VERSION through review to publish another release; the existing
version command derives a separate timestamped build identifier from the commit.

Install options are `--update-source <repository-url>` and
`--update-channel stable|branch:<name>`. The default is community + stable.
For dogfooding, choose `branch:integration/nightshift`; private source URLs are
explicit opt-ins. No automatic private-to-community mirroring occurs.
Do not embed access tokens in repository URLs; use Git's credential helper.

`nightshift sync --check` checks without changing source files.
`nightshift sync --apply` attempts a safe fast-forward.
`nightshift sync --configure --source <url> --channel <channel>` persists settings
in NIGHTSHIFT_HOME/updates.json. Environment overrides are NIGHTSHIFT_UPDATE_SOURCE
and NIGHTSHIFT_UPDATE_CHANNEL. Set NIGHTSHIFT_SYNC_CHECK=off to disable launch checks.
Legacy detached-worktree preparation remains available through
scripts/nightshift-sync.sh, but does not install or activate an update.

On ticket/batch launch, an update may be applied before the runtime starts. All
cooperating terminal runs retain a shared OS lock; an updater needs the exclusive
lock. Active runs defer updates. The lock is released automatically on exit.
Offline checks fail open to the installed version, not to another source.
No reset, force push, branch switch or automatic repair of local changes occurs.
Stable installs must be clean and on main; branch-channel installs must be clean
and on their configured branch. Divergent histories and copy installs require
manual reconciliation/reinstallation. Configuration changes never transplant
private history into the community repository.

This lock covers terminal factory launches, not independently launched IDE slash
commands or external Git operations. Do not manually update a checkout while an
IDE workflow is using it. Help, setup, version and dashboard commands do not
automatically update the runtime.
