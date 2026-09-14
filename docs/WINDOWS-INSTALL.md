# Windows installation

Git for Windows includes Bash: https://gitforwindows.org/ . Nightshift's full CLI
also uses Unix-only Python `fcntl` locking and process groups. Git Bash does not
supply these to native Windows Python: https://docs.python.org/3/library/fcntl.html .

The Windows installer provides a PowerShell command backed by Ubuntu in WSL.
It uses the same runtime and gates as macOS/Linux. It does not port the runtime
to native Windows or alter your existing Windows Claude installation.

## Install

Download or clone the Nightshift branch containing `install.ps1`, open PowerShell
in the checkout, and run `powershell -ExecutionPolicy Bypass -File .\install.ps1`.
Implementation and options: [`install.ps1`](../install.ps1).

The default installs the Claude adapter and retains Nightshift's subscription
authentication preference. For sponsored API credits, use
`powershell -ExecutionPolicy Bypass -File .\install.ps1 -Auth api`.
The installer never asks for or stores an API key and never starts a model request.
Set your provided key for the terminal session before using `--auth api`.

The installer:

1. Installs Ubuntu-24.04 through WSL if absent. Windows may request elevation or
   a reboot. Finish Ubuntu's first-user setup with a regular user and rerun.
2. Installs Git, Python 3.11+, jq, curl and certificates inside Ubuntu using apt.
3. Installs Linux Claude Code through Anthropic's native installer if absent.
4. Creates a Linux source checkout from your committed Windows checkout, then
   delegates to the existing Nightshift installer. Keep the Windows source checkout
   available for future updates. Uncommitted sources and dirty installed checkouts
   are retained and rejected, never reset.
5. Checks `nightshift --help` before installing a Windows launcher and adding its
   folder to your user PATH. Open a new terminal afterward.

Sources: [`nightshift-windows-bootstrap.sh`](../scripts/nightshift-windows-bootstrap.sh),
[Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install),
[Claude Code installation](https://code.claude.com/docs/en/setup).

## Use

From your project folder in PowerShell, run
`nightshift init claude --profile workshop --include test-coach-brief.md`, then
`nightshift claude test-coach-brief.md --auth api` for sponsored API access.
These are the existing workshop commands; the Windows launcher forwards them to
WSL while retaining the current project directory. Use relative file paths with
forward slashes (for example `docs/brief.md`), not Windows drive paths in arguments.
Implementation: [`nightshift-windows.ps1`](../scripts/nightshift-windows.ps1).

For the best filesystem performance, keep larger projects in Ubuntu's filesystem
and open them using VS Code's WSL integration. Windows folders also remain accessible
through WSL. See [Microsoft filesystem guidance](https://learn.microsoft.com/en-us/windows/wsl/filesystems).

API keys explicitly present as `ANTHROPIC_API_KEY` in the Windows process are passed
to WSL for that command, not written to configuration. Windows subscription login
state is not copied; subscription users sign in to Claude inside Ubuntu.

## Options and recovery

- `-Plan`: print the intended installation without changing the system.
- `-SkipDependencies`: verify/use existing dependencies; do not install OS packages.
- `-Distribution Ubuntu-24.04`: select an Ubuntu distribution by its registered name.
  The bootstrap uses apt and requires Python 3.11+.
- `-Runtime claude|codex|local|all`: choose installed Nightshift adapters. Provider
  CLI installation is automatic for Claude only; other provider CLIs must already
  be installed in Ubuntu before running those adapters.
- `-Auth subscription|api`: set the saved authentication preference; API runs still
  require explicit `--auth api` as documented by the core launcher.

If Windows requests a restart, restart and rerun. If Ubuntu opens its account setup,
finish it, exit the Ubuntu shell, and rerun. If a dependency or CLI check fails,
fix the reported step and rerun. Existing distribution defaults are not changed.
Existing launcher files receive backups; unrelated `nightshift.cmd` files are not overwritten.
No uninstall or data-removal action is performed by this installer.

## Verification boundary

Offline tests exercise argument preservation (spaces, quotes, shell metacharacters,
empty arguments), exit-code propagation, PowerShell parsing and plan output,
bootstrap reruns, preference forwarding, invalid selections, and dirty-source refusal.
The Windows CI workflow runs PowerShell contracts under both PowerShell 7 and 5.1.
These checks do not constitute an actual WSL installation or a student API run.
A fresh Windows/WSL installation and model run remain the release acceptance check.

Tests: [`test-windows-installer.py`](../tests/test-windows-installer.py).
