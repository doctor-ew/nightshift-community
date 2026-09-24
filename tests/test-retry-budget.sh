#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
import importlib.util
import pathlib
import sys
import tempfile
import json
from unittest.mock import patch
import subprocess
import os
import hashlib
spec = importlib.util.spec_from_file_location('budget', pathlib.Path(sys.argv[1])/'scripts/nightshift-retry-budget.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory() as tmp:
    path = pathlib.Path(tmp)/'state.json'
    module.account(path, '1', 'model_unavailable')
    module.account(path, '2', 'transport')
    state = module.account(path, '3', 'substantive')
    assert state['substantive_failures'] == 1 and state['infrastructure_failures'] == 2
    assert state['next_action'] == 'repair_spec_before_retry'
    assert module.account(path, '3', 'substantive') == state
    state = module.account(path, '4', 'capacity')
    assert state['next_action'] == 'stop'
    try: module.account(path, '5', 'success')
    except ValueError: pass
    else: raise AssertionError('exhausted budget accepted another call')
    path = pathlib.Path(tmp)/'total.json'
    for i in range(12): state = module.account(path, str(i), 'success')
    assert state['next_action'] == 'stop' and state['total'] == 12
    path = pathlib.Path(tmp)/'repairs.json'
    for i in range(4): state = module.account(path, str(i), 'substantive')
    assert state['next_action'] == 'stop' and state['infrastructure_failures'] == 0
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    routing = root/'routing.json'
    routing.write_text('{}')
    output = root/'out.json'
    calls = []
    records = [
        {'status': 'FAILED', 'rules_fired': ['dispatcher_failure'], 'reason': '(category=capacity)'},
        {'status': 'FAILED', 'rules_fired': ['dispatcher_failure'], 'reason': '(category=authentication)'},
        {'status': 'SUCCESS', 'results': {'claims': [{'status': 'CONFLICT'}]}}]
    def provider(command):
        calls.append(command)
        pathlib.Path(command[command.index('--out')+1]).write_text(json.dumps(records.pop(0)))
        return subprocess.CompletedProcess(command, 0)
    args = ['nightshift-code-fact-extractor', '--out', str(output), '--adversarial']
    with patch.dict(os.environ, NIGHTSHIFT_ROUTING_FILE=str(routing)), patch.object(module.subprocess, 'run', provider):
        for _ in range(2): assert module.run_dispatch(args) == 1
        assert module.run_dispatch(args) == 0  # Report available, not gate approval.
    sidecar = json.loads(pathlib.Path(str(output)+'.retry.json').read_text())
    state = module.account(sidecar['state_path'], sidecar['attempt_id'], 'substantive')
    state = json.loads((root/'.adversarial-budget.json').read_text())
    assert state['infrastructure_failures'] == 2 and state['substantive_failures'] == 1
    assert state['total'] == 3 and len(calls) == 3
    records.append({'status': 'FAILED', 'rules_fired': ['dispatcher_failure'], 'reason': '(category=model_unavailable)'})
    # Separate task: rejection cannot be bypassed by changing attempt/output.
    task = root/'other'
    args[2] = str(task/'out.json')
    with patch.dict(os.environ, NIGHTSHIFT_ROUTING_FILE=str(routing)), patch.object(module.subprocess, 'run', provider):
        assert module.run_dispatch(args) == 1
        try: module.run_dispatch(args + ['--attempt', '2'])
        except ValueError: pass
        else: raise AssertionError('unchanged rejected configuration launched')
        routing.write_text('{"updated":true}')
        records.append({'status': 'SUCCESS', 'results': {'claims': [{'status': 'VERIFIED'}]}})
        assert module.run_dispatch(args) == 0
        sidecar = json.loads(pathlib.Path(args[2]+'.retry.json').read_text())
        module.account(sidecar['state_path'], sidecar['attempt_id'], 'success')
        records.append({'status': 'SUCCESS', 'results': {'claims': [{'status': 'NOT_FOUND'}]}})
        assert module.run_dispatch(args) == 0
        before = json.loads((task/'.adversarial-budget.json').read_text())
        assert before['substantive_failures'] == 0 and 'pending' in before['attempts'].values()
        try: module.run_dispatch(args)
        except ValueError: pass
        else: raise AssertionError('unmapped report accepted another launch')
        sidecar = json.loads(pathlib.Path(args[2]+'.retry.json').read_text())
        # Canonical stage mapped the spec's NEW claim to NET_NEW.
        module.account(sidecar['state_path'], sidecar['attempt_id'], 'success')
        records.append({'status': 'SUCCESS', 'results': {}})
        assert module.run_dispatch(args) == 1
    state = json.loads((task/'.adversarial-budget.json').read_text())
    assert state['infrastructure_failures'] == 2 and state['substantive_failures'] == 0
    assert state['total'] == 4
    completion = subprocess.run([sys.executable, module.__file__, '--state', sidecar['state_path'],
        '--attempt-id', sidecar['attempt_id'], '--category', 'success'], capture_output=True, text=True)
    assert completion.returncode == 0, completion.stderr
    assert json.loads(completion.stdout) == state
    cli_state = root/'cli-finalize.json'
    module.account(cli_state, 'reviewed-report', 'pending')
    completion = subprocess.run([sys.executable, module.__file__, '--state', str(cli_state),
        '--attempt-id', 'reviewed-report', '--category', 'schema'], capture_output=True, text=True)
    assert completion.returncode == 0, completion.stderr
    finalized = json.loads(completion.stdout)
    assert finalized['total'] == 1 and finalized['infrastructure_failures'] == 1
    assert finalized['attempts']['reviewed-report'] == 'schema'
    module.account(task/'.adversarial-budget.json', 'interrupted', 'pending')
    with patch.dict(os.environ, NIGHTSHIFT_ROUTING_FILE=str(routing)):
        try: module.run_dispatch(args)
        except ValueError: pass
        else: raise AssertionError('pending reservation accepted another launch')
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp).resolve()
    decision = root/'decision.md'
    decision.write_text('User requested a supervised corrective continuation. Preserve original counts.')
    path = root/'.adversarial-budget.json'
    for i in range(4): module.account(path, str(i), 'substantive')
    before = json.loads(path.read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for amount in (0, 4, True):
        try: module.authorize_continuation(path, decision, digest, amount)
        except ValueError: pass
        else: raise AssertionError('unbounded continuation accepted')
    try: module.authorize_continuation(path, decision, 'stale', 3)
    except ValueError: pass
    else: raise AssertionError('stale ledger accepted')
    resumed = module.authorize_continuation(path, decision, digest, 3)
    for key in ('limits', 'total', 'attempts', 'substantive_failures', 'infrastructure_failures'):
        assert resumed[key] == before[key], key
    assert module.authorize_continuation(path, decision, digest, 3) == resumed
    # A successful report still awaits canonical gate evaluation; exactly three
    # additional launches are possible, including failures and successful calls.
    for i in range(3):
        module.account(path, 'supplement-'+str(i), 'pending')
        state = module.account(path, 'supplement-'+str(i), 'success')
    assert state['total'] == 7 and state['next_action'] == 'stop'
    assert state['substantive_failures'] == 4 and state['limits'] == before['limits']
    assert module.authorize_continuation(path, decision, digest, 3) == state
    try: module.account(path, 'extra', 'pending')
    except ValueError: pass
    else: raise AssertionError('continuation exceeded three calls')
    # Pending calls, infrastructure exhaustion and proof ledgers cannot be opened.
    for name, categories in [('pending', ['pending']), ('infra', ['transport']*3)]:
        other = root/(name+'.json')
        for i, category in enumerate(categories): module.account(other, str(i), category)
        snapshot = other.read_bytes()
        try: module.authorize_continuation(other, decision, hashlib.sha256(snapshot).hexdigest())
        except ValueError: pass
        else: raise AssertionError('ineligible ledger accepted')
        assert other.read_bytes() == snapshot
    proof = root/'proof.json'
    proof.write_text(json.dumps({'budget': {'pinned': True}, 'version': 1}))
    snapshot = proof.read_bytes()
    try: module.authorize_continuation(proof, decision, hashlib.sha256(snapshot).hexdigest())
    except ValueError: pass
    else: raise AssertionError('proof budget modified')
    assert proof.read_bytes() == snapshot
print('PASS: accounting, dispatcher admission, and bounded audited continuation')
PY
