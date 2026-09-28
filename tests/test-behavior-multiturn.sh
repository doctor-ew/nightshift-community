#!/usr/bin/env bash
# nightshift-ci-weight: 8
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 "$ROOT/tests/test-behavior-multiturn.py"
