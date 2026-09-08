#!/usr/bin/env bash
# nightshift-triage.sh — apply universal quality gates to a set of candidate tickets and
# write a triage report. Source-agnostic: the input is normalized ticket JSON, so it
# works for any source (jira/gh/monday/notion) that the caller has already fetched.
#
# Usage:
#   nightshift-triage.sh --n <count> --query "<source query>" --input <json_file>
#
# Input JSON shape (the shape nightshift-ticket-source.sh / an MCP search produces):
#   { "issues": [ { "key": "MVP-1", "fields": { "summary": "...", "description": "..." } } ] }
#
# Outputs:
#   - Triage markdown → .claude/task-progress/triage-YYYYMMDD-HHMM.md
#   - Passing ticket keys printed one per line to stdout (the batch list)
#   - Exit 0 if >= 1 passing ticket; exit 2 if 0 passing tickets
#
# The gates are keyword heuristics — they pre-filter work that an unattended batch run
# should NOT auto-implement (design-heavy, security-sensitive, integration-coupled).
# Manual review of the passing set is still recommended.
set -euo pipefail

PROJECT="$(python3 "$(dirname "${BASH_SOURCE[0]}")/nightshift-project-context.py" --root-only)" || exit $?
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT" --create)
N=5
QUERY=""
INPUT_FILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --n)     N="$2"; shift 2 ;;
    --query) QUERY="$2"; shift 2 ;;
    --jql)   QUERY="$2"; shift 2 ;;   # alias
    --input) INPUT_FILE="$2"; shift 2 ;;
    *)       shift ;;
  esac
done

if [ "$N" -gt 50 ]; then
  echo "WARN: --n capped at 50 (requested $N)" >&2
  N=50
fi

[ -z "$INPUT_FILE" ] && { echo "ERROR: --input required" >&2; exit 1; }
[ ! -f "$INPUT_FILE" ] && { echo "ERROR: input file not found: $INPUT_FILE" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq required but not installed" >&2; exit 1; }

TIMESTAMP=$(date -u +"%Y%m%d-%H%M")
OUTPUT_FILE="${STATE_DIR}/triage-${TIMESTAMP}.md"

PASSING_KEYS=()
EXCLUDED_ROWS=()
PASSING_ROWS=()
TOTAL=$(jq '.issues | length' "$INPUT_FILE" 2>/dev/null || echo 0)

for i in $(seq 0 $((TOTAL - 1))); do
  KEY=$(jq -r ".issues[$i].key // empty" "$INPUT_FILE")
  SUMMARY=$(jq -r ".issues[$i].fields.summary // empty" "$INPUT_FILE")
  DESC=$(jq -r ".issues[$i].fields.description // empty" "$INPUT_FILE")
  [ -z "$KEY" ] && continue

  GATE_FAIL=""; FAIL_REASON=""

  # G1: Description >= 20 words
  WORD_COUNT=$(echo "$DESC" | wc -w | tr -d ' ')
  if [ "$WORD_COUNT" -lt 20 ]; then
    GATE_FAIL="G1"; FAIL_REASON="description < 20 words ($WORD_COUNT)"
  fi
  # G2: Action-oriented language
  if [ -z "$GATE_FAIL" ] && ! echo "$DESC" | grep -qiE 'fix|add|update|prevent|implement|build|create|remove|migrate|refactor'; then
    GATE_FAIL="G2"; FAIL_REASON="no action-oriented language detected"
  fi
  # G3: No UX design required
  if [ -z "$GATE_FAIL" ] && echo "$DESC" | grep -qiE 'wireframe|mockup|redesign|prototype|design review|figma'; then
    GATE_FAIL="G3"; FAIL_REASON="UX design language detected"
  fi
  # G4: No external integration dependency
  if [ -z "$GATE_FAIL" ] && echo "$DESC" | grep -qiE 'third.party|webhook|oauth|api key|api token|integration with|salesforce|stripe|twilio'; then
    GATE_FAIL="G4"; FAIL_REASON="external integration dependency detected"
  fi
  # G5: Not security-sensitive
  if [ -z "$GATE_FAIL" ] && echo "$DESC" | grep -qiE 'auth|encrypt|pii|payment|credential|secret|token|password|ssn|hipaa'; then
    GATE_FAIL="G5"; FAIL_REASON="security-sensitive language detected"
  fi

  SAFE_SUMMARY="${SUMMARY:0:60}"
  if [ -z "$GATE_FAIL" ]; then
    PASSING_KEYS+=("$KEY")
    PASSING_ROWS+=("| ${#PASSING_KEYS[@]} | $KEY | $SAFE_SUMMARY | PASS | PASS | PASS | PASS | PASS |")
    echo "$KEY"
  else
    EXCLUDED_ROWS+=("| $KEY | $SAFE_SUMMARY | $GATE_FAIL | $FAIL_REASON |")
  fi
done

PASS_COUNT=${#PASSING_KEYS[@]}

{
  echo "# Triage Run — ${TIMESTAMP}"
  echo ""
  echo "**Query:** \`${QUERY}\`"
  echo "**Fetched:** ${TOTAL} tickets"
  echo "**Passing:** ${PASS_COUNT} tickets"
  echo "**Run by:** nightshift-triage.sh"
  echo ""
  echo "> Gate results are keyword heuristics. Review the passing set before committing to an unattended batch."
  echo ""
  echo "## Passing Tickets (ordered)"
  echo ""
  echo "| # | Key | Summary | G1 | G2 | G3 | G4 | G5 |"
  echo "|---|-----|---------|----|----|----|----|-----|"
  if [ ${#PASSING_ROWS[@]} -eq 0 ]; then
    echo "| — | — | No tickets passed all gates | — | — | — | — | — |"
  else
    for row in "${PASSING_ROWS[@]}"; do echo "$row"; done
  fi
  echo ""
  echo "## Excluded Tickets"
  echo ""
  echo "| Key | Summary | Gate Failed | Reason |"
  echo "|-----|---------|-------------|--------|"
  if [ ${#EXCLUDED_ROWS[@]} -eq 0 ]; then
    echo "| — | — | — | All tickets passed |"
  else
    for row in "${EXCLUDED_ROWS[@]}"; do echo "$row"; done
  fi
} > "$OUTPUT_FILE"

echo "TRIAGE_OUTPUT: ${OUTPUT_FILE#$PROJECT/}" >&2
echo "TRIAGE_PASSING: $PASS_COUNT / $TOTAL" >&2

[ "$PASS_COUNT" -eq 0 ] && exit 2
exit 0
