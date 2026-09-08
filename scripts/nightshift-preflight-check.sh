#!/usr/bin/env bash
# nightshift-preflight-check.sh — deterministic, read-only admission coordinator.
#
# Runs the same checks nightshift-factory.sh would eventually hit anyway, in a
# fixed order, before any provider is invoked and before factory's own setup,
# dashboard, or auth probes run: (1) project/baseline, (2) local-input/ticket
# identity, (3) manifest, (4) worktree collision. Every check shares the exact
# predicate an actual run would use (nightshift-baseline-check.sh,
# nightshift-ticket-source.sh --derive-id, nightshift-manifest-validate.sh,
# nightshift-worktree.sh check) — this script does not re-implement any of
# them. It never mutates state and never runs automatic repair/migration/setup
# on failure; that stays an explicit, separate operator action.
#
# Usage:
#   nightshift-preflight-check.sh --project DIR --branch VALUE
#     (--ref REF | --batch-input TEXT | --resume FILE)
#     [--base REF] [--root DIR] [--requires REF]
#
# Emits exactly one JSON object to stdout:
#   {
#     "schema_version": 1,
#     "status": "ok" | "blocked",
#     "checks": {"baseline":.., "input":.., "manifest":.., "collision":..}  # pass|fail|not_applicable
#     "reason": "<enum>" | null,
#     "next_action": "<enum>" | null,
#     "tasks": ["<task-id>", ...]
#   }
#
# reason (only set when status=blocked): BASE_MISSING, SPEC_INPUT_INVALID,
#   MANIFEST_MISSING, MANIFEST_INVALID, WORKTREE_COLLISION, TASK_UNRESOLVED,
#   INPUT_RESOLUTION_REQUIRED, BRANCH_POLICY_UNSUPPORTED, USAGE.
#
# Exit code mirrors reason (documented, stable, scriptable):
#   0 ok · 64 USAGE · 65 SPEC_INPUT_INVALID · 66 BASE_MISSING ·
#   67 WORKTREE_COLLISION · 68 MANIFEST_MISSING/MANIFEST_INVALID ·
#   69 TASK_UNRESOLVED · 70 BRANCH_POLICY_UNSUPPORTED · 71 INPUT_RESOLUTION_REQUIRED
#
# stdout never contains secrets, raw error text, prompts, or ticket bodies —
# only the fixed fields above and bare task identifiers.
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PROJECT="" BRANCH="" REF="" BATCH_INPUT="" RESUME="" BASE="" ROOT="" REQUIRES=""
HAVE_REF=false HAVE_BATCH=false HAVE_RESUME=false HAVE_BASE=false HAVE_ROOT=false HAVE_REQUIRES=false
HAVE_PROJECT=false HAVE_BRANCH=false
USAGE_ERR=""

emit() {
  # $1=status $2=baseline $3=input $4=manifest $5=collision $6=reason $7=next_action; $8..=tasks
  local status="$1" baseline="$2" input="$3" manifest="$4" collision="$5" reason="$6" next_action="$7"
  shift 7
  local tasks_json="[]"
  if [ "$#" -gt 0 ]; then
    tasks_json="$(printf '%s\n' "$@" | jq -R . | jq -s .)"
  fi
  jq -cn --arg status "$status" --arg baseline "$baseline" --arg input "$input" \
    --arg manifest "$manifest" --arg collision "$collision" \
    --arg reason "$reason" --arg next_action "$next_action" --argjson tasks "$tasks_json" '
    {
      schema_version: 1,
      status: $status,
      checks: {baseline:$baseline, input:$input, manifest:$manifest, collision:$collision},
      reason: (if $reason == "" then null else $reason end),
      next_action: (if $next_action == "" then null else $next_action end),
      tasks: $tasks
    }'
}

block() {
  # $1=reason $2=next_action $3=exit_code; checks state comes from globals below
  emit blocked "$CK_BASELINE" "$CK_INPUT" "$CK_MANIFEST" "$CK_COLLISION" "$1" "$2" "${TASKS[@]}"
  exit "$3"
}

