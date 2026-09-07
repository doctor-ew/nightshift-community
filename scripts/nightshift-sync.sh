#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; REMOTE="origin"; BRANCH="main"; WORKTREE=""; CHECK_ONLY="false"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) PROJECT="${2:?--project requires a path}"; shift 2 ;;
    --remote) REMOTE="${2:?--remote requires a name}"; shift 2 ;;
    --branch) BRANCH="${2:?--branch requires a name}"; shift 2 ;;
    --worktree) WORKTREE="${2:?--worktree requires a path}"; shift 2 ;;
    --check) CHECK_ONLY="true"; shift ;;
    *) echo "ERROR: unknown argument '$1'" >&2; exit 64 ;;
  esac
done
PROJECT="$(cd "$PROJECT" && pwd)"
git -C "$PROJECT" check-ref-format --branch "$BRANCH" >/dev/null
git -C "$PROJECT" remote get-url "$REMOTE" >/dev/null
git -C "$PROJECT" fetch --quiet "$REMOTE" "$BRANCH"
REF="$REMOTE/$BRANCH"; REMOTE_SHA="$(git -C "$PROJECT" rev-parse "$REF")"
REMOTE_VERSION="$(git -C "$PROJECT" show "$REF:VERSION" 2>/dev/null | tr -d '[:space:]' || true)"
[ -n "$REMOTE_VERSION" ] || {
  if [ "$CHECK_ONLY" = "true" ]; then
    jq -n --arg remote "$REMOTE" --arg branch "$BRANCH" --arg revision "$REMOTE_SHA" \
      '{status: "unversioned", remote: $remote, branch: $branch, revision: $revision}'
    exit 0
  fi
  echo "ERROR: $REF has no VERSION file" >&2
  exit 66
}
STAMP="$(git -C "$PROJECT" show -s --format=%cI "$REF" | sed -E 's/^([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2}):([0-9]{2}).*/\1-\2\3/')"; BUILD_ID="$REMOTE_VERSION.$STAMP"
if [ "$CHECK_ONLY" = "true" ]; then
  jq -n --arg remote "$REMOTE" --arg branch "$BRANCH" --arg revision "$REMOTE_SHA" --arg build "$BUILD_ID" '{status: "update-check", remote: $remote, branch: $branch, revision: $revision, build: $build}'
  exit 0
fi
if [ -z "$WORKTREE" ]; then SAFE_BRANCH="$(printf '%s' "$BRANCH" | tr '/:' '__')"; WORKTREE="$PROJECT/.nightshift-sync/$SAFE_BRANCH"; fi
if [ -e "$WORKTREE" ]; then
  { [ -d "$WORKTREE/.git" ] || [ -f "$WORKTREE/.git" ]; } || { echo "ERROR: sync worktree is not a Git worktree: $WORKTREE" >&2; exit 66; }
  git -C "$WORKTREE" diff --quiet && [ -z "$(git -C "$WORKTREE" ls-files --others --exclude-standard)" ] || { echo "ERROR: refusing to overwrite dirty sync worktree: $WORKTREE" >&2; exit 73; }
  git -C "$WORKTREE" checkout --detach --quiet "$REF"
else
  mkdir -p "$(dirname "$WORKTREE")"; git -C "$PROJECT" worktree add --detach "$WORKTREE" "$REF" >/dev/null
fi
jq -n --arg remote "$REMOTE" --arg branch "$BRANCH" --arg revision "$REMOTE_SHA" --arg build "$BUILD_ID" --arg worktree "$WORKTREE" '{status: "synced", remote: $remote, branch: $branch, revision: $revision, build: $build, worktree: $worktree}'
