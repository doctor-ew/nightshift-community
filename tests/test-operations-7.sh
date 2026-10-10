#!/usr/bin/env bash
# nightshift-ci-weight: 90
# Synthetic operation/controller/transport regressions; never live providers.
# Part 7 of 7, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operation-interfaces.py"
python3 "$ROOT/tests/test-operation-supervisor-review.py"
python3 "$ROOT/tests/test-operation-supervisor-admission-review.py"
python3 "$ROOT/tests/test-semantic-cache-review.py"
python3 "$ROOT/tests/test-manual-acceptance-review.py"
python3 "$ROOT/tests/test-operation-reconciliation-review.py"
python3 "$ROOT/tests/test-semantic-provenance-review.py"
