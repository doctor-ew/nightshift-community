#!/usr/bin/env python3
"""Normalize local Markdown requirements without executing their content."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

try:
    path = Path(sys.argv[1].removeprefix("spec:")).resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in (".md", ".markdown"):
        raise ValueError("Markdown file required")
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("maximum size is 1 MiB")
    body = path.read_text(encoding="utf-8")
    if not body.strip():
        raise ValueError("empty input")
    trees = subprocess.check_output(["git", "worktree", "list", "--porcelain"], text=True, stderr=subprocess.PIPE)
    relative = None
    for line in trees.splitlines():
        if line.startswith("worktree "):
            try:
                relative = path.relative_to(Path(line[9:]).resolve()).as_posix()
                break
            except ValueError:
                pass
    if relative is None:
        raise ValueError("input must belong to a project worktree")
    identity = "spec-" + hashlib.sha256(relative.encode()).hexdigest()[:16]
    title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), path.stem)
    print(json.dumps({"source": "spec", "source_id": identity,
                      "external_ref": "spec:" + relative, "title": title,
                      "body": body, "labels": [], "url": "", "state": "open",
                      "source_path": relative,
                      "source_revision": hashlib.sha256(body.encode()).hexdigest()}))
except (OSError, ValueError, subprocess.SubprocessError, IndexError) as error:
    print(json.dumps({"error": "Cannot read project Markdown specification",
                      "reason": type(error).__name__}), file=sys.stderr)
    sys.exit(65)
