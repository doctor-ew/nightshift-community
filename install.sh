#!/usr/bin/env bash
# install.sh — install nightshift for Claude Code and/or Codex
#
# Modes:
#   install.sh                  install shared Nightshift runtime + selected adapters (default)
#   install.sh --copy           plain copy instead of symlinks
#   install.sh --check          dry-run; report deps + conflicts + hook status
#   install.sh --with-hook      additionally wire scope-freeze + spec-guardrail (PreToolUse) and nightshift-stop-hook (Stop) into ~/.claude/settings.json
#   install.sh --uninstall      remove everything this installer placed
#   install.sh --runtime NAME   codex, claude, local, or all (default: all)
#   install.sh --target DIR     override ~/.claude (Claude compatibility target)
#   install.sh --nightshift-target DIR override ~/.nightshift (shared runtime target)
#   install.sh --codex-target DIR override ~/.codex (e.g. for testing)
#   install.sh --bin-target DIR install the agent-agnostic nightshift launcher there
#   install.sh --unattended-shell disable Codex and Claude Code permission dialogs
#   install.sh --auth subscription|api set auth preference (API still requires per-run --auth api)
#   install.sh --update-source URL explicit repository (default: community)
#   install.sh --update-channel stable|branch:NAME (default: stable)
#
# Idempotent. Backs up overwritten files to <nightshift-target>/.backup/<timestamp>/.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${HOME}/.claude"
CODEX_TARGET="${CODEX_HOME:-${HOME}/.codex}"
NIGHTSHIFT_TARGET="${NIGHTSHIFT_HOME:-${HOME}/.nightshift}"
BIN_TARGET="${NIGHTSHIFT_BIN_DIR:-${HOME}/.local/bin}"
MODE="symlink"     # symlink | copy
ACTION="install"   # install | check | uninstall
WITH_HOOK="no"
RUNTIME="all"       # codex | claude | local | all
UNATTENDED_SHELL="no"
AUTH_MODE=""
SETUP_PROJECT=""
UPDATE_SOURCE=""
UPDATE_CHANNEL=""

while [ $# -gt 0 ]; do
  case "$1" in
    --copy)       MODE="copy" ;;
    --symlink)    MODE="symlink" ;;
    --check)      ACTION="check" ;;
    --uninstall)  ACTION="uninstall" ;;
    --with-hook)  WITH_HOOK="yes" ;;
    --runtime)    shift; RUNTIME="$1" ;;
    --target)     shift; TARGET="$1" ;;
    --codex-target) shift; CODEX_TARGET="$1" ;;
    --nightshift-target) shift; NIGHTSHIFT_TARGET="$1" ;;
    --bin-target) shift; BIN_TARGET="$1" ;;
    --unattended-shell) UNATTENDED_SHELL="yes" ;;
    --auth) shift; AUTH_MODE="$1" ;;
    --setup-project) shift; SETUP_PROJECT="$1" ;;
    --update-source) shift; UPDATE_SOURCE="$1" ;;
    --update-channel) shift; UPDATE_CHANNEL="$1" ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      exit 64
      ;;
  esac
  shift
done

case "$RUNTIME" in
  codex|claude|local|all) ;;
  *) echo "Unknown runtime: $RUNTIME (expected codex, claude, local, or all)" >&2; exit 64 ;;
esac
case "$AUTH_MODE" in
  ""|subscription|api) ;;
  *) echo "Unknown auth mode: $AUTH_MODE (expected subscription or api)" >&2; exit 64 ;;
esac

