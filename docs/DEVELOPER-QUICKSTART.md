# Developer walkthrough: first ticket to pull request

Use this walkthrough to onboard a developer to the terminal launcher and local
console. It covers the standard engineering workflow: ticket or brief → spec →
verification → implementation → review → optional push and PR. A factory run does
not merge its PR or deploy the application.

Examples use placeholder ticket IDs, site names, and project paths. Substitute
your team's values. Run project commands from the repository you want to change,
not from the Nightshift source checkout.

## 1. Choose the tools your team permits

There are three separate choices:

| Choice | What it controls | Example |
|---|---|---|
| Installation runtime | Which adapters Nightshift installs | `install.sh --runtime all` |
| Factory provider | Which CLI coordinates a run | `nightshift claude gh:123` |
| Provider policy and role routing | Which providers perform the specialist and review calls | `--provider-policy claude-only` and `routing.json` |

**Selecting Claude as the factory provider does not, by itself, restrict every
role to Claude.** Use the Claude-only policy when that restriction matters.
Installing adapters does not install the provider CLIs, sign you in, or download
model weights.

| Team setup | Install adapters | Run policy |
|---|---|---|
| Claude only | `--runtime claude` | `--provider-policy claude-only` |
| Claude and Codex | `--runtime all` | `standard`, with role routes in `routing.json` |
| Local experimentation | `--runtime local` or `all` | Local factory requires Codex, Ollama, and an available model; review routes may still use cloud providers |

There is currently no `codex-only` or `local-only` provider policy. Azure AI
Foundry and a direct Docker model runner are not implemented provider adapters.
Keep local-model experiments separate from the team's first onboarding run.

## 2. Install Nightshift once per developer

Prerequisites:

- Git, Python 3.11 or newer, `jq`, and `curl`.
- The selected provider CLI, already installed and authenticated.
- `gh` for GitHub issue input. Authenticate repository publication separately for
  your Git host; using Jira for input does not choose the Git host for the PR.
- `bd` only if using a Beads ticket as input. Other sources can run without it.

From a directory where you keep tools:

```bash
git clone https://github.com/doctor-ew/nightshift-community.git
cd nightshift-community
bash install.sh --runtime claude --auth subscription --with-hook --update-channel branch:main
```

For mixed Claude/Codex use, replace `--runtime claude` with `--runtime all`.
The `branch:main` channel follows main; `stable` follows release tags. Keep the
checkout: the default installation uses symlinks into it.

Ensure `~/.local/bin` is on PATH, then check:

```bash
nightshift --help
nightshift version
bash install.sh --check --runtime claude
```

Use `--runtime all` for the check if that is what you installed. The install audit
checks owned assets; it does not prove provider login or repository access.

For Claude subscription access:

```bash
claude auth login
claude auth status --json
```

For a mixed-provider setup, also sign Codex into your permitted subscription:

```bash
env -u OPENAI_API_KEY codex login
env -u OPENAI_API_KEY codex login status
```

Subscription is the default. `--auth api` is an explicit per-run API-billing
choice, not a repair for a failed subscription login.

## 3. Initialize each consumer repository

Switch to the repository you want Nightshift to work on:

```bash
cd /path/to/project
nightshift init claude
```

Initialization creates or completes `.nightshift.toml` and `routing.json`,
validates them, and commits the initialization files. It does not start a model.
Git author identity must already be configured. Initialization commits only its
configuration files and explicitly included files. Unrelated staged and unstaged
changes are preserved. Existing edits to initialization files must be resolved
before initialization.

For a mixed-provider team, `nightshift init codex` saves Codex as the factory
default. You can still select Claude per run.

For a new Markdown task, create a file named `onboarding-task.md` with a small,
repository-specific requirement and acceptance criteria, then include it in the
initial baseline explicitly:

```bash
nightshift init claude --include onboarding-task.md
```

`nightshift setup --project .` is the interactive configuration wizard. `init` is
the shorter path that also establishes the Git baseline. The generated production
URL is a placeholder; it is not needed to run a ticket through a PR. Configure a
real target separately before deliberately using deployment stages.

### Make Claude-only the project default

Edit the existing `[providers]` table in `.nightshift.toml`; do not add a second
copy of the table:

```toml
[providers]
routing_file = "routing.json"
policy = "claude-only"
```

Commit this configuration change for the team. The command-line policy shown
below also applies to the entire managed run. A child cannot relax an inherited
Claude-only restriction by requesting `standard`.

### Configure a mixed-provider project

Leave the policy as `standard` (the default), and review the project's
`routing.json`. Its role `gears` select a provider and model; its `adversarial`
routes select independent reviewers. Confirm that developers can access the
configured models. `--model` selects the factory model, not every role's model.

