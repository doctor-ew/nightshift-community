#!/usr/bin/env bash
# Managed, retain-only ticket worktrees. Diagnostics never contaminate JSON stdout.
set -euo pipefail
fail() { echo "nightshift-worktree: $*" >&2; exit 1; }
canonical() {
  local parent leaf composed
  if [ -d "$1" ]; then
    (cd "$1" && pwd -P)
    return
  fi
  [ ! -e "$1" ] && [ ! -L "$1" ] || { echo "nightshift-worktree: unusable directory: $1" >&2; return 1; }
  parent=$(dirname "$1"); leaf=$(basename "$1")
  [ "$parent" != "$1" ] || return 1
  parent=$(canonical "$parent") || return 1
  case "$leaf" in
    .) composed=$parent ;;
    ..) composed=$(dirname "$parent") ;;
    *) composed="${parent%/}/$leaf" ;;
  esac
  # Dot normalization can expose a directory or symlink that the original path
  # could not reach through a missing ancestor. Resolve it again physically.
  if [ -d "$composed" ]; then
    (cd "$composed" && pwd -P)
  elif [ -e "$composed" ] || [ -L "$composed" ]; then
    echo "nightshift-worktree: unusable directory: $composed" >&2
    return 1
  else
    printf '%s\n' "$composed"
  fi
}

[ "$#" -ge 2 ] || fail 'usage: prepare|finish|migrate TASK --project PATH [--base REF] [--root DIR] [--legacy PATH]'
operation=$1; task=$2; shift 2
[[ "$task" =~ ^[[:alnum:]][[:alnum:]._-]*$ ]] || fail 'unsafe task identifier'
case "$operation" in prepare|finish|migrate|refresh) ;; *) fail "unknown operation: $operation" ;; esac
project=; base=; root=; legacy=; required=; spec_worktree=; explicit=false
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] && [ -n "$2" ] || fail "missing value for $1"
  case "$1" in
    --project) [ -z "$project" ] || fail 'duplicate --project'; project=$2 ;;
    --base) [ "$operation" != finish ] && [ "$explicit" = false ] || fail 'unsupported/duplicate --base'; base=$2; explicit=true ;;
    --root) [ "$operation" != finish ] && [ -z "$root" ] || fail 'unsupported/duplicate --root'; root=$2 ;;
    --legacy) [ "$operation" = migrate ] && [ -z "$legacy" ] || fail 'unsupported/duplicate --legacy'; legacy=$2 ;;
    --spec-worktree) [ "$operation" = migrate ] && [ -z "$spec_worktree" ] || fail 'unsupported/duplicate --spec-worktree'; spec_worktree=$2 ;;
    --requires) [ "$operation" = prepare ] && [ -z "$required" ] || fail 'unsupported/duplicate --requires'; required=$2 ;;
    *) fail "unknown option: $1" ;;
  esac
  shift 2
