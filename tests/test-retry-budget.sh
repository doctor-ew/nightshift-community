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
        for _ in range(3): assert module.run_dispatch(args) == 1
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
        records.append({'status': 'SUCCESS', 'results': {}})
        assert module.run_dispatch(args) == 1
    state = json.loads((task/'.adversarial-budget.json').read_text())
    assert state['infrastructure_failures'] == 2 and state['substantive_failures'] == 0
    module.account(task/'.adversarial-budget.json', 'interrupted', 'pending')
    with patch.dict(os.environ, NIGHTSHIFT_ROUTING_FILE=str(routing)):
        try: module.run_dispatch(args)
        except ValueError: pass
        else: raise AssertionError('pending reservation accepted another launch')
print('PASS: accounting and dispatcher admission, classification, rejection and interruption')
PY
