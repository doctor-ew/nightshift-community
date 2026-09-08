#!/usr/bin/env bash
# nightshift-baseline-check.sh — shared baseline predicate.
#
# Factored out of nightshift-factory.sh so nightshift-preflight-check.sh (and any
# future caller) can run the identical check without duplicating its exact text
# or exit code. Behavior and wording are unchanged from the inline check this
# replaces (see git blame on nightshift-factory.sh for the prior inline form).
#
# Usage: nightshift-baseline-check.sh --project DIR --branch VALUE
#
# `--branch none` never requires an initial commit — it skips isolation
# entirely, so there is nothing to base a worktree on. Any other branch value
# (auto or a name) requires the project to already have at least one commit;
# nightshift creates a worktree/branch from HEAD and cannot do that in an
# empty repository. A project that is not a Git repository at all is only
# valid with --branch none; any other branch value fails the same way an
# empty repository does, since `git rev-parse` has nothing to resolve.
#
# Exit 0: baseline satisfied (or not required for this branch value).
# Exit 66: BASE_MISSING — isolated runs require an initial Git commit.
# Exit 64: usage error.
set -euo pipefail

PROJECT=""
BRANCH=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      [ "$#" -ge 2 ] || { echo "nightshift-baseline-check: missing value for --project" >&2; exit 64; }
      PROJECT="$2"; shift 2 ;;
    --branch)
      [ "$#" -ge 2 ] || { echo "nightshift-baseline-check: missing value for --branch" >&2; exit 64; }
      BRANCH="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: nightshift-baseline-check.sh --project DIR --branch VALUE"
      exit 0 ;;
    *) echo "nightshift-baseline-check: unknown option: $1" >&2; exit 64 ;;
  esac
done

[ -n "$PROJECT" ] || { echo "nightshift-baseline-check: --project is required" >&2; exit 64; }
[ -n "$BRANCH" ] || { echo "nightshift-baseline-check: --branch is required" >&2; exit 64; }

if [ "$BRANCH" != none ] && ! git -C "$PROJECT" rev-parse --verify 'HEAD^{commit}' >/dev/null 2>&1; then
  echo 'nightshift: BASE_MISSING: isolated runs require an initial Git commit. Review and commit the starter files first; no model was started.' >&2
  exit 66
fi
exit 0
