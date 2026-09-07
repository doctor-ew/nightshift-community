#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/evals/fixtures/worktree-repo.sh"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/nightshift-prerequisite.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
make_repo "$TMP/repo"
HELPER="$ROOT/scripts/nightshift-worktree.sh"
git -C "$TMP/repo" branch prerequisite
git -C "$TMP/repo" commit --allow-empty -qm integration
bash "$HELPER" prepare ticket --project "$TMP/repo" --base HEAD --root "$TMP/trees" > "$TMP/before"
bash "$HELPER" prepare ticket --project "$TMP/repo" --requires prerequisite > "$TMP/after"
cmp "$TMP/before" "$TMP/after"
if bash "$HELPER" prepare ticket --project "$TMP/repo" --base prerequisite >/dev/null 2>&1; then exit 1; fi
git -C "$TMP/repo" commit --allow-empty -qm newer
if bash "$HELPER" prepare ticket --project "$TMP/repo" --requires HEAD >/dev/null 2>&1; then exit 1; fi
if bash "$HELPER" prepare ticket --project "$TMP/repo" --requires nonexistent >/dev/null 2>&1; then exit 1; fi
if bash "$HELPER" prepare other --project "$TMP/repo" --base prerequisite --requires HEAD --root "$TMP/trees" >/dev/null 2>&1; then exit 1; fi
[ ! -e "$TMP/trees/other" ]
git -C "$TMP/repo" checkout -qb divergent prerequisite
git -C "$TMP/repo" commit --allow-empty -qm divergent
if bash "$HELPER" prepare ticket --project "$TMP/repo" --requires divergent >/dev/null 2>&1; then exit 1; fi
printf 'PASS: included prerequisite accepted without rewriting base; missing/newer/divergent requirements rejected\n'
