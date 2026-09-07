#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=evals/lib/assert.sh
source "$ROOT/evals/lib/assert.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-runner-eval.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
RUNNER="$ROOT/evals/run-tests.sh"
if [ ! -f "$RUNNER" ]; then check 'offline suite aggregation capability exists' false; summary; exit 1; fi
mkdir -p "$TMP/root/tests" "$TMP/root/evals/unit" "$TMP/root/evals/integration" "$TMP/empty"
export EVAL_MARKER="$TMP/executed"
printf '#!/usr/bin/env bash\nexit 1\n' > "$TMP/root/tests/test-01-fail.sh"
printf '#!/usr/bin/env bash\nprintf later >> "$EVAL_MARKER"\n' > "$TMP/root/evals/integration/test-99-later.sh"
printf '#!/usr/bin/env bash\nexit 0\n' > "$TMP/root/evals/unit/test-space ; literal.sh"
RC=0; bash "$RUNNER" --root "$TMP/root" > "$TMP/log" 2>&1 || RC=$?
check 'suite failure yields nonzero' test "$RC" -ne 0
check 'later suite still runs' grep -q later "$EVAL_MARKER"
check 'metacharacter filename treated literally' grep -q 'test-space ; literal.sh' "$TMP/log"
printf '#!/usr/bin/env bash\nexit 0\n' > "$TMP/root/tests/test-01-fail.sh"
RC=0; bash "$RUNNER" --root "$TMP/root" > "$TMP/log" 2>&1 || RC=$?
check 'all passing suites succeed' test "$RC" -eq 0
RC=0; bash "$RUNNER" --root "$TMP/empty" > "$TMP/log" 2>&1 || RC=$?
check 'no suites fails closed' test "$RC" -ne 0
summary
