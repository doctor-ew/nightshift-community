#!/usr/bin/env bash
# nightshift-ci-weight: 87
set -euo pipefail
# Part 1 of 2, balanced by measured CI duration.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-package-controller.py"
python3 "$ROOT/tests/test-package-authoring.py"
python3 "$ROOT/tests/test-package-authoring-review.py"
python3 "$ROOT/tests/test-package-acceptance-review.py"
