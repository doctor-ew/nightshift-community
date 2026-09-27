#!/usr/bin/env bash
# nightshift-ci-weight: 97
# Synthetic operation/controller/transport regressions; never live providers.
# Part 3 of 4, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operations.py"
python3 "$ROOT/tests/test-semantic-handoffs-review.py"
python3 "$ROOT/tests/test-semantic-cache-review.py"
python3 "$ROOT/tests/test-manual-acceptance-review.py"
python3 "$ROOT/tests/test-operation-questions-review.py"
python3 "$ROOT/tests/test-semantic-provenance-review.py"
python3 "$ROOT/tests/test-owned-process-startup-review.py"
python3 "$ROOT/tests/test-delivery-handoff-adversarial-review.py"