CMD_SRC="${REPO_DIR}/commands"
SCRIPT_SRC="${REPO_DIR}/scripts"
AGENT_SRC="${REPO_DIR}/agents"
ROUTING_SRC="${REPO_DIR}/routing.json"
MANIFEST_SRC="${REPO_DIR}/nightshift.toml"
CMD_DST="${TARGET}/commands"
SCRIPT_DST="${NIGHTSHIFT_TARGET}/scripts"
AGENT_DST="${NIGHTSHIFT_TARGET}/agents"
ROUTING_DST="${NIGHTSHIFT_TARGET}/routing.json"
FACTORY_CONFIG="${NIGHTSHIFT_TARGET}/config"
CLAUDE_SCRIPT_DST="${TARGET}/scripts"
CLAUDE_AGENT_DST="${TARGET}/agents"
CLAUDE_ROUTING_DST="${TARGET}/nightshift-routing.json"
CODEX_SKILL_SRC="${REPO_DIR}/skills/nightshift"
CODEX_SKILL_DST="${CODEX_TARGET}/skills/nightshift"
FACTORY_SRC="${REPO_DIR}/scripts/nightshift-factory.sh"
FACTORY_DST="${BIN_TARGET}/nightshift"
SETTINGS="${TARGET}/settings.json"
CODEX_HOOKS="${CODEX_TARGET}/hooks.json"
BACKUP="${NIGHTSHIFT_TARGET}/.backup/$(date +%Y%m%d-%H%M%S)"

# ───────────────────────── helpers ─────────────────────────

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
err()  { printf '  \033[31m✗\033[0m %s\n' "$1"; }

# Returns 0 if dep present, 1 if missing
check_dep() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "$1: $(command -v "$1")"
    return 0
  else
    warn "$1: not found ($2)"
    return 1
  fi
}

backup_if_exists() {
  local path="$1"
  if [ -e "$path" ] || [ -L "$path" ]; then
    mkdir -p "$BACKUP"
    cp -RP "$path" "$BACKUP/" 2>/dev/null || true
  fi
}

install_one() {
  local src="$1" dst="$2"
  backup_if_exists "$dst"
  rm -f "$dst"
  if [ "$MODE" = "symlink" ]; then
    ln -s "$src" "$dst"
  else
    cp "$src" "$dst"
  fi
  ok "$(basename "$dst")"
}

install_tree() {
  local src="$1" dst="$2"
  backup_if_exists "$dst"
  rm -rf "$dst"
  mkdir -p "$(dirname "$dst")"
  if [ "$MODE" = "symlink" ]; then
    ln -s "$src" "$dst"
  else
    cp -R "$src" "$dst"
  fi
  ok "$(basename "$dst")"
}

want_claude() { [ "$RUNTIME" = "claude" ] || [ "$RUNTIME" = "all" ]; }
want_codex() { [ "$RUNTIME" = "codex" ] || [ "$RUNTIME" = "local" ] || [ "$RUNTIME" = "all" ]; }

