#!/usr/bin/env bash
# nightshift-ci-weight: 12
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 "$root/tests/test-recovery-independent-review.py"
python3 "$root/tests/test-recovery-decisions.py"
python3 "$root/tests/test-decision-engine.py"
python3 "$root/tests/test-controller-recovery.py"

python3 "$root/tests/test-recovery-acceptance-review.py"
python3 "$root/tests/test-recovery-reviewer-environment.py"
python3 "$root/tests/test-recovery-findings-review.py"
python3 "$root/tests/test-recovery-progress-review.py"
python3 "$root/tests/test-decision-reviewer-schema.py"
python3 "$root/tests/test-reviewer-grounding.py"
python3 "$root/tests/test-reviewer-reuse.py"
python3 "$root/tests/test-deterministic-evidence.py"
python3 "$root/tests/test-operator-escalation.py"
