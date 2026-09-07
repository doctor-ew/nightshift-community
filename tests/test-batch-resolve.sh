#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOLVER="${REPO_DIR}/scripts/nightshift-batch-resolve.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-batch-resolve.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_eq() { [ "$1" = "$2" ] || fail "expected '$2', got '$1'"; }

mkdir -p "$TMP_ROOT/bin" "$TMP_ROOT/project/docs/existing-task"
touch "$TMP_ROOT/project/docs/existing-task/SPEC.md"
cat > "$TMP_ROOT/bin/bd" <<'EOF'
#!/usr/bin/env bash
[ "$1" = show ] && [ "$2" = dp-g45.4 ] && [ "$3" = --json ] && exit 0
exit 1
EOF
chmod +x "$TMP_ROOT/bin/bd"

resolved=$(PATH="$TMP_ROOT/bin:$PATH" CLAUDE_PROJECT_DIR="$TMP_ROOT/project" "$RESOLVER" --input 'dp-g45.4 dp-g45.4')
assert_eq "$resolved" $'bd:dp-g45.4\nbd:dp-g45.4'

resolved=$(PATH="$TMP_ROOT/bin:$PATH" CLAUDE_PROJECT_DIR="$TMP_ROOT/project" "$RESOLVER" --input 'existing-task,bd:dp-g45.4')
assert_eq "$resolved" $'existing-task\nbd:dp-g45.4'

if PATH="$TMP_ROOT/bin:$PATH" CLAUDE_PROJECT_DIR="$TMP_ROOT/project" "$RESOLVER" --input 'project=MVP AND status=Open'; then
  fail 'a source query was incorrectly accepted as an explicit list'
fi

printf 'PASS: nightshift batch explicit-list resolution\n'