CK_BASELINE=not_applicable CK_INPUT=not_applicable CK_MANIFEST=not_applicable CK_COLLISION=not_applicable
TASKS=()
REFS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      [ "$#" -ge 2 ] || { USAGE_ERR="missing value for --project"; break; }
      [ "$HAVE_PROJECT" = false ] || { USAGE_ERR="duplicate --project"; break; }
      PROJECT="$2"; HAVE_PROJECT=true; shift 2 ;;
    --branch)
      [ "$#" -ge 2 ] || { USAGE_ERR="missing value for --branch"; break; }
      [ "$HAVE_BRANCH" = false ] || { USAGE_ERR="duplicate --branch"; break; }
      BRANCH="$2"; HAVE_BRANCH=true; shift 2 ;;
    --ref)
      [ "$#" -ge 2 ] || { USAGE_ERR="missing value for --ref"; break; }
      [ -n "$2" ] || { USAGE_ERR="empty --ref"; break; }
      REFS+=("$2"); HAVE_REF=true; shift 2 ;;
    --batch-input)
      [ "$#" -ge 2 ] || { USAGE_ERR="missing value for --batch-input"; break; }
      [ "$HAVE_BATCH" = false ] || { USAGE_ERR="duplicate --batch-input"; break; }
      BATCH_INPUT="$2"; HAVE_BATCH=true; shift 2 ;;
    --resume)
      [ "$#" -ge 2 ] || { USAGE_ERR="missing value for --resume"; break; }
      [ "$HAVE_RESUME" = false ] || { USAGE_ERR="duplicate --resume"; break; }
      RESUME="$2"; HAVE_RESUME=true; shift 2 ;;
    --base)
      [ "$#" -ge 2 ] || { USAGE_ERR="missing value for --base"; break; }
      [ "$HAVE_BASE" = false ] || { USAGE_ERR="duplicate --base"; break; }
      BASE="$2"; HAVE_BASE=true; shift 2 ;;
    --root)
      [ "$#" -ge 2 ] || { USAGE_ERR="missing value for --root"; break; }
      [ "$HAVE_ROOT" = false ] || { USAGE_ERR="duplicate --root"; break; }
      ROOT="$2"; HAVE_ROOT=true; shift 2 ;;
    --requires)
      [ "$#" -ge 2 ] || { USAGE_ERR="missing value for --requires"; break; }
      [ "$HAVE_REQUIRES" = false ] || { USAGE_ERR="duplicate --requires"; break; }
      REQUIRES="$2"; HAVE_REQUIRES=true; shift 2 ;;
    *) USAGE_ERR="unknown option: $1"; break ;;
  esac
done

[ -n "$USAGE_ERR" ] || { [ "$HAVE_PROJECT" = true ] || USAGE_ERR="--project is required"; }
[ -n "$USAGE_ERR" ] || { [ "$HAVE_BRANCH" = true ] || USAGE_ERR="--branch is required"; }
if [ -z "$USAGE_ERR" ]; then
  count=0
  [ "$HAVE_REF" = true ] && count=$((count + 1))
  [ "$HAVE_BATCH" = true ] && count=$((count + 1))
  [ "$HAVE_RESUME" = true ] && count=$((count + 1))
  [ "$count" -eq 1 ] || USAGE_ERR="exactly one of --ref, --batch-input, or --resume is required"
fi
if [ -n "$USAGE_ERR" ]; then
  block USAGE fix_usage 64
fi

PROJECT="$(cd "$PROJECT" 2>/dev/null && pwd)" || block USAGE fix_usage 64

# ── (1) project / baseline ──────────────────────────────────────────────────
if bash "$SCRIPT_DIR/nightshift-baseline-check.sh" --project "$PROJECT" --branch "$BRANCH" >/dev/null 2>&1; then
  CK_BASELINE=pass
else
  CK_BASELINE=fail
  block BASE_MISSING commit_initial_baseline 66
fi

# ── (2) local input / ticket identity ───────────────────────────────────────
derive_task() {
  # Prints the resolved task id on stdout; on failure, sets DERIVE_REASON and
  # returns nonzero. Never prints ticket title/body/url.
  local ref="$1" out rc errfile
  errfile="$(mktemp "${TMPDIR:-/tmp}/nightshift-preflight-derive.XXXXXX")"
  out="$(bash "$SCRIPT_DIR/nightshift-ticket-source.sh" --derive-id "$ref" --project "$PROJECT" 2>"$errfile")"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    rm -f "$errfile"
    TASK_ID=$(printf '%s\n' "$out" | jq -er '.source_id')
    return $?
  fi
  if [ "$rc" -eq 65 ]; then
    DERIVE_REASON=SPEC_INPUT_INVALID
  elif grep -q 'no docs/\*/\.bd-id points to it' "$errfile" 2>/dev/null; then
    DERIVE_REASON=TASK_UNRESOLVED
  else
    DERIVE_REASON=INPUT_RESOLUTION_REQUIRED
  fi
  rm -f "$errfile"
  return 1
}

reason_exit() {
  case "$1" in
    SPEC_INPUT_INVALID) echo 65 ;;
    TASK_UNRESOLVED) echo 69 ;;
    INPUT_RESOLUTION_REQUIRED) echo 71 ;;
    *) echo 1 ;;
  esac
}
reason_next_action() {
  case "$1" in
    SPEC_INPUT_INVALID) echo fix_spec_input ;;
    TASK_UNRESOLVED) echo resolve_task_mapping ;;
    INPUT_RESOLUTION_REQUIRED) echo provide_explicit_ticket_list ;;
    *) echo "" ;;
  esac
}

if [ "$HAVE_REF" = true ]; then
  for REF in "${REFS[@]}"; do
  if derive_task "$REF"; then
    TASKS+=("$TASK_ID")
    CK_INPUT=pass
  else
    CK_INPUT=fail
    block "$DERIVE_REASON" "$(reason_next_action "$DERIVE_REASON")" "$(reason_exit "$DERIVE_REASON")"
  fi
  done
