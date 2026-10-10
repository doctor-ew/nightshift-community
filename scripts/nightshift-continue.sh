#!/usr/bin/env bash
# Explicit continuation retains all reservations and call limits.
set -euo pipefail
RUN=false
if [ "${1:-}" = --run ]; then RUN=true; shift; fi
if [ "$#" -eq 0 ] || [ "$1" = --help ]; then
  echo 'Usage: nightshift continue jira:TICKET [--project DIR]'
  echo 'Explicitly grants up to 10 minutes and resumes the retained ticket.'
  exit 0
fi
REF=$1; shift
PROJECT=$PWD
if [ "${1:-}" = --project ] && [ "$#" -eq 2 ]; then PROJECT=$2; shift 2; fi
[ "$#" -eq 0 ] || { echo 'Unexpected continuation arguments' >&2; exit 64; }
case "$REF" in
  jira:*) TASK=${REF#jira:} ;;
  *) echo 'Expected a jira: ticket reference.' >&2; exit 64 ;;
esac
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
TARGET=$(python3 "$SCRIPT_DIR/nightshift-pipeline.py" --project "$PROJECT" --task "$TASK" --continuation-preflight)
python3 "$SCRIPT_DIR/nightshift-ticket-budget.py" continue --project "$TARGET" \
  --task "$TASK" --continuation-seconds 600
if [ "$RUN" = true ]; then
  exec bash "$SCRIPT_DIR/nightshift-factory.sh" "$REF" --project "$PROJECT"
fi
