# Isolated topic-profile activation proposal

This is a reviewable proposal, not authorization or an executed installation. It
pins synthetic-tested topic candidate `8300df7bc9e8cb7cbaa2ecd54dbcec626623b60e`. It does
not certify an integrated release or complete issue #2.

The exact command arguments, environment, audit expectations and rollback are in
[TOPIC-PROFILE-ACTIVATION-PROPOSAL.json](TOPIC-PROFILE-ACTIVATION-PROPOSAL.json).
The proposed root is `/private/tmp/nightshift-community-certification-8300df7`; it was absent
when prepared and must still be absent before authorized creation. A collision
requires review, never replacement or deletion.

| Purpose | Proposed destination |
| --- | --- |
| source | `/private/tmp/nightshift-community-certification-8300df7/nightshift-source` |
| runtime | `/private/tmp/nightshift-community-certification-8300df7/nightshift-runtime` |
| claude | `/private/tmp/nightshift-community-certification-8300df7/nightshift-claude` |
| codex | `/private/tmp/nightshift-community-certification-8300df7/nightshift-codex` |
| bin | `/private/tmp/nightshift-community-certification-8300df7/nightshift-bin` |
| evidence | `/private/tmp/nightshift-community-certification-8300df7/nightshift-evidence` |
| practice | `/private/tmp/nightshift-community-certification-8300df7/nightshift-practice` |

After separate authorization, clone the public Community source, select the exact
commit, and use the JSON's explicit `--runtime all`, `--symlink`, subscription-auth
and four installer-target arguments. Require the matching `install.sh --check`
audit to pass. Confirm the explicit launcher
`/private/tmp/nightshift-community-certification-8300df7/nightshift-bin/nightshift`
resolves to that clone's `scripts/nightshift-factory.sh`; use `version` only as a
build display alongside the exact Git revision and retained installation inventory.
All required checks must be reviewed at their actual status before proceeding.

Apply the proposed environment only to this profile's commands. Keep the existing
global launcher, shell configuration and installed provider runtimes unchanged.
No login, model request, ticket run, grant, merge, deployment or update application
is proposed. The configured update source/channel does not authorize changing the
pinned candidate. Live subscription availability remains unverified.

Retain command output and pre/post installation identity in the proposed private
evidence directory. Temporary storage is not a durability guarantee: preserve the
evidence to an approved durable location before operating-system cleanup. Rollback
means ceasing to invoke this launcher, stopping only proven owned processes if
separately started, and retaining all files and evidence. Do not uninstall or
redirect the existing runtime.

The [endpoint procedure](ENDPOINT-CERTIFICATION-PROPOSAL.md) and
[live proposal](CERTIFICATION-PROPOSAL.json) retain their separate scope. This file
makes a topic-profile destination inventory concrete; a future integrated-release
revision, actual practice assessment and live grant remain pending. No synthetic
grant or topic-candidate receipt may be reused as their authorization.
