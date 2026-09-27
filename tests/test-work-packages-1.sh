#!/usr/bin/env bash
# nightshift-ci-weight: 55
# Part 1 of 2, balanced by measured CI duration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-work-packages.py"
python3 "$ROOT/tests/test-work-packages-review.py"
python3 "$ROOT/tests/test-package-controller.py"
python3 "$ROOT/tests/test-package-convergence-review.py"
python3 "$ROOT/tests/test-package-authoring-review.py"
python3 "$ROOT/tests/test-package-wall-review.py"
python3 "$ROOT/tests/test-package-hardening-review.py"
python3 "$ROOT/tests/test-package-authoring-hardening-review.py"
