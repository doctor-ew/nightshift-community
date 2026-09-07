#!/usr/bin/env bash
# nightshift-capability.sh — probe and cache which optional tools are available.
#
# nightshift requires almost nothing. Every tool below is optional; the pipeline
# degrades to a documented fallback when one is absent. This script is the single
# place that decides "is X usable here", so no command or agent has to re-probe.
#
# Usage:
#   bash nightshift-capability.sh                 # probe (honors cache), print KEY="value" lines
#   bash nightshift-capability.sh --refresh       # ignore cache, re-probe
#   bash nightshift-capability.sh --has <tool>    # exit 0 if available, 1 if not (no output)
#   bash nightshift-capability.sh --which <tool>  # print the resolved command, empty if absent
#   . "$(dirname "$0")/nightshift-capability.sh"  # NOT sourceable — call it, then eval the output
#
# Cache: $NIGHTSHIFT_CACHE_DIR/capabilities (default ~/.nightshift/capabilities), TTL 24h.
# Output is safe to `eval`.
#
# Deliberately NOT set -euo pipefail: probes must be allowed to fail.

CACHE_DIR="${NIGHTSHIFT_CACHE_DIR:-$HOME/.nightshift}"
CACHE_FILE="$CACHE_DIR/capabilities"
TTL=86400

REFRESH="no"; QUERY=""; QMODE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --refresh) REFRESH="yes" ;;
    --has)     QMODE="has";   shift; QUERY="${1:-}" ;;
    --which)   QMODE="which"; shift; QUERY="${1:-}" ;;
    -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "nightshift-capability: unknown flag: $1" >&2; exit 64 ;;
  esac
  shift
done

# ── cache read ───────────────────────────────────────────────────────────────
_fresh="no"
if [ "$REFRESH" = "no" ] && [ -f "$CACHE_FILE" ]; then
  _t=$(grep '^NIGHTSHIFT_PROBE_TIME=' "$CACHE_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"')
  if [ -n "$_t" ] && [ $(( $(date +%s) - _t )) -lt "$TTL" ]; then
    _fresh="yes"
  fi
fi

# ── probe ────────────────────────────────────────────────────────────────────
if [ "$_fresh" = "no" ]; then
  mkdir -p "$CACHE_DIR" 2>/dev/null

  # Tool -> capability key. Presence on PATH is necessary but not always sufficient;
  # where a tool can be present-but-unusable we probe behavior, not just existence.
  NIGHTSHIFT_BD=""
  if command -v bd >/dev/null 2>&1 && bd --version >/dev/null 2>&1; then NIGHTSHIFT_BD="$(command -v bd)"; fi

  NIGHTSHIFT_MEX=""
  if command -v mex >/dev/null 2>&1; then NIGHTSHIFT_MEX="$(command -v mex)"; fi

  NIGHTSHIFT_GH=""
  if command -v gh >/dev/null 2>&1; then NIGHTSHIFT_GH="$(command -v gh)"; fi
  NIGHTSHIFT_GH_AUTH="no"
  if [ -n "$NIGHTSHIFT_GH" ] && gh auth status >/dev/null 2>&1; then NIGHTSHIFT_GH_AUTH="yes"; fi

  NIGHTSHIFT_JQ=""
  if command -v jq >/dev/null 2>&1; then NIGHTSHIFT_JQ="$(command -v jq)"; fi

  NIGHTSHIFT_CLAUDE=""
  if command -v claude >/dev/null 2>&1; then NIGHTSHIFT_CLAUDE="$(command -v claude)"; fi

  NIGHTSHIFT_CODEX=""
  if command -v codex >/dev/null 2>&1; then NIGHTSHIFT_CODEX="$(command -v codex)"; fi

  NIGHTSHIFT_OLLAMA=""
  if command -v ollama >/dev/null 2>&1 && ollama list >/dev/null 2>&1; then
    NIGHTSHIFT_OLLAMA="$(command -v ollama)"
  fi

  NIGHTSHIFT_PYTHON3=""
  if python3 -c 'import sys; sys.exit(0 if sys.version_info.major==3 else 1)' >/dev/null 2>&1; then
    NIGHTSHIFT_PYTHON3="python3"
  fi

  umask 077
  {
    echo "# nightshift capability cache — regenerate with nightshift-capability.sh --refresh"
    echo "NIGHTSHIFT_PROBE_TIME=\"$(date +%s)\""
    echo "NIGHTSHIFT_BD=\"$NIGHTSHIFT_BD\""
    echo "NIGHTSHIFT_MEX=\"$NIGHTSHIFT_MEX\""
    echo "NIGHTSHIFT_GH=\"$NIGHTSHIFT_GH\""
    echo "NIGHTSHIFT_GH_AUTH=\"$NIGHTSHIFT_GH_AUTH\""
    echo "NIGHTSHIFT_JQ=\"$NIGHTSHIFT_JQ\""
    echo "NIGHTSHIFT_CLAUDE=\"$NIGHTSHIFT_CLAUDE\""
    echo "NIGHTSHIFT_CODEX=\"$NIGHTSHIFT_CODEX\""
    echo "NIGHTSHIFT_OLLAMA=\"$NIGHTSHIFT_OLLAMA\""
    echo "NIGHTSHIFT_PYTHON3=\"$NIGHTSHIFT_PYTHON3\""
  } > "$CACHE_FILE"
fi

# ── query modes ──────────────────────────────────────────────────────────────
_key_for() {
  case "$1" in
    bd)        echo NIGHTSHIFT_BD ;;
    mex)       echo NIGHTSHIFT_MEX ;;
    gh)        echo NIGHTSHIFT_GH ;;
    gh-auth)   echo NIGHTSHIFT_GH_AUTH ;;
    jq)        echo NIGHTSHIFT_JQ ;;
    claude)    echo NIGHTSHIFT_CLAUDE ;;
    codex)     echo NIGHTSHIFT_CODEX ;;
    ollama)    echo NIGHTSHIFT_OLLAMA ;;
    python3)   echo NIGHTSHIFT_PYTHON3 ;;
    *)         echo "" ;;
  esac
}

if [ -n "$QMODE" ]; then
  KEY=$(_key_for "$QUERY")
  if [ -z "$KEY" ]; then
    echo "nightshift-capability: unknown tool: $QUERY" >&2
    exit 64
  fi
  VAL=$(grep "^$KEY=" "$CACHE_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"')
  case "$QMODE" in
    has)   [ -n "$VAL" ] && [ "$VAL" != "no" ] && exit 0 || exit 1 ;;
    which) printf '%s\n' "$VAL"; exit 0 ;;
  esac
fi

grep -v '^#' "$CACHE_FILE" 2>/dev/null
