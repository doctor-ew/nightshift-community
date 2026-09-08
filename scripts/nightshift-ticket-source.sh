#!/usr/bin/env bash
# nightshift-ticket-source.sh — normalize a ticket reference into a JSON blob.
#
# Usage:
#   nightshift-ticket-source.sh <ref>
#
# Ref formats:
#   gh:123                 GitHub Issue 123 in the current repo
#   gh:owner/repo#123      GitHub Issue 123 in owner/repo
#   jira:KEY-123           Jira issue KEY-123 (requires JIRA_BASE_URL + JIRA_TOKEN env)
#   monday:1234567890      Monday item id (requires MONDAY_TOKEN env)
#   notion:<page-id>       Notion page (requires NOTION_TOKEN env)
#   bd:bd-abc123           Beads issue (local)
#   <bare>                 Auto-detect: try beads first (id wildcard), then prompt
#
# Emits JSON to stdout:
#   {
#     "source":      "gh|jira|monday|notion|bd",
#     "source_id":   "<id within source>",
#     "external_ref":"<source>-<id>",
#     "title":       "...",
#     "body":        "...",
#     "labels":      ["...", "..."],
#     "url":         "https://...",
#     "state":       "open|closed|in_progress|..."
#   }
#
# Exits non-zero with a JSON error blob if the ref cannot be resolved.

set -euo pipefail

