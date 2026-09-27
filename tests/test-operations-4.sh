#!/usr/bin/env bash
# nightshift-ci-weight: 97
# Synthetic operation/controller/transport regressions; never live providers.
# Part 4 of 4, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operation-integrated-acceptance.py"
python3 "$ROOT/tests/test-operation-context-review.py"
python3 "$ROOT/tests/test-semantic-transport-review.py"
python3 "$ROOT/tests/test-delivery-handoff-review.py"
python3 "$ROOT/tests/test-delivery-repair-review.py"
python3 "$ROOT/tests/test-actions-ci-producer.py"
python3 "$ROOT/tests/test-delivery-actions-integration.py"