done
[ -n "$project" ] || fail '--project is required'
project=$(git -C "$project" rev-parse --show-toplevel) || fail 'project is not a Git checkout'
project=$(canonical "$project")
common=$(git -C "$project" rev-parse --git-common-dir)
[[ "$common" = /* ]] || common="$project/$common"
common=$(canonical "$common")
branch="nightshift/$task"
git check-ref-format --branch "$branch" >/dev/null || fail 'invalid task branch'
if [ "$explicit" = true ]; then
  base_sha=$(git -C "$project" rev-parse --verify --end-of-options "$base^{commit}") || fail "invalid base: $base"
fi
if [ -n "$required" ]; then
  required_sha=$(git -C "$project" rev-parse --verify --end-of-options "$required^{commit}") || fail 'invalid prerequisite'
fi
metadata="$common/nightshift/worktrees"
mkdir -p "$metadata"
lock="$metadata/$task.lock"; locked=false; scope_locked=false; temporary=
cleanup() {
  [ -z "$temporary" ] || rm -f -- "$temporary"
  if [ "$scope_locked" = true ]; then rmdir "$publication_lock"; fi
  if [ "$locked" = true ]; then rmdir "$lock"; fi
}
trap cleanup EXIT
for ((attempt=0; attempt<100; attempt++)); do
  if mkdir "$lock" 2>/dev/null; then locked=true; break; fi
  sleep 0.1
done
[ "$locked" = true ] || fail "task lock busy; reconcile retained lock $lock"
receipt="$metadata/$task.json"
if [ "$operation" = migrate ]; then
  [ "$explicit" = true ] && [ -n "$legacy" ] || fail 'migration requires --legacy PATH and --base REF'
  [ ! -e "$receipt" ] || fail 'managed receipt already exists; use prepare/resume'
  legacy=$(canonical "$legacy")
  [ "$legacy" != "$project" ] || fail 'cannot migrate the caller checkout'
  [ "$(git -C "$legacy" rev-parse --show-toplevel)" = "$legacy" ] || fail 'legacy path is not a worktree root'
  legacy_common=$(git -C "$legacy" rev-parse --git-common-dir)
  [[ "$legacy_common" = /* ]] || legacy_common="$legacy/$legacy_common"
  [ "$(canonical "$legacy_common")" = "$common" ] || fail 'legacy repository mismatch'
  git -C "$project" worktree list --porcelain | awk -v p="worktree $legacy" '$0==p {found=1} END {exit !found}' || fail 'legacy worktree is not registered'
  [ "$(git -C "$legacy" symbolic-ref --short HEAD)" = "$branch" ] || fail 'legacy branch does not match task'
  spec_source="$legacy"
  if [ -n "$spec_worktree" ]; then
    spec_source=$(canonical "$spec_worktree")
    [ "$(git -C "$spec_source" rev-parse --show-toplevel)" = "$spec_source" ] || fail 'spec source is not a worktree root'
    spec_common=$(git -C "$spec_source" rev-parse --path-format=absolute --git-common-dir)
    [ "$(canonical "$spec_common")" = "$common" ] || fail 'spec source repository mismatch'
    git -C "$project" worktree list --porcelain | awk -v p="worktree $spec_source" '$0==p {found=1} END {exit !found}' || fail 'spec source is not registered'
    [ "$(cat "$spec_source/docs/$task/.bd-id")" = "$task" ] || fail 'spec source ticket identity mismatch'
  fi
  spec_path="$spec_source/docs/$task/SPEC.md"
  [ -f "$spec_path" ] || fail 'legacy task spec is missing'
  spec_hash=$(git hash-object "$spec_path")
  [ -n "$root" ] || root="$(dirname "$project")/$(basename "$project")-worktrees"
  root=$(canonical "$root")
  case "$root/" in "$project/"*) fail 'worktree root must be outside caller checkout' ;; esac
  case "$root/" in "$legacy/"*) fail 'migration target must be outside legacy checkout' ;; esac
  [[ "$root/$task" != *$'\n'* && "$root/$task" != *$'\r'* ]] || fail 'unsafe migration target'
  [ ! -e "$root/$task" ] && [ ! -L "$root/$task" ] || fail 'migration target already exists; choose a separate --root'
  legacy_sha=$(git -C "$legacy" rev-parse HEAD)
  archive="nightshift-legacy/$task-${legacy_sha:0:12}"
  if git -C "$project" show-ref --verify --quiet "refs/heads/$archive"; then fail 'archive branch already exists; reconcile retained migration'; fi
  migration="$metadata/$task-migration.json"
  [ ! -e "$migration" ] || fail 'migration journal exists; reconcile before retrying'
  temporary=$(mktemp "$metadata/.migration.XXXXXX")
  jq -n --arg task "$task" --arg source "$legacy" --arg head "$legacy_sha" --arg old "$branch" --arg archive "$archive" --arg base "$base_sha" --arg target "$root/$task" \
    --arg spec "$spec_path" --arg spec_hash "$spec_hash" \
    '{task:$task,legacy_worktree:$source,legacy_head:$head,original_branch:$old,archive_branch:$archive,target:$target,base_sha:$base,spec_source:$spec,spec_hash:$spec_hash,status:"planned",policy:"retain legacy files; reverify before carrying changes forward"}' > "$temporary"
  mv "$temporary" "$migration"; temporary=
  # Local rename only: never reset, clean, stash, force-push, or edit legacy files.
  git -C "$legacy" branch -m "$archive"
  temporary=$(mktemp "$metadata/.migration.XXXXXX")
  jq '.status="archived"' "$migration" > "$temporary"
  mv "$temporary" "$migration"; temporary=
  operation=prepare
fi
if [ -e "$receipt" ]; then
  jq -e --arg t "$task" --arg r "$common" --arg b "$branch" '
    type == "object" and .version == 1 and (.version|type)=="number" and
    .task == $t and .repository == $r and .branch == $b and
    (.worktree|type)=="string" and (.worktree|startswith("/")) and
    (.base_ref|type)=="string" and (.base_ref|length)>0 and
    (.base_sha|type)=="string" and (.base_sha|test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
    (.dependency|type)=="string" and (.dependency=="" or .dependency==.base_ref) and
    (.status=="prepared" or .status=="finished")' "$receipt" >/dev/null || fail "invalid receipt: $receipt"
  target=$(jq -r .worktree "$receipt")
  recorded_sha=$(jq -r .base_sha "$receipt")
  if [ -n "$required" ]; then
    git -C "$project" merge-base --is-ancestor "$required_sha" "$recorded_sha" || fail 'recorded base does not include required prerequisite'
  fi
  if [ "$explicit" = true ] && [ "$operation" != refresh ]; then
    [ "$base_sha" = "$recorded_sha" ] || fail 'explicit base differs from recorded base'
  fi
  if [ -n "$root" ]; then
    [ "$(canonical "$root")/$task" = "$target" ] || fail 'requested root differs from receipt'
  fi
  [ "$(canonical "$target")" = "$target" ] || fail 'receipt worktree path is not canonical'
  [ -d "$target" ] || fail "missing worktree: $target"
  actual=$(git -C "$target" rev-parse --git-common-dir) || fail 'invalid worktree'
  [[ "$actual" = /* ]] || actual="$target/$actual"
  [ "$(canonical "$actual")" = "$common" ] || fail 'worktree repository mismatch'
  [ "$(git -C "$target" rev-parse --show-toplevel)" = "$target" ] || fail 'worktree root mismatch'
  git -C "$project" worktree list --porcelain | awk -v p="worktree $target" '$0==p {found=1} END {exit !found}' || fail 'worktree is not registered'
  [ "$(git -C "$target" symbolic-ref --short HEAD)" = "$branch" ] || fail 'worktree branch mismatch'
  git -C "$target" merge-base --is-ancestor "$recorded_sha" HEAD || fail 'recorded base is no longer ancestral'
  if [ "$operation" = refresh ]; then
    [ "$explicit" = true ] || fail 'refresh requires --base REF'
    for state in .nightshift .drew .claude/task-progress .Codex/task-progress; do
      [ ! -e "$target/$state/.checkout-lease" ] || fail 'refresh refuses an active checkout lease'
    done
    current_sha=$(git -C "$target" rev-parse HEAD)
    [ "$current_sha" = "$recorded_sha" ] || [ "$current_sha" = "$base_sha" ] || fail 'refresh refuses ticket commits; reconcile manually'
    git -C "$target" merge-base --is-ancestor "$recorded_sha" "$base_sha" || fail 'refresh requires a fast-forward base'
    git -C "$target" diff --quiet && git -C "$target" diff --cached --quiet || fail 'refresh refuses tracked changes'
    artifacts="docs/$task"
    [ ! -L "$target/docs" ] && [ ! -L "$target/$artifacts" ] || fail 'refresh refuses symlink artifact directories'
    while IFS= read -r -d '' path; do
      case "$path" in "$artifacts/"*) ;; *) fail "refresh refuses unrelated untracked path: $path" ;; esac
    done < <(git -C "$target" ls-files --others --exclude-standard -z)
    [ -z "$(git -C "$target" ls-tree -r --name-only HEAD -- "$artifacts")" ] || fail 'artifact directory contains tracked files'
    [ -z "$(git -C "$target" ls-tree -r --name-only "$base_sha" -- "$artifacts")" ] || fail 'incoming base collides with retained artifacts'
    snapshot=$(mktemp -d "$metadata/$task-refresh.XXXXXX")
    cp "$receipt" "$snapshot/receipt-before.json"
    jq -n --arg old "$recorded_sha" --arg new "$base_sha" --arg worktree "$target" \
      '{status:"planned",old_base:$old,new_base:$new,worktree:$worktree}' > "$snapshot/journal.json"
    # Move, never delete: parked artifacts remain available for re-grounding.
    [ ! -d "$target/$artifacts" ] || mv "$target/$artifacts" "$snapshot/artifacts"
    git -C "$target" merge --ff-only --no-overwrite-ignore "$base_sha" >&2 || fail "refresh interrupted; recover from $snapshot"
    [ "$(git -C "$target" rev-parse HEAD)" = "$base_sha" ] || fail "refresh head mismatch; inspect $snapshot"
    temporary=$(mktemp "$metadata/.receipt.XXXXXX")
    jq --arg base "$base" --arg sha "$base_sha" --arg snapshot "$snapshot" \
      '.base_ref=$base | .base_sha=$sha | .dependency=$base | .status="prepared" | .refresh_history=((.refresh_history // [])+[$snapshot])' "$receipt" > "$temporary"
    mv "$temporary" "$receipt"; temporary=
    temporary=$(mktemp "$snapshot/.journal.XXXXXX")
    jq '.status="complete"' "$snapshot/journal.json" > "$temporary"
    mv "$temporary" "$snapshot/journal.json"; temporary=
    operation=prepare
  fi
  if [ "$operation" = prepare ]; then
    [ -z "$(git -C "$target" status --porcelain --untracked-files=all)" ] || fail "dirty worktree cannot be reused: $target"
  fi
else
  [ "$operation" = prepare ] || fail "no ownership receipt for $task"
  [ -n "$root" ] || root="$(dirname "$project")/$(basename "$project")-worktrees"
  root=$(canonical "$root"); target="$root/$task"
  case "$root/" in "$project/"*) fail 'worktree root must be outside caller checkout' ;; esac
  [[ "$target" != *$'\n'* && "$target" != *$'\r'* ]] || fail 'unsafe worktree path'
  [ ! -e "$target" ] && [ ! -L "$target" ] || fail "unowned target exists: $target"
  if git -C "$project" show-ref --verify --quiet "refs/heads/$branch"; then fail "unowned branch exists: $branch"; fi
  if [ "$explicit" = false ]; then base=HEAD; base_sha=$(git -C "$project" rev-parse --verify 'HEAD^{commit}'); fi
  if [ -n "$required" ]; then
    git -C "$project" merge-base --is-ancestor "$required_sha" "$base_sha" || fail 'new base does not include required prerequisite'
  fi
  mkdir -p "$root"
  git -C "$project" worktree add -b "$branch" "$target" "$base_sha" >&2 || fail "creation failed; retain and reconcile $target and $branch"
  [ "$(git -C "$target" symbolic-ref --short HEAD)" = "$branch" ] || fail 'created branch mismatch'
  git -C "$target" merge-base --is-ancestor "$base_sha" HEAD || fail 'created base mismatch'
  [ -z "$(git -C "$target" status --porcelain --untracked-files=all)" ] || fail 'created worktree is dirty; retained for reconciliation'
  dependency=; [ "$explicit" = false ] || dependency=$base
  temporary=$(mktemp "$metadata/.receipt.XXXXXX")
  jq -n --arg task "$task" --arg repository "$common" --arg branch "$branch" --arg worktree "$target" --arg base_ref "$base" --arg base_sha "$base_sha" --arg dependency "$dependency" '{version:1,task:$task,repository:$repository,branch:$branch,worktree:$worktree,base_ref:$base_ref,base_sha:$base_sha,dependency:$dependency,status:"prepared"}' > "$temporary"
  mv "$temporary" "$receipt"; temporary=
fi
if [ "$operation" = finish ]; then
  script_dir=$(cd "$(dirname "$0")" && pwd)
  publication_lock=$(git -C "$target" rev-parse --git-path nightshift-scope-publication.lock)
  [[ "$publication_lock" = /* ]] || publication_lock="$target/$publication_lock"
  mkdir "$publication_lock" 2>/dev/null || fail "scope publication busy: $publication_lock"
  scope_locked=true
  while IFS= read -r state; do
    [ -d "$state" ] || continue
    retirement=
    if [ -f "$state/.checkout-lease/owner" ] && [ "$(cat "$state/.checkout-lease/owner")" = "$task" ]; then
      retirement=$(mktemp -d "$state/.retired-$task.XXXXXX")
      mv "$state/.checkout-lease" "$retirement/checkout-lease"
    fi
    scope="$state/.active-scope-$task"
    if [ -f "$scope" ] && [ "$(head -n 1 "$scope")" = "$task" ]; then
      [ -n "$retirement" ] || retirement=$(mktemp -d "$state/.retired-$task.XXXXXX")
      mv "$scope" "$retirement/active-scope"
    fi
  done < <(bash "$script_dir/nightshift-state-dir.sh" --project "$target" --all)
fi
temporary=$(mktemp "$metadata/.receipt.XXXXXX")
status=prepared; [ "$operation" != finish ] || status=finished
jq --arg status "$status" '.status=$status' "$receipt" > "$temporary"
mv "$temporary" "$receipt"; temporary=
if [ -n "${migration:-}" ]; then
  temporary=$(mktemp "$metadata/.receipt.XXXXXX")
  jq --arg migration "$migration" '.migration=$migration' "$receipt" > "$temporary"
  mv "$temporary" "$receipt"; temporary=
  temporary=$(mktemp "$metadata/.migration.XXXXXX")
  jq '.status="prepared"' "$migration" > "$temporary"
  mv "$temporary" "$migration"; temporary=
fi
cat "$receipt"
