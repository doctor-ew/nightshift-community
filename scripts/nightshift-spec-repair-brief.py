#!/usr/bin/env python3
"""Require a current, focused repair brief before rewriting an existing draft."""
import argparse
import hashlib
import json
from pathlib import Path


def brief(directory):
    directory = Path(directory)
    spec = directory / 'SPEC.md'
    if not spec.exists():
        return ''
    path = directory / 'spec-repair.json'
    if not path.is_file():
        raise ValueError('Existing draft: reuse it for validation/review. A writer requires spec-repair.json with current spec_sha256 and concrete findings; do not ask the operator to regenerate.')
    if spec.is_symlink() or path.is_symlink() or path.stat().st_size > 32768:
        raise ValueError('Unsafe or oversized spec repair brief')
    value = json.loads(path.read_text())
    if set(value) != {'spec_sha256', 'findings'} or value['spec_sha256'] != hashlib.sha256(spec.read_bytes()).hexdigest():
        raise ValueError('Repair brief must bind the current draft')
    findings = value['findings']
    if not isinstance(findings, list) or not 1 <= len(findings) <= 20:
        raise ValueError('Repair requires 1..20 concrete findings')
    ids = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {'id', 'target', 'problem'}:
            raise ValueError('Each finding requires id, target and problem')
        if any(not isinstance(v,str) or not v.strip() or len(v)>4000 for v in finding.values()) or finding['id'] in ids:
            raise ValueError('Findings must be nonempty and uniquely identified')
        ids.add(finding['id'])
    return ('Repair the existing draft only for these retained findings. Preserve unaffected sections, '
            'recorded decisions and acceptance criteria. Do not repeat discovery or rewrite the full specification. '
            'This brief is scope, not approval.\n' + json.dumps(value, ensure_ascii=False))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True)
    args=parser.parse_args()
    try: print(brief(args.directory))
    except (OSError,ValueError,TypeError) as error: parser.exit(65, str(error)+'\n')
