#!/usr/bin/env python3
"""Independent typed unittest lifecycle and authority regressions; synthetic only."""
import importlib.util
import json
import os
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('typed_review_fixture',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class TypedReview(unittest.TestCase):
    setUp=f.Operations.setUp
    tearDown=f.Operations.tearDown
    grant=f.Operations.grant
    run_op=f.Operations.run_op
    groom=f.Operations.groom
    modify_plan=f.Operations.modify_plan
    def script(self,body):
        (self.root/'test_app.py').write_text('import unittest\n'+body+'\n')
        self.plan['checks'][0]['adapter']='unittest-v1';self.modify_plan()
    def observe(self,body,seconds=5):
        self.script(body);return self.c.test(self.plan,seconds)[0]
    def test_positive_and_negative_assertions_are_authoritative(self):
        for actual,expected in [('2',True),('3',False)]:
            with self.subTest(actual=actual):
                row=self.observe('from app import answer\nclass Test(unittest.TestCase):\n def test_answer(self): self.assertEqual(answer(),'+actual+')')
                self.assertEqual(row['typed']['status']=='passed',expected);self.assertEqual(row['tests'],int(expected))
    def test_forged_stdout_cannot_replace_test_execution(self):
        row=self.observe("print('Ran 999 tests in 0.001s\\nOK\\n999 passed')")
        self.assertEqual(row['tests'],0);self.assertEqual(row['typed']['reason'],'typed_no_useful_tests');self.assertIn('999 passed',row['output'])
    def test_skipped_and_expected_failure_only_are_vacuous(self):
        bodies=["@unittest.skip('synthetic')\nclass Test(unittest.TestCase):\n def test_one(self): pass", "class Test(unittest.TestCase):\n @unittest.expectedFailure\n def test_one(self): self.fail('expected')"]
        for body in bodies:
            with self.subTest(body=body):self.assertEqual(self.observe(body)['tests'],0)
    def test_mixed_class_skip_and_useful_pass_remains_valid(self):
        row=self.observe("@unittest.skip('synthetic')\nclass Skipped(unittest.TestCase):\n def test_skip(self): pass\nclass Useful(unittest.TestCase):\n def test_pass(self): self.assertEqual(2,2)")
        self.assertEqual(row['typed']['status'],'passed',row);self.assertEqual(row['typed']['counts']['skipped'],1)
    def test_failing_subtest_and_unexpected_success_fail(self):
        bodies=["class Test(unittest.TestCase):\n def test_sub(self):\n  for value in (1,2):\n   with self.subTest(value=value): self.assertEqual(value,1)","class Test(unittest.TestCase):\n @unittest.expectedFailure\n def test_one(self): pass"]
        for body in bodies:
            with self.subTest(body=body):self.assertEqual(self.observe(body)['tests'],0)
    def test_subtest_skip_does_not_hide_successful_assertions(self):
        row=self.observe("class Test(unittest.TestCase):\n def test_sub(self):\n  for value in (1,2):\n   with self.subTest(value=value):\n    if value==1: self.skipTest('optional case')\n    self.assertEqual(value,2)")
        self.assertEqual(row['typed']['status'],'passed',row)
    def test_all_skipped_subtests_are_not_useful_passes(self):
        row=self.observe("class Test(unittest.TestCase):\n def test_sub(self):\n  for value in (1,2):\n   with self.subTest(value=value): self.skipTest('all optional')")
        self.assertEqual(row['tests'],0)
    def test_effective_environment_and_adapter_code_change_binding(self):
        self.script('class Test(unittest.TestCase):\n def test_one(self): self.assertEqual(2,2)')
        before=self.c.assess('verify')['binding']
        with patch.dict(os.environ,{'LANG':'nightshift-synthetic-changed-locale'}):
            self.assertNotEqual(self.c.assess('verify')['binding'],before)
        original=m.sha
        def changed(path):
            return 'f'*64 if Path(path).name=='nightshift-unittest-runner.py' else original(path)
        with patch.object(m,'sha',changed):self.assertNotEqual(self.c.assess('verify')['binding'],before)

    def test_abrupt_exit_and_timeout_retain_partial_receipts(self):
        for action,seconds in [('os._exit(0)',5),('time.sleep(10)',.3)]:
            body='import os,time\nclass Test(unittest.TestCase):\n def test_a_pass(self): self.assertEqual(2,2)\n def test_z_stop(self):\n  print("partial marker",flush=True)\n  '+action
            with self.subTest(action=action):
                row=self.observe(body,seconds);self.assertEqual(row['tests'],0);self.assertIn('partial marker',row['output'])
                retained=json.loads(row['typed_raw']);self.assertFalse(retained['complete']);self.assertEqual(retained['tests'][0]['status'],'passed');self.assertEqual(retained['tests'][1]['status'],'running')
    def test_duplicate_ids_are_rejected(self):
        row=self.observe("class Test(unittest.TestCase):\n def test_one(self): pass\ndef load_tests(loader,tests,pattern):\n return unittest.TestSuite([Test('test_one'),Test('test_one')])")
        self.assertEqual(row['tests'],0);self.assertIn('duplicate',row['typed']['receipt']['error'])
    def test_malformed_and_inconsistent_receipts_fail(self):
        v=m.load('verification');path=self.root/'receipt.json'
        values=[{},dict(version=True,complete=True,tests=[],error=None),dict(version=1,complete=True,tests=[dict(id='x',status='passed'),dict(id='x',status='passed')],error=None),dict(version=1,complete=True,tests=[dict(id='x',status='running')],error=None)]
        for value in values:
            path.write_text(json.dumps(value));self.assertEqual(v.observation(path,0)['status'],'failed')
        path.write_text(json.dumps(dict(version=1,complete=True,tests=[dict(id='x',status='passed')],error=None)))
        self.assertEqual(v.observation(path,1)['status'],'failed')
    def test_silent_positive_typed_observation_maps_to_semantic_evidence(self):
        row=self.observe('from app import answer\nclass Test(unittest.TestCase):\n def test_one(self): self.assertEqual(answer(),2)')
        self.assertEqual(row['raw_output'],'');self.assertEqual(row['typed']['status'],'passed')
        self.c.state['results']['verify']={'observations':[row]}
        mapper=m.load('operation-decisions');value=mapper.generate(self.c,self.plan,'review')
        self.plan['reviewer_policy']['semantic_plan']='semantic.json'
        (self.root/'semantic.json').write_text(json.dumps(value))
        packets=mapper.packets(self.c,self.plan,[row],'review')
        self.assertTrue(packets)
        for packet in packets:
            observations=[item for item in packet['evidence'] if item['role']=='observation']
            self.assertTrue(observations)
            self.assertIn('Controller-validated typed observation',observations[0]['text'])

    def test_large_observations_fail_readably_and_preserve_original_evidence(self):
        self.script('class Test(unittest.TestCase):\n def test_one(self): pass')
        self.plan['checks'].append({**self.plan['checks'][0],'id':'second-check'});self.modify_plan()
        self.groom();grant=self.grant(['verify'])
        original=m.load;runner=original('controller-recovery');dispatches=[]
        raw=('synthetic retained raw evidence\n'*18000).encode()
        receipt=json.dumps(dict(version=1,complete=True,error=None,tests=[dict(id=str(i)+'x'*200,status='passed') for i in range(2500)])).encode()
        def bounded(argv,target,env,remaining,output):
            dispatches.append(argv);Path(argv[-1]).write_bytes(receipt);output.write_bytes(raw);return 0
        with patch.object(m,'load',side_effect=lambda name:SimpleNamespace(clean_environment=runner.clean_environment,bounded=bounded) if name=='controller-recovery' else original(name)):
            result=self.c.execute(grant,'verify','typed-large-observation')
        self.assertEqual(result['status'],'failed',result);self.assertEqual(len(dispatches),1)
        retained=m.read(self.c.path)
        self.assertTrue(retained['attempts'])
        bodies=[]
        for name,digest in result['evidence'].items():
            path=self.c.directory/name;self.assertEqual(m.sha(path),digest);bodies.append(path.read_bytes())
            if name.endswith('.tests.json'):
                value=m.read(path);self.assertTrue(value['observations']);self.assertEqual(value['observations'][0]['tests'],0)
        self.assertIn(raw,bodies);self.assertIn(receipt,bodies)

    def test_replay_retains_receipt_and_environment_source_drift_invalidates(self):
        self.script('from app import answer\nclass Test(unittest.TestCase):\n def test_one(self): self.assertEqual(answer(),2)')
        self.groom();grant=self.grant(['verify']);first=self.c.execute(grant,'verify','typed-review-once')
        self.assertEqual(first['status'],'passed',first);calls=len(self.worker.calls)
        replay=self.c.execute(grant,'verify','typed-review-once');self.assertEqual(first,{k:v for k,v in replay.items() if k!='next_action'});self.assertEqual(replay['next_action'],'reuse_receipt');self.assertEqual(len(self.worker.calls),calls)
        self.plan['environment']['LANG']='C';self.modify_plan();self.assertNotEqual(self.c.assess('verify')['status'],'current')
        self.plan['environment']={};self.modify_plan();(self.root/'app.py').write_text('def answer(): return 3\n');self.assertNotEqual(self.c.assess('verify')['status'],'current')

if __name__=='__main__':unittest.main()