# ───────────────────────────── --derive-id ─────────────────────────────
# nightshift-ticket-source.sh --derive-id REF --project DIR
#
# Cheap identity-only classification for admission checks: reuses this
# script's own source classification and, for GitHub/Jira/Monday/Notion refs,
# derives source/source_id/external_ref directly from the ref text — no
# network fetch, no title/body. Beads and task-key refs still resolve
# locally (an existing task folder, or an existing docs/*/.bd-id mapping for
# a bare bead id) since that identity cannot be read off the ref text alone;
# a missing/ambiguous mapping is a hard failure, never a silent skip. Emits
# {"source":...,"source_id":...,"external_ref":...} on success; a JSON error
# blob on stderr and a nonzero exit otherwise. Callers decide the admission
# reason/exit code for their own contract — this only reports resolvability.
if [ "${1:-}" = "--derive-id" ]; then
  shift
  D_REF="" D_PROJECT=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --project)
        [ "$#" -ge 2 ] || { jq -cn '{error:"--derive-id: missing value for --project"}' >&2; exit 64; }
        [ -z "$D_PROJECT" ] || exit 64
        D_PROJECT="$2"; shift 2 ;;
      --*) jq -cn --arg m "--derive-id: unknown option: $1" '{error:$m}' >&2; exit 64 ;;
      *)
        [ -z "$D_REF" ] || { jq -cn '{error:"--derive-id: only one ref is accepted"}' >&2; exit 64; }
        D_REF="$1"; shift ;;
    esac
  done
  [ -n "$D_REF" ] || { jq -cn '{error:"--derive-id: missing ref argument"}' >&2; exit 64; }
  [ -n "$D_PROJECT" ] || { jq -cn '{error:"--derive-id: --project is required"}' >&2; exit 64; }
  D_PROJECT="$(cd "$D_PROJECT" 2>/dev/null && pwd)" || { jq -cn '{error:"--derive-id: project directory not found"}' >&2; exit 64; }

  derive_error() { jq -cn --arg msg "$1" '{error:$msg}' >&2; exit 1; }

  # Local Markdown specs already have a cheap, network-free, non-fetching
  # identity derivation; reuse it verbatim rather than re-implementing it.
  if [[ "$D_REF" == spec:* ]] || [ -f "$D_PROJECT/$D_REF" ] || { [[ "$D_REF" = /* ]] && [ -f "$D_REF" ]; }; then
    normalizer="$(cd "$(dirname "$0")" && pwd)/nightshift-spec-source.py"
    (cd "$D_PROJECT" && python3 "$normalizer" "$D_REF") | jq '{source,source_id,external_ref}'
    exit "${PIPESTATUS[0]}"
  fi

  case "$D_REF" in
    gh:*)
      raw="${D_REF#gh:}"; id="${raw##*#}"
      [ -n "$id" ] || derive_error "gh ref requires an issue number"
      jq -cn --arg sid "$id" '{source:"gh",source_id:$sid,external_ref:("gh-"+$sid)}' ;;
    jira:*)
      raw="${D_REF#jira:}"
      [ -n "$raw" ] || derive_error "jira ref requires an issue key"
      jq -cn --arg sid "$raw" '{source:"jira",source_id:$sid,external_ref:("jira-"+$sid)}' ;;
    monday:*)
      raw="${D_REF#monday:}"
      [ -n "$raw" ] || derive_error "monday ref requires an item id"
      jq -cn --arg sid "$raw" '{source:"monday",source_id:$sid,external_ref:("monday-"+$sid)}' ;;
    notion:*)
      raw="${D_REF#notion:}"
      [ -n "$raw" ] || derive_error "notion ref requires a page id"
      jq -cn --arg sid "$raw" '{source:"notion",source_id:$sid,external_ref:("notion-"+$sid)}' ;;
    bd:*|bd-*)
      raw="$D_REF"; [[ "$D_REF" == bd:* ]] && raw="${D_REF#bd:}"
      command -v bd >/dev/null 2>&1 && (cd "$D_PROJECT" && bd show "$raw" --json) >/dev/null 2>&1 || derive_error "bd show failed for $raw; beads unavailable or issue not found"
      jq -cn --arg sid "$raw" '{source:"bd",source_id:$sid,external_ref:$sid}' ;;
    *)
      if [ -f "${D_PROJECT}/docs/${D_REF}/SPEC.md" ]; then
        # Existing task folder: the folder key is already the canonical identity.
        jq -cn --arg sid "$D_REF" '{source:"task",source_id:$sid,external_ref:$sid}'
      elif command -v bd >/dev/null 2>&1 && (cd "$D_PROJECT" && bd show "$D_REF" --json) >/dev/null 2>&1; then
        mapped=""
        for f in "${D_PROJECT}"/docs/*/.bd-id; do
          [ -f "$f" ] || continue
          if [ "$(cat "$f" 2>/dev/null)" = "$D_REF" ]; then
            [ -z "$mapped" ] || derive_error 'ambiguous bead mapping'
            mapped="$(basename "$(dirname "$f")")"
          fi
        done
        if [ -z "$mapped" ]; then
          derive_error "bead $D_REF exists but no docs/*/.bd-id points to it; run nightshift-product bd:$D_REF or pass the task key directly"
        fi
        jq -cn --arg sid "$mapped" --arg bead "$D_REF" '{source:"task",source_id:$sid,external_ref:$sid,bead_id:$bead}'
      else
        derive_error "bare ref '$D_REF' did not resolve as a task key or a beads issue; prefix it with gh:/jira:/monday:/notion:/bd: to disambiguate"
      fi
      ;;
  esac
  exit 0
fi

REF="${1:-}"
if [ -z "$REF" ]; then
  jq -n '{error: "nightshift-ticket-source.sh: missing ref argument"}' >&2
  exit 64
fi

emit_error() {
  local msg="$1"
  jq -n --arg msg "$msg" '{error: $msg}' >&2
  exit 1
}

# ───────────────────────────── source detection ─────────────────────────────

if [[ "$REF" == spec:* ]] || [ -f "$REF" ]; then
  exec python3 "$(dirname "$0")/nightshift-spec-source.py" "$REF"
fi

case "$REF" in
  gh:*)      SOURCE="gh";      RAW="${REF#gh:}" ;;
  jira:*)    SOURCE="jira";    RAW="${REF#jira:}" ;;
  monday:*)  SOURCE="monday";  RAW="${REF#monday:}" ;;
  notion:*)  SOURCE="notion";  RAW="${REF#notion:}" ;;
  bd:*)      SOURCE="bd";      RAW="${REF#bd:}" ;;
  bd-*)      SOURCE="bd";      RAW="$REF" ;;
  *)
    # Bare ref — try beads lookup. If nothing matches, error out asking for prefix.
    if bd show "$REF" --json >/dev/null 2>&1; then
      SOURCE="bd"; RAW="$REF"
    else
      emit_error "nightshift-ticket-source.sh: bare ref '$REF' did not resolve as a beads issue. Prefix it with gh:/jira:/monday:/notion:/bd: to disambiguate."
    fi
    ;;
esac

# ───────────────────────────── adapters ─────────────────────────────

