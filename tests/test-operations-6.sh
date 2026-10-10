#!/usr/bin/env bash
# nightshift-ci-weight: 89
# Synthetic operation/controller/transport regressions; never live providers.
# Part 6 of 7, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operations.py"
python3 "$ROOT/tests/test-operation-supervisor.py"
python3 "$ROOT/tests/test-semantic-handoffs.py"
python3 "$ROOT/tests/test-package-cancellation-review.py"
python3 "$ROOT/tests/test-operation-hitl-additional-review.py"
python3 "$ROOT/tests/test-owned-process-startup-review.py"
python3 "$ROOT/tests/test-verification-controller-review.py"
python3 "$ROOT/tests/test-delivery-actions-review.py"
