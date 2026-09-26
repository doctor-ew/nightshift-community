#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/test-work-packages.py"
