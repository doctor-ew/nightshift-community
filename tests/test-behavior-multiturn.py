#!/usr/bin/env python3
"""Offline multi-turn proof regression via public admission/evaluation APIs."""
import sys
sys.dont_write_bytecode = True
import importlib.util, json, pathlib, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fixture', ROOT/'tests/nightshift-behavior-fixture.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)

class StructuralOracles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('proof_oracles', ROOT/'scripts/nightshift-behavior-proof.py')
        cls.proof = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.proof)
    def check_oracle(self, op, value, accepted, rejected):
        assertion = dict(op=op, field=['nested','field'], value=value)
        self.proof.assertion(assertion)
        case = dict(expected=[assertion], prohibited=[])
        for item in accepted:
            self.assertTrue(self.proof.evaluate(json.dumps({'nested':{'field':item}}), case), repr(item))
        for item in rejected:
            self.assertFalse(self.proof.evaluate(json.dumps({'nested':{'field':item}}), case), repr(item))
        self.assertFalse(self.proof.evaluate('{"nested":{}}', case))
        self.assertFalse(self.proof.evaluate('not JSON', case))
        self.assertFalse(self.proof.evaluate('{"nested":{"field":[],"field":[1]}}', case))
        prohibited = dict(expected=[], prohibited=[assertion])
        self.assertFalse(self.proof.evaluate(json.dumps({'nested':{'field':accepted[0]}}), prohibited))
    def test_array_length(self):
        self.check_oracle('json_field_length_at_most', 3, [[], [1], [1,2,3]], [[1,2,3,4], '', {}, True, 3, None])
    def test_nonempty(self):
        self.check_oracle('json_field_nonempty', True, ['yes', [None]], ['', '  \n', [], {}, True, 1, None])
    def test_structural_schema_bounds(self):
        for op, invalid in [('json_field_length_at_most', [True, 0, 17, 1.0, '3']),
                            ('json_field_nonempty', [False, 1, 'true', None])]:
            for value in invalid:
                with self.assertRaises(self.proof.Invalid):
                    self.proof.assertion(dict(op=op, field=['x'], value=value))
        for field in ([], 'x', [1]):
            with self.assertRaises(self.proof.Invalid):
                self.proof.assertion(dict(op='json_field_nonempty', field=field, value=True))
        with self.assertRaises(self.proof.Invalid):
            self.proof.assertion(dict(op='json_field_unknown', field=['x'], value=True))

