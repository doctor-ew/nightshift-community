#!/usr/bin/env python3
"""Bounded, observational ticket progress. No gate state or usage is inferred.

progress(project, task, launch=None, running=False) returns workers, phase,
action_required, last_activity_at/last_activity_age_seconds, latest_event and evidence.
The caller's running flag is a hint, never evidence of process liveness.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import time


def safe_text(path, limit=65536, tail=False):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError('Symlink evidence refused')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Not a regular evidence file')
        if info.st_size > limit and not tail:
            raise ValueError('Oversized evidence')
        if tail and info.st_size > limit:
            stream.seek(-limit, os.SEEK_END)
            data = stream.read(limit).split(b'\n', 1)[-1]
        else:
            data = stream.read(limit)
    return data.decode('utf-8', errors='replace'), info.st_mtime


def record(path):
    value = json.loads(safe_text(path)[0])
    if not isinstance(value, dict):
        raise ValueError('Expected evidence object')
    return value


def timestamp(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError):
        return None


def process_identity(pid):
    if type(pid) is not int or pid <= 0:
        return None
    try:
        command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True, timeout=2).strip()
        started = subprocess.check_output(['ps', '-p', str(pid), '-o', 'lstart='], text=True, timeout=2).strip()
        return command, started
    except (OSError, subprocess.SubprocessError):
        return None


def common_dir(project):
    value = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--git-common-dir'], text=True, timeout=3).strip()
    return (Path(project) / value).resolve()


def cleaned(value, limit=600):
    text = ' '.join(str(value or '').split())
    # Suppress messages which may expose credential assignments or private cases.
    if re.search(r'(?i)(api[_ -]?key|authorization|bearer\s|password|secret|heldout|holdout)', text):
        return 'Activity recorded; sensitive details omitted.'
    return text[:limit]


def progress(project, task, launch=None, running=False):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', task):
        raise ValueError('Invalid task')
    now = time.time()
    result = dict(workers=[], phase='No verified active worker', action_required='Inspect latest recorded gate',
                  last_activity_at=None, last_activity_age_seconds=None, latest_event=None, evidence=[], running=False, activity=None, next='Await next recorded pipeline event')
    common = common_dir(project)
    console = common / 'nightshift/console'
    owner_pending = False
    try:
        owner = record(common / 'nightshift/worktrees' / (task + '.json'))
        target = Path(owner['worktree']).absolute()
        if owner.get('task') != task or target.resolve() != target or common_dir(target) != common:
            return result
    except FileNotFoundError:
        target = Path(project).resolve()
        owner_pending = True
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return result
    try:
        saved = record(console / (task + '.json'))
        ref = saved.get('settings', {}).get('ref') if saved.get('task') == task else None
    except (OSError, ValueError):
        ref = None
    updates = []
    roots = [target / '.nightshift/agents']
    if Path(project).resolve() != target:
        roots.append(Path(project).resolve() / '.nightshift/agents')
    for root in roots:
        if root.resolve() != root:
            continue
        # Bound both enumeration and JSON loads; no recursive traversal.
        try:
            paths = []
            with os.scandir(root) as entries:
                for entry in entries:
                    if len(paths) >= 512:
                        break
                    if entry.name.endswith('.json') and entry.is_file(follow_symlinks=False):
                        paths.append(Path(entry.path))
        except OSError:
            continue
        for path in paths:
            try:
                agent = record(path)
                explicit = agent.get('ticket', {}).get('source_id')
                if explicit and explicit != task:
                    continue
                if (owner_pending or root != roots[0]) and explicit != task:
                    continue
                role = agent.get('role', '')
                if not re.fullmatch(r'nightshift-[a-z0-9-]+', role):
                    continue
                changed = timestamp(agent.get('finished_at') or agent.get('started_at'))
                if changed:
                    updates.append((changed, cleaned(role + ': ' + str(agent.get('status', 'recorded'))), path))
                if agent.get('status') != 'running':
                    continue
                identity = process_identity(agent.get('pid'))
                if not identity:
                    continue
                tokens = shlex.split(identity[0])
                is_factory = role == 'nightshift-factory'
                executable = 'nightshift-factory.sh' if is_factory else 'nightshift-agent.sh'
                if not any(Path(t).name == executable for t in tokens):
                    continue
                if not is_factory and role not in tokens:
                    continue
                # A recycled PID must also match the task-specific invocation path.
                if not (any(task in Path(t).parts or task in t for t in tokens) or (is_factory and explicit == task and ref and ref in tokens)):
                    continue
                started = timestamp(agent.get('started_at'))
                try:
                    actual_start = dt.datetime.strptime(identity[1], '%a %b %d %H:%M:%S %Y').timestamp()
                except ValueError:
                    continue
                if not started or abs(actual_start - started) > 10:
                    continue
                def option(name):
                    try:
                        return tokens[tokens.index(name) + 1]
                    except (ValueError, IndexError):
                        return None
                attempt = option('--attempt')
                attempt = int(attempt) if attempt and attempt.isdigit() and len(attempt) < 4 else None
                stage = cleaned(option('--stage'), 80) or None
                result['workers'].append(dict(attempt=attempt, stage=stage, role=role, provider=cleaned(agent.get('provider'), 80),
                    model=cleaned(agent.get('model'), 120), started_at=agent.get('started_at'),
                    elapsed_seconds=max(0, int(now-started)), pid=agent['pid'], evidence=path.as_uri()))
            except (OSError, ValueError, TypeError, AttributeError):
                continue
    if launch and launch.get('status') == 'running':
        identity = process_identity(launch.get('pid'))
        if identity and identity[1] == launch.get('started_identity'):
            tokens = shlex.split(identity[0])
            if any(Path(t).name in ('nightshift-factory.sh', 'nightshift-console-repair.py') for t in tokens) and (any(task in t for t in tokens) or (ref and ref in tokens and str(Path(project).resolve()) in tokens)):
                result['running'] = True
    result['running'] = result['running'] or bool(result['workers'])
    # Only a registered console log in this task's namespace is eligible.
    if launch and launch.get('log'):
        log = Path(launch['log']).absolute()
        if log.parent == console and log.name.startswith(task + '-'):
            try:
                text, modified = safe_text(log, 131072, tail=True)
                for line in reversed(text.splitlines()[-100:]):
                    if len(line) > 16384:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    item = event.get('item', {})
                    message = item.get('text') if item.get('type') == 'agent_message' else None
                    if message:
                        updates.append((modified, cleaned(message), log))
                        break
            except (OSError, ValueError, AttributeError):
                pass
    if updates:
        when, message, evidence = max(updates, key=lambda item: item[0])
        result.update(last_activity_at=dt.datetime.fromtimestamp(when, dt.timezone.utc).isoformat(),
                      last_activity_age_seconds=max(0, int(now-when)), latest_event=message, evidence=[dict(label='Latest activity evidence', href=evidence.as_uri())])
    specialists = [w for w in result['workers'] if w['role'] != 'nightshift-factory']
    if specialists:
        worker = max(specialists, key=lambda w: w['started_at'])
        result.update(phase=worker['role'].removeprefix('nightshift-').replace('-', ' '), action_required='None — worker active')
    elif result['running']:
        result.update(phase='Orchestrator active; waiting for next worker update', action_required='None — awaiting update')
    else:
        result['next'] = 'Inspect the recorded outcome before choosing a recovery action'
    result['activity'] = result['phase']
    if specialists and worker.get('attempt'):
        result['activity'] += ' · attempt ' + str(worker['attempt'])
    return result