elif [ "$HAVE_BATCH" = true ]; then
  RESOLVED="$(CLAUDE_PROJECT_DIR="$PROJECT" bash "$SCRIPT_DIR/nightshift-batch-resolve.sh" --input "$BATCH_INPUT" 2>/dev/null)"
  rc=$?
  if [ "$rc" -eq 2 ]; then
    CK_INPUT=fail
    block INPUT_RESOLUTION_REQUIRED provide_explicit_ticket_list 71
  elif [ "$rc" -ne 0 ] || [ -z "$RESOLVED" ]; then
    CK_INPUT=fail
    block INPUT_RESOLUTION_REQUIRED provide_explicit_ticket_list 71
  fi
  TASKS=()
  while IFS= read -r one; do
    [ -n "$one" ] || continue
    if derive_task "$one"; then
      TASKS+=("$TASK_ID")
    else
      CK_INPUT=fail
      block "$DERIVE_REASON" "$(reason_next_action "$DERIVE_REASON")" "$(reason_exit "$DERIVE_REASON")"
    fi
  done <<< "$RESOLVED"
  CK_INPUT=pass
elif [ "$HAVE_RESUME" = true ]; then
  BASENAME="$(basename "$RESUME")"
  if ! [[ "$BASENAME" =~ ^batch-[0-9]+-[0-9]+\.json$ ]]; then
    CK_INPUT=fail
    block SPEC_INPUT_INVALID fix_spec_input 65
  fi
  STATE_DIR="$(bash "$SCRIPT_DIR/nightshift-state-dir.sh" --project "$PROJECT" --task "$BASENAME" 2>/dev/null)"
  STATE_PATH="$STATE_DIR/$BASENAME"
  if [ ! -f "$STATE_PATH" ] || ! jq -e 'type == "object" and (.tickets | type == "array" and length > 0 and all(.[]; type == "string" and length > 0)) and (.statuses | type == "object")' "$STATE_PATH" >/dev/null 2>&1; then
    CK_INPUT=fail
    block SPEC_INPUT_INVALID fix_spec_input 65
  fi
  PENDING="$(jq -r '
    (.tickets // [])[] as $k |
    if (((.statuses // {})[$k].status // "pending") | test("^(complete|skipped)$") | not) then $k else empty end
  ' "$STATE_PATH" 2>/dev/null)"
  if [ "$?" -ne 0 ]; then
    CK_INPUT=fail
    block SPEC_INPUT_INVALID fix_spec_input 65
  fi
  TASKS=()
  if [ -n "$PENDING" ]; then
    while IFS= read -r one; do
      [ -n "$one" ] || continue
      if derive_task "$one"; then
        TASKS+=("$TASK_ID")
      else
        CK_INPUT=fail
        block "$DERIVE_REASON" "$(reason_next_action "$DERIVE_REASON")" "$(reason_exit "$DERIVE_REASON")"
      fi
    done <<< "$PENDING"
  fi
  CK_INPUT=pass
fi

# ── (3) manifest ─────────────────────────────────────────────────────────────
MANIFEST_OUT="$(bash "$SCRIPT_DIR/nightshift-manifest-validate.sh" --project "$PROJECT" 2>/dev/null)"
rc=$?
if [ "$rc" -eq 0 ]; then
  CK_MANIFEST=pass
else
  CK_MANIFEST=fail
  MANIFEST_CODE="$(printf '%s' "$MANIFEST_OUT" | jq -r '.code // ""' 2>/dev/null)"
  if [ "$MANIFEST_CODE" = MANIFEST_MISSING ]; then
    block MANIFEST_MISSING run_setup 68
  else
    block MANIFEST_INVALID fix_manifest 68
  fi
fi

# ── (4) worktree collision ──────────────────────────────────────────────────
if [ "$BRANCH" = none ]; then
  CK_COLLISION=not_applicable
elif [ "$BRANCH" != auto ]; then
  # The worktree layer only ever manages the fixed nightshift/<task> branch.
  # A literal named branch has no corresponding managed-branch predicate to
  # check here; approving it against the fixed name would be a false pass
  # for a branch the real run would not actually use.
  CK_COLLISION=fail
  block BRANCH_POLICY_UNSUPPORTED use_supported_branch_policy 70
else
  CK_COLLISION=pass
  for task in "${TASKS[@]}"; do
    ARGS=(check "$task" --project "$PROJECT")
    [ "$HAVE_BASE" = true ] && ARGS+=(--base "$BASE")
    [ "$HAVE_ROOT" = true ] && ARGS+=(--root "$ROOT")
    [ "$HAVE_REQUIRES" = true ] && ARGS+=(--requires "$REQUIRES")
    if ! bash "$SCRIPT_DIR/nightshift-worktree.sh" "${ARGS[@]}" >/dev/null 2>&1; then
      CK_COLLISION=fail
      break
    fi
  done
  if [ "$CK_COLLISION" = fail ]; then
    block WORKTREE_COLLISION reconcile_worktree 67
  fi
fi

emit ok "$CK_BASELINE" "$CK_INPUT" "$CK_MANIFEST" "$CK_COLLISION" "" start_provider "${TASKS[@]}"
exit 0
