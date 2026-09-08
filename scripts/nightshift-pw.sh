#!/usr/bin/env bash
# nightshift-pw.sh — Playwright-aware test runner for the nightshift-* pipeline.
#
# The single primitive behind every Playwright touchpoint (nightshift-implement E2E,
# nightshift-qa gate, nightshift-deploy smoke). It is convention-detected, not configured: if
# the project has no Playwright, every mode no-ops to a PASS so consumers are
# zero-cost on non-Playwright projects.
#
# Usage:
#   nightshift-pw.sh <task-key> --detect
#       → PW_PRESENT: true|false   (and PW_CONFIG / PW_PM on true)
#
#   nightshift-pw.sh <task-key> --run [--grep <pattern>] [--only <glob>] \
#                              [--url <baseURL>] [--cwd <dir>] [--out <file>] [--label <name>]
#       → PW_PASS  | PW_FAIL  | PW_SKIPPED (Playwright absent)
#
# Detection: `@playwright/test` in package.json (deps or devDeps), OR a
#   playwright.config.{ts,js,mjs,cjs} at the project/cwd root.
# Package manager: chosen by lockfile (bun → pnpm → yarn → npm), so the run honors
#   the project's own toolchain. If a `test:e2e` npm script exists it is preferred
#   (the project's declared convention wins).
# baseURL: passed via PLAYWRIGHT_BASE_URL and BASE_URL env so smoke runs can target a
#   live deploy without editing playwright.config.
#
# bash 3.x compatible (macOS default shell).
set -uo pipefail

PROJECT="$(python3 "$(dirname "${BASH_SOURCE[0]}")/nightshift-project-context.py" --root-only)" || exit $?
TASK="${1:-}"; shift || true
[ -z "$TASK" ] && { echo "ERROR: usage: nightshift-pw.sh <task-key> --detect|--run [opts]" >&2; exit 2; }

MODE=""; GREP=""; ONLY=""; URL=""; CWD="$PROJECT"; OUT=""; LABEL="e2e"
while [ $# -gt 0 ]; do
  case "$1" in
    --detect) MODE="detect"; shift ;;
    --run)    MODE="run"; shift ;;
    --grep)   GREP="$2"; shift 2 ;;
    --only)   ONLY="$2"; shift 2 ;;
    --url)    URL="$2"; shift 2 ;;
    --cwd)    CWD="$2"; shift 2 ;;
    --out)    OUT="$2"; shift 2 ;;
    --label)  LABEL="$2"; shift 2 ;;
    *)        shift ;;
  esac
done
[ -z "$MODE" ] && { echo "ERROR: one of --detect or --run is required" >&2; exit 2; }

# Resolve cwd relative to project if a bare relative dir was passed.
case "$CWD" in
  /*) : ;;
  *)  CWD="${PROJECT}/${CWD}" ;;
esac

# ── detection ──────────────────────────────────────────────────────────────
PW_PRESENT="false"; PW_CONFIG=""
PKG="${CWD}/package.json"
if [ -f "$PKG" ] && grep -q '"@playwright/test"' "$PKG" 2>/dev/null; then
  PW_PRESENT="true"
fi
for c in playwright.config.ts playwright.config.js playwright.config.mjs playwright.config.cjs; do
  if [ -f "${CWD}/${c}" ]; then PW_PRESENT="true"; PW_CONFIG="$c"; break; fi
done

# Package manager by lockfile (CoC — the project's toolchain, not ours).
pick_pm() {
  if   [ -f "${CWD}/bun.lockb" ] || [ -f "${CWD}/bun.lock" ]; then echo "bunx" ;
  elif [ -f "${CWD}/pnpm-lock.yaml" ]; then echo "pnpm exec" ;
  elif [ -f "${CWD}/yarn.lock" ]; then echo "yarn" ;
  else echo "npx" ; fi
}
PW_PM="$(pick_pm)"

if [ "$MODE" = "detect" ]; then
  echo "PW_PRESENT: ${PW_PRESENT}"
  [ "$PW_PRESENT" = "true" ] && { echo "PW_PM: ${PW_PM}"; [ -n "$PW_CONFIG" ] && echo "PW_CONFIG: ${PW_CONFIG}"; }
  exit 0
fi

# ── run ────────────────────────────────────────────────────────────────────
if [ "$PW_PRESENT" != "true" ]; then
  echo "PW_SKIPPED: no Playwright detected in ${CWD#$PROJECT/} (no @playwright/test, no playwright.config.*) — treated as PASS."
  exit 0
fi

# Build the command. Prefer the project's declared test:e2e script when present.
HAS_E2E_SCRIPT="false"
if [ -f "$PKG" ] && grep -qE '"test:e2e"[[:space:]]*:' "$PKG" 2>/dev/null && [ -z "$GREP" ] && [ -z "$ONLY" ]; then
  HAS_E2E_SCRIPT="true"
fi

CMD=()
if [ "$HAS_E2E_SCRIPT" = "true" ]; then
  case "$PW_PM" in
    "bunx")      CMD=(bun run test:e2e) ;;
    "pnpm exec") CMD=(pnpm run test:e2e) ;;
    "yarn")      CMD=(yarn test:e2e) ;;
    *)           CMD=(npm run test:e2e) ;;
  esac
else
  # Direct playwright invocation via the project's PM exec.
  # shellcheck disable=SC2206
  CMD=($PW_PM playwright test)
  [ -n "$ONLY" ] && CMD+=("$ONLY")
  [ -n "$GREP" ] && CMD+=(--grep "$GREP")
fi

echo "PW_RUN: (${LABEL}) ${CMD[*]}  [cwd=${CWD#$PROJECT/}]${URL:+  baseURL=$URL}"

LOG="${OUT:-$(mktemp)}"
(
  cd "$CWD" || exit 97
  if [ -n "$URL" ]; then export PLAYWRIGHT_BASE_URL="$URL" BASE_URL="$URL"; fi
  "${CMD[@]}"
) >"$LOG" 2>&1
RC=$?

# Surface a bounded tail so a consumer command can quote evidence without the full dump.
echo "─── playwright output (tail) ───"
tail -n 25 "$LOG" 2>/dev/null
echo "────────────────────────────────"

if [ "$RC" -eq 0 ]; then
  echo "PW_PASS: ${LABEL} suite passed"
else
  echo "PW_FAIL: ${LABEL} suite failed (exit ${RC}). Full output: ${OUT:-$LOG}"
fi
[ -z "$OUT" ] && rm -f "$LOG"
exit "$RC"