# Retire only symlinks demonstrably owned by this checkout's compatibility tree
# or launcher. Move them, retaining the exact link and never traversing targets.
retire_owned_aliases() {
  local directory link target category
  for category in commands skills bin; do
    case "$category" in
      commands) directory="$CMD_DST" ;;
      skills) directory="$CODEX_TARGET/skills" ;;
      bin) directory="$BIN_TARGET" ;;
    esac
    [ -d "$directory" ] || continue
    for link in "$directory"/*; do
      [ -L "$link" ] || continue
      target=$(readlink "$link")
      case "$target" in
        "$REPO_DIR"/compat/*) ;;
        "$FACTORY_SRC") [ "$link" != "$FACTORY_DST" ] || continue ;;
        *) continue ;;
      esac
      mkdir -p "$BACKUP/retired/$category"
      [ ! -e "$BACKUP/retired/$category/$(basename "$link")" ] && [ ! -L "$BACKUP/retired/$category/$(basename "$link")" ] || return 1
      mv "$link" "$BACKUP/retired/$category/"
      ok "archived retired $category alias"
    done
  done
}

migrate_legacy_hooks() {
  local path="$1"
  [ -f "$path" ] || return 0
  # Match the literal tilde stored in hook command text, not an expanded path.
  # shellcheck disable=SC2088
  grep -q '~/.claude/scripts/nightshift-' "$path" 2>/dev/null || return 0
  backup_if_exists "$path"
  python3 - "$path" <<'PYEOF'
import json, sys
path = sys.argv[1]
with open(path) as f:
    settings = json.load(f)
changed = False
for groups in settings.get("hooks", {}).values():
    for group in groups:
        for hook in group.get("hooks", []):
            command = hook.get("command")
            if isinstance(command, str):
                migrated = command.replace("~/.claude/scripts/nightshift-", "~/.nightshift/scripts/nightshift-")
                if migrated != command:
                    hook["command"] = migrated
                    changed = True
if changed:
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
PYEOF
  ok "migrated shared-runtime hook paths in $(basename "$path")"
}

# ───────────────────────── check ─────────────────────────

bold "nightshift installer"
echo "Repo:    $REPO_DIR"
echo "Target:  $TARGET"
echo "Codex:   $CODEX_TARGET"
echo "Bin:     $BIN_TARGET"
echo "Runtime: $RUNTIME"
echo "Mode:    $MODE"
echo "Action:  $ACTION"
echo "Hook:    $WITH_HOOK"
echo "Unattended shell: $UNATTENDED_SHELL"
echo "Auth mode: ${AUTH_MODE:-subscription (default)}"
echo

bold "Dependencies"
MISSING=0
check_dep jq      "brew install jq" || MISSING=$((MISSING+1))
check_dep python3 "ships with macOS / brew install python" || MISSING=$((MISSING+1))
check_dep bd      "https://github.com/gastownhall/beads — required for beads mirroring" || MISSING=$((MISSING+1))
check_dep gh      "brew install gh — required for gh: ticket source" || true
check_dep curl    "ships with macOS" || MISSING=$((MISSING+1))
check_dep git     "brew install git" || MISSING=$((MISSING+1))
check_dep bc      "ships with macOS — optional; nightshift-batch-retro falls back to '?' without it" || true
echo

if [ "$MISSING" -gt 0 ]; then
  warn "$MISSING required deps missing. Install before running nightshift-* commands."
fi

# ─────────────────── namespace guard (dp-0aw) ───────────────────
# Everything nightshift installs into the shared ~/.claude namespace MUST carry a nightshift- prefix.
# ~/.claude/{commands,scripts,agents} are flat, single-slot namespaces shared with every other
# plugin. An unprefixed name silently clobbers — and, when the installed path is a symlink back
# into this repo, the *other* plugin's sync writes its content INTO this repo. That has happened:
# scripts/scope-freeze.sh was once byte-identical to the CX plugin's copy.
NS_VIOLATION=0
for f in "$CMD_SRC"/*.md "$SCRIPT_SRC"/*.sh "$AGENT_SRC"/*.md; do
  [ -e "$f" ] || continue
  base=$(basename "$f")
  case "$base" in
    nightshift-*) ;;
    *) echo "NAMESPACE VIOLATION: $f must be named nightshift-$base" >&2; NS_VIOLATION=$((NS_VIOLATION+1)) ;;
  esac
done
if [ "$NS_VIOLATION" -gt 0 ]; then
  echo "Refusing to install: $NS_VIOLATION unprefixed file(s). Rename them and re-run." >&2
  exit 65
fi

bold "Existing conflicts"
if want_claude; then
mkdir -p "$CMD_DST" "$SCRIPT_DST" "$AGENT_DST"
CONFLICTS=0
for f in "$CMD_SRC"/*.md; do
  base=$(basename "$f")
  if [ -e "$CMD_DST/$base" ] && [ ! -L "$CMD_DST/$base" ]; then
    warn "commands/$base exists (not a symlink — will be backed up)"
    CONFLICTS=$((CONFLICTS+1))
  fi
done
for f in "$SCRIPT_SRC"/*.sh; do
  base=$(basename "$f")
  if [ -e "$SCRIPT_DST/$base" ] && [ ! -L "$SCRIPT_DST/$base" ]; then
    warn "scripts/$base exists (not a symlink — will be backed up)"
    CONFLICTS=$((CONFLICTS+1))
  fi
done
for f in "$AGENT_SRC"/*.md; do
  base=$(basename "$f")
  if [ -e "$AGENT_DST/$base" ] && [ ! -L "$AGENT_DST/$base" ]; then
    warn "agents/$base exists (not a symlink — will be backed up); another plugin may own this role"
    CONFLICTS=$((CONFLICTS+1))
  fi
done
[ "$CONFLICTS" = "0" ] && ok "no conflicts"
fi

if want_codex && { [ -e "$CODEX_SKILL_DST" ] || [ -L "$CODEX_SKILL_DST" ]; }; then
  warn "Codex skill nightshift exists (will be backed up)"
fi
if { [ -e "$FACTORY_DST" ] || [ -L "$FACTORY_DST" ]; }; then
  warn "nightshift launcher exists in $BIN_TARGET (will be backed up)"
fi
echo

bold "Hook status"
if [ -f "$SETTINGS" ] && grep -q "nightshift-scope-freeze.sh" "$SETTINGS" 2>/dev/null; then
  ok "scope-freeze hook is wired in $SETTINGS"
else
  warn "scope-freeze hook not wired (run with --with-hook to add it)"
fi
if [ -f "$SETTINGS" ] && grep -q "nightshift-spec-guardrail.sh" "$SETTINGS" 2>/dev/null; then
  ok "spec-guardrail hook is wired in $SETTINGS"
else
  warn "spec-guardrail hook not wired (run with --with-hook to add it)"
fi
if [ -f "$SETTINGS" ] && grep -q "nightshift-stop-hook.sh" "$SETTINGS" 2>/dev/null; then
  ok "nightshift-stop-hook (Stop) is wired in $SETTINGS"
else
  warn "nightshift-stop-hook not wired (run with --with-hook to add it)"
fi
echo

if [ "$ACTION" = "check" ]; then
  bold "Dry-run complete. No changes made."
  exit 0
fi

# ───────────────────────── uninstall ─────────────────────────

if [ "$ACTION" = "uninstall" ]; then
  bold "Uninstalling"
  if want_claude; then
  for f in "$CMD_SRC"/*.md; do
    base=$(basename "$f")
    if [ -e "$CMD_DST/$base" ] || [ -L "$CMD_DST/$base" ]; then
      rm -f "$CMD_DST/$base"
      ok "removed commands/$base"
    fi
  done
  for f in "$SCRIPT_SRC"/*.sh; do
    base=$(basename "$f")
    if [ -e "$SCRIPT_DST/$base" ] || [ -L "$SCRIPT_DST/$base" ]; then
      rm -f "$SCRIPT_DST/$base"
      ok "removed scripts/$base"
    fi
  done
  for f in "$AGENT_SRC"/*.md; do
    base=$(basename "$f")
    if [ -e "$AGENT_DST/$base" ] || [ -L "$AGENT_DST/$base" ]; then
      rm -f "$AGENT_DST/$base"
      ok "removed agents/$base"
    fi
  done
  if [ -e "$ROUTING_DST" ] || [ -L "$ROUTING_DST" ]; then
    rm -f "$ROUTING_DST"
    ok "removed $(basename "$ROUTING_DST")"
  fi
  if [ -f "$SETTINGS" ] && grep -q "nightshift-scope-freeze.sh" "$SETTINGS"; then
    warn "scope-freeze hook still wired in $SETTINGS — edit manually if you want it gone"
  fi
  fi
  if want_codex && { [ -e "$CODEX_SKILL_DST" ] || [ -L "$CODEX_SKILL_DST" ]; }; then
    rm -rf "$CODEX_SKILL_DST"
    ok "removed Codex skill nightshift"
  fi
  if [ -e "$FACTORY_DST" ] || [ -L "$FACTORY_DST" ]; then
    rm -f "$FACTORY_DST"
    ok "removed nightshift launcher"
  fi
  echo
  bold "Uninstall complete."
  exit 0
fi

# ───────────────────────── install ─────────────────────────

if [ "$UNATTENDED_SHELL" = "yes" ]; then
  bold "Configuring unattended shell execution"
  mkdir -p "$CODEX_TARGET"
  backup_if_exists "${CODEX_TARGET}/config.toml"
  python3 - "${CODEX_TARGET}/config.toml" <<'PYEOF'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text() if path.exists() else ""
line = 'approval_policy = "never"'
if re.search(r'^approval_policy\s*=.*$', text, flags=re.M):
    text = re.sub(r'^approval_policy\s*=.*$', line, text, flags=re.M)
else:
    text = line + "\n" + text
path.write_text(text)
PYEOF

  mkdir -p "$TARGET"
  [ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
  backup_if_exists "$SETTINGS"
  python3 - "$SETTINGS" <<'PYEOF'
import json, sys
path = sys.argv[1]
with open(path) as f:
    raw = f.read()
settings = json.loads(raw) if raw.strip() else {}
settings.setdefault("permissions", {})["defaultMode"] = "bypassPermissions"
with open(path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
PYEOF
  ok "Codex approval_policy=never; Claude Code defaultMode=bypassPermissions"
  echo
fi

retire_owned_aliases

if want_claude; then
bold "Installing Claude commands"
for f in "$CMD_SRC"/*.md; do
  install_one "$f" "$CMD_DST/$(basename "$f")"
done
echo
fi

bold "Installing shared Nightshift runtime"
mkdir -p "$SCRIPT_DST" "$AGENT_DST" "${NIGHTSHIFT_TARGET}/contracts"
install_one "$SCRIPT_SRC/nightshift-contract.jq" "$SCRIPT_DST/nightshift-contract.jq"
for helper in "$SCRIPT_SRC"/nightshift-*.py; do
  [ -f "$helper" ] || continue
  install_one "$helper" "$SCRIPT_DST/$(basename "$helper")"
done
for f in "$REPO_DIR"/contracts/nightshift-*.schema.json; do
  install_one "$f" "${NIGHTSHIFT_TARGET}/contracts/$(basename "$f")"
done
for f in "$SCRIPT_SRC"/*.sh; do
  install_one "$f" "$SCRIPT_DST/$(basename "$f")"
  chmod +x "$SCRIPT_DST/$(basename "$f")" 2>/dev/null || true
done
echo

bold "Installing shared agent role prompts"
for f in "$AGENT_SRC"/*.md; do
  install_one "$f" "$AGENT_DST/$(basename "$f")"
done
install_one "$ROUTING_SRC" "$ROUTING_DST"
install_one "$MANIFEST_SRC" "${NIGHTSHIFT_TARGET}/nightshift.toml"
if [ -d "$REPO_DIR/dashboard/dist" ]; then
  install_tree "$REPO_DIR/dashboard/dist" "${NIGHTSHIFT_TARGET}/dashboard/dist"
  install_one "$REPO_DIR/dashboard/server.py" "${NIGHTSHIFT_TARGET}/dashboard/server.py"
fi
echo

if want_claude; then
  bold "Installing legacy Claude script adapters"
  mkdir -p "$CLAUDE_SCRIPT_DST" "$CLAUDE_AGENT_DST"
  for f in "$SCRIPT_SRC"/*.sh; do
    install_one "$f" "$CLAUDE_SCRIPT_DST/$(basename "$f")"
    chmod +x "$CLAUDE_SCRIPT_DST/$(basename "$f")" 2>/dev/null || true
  done
  for f in "$AGENT_SRC"/*.md; do
    install_one "$f" "$CLAUDE_AGENT_DST/$(basename "$f")"
  done
  install_one "$ROUTING_SRC" "$CLAUDE_ROUTING_DST"
  install_one "$SCRIPT_SRC/nightshift-contract.jq" "$CLAUDE_SCRIPT_DST/nightshift-contract.jq"
  mkdir -p "${TARGET}/contracts"
  for f in "$REPO_DIR"/contracts/nightshift-*.schema.json; do
    install_one "$f" "${TARGET}/contracts/$(basename "$f")"
  done
  migrate_legacy_hooks "$SETTINGS"
  echo

if [ "$WITH_HOOK" = "yes" ]; then
  bold "Wiring hooks (scope-freeze + spec-guardrail + nightshift-stop-hook)"
  if [ ! -f "$SETTINGS" ]; then
    echo '{}' > "$SETTINGS"
  fi
  backup_if_exists "$SETTINGS"
  python3 - "$SETTINGS" << 'PYEOF'
import json, sys, os
path = sys.argv[1]
with open(path) as f:
    raw = f.read()
s = json.loads(raw) if raw.strip() else {}
hooks = s.setdefault("hooks", {})
pre = hooks.setdefault("PreToolUse", [])
stop = hooks.setdefault("Stop", [])

def pre_wired(script_name):
    return any(
        isinstance(b, dict) and b.get("matcher") == "Edit|Write"
        and any(script_name in (h.get("command") or "") for h in (b.get("hooks") or []))
        for b in pre
    )

def stop_wired(script_name):
    return any(
        isinstance(b, dict)
        and any(script_name in (h.get("command") or "") for h in (b.get("hooks") or []))
        for b in stop
    )

added = []
if not pre_wired("nightshift-scope-freeze.sh"):
    pre.append({
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": "bash ~/.nightshift/scripts/nightshift-scope-freeze.sh"}]
    })
    added.append("scope-freeze")

if not pre_wired("nightshift-spec-guardrail.sh"):
    pre.append({
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": "bash ~/.nightshift/scripts/nightshift-spec-guardrail.sh"}]
    })
    added.append("spec-guardrail")

if not stop_wired("nightshift-stop-hook.sh"):
    stop.append({
        "hooks": [{"type": "command", "command": "bash ~/.nightshift/scripts/nightshift-stop-hook.sh"}]
    })
    added.append("nightshift-stop-hook")

with open(path, "w") as f:
    json.dump(s, f, indent=2)

if added:
    print(f"  added: {', '.join(added)}")
else:
    print("  both hooks already wired (no change)")
PYEOF
  echo
fi
fi

if want_codex; then
  bold "Installing Codex skill"
  install_tree "$CODEX_SKILL_SRC" "$CODEX_SKILL_DST"
  migrate_legacy_hooks "$CODEX_HOOKS"
  echo
fi

bold "Installing agent-agnostic launcher"
UPDATE_ARGS=()
[ -z "$UPDATE_SOURCE" ] || UPDATE_ARGS+=(--source "$UPDATE_SOURCE")
[ -z "$UPDATE_CHANNEL" ] || UPDATE_ARGS+=(--channel "$UPDATE_CHANNEL")
NIGHTSHIFT_HOME="$NIGHTSHIFT_TARGET" python3 "$SCRIPT_SRC/nightshift-update.py" \
  --project "$REPO_DIR" --configure "${UPDATE_ARGS[@]}" --install-args \
  --runtime "$RUNTIME" --target "$TARGET" --codex-target "$CODEX_TARGET" \
  --nightshift-target "$NIGHTSHIFT_TARGET" --bin-target "$BIN_TARGET" "--$MODE"
mkdir -p "$BIN_TARGET"
install_one "$FACTORY_SRC" "$FACTORY_DST"
chmod +x "$FACTORY_DST" 2>/dev/null || true
if [ -n "$AUTH_MODE" ] || [ ! -e "$FACTORY_CONFIG" ]; then
  backup_if_exists "$FACTORY_CONFIG"
  printf 'NIGHTSHIFT_AUTH=%s\n' "${AUTH_MODE:-subscription}" > "$FACTORY_CONFIG"
  ok "configured launcher authentication preference: ${AUTH_MODE:-subscription} (API requires per-run --auth api)"
fi
echo

bold "Done."
echo "Backups (if any): $BACKUP"
echo
echo "Next steps:"
echo "  - Test the adapter:  ~/.nightshift/scripts/nightshift-ticket-source.sh gh:1   (any real ticket)"
if want_codex; then
  echo "  - Codex: start in a consumer repo, then use: \$nightshift <ref>"
  echo "  - One terminal call: nightshift <ref>"
fi
if [ "$RUNTIME" = "local" ] || [ "$RUNTIME" = "all" ]; then
  echo "  - Local: codex --oss --local-provider ollama -m <coding-model> -C <consumer-repo>"
fi
if want_claude; then
  echo "  - Claude Code: /nightshift-eng <ref>"
fi
echo "  - See README.md for ticket-source env vars (jira/monday/notion)"
if [ -n "$SETUP_PROJECT" ]; then
  bash "$SCRIPT_SRC/nightshift-setup.sh" --project "$SETUP_PROJECT"
fi
