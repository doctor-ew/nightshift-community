#!/usr/bin/env bash
# Acquire one implementation lease per checkout, then atomically publish scope.
set -euo pipefail
fail() { echo "nightshift-scope-activate: $*" >&2; exit 1; }
[ "$#" -ge 1 ] || fail 'usage: TASK --project PATH --spec FILE'
task=$1; shift
[[ "$task" =~ ^[[:alnum:]][[:alnum:]._-]*$ ]] || fail 'unsafe task identifier'
project=; spec=
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] && [ -n "$2" ] || fail "missing value for $1"
  case "$1" in
    --project) [ -z "$project" ] || fail 'duplicate project'; project=$2 ;;
    --spec) [ -z "$spec" ] || fail 'duplicate spec'; spec=$2 ;;
    *) fail "unknown option: $1" ;;
  esac
  shift 2
done
[ -n "$project" ] && [ -f "$spec" ] || fail 'project and readable spec are required'
project=$(git -C "$project" rev-parse --show-toplevel) || fail 'project is not a checkout'
# Only the actual section table can grant paths. Bad rows invalidate the whole list.
paths=$(awk '
  /^## / { if (section) exit; if ($0 ~ /^## Files[ -]to[ -]Change[[:space:]]*$/) {section=1; next} }
  section && /^\|/ {
    n=split($0,c,"|"); p=c[2]; gsub(/^[[:space:]]+|[[:space:]]+$/, "", p)
    if (p=="File" || p ~ /^:?-+:?$/) next
    if (n<4) {bad=1; next}
    sub(/^`/, "", p); sub(/`$/, "", p)
    if (p=="" || p ~ /^\// || p ~ /(^|\/)\.\.?(\/|$)/ || p ~ /[`\\\r\t]/ || p ~ /^[-~]/) {bad=1; next}
    print p; count++
  }
  END {if (!section || !count || bad) exit 1}
' "$spec") || fail "malformed or empty Files to Change table: $spec"
script_dir=$(cd "$(dirname "$0")" && pwd)
# Match the hook's default home; task-specific legacy trackers can live elsewhere.
state=$(bash "$script_dir/nightshift-state-dir.sh" --project "$project")
task_state=$(bash "$script_dir/nightshift-state-dir.sh" --project "$project" --task "$task")
publication_lock=$(git -C "$project" rev-parse --git-path nightshift-scope-publication.lock)
[[ "$publication_lock" = /* ]] || publication_lock="$project/$publication_lock"
locked=false; temporary=
cleanup() { [ -z "$temporary" ] || rm -f -- "$temporary"; if [ "$locked" = true ]; then rmdir "$publication_lock"; fi; }
trap cleanup EXIT
for ((attempt=0; attempt<100; attempt++)); do
  if mkdir "$publication_lock" 2>/dev/null; then locked=true; break; fi
  sleep 0.1
done
[ "$locked" = true ] || fail "scope publication busy: $state"
shopt -s nullglob
while IFS= read -r state_home; do
  [ -d "$state_home" ] || continue
  if [ -d "$state_home/.checkout-lease" ]; then
    owner=$(cat "$state_home/.checkout-lease/owner" 2>/dev/null) || fail "incomplete checkout lease: $state_home/.checkout-lease"
    [ "$owner" = "$task" ] || fail "checkout lease belongs to $owner (tracker $state_home/$owner.md)"
  fi
  for scope in "$state_home"/.active-scope-*; do
    owner=$(head -n 1 "$scope")
    [ "$scope" = "$state_home/.active-scope-$task" ] && [ "$owner" = "$task" ] || fail "checkout scope belongs to $owner: $scope (tracker $state_home/$owner.md)"
  done
done < <(bash "$script_dir/nightshift-state-dir.sh" --project "$project" --all)
# Resolve again under the checkout lock and only create state after all owners pass.
state=$(bash "$script_dir/nightshift-state-dir.sh" --project "$project")
task_state=$(bash "$script_dir/nightshift-state-dir.sh" --project "$project" --task "$task")
mkdir -p "$state"
lease="$state/.checkout-lease"
if mkdir "$lease" 2>/dev/null; then
  printf '%s\n' "$task" > "$lease/owner"
else
  owner=$(cat "$lease/owner" 2>/dev/null) || fail "incomplete checkout lease: $lease"
  [ "$owner" = "$task" ] || fail "checkout lease belongs to $owner (tracker $state/$owner.md)"
fi
temporary=$(mktemp "$state/.scope.XXXXXX")
{
  printf '%s\n%s\n' "$task" "$paths"
  # The pipeline must be able to maintain only this task's own runtime artifacts.
  printf '%s\n' "${task_state#"$project"/}/$task.md" "${task_state#"$project"/}/$task-citations.jsonl" "docs/$task/"
} > "$temporary"
mv "$temporary" "$state/.active-scope-$task"; temporary=
printf '%s\n' "$state/.active-scope-$task"
