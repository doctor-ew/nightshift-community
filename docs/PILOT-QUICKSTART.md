# Engineer pilot and Hack-her-thon quickstart

Status: engineer pilot candidate, not yet a validated beginner release.
Use main for the shared baseline.
Local-model execution upgrades and ACP are experimental, not prerequisites.

Start with the [developer walkthrough](DEVELOPER-QUICKSTART.md) for installation,
initialization, credentials, flags, and recovery. This checklist adds pilot-specific
practice and review expectations.

## Before starting

Use a disposable practice repository and a small GitHub issue with clear expected
behavior and tests. Do not start with production credentials, personal data,
authentication changes or destructive operations. An experienced mentor should
review the first run and every proposed pull request.

Each participant needs their own permitted provider account and GitHub access.
Do not share credentials. Confirm provider eligibility and event account/billing
arrangements with organizers before onboarding participants.

Install Git, Python 3.11 or newer, jq and curl; GitHub issue workflows also require gh.
Beads is optional unless it is the ticket input source.
Install the chosen Codex or Claude Code CLI separately and sign in interactively.
Standard cross-provider review may require both providers to be available.
For Claude-only teams, use `--provider-policy claude-only`; review uses a fresh
Claude session.
Missing reviewer access is a blocker, not permission to self-approve.
Dependency checks are defined in [install.sh](../install.sh).

## Install from main

Clone https://github.com/doctor-ew/nightshift-community and keep the checkout: the default
installation uses symlinks into it. From that checkout, run
`bash install.sh --runtime all --auth subscription --with-hook`.
The installer changes user-level command/skill/hook configuration; review its
output and backups. Do not use the experimental model branches for the pilot.
Installer options: [install.sh](../install.sh).

Ensure the installed launcher directory, normally ~/.local/bin, is on PATH.
Open a new terminal if needed; `nightshift --help` should display launcher help.
If it does not, use the explicit ~/.local/bin/nightshift path until PATH is fixed.

## Configure your practice repository

Inside your own practice repository run `nightshift init claude`.
This creates and commits the configuration baseline without starting a model.
Use `nightshift setup --project .` for interactive configuration. Do not copy the
Nightshift repository's deployment placeholder URL as your application's URL.
Incomplete unattended configuration must stop; it should not guess.
Configuration behavior: [setup helper](../scripts/nightshift-setup.sh).

Confirm GitHub login with `gh auth status`. For the chosen coding CLI, complete
its interactive subscription sign-in before launching the factory.
Subscription mode does not guarantee unlimited usage or disable provider-account
extra usage. Review account limits separately. Never add --auth api to fix login.
See [cost policy](NIGHTSHIFT-COST-POLICY.md).

## First ticket

Use the actual GitHub issue number in your practice repository:
`nightshift gh:ISSUE_NUMBER --project /absolute/path/to/practice-repo --provider-policy claude-only --auth subscription --branch auto --push --pr`.
For mixed-provider routing, replace the policy flag with `--provider codex`. ISSUE_NUMBER and the project path are
placeholders, not literal values. Flags: [factory launcher](../scripts/nightshift-factory.sh).

The run may create branches/worktrees, edit files, run commands, commit, push and
open a PR. Factory mode bypasses CLI permission prompts for branch-enabled runs.
Prompt instructions are not a complete containment boundary. Run only on trusted
practice inputs without sensitive credentials. --push --pr does not authorize
merge or deployment.

## Watch, recover and finish

Run `nightshift dashboard --project /absolute/path/to/practice-repo` in a
separate terminal and open the URL it prints. Keep that process running.
Recorded observations are not unique current blockers or verified live workers.
Use Resume or Clean up for recorded individual tickets. See [dashboard guide](../dashboard/README.md).

If login expires, sign in again. If a run fails, read its receipt and tracker;
do not delete worktrees, ownership receipts or tests to force continuation.
Follow the recorded resume instruction. Ask a mentor about conflicting ownership.
Logs can include repository content: redact before sharing.

Before merging, require passing tests and independent review of source citations,
scope, test integrity and the final diff. For Nightshift itself PRs target
main; other repositories use their own agreed development base.
Do not run a production deployment during this pilot.

## Release gate still outstanding

A fresh target-directory installation on the maintainer's machine is not a fresh
laptop test. Have a second engineer follow this guide from main and complete a
new issue through a reviewed PR with no hidden local configuration. Record
commands, versions, auth mode (never secrets), failures and help required.
Only then label the path ready for beginner onboarding.
