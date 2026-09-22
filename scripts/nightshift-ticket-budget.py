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


def update(project, task, operation, invocation='', max_calls=None, max_seconds=None, outcome='', now=None):
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
                         started_at=now, max_calls=max_calls if max_calls is not None else 64,
                         max_active_seconds=max_seconds if max_seconds is not None else 3600, reservations={})
        for name, requested in [('max_calls', max_calls), ('max_active_seconds', max_seconds)]:
            if type(state[name]) is not int or state[name] <= 0:
                raise ValueError('budget limits must be positive integers')
            if requested is not None and requested != state[name]:
                raise ValueError('budget limits are pinned; changing environment cannot reset or expand them')
        reservations = state['reservations']
        def elapsed():
            return sum(max(0, r.get('finished_at', now) - r['started_at']) for r in reservations.values())
        allowed, reason = True, ''
        if operation == 'reserve':
            if not invocation or len(invocation) > 256:
                raise ValueError('reservation requires bounded invocation identity')
            if invocation in reservations:
                # Idempotent accounting, but never permit a duplicate provider launch.
                allowed, reason = False, 'invocation_already_reserved'
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
            if elapsed() >= state['max_active_seconds']:
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
                    max_calls=state['max_calls'], max_active_seconds=state['max_active_seconds'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['reserve', 'check', 'finish'])
    parser.add_argument('--project', default='.')
    parser.add_argument('--task', required=True)
    parser.add_argument('--invocation', default='')
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--max-seconds', type=int)
    parser.add_argument('--outcome', default='')
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
