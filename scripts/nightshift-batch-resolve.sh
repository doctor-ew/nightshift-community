#!/usr/bin/env bash
# nightshift-batch-resolve.sh — classify an explicit batch list and normalize
# bare local Beads IDs into bd:<id> references for a fresh pipeline run.
#
# Usage: nightshift-batch-resolve.sh --input "REF[,REF ...]"
#
# Prints one canonical ticket reference per line. Exits 2 when INPUT is not an
# explicit list, allowing the caller to handle it as a source query.

set -euo pipefail

PROJECT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
INPUT=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --input) INPUT="${2:-}"; shift 2 ;;
    -h|--help)
      echo 'Usage: nightshift-batch-resolve.sh --input "REF[,REF ...]"'
      exit 0
      ;;
    *) echo "ERROR: unknown option: $1" >&2; exit 64 ;;
  esac
done

[ -n "$INPUT" ] || exit 2

# Batch ticket references cannot contain whitespace or commas. Replacing commas
# lets callers use either documented comma lists or shell-friendly whitespace.
read -r -a TOKENS <<< "${INPUT//,/ }"
[ "${#TOKENS[@]}" -gt 0 ] || exit 2

for token in "${TOKENS[@]}"; do
  case "$token" in
    gh:*|jira:*|monday:*|notion:*|bd:*)
      [ "${token#*:}" != "$token" ] || exit 2
      printf '%s\n' "$token"
      ;;
    *)
      if [ -f "${PROJECT}/docs/${token}/SPEC.md" ]; then
        # Existing task keys resume without re-fetching their ticket source.
        printf '%s\n' "$token"
      elif command -v bd >/dev/null 2>&1 && bd show "$token" --json >/dev/null 2>&1; then
        # /nightshift-eng treats bare beads as resumes and requires a docs
        # mapping. Prefixing it forces the fresh bd source path instead.
        printf 'bd:%s\n' "$token"
      else
        exit 2
      fi
      ;;
  esac
done
