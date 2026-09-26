#!/usr/bin/env python3
"""Shared CLI/HTTP intake with disposable repositories and synthetic providers."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('intake_interfaces',ROOT/'tests/test-operation-interfaces.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
CHOICES=dict(scope=['app.py'],rules='rules.md',architecture='architecture.md',check='test_app.py',interpreter='python3',requirement='Return two.')

class Intake(unittest.TestCase):
    setUp=f.Interfaces.setUp
    tearDown=f.Interfaces.tearDown
    http=f.Interfaces.http
    def call(self,body):
        status,result=self.http('/api/intake',body);self.assertEqual(status,200,result);return result
    def intake_cli(self,body):
        result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'intake','--project',str(self.root),'--request','-'],input=json.dumps(body),env=self.env,text=True,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);return json.loads(result.stdout)
    def test_local_intake_cli_http_parity_then_shared_factory(self):
        resolved=self.call(dict(action='resolve',reference='spec:request.md'));task=resolved['task']
        self.assertEqual(resolved,self.intake_cli(dict(action='view',task=task)))
        draft=self.call(dict(action='draft',task=task,choices=CHOICES))
        self.assertFalse((self.root/'.synthetic-calls.jsonl').exists())
        self.assertEqual(draft,self.intake_cli(dict(action='draft',task=task,choices=CHOICES)))
        request=dict(action='materialize',task=task,binding=draft['draft']['binding'])
        ready=self.call(request);self.assertEqual(ready['status'],'materialized')
        self.assertEqual(ready,self.intake_cli(request))
        self.assertFalse((self.root/'.synthetic-calls.jsonl').exists())
        assessment=ready['operations']['operations'][0]
        payload=dict(action='authorize',task=task,operations=ready['operations']['recipes']['factory'],binding=assessment['binding'],operator='synthetic-intake',request='factory')
        status,grant=self.http('/api/operations',payload);self.assertEqual(status,200,grant)
        status,result=self.http('/api/operations',dict(action='chain',task=task,grant=grant['id']));self.assertEqual(status,200,result);self.assertEqual(result['view']['status'],'pending_manual_acceptance',result)
        calls=(self.root/'.synthetic-calls.jsonl').read_bytes()
        self.assertEqual(len(calls.splitlines()),4)
        replay=self.http('/api/operations',payload)[1]
        self.assertEqual(replay['id'],grant['id']);self.assertEqual(replay['deadline'],grant['deadline'])
        self.http('/api/operations',dict(action='chain',task=task,grant=grant['id']))
        self.assertEqual((self.root/'.synthetic-calls.jsonl').read_bytes(),calls)
    def test_missing_choices_answer_and_cancel_never_dispatch(self):
        resolved=self.call(dict(action='resolve',reference='spec:request.md'));task=resolved['task']
        missing={**CHOICES,'scope':[],'check':''}
        first=self.call(dict(action='draft',task=task,choices=missing))
        self.assertEqual(len(first['decisions']['pending']),1)
        self.assertEqual(first,self.call(dict(action='draft',task=task,choices=missing)))
        answer=dict(action='answer',task=task,sha256=first['decisions']['pending'][0]['sha256'],answer='Use app.py and test_app.py.')
        answered=self.call(answer);self.assertEqual(answered,self.call(answer))
        draft=self.call(dict(action='draft',task=task,choices=CHOICES))
        self.call(dict(action='cancel',task=task))
        status,_=self.http('/api/intake',dict(action='materialize',task=task,binding=draft['draft']['binding']));self.assertEqual(status,409)
        self.assertFalse((self.root/'docs'/task).exists())
        self.assertFalse((self.root/'.synthetic-calls.jsonl').exists())
    def test_intake_requires_same_origin_token_and_bounded_source(self):
        body=dict(action='resolve',reference='spec:request.md')
        self.assertEqual(self.http('/api/intake',body,token=False)[0],403)
        for reference in ('spec:../request.md','spec:.git/config','gh:unqualified','spec:docs/../request.md'):
            self.assertEqual(self.http('/api/intake',dict(action='resolve',reference=reference))[0],409)
        self.assertFalse((self.root/'.synthetic-calls.jsonl').exists())

if __name__=='__main__':unittest.main()
