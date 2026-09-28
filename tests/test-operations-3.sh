#!/usr/bin/env bash
# nightshift-ci-weight: 89
# Synthetic operation/controller/transport regressions; never live providers.
# Part 3 of 7, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operation-installation.py"
python3 "$ROOT/tests/test-operation-byte-preservation-review.py"
python3 "$ROOT/tests/test-verification-adapters-review.py"
python3 "$ROOT/tests/test-delivery-repair-review.py"
python3 "$ROOT/tests/test-actions-ci-producer.py"
