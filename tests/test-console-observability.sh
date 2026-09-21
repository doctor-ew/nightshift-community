#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for suite in console-chat console-progress routing-path decomposition; do
  python3 "$ROOT/tests/test-$suite.py"
done
