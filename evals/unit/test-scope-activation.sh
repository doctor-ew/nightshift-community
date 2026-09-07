#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=evals/lib/assert.sh
source "$ROOT/evals/lib/assert.sh"
# shellcheck source=evals/fixtures/worktree-repo.sh
source "$ROOT/evals/fixtures/worktree-repo.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-scope-eval.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
HELPER="$ROOT/scripts/nightshift-scope-activate.sh"; LIFE="$ROOT/scripts/nightshift-worktree.sh"
if [ ! -f "$HELPER" ] || [ ! -f "$LIFE" ]; then check 'guarded scope capability exists' false; summary; exit 1; fi
REPO="$TMP/repo"; make_repo "$REPO"
bash "$LIFE" prepare alpha --project "$REPO" --root "$TMP/trees" > "$TMP/a.json"
bash "$LIFE" prepare beta --project "$REPO" --root "$TMP/trees" > "$TMP/b.json"
A="$(jq -r .worktree "$TMP/a.json")"; B="$(jq -r .worktree "$TMP/b.json")"
make_spec "$A" alpha; make_spec "$B" beta
bash "$HELPER" alpha --project "$A" --spec "$A/docs/alpha/SPEC.md"
check 'checkout lease identifies task' grep -qx alpha "$A/.nightshift/.checkout-lease/owner"
check 'scope contains declared path' grep -qx source.txt "$A/.nightshift/.active-scope-alpha"
bash "$HELPER" alpha --project "$A" --spec "$A/docs/alpha/SPEC.md"
cp "$A/.nightshift/.active-scope-alpha" "$TMP/before"
make_spec "$A" intruder
RC=0; bash "$HELPER" intruder --project "$A" --spec "$A/docs/intruder/SPEC.md" > /dev/null 2> "$TMP/err" || RC=$?
check 'same checkout collision rejected' test "$RC" -ne 0
check 'collision identifies owner' grep -q alpha "$TMP/err"
check 'collision preserves scope bytes' cmp "$TMP/before" "$A/.nightshift/.active-scope-alpha"
check 'collision creates no intruder scope' test ! -e "$A/.nightshift/.active-scope-intruder"
printf '# empty\n' > "$TMP/empty-spec"
RC=0; bash "$HELPER" alpha --project "$A" --spec "$TMP/empty-spec" > /dev/null 2>&1 || RC=$?
check 'empty allowlist rejected' test "$RC" -ne 0
check 'invalid reactivation preserves scope' cmp "$TMP/before" "$A/.nightshift/.active-scope-alpha"
bash "$HELPER" beta --project "$B" --spec "$B/docs/beta/SPEC.md"
check 'second worktree independent lease' grep -qx beta "$B/.nightshift/.checkout-lease/owner"
for kind in allow block; do
  if [ "$kind" = allow ]; then file=source.txt; expected=approve; else file=not-allowed.txt; expected=block; fi
  jq -n --arg p "$B/$file" '{tool_name:"Write",tool_input:{file_path:$p}}' | CLAUDE_PROJECT_DIR="$B" bash "$ROOT/scripts/nightshift-scope-freeze.sh" > "$TMP/hook"
  check "scope enforcement $kind" jq -e --arg verdict "$expected" '.decision==$verdict' "$TMP/hook"
done
bash "$LIFE" finish alpha --project "$REPO" > /dev/null
check 'finish releases own lease' test ! -d "$A/.nightshift/.checkout-lease"
check 'finish retires own active scope' test ! -e "$A/.nightshift/.active-scope-alpha"
check 'finish preserves other checkout owner' grep -qx beta "$B/.nightshift/.checkout-lease/owner"
check 'finish preserves spec artifact' test -f "$A/docs/alpha/SPEC.md"
# Legacy and canonical state homes share one checkout owner.
bash "$LIFE" finish beta --project "$REPO" > /dev/null
mkdir -p "$B/.drew"
printf '# legacy tracker\n' > "$B/.drew/legacy.md"
make_spec "$B" legacy; make_spec "$B" newcomer
bash "$HELPER" legacy --project "$B" --spec "$B/docs/legacy/SPEC.md"
RC=0; bash "$HELPER" newcomer --project "$B" --spec "$B/docs/newcomer/SPEC.md" > /dev/null 2> "$TMP/legacy-error" || RC=$?
check 'legacy/current checkout collision rejected' test "$RC" -ne 0
check 'legacy collision identifies owner' grep -q legacy "$TMP/legacy-error"
jq -n --arg p "$B/forbidden.txt" '{tool_name:"Write",tool_input:{file_path:$p}}' | CLAUDE_PROJECT_DIR="$B" bash "$ROOT/scripts/nightshift-scope-freeze.sh" > "$TMP/legacy-hook"
check 'legacy owner scope remains enforced in existing canonical home' jq -e '.decision=="block"' "$TMP/legacy-hook"
check 'canonical competing scope absent' test ! -e "$B/.nightshift/.active-scope-newcomer"
# Rejected activation cannot create a canonical home that hides legacy enforcement.
bash "$LIFE" prepare gamma --project "$REPO" --root "$TMP/trees" > "$TMP/c.json"
C="$(jq -r .worktree "$TMP/c.json")"
mkdir -p "$C/.drew"; printf '# old tracker\n' > "$C/.drew/old.md"
make_spec "$C" old; make_spec "$C" fresh
bash "$HELPER" old --project "$C" --spec "$C/docs/old/SPEC.md"
RC=0; bash "$HELPER" fresh --project "$C" --spec "$C/docs/fresh/SPEC.md" > /dev/null 2>&1 || RC=$?
check 'fresh task rejected against legacy owner' test "$RC" -ne 0
check 'rejection does not create canonical state home' test ! -d "$C/.nightshift"
jq -n --arg p "$C/forbidden.txt" '{tool_name:"Write",tool_input:{file_path:$p}}' | CLAUDE_PROJECT_DIR="$C" bash "$ROOT/scripts/nightshift-scope-freeze.sh" > "$TMP/fresh-hook"
check 'rejected activation preserves effective legacy scope' jq -e '.decision=="block"' "$TMP/fresh-hook"
summary
