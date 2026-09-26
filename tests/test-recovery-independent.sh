#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 "$root/tests/test-recovery-independent-review.py"
python3 "$root/tests/test-recovery-decisions.py"
python3 "$root/tests/test-decision-engine.py"
python3 "$root/tests/test-controller-recovery.py"

python3 "$root/tests/test-recovery-acceptance-review.py"
python3 "$root/tests/test-recovery-reviewer-environment.py"
