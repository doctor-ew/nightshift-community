#!/usr/bin/env bash
# nightshift-ci-weight: 57
# Part 2 of 2, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-package-controller-review.py"
python3 "$ROOT/tests/test-package-authoring.py"
python3 "$ROOT/tests/test-package-acceptance-review.py"
python3 "$ROOT/tests/test-package-composition-window-review.py"
