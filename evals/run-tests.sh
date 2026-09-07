#!/usr/bin/env bash
# Execute each discovered suite literally, independently, and collect all failures.
set -uo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
if [ "$#" -gt 0 ]; then
  if [ "$#" -ne 2 ] || [ "$1" != --root ] || [ ! -d "$2" ]; then
    echo 'usage: run-tests.sh [--root DIR]' >&2; exit 64
  fi
  root=$(cd "$2" && pwd)
fi
suites=()
while IFS= read -r -d '' suite; do suites+=("$suite"); done < <(
  for directory in "$root/tests" "$root/evals/unit" "$root/evals/integration"; do
    [ ! -d "$directory" ] || find "$directory" -type f -name 'test-*.sh' -print0
  done | LC_ALL=C sort -z
)
[ "${#suites[@]}" -gt 0 ] || { echo 'FAIL: no test suites discovered' >&2; exit 1; }
passed=0; failed=0
for suite in "${suites[@]}"; do
  printf '\nRUN %s\n' "$suite"
  if bash "$suite"; then
    printf 'PASS %s\n' "$suite"; passed=$((passed + 1))
  else
    result=$?; printf 'FAIL %s (exit %s)\n' "$suite" "$result"; failed=$((failed + 1))
  fi
done
printf '\nSummary: %s passed, %s failed, %s total\n' "$passed" "$failed" "${#suites[@]}"
[ "$failed" -eq 0 ]
