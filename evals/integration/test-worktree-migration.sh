#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/evals/fixtures/worktree-repo.sh"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/nightshift-migration.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
make_repo "$TMP/repo"
HELPER="$ROOT/scripts/nightshift-worktree.sh"
git -C "$TMP/repo" worktree add -b nightshift/ticket "$TMP/legacy" >/dev/null
mkdir -p "$TMP/legacy/docs/ticket"
printf 'legacy spec\n' > "$TMP/legacy/docs/ticket/SPEC.md"
printf 'unfinished tracked work\n' > "$TMP/legacy/source.txt"
printf 'unfinished untracked work\n' > "$TMP/legacy/new.txt"
git -C "$TMP/legacy" diff --binary > "$TMP/before.diff"
git -C "$TMP/legacy" status --porcelain > "$TMP/before.status"
head=$(git -C "$TMP/legacy" rev-parse HEAD)
if bash "$HELPER" prepare ticket --project "$TMP/repo" --root "$TMP/new" >/dev/null 2>&1; then exit 1; fi
if bash "$HELPER" migrate wrong --project "$TMP/repo" --legacy "$TMP/legacy" --base HEAD --root "$TMP/new" >/dev/null 2>&1; then exit 1; fi
if bash "$HELPER" migrate ticket --project "$TMP/repo" --legacy "$TMP/legacy" --root "$TMP/new" >/dev/null 2>&1; then exit 1; fi
[ "$(git -C "$TMP/legacy" symbolic-ref --short HEAD)" = nightshift/ticket ]
bash "$HELPER" migrate ticket --project "$TMP/repo" --legacy "$TMP/legacy" --base HEAD --root "$TMP/new" > "$TMP/receipt"
jq -e '.status=="prepared" and (.migration|length)>0' "$TMP/receipt" >/dev/null
jq -e '.status=="prepared"' "$(jq -r .migration "$TMP/receipt")" >/dev/null
[ "$(git -C "$TMP/legacy" rev-parse HEAD)" = "$head" ]
git -C "$TMP/legacy" diff --binary > "$TMP/after.diff"
git -C "$TMP/legacy" status --porcelain > "$TMP/after.status"
cmp "$TMP/before.diff" "$TMP/after.diff"
cmp "$TMP/before.status" "$TMP/after.status"
grep -qx 'unfinished untracked work' "$TMP/legacy/new.txt"
[ "$(git -C "$TMP/legacy" symbolic-ref --short HEAD)" = "nightshift-legacy/ticket-${head:0:12}" ]
[ -z "$(git -C "$TMP/new/ticket" status --porcelain)" ]
bash "$HELPER" prepare ticket --project "$TMP/repo" --root "$TMP/new" >/dev/null
if bash "$HELPER" migrate ticket --project "$TMP/repo" --legacy "$TMP/legacy" --base HEAD --root "$TMP/new" >/dev/null 2>&1; then exit 1; fi
printf 'PASS: migration preserves dirty legacy work and creates a reusable clean receipt\n'
git -C "$TMP/repo" worktree add -b nightshift/split "$TMP/split" >/dev/null
git -C "$TMP/repo" worktree add -b split-spec "$TMP/spec" >/dev/null
mkdir -p "$TMP/spec/docs/split"
printf 'split spec\n' > "$TMP/spec/docs/split/SPEC.md"
printf 'wrong\n' > "$TMP/spec/docs/split/.bd-id"
if bash "$HELPER" migrate split --project "$TMP/repo" --legacy "$TMP/split" --spec-worktree "$TMP/spec" --base HEAD --root "$TMP/new" >/dev/null 2>&1; then exit 1; fi
[ "$(git -C "$TMP/split" symbolic-ref --short HEAD)" = nightshift/split ]
printf 'split\n' > "$TMP/spec/docs/split/.bd-id"
bash "$HELPER" migrate split --project "$TMP/repo" --legacy "$TMP/split" --spec-worktree "$TMP/spec" --base HEAD --root "$TMP/new" > "$TMP/split-receipt"
journal=$(jq -r .migration "$TMP/split-receipt")
[ "$(jq -r .spec_hash "$journal")" = "$(git hash-object "$TMP/spec/docs/split/SPEC.md")" ]
grep -qx 'split spec' "$TMP/spec/docs/split/SPEC.md"
printf 'PASS: registered cross-worktree spec identity and content hash verified\n'
