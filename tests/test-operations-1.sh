#!/usr/bin/env bash
# nightshift-ci-weight: 91
# Synthetic operation/controller/transport regressions; never live providers.
# Part 1 of 7, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-delivery-review.py"
