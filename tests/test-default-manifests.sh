#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python3 - "$ROOT" <<'PY'
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('published_defaults', root/'scripts/nightshift-behavior-proof.py')
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)
keys = ('development_calls', 'final_calls', 'repairs', 'infrastructure_failures')
for name in ('.nightshift.toml', 'nightshift.toml'):
    content = subprocess.check_output(['git', '-C', str(root), 'show', 'HEAD:'+name], text=True)
    data = tomllib.loads(content)
    assert all(value == 0 for value in data['repair_budgets'].values()), name+' publishes finite default repairs'
    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary)
        (project/name).write_text(content)
        policy = proof.config(project)
        assert all(policy[key] is None for key in keys), (name, policy)
with tempfile.TemporaryDirectory() as temporary:
    project = Path(temporary)
    (project/'.nightshift.toml').write_text('[behavior_proof]\nversion=1\ndevelopment_calls=11\nfinal_calls=7\nrepairs=5\ninfrastructure_failures=6\n')
    policy = proof.config(project)
    assert [policy[key] for key in keys] == [11, 7, 5, 6], policy
print('PASS: both published manifests have unlimited defaults; explicit operator limits remain enforced')
PY
