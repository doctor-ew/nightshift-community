#!/usr/bin/env bash
# nightshift-ci-weight: 90
# Synthetic operation/controller/transport regressions; never live providers.
# Part 4 of 7, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operation-decisions.py"
python3 "$ROOT/tests/test-operation-questions-review.py"
python3 "$ROOT/tests/test-operation-context-review.py"
python3 "$ROOT/tests/test-delivery-composition-review.py"
