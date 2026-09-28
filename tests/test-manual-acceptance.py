#!/usr/bin/env python3
"""Manual external acceptance admits development without asserting final success."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

fixture = load('manual_fixture', 'tests/nightshift-behavior-fixture.py')
proof = load('manual_proof', 'scripts/nightshift-behavior-proof.py')

class ManualAcceptance(unittest.TestCase):
    def test_real_red_repair_green_preserves_manual_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'project'
            # Actual failing assertion, locked tests, repair and passing assertion.
            result = fixture.prepare(ROOT, project, manual=True, final=True)
            def gate(name):
                run = subprocess.run([sys.executable, str(ROOT / 'scripts/nightshift-behavior-proof.py'),
                    'gate', '--project', str(project), '--task', 'fixture', '--gate', name],
                    capture_output=True, text=True)
                return run.returncode, json.loads(run.stdout)
            code, development = gate('development')
            self.assertEqual(code, 0, development)
            self.assertEqual(development['reason'], 'development_eligible_manual_pending')
            self.assertNotIn('manual-delivery', development['scenario_ids'])
            code, final = gate('final')
            self.assertNotEqual(code, 0)
            self.assertEqual(final['reason'], 'manual_acceptance_pending')
            self.assertEqual(final['next_action'], 'operator_verify_manual_acceptance')
            doc = json.loads(Path(result['scenario_path']).read_text())
            for mutation in ('missing_owner', 'missing_contract', 'optional', 'model_risk'):
                altered = copy.deepcopy(doc)
                case = altered['cases'][-1]
                if mutation == 'missing_owner': case['manual_acceptance']['owner'] = ''
                if mutation == 'missing_contract': del case['manual_acceptance']
                if mutation == 'optional': case['required'] = False
                if mutation == 'model_risk': case['applicability']['risks'] = ['prompt_behavior']
                with self.subTest(mutation=mutation), self.assertRaises(proof.Invalid):
                    proof.validate_doc(altered)
            # Changing the retained operator instruction invalidates the seal.
            doc['cases'][-1]['manual_acceptance']['authorization'] = 'Changed instruction'
            Path(result['scenario_path']).write_text(json.dumps(doc))
            self.assertNotEqual(gate('development')[0], 0)

if __name__ == '__main__':
    unittest.main()