class Multiturn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nightshift-multiturn-')
        self.addCleanup(self.tmp.cleanup)
        self.fx = fixture.PrototypeFixture(ROOT, self.tmp.name, multiturn=True)
        self.public = json.loads(self.fx.scenarios.read_text())
    def write(self):
        self.fx.scenarios.write_bytes(fixture.canonical(fixture.attest(self.public)))
    def test_real_history_all_turns_and_final_gate(self):
        self.fx.seal()
        result = self.fx.call('run', '--gate', 'development')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [c for c in self.fx.model_calls() if '--json-schema' not in c['argv'] and '--agents' not in c['argv']]
        self.assertEqual(len(calls), 2)
        replay = json.loads(calls[-1]['argv'][-1].split('\n', 1)[1])
        self.assertEqual([m['role'] for m in replay], ['user', 'assistant', 'user'])
        self.assertEqual(replay[1]['content'], self.fx.response.read_text())
        self.assertEqual(calls[-1]['argv'][calls[-1]['argv'].index('--tools')+1], '')
        receipt = json.loads(result.stdout)
        state = json.loads((self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json').read_text())
        turns = state['observations'][-1]['turns']
        self.assertEqual(len(turns), 2)
        self.assertEqual(state['budget']['launches']['development'], 3)
        self.assertEqual(state['observations'][-1]['usage'], {'input_tokens': 6, 'output_tokens': 4})
        self.assertEqual(self.fx.call('run', '--gate', 'final').returncode, 0)
    def test_public_development_retains_actual_turns_and_final_is_private(self):
        self.fx.seal()
        self.assertEqual(self.fx.call('run', '--gate', 'development').returncode, 0)
        ledger = self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json'
        state = json.loads(ledger.read_text())
        evidence = []
        for turn in state['observations'][-1]['turns']:
            ref = turn['development_evidence']
            path = self.fx.project/ref['path']
            self.assertEqual(__import__('hashlib').sha256(fixture.canonical(json.loads(path.read_text()))).hexdigest(), ref['sha256'])
            evidence.append(json.loads(path.read_text()))
        self.assertEqual(evidence[0]['input'], self.public['cases'][0]['input'][0]['input'])
        self.assertEqual(evidence[0]['completion'], self.fx.response.read_text())
        self.assertEqual(evidence[1]['index'], 1)
        self.assertEqual(evidence[1]['turn_assertions']['expected'], [True])
        before = set((self.fx.project/'docs/prototype').glob('development-*.json'))
        self.fx.response.write_text('{"choice":"allow","secret":"PRIVATE-FINAL-SENTINEL"}')
        self.assertEqual(self.fx.call('run', '--gate', 'final').returncode, 0)
        self.assertNotIn('PRIVATE-FINAL-SENTINEL', ledger.read_text())
        self.assertEqual(before, set((self.fx.project/'docs/prototype').glob('development-*.json')))
        state = json.loads(ledger.read_text())
        for record in state['observations'] + state['turn_observations']:
            if record['gate'] == 'final':
                self.assertNotIn('development_evidence', json.dumps(record))
                self.assertNotIn('completion":', json.dumps(record))
    def test_failed_development_retains_completion_without_resampling(self):
        self.fx.seal(); self.fx.response.write_text('{"choice":"deny"}')
        self.assertNotEqual(self.fx.call('run', '--gate', 'development').returncode, 0)
        ledger = self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json'
        state = json.loads(ledger.read_text())
        turn = state['turn_observations'][-1]
        evidence = json.loads((self.fx.project/turn['development_evidence']['path']).read_text())
        self.assertEqual(evidence['completion'], '{"choice":"deny"}')
        self.assertEqual(evidence['turn_assertions']['expected'], [False])
        self.assertEqual(evidence['outcome'], 'fail')
        before = len(self.fx.model_calls())
        self.assertEqual(json.loads(self.fx.call('run', '--gate', 'development').stdout)['reason'], 'prototype_revision_required')
        self.assertEqual(len(self.fx.model_calls()), before)
    def test_runtime_reseal_retains_failed_prompt_and_repair_accounting(self):
        spec = importlib.util.spec_from_file_location('reseal_proof', ROOT/'scripts/nightshift-behavior-proof.py')
        proof = importlib.util.module_from_spec(spec); spec.loader.exec_module(proof)
        self.fx.seal(); self.fx.response.write_text('{"choice":"deny"}')
        self.assertNotEqual(self.fx.call('run', '--gate', 'development').returncode, 0)
        ledger = self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json'
        state = json.loads(ledger.read_text())
        # Model an older engine seal without modifying production/consumer state.
        state['seal']['oracle_sha256'] = '0' * 64
        state['seal']['sha256'] = proof.seal_digest(state['seal'])
        for record in state['observations'] + state['turn_observations']:
            record['seal_sha256'] = state['seal']['sha256']
        launches = state['budget']['launches']['development']
        ledger.write_text(json.dumps(state))
        self.fx.seal()
        sealed = json.loads(ledger.read_text())
        self.assertEqual(sealed['budget']['launches']['development'], launches + 1)
        self.assertEqual(sealed['budget']['repairs'], 0)
        self.assertEqual(len(sealed['seals']), 1)
        before = len(self.fx.model_calls())
        result = self.fx.call('run', '--gate', 'development')
        self.assertEqual(json.loads(result.stdout)['reason'], 'prototype_revision_required')
        self.assertEqual(len(self.fx.model_calls()), before)
        self.fx.prompt.write_text(self.fx.prompt.read_text() + 'Repair the prototype.\n')
        self.fx.response.write_text('{"choice":"allow"}')
        self.assertEqual(self.fx.call('run', '--gate', 'development').returncode, 0)
        self.assertEqual(json.loads(ledger.read_text())['budget']['repairs'], 1)
    def test_runtime_reseal_never_reuses_previous_engine_success(self):
        spec = importlib.util.spec_from_file_location('reseal_success', ROOT/'scripts/nightshift-behavior-proof.py')
        proof = importlib.util.module_from_spec(spec); spec.loader.exec_module(proof)
        self.fx.seal()
        self.assertEqual(self.fx.call('run', '--gate', 'development').returncode, 0)
        ledger = self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json'
        state = json.loads(ledger.read_text())
        state['seal']['oracle_sha256'] = '0' * 64
        state['seal']['sha256'] = proof.seal_digest(state['seal'])
        for record in state['observations'] + state['turn_observations']:
            record['seal_sha256'] = state['seal']['sha256']
        ledger.write_text(json.dumps(state))
        self.fx.seal()
        self.assertNotEqual(self.fx.call('gate', '--gate', 'development').returncode, 0)
        before = len(self.fx.model_calls())
        self.assertEqual(self.fx.call('run', '--gate', 'development').returncode, 0)
        self.assertEqual(len(self.fx.model_calls()), before + 2)
    def test_retention_write_failure_preserves_grading_and_budget(self):
        spec = importlib.util.spec_from_file_location('retention_error', ROOT/'scripts/nightshift-behavior-proof.py')
        proof = importlib.util.module_from_spec(spec); spec.loader.exec_module(proof)
        self.fx.seal()
        from unittest.mock import patch
        with patch.dict('os.environ', self.fx.env, clear=True), patch.object(proof, 'write_public', side_effect=OSError('fixture write failure')):
            result = proof.run_proof(proof.Proof(self.fx.project, self.fx.task, proof.config(self.fx.project)), 'development')
        self.assertEqual(result['outcome'], 'pass')
        ledger = json.loads((self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json').read_text())
        self.assertEqual(ledger['budget']['launches']['development'], 3)
        self.assertEqual(ledger['observations'][-1]['turns'][0]['development_evidence_error'], 'artifact_unavailable')
    def test_runtime_reseal_rejects_simultaneous_prompt_change(self):
        spec = importlib.util.spec_from_file_location('reseal_changed', ROOT/'scripts/nightshift-behavior-proof.py')
        proof = importlib.util.module_from_spec(spec); spec.loader.exec_module(proof)
        self.fx.seal()
        ledger = self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json'
        state = json.loads(ledger.read_text())
        state['seal']['oracle_sha256'] = '0' * 64
        state['seal']['sha256'] = proof.seal_digest(state['seal'])
        ledger.write_text(json.dumps(state))
        self.fx.prompt.write_text(self.fx.prompt.read_text() + 'Uncounted change.\n')
        result = self.fx.call('seal', '--scenarios', self.fx.scenarios, '--challenge', self.fx.challenge, '--heldout', self.fx.private)
        self.assertEqual(json.loads(result.stdout)['reason'], 'use_bounded_prototype_revision')
        self.assertEqual(json.loads(ledger.read_text())['budget']['repairs'], 0)
    def test_single_turn_development_retains_evidence(self):
        with tempfile.TemporaryDirectory(prefix='nightshift-single-evidence-') as temp:
            fx = fixture.PrototypeFixture(ROOT, temp)
            fx.seal()
            self.assertEqual(fx.call('run', '--gate', 'development').returncode, 0)
            state = json.loads((fx.project/'.git/nightshift/behavior-proof/prototype/state.json').read_text())
            record = state['observations'][-1]
            evidence = json.loads((fx.project/record['development_evidence']['path']).read_text())
            self.assertEqual(evidence['completion'], fx.response.read_text())
            self.assertEqual(evidence['case_assertions'], {'expected': [True], 'prohibited': [True]})
    def test_failed_first_turn_never_accepts_or_launches_second(self):
        self.fx.seal(); self.fx.response.write_text('{"choice":"deny"}')
        result = self.fx.call('run', '--gate', 'development')
        self.assertNotEqual(result.returncode, 0)
        calls = [c for c in self.fx.model_calls() if '--json-schema' not in c['argv'] and '--agents' not in c['argv']]
        self.assertEqual(len(calls), 1)
        self.assertNotEqual(self.fx.call('gate', '--gate', 'development').returncode, 0)
    def test_second_turn_failure_cannot_reuse_first_pass(self):
        stub = self.fx.binary/'claude'
        source = stub.read_text()
        marker = "mode=os.environ.get('FIXTURE_MODE','normal')"
        source = source.replace(marker, "if '\"role\":\"assistant\"' in args[-1]:\n print(json.dumps({'type':'result','is_error':False,'result':'{\"choice\":\"deny\"}'}));sys.exit(0)\n" + marker)
        stub.write_text(source)
        self.fx.seal()
        self.assertNotEqual(self.fx.call('run','--gate','development').returncode, 0)
        self.assertNotEqual(self.fx.call('gate','--gate','development').returncode, 0)
        state = json.loads((self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json').read_text())
        self.assertEqual([t['outcome'] for t in state['observations'][-1]['turns']], ['pass','fail'])
    def test_sealed_turn_mutation_blocks_before_provider(self):
        self.fx.seal()
        self.public['cases'][0]['input'][1]['input'] = 'Changed after review'
        self.write()
        before = len(self.fx.model_calls())
        self.assertNotEqual(self.fx.call('run','--gate','development').returncode, 0)
        self.assertEqual(len(self.fx.model_calls()), before)
    def test_transport_unknown_never_launches_second_turn(self):
        self.fx.seal(); self.fx.env['FIXTURE_MODE'] = 'transport'
        result = self.fx.call('run','--gate','development')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['outcome'], 'unknown')
        state = json.loads((self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json').read_text())
        self.assertEqual(len(state['observations'][-1]['turns']), 1)
        self.assertFalse(list((self.fx.project/'docs/prototype').glob('development-*.json')))
    def test_crash_after_failed_turn_cannot_resample_development_or_heldout(self):
        # Simulate only the exact durable boundary: turn+budget saved, aggregate absent.
        for gate in ('development', 'final'):
            with self.subTest(gate=gate), tempfile.TemporaryDirectory(prefix='nightshift-crash-turn-') as temp:
                fx = fixture.PrototypeFixture(ROOT, temp, multiturn=True)
                with (fx.project/'.nightshift.toml').open('a') as stream:
                    stream.write('final_calls = 4\n')
                fx.seal()
                if gate == 'final':
                    self.assertEqual(fx.call('run','--gate','development').returncode, 0)
                fx.response.write_text('{"choice":"deny"}')
                self.assertNotEqual(fx.call('run','--gate',gate).returncode, 0)
                ledger = fx.project/'.git/nightshift/behavior-proof/prototype/state.json'
                state = json.loads(ledger.read_text())
                state['observations'] = [o for o in state['observations'] if o['gate'] != gate]
                ledger.write_text(json.dumps(state))
                fx.response.write_text('{"choice":"allow"}')
                before = len(fx.model_calls())
                result = fx.call('run','--gate',gate)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(json.loads(result.stdout)['reason'],
                                 'prototype_revision_required' if gate == 'development' else 'heldout_replacement_required')
                self.assertEqual(len(fx.model_calls()), before)
                self.assertNotEqual(fx.call('gate','--gate',gate).returncode, 0)
                fx.prompt.write_text(fx.prompt.read_text() + 'Changed prototype.\n')
                revised = fx.call('run','--gate','development')
                if gate == 'final':
                    self.assertEqual(json.loads(revised.stdout)['reason'], 'heldout_replacement_required')
                    self.assertEqual(len(fx.model_calls()), before)
                else:
                    self.assertEqual(revised.returncode, 0, revised.stdout)
                    changed = json.loads(ledger.read_text())
                    self.assertEqual(changed['budget']['repairs'], 1)
    def test_invalid_turn_shapes(self):
        for value in ([], [{}], [{'input':'x','expected':[],'prohibited':[]}], 'single turn', [dict(input='x',expected=[{'op':'text_equals','value':'x'}],prohibited=[])] * 17):
            with self.subTest(value=value):
                self.public['cases'][0]['input'] = value; self.write()
                self.assertNotEqual(self.fx.call('validate','--scenarios',self.fx.scenarios).returncode, 0)
    def test_budget_admits_whole_conversation_before_launch(self):
        with (self.fx.project/'.nightshift.toml').open('a') as stream:
            stream.write('development_calls = 2\n')
        self.fx.seal()
        before = len(self.fx.model_calls())
        result = self.fx.call('run', '--gate', 'development')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.fx.model_calls()), before)

if __name__ == '__main__': unittest.main()
