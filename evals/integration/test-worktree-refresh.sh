#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/evals/fixtures/worktree-repo.sh"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/nightshift-refresh.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
make_repo "$TMP/repo"
HELPER="$ROOT/scripts/nightshift-worktree.sh"
bash "$HELPER" prepare ticket --project "$TMP/repo" --root "$TMP/trees" > "$TMP/old"
mkdir -p "$TMP/trees/ticket/docs/ticket"
printf 'unfinished spec\n' > "$TMP/trees/ticket/docs/ticket/SPEC.md"
git -C "$TMP/repo" commit --allow-empty -qm advance
printf 'dirty\n' > "$TMP/trees/ticket/source.txt"
if bash "$HELPER" refresh ticket --project "$TMP/repo" --base HEAD >/dev/null 2>&1; then exit 1; fi
git -C "$TMP/repo" show HEAD:source.txt > "$TMP/trees/ticket/source.txt"
printf 'unrelated\n' > "$TMP/trees/ticket/unrelated"
if bash "$HELPER" refresh ticket --project "$TMP/repo" --base HEAD >/dev/null 2>&1; then exit 1; fi
mv "$TMP/trees/ticket/unrelated" "$TMP/retained"
bash "$HELPER" refresh ticket --project "$TMP/repo" --base HEAD > "$TMP/new"
snapshot=$(jq -r '.refresh_history[-1]' "$TMP/new")
cmp "$TMP/old" "$snapshot/receipt-before.json"
grep -qx 'unfinished spec' "$snapshot/artifacts/SPEC.md"
jq -e '.status=="complete"' "$snapshot/journal.json" >/dev/null
[ "$(git -C "$TMP/trees/ticket" rev-parse HEAD)" = "$(git -C "$TMP/repo" rev-parse HEAD)" ]
[ -z "$(git -C "$TMP/trees/ticket" status --porcelain)" ]
bash "$HELPER" prepare ticket --project "$TMP/repo" --requires HEAD >/dev/null
bash "$HELPER" prepare recovered --project "$TMP/repo" --root "$TMP/trees" >/dev/null
git -C "$TMP/repo" commit --allow-empty -qm another
next=$(git -C "$TMP/repo" rev-parse HEAD)
git -C "$TMP/trees/recovered" merge --ff-only "$next" >/dev/null
bash "$HELPER" refresh recovered --project "$TMP/repo" --base HEAD > "$TMP/recovered"
[ "$(jq -r .base_sha "$TMP/recovered")" = "$next" ]
git -C "$TMP/trees/recovered" -c user.name=test -c user.email=test@example.invalid commit --allow-empty -qm ticket-work
if bash "$HELPER" refresh recovered --project "$TMP/repo" --base HEAD >/dev/null 2>&1; then exit 1; fi
printf 'PASS: refresh fast-forwards, archives artifacts and old receipt, rejects tracked/unrelated dirt\n'
