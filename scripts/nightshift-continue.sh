#!/usr/bin/env bash
# Explicitly grant one bounded continuation; retain all reservations and call limits.
set -euo pipefail
if [ "$#" -ne 1 ] || [ "$1" = --help ]; then
  echo 'Usage: nightshift-continue.sh jira:TICKET'
  echo 'Grants up to 10 additional minutes in the current repository. Does not start a model.'
  exit 0
fi
case "$1" in
  jira:*) task=${1#jira:} ;;
  *) echo 'Expected a jira: ticket reference.' >&2; exit 64 ;;
esac
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
exec python3 "$SCRIPT_DIR/nightshift-ticket-budget.py" continue --project "$PWD" \
  --task "$task" --continuation-seconds 600
