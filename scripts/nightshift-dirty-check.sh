#!/usr/bin/env bash
# nightshift-dirty-check.sh — report working-tree cleanliness before branch creation.
#
# Used by /nightshift-implement Step 1 to decide whether to offer the worktree menu.
# Outputs exactly one line:
#   DIRTY: 0    clean tree — safe to `git checkout -b` directly
#   DIRTY: N    N uncommitted changes — offer worktree / checkout / stash menu
#
# Fail-open: a non-git dir or any git error reports DIRTY: 0 (never blocks).
COUNT=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
echo "DIRTY: ${COUNT:-0}"
