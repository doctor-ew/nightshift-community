#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 "$root/tests/test-architecture.py"
python3 "$root/tests/test-handoff.py"
python3 "$root/tests/test-pipeline.py"
python3 "$root/tests/test-continue.py"
python3 "$root/tests/test-retained-manifest.py"
python3 "$root/tests/test-console-chat.py"
python3 "$root/tests/test-output.py"
python3 "$root/tests/test-mex-init.py"
python3 "$root/tests/test-init.py"
python3 "$root/tests/test-runtime-home-prompts.py"
python3 "$root/tests/test-isolated-runtime-paths-review.py"
python3 "$root/tests/test-stage-receipt-diagnostics.py"
python3 "$root/tests/test-agent-auth-diagnostics-review.py"
python3 "$root/tests/test-console-continuation.py"
