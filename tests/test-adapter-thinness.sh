#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
for stage in product adversarial implement review drift qa preflight deploy batch; do
  [ -f "$REPO_DIR/commands/nightshift-${stage}.md" ] || fail "missing shared ${stage} command"
done
grep -q 'canonical stage instructions' "$REPO_DIR/skills/nightshift/SKILL.md" || fail 'Codex adapter does not delegate to shared commands'
for adapter in "$REPO_DIR"/commands/*.md; do
  case "$(basename "$adapter")" in nightshift-*) ;; *) fail "unprefixed command: $adapter";; esac
done
printf 'PASS: runtime adapters delegate to shared Nightshift core\n'
