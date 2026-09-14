#!/usr/bin/env bash
# WSL half of install.ps1. Retains checkouts and delegates runtime installation.
set -euo pipefail
source_repo=${1:?source checkout}; runtime=${2:?runtime}; auth=${3:?auth}; mode=${4:?dependency mode}
case "$runtime" in claude|codex|local|all) ;; *) exit 64 ;; esac
case "$auth" in subscription|api) ;; *) exit 64 ;; esac
case "$mode" in install|check) ;; *) exit 64 ;; esac
[ "$(id -u)" != 0 ] || { echo 'Run as your regular Ubuntu user, not root.' >&2; exit 1; }
export PATH="$HOME/.local/bin:$PATH"
if [ "$mode" = install ]; then
  sudo apt-get update
  sudo apt-get install -y git python3 jq curl ca-certificates
fi
for dep in git python3 jq curl; do command -v "$dep" >/dev/null || { echo "Missing Linux prerequisite: $dep" >&2; exit 1; }; done
python3 -c 'import sys, tomllib, fcntl; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
if [ "$runtime" = claude ] || [ "$runtime" = all ]; then
  if ! command -v claude >/dev/null; then
    [ "$mode" = install ] || { echo 'Install Claude Code inside Ubuntu, or rerun without -SkipDependencies.' >&2; exit 1; }
    installer=$(mktemp)
    # Retain downloaded installer for troubleshooting; only execute after successful download.
    curl -fsSL https://claude.ai/install.sh -o "$installer"
    bash "$installer"
  fi
  claude --version
fi
# A Linux checkout avoids CRLF and Windows symlink requirements. Never reset dirty work.
[ -z "$(git -C "$source_repo" status --porcelain --untracked-files=normal)" ] || {
  echo 'Commit or set aside checkout changes before installing; only committed source is installed.' >&2; exit 1;
}
revision=$(git -C "$source_repo" rev-parse HEAD)
target="$HOME/.nightshift/windows-source"
if [ ! -e "$target" ]; then
  mkdir -p "$(dirname "$target")"
  git -c core.autocrlf=false clone --no-local "$source_repo" "$target"
else
  [ -d "$target/.git" ] || { echo "Not a Nightshift checkout: $target" >&2; exit 1; }
  [ "$(git -C "$target" remote get-url origin)" = "$source_repo" ] || { echo 'Installer source differs from existing checkout; retained existing checkout.' >&2; exit 1; }
  [ -z "$(git -C "$target" status --porcelain)" ] || { echo "Retained dirty checkout: $target" >&2; exit 1; }
  git -C "$target" fetch origin
  git -C "$target" merge --ff-only "$revision"
fi
[ "$(git -C "$target" rev-parse HEAD)" = "$revision" ] || { echo 'Installed source is not the requested revision.' >&2; exit 1; }
bash "$target/install.sh" --runtime "$runtime" --auth "$auth" --symlink
bash "$HOME/.local/bin/nightshift" --help >/dev/null
printf '%s\n' 'Linux runtime installed. Codex/local provider CLIs, when selected, use their separate installation instructions.'
