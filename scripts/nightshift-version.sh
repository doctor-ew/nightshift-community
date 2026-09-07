#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ACTION="build"; BUMP=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) PROJECT="${2:?--project requires a path}"; shift 2 ;;
    --build) ACTION="build"; shift ;;
    --bump) ACTION="bump"; BUMP="${2:?--bump requires patch, minor, or major}"; shift 2 ;;
    *) echo "ERROR: unknown argument '$1'" >&2; exit 64 ;;
  esac
done
PROJECT="$(cd "$PROJECT" && pwd)"; VERSION_FILE="$PROJECT/VERSION"
[ -f "$VERSION_FILE" ] || { echo "ERROR: VERSION is required" >&2; exit 66; }
VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
case "$VERSION" in [0-9]*.[0-9]*.[0-9]*) ;; *) echo "ERROR: VERSION must be semantic major.minor.patch" >&2; exit 65 ;; esac
if [ "$ACTION" = "bump" ]; then
  IFS=. read -r MAJOR MINOR PATCH <<< "$VERSION"
  case "$BUMP" in patch) PATCH=$((PATCH + 1)) ;; minor) MINOR=$((MINOR + 1)); PATCH=0 ;; major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;; *) echo "ERROR: --bump requires patch, minor, or major" >&2; exit 64 ;; esac
  printf '%s.%s.%s\n' "$MAJOR" "$MINOR" "$PATCH" > "$VERSION_FILE"
  printf 'VERSION_BUMPED: %s\n' "$(tr -d '[:space:]' < "$VERSION_FILE")"
  exit 0
fi
STAMP="$(git -C "$PROJECT" show -s --format=%cI HEAD 2>/dev/null | sed -E 's/^([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2}):([0-9]{2}).*/\1-\2\3/')"
[ -n "$STAMP" ] || STAMP="$(date -u +%Y-%m-%d-%H%M)"
printf '%s.%s\n' "$VERSION" "$STAMP"
