#!/usr/bin/env python3
"""Atomic retry accounting; attempt IDs make repeated receipt ingestion idempotent."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import tempfile
import hashlib
import subprocess
import sys
import uuid
from contextlib import contextmanager
import stat
import math


def _secure_path(path, root, create=False):
    """Proof callers supply a verified common Git directory as the trust root."""
    relative = path.relative_to(root)
    current = root
    for part in relative.parts[:-1]:
        if part in ('', '.', '..'):
            raise ValueError('unsafe accounting path')
        current /= part
        if create:
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError('unsafe accounting directory')
    for candidate in (path, path.with_suffix('.lock')):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError('unsafe accounting file')


@contextmanager
def transaction(path, initial, secure_root=None, readonly=False):
    """Shared lock/atomic-write mechanics for legacy and proof state machines."""
    path = Path(path)
    if secure_root is not None:
        _secure_path(path, Path(secure_root), create=not readonly)
    elif not readonly:
        path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDONLY if readonly else os.O_RDWR | os.O_CREAT
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path.with_suffix('.lock'), flags, 0o600)
    with os.fdopen(descriptor, 'r' if readonly else 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH if readonly else fcntl.LOCK_EX)
        if secure_root is not None:
            _secure_path(path, Path(secure_root))
        if path.exists():
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('duplicate accounting key')
                    result[key] = value
                return result
            with path.open('rb') as stream:
                raw = stream.read(64 * 1024 * 1024 + 1)
            if len(raw) > 64 * 1024 * 1024:
                raise ValueError('accounting state oversized')
            state = json.loads(raw, object_pairs_hook=unique)
            def finite(value):
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError('nonfinite accounting state')
                if isinstance(value, dict):
                    for item in value.values():
                        finite(item)
                elif isinstance(value, list):
                    for item in value:
                        finite(item)
            finite(state)
        else:
            state = initial()

        def save():
            if readonly:
                raise ValueError('read-only accounting transaction')
            if secure_root is not None:
                _secure_path(path, Path(secure_root))
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
                    temporary = out.name
                    json.dump(state, out, allow_nan=False)
                    out.write('\n')
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, path)
                temporary = None
            finally:
                if temporary is not None:
                    os.unlink(temporary)
        yield state, save


def account(path, attempt, category):
    with transaction(path, lambda: {
            'version': 1, 'infrastructure_failures': 0, 'substantive_failures': 0,
            'total': 0, 'limits': {'infrastructure': 3, 'substantive': 4, 'total': 12},
            'attempts': {}, 'next_action': 'continue'}) as (state, save):
        finalizing = state['attempts'].get(attempt) == 'pending' and category != 'pending'
        if attempt in state['attempts'] and not finalizing:
            if state['attempts'][attempt] != category:
                raise ValueError('attempt result changed')
            return state
        if state['next_action'] == 'stop' and not finalizing:
            raise ValueError('budget exhausted; retain state')
        state['attempts'][attempt] = category
        if not finalizing:
            state['total'] += 1
        if category in ('transport', 'capacity', 'model_unavailable', 'schema', 'authentication', 'unknown'):
            state['infrastructure_failures'] += 1
        elif category == 'substantive':
            state['substantive_failures'] += 1
        action = {'model_unavailable': 'change_config_before_retry',
                  'pending': 'evaluate_report_before_retry',
                  'authentication': 'restore_auth_before_retry',
                  'unknown': 'diagnose_before_retry',
                  'schema': 'repair_transport_before_retry',
                  'substantive': 'repair_spec_before_retry'}.get(category, 'continue')
        if (state['infrastructure_failures'] >= state['limits']['infrastructure'] or
                state['substantive_failures'] >= state['limits']['substantive'] or
                state['total'] >= state['limits']['total']):
            action = 'stop'
        state['next_action'] = action
        save()
        return state


def proof_budget(state, policy):
    if 'budget' not in state:
        state['budget'] = {'policy': dict(policy), 'pinned': False, 'attempts': {},
                           'reservations': {'development': 0, 'final': 0},
                           'launches': {'development': 0, 'final': 0},
                           'infrastructure_failures': 0, 'repairs': 0}
    budget = state['budget']
    proof_validate(state)
    if budget['policy'] != policy:
        if budget['pinned']:
            raise ValueError('proof policy changed')
        budget['policy'] = dict(policy)
    return budget


def proof_validate(state):
    if 'budget' not in state:
        return
    budget = state['budget']
    keys = {'policy', 'pinned', 'attempts', 'reservations', 'launches', 'infrastructure_failures', 'repairs'}
    if not isinstance(budget, dict) or set(budget) != keys or type(budget['pinned']) is not bool:
        raise ValueError('invalid proof accounting state')
    policy = budget['policy']
    bounds = {'version': (1, 1), 'development_calls': (1, 64), 'final_calls': (1, 64),
              'repairs': (0, 64), 'infrastructure_failures': (0, 2),
              'timeout_seconds': (1, 120), 'output_bytes': (1, 1048576)}
    if not isinstance(policy, dict) or set(policy) != set(bounds) | {'force_prompt'} or type(policy['force_prompt']) is not bool:
        raise ValueError('invalid pinned proof policy')
    for key, (low, high) in bounds.items():
        if type(policy[key]) is not int or not low <= policy[key] <= high:
            raise ValueError('invalid pinned proof policy')
    for key in ('infrastructure_failures', 'repairs'):
        if type(budget[key]) is not int or budget[key] < 0:
            raise ValueError('invalid proof counter')
    if budget['repairs'] > policy['repairs']:
        raise ValueError('invalid proof repair counter')
    for key in ('reservations', 'launches'):
        if not isinstance(budget[key], dict) or set(budget[key]) != {'development', 'final'}:
            raise ValueError('invalid proof gate counters')
        for gate, count in budget[key].items():
            if type(count) is not int or not 0 <= count <= policy[gate + '_calls']:
                raise ValueError('invalid proof gate counter')
    if not isinstance(budget['attempts'], dict):
        raise ValueError('invalid proof attempts')
    reservations = {'development': 0, 'final': 0}; launches = dict(reservations); failures = 0
    for attempt, item in budget['attempts'].items():
        if (not isinstance(attempt, str) or not attempt or not isinstance(item, dict)
                or set(item) != {'gate', 'kind', 'launched', 'outcome'}
                or item['gate'] not in reservations or item['kind'] not in ('prototype', 'challenge', 'probe')
                or type(item['launched']) is not bool or item['outcome'] not in ('pending', 'pass', 'fail', 'unknown')):
            raise ValueError('invalid proof attempt')
        if item['kind'] != 'probe':
            reservations[item['gate']] += 1
        elif item['launched'] or item['outcome'] != 'unknown':
            raise ValueError('invalid proof probe')
        if item['launched']:
            launches[item['gate']] += 1
        if item['outcome'] == 'unknown':
            failures += 1
    if reservations != budget['reservations'] or launches != budget['launches'] or failures != budget['infrastructure_failures']:
        raise ValueError('proof counter mismatch')


def proof_admit(state, policy, gate, minimum=1):
    budget = proof_budget(state, policy)
    if any(item['outcome'] == 'pending' for item in budget['attempts'].values()):
        raise ValueError('pending proof attempt')
    failures = budget['infrastructure_failures']
    if failures > 0 and failures >= policy['infrastructure_failures']:
        raise ValueError('proof infrastructure exhausted')
    if budget['reservations'][gate] + minimum > policy[gate + '_calls']:
        raise ValueError('proof calls exhausted')
    return budget


def proof_account(state, policy, operation, attempt, gate='development', outcome=None, kind='prototype'):
    """Proof transitions; caller holds transaction() and persists before launch."""
    budget = proof_budget(state, policy)
    previous = budget['attempts'].get(attempt)
    if gate not in ('development', 'final') or (previous is not None and previous['gate'] != gate):
        raise ValueError('proof attempt gate changed')
    if operation == 'reserve':
        if previous is not None:
            if previous['gate'] != gate or previous['kind'] != kind:
                raise ValueError('proof attempt identity changed')
            return budget
        proof_admit(state, policy, gate)
        budget['pinned'] = True
        budget['reservations'][gate] += 1
        budget['attempts'][attempt] = {'gate': gate, 'kind': kind,
                                       'launched': False, 'outcome': 'pending'}
    elif operation == 'probe-failure':
        if previous is not None:
            if previous['kind'] != 'probe':
                raise ValueError('proof attempt identity changed')
            return budget
        proof_admit(state, policy, gate, 0)
        budget['pinned'] = True
        budget['infrastructure_failures'] += 1
        budget['attempts'][attempt] = {'gate': gate, 'kind': 'probe',
                                       'launched': False, 'outcome': 'unknown'}
    elif operation == 'launch':
        if previous is None or previous['outcome'] != 'pending':
            raise ValueError('proof reservation required')
        if not previous['launched']:
            previous['launched'] = True
            budget['launches'][previous['gate']] += 1
    elif operation == 'finalize':
        if previous is None or outcome not in ('pass', 'fail', 'unknown'):
            raise ValueError('invalid proof finalization')
        if outcome in ('pass', 'fail') and not previous['launched']:
            raise ValueError('confirmed proof launch required')
        if previous['outcome'] != 'pending':
            if previous['outcome'] != outcome:
                raise ValueError('proof attempt result changed')
            return budget
        previous['outcome'] = outcome
        if outcome == 'unknown':
            budget['infrastructure_failures'] += 1
    else:
        raise ValueError('unknown proof accounting operation')
    return budget


def run_dispatch(arguments):
    # Only the existing extractor dispatcher is exposed; never execute an input command.
    if not arguments or arguments[0] != 'nightshift-code-fact-extractor':
        raise ValueError('extractor role required')
    output = Path(arguments[arguments.index('--out') + 1]).resolve()
    directory = output.parent
    state_path = directory / '.adversarial-budget.json'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.adversarial-invocation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if state_path.exists():
            state = json.loads(state_path.read_text())
            if state['next_action'] == 'stop' or 'pending' in state['attempts'].values():
                raise ValueError('exhausted or interrupted budget; inspect retained evidence')
        routing = Path(os.environ.get('NIGHTSHIFT_ROUTING_FILE', str(Path(__file__).resolve().parents[1] / 'routing.json')))
        # Conservative admission: changing an attempt number or output path must
        # not re-launch a model already rejected under this routing configuration.
        fingerprint = hashlib.sha256(routing.read_bytes()).hexdigest()
        rejected = directory / '.adversarial-rejected-config'
        if rejected.exists() and rejected.read_text() == fingerprint:
            raise ValueError('model configuration previously rejected; change routing before retry')
        identity = uuid.uuid4().hex
        account(state_path, identity, 'pending')
        script = Path(__file__).resolve().with_name('nightshift-agent.sh')
        # A unique result path prevents stale successful output from being consumed.
        invocation = directory / ('adversarial-' + identity + '.json')
        forwarded = list(arguments)
        forwarded[forwarded.index('--out') + 1] = str(invocation)
        category = 'unknown'
        code = 1
        try:
            result = subprocess.run(['bash', str(script), *forwarded])
            code = result.returncode
            record = json.loads(invocation.read_text())
            if 'dispatcher_failure' in record.get('rules_fired', []):
                reason = record.get('reason', '')
                for known in ('model_unavailable', 'authentication', 'schema', 'capacity'):
                    if 'category=' + known + ')' in reason:
                        category = known
                        break
            elif code == 0 and record.get('status') == 'SUCCESS':
                claims = record.get('results', {}).get('claims')
                if not isinstance(claims, list) or not claims:
                    category = 'schema'
                elif all(isinstance(c, dict) and c.get('status') in ('VERIFIED', 'NOT_FOUND', 'CONFLICT') for c in claims):
                    # The canonical gate owns NEW/EXISTING mapping, completeness,
                    # evidence checks and overrides. Transport cannot judge them.
                    category = 'pending'
                else:
                    category = 'schema'
            else:
                category = 'substantive'
            with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as out:
                json.dump(record, out)
                temporary = out.name
            os.replace(temporary, output)
            if category == 'pending':
                with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as out:
                    json.dump({'attempt_id': identity, 'state_path': str(state_path),
                               'result_path': str(invocation)}, out)
                    temporary = out.name
                os.replace(temporary, str(output) + '.retry.json')
        except (OSError, ValueError, TypeError, AttributeError):
            category = 'unknown'
        if category == 'model_unavailable':
            with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as out:
                out.write(fingerprint)
                temporary = out.name
            os.replace(temporary, rejected)
        state = account(state_path, identity, category)
        print(json.dumps({'budget': str(state_path), 'category': category,
                          'next_action': state['next_action']}), file=sys.stderr)
        # Zero means a report is available for authoritative gate evaluation,
        # never that the gate is approved. Pending blocks another dispatch.
        return 0 if category == 'pending' else 1


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'dispatch':
        try:
            sys.exit(run_dispatch(sys.argv[2:]))
        except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
            print('nightshift: retry budget refused dispatch: ' + str(error), file=sys.stderr)
            sys.exit(1)
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True)
    parser.add_argument('--attempt-id', required=True)
    parser.add_argument('--category', required=True, choices=(
        'success', 'substantive', 'transport', 'capacity', 'model_unavailable',
        'schema', 'authentication', 'unknown'))
    args = parser.parse_args()
    print(json.dumps(account(args.state, args.attempt_id, args.category)))
