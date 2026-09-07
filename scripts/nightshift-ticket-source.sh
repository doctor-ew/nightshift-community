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
