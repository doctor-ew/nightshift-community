#!/usr/bin/env bash
# nightshift-ci-weight: 87
set -euo pipefail
# Part 2 of 2, balanced by measured CI duration.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-work-packages.py"
python3 "$ROOT/tests/test-work-packages-review.py"
python3 "$ROOT/tests/test-package-controller-review.py"
python3 "$ROOT/tests/test-package-convergence-review.py"
python3 "$ROOT/tests/test-package-wall-review.py"
python3 "$ROOT/tests/test-package-hardening-review.py"
python3 "$ROOT/tests/test-package-authoring-hardening-review.py"
python3 "$ROOT/tests/test-package-composition-window-review.py"
