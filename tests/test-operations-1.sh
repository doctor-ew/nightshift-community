#!/usr/bin/env bash
# nightshift-ci-weight: 97
# Synthetic operation/controller/transport regressions; never live providers.
# Part 1 of 4, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operation-supervisor.py"
python3 "$ROOT/tests/test-operation-supervisor-admission-review.py"
python3 "$ROOT/tests/test-operation-byte-preservation-review.py"
python3 "$ROOT/tests/test-semantic-handoffs.py"
python3 "$ROOT/tests/test-operation-reconciliation-review.py"
python3 "$ROOT/tests/test-package-cancellation-review.py"
python3 "$ROOT/tests/test-operation-hitl-additional-review.py"
python3 "$ROOT/tests/test-delivery-composition-review.py"
