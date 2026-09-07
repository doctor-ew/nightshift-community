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

# Preserve a single existing path before parsing quoted comma/space lists.
PARSED=$(python3 - "$INPUT" "$PROJECT" <<'PY'
import pathlib, shlex, sys
value, project = sys.argv[1:]
path = pathlib.Path(value.removeprefix('spec:'))
if not path.is_absolute():
    path = pathlib.Path(project) / path
if path.is_file():
    tokens = [value if value.startswith('spec:') else 'spec:' + value]
else:
    lexer = shlex.shlex(value, posix=True)
    lexer.whitespace += ','
    lexer.whitespace_split = True
    lexer.commenters = ''
    try:
        tokens = list(lexer)
    except ValueError:
        sys.exit(2)
if any('\n' in token or '\r' in token for token in tokens):
    sys.exit(2)
print('\n'.join(tokens))
PY
) || exit 2
TOKENS=()
while IFS= read -r token; do
  [ -z "$token" ] || TOKENS+=("$token")
done <<< "$PARSED"
[ "${#TOKENS[@]}" -gt 0 ] || exit 2
RESULTS=()
for token in "${TOKENS[@]}"; do
  case "$token" in
    gh:*|jira:*|monday:*|notion:*|bd:*|spec:*)
      [ -n "${token#*:}" ] || exit 2
      RESULTS+=("$token")
      ;;
    *)
      if [ -f "$token" ] || [ -f "${PROJECT}/$token" ]; then
        RESULTS+=("spec:$token")
      elif [ -f "${PROJECT}/docs/${token}/SPEC.md" ]; then
        # Existing task keys resume without re-fetching their ticket source.
        RESULTS+=("$token")
      elif command -v bd >/dev/null 2>&1 && bd show "$token" --json >/dev/null 2>&1; then
        # /nightshift-eng treats bare beads as resumes and requires a docs
        # mapping. Prefixing it forces the fresh bd source path instead.
        RESULTS+=("bd:$token")
      else
        exit 2
      fi
      ;;
  esac
done
printf '%s\n' "${RESULTS[@]}"
