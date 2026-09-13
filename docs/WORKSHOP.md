# A bounded, spec-driven coaching-prompt workshop

Use this profile for the small standalone coaching prompt exercise. It teaches a
written spec, explicit approval, implementation, behavior tests, independent
review sessions, drift checks, and retained evidence. It does not issue the
standard pipeline's production proof certificate. BMad and Beads are optional.

## Student laptops

| Component | Mac | Windows |
| --- | --- | --- |
| Shell/toolchain | Terminal, Bash | WSL2 with Ubuntu 24.04; run all commands inside Ubuntu |
| Nightshift | Git, Python **3.11+**, jq, curl, Bash | Same dependencies inside WSL |
| Model access | Current native Claude Code (`--safe-mode`, `--bare`) + sponsored Anthropic API key | Linux Claude Code installed inside WSL + sponsored key |
| Editor | Any Markdown editor | Any Markdown editor; VS Code with WSL is convenient |
| Optional | BMad; Node/npm and uv for its documented installer | Same inside WSL |
| Not required | Codex, Beads, local GPU, Ollama, GitHub remote | Same |

Nightshift's workshop uses Unix process groups and `fcntl`; native PowerShell is
not supported by this runner. Claude Code itself supports native Windows and
macOS; its native install does not require Node. See the official
[Claude setup instructions](https://code.claude.com/docs/en/setup).
Windows/WSL is a documented setup path, **not a verified live classroom run** in
this release. Test a fresh Windows student laptop before class.

Mac (after installing Homebrew):

```bash
brew install git python jq
curl -fsSL https://claude.ai/install.sh | bash
```

Windows: enable WSL2 using Microsoft's [WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install),
then in an Ubuntu 24.04 terminal:

```bash
sudo apt update
sudo apt install git python3 jq curl
curl -fsSL https://claude.ai/install.sh | bash
```

Both platforms:

```bash
export PATH="$HOME/.local/bin:$PATH"
python3 -c 'import sys, tomllib; assert sys.version_info >= (3, 11)'
git --version
jq --version
claude --version
```

Set your own Git identity if not already configured. Keep Windows projects in
`~/projects` within WSL, and install the runtime there too.

## Install and initialize

This feature is on a review branch until promoted to the release channel:

```bash
mkdir -p ~/projects
cd ~/projects
git clone --branch nightshift/workshop-bounded https://github.com/doctor-ew/nightshift-community.git nightshift
cd nightshift
bash install.sh --runtime claude --symlink --auth api --update-channel branch:nightshift/workshop-bounded
mkdir -p ~/projects/coach-workshop
cd ~/projects/coach-workshop
```

Save the instructor's brief as `brief.md` in this directory, then:

```bash
nightshift init claude --profile workshop --include brief.md
```

Initialization runs no model. It saves the workshop route, chooses the file
ledger, and commits only configuration and explicitly included files. A remote
is unnecessary. If updating an existing initialized project, this command adds
the missing workshop route while preserving other configured roles.

## API credits and first run

Have each student enter their assigned key in their own terminal. In Bash/WSL:

```bash
read -rsp 'Anthropic API key: ' ANTHROPIC_API_KEY
printf '\n'
export ANTHROPIC_API_KEY
nightshift claude brief.md --auth api --output concise
```

In macOS Zsh, use `read -rs 'ANTHROPIC_API_KEY?Anthropic API key: '` instead of
Bash's `read -rsp`. Never put a key in a brief, Git, shared worksheet, or screenshot.
An API workshop requires the explicit flag and key, uses Claude's minimal API
mode, and does not fall back to a subscription or another provider. An existing
subscription can instead be used with `--auth subscription`.

The first run checks the actual detached runtime invocation and both configured
model roles, then writes and reviews `SPEC.md` in an isolated worktree. It stops
at **awaiting_spec_approval**. It also saves an identical `NIGHTSHIFT-SPEC-workshop-<id>.md`
in your current project directory. Existing edited copies are never overwritten.

Open the local dashboard's **Review your spec** section to read the complete spec
and click **Approve and build**. The saved workshop resumes automatically with its
original authentication mode, configured model and remaining budget. No terminal
rerun or hash is needed. Duplicate clicks reuse the running launch. If you already
approved under an older version, click **Continue approved build**.
Only the exact version displayed can be approved; changed copies are rejected.
The terminal SHA-256 approval below remains available as an alternative.

Read the spec against the brief. Discuss what would count as convincing evidence,
what is excluded, and where AI could mislead you. If acceptable, repeat the same
command, retaining `--auth api`, with the printed value:

```bash
nightshift claude brief.md --auth api --approve-spec <SHA256_FROM_OUTPUT> --output concise
```

The placeholder must be replaced, without angle brackets. Approval is an explicit
operator attestation tied to exact spec bytes; the CLI cannot verify who reviewed
it. If you reject the spec, revise the brief under a new filename and commit it,
preserving the prior exercise and evidence.

The runner creates eight public positive/negative cases before implementation,
reviews them, writes a 15–30 line prompt, executes every case in a fresh tool-free
session, then grades and reviews the observations. One repair may rerun all eight
cases. Failed observations remain on disk. Safe mode disables personal CLAUDE.md, skills, plugins and other customizations;
model workers receive the supplied stage inputs. Managed organizational policy
can still apply. The availability probes also check support for these CLI flags. Review uses separate sessions; a different configured Claude model is
possible, but this is not cross-provider review or hidden-heldout certification.

Inspect `prompts/workshop-agent.md` and `docs/workshop-*/` in the printed worktree.
Students should try new inputs themselves, label synthetic results as synthetic,
and distinguish a passing example from evidence about real reachable users.

## Budgets and progress

The default maximums apply across resume and repairs:

- 30 model calls, 900 active seconds, 90 seconds per model call.
- $2 reported-cost stop threshold; up to $0.25 requested per call.
- 1,000,000 input tokens including cache and 40,000 output tokens.
- 32 KiB of supplied context per call and 1 MiB of runtime output.

Configure these before a new exercise in `.nightshift.toml`:

```toml
[workshop]
seconds = 900
calls = 30
cost_usd = 2.0
call_usd = 0.25
input_tokens = 1000000
output_tokens = 40000
call_seconds = 90
input_bytes = 32768
response_bytes = 1048576
```

These are admission/stop limits, **not a guarantee of an exact API invoice cap**:
a response can cross the threshold before its receipt arrives. Missing receipts
retain the reserved cost. Use Anthropic account/project spending controls as the
billing backstop. A subscription's reported dollar estimate is not an API bill.
Time spent waiting for spec approval is excluded. Exhausted or failed exercises
cannot silently reset their budgets on resume; preserve them and use a new named
brief for an explicitly new exercise. Record every trial when assessing costs.

`--output concise` shows stages; `--output verbose` exposes events; `--output quiet`
shows the result. Private full logs remain available. The dashboard discovers the
workshop's worktree and worker lifecycle records. `RUN.json` holds individual
calls, models, usage (fresh/cache-write/cache-read/output), failures, and totals.
A worker finishing the spec phase does not mean the exercise is complete: check
its task status and spec-approval result.

## Delivery and teaching sequence

Local completion never asks for a remote. Only add `--push` if a configured
`origin` should receive the verified branch, and `--pr` with it to request a PR.
The workflow does not merge or deploy. Keep the final approved prompt and evidence
for the class discussion; a GitHub account is unnecessary for the exercise.

Suggested class allocation (a teaching plan, not a measured promise):
10 minutes brief/trust discussion, 10 minutes spec review, up to 15 minutes bounded
execution, 10 minutes evidence inspection and new tests, 5 minutes reflection.
Do setup before class; allow extra time for Windows onboarding.

BMad can help students explore requirements before this run; use its output as the
brief. It is independently installable, not embedded as a runtime dependency.
Follow the pinned version of the official
[BMad installer guide](https://docs.bmad-method.org/start/install-bmad/) for its
Node/npm and uv requirements. Avoid teaching two orchestration loops at once.

## Evidence integrity and older exercises

Workshop reviews now distinguish a supplied URL from a verified claim. A tool-free
coach can reason conditionally from a citation; it cannot establish truth simply
because a URL was supplied. Synthetic examples must remain labeled synthetic.
A metric also does not replace the procedure for an experiment.

Scenario and implementation reviewers write an `evidence_audit` and return an explicit `oracle_valid` decision.
The final reviewer sees the cases and raw responses alongside the grader's verdict.
Invalid expectations or grading stop the exercise before automatic prompt repair;
the failure and review remain available for inspection. This adds no model calls.
Review remains model judgment, not a deterministic guarantee of correctness.

The `source-integrity-v1` policy is pinned in each new run's identity. Older runs
cannot reuse cached results under this policy. Preserve their artifacts and use a
new brief filename (tracked in Git) for a fresh exercise and spec approval. This
update does not repair or retroactively certify previously completed prompts.
