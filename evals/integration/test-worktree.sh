#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=evals/lib/assert.sh
source "$ROOT/evals/lib/assert.sh"
# shellcheck source=evals/fixtures/worktree-repo.sh
source "$ROOT/evals/fixtures/worktree-repo.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-worktree-eval.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
HELPER="$ROOT/scripts/nightshift-worktree.sh"
if [ ! -f "$HELPER" ]; then check 'ticket isolation capability exists' false; summary; exit 1; fi
REPO="$TMP/caller repo"; WROOT="$TMP/ticket trees"; make_repo "$REPO"
git -C "$REPO" branch prerequisite
BASE="$(git -C "$REPO" rev-parse prerequisite)"
printf 'dirty tracked\n' > "$REPO/source.txt"
printf 'dirty untracked\n' > "$REPO/untracked.txt"
git -C "$REPO" diff > "$TMP/before.diff"
git -C "$REPO" status --porcelain=v1 > "$TMP/before.status"
RC=0; bash "$HELPER" prepare one --project "$REPO" --base prerequisite --root "$WROOT" > "$TMP/one.json" 2> "$TMP/err" || RC=$?
check 'prepare dirty caller succeeds' test "$RC" -eq 0
if [ "$RC" -ne 0 ]; then cat "$TMP/err" >&2; summary; exit 1; fi
WT="$(jq -r .worktree "$TMP/one.json")"
check 'receipt identity and dependency' jq -e --arg base "$BASE" '.version==1 and .task=="one" and .branch=="nightshift/one" and .base_sha==$base and .dependency=="prerequisite" and .status=="prepared"' "$TMP/one.json"
check 'worktree is clean' test -z "$(git -C "$WT" status --porcelain)"
check 'branch starts prerequisite' test "$(git -C "$WT" rev-parse HEAD)" = "$BASE"
git -C "$REPO" diff > "$TMP/after.diff"; git -C "$REPO" status --porcelain=v1 > "$TMP/after.status"
check 'caller tracked diff preserved' cmp "$TMP/before.diff" "$TMP/after.diff"
check 'caller status preserved' cmp "$TMP/before.status" "$TMP/after.status"
check 'caller branch preserved' test "$(git -C "$REPO" branch --show-current)" = main
check 'caller untracked bytes preserved' grep -qx 'dirty untracked' "$REPO/untracked.txt"
bash "$HELPER" prepare one --project "$REPO" --root "$WROOT" > "$TMP/reused.json"
check 'same task reuses receipt path' test "$(jq -r .worktree "$TMP/reused.json")" = "$WT"
printf 'ticket dirt\n' > "$WT/ticket.txt"
RC=0; bash "$HELPER" prepare one --project "$REPO" --root "$WROOT" > /dev/null 2> "$TMP/err" || RC=$?
check 'dirty reuse rejected' test "$RC" -ne 0
bash "$HELPER" finish one --project "$REPO" > "$TMP/finished.json"
check 'finish retained status' jq -e '.status=="finished"' "$TMP/finished.json"
check 'finish keeps dirty data' grep -qx 'ticket dirt' "$WT/ticket.txt"
check 'finish keeps branch' git -C "$REPO" show-ref --verify refs/heads/nightshift/one
bash "$HELPER" finish one --project "$REPO" > /dev/null
for bad in '../escape' 'bad/name' 'x;touch'; do
  RC=0; bash "$HELPER" prepare "$bad" --project "$REPO" --root "$WROOT" > /dev/null 2>&1 || RC=$?
  check 'unsafe task rejected' test "$RC" -ne 0
done
RC=0; bash "$HELPER" prepare nested --project "$REPO" --root "$REPO/inside" > /dev/null 2>&1 || RC=$?
check 'root inside caller rejected' test "$RC" -ne 0
check 'caller nested root not created' test ! -d "$REPO/inside"
RC=0; bash "$HELPER" prepare dotted --project "$REPO" --root "$TMP/missing/../caller repo/inside" > /dev/null 2>&1 || RC=$?
check 'nonexistent dot-segment root cannot bypass caller boundary' test "$RC" -ne 0
check 'dot-segment rejection preserves caller directory' test ! -d "$REPO/inside"
ln -s "$REPO" "$TMP/alias"
RC=0; bash "$HELPER" prepare aliased --project "$REPO" --root "$TMP/missing/../alias/inside" > /dev/null 2>&1 || RC=$?
check 'symlink after missing dot segments cannot enter caller' test "$RC" -ne 0
check 'symlink rejection preserves caller directory' test ! -d "$REPO/inside"
git -C "$REPO" branch nightshift/unowned
RC=0; bash "$HELPER" prepare unowned --project "$REPO" --root "$WROOT" > /dev/null 2>&1 || RC=$?
check 'unowned branch not adopted' test "$RC" -ne 0
# Separate tasks and concurrent same-task calls must leave consistent registrations.
bash "$HELPER" prepare two --project "$REPO" --base prerequisite --root "$WROOT" > "$TMP/two.json"
check 'independent task path differs' test "$(jq -r .worktree "$TMP/two.json")" != "$WT"
bash "$HELPER" prepare race --project "$REPO" --root "$WROOT" > "$TMP/race1" 2> "$TMP/race1.err" & p1=$!
bash "$HELPER" prepare race --project "$REPO" --root "$WROOT" > "$TMP/race2" 2> "$TMP/race2.err" & p2=$!
r1=0; wait "$p1" || r1=$?; r2=0; wait "$p2" || r2=$?
check 'one concurrent preparation succeeds' test "$((r1*r2))" -eq 0
check 'one branch registration' test "$(git -C "$REPO" worktree list --porcelain | grep -c '^branch refs/heads/nightshift/race$')" -eq 1
# A tampered receipt must fail closed, retaining all worktrees.
COMMON="$(jq -r .repository "$TMP/two.json")"
printf '{"version":1}\n' > "$COMMON/nightshift/worktrees/two.json"
RC=0; bash "$HELPER" prepare two --project "$REPO" --root "$WROOT" > /dev/null 2>&1 || RC=$?
check 'malformed receipt rejected' test "$RC" -ne 0
check 'tampered receipt does not remove tree' test -d "$(jq -r .worktree "$TMP/two.json")"
summary
