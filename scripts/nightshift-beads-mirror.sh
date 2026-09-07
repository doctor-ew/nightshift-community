#!/usr/bin/env bash
# nightshift-beads-mirror.sh — mirror a normalized ticket JSON into beads as the local
# engineering ledger. Idempotent: matches existing beads via the
# `ext:<external_ref>` label. Returns the bead id on stdout.
#
# Usage:
#   nightshift-ticket-source.sh gh:12 | nightshift-beads-mirror.sh
#
# Behavior:
#   - If a bead with label `ext:<external_ref>` exists, prints its id and exits.
#   - Otherwise creates a new bead, tags it with both `ext:<ref>` and
#     `nightshift`, and prints the new id.
#
# Output: a single line `bd-XXXXXXXX`.
# Errors go to stderr as JSON.

set -euo pipefail

emit_error() {
  jq -n --arg msg "$1" '{error: $msg}' >&2
  exit 1
}

if ! command -v bd >/dev/null 2>&1; then
  emit_error "nightshift-beads-mirror.sh: bd not on PATH"
fi
if ! command -v jq >/dev/null 2>&1; then
  emit_error "nightshift-beads-mirror.sh: jq not on PATH"
fi

# Read normalized ticket JSON from stdin. Use `printf '%s'` (not `echo`) when
# re-piping the captured value — on shells where echo interprets backslash
# escapes (POSIX xpg_echo, dash sh), `\n` inside string values gets converted
# to a literal newline, producing invalid JSON. printf %s is escape-safe.
TICKET=$(cat)
if [ -z "$TICKET" ] || ! printf '%s' "$TICKET" | jq empty 2>/dev/null; then
  emit_error "nightshift-beads-mirror.sh: stdin was not valid JSON"
fi

EXT_REF=$(printf   '%s' "$TICKET" | jq -r '.external_ref // empty')
TITLE=$(printf     '%s' "$TICKET" | jq -r '.title // "(untitled)"')
BODY=$(printf      '%s' "$TICKET" | jq -r '.body // ""')
URL=$(printf       '%s' "$TICKET" | jq -r '.url // ""')
SOURCE=$(printf    '%s' "$TICKET" | jq -r '.source // ""')
SOURCE_ID=$(printf '%s' "$TICKET" | jq -r '.source_id // ""')

if [ -z "$EXT_REF" ]; then
  emit_error "nightshift-beads-mirror.sh: ticket JSON missing .external_ref"
fi

# Short-circuit: when the source IS beads, the source_id IS already a bead id.
# Mirroring a bead onto itself would create a duplicate — return the existing
# id without touching the ledger.
if [ "$SOURCE" = "bd" ]; then
  printf '%s\n' "$SOURCE_ID"
  exit 0
fi

EXT_LABEL="ext:${EXT_REF}"

# ───────────────────────── lookup existing bead ─────────────────────────
# bd query supports label filtering; use it to find any open mirror bead.
EXISTING_ID=$(bd query "label=${EXT_LABEL}" --json 2>/dev/null \
  | jq -r '.[0].id // empty' 2>/dev/null || true)

# Body composed for traceability — points back at the source-of-truth ticket.
COMPOSED_BODY=$(printf '%s\n\n---\n**Source:** %s (%s)\n**External ref:** %s\n%s\n' \
  "$BODY" "$SOURCE" "$SOURCE_ID" "$EXT_REF" \
  "$( [ -n "$URL" ] && printf '**URL:** %s' "$URL" || true )")

if [ -n "$EXISTING_ID" ]; then
  # Update existing bead with latest title/body/url so beads stays in sync.
  bd update "$EXISTING_ID" \
    --description "$COMPOSED_BODY" \
    --external-ref "$EXT_REF" \
    >/dev/null 2>&1 || true
  printf '%s\n' "$EXISTING_ID"
  exit 0
fi

# ───────────────────────── create new bead ─────────────────────────
NEW_ID=$(bd create "$TITLE" \
  --description "$COMPOSED_BODY" \
  --external-ref "$EXT_REF" \
  --labels "${EXT_LABEL},nightshift" \
  --json 2>&1 \
  | jq -r '.id // .ID // empty' 2>/dev/null || true)

if [ -z "$NEW_ID" ]; then
  # Fallback: bd q (quick capture) returns just the id.
  NEW_ID=$(bd q "$TITLE" 2>/dev/null | tail -1 | tr -d '[:space:]')
  if [ -n "$NEW_ID" ]; then
    bd update "$NEW_ID" \
      --description "$COMPOSED_BODY" \
      --external-ref "$EXT_REF" \
      --add-label "$EXT_LABEL" \
      --add-label "nightshift" \
      >/dev/null 2>&1 || true
  fi
fi

if [ -z "$NEW_ID" ]; then
  emit_error "nightshift-beads-mirror.sh: bd create succeeded but id could not be parsed"
fi

printf '%s\n' "$NEW_ID"
