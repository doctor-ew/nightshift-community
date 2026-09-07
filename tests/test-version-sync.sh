#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; VERSION="$ROOT/scripts/nightshift-version.sh"; SYNC="$ROOT/scripts/nightshift-sync.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-sync.XXXXXX")"; trap 'rm -rf "$TMP_ROOT"' EXIT
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
git init -q --bare "$TMP_ROOT/remote.git"; git init -q -b main "$TMP_ROOT/source"
git -C "$TMP_ROOT/source" config user.email test@example.invalid; git -C "$TMP_ROOT/source" config user.name test
printf '0.1.0\n' > "$TMP_ROOT/source/VERSION"; git -C "$TMP_ROOT/source" add VERSION; git -C "$TMP_ROOT/source" commit -qm initial
git -C "$TMP_ROOT/source" remote add origin "$TMP_ROOT/remote.git"; git -C "$TMP_ROOT/source" push -q -u origin main
git clone -q "$TMP_ROOT/remote.git" "$TMP_ROOT/local"; git -C "$TMP_ROOT/local" checkout -q main
check="$($SYNC --project "$TMP_ROOT/local" --branch main --check)"; printf '%s' "$check" | jq -e '.status == "update-check" and (.build | startswith("0.1.0."))' >/dev/null || fail 'build check failed'
synced="$($SYNC --project "$TMP_ROOT/local" --branch main --worktree "$TMP_ROOT/test")"; printf '%s' "$synced" | jq -e '.status == "synced" and .worktree == $worktree' --arg worktree "$TMP_ROOT/test" >/dev/null || fail 'sync failed'
[ "$(cat "$TMP_ROOT/test/VERSION")" = "0.1.0" ] || fail 'wrong synced VERSION'
$VERSION --project "$TMP_ROOT/test" --bump minor | grep -q 'VERSION_BUMPED: 0.2.0' || fail 'minor bump failed'
printf 'PASS: Nightshift version and branch sync\n'
mkdir -p "$TMP_ROOT/bin" "$TMP_ROOT/unrelated"
ln -s "$ROOT/scripts/nightshift-factory.sh" "$TMP_ROOT/bin/nightshift"
installed_build=$(cd "$TMP_ROOT/unrelated" && "$TMP_ROOT/bin/nightshift" version)
[ "$installed_build" = "$(bash "$VERSION" --project "$ROOT")" ] || fail 'symlink launcher version used consumer project instead of installed source'
printf 'PASS: installed symlink resolves runtime source outside the consumer project\n'
