---
name: "INDEX"
description: "Starter task-pattern lookup."
triggers: ["task", "pattern"]
edges: [{"target": "patterns/change-cli-runtime.md", "condition": "Change CLI runtime selectors, defaults, or aliases"}, {"target": "patterns/edit-trajectory-contract.md", "condition": "Change trajectory evidence without weakening replay checks"}, {"target": "patterns/preserve-setup-files.md", "condition": "Preserve private file semantics when editing setup"}, {"target": "patterns/debug-proof-budget.md", "condition": "Diagnose proof admission and counter failures"}, {"target": "patterns/change-release-update.md", "condition": "Change release/update integration while preserving local work"}]
grounds_to: []
last_updated: "2026-09-11"
---

# Pattern Index

| Pattern | Use when |
|---------|----------|
| [change-cli-runtime.md](change-cli-runtime.md) | Change CLI selectors, model defaults, or aliases while preserving input and role routing |
| [change-release-update.md](change-release-update.md) | Change release/update integration while preserving local work |
| [debug-proof-budget.md](debug-proof-budget.md) | Diagnose proof admission and counter failures |
| [edit-trajectory-contract.md](edit-trajectory-contract.md) | Change trajectory evidence without weakening replay checks |
| [preserve-setup-files.md](preserve-setup-files.md) | Preserve private file semantics when editing setup |
