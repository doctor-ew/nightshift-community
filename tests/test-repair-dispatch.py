#!/usr/bin/env python3
"""Verify failed repair never reaches paid dispatcher or consumes retry allowance."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retry', ROOT/'scripts/nightshift-retry-budget.py')
retry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retry)

class RepairDispatch(unittest.TestCase):
    def test_admission_runs_real_checker_before_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            prior = root/'prior.json'
            prior.write_text('{"turn3":"ambiguous"}')
            current = root/'current.json'
            current.write_bytes(prior.read_bytes())
            manifest = {'schema_version': 1, 'findings': [{
                'id': 'acceptance', 'artifact': 'current.json', 'pointer': '/turn3',
                'expected': 'one sentence', 'prior_artifact': 'prior.json',
                'prior_sha256': hashlib.sha256(prior.read_bytes()).hexdigest()}]}
            (root/'repair-checks.json').write_text(json.dumps(manifest))
            (root/'routing.json').write_text('{}')
            args = ['nightshift-code-fact-extractor', '--out', str(root/'review.json'), '--adversarial']
            original = subprocess.run
            paid = []
            def run(command, **kwargs):
                if 'nightshift-repair-check.py' in command[1]:
                    return original(command, **kwargs)
                paid.append(command)
                Path(command[command.index('--out')+1]).write_text(json.dumps({
                    'status':'SUCCESS', 'results':{'claims':[{'status':'VERIFIED'}]}}))
                return subprocess.CompletedProcess(command, 0)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, NIGHTSHIFT_ROUTING_FILE=str(root/'routing.json')), patch.object(retry.subprocess, 'run', run):
                    with self.assertRaisesRegex(ValueError, 'no model launched'):
                        retry.run_dispatch(args)
                    self.assertEqual(paid, [])
                    self.assertFalse((root/'.adversarial-budget.json').exists())
                    current.write_text('{"turn3":"one sentence"}')
                    self.assertEqual(retry.run_dispatch(args), 0)
                    self.assertEqual(len(paid), 1)
                    self.assertFalse(json.loads((root/'repair-check.receipt.json').read_text())['gate_approval'])
            finally:
                os.chdir(cwd)


class RecurringRepair(unittest.TestCase):
    def test_unchanged_substantive_review_is_blocked_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            root = project/'docs/task'
            root.mkdir(parents=True)
            prior = root/'prior.json'
            prior.write_text('{"value":"bad","detail":"first"}')
            current = root/'current.json'
            current.write_text('{"value":"fixed","detail":"first"}')
            manifest = {'schema_version': 1, 'findings': [{
                'id': 'stable-finding', 'artifact': 'docs/task/current.json', 'pointer': '/value',
                'expected': 'fixed', 'prior_artifact': 'docs/task/prior.json',
                'prior_sha256': hashlib.sha256(prior.read_bytes()).hexdigest()}]}
            manifest_path = root/'repair-checks.json'
            manifest_path.write_text(json.dumps(manifest))
            args = ['nightshift-code-fact-extractor', '--out', str(root/'review.json'), '--adversarial']
            original = subprocess.run
            calls = []
            def run(command, **kwargs):
                if command[0] != 'bash':
                    return original(command, **kwargs)
                calls.append(command)
                Path(command[command.index('--out')+1]).write_text(json.dumps({
                    'status':'SUCCESS', 'results':{'claims':[{'status':'VERIFIED'}]}}))
                return subprocess.CompletedProcess(command, 0)
            cwd = Path.cwd()
            try:
                os.chdir(project)
                with patch.object(retry.subprocess, 'run', run):
                    self.assertEqual(retry.run_dispatch(args), 0)
                    pending = json.loads((root/'review.json.retry.json').read_text())
                    retry.account(pending['state_path'], pending['attempt_id'], 'substantive')
                    before = (root/'.adversarial-budget.json').read_bytes()
                    # Formatting, finding renaming and output renaming are not repairs.
                    current.write_text(json.dumps({'detail':'first','value':'fixed'}, indent=4))
                    manifest['findings'][0]['id'] = 'renamed-finding'
                    manifest_path.write_text(json.dumps(manifest, indent=2))
                    args[2] = str(root/'other-review.json')
                    # Fresh CLI process proves enforcement does not rely on memory.
                    blocked = original([os.sys.executable, str(ROOT/'scripts/nightshift-retry-budget.py'), 'dispatch', *args], capture_output=True, text=True, timeout=10)
                    self.assertNotEqual(blocked.returncode, 0)
                    self.assertIn('unchanged registered repair', blocked.stderr)
                    self.assertEqual((root/'.adversarial-budget.json').read_bytes(), before)
                    self.assertEqual(len(calls), 1)
                    receipt = json.loads((root/'repair-admission.json').read_text())
                    self.assertEqual(receipt['status'], 'needs-decision')
                    self.assertFalse(receipt['gate_approval'])
                    portal = original(['bash', str(ROOT/'scripts/nightshift-dashboard.sh'), '--project', str(project), '--json'], capture_output=True, text=True, check=True, timeout=10)
                    self.assertIn('unchanged registered repair', portal.stdout)
                    self.assertIn('needs-decision', portal.stdout)
                    current.write_text('{"value":"fixed","detail":"repaired underlying cause"}')
                    self.assertEqual(retry.run_dispatch(args), 0)
                    self.assertEqual(len(calls), 2)
                    self.assertEqual(json.loads((root/'repair-admission.json').read_text())['status'], 'skipped')
                    self.assertFalse(json.loads((root/'repair-admission.json').read_text())['gate_approval'])
                    # Pending remains blocking; a transport/schema failure permits
                    # re-evaluation of unchanged input under the original allowance.
                    with self.assertRaisesRegex(ValueError, 'interrupted budget'):
                        retry.run_dispatch(args)
                    pending = json.loads((root/'other-review.json.retry.json').read_text())
                    retry.account(pending['state_path'], pending['attempt_id'], 'schema')
                    self.assertEqual(retry.run_dispatch(args), 0)
                    self.assertEqual(len(calls), 3)
            finally:
                os.chdir(cwd)

if __name__ == '__main__':
    unittest.main()
