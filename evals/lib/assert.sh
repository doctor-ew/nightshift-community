#!/usr/bin/env bash
# Assertions take argv directly; never evaluate a shell command string.
PASS=0 FAIL=0
check() {
  local label="$1"; shift
  if "$@"; then PASS=$((PASS+1)); else printf 'FAIL: %s\n' "$label" >&2; FAIL=$((FAIL+1)); fi
}
summary() { printf 'Assertions: %s passed, %s failed\n' "$PASS" "$FAIL"; [ "$FAIL" -eq 0 ]; }
