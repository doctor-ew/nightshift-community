#!/usr/bin/env python3
"""Durable recovery checkpoints. Callers hold the existing per-ticket lease."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / ('nightshift-' + name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def atomic(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.recovery-', dir=path.parent)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def location(project, task):
    return load('console-decisions').location(project, task).with_name(task + '.recovery.json')


def snapshot(project, task):
    path = location(project, task)
    if not path.exists():
        return None
    if path.resolve() != path.absolute() or path.stat().st_size > 2_000_000:
        raise ValueError('Unsafe recovery state')
    state = json.loads(path.read_text())
    if state.get('version') != 1 or state.get('task') != task:
        raise ValueError('Invalid recovery state')
    return state


def workspace(target):
    """Hash the complete nonignored input corpus; never reuse partial snapshots."""
    target = Path(target).resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(target), *args])
    names = sorted(set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')) - {''})
    if len(names) > 10000:
        raise ValueError('Recovery input corpus exceeds 10000 files')
    files, size = {}, 0
    for name in names:
        if name.startswith('.nightshift/'):
            continue  # lifecycle output is not a source dependency
        path = target / name
        if path.is_symlink() or path.resolve() != path.absolute() or (path.exists() and not path.is_file()):
            raise ValueError('Recovery input must be a regular file: ' + name)
        if not path.exists():
            files[name] = None
            continue
        size += path.stat().st_size
        if size > 64 * 1024 * 1024:
            raise ValueError('Recovery input corpus exceeds 64 MiB')
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(head=git('rev-parse', 'HEAD').decode().strip(), files=files)


def plan(target, settings, provider='auto'):
    """Resolve author and both reviewers before reserving or launching anything."""
    budget = load('ticket-budget').snapshot(target, settings['_task'])
    if budget and budget.get('exhausted'):
        raise ValueError('Ticket budget exhausted; recovery cannot reset it')
    routing_path = load('routing-path').resolve(HERE.parent, target)
    routing = json.loads(routing_path.read_text())
    policy_module = load('provider-policy')
    policy = policy_module.mode(target)
    if settings['policy'] == 'claude-only':
        policy = 'claude-only'
    role = 'nightshift-repair-analyst'
    if role not in routing['roles']:
        routing['roles'][role] = json.loads(json.dumps(routing['roles']['nightshift-engineer']))
        routing['roles'][role].update(prompt='agents/nightshift-repair-analyst.md', sandbox='read-only')
    initial = None
    if provider != 'auto':
        if policy == 'claude-only' and provider != 'claude':
            raise ValueError('Repair selection conflicts with the saved provider policy')
        choices = [r for v in routing['roles'].values() for r in v['gears'].values()]
        initial = next((r for r in choices if r.get('provider') == provider and r.get('model')), None)
        if initial is None:
            raise ValueError('No configured model for the selected repair provider')
    author = policy_module.select_route(routing, role, 1, policy, initial=initial)
    routing['roles'][role]['gears']['1'] = author
    review = policy_module.select_route(routing, role, 1, policy, author['provider'], True)
    verification = policy_module.select_route(routing, 'nightshift-run-all-tests', 1, policy, author['provider'], True)
    for route in (author, review, verification):
        if route.get('provider') not in ('claude', 'codex', 'local') or not route.get('model'):
            raise ValueError('Invalid recovery route')
    decisions = load('console-decisions').read(load('console-decisions').location(target, settings['_task']))
    if any(r['response'] is None for r in decisions['requests']):
        raise ValueError('Unresolved operator decision')
    answers = [dict(sha256=r['sha256'], question=r['question'], response=r['response']) for r in decisions['requests']]
    return dict(routing=routing, policy=policy, routes=dict(proposal=author, review=review, verification=verification),
                decisions=answers, settings={k:v for k,v in settings.items() if k != '_task'},
                assets={p:hashlib.sha256((HERE.parent / p).read_bytes()).hexdigest() for p in
                    ('scripts/nightshift-agent.sh', 'scripts/nightshift-provider-policy.py',
                     'agents/nightshift-repair-analyst.md', 'agents/nightshift-run-all-tests.md',
                     'contracts/nightshift-repair-analyst.schema.json', 'contracts/nightshift-run-all-tests.schema.json')})


class Recovery:
    def __init__(self, project, task, target, plan, evidence):
        self.path = location(project, task)
        self.target = Path(target)
        self.state = snapshot(project, task)
        inputs = workspace(target)
        binding = digest(plan)
        if self.state is None:
            budget = load('ticket-budget').snapshot(project, task)
            remaining = budget.get('wall_seconds_remaining') if budget else None
            allowance = min(600, remaining) if remaining is not None else 600
            self.state = dict(version=1, task=task, worktree=str(target), deadline_at=time.time()+allowance,
                              attempts=[], history=[], completed={}, next_action='proposal', findings=[])
        if self.state['worktree'] != str(target):
            raise ValueError('Recovery worktree identity changed')
        if self.state.get('binding') != binding or self.state.get('inputs') != inputs:
            if self.state.get('binding'):
                self.state['history'].append({k:self.state.get(k) for k in ('binding', 'inputs', 'completed', 'findings', 'next_action')})
            self.state.update(binding=binding, inputs=inputs, completed={}, next_action='proposal', findings=[],
                              manual_acceptance='unverified', delivery_status='pending_required_checks')
        self.state.update(plan=plan, evidence=str(evidence))
        self.save()

    def save(self):
        atomic(self.path, self.state)

    def result(self, stage):
        row = self.state['completed'].get(stage)
        if not row:
            return None
        path = Path(row['path'])
        if path.resolve() != path.absolute() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Retained recovery evidence changed: ' + stage)
        return json.loads(path.read_text())

    def reserve(self, stage, output):
        if time.time() >= self.state['deadline_at']:
            raise ValueError('Recovery deadline exhausted; resume cannot renew it')
        if sum(a['stage'] == stage for a in self.state['attempts']) >= 3:
            raise ValueError('Recovery stage budget exhausted; history retained')
        self.state['attempts'].append(dict(stage=stage, output=str(output), outcome='pending'))
        self.state['next_action'] = stage
        self.save()

    def finish(self, stage, output, passed, reason=''):
        self.state['attempts'][-1].update(outcome='pass' if passed else 'fail', reason=reason)
        if passed:
            self.state['completed'][stage] = dict(path=str(output), sha256=hashlib.sha256(output.read_bytes()).hexdigest())
            self.state['findings'] = [f for f in self.state['findings'] if f['stage'] != stage]
            self.state['next_action'] = dict(proposal='review', review='apply', verification='resume_pipeline')[stage]
        else:
            self.state['findings'].append(dict(stage=stage, reason=reason, evidence=str(output)))
        self.save()

    def applied(self):
        self.state.update(inputs=workspace(self.target), next_action='verification')
        self.state['completed']['apply'] = True
        self.save()

    def delivery(self, receipt):
        self.state['delivery_evidence'] = receipt
        if receipt.get('reason') == 'manual_acceptance_pending':
            self.state.update(delivery_status='pending_manual_acceptance', manual_acceptance='pending',
                              next_action='operator_verify_manual_acceptance')
        else:
            self.state.update(delivery_status='pending_required_checks', next_action='inspect_required_checks')
        self.save()
