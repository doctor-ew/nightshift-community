#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 "$root/tests/test-architecture.py"
python3 "$root/tests/test-handoff.py"
python3 "$root/tests/test-pipeline.py"
python3 "$root/tests/test-mex-init.py"
python3 "$root/tests/test-init.py"
python3 "$root/tests/test-runtime-home-prompts.py"
python3 "$root/tests/test-isolated-runtime-paths-review.py"
