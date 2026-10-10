#!/usr/bin/env bash
# Execute each discovered suite literally, independently, and collect all failures.
set -uo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
usage() { echo 'usage: run-tests.sh [--root DIR] [--shard K/N]' >&2; exit 64; }
shard=1/1
while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) [ "$#" -ge 2 ] && [ -d "$2" ] || usage; root=$(cd "$2" && pwd); shift 2 ;;
    --shard) [ "$#" -ge 2 ] || usage; shard=$2; shift 2 ;;
    *) usage ;;
  esac
done
[[ "$shard" =~ ^([1-9][0-9]*)/([1-9][0-9]*)$ ]] || usage
shard_index=${BASH_REMATCH[1]}; shard_count=${BASH_REMATCH[2]}
[ "$shard_index" -le "$shard_count" ] || usage
suites=()
while IFS= read -r -d '' suite; do suites+=("$suite"); done < <(
  for directory in "$root/tests" "$root/evals/unit" "$root/evals/integration"; do
    [ ! -d "$directory" ] || find "$directory" -type f -name 'test-*.sh' -print0
  done | LC_ALL=C sort -z
)
[ "${#suites[@]}" -gt 0 ] || { echo 'FAIL: no test suites discovered' >&2; exit 1; }
# Sharding: a suite may declare its measured duration as "# nightshift-ci-weight: N"
# (tenths of a minute); undeclared suites weigh 1. Heaviest first, each to the
# lightest shard (ties to the lowest shard, then by path), so every shard of the
# same checkout computes the same partition and every suite runs exactly once.
if [ "$shard_count" -gt 1 ]; then
  weighted=()
  for suite in "${suites[@]}"; do
    weight=$(sed -n 's/^# nightshift-ci-weight: \([1-9][0-9]*\)$/\1/p' "$suite" | head -n 1)
    weighted+=("${weight:-1} $suite")
  done
  loads=(); for ((i = 0; i < shard_count; i++)); do loads+=(0); done
  mine=()
  while read -r weight suite; do
    target=0
    for ((i = 1; i < shard_count; i++)); do [ "${loads[i]}" -lt "${loads[target]}" ] && target=$i; done
    loads[target]=$((loads[target] + weight))
    [ "$target" -eq $((shard_index - 1)) ] && mine+=("$suite")
  done < <(printf '%s\n' "${weighted[@]}" | LC_ALL=C sort -k1,1nr -k2,2)
  suites=("${mine[@]+"${mine[@]}"}")
  printf 'Shard %s: %s suites, weight %s\n' "$shard" "${#suites[@]}" "${loads[shard_index - 1]}"
  [ "${#suites[@]}" -gt 0 ] || { echo "Summary: 0 passed, 0 failed, 0 total"; exit 0; }
fi
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