fetch_gh() {
  local raw="$1" repo_arg=() id
  if [[ "$raw" == *"#"* ]]; then
    repo_arg=(--repo "${raw%#*}")
    id="${raw#*#}"
  else
    id="$raw"
  fi
  local json
  if ! json=$(gh issue view "$id" "${repo_arg[@]}" \
      --json number,title,body,state,labels,url 2>&1); then
    emit_error "gh issue view failed: $json"
  fi
  echo "$json" | jq --arg src "gh" --arg sid "$id" '{
    source:       $src,
    source_id:    $sid,
    external_ref: ("gh-" + $sid),
    title:        .title,
    body:         (.body // ""),
    labels:       [.labels[]?.name],
    url:          .url,
    state:        (.state // "open" | ascii_downcase)
  }'
}

fetch_jira() {
  local key="$1"
  : "${JIRA_BASE_URL:?nightshift-ticket-source.sh: JIRA_BASE_URL not set}"
  : "${JIRA_TOKEN:?nightshift-ticket-source.sh: JIRA_TOKEN not set}"
  : "${JIRA_EMAIL:?nightshift-ticket-source.sh: JIRA_EMAIL not set}"
  local json
  if ! json=$(curl -fsS -u "${JIRA_EMAIL}:${JIRA_TOKEN}" \
      -H "Accept: application/json" \
      "${JIRA_BASE_URL%/}/rest/api/3/issue/${key}" 2>&1); then
    emit_error "jira fetch failed for $key: $json"
  fi
  echo "$json" | jq --arg src "jira" --arg sid "$key" --arg base "${JIRA_BASE_URL%/}" '{
    source:       $src,
    source_id:    $sid,
    external_ref: ("jira-" + $sid),
    title:        .fields.summary,
    body:         (.fields.description // "" | tostring),
    labels:       (.fields.labels // []),
    url:          ($base + "/browse/" + $sid),
    state:        (.fields.status.name // "open" | ascii_downcase)
  }'
}

fetch_monday() {
  local item_id="$1"
  : "${MONDAY_TOKEN:?nightshift-ticket-source.sh: MONDAY_TOKEN not set}"
  local query payload json
  query='query ($id: [ID!]) { items (ids: $id) { id name state url updates { body } column_values { id text } } }'
  payload=$(jq -n --arg q "$query" --arg id "$item_id" \
    '{query: $q, variables: {id: [$id]}}')
  if ! json=$(curl -fsS -X POST \
      -H "Authorization: ${MONDAY_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "$payload" \
      "https://api.monday.com/v2" 2>&1); then
    emit_error "monday fetch failed for $item_id: $json"
  fi
  echo "$json" | jq --arg src "monday" --arg sid "$item_id" '
    .data.items[0] as $i |
    if $i == null then error("monday: item not found") else
      {
        source:       $src,
        source_id:    $sid,
        external_ref: ("monday-" + $sid),
        title:        $i.name,
        body:         ([$i.column_values[]? | "\(.id): \(.text // "")"] | join("\n")),
        labels:       [],
        url:          ($i.url // ""),
        state:        (($i.state // "active") | ascii_downcase)
      }
    end'
}

fetch_notion() {
  local page_id="$1"
  : "${NOTION_TOKEN:?nightshift-ticket-source.sh: NOTION_TOKEN not set}"
  local json
  if ! json=$(curl -fsS \
      -H "Authorization: Bearer ${NOTION_TOKEN}" \
      -H "Notion-Version: 2022-06-28" \
      "https://api.notion.com/v1/pages/${page_id}" 2>&1); then
    emit_error "notion fetch failed for $page_id: $json"
  fi
  echo "$json" | jq --arg src "notion" --arg sid "$page_id" '
    {
      source:       $src,
      source_id:    $sid,
      external_ref: ("notion-" + $sid),
      title:        ([.properties[]? | select(.title?) | .title[]?.plain_text] | join("") // "(untitled)"),
      body:         "",
      labels:       [],
      url:          (.url // ""),
      state:        (if (.archived // false) then "closed" else "open" end)
    }'
}

fetch_bd() {
  local bid="$1" json
  if ! json=$(bd show "$bid" --json 2>&1); then
    emit_error "bd show failed for $bid: $json"
  fi
  # `bd show --json` emits a single-element array; unwrap to object via `.[0]`
  # so the field accessors below work whether bd returns [{...}] or {...}.
  echo "$json" | jq --arg src "bd" --arg sid "$bid" '
    (if type == "array" then .[0] else . end) as $i |
    {
      source:       $src,
      source_id:    $sid,
      external_ref: $sid,
      title:        ($i.title // ""),
      body:         ($i.description // ""),
      labels:       ($i.labels // []),
      url:          "",
      state:        ($i.status // "open" | ascii_downcase)
    }'
}

# ───────────────────────────── dispatch ─────────────────────────────

case "$SOURCE" in
  gh)     fetch_gh     "$RAW" ;;
  jira)   fetch_jira   "$RAW" ;;
  monday) fetch_monday "$RAW" ;;
  notion) fetch_notion "$RAW" ;;
  bd)     fetch_bd     "$RAW" ;;
  *)      emit_error "nightshift-ticket-source.sh: unknown source '$SOURCE'" ;;
esac
