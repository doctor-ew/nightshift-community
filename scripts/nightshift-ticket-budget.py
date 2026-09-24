#!/usr/bin/env python3
"""Persistent admission for instrumented dispatcher calls, not token/billing accounting.

The first reservation starts coverage. Existing historical work is never inferred.
Unfinished reservations remain charged conservatively; restarts cannot reset limits.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def ledger_path(project, task):
    if not task or len(task) > 256 or any(ord(c) < 32 for c in task):
        raise ValueError('invalid budget task')
    common = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--git-common-dir'], text=True).strip()
    common = (Path(project) / common).resolve()
    return common / 'nightshift' / 'ticket-budgets' / (hashlib.sha256(task.encode()).hexdigest() + '.json')


def update(project, task, operation, invocation='', max_calls=None, max_seconds=None, outcome='', now=None, max_wall_seconds=None, continuation_seconds=None, expected_revision=None):
    now = time.time() if now is None else now
    path = ledger_path(project, task)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            state = json.loads(path.read_text())
            if state.get('version') != 1 or state.get('task') != task:
                raise ValueError('invalid budget ledger')
        else:
            if operation != 'reserve':
                raise ValueError('budget has no instrumented reservations')
            state = dict(version=1, task=task, coverage='instrumented-dispatches-only', historical_usage='unknown',
                         started_at=now, deadline_at=now + (max_wall_seconds if max_wall_seconds is not None else 600),
                         max_wall_seconds=max_wall_seconds if max_wall_seconds is not None else 600, max_calls=max_calls if max_calls is not None else 64,
                         max_active_seconds=max_seconds if max_seconds is not None else 3600, reservations={})
        for name, requested in [('max_calls', max_calls), ('max_active_seconds', max_seconds)]:
            if type(state[name]) is not int or state[name] <= 0:
                raise ValueError('budget limits must be positive integers')
            if requested is not None and requested != state[name]:
                raise ValueError('budget limits are pinned; changing environment cannot reset or expand them')
        if max_wall_seconds is not None and state.get('max_wall_seconds') is None:
            raise ValueError('This historical ticket has no wall-clock deadline. Use explicit continuation before resuming; prior usage and call limits will be retained.')
        if max_wall_seconds is not None and max_wall_seconds != state.get('max_wall_seconds'):
            raise ValueError('wall-clock limit is pinned')
        if state.get('max_wall_seconds') is not None and (type(state['max_wall_seconds']) is not int or state['max_wall_seconds'] <= 0):
            raise ValueError('wall-clock limit must be a positive integer')
        reservations = state['reservations']
        def elapsed():
            return sum(max(0, r.get('finished_at', now) - r['started_at']) for r in reservations.values())
        allowed, reason = True, ''
        if operation == 'continue':
            if expected_revision is not None and hashlib.sha256(path.read_bytes()).hexdigest() != expected_revision:
                raise ValueError('Budget changed; refresh before granting more time')
            if type(continuation_seconds) is not int or not 1 <= continuation_seconds <= 600:
                raise ValueError('explicit continuation must be between 1 and 600 seconds')
            if any('finished_at' not in r for r in reservations.values()):
                raise ValueError('cannot continue while reservations are unfinished')
            if len(reservations) >= state['max_calls']:
                raise ValueError('call budget exhausted; continuation cannot add calls')
            state.setdefault('continuations', []).append(dict(at=now, seconds=continuation_seconds,
                previous_deadline_at=state.get('deadline_at'), previous_max_active_seconds=state['max_active_seconds'],
                active_seconds=elapsed(), calls_reserved=len(reservations)))
            state['max_active_seconds'] = elapsed() + continuation_seconds
            state['max_active_seconds'] = int(state['max_active_seconds'])
            state['max_wall_seconds'] = continuation_seconds
            state['deadline_at'] = now + continuation_seconds
        elif operation == 'reserve':
            if not invocation or len(invocation) > 256:
                raise ValueError('reservation requires bounded invocation identity')
            if invocation in reservations:
                # Idempotent accounting, but never permit a duplicate provider launch.
                allowed, reason = False, 'invocation_already_reserved'
            elif state.get('deadline_at') is not None and now >= state['deadline_at']:
                allowed, reason = False, 'ticket_wall_time_budget_exhausted'
            elif len(reservations) >= state['max_calls']:
                allowed, reason = False, 'ticket_call_budget_exhausted'
            elif elapsed() >= state['max_active_seconds']:
                allowed, reason = False, 'ticket_active_time_budget_exhausted'
            else:
                reservations[invocation] = dict(started_at=now, outcome='reserved')
        elif operation == 'finish':
            if invocation not in reservations:
                raise ValueError('unknown reservation')
            if 'finished_at' not in reservations[invocation]:
                reservations[invocation].update(finished_at=now, outcome=outcome or 'unknown')
        elif operation == 'check':
            if state.get('deadline_at') is not None and now >= state['deadline_at']:
                allowed, reason = False, 'ticket_wall_time_budget_exhausted'
            elif elapsed() >= state['max_active_seconds']:
                allowed, reason = False, 'ticket_active_time_budget_exhausted'
        else:
            raise ValueError('unsupported operation')
        state['last_event'] = dict(operation=operation, invocation=invocation, allowed=allowed, reason=reason, at=now)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.budget-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(state, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return dict(allowed=allowed, reason=reason, ledger=str(path), task=task,
                    coverage=state['coverage'], historical_usage=state['historical_usage'],
                    calls_reserved=len(reservations), active_seconds=elapsed(),
                    max_calls=state['max_calls'], max_active_seconds=state['max_active_seconds'],
                    deadline_at=state.get('deadline_at'), max_wall_seconds=state.get('max_wall_seconds'))


def snapshot(project, task, now=None):
    """Read-only public accounting; do not create or renew allowances."""
    now = time.time() if now is None else now
    path = ledger_path(project, task)
    if not path.exists():
        return None
    content = path.read_bytes()
    state = json.loads(content)
    if state.get('version') != 1 or state.get('task') != task:
        raise ValueError('invalid budget ledger')
    reservations = state['reservations']
    active = sum(max(0, r.get('finished_at', now) - r['started_at']) for r in reservations.values())
    deadline = state.get('deadline_at')
    remaining = max(0, state['max_active_seconds'] - active)
    wall_remaining = max(0, deadline - now) if deadline is not None else None
    return dict(revision=hashlib.sha256(content).hexdigest(),
                unfinished=sum(1 for r in reservations.values() if 'finished_at' not in r),
                continuations=len(state.get('continuations', [])),
                calls_reserved=len(reservations), max_calls=state['max_calls'],
                active_seconds=active, active_seconds_remaining=remaining,
                wall_seconds_remaining=wall_remaining,
                exhausted=remaining <= 0 or len(reservations) >= state['max_calls']
                          or wall_remaining == 0,
                coverage=state['coverage'], historical_usage=state['historical_usage'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['reserve', 'check', 'finish', 'continue'])
    parser.add_argument('--project', default='.')
    parser.add_argument('--task', required=True)
    parser.add_argument('--invocation', default='')
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--max-seconds', type=int)
    parser.add_argument('--outcome', default='')
    parser.add_argument('--max-wall-seconds', type=int)
    parser.add_argument('--continuation-seconds', type=int)
    args = vars(parser.parse_args())
    try:
        result = update(**args)
        print(json.dumps(result))
        return 0 if result['allowed'] else 75
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(allowed=False, reason=str(error))))
        return 75


if __name__ == '__main__':
    raise SystemExit(main())
