#!/usr/bin/env bash
# nightshift-ci-weight: 97
# Synthetic operation/controller/transport regressions; never live providers.
# Part 2 of 4, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operation-decisions.py"
python3 "$ROOT/tests/test-operation-review-regressions.py"
python3 "$ROOT/tests/test-operation-interfaces.py"
python3 "$ROOT/tests/test-operation-installation.py"
python3 "$ROOT/tests/test-operation-supervisor-review.py"
python3 "$ROOT/tests/test-verification-adapters-review.py"
python3 "$ROOT/tests/test-verification-controller-review.py"
python3 "$ROOT/tests/test-delivery-review.py"
python3 "$ROOT/tests/test-delivery-actions-review.py"
