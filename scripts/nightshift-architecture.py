#!/usr/bin/env python3
"""Operator-accepted project constraints, shared across ticket worktrees."""
import argparse
import fnmatch
import hashlib
import importlib.util
import json
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('decisions', HERE/'nightshift-console-decisions.py')
decisions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decisions)


def location(project):
    return decisions.location(project, 'architecture').parent.parent/'architecture.json'


def read(project):
    common = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--git-common-dir'], text=True).strip()
    path = (Path(project) / common).resolve() / 'nightshift/architecture.json'
    if not path.exists():
        return {'version': 1, 'records': []}
    if path.is_symlink() or path.stat().st_size > 1_000_000:
        raise ValueError('unsafe_architecture_record')
    value = json.loads(path.read_text())
    if value.get('version') != 1 or not isinstance(value.get('records'), list):
        raise ValueError('invalid_architecture_record')
    seen = set()
    for row in value['records']:
        body = {k: v for k, v in row.items() if k != 'sha256'}
        if row.get('sha256') != decisions.digest(body) or row['sha256'] in seen:
            raise ValueError('changed_architecture_record')
        if row.get('supersedes') and row['supersedes'] not in seen:
            raise ValueError('invalid_architecture_supersession')
        seen.add(row['sha256'])
    return value


def resolve(project):
    rows = read(project)['records']
    replaced = {r.get('supersedes') for r in rows}
    return [r for r in rows if r['sha256'] not in replaced]


def safe_path(value):
    if not isinstance(value, str) or not value or len(value) > 500 or '\\' in value or '\0' in value or Path(value).is_absolute() or '..' in Path(value).parts:
        raise ValueError('invalid_architecture_path')
    return value


def accept(project, value):
    """Explicit operator operation; never invoked by a worker or automatic repair."""
    required = {'id', 'decision', 'operator', 'upstream', 'scope', 'reference', 'constraints'}
    if not isinstance(value, dict) or not required <= set(value) or set(value)-required-{'supersedes', 'reason'}:
        raise ValueError('invalid_architecture_proposal')
    row = dict(value)
    for key in ('id', 'decision', 'operator', 'upstream'):
        row[key] = decisions.text(row[key], 4000 if key == 'decision' else 500)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', row['id']):
        raise ValueError('invalid_architecture_id')
    if not row['upstream'].startswith('https://'):
        raise ValueError('architecture_requires_upstream_reference')
    if not isinstance(row['scope'], list) or not 1 <= len(row['scope']) <= 20:
        raise ValueError('architecture_requires_scope')
    row['scope'] = [safe_path(v) for v in row['scope']]
    reference = Path(project).resolve()/safe_path(row['reference'])
    if reference.resolve() != reference.absolute() or not reference.is_file() or reference.stat().st_size > 8000:
        raise ValueError('unsafe_or_oversized_architecture_reference')
    content = reference.read_text()
    row['reference'] = {'path': row['reference'], 'sha256': hashlib.sha256(reference.read_bytes()).hexdigest(), 'content': content}
    if not isinstance(row['constraints'], list) or not 1 <= len(row['constraints']) <= 20:
        raise ValueError('architecture_requires_constraints')
    for rule in row['constraints']:
        if not isinstance(rule, dict) or set(rule) != {'kind', 'value'} or rule['kind'] not in ('forbidden_path', 'forbidden_literal'):
            raise ValueError('unsupported_architecture_constraint')
        decisions.text(rule['value'], 500)
        if rule['kind'] == 'forbidden_path':
            safe_path(rule['value'])
    path = location(project)
    with decisions.locked(path):
        data = read(project)
        active = resolve(project)
        previous = next((r for r in active if r['id'] == row['id']), None)
        if previous:
            if row.get('supersedes') != previous['sha256'] or not row.get('reason'):
                raise ValueError('explicit_architecture_supersession_required')
            row['reason'] = decisions.text(row['reason'], 4000)
        elif row.get('supersedes') or row.get('reason'):
            raise ValueError('invalid_architecture_supersession')
        row['sha256'] = decisions.digest(row)
        data['records'].append(row)
        if len(json.dumps(data).encode()) > 1_000_000:
            raise ValueError('architecture_record_limit')
        decisions.write(path, data)
    return row


