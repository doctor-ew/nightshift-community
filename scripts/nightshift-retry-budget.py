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


def account(path, attempt, category):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.exists() else {
            'version': 1, 'infrastructure_failures': 0, 'substantive_failures': 0,
            'total': 0, 'limits': {'infrastructure': 3, 'substantive': 4, 'total': 12},
            'attempts': {}, 'next_action': 'continue'}
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
                  'authentication': 'restore_auth_before_retry',
                  'unknown': 'diagnose_before_retry',
                  'schema': 'repair_transport_before_retry',
                  'substantive': 'repair_spec_before_retry'}.get(category, 'continue')
        if (state['infrastructure_failures'] >= state['limits']['infrastructure'] or
                state['substantive_failures'] >= state['limits']['substantive'] or
                state['total'] >= state['limits']['total']):
            action = 'stop'
        state['next_action'] = action
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
            json.dump(state, out)
            out.write('\n')
            temporary = out.name
        os.replace(temporary, path)
        return state


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
                elif all(isinstance(c, dict) and c.get('status') in ('VERIFIED', 'NET_NEW') for c in claims):
                    category = 'success'
                else:
                    category = 'substantive'
            else:
                category = 'substantive'
            with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as out:
                json.dump(record, out)
                temporary = out.name
            os.replace(temporary, output)
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
        return 0 if category == 'success' else 1


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
