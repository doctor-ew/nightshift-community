#!/usr/bin/env python3
"""Conservative source-review reuse bound to current workspace and review policy."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fingerprint(arguments, directory, state, routing):
    # Legacy callers without a readable request cannot reuse a report.
    if '--in' not in arguments:
        return None
    source = Path(arguments[arguments.index('--in') + 1]).resolve()
    project = Path.cwd().resolve()
    try:
        top = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], stderr=subprocess.DEVNULL).decode().strip()
        if Path(top).resolve() != project:
            return None
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
        paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'])
        excluded = {source, Path(arguments[arguments.index('--out') + 1]).resolve()}
        for row in state.get('review_requests', {}).values():
            excluded.update(Path(row[k]) for k in ('output', 'retained'))
        excluded |= {Path(str(p) + '.retry.json') for p in list(excluded)}
        hashes = []
        size = 0
        for name in sorted(set(paths.decode().split('\0')) - {''}):
            path = project / name
            if path in excluded:
                continue
            if path.parent == directory and (path.name.startswith('.adversarial-') or path.name in
                    ('repair-admission.json', 'repair-check.receipt.json', 'review-reuse.json', 'review-convergence.json')):
                continue
            # Symlinks and submodules require fresh review; never reuse incomplete evidence.
            if path.is_symlink() or (path.exists() and not path.is_file()):
                return None
            if not path.exists():
                hashes.append((name, 'deleted'))
                continue
            size += path.stat().st_size
            if size > 64 * 1024 * 1024 or len(hashes) >= 10000:
                return None
            hashes.append((name, digest(path.read_bytes())))
        options = []
        skip = False
        for arg in arguments:
            if skip:
                skip = False
                continue
            if arg in ('--in', '--out', '--attempt'):
                skip = True
            else:
                options.append(arg)
        runtime = Path(__file__).resolve().parent.parent
        assets = ['scripts/nightshift-agent.sh', 'scripts/nightshift-provider-policy.py',
                  'agents/nightshift-code-fact-extractor.md', 'contracts/nightshift-code-fact-extractor.schema.json',
                  'scripts/nightshift-contract.jq']
        payload = dict(version=1, head=head, input=digest(source.read_bytes()), files=hashes,
                       options=options, routing=digest(routing.read_bytes()),
                       policy=subprocess.check_output(['python3', str(runtime / 'scripts/nightshift-provider-policy.py'), 'mode'], stderr=subprocess.DEVNULL).decode().strip(),
                       assets={p:digest((runtime / p).read_bytes()) for p in assets})
        return digest(json.dumps(payload, sort_keys=True).encode())
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return None


def candidate(state, signature):
    if signature is None:
        return None
    for identity, row in reversed(list(state.get('review_requests', {}).items())):
        if row['signature'] != signature:
            continue
        category = state['attempts'].get(identity)
        if category not in ('success', 'substantive'):
            continue
        path = Path(row['retained'])
        if not path.is_file() or digest(path.read_bytes()) != row.get('report_sha256'):
            continue
        record = json.loads(path.read_text())
        if category == 'success':
            # Reuse positive file evidence only. Negative searches and incomplete
            # dependency reports must be reviewed afresh.
            claims = record.get('results', {}).get('claims', [])
            known = set(subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard']).decode().split('\0'))
            if record.get('status') != 'SUCCESS' or not claims or any(c.get('status') != 'VERIFIED' or not c.get('inspected_files')
                                 or not set(c['inspected_files']) <= known for c in claims):
                continue
        return identity, row, category
    return None


def recurring_findings(state):
    """Detect repeated explicit conflicts without mistaking NEW/NOT_FOUND for failure."""
    seen = {}
    for identity, row in state.get('review_requests', {}).items():
        if state['attempts'].get(identity) != 'substantive':
            continue
        path = Path(row['retained'])
        if not path.is_file() or digest(path.read_bytes()) != row.get('report_sha256'):
            continue
        for claim in json.loads(path.read_text()).get('results', {}).get('claims', []):
            if claim.get('status') != 'CONFLICT':
                continue
            key = (' '.join(claim.get('claim', '').split()).casefold(), claim.get('file', ''))
            if not key[0]:
                continue
            seen.setdefault(key, set()).add(identity)
    return [dict(claim=key[0], file=key[1], attempts=sorted(attempts))
            for key, attempts in seen.items() if len(attempts) > 1]
