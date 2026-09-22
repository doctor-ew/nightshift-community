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

if __name__ == '__main__':
    unittest.main()
