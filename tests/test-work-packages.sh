#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-work-packages.py"
python3 "$ROOT/tests/test-work-packages-review.py"
python3 "$ROOT/tests/test-package-controller.py"
python3 "$ROOT/tests/test-package-controller-review.py"
python3 "$ROOT/tests/test-package-convergence-review.py"
python3 "$ROOT/tests/test-package-authoring.py"
python3 "$ROOT/tests/test-package-authoring-review.py"
python3 "$ROOT/tests/test-package-wall-review.py"
python3 "$ROOT/tests/test-package-hardening-review.py"
python3 "$ROOT/tests/test-package-authoring-hardening-review.py"
python3 "$ROOT/tests/test-package-acceptance-review.py"
python3 "$ROOT/tests/test-package-composition-window-review.py"
