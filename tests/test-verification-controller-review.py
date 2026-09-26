#!/usr/bin/env python3
"""Independent typed verification integration through authorized synthetic operations."""
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('verification_controller_fixture',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class VerificationControllerReview(unittest.TestCase):
    setUp=f.Operations.setUp
    tearDown=f.Operations.tearDown
    grant=f.Operations.grant
    run_op=f.Operations.run_op
    groom=f.Operations.groom
    modify_plan=f.Operations.modify_plan
    def script(self,body):
        (self.root/'test_app.py').write_text(body)
    def verify(self):
        self.groom();return self.run_op('verify')
    def test_replay_and_typed_semantic_context(self):
        self.groom();g=self.grant(['verify']);first=self.c.execute(g,'verify','independent-typed-replay')
        self.assertEqual(first['status'],'passed',first)
        count=len(self.worker.calls);second=self.c.execute(g,'verify','independent-typed-replay')
        self.assertEqual(first,{k:v for k,v in second.items() if k!='next_action'});self.assertEqual(len(self.worker.calls),count)
        row=self.c.state['results']['verify']['observations'][0];self.assertIn('Controller-validated typed observation',row['output'])
        self.assertEqual(row['counts']['passed'],1)
        mapper=m.load('operation-decisions');value=mapper.generate(self.c,self.plan,'review')
        self.plan['reviewer_policy']['semantic_plan']='semantic.json';(self.root/'semantic.json').write_text(json.dumps(value))
        packets=mapper.packets(self.c,self.plan,[row],'review')
        self.assertTrue(packets)
        for packet in packets:
            observations=[item for item in packet['evidence'] if item['role']=='observation']
            self.assertTrue(observations);self.assertIn('Controller-validated typed observation',observations[0]['text'])
    def test_effective_environment_adapter_and_source_invalidate(self):
        self.assertEqual(self.verify()['status'],'passed')
        before=self.c.assess('verify')['binding']
        with patch.dict(os.environ,{'LANG':'nightshift-synthetic-locale'}):self.assertNotEqual(self.c.assess('verify')['binding'],before)
        adapter=m.load('verification-adapters');original=adapter.assets
        def changed(check):return {**original(check),'independent-synthetic-asset':'f'*64}
        original_load=m.load
        with patch.object(adapter,'assets',side_effect=changed),patch.object(m,'load',side_effect=lambda name:adapter if name=='verification-adapters' else original_load(name)):
            self.assertNotEqual(self.c.assess('verify')['binding'],before)
        (self.root/'app.py').write_text('def answer(): return 3\n');self.assertNotEqual(self.c.assess('verify')['status'],'current')
    def test_timeout_retains_raw_and_incomplete_typed_receipt(self):
        self.script('import unittest,time\nclass Test(unittest.TestCase):\n def test_a(self): pass\n def test_z(self):\n  print("retained timeout marker",flush=True)\n  time.sleep(10)\nunittest.main()\n')
        self.plan['limits']['verify']['wall_seconds']=.4;self.modify_plan()
        result=self.verify();self.assertEqual(result['status'],'failed',result)
        bodies=[(self.c.directory/name).read_bytes() for name in result['evidence']]
        self.assertTrue(any(b'retained timeout marker' in body for body in bodies))
        reports=[json.loads(body) for body in bodies if body.startswith(b'{') and b'python-unittest-v1' in body and b'"runs"' in body]
        self.assertTrue(reports);self.assertFalse(reports[0]['complete']);self.assertEqual(reports[0]['runs'][0]['tests'][0]['status'],'passed')
    def test_large_raw_evidence_is_retained_without_dispatching_later_check(self):
        self.script('import unittest\nprint("synthetic retained evidence"*30000)\nclass Test(unittest.TestCase):\n def test_one(self): pass\nunittest.main()\n')
        self.plan['checks'].append({'id':'later','argv':['python3','test_later.py']})
        (self.root/'test_later.py').write_text('raise RuntimeError("SECOND_CHECK_MUST_NOT_EXECUTE")\n');self.modify_plan()
        result=self.verify();self.assertEqual(result['status'],'failed',result)
        retained=next(json.loads((self.c.directory/name).read_text()) for name in result['evidence'] if name.endswith('.tests.json'))
        row=retained['observations'][0];self.assertEqual(row['tests'],0);self.assertEqual(row['reason'],'verification_evidence_too_large')
        self.assertEqual(len(retained['observations']),1)
        files=[self.c.directory/name for name in result['evidence']]
        self.assertTrue(any(p.stat().st_size>500000 for p in files))
        for name,digest in result['evidence'].items():self.assertEqual(m.sha(self.c.directory/name),digest)
    def test_node_runs_through_same_verify_operation(self):
        (self.root/'test_app.mjs').write_text('import test from "node:test";import assert from "node:assert/strict";test("typed node",()=>assert.equal(2,2));\n')
        self.plan['checks']=[{'id':'node','argv':['node','test_app.mjs'],'adapter':'node-test-v1'}];self.modify_plan()
        result=self.verify();self.assertEqual(result['status'],'passed',result);self.assertEqual(self.c.state['results']['verify']['observations'][0]['counts']['passed'],1)
    def test_fallback_discovery_preserves_main_script_effects(self):
        self.script('import unittest\nassert __name__=="__main__"\nclass Test(unittest.TestCase):\n def test_one(self): self.assertEqual(2,2)\n')
        result=self.verify();self.assertEqual(result['status'],'passed',result)

if __name__=='__main__':unittest.main()
