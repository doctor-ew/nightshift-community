#!/usr/bin/env bash
# Model-free public contract tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-packages.py"
python3 "$ROOT/tests/test-package-contract-review.py"
