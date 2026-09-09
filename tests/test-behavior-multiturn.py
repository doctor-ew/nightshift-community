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
