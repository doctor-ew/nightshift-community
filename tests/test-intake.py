#!/usr/bin/env python3
"""Synthetic source intake with no provider or installed-runtime invocation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('intake_fixture',ROOT/'tests/test-operations.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m.load('intake')

class Intake(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nightshift-intake-test-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.base=f.fixture(self.root)
        self.choices=dict(scope=['app.py'],checks=self.base['checks'],requirements=[dict(id='two',requirement='Return two',manual=False)],rules='rules.md',architecture='architecture.md',allowance=dict(calls=12,seconds=180,wall_seconds=180))
    def preview(self,choices=None):
        return m.api(self.root,dict(action='intake-preview',source='spec:request.md',choices=self.choices if choices is None else choices))
    def apply(self,row,request='prepare'):
        return m.api(self.root,dict(action='intake-apply',task=row['task'],binding=row['binding'],operator='synthetic',request=request))
    def test_fresh_local_plan_and_duplicate_are_model_free(self):
        row=self.preview();self.assertEqual(row['status'],'preview');self.assertFalse((self.root/'docs'/row['task']).exists())
        result=self.apply(row);self.assertEqual(result['status'],'prepared');self.assertEqual(result['provider_calls'],0)
        self.assertEqual(self.apply(row,'duplicate'),result)
        self.assertEqual(f.m.plan(self.root,row['task']),row['plan'])
        c=f.m.Operations(self.root,row['task']);self.assertFalse(c.state['calls']);self.assertFalse(c.state['authorizations'])
    def test_pending_answers_persist_without_running(self):
        row=self.preview({});self.assertEqual(row['status'],'needs_decision')
        self.assertEqual(row['decision']['continuation_operation'],'none')
        with self.assertRaisesRegex(ValueError,'decisions_required'):self.apply(row)
        nextrow=m.api(self.root,dict(action='intake-answer',task=row['task'],binding=row['binding'],choices=self.choices))
        self.assertEqual(nextrow['status'],'preview')
        decision=m.ops.load('console-decisions').snapshot(self.root,row['decision']['task'])['answered'][0]
        self.assertTrue(decision['response']);self.assertNotIn('continuation',decision)
        self.assertEqual(self.apply(nextrow)['status'],'prepared')
    def test_changed_source_and_existing_file_are_preserved(self):
        row=self.preview();source=self.root/'request.md';source.write_text('Changed request\n')
        with self.assertRaisesRegex(ValueError,'stale'):self.apply(row)
        row=self.preview();dest=self.root/row['plan']['inputs']['spec'];dest.parent.mkdir(parents=True);dest.write_text('Operator work\n')
        with self.assertRaisesRegex(ValueError,'input_changed'):self.apply(row)
        self.assertEqual(dest.read_text(),'Operator work\n')
    def test_cancel_is_idempotent_and_never_removes_source(self):
        row=self.preview();body=dict(action='intake-cancel',task=row['task'],binding=row['binding'],operator='synthetic',request='cancel')
        result=m.api(self.root,body);self.assertEqual(m.api(self.root,body),result)
        with self.assertRaisesRegex(ValueError,'cancelled'):self.apply(row)
        self.assertTrue((self.root/'request.md').exists());self.assertFalse((self.root/'docs'/row['task']).exists())
    def test_cli_and_api_preview_bindings_match(self):
        row=self.preview();result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'intake','preview','--source','spec:request.md','--choices',json.dumps(self.choices),'--project',str(self.root)],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout)['binding'],row['binding'])
    def test_missing_manifest_is_explicit_without_preventing_draft(self):
        row=self.preview();self.assertEqual(row['readiness']['admission']['reason'],'MANIFEST_MISSING')
        self.assertEqual(row['readiness']['provider_auth'],'unverified:no_provider_probe')

if __name__=='__main__':unittest.main()
