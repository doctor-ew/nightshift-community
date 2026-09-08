#!/usr/bin/env bash
# nightshift-citations-trim.sh — project the full citations JSONL to a trimmed schema that
# the implementation agent reads during planning, so it pays for claim + location +
# risk, not the full challenge/override prose.
#
# Trimmed schema: id, claim, status, source.{file,line}, risk_level
# Dropped: challenge, override_reasoning, cache_key, cache_origin, inspected_files
#
# Usage: nightshift-citations-trim.sh <task-key>
# Idempotent: re-running overwrites the trim file in place. Silent exit 0 if the
# source citation file is absent.
set -uo pipefail

PROJECT="$(python3 "$(dirname "${BASH_SOURCE[0]}")/nightshift-project-context.py" --root-only)" || exit $?
TASK="${1:-}"
[ -z "$TASK" ] && { echo "[nightshift] WARNING: nightshift-citations-trim.sh — no task-key passed"; exit 0; }
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR=$(bash "${SCRIPT_DIR}/nightshift-state-dir.sh" --project "$PROJECT" --task "$TASK" --create)

FULL="${STATE_DIR}/${TASK}-citations.jsonl"
TRIM="${STATE_DIR}/${TASK}-citations-trim.jsonl"

[ -f "$FULL" ] || exit 0

N=$(python3 - "$FULL" "$TRIM" << 'PYEOF'
import json, sys

full_path, trim_path = sys.argv[1], sys.argv[2]
count = 0
with open(full_path) as f_in, open(trim_path, "w") as f_out:
    for idx, line in enumerate(f_in, start=1):
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        src = entry.get("source") or {}
        trimmed = {
            "id": idx,
            "claim": entry.get("claim", ""),
            "status": entry.get("status", ""),
            "source": {
                "file": src.get("file") if isinstance(src, dict) else None,
                "line": src.get("line") if isinstance(src, dict) else None,
            },
            "risk_level": entry.get("risk_level"),
        }
        f_out.write(json.dumps(trimmed) + "\n")
        count += 1
print(count)
PYEOF
)
echo "[nightshift] Citations trimmed: ${TRIM#$PROJECT/} (${N} entries)"
