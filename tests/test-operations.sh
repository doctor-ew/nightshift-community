#!/usr/bin/env bash
# Synthetic operation/controller/transport regressions; never live providers.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operations.py"
python3 "$ROOT/tests/test-operation-decisions.py"
python3 "$ROOT/tests/test-operation-review-regressions.py"
python3 "$ROOT/tests/test-operation-interfaces.py"