Do not replace role prompts with provider-specific instructions to change models.
See [provider configuration](CONFIGURATION.md#claude-only-provider-policy) for
policy behavior and [routing.json](../routing.json) for the bundled routes.

## 4. Connect a ticket source

A source prefix selects the input adapter. `init` may report `ticket_source: spec`;
an explicit `jira:` or `gh:` reference still selects that adapter for the run.

| Input | Example | Required access |
|---|---|---|
| GitHub issue in this repository | `gh:123` | `gh auth login` and repository access |
| GitHub issue in another repository | `gh:owner/repository#123` | Access to that repository |
| Jira issue | `jira:APP-123` | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_TOKEN` |
| Monday item | `monday:1234567890` | `MONDAY_TOKEN` |
| Notion page | `notion:PAGE_ID` | `NOTION_TOKEN` and page access |
| Local Beads issue | `bd:BEAD_ID` | `bd` and the local ledger |
| Markdown brief | `onboarding-task.md` or `spec:onboarding-task.md` | The local file |

### Jira setup

Use the site root, for example `https://YOUR-SITE.atlassian.net`, not `/browse/`.
A trailing slash is accepted. The adapter uses direct REST access; an Atlassian
MCP connection in another application does not configure these variables.

Bash/zsh environment template:

```bash
export JIRA_BASE_URL='https://YOUR-SITE.atlassian.net'
export JIRA_EMAIL='you@example.com'
export JIRA_TOKEN="$JIRA_API_KEY"
```

The last line assumes your credential setup already exports the token under
`JIRA_API_KEY`. If it uses a different name, map that value to `JIRA_TOKEN`.
Nightshift does not read `JIRA_API_KEY` as an alias automatically.

Fish equivalent, using an existing token variable:

```fish
set -Ux JIRA_BASE_URL https://YOUR-SITE.atlassian.net
set -Ux JIRA_EMAIL you@example.com
set -Ux JIRA_TOKEN "$JIRA_API_KEY"
```

Fish universal exported variables persist for future shells. Use your team's
credential-management method; do not put credentials in the repository. Start the
console from a terminal with the same credentials so its Resume action can use
Jira too. Already-running processes do not acquire later environment changes.

### GitHub setup

```bash
gh auth login
gh auth status
```

For Monday or Notion, configure the environment variable in the table using your
team's credential setup. All sources share the same engineering pipeline.

## 5. Run a small first task

### Claude-only, keep the result local

```bash
nightshift jira:APP-123 --provider-policy claude-only
```

Or use your new Markdown brief:

```bash
nightshift onboarding-task.md --provider-policy claude-only
```

Nightshift creates or reuses an isolated ticket worktree, performs the workflow,
and retains its results locally. Without `--push`, it does not publish the branch.
Workflow bookkeeping and verification can still create local commits.

### Claude-only, deliver a branch and PR

```bash
nightshift jira:APP-123 --provider-policy claude-only --branch auto --push --pr
```

The flags mean:

1. `jira:APP-123`: fetch this Jira issue.
2. `--provider-policy claude-only`: use Claude for the factory and every managed role.
3. `--branch auto`: use an owned ticket branch/worktree; this is also the default.
4. `--push`: after required verification, commit and push the ticket work.
5. `--pr`: open a PR after pushing. This requires `--push`.

Neither flag authorizes merging or deployment. Branch-enabled factory runs are
autonomous and bypass provider CLI permission prompts; choose a repository and
scope in which you intend the agent to edit and execute commands.

### Mixed-provider run

```bash
nightshift codex gh:123 --branch auto --push --pr
```

Codex coordinates this run. Specialist and review calls follow `routing.json` and
the effective provider policy. `nightshift claude gh:123` changes the coordinator,
not the whole routing table. Standard adversarial review can require access to a
second provider; Claude-only uses a fresh, separate Claude review session.

### A dependency branch or a different project

```bash
nightshift jira:APP-123 --provider-policy claude-only --base origin/main --push --pr
nightshift gh:123 --project /path/to/project --provider-policy claude-only
```

New worktrees normally refresh the remote default branch referenced by
`origin/HEAD`. They do not inherit your current prototype branch automatically.
Use `--base` for a verified dependency branch. Existing owned worktrees retain
their recorded base; changing `--base` is not a reset or rebase operation.

## 6. Watch the work and its usage

The launcher prints the local console URL. Use that URL: an occupied port may
cause Nightshift to choose another one. To start a console explicitly in a
separate terminal:

```bash
nightshift dashboard --project /path/to/project --port 8765
```

The console shows:

- **Continue a ticket:** Resume and Clean up for recorded individual runs.
- **Ticket cost and tokens:** known totals across runs/retries and stage breakdowns.
- **Agents:** factory and role lifecycle records.
- **Run overview:** separate run and gate evidence.

Usage updates when a worker finishes. Provider estimates are not subscription
invoice charges. **Partial usage** means coverage is incomplete; **Unknown** is
not zero. Run/gate counters and agent counts measure different records.

For more terminal detail, add `--output verbose`. `--dashboard off` suppresses
console startup; `--dashboard-browser off` starts/reuses it without opening a tab.

## 7. Stop, recover, and resume

Interrupt a terminal run with Ctrl-C. Avoid starting another copy while its
worker is still alive. A suspended process is also still alive.

For a stopped ticket, use **Resume** in the console. It checks and reconciles
retained artifacts, then reuses the recorded provider and publication settings.
**Clean up** performs reconciliation without starting a model. If a worker or
source changes prevent recovery, the action reports the blocker.

Terminal equivalent for an example Jira ticket:

```bash
nightshift cleanup APP-123
nightshift jira:APP-123 --provider-policy claude-only --branch auto --push --pr
```

The next factory invocation also tries safe artifact cleanup automatically after
a worktree collision. Cleanup preserves files and creates a private recovery
snapshot; it does not delete the worktree, commit drafts, reset a branch, or stop
a live worker. Source changes, staged changes, and deleted files need review.

## Flag reference

| Option | When to use it |
|---|---|
| `--provider claude` / `codex` / `local` | Select the coordinating runtime. `ollama` aliases `local`. |
| `--provider-policy claude-only` | Restrict all managed provider calls to Claude. |
| `--model MODEL` | Choose the factory model available to your account/runtime. |
| `--auth subscription` | Subscription login; default. |
| `--auth api` | Explicit API authentication/billing for this invocation. |
| `--project DIR` | Run against another consumer repository. |
| `--branch auto` | Managed isolated ticket worktree; default. |
| `--branch none` | Work in the caller checkout; use for runs without branch publication. |
| `--base REF` | Select an explicit base for an individual ticket. |
| `--push` / `--pr` | Publish verified work / open its PR. |
| `--gear auto` or `0`–`4` | Role-router preference, subject to risk and provider policy. |
| `--risk low` / `standard` / `high` | Input to role selection. |
| `--output concise` / `verbose` / `quiet` | Terminal display; default is configured, then concise. |
| `--dashboard auto` / `off` | Automatic console startup. |
| `--dashboard-browser once` / `off` | Open a browser on console start or leave it closed. |

Use `auto` or `none` for `--branch`. Named branches are currently rejected by
preflight even though older help text lists them.

Advanced workflows:

```bash
nightshift batch "gh:123,gh:124" --provider-policy claude-only --push --pr
nightshift batch --resume BATCH_STATE_FILE --provider-policy claude-only --push --pr
```

`BATCH_STATE_FILE` is the existing batch state file reported by your run. `--resume`
is a batch option, not a single-ticket launcher flag. The `workshop` profile has
its own spec-approval flow; see the [workshop guide](WORKSHOP.md).

## Troubleshooting and updates

| Symptom | Next step |
|---|---|
| `MANIFEST_MISSING` | Run `nightshift init claude` in the consumer repository. |
| Jira variables missing | Check exact variable names and the environment of the process doing the work. |
| `WORKTREE_COLLISION` | Try Clean up; if blocked, inspect live workers or source changes. Preserve the worktree. |
| Dependency already merged but absent | Check the recorded base; use the integration or dependency branch for new work. |
| Reviewer/provider unavailable | Check role routes and login; use Claude-only when it matches team policy. |
| Resume settings changed | Refresh the console before clicking again. |
| Unexpected provider failure | Read the full log path printed by the launcher. Do not enable API billing as a login workaround. |

Check and apply updates from the configured channel:

```bash
nightshift sync --check
nightshift sync --apply
```

Updates can defer while a run is active. Keep the tool checkout and avoid editing
installed assets in a consumer repository.

For a team walkthrough, have each developer complete one small ticket, inspect
the tests and PR diff, locate its cost report, and practice stopping and resuming.
See [configuration](CONFIGURATION.md), [cost policy](NIGHTSHIFT-COST-POLICY.md),
[measurement details](RUN-MEASUREMENTS.md), and the [console guide](../dashboard/README.md).

## Review a local input spec in the console

For a local spec inside the consumer repository, add `--review-spec` to an
individual run with `--branch auto`. For example, after creating and committing
`onboarding-task.md` as described above:

```bash
nightshift spec:onboarding-task.md --provider-policy claude-only --review-spec
```

The launcher records the input spec for review and exits before starting a model.
Open the printed console URL, read the spec under **Awaiting spec approval**, and
select **Approve and continue**. The action starts the recorded run. Approval is
bound to both the file bytes and provider/publication settings; changed content
or settings require fresh approval. Retrying without the flag does not bypass a
pending review. This approval covers the input requirements, not later generated
spec changes, failed verification gates, or a production deployment.

Workshop spec review remains available through the workshop profile. Arbitrary
engineering-stage approval requests are not yet converted into UI approval cards.
