#!/usr/bin/env bash
# nightshift-spec-guardrail.sh — PreToolUse hook for Write/Edit that blocks any spec from
# landing without a verified `## Sources` section and a filled `## Model Router`.
#
# Activation:
#   Fires only on Write/Edit whose file_path matches `**/docs/*/SPEC.md`.
#   All other tool calls are approved silently.
#
# Validation rules:
#   1. The full spec content must contain a `## Sources` section with at least
#      one entry matching:  `path/to/file:LINE` ... commit: <sha>
#   2. The full spec content must contain a `## Model Router` section with a
#      `**Decision:**` line whose value is NOT an empty bracket placeholder.
#
# Hook input (stdin, JSON from Claude Code):
#   { "tool_name": "Write"|"Edit", "tool_input": { "file_path": "...", ... } }
#
# Decision contract (stdout JSON):
#   { "decision": "approve" }
#   { "decision": "block", "reason": "..." }
#
# Exit code 0 always — Claude Code reads decision from JSON.

set -euo pipefail

# Read hook input from stdin BEFORE handing off to python (the heredoc would
# otherwise consume stdin and python's sys.stdin.read() would be empty).
INPUT=$(cat)

# All validation logic lives in python — pass INPUT as argv to avoid the
# stdin-collision pitfall. The python source itself comes via heredoc.
exec python3 -c '
import json, os, re, sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print(json.dumps({"decision": "approve"}))
    sys.exit(0)

tool = data.get("tool_name")
ti = data.get("tool_input") or {}
fp = ti.get("file_path", "")

if tool not in ("Write", "Edit"):
    print(json.dumps({"decision": "approve"}))
    sys.exit(0)

if not re.search(r"/docs/[^/]+/SPEC\.md$", fp):
    print(json.dumps({"decision": "approve"}))
    sys.exit(0)

# Reconstruct the full content that WILL exist after this tool call.
if tool == "Write":
    content = ti.get("content", "")
else:  # Edit
    if not os.path.exists(fp):
        print(json.dumps({"decision": "approve"}))
        sys.exit(0)
    with open(fp) as f:
        existing = f.read()
    old = ti.get("old_string", "")
    new = ti.get("new_string", "")
    if ti.get("replace_all"):
        content = existing.replace(old, new)
    else:
        content = existing.replace(old, new, 1)

problems = []

# Rule 1: ## Sources must exist with a valid entry
sm = re.search(r"^## Sources\s*\n(.+?)(?=\n## |\Z)", content, re.MULTILINE | re.DOTALL)
if not sm:
    problems.append(
        "Missing ## Sources section. Every spec must end with a ## Sources "
        "section listing every file read to support a factual claim."
    )
else:
    body = sm.group(1)
    valid = re.search(
        r"`?[\w/\.\-]+\.[\w]+:\d+(?:-\d+)?`?.*?commit[:\s]+\w+",
        body, re.IGNORECASE
    )
    if not valid:
        problems.append(
            "## Sources section has no valid entries. Each entry must include "
            "`path/to/file.ext:LINE_START-LINE_END` and a commit SHA. "
            "Example: `src/foo.ts:12-30` (branch: main, commit: abc1234) — what this confirms"
        )

# Rule 2: ## Model Router must exist with a non-placeholder Decision
rm_ = re.search(r"^## Model Router\s*\n(.+?)(?=\n## |\Z)", content, re.MULTILINE | re.DOTALL)
if not rm_:
    problems.append(
        "Missing ## Model Router section. Every spec must include a Model Router "
        "with a filled **Decision:** line."
    )
else:
    body = rm_.group(1)
    dm = re.search(r"\*\*Decision:\*\*\s*(.+)", body)
    if not dm:
        problems.append(
            "## Model Router has no **Decision:** line. Add: "
            "`**Decision:** Sonnet / General Engineer` (or Opus / Enterprise Architect)."
        )
    else:
        val = dm.group(1).strip()
        if re.fullmatch(r"\[\s*[\w\s/]*\s*\]", val):
            problems.append(
                f"## Model Router **Decision:** is a bracket placeholder "
                f"(`{val}`). Replace with a filled value, e.g., "
                f"`**Decision:** Sonnet / General Engineer`."
            )
        elif not val:
            problems.append("## Model Router **Decision:** value is empty.")

if problems:
    bullets = "\n".join(f"- {p}" for p in problems)
    reason = (
        "spec-guardrail blocked SPEC.md write — fix these issues:\n\n"
        f"{bullets}\n\n"
        "To skip this check (not recommended), temporarily disable the hook "
        "in ~/.claude/settings.json."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
else:
    print(json.dumps({"decision": "approve"}))
' "$INPUT"