def check(project, task, rows):
    """Execute narrow literal/path constraints, not self-reported worker checks."""
    result = subprocess.run(['git', '-C', str(project), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], capture_output=True, check=True, timeout=15)
    if len(result.stdout) > 2_000_000:
        raise ValueError('architecture_file_inventory_limit')
    files = sorted(set(result.stdout.decode().split('\0'))-{''})
    findings, evidence = [], {}
    for name in files:
        applicable = [r for r in rows if any(fnmatch.fnmatchcase(name, pattern) for pattern in r['scope'])]
        if not applicable:
            continue
        path = Path(project)/name
        if not path.exists() and not path.is_symlink():
            continue
        if path.resolve() != path.absolute() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError('unsafe_or_oversized_architecture_source: '+name)
        content = path.read_bytes()
        evidence[name] = hashlib.sha256(content).hexdigest()
        for row in applicable:
            for rule in row['constraints']:
                failed = fnmatch.fnmatchcase(name, rule['value']) if rule['kind'] == 'forbidden_path' else rule['value'].encode() in content
                if failed:
                    findings.append({'id': row['id'], 'target': name, 'problem': 'Accepted decision '+row['sha256']+': '+rule['kind']+' '+rule['value']})
    return {'version': 1, 'task': task, 'status': 'fail' if findings else 'pass', 'decisions': [r['sha256'] for r in rows], 'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'source': evidence, 'findings': findings}


def mirror(project, rows, previous, ticket=None):
    """Mirror references only. Beads never becomes a second policy authority."""
    fingerprint = decisions.digest([r['sha256'] for r in rows])
    if previous.get('sha256') == fingerprint:
        return previous
    if not rows:
        return {'status': 'not_required', 'sha256': fingerprint, 'links': []}
    common = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--git-common-dir'], text=True).strip()
    ledger_project = Path(project) if (Path(project)/'.beads').exists() else (Path(project)/common).resolve().parent
    if not (ledger_project/'.beads').exists():
        return {'status': 'unavailable', 'reason': 'beads_not_initialized', 'sha256': fingerprint, 'links': []}
    links = []
    deadline = time.monotonic()+30
    def remaining():
        seconds = deadline-time.monotonic()
        if seconds <= 0:
            raise ValueError('beads_link_deadline')
        return min(15, seconds)
    try:
        for row in rows:
            reference_ticket = {'external_ref': row['upstream']+'#nightshift-decision-'+row['sha256'], 'title': 'Architecture decision: '+row['id'], 'body': 'Operator-accepted decision reference. Resolve policy from Nightshift, not this mirror.\nDecision: '+row['id']+'\nSHA256: '+row['sha256'], 'url': row['upstream'], 'source': 'architecture', 'source_id': row['id']}
            proc = subprocess.run(['bash', str(HERE/'nightshift-beads-mirror.sh')], cwd=ledger_project, input=json.dumps(reference_ticket), capture_output=True, text=True, timeout=remaining())
            if proc.returncode or not re.fullmatch(r'[A-Za-z0-9_.-]+', proc.stdout.strip()):
                raise ValueError('beads_mirror_failed')
            links.append({'id': row['id'], 'sha256': row['sha256'], 'bead': proc.stdout.strip()})
        ticket_bead = None
        if ticket:
            task_ticket = dict(ticket)
            task_ticket['body'] = task_ticket.get('body', '')+'\n\nAccepted architecture references (policy remains in Nightshift):\n'+'\n'.join(r['bead']+' '+r['sha256'] for r in links)
            proc = subprocess.run(['bash', str(HERE/'nightshift-beads-mirror.sh')], cwd=ledger_project, input=json.dumps(task_ticket), capture_output=True, text=True, timeout=remaining())
            if proc.returncode or not re.fullmatch(r'[A-Za-z0-9_.-]+', proc.stdout.strip()):
                raise ValueError('beads_ticket_link_failed')
            ticket_bead = proc.stdout.strip()
        return {'status': 'linked', 'sha256': fingerprint, 'links': links, 'ticket_bead': ticket_bead}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'status': 'unavailable', 'reason': 'beads_mirror_failed', 'sha256': fingerprint, 'links': links}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['accept', 'show', 'check'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--input')
    parser.add_argument('--task', default='architecture')
    args = parser.parse_args()
    if args.action == 'accept':
        if not args.input:
            parser.error('accept requires --input with an operator-approved proposal')
        value = accept(args.project, json.loads(Path(args.input).read_text()))
    elif args.action == 'show':
        value = resolve(args.project)
    else:
        value = check(Path(args.project).resolve(), args.task, resolve(args.project))
    print(json.dumps(value, indent=2))
    return 1 if isinstance(value, dict) and value.get('status') == 'fail' else 0


if __name__ == '__main__':
    raise SystemExit(main())
