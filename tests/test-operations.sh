#!/usr/bin/env bash
# Synthetic operation/controller/transport regressions; never live providers.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-operations.py"
python3 "$ROOT/tests/test-operation-decisions.py"
python3 "$ROOT/tests/test-operation-review-regressions.py"
python3 "$ROOT/tests/test-operation-interfaces.py"
python3 "$ROOT/tests/test-operation-integrated-acceptance.py"
python3 "$ROOT/tests/test-operation-installation.py"
python3 "$ROOT/tests/test-operation-supervisor.py"
python3 "$ROOT/tests/test-operation-supervisor-review.py"
python3 "$ROOT/tests/test-operation-supervisor-admission-review.py"
python3 "$ROOT/tests/test-operation-byte-preservation-review.py"
