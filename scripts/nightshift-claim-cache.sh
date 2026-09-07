#!/usr/bin/env bash
# nightshift-claim-cache.sh — content-addressed durable cache for code-fact-extractor results.
#
# Used by /nightshift-product and /nightshift-adversarial to avoid re-running the extractor
# on identical (claim, HEAD_sha, file_targets) tuples across pipeline runs,
# spec re-approvals, and same-project tickets.
#
# Two-tier lookup model (caller's responsibility — this script only operates on
# one cache file at a time):
#   1. Per-task cache — the existing .claude/task-progress/<task-key>-citations.jsonl
#      (nightshift-adversarial already writes/reads it for resume support).
#   2. Shared cache  — .claude/task-progress/.claim-cache.jsonl (default for this
#      script). Project-scoped, append-only, gitignored by default.
#
# Record shape (one per line, append-only JSONL):
#   {
#     "key": "<sha256>",
#     "claim": "<text>",
#     "head_sha": "<sha>",
#     "file_targets": ["a","b"],
#     "inspected_files": ["a","b","c"],
#     "citation": { ... },
#     "ts": "<iso8601>"
#   }
#
# Usage:
#   nightshift-claim-cache.sh hash <claim-json>
#     Input JSON: {"claim":"<text>","head_sha":"<sha>","file_targets":["a","b"]}
#     Output:     64-char hex sha256 on stdout.
#
#   nightshift-claim-cache.sh lookup <key> [--cache <path>]
#     Default cache: $CLAUDE_PROJECT_DIR/.claude/task-progress/.claim-cache.jsonl
#     Output: the matching record's "citation" field as compact JSON, or empty.
#     Exit 0 always; absence == miss.
#
#   nightshift-claim-cache.sh append <key> <record-json> [--cache <path>]
#     Appends the record line to the cache. Idempotent: skips if key already
#     present. Always rewrites the record's "key" field to match the CLI arg.

set -euo pipefail

CMD="${1:-}"
shift || true

resolve_cache_path() {
  local override=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --cache) override="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  if [ -n "$override" ]; then
    printf '%s\n' "$override"
    return
  fi
  local project
  project="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
  local script_dir
  script_dir="$(cd "$(dirname "$0")" && pwd)"
  local state_dir
  state_dir=$(bash "${script_dir}/nightshift-state-dir.sh" --project "$project" --create)
  printf '%s\n' "${state_dir}/.claim-cache.jsonl"
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha256sum | cut -d' ' -f1
  else
    printf '%s' "$1" | shasum -a 256 | cut -d' ' -f1
  fi
}

case "$CMD" in
  hash)
    INPUT="${1:-}"
    if [ -z "$INPUT" ]; then
      echo "Usage: nightshift-claim-cache.sh hash <claim-json>" >&2
      exit 1
    fi
    # Canonical form: claim \n head_sha \n sorted(file_targets) joined by \n.
    # Empty file_targets is fine — yields a trailing newline; still deterministic.
    CANON=$(printf '%s' "$INPUT" | jq -r '
      [
        .claim // "",
        .head_sha // "",
        ((.file_targets // []) | sort | join("\n"))
      ] | join("\n")
    ')
    sha256_of "$CANON"
    ;;

  lookup)
    KEY="${1:-}"
    shift || true
    if [ -z "$KEY" ]; then
      echo "Usage: nightshift-claim-cache.sh lookup <key> [--cache <path>]" >&2
      exit 1
    fi
    CACHE=$(resolve_cache_path "$@")
    if [ ! -f "$CACHE" ]; then
      exit 0
    fi
    # Append-only file: take the last matching record so rewrites win.
    LINE=$(grep -F "\"key\":\"${KEY}\"" "$CACHE" | tail -1 || true)
    if [ -z "$LINE" ]; then
      exit 0
    fi
    printf '%s\n' "$LINE" | jq -c '.citation'
    ;;

  append)
    KEY="${1:-}"
    RECORD="${2:-}"
    shift 2 || true
    if [ -z "$KEY" ] || [ -z "$RECORD" ]; then
      echo "Usage: nightshift-claim-cache.sh append <key> <record-json> [--cache <path>]" >&2
      exit 1
    fi
    CACHE=$(resolve_cache_path "$@")
    mkdir -p "$(dirname "$CACHE")"
    touch "$CACHE"
    if grep -qF "\"key\":\"${KEY}\"" "$CACHE" 2>/dev/null; then
      exit 0
    fi
    printf '%s' "$RECORD" | jq -c --arg k "$KEY" '. + {key: $k}' >> "$CACHE"
    ;;

  invalidate)
    # invalidate <key> [--cache <path>] — drop entries with this key.
    # Used when extractor reports inspected_files outside the cache key's file_targets.
    KEY="${1:-}"
    shift || true
    if [ -z "$KEY" ]; then
      echo "Usage: nightshift-claim-cache.sh invalidate <key> [--cache <path>]" >&2
      exit 1
    fi
    CACHE=$(resolve_cache_path "$@")
    if [ ! -f "$CACHE" ]; then
      exit 0
    fi
    grep -vF "\"key\":\"${KEY}\"" "$CACHE" > "${CACHE}.tmp" || true
    mv "${CACHE}.tmp" "$CACHE"
    ;;

  *)
    echo "Usage: nightshift-claim-cache.sh {hash|lookup|append|invalidate} [args]" >&2
    exit 1
    ;;
esac
