#!/usr/bin/env python3
"""Independent evidence-bound questions; no real providers or execution authority."""
import copy
import difflib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('question_review_fixture',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class Questions(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-question-review-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();f.fixture(self.root);self.worker=f.Worker();self.c=m.Operations(self.root,'demo',self.worker)
    def ask(self,operation='groom-spec',text='Which behavior is required?'):
        assessed=self.c.assess(operation)
        with self.c.lease():return self.c.question(operation,assessed['binding'],dict(question=text,reason='Synthetic unresolved requirement',options=[]))
    def answer(self,item,operation='groom-spec',text='Return exactly two.'):
        return self.c.answer(operation,self.c.assess(operation)['binding'],item['sha256'],'',text)
    def groom(self):
        a=self.c.assess('groom-spec');g=self.c.authorize(m.RECIPES['groom'],a['binding'],'synthetic','groom')
        result=self.c.chain(g['id']);self.assertTrue(all(r['status']=='passed' for r in result['results']),result)
    def test_question_and_answer_never_grant_or_execute(self):
        before=self.c.assess('groom-spec')['binding'];question=self.ask()
        self.assertEqual(question['continuation_operation'],'none')
        self.assertIn('operator_decision_required',self.c.assess('groom-spec')['blockers'])
        self.answer(question)
        self.assertNotEqual(self.c.assess('groom-spec')['binding'],before)
        self.assertFalse(self.c.state['authorizations']);self.assertFalse(self.c.state['results']);self.assertFalse(self.worker.calls)
        self.assertIn('Return exactly two.',json.dumps(self.c.packet('groom-spec',self.c.assess('groom-spec'),m.plan(self.root,'demo'))['operator_decisions']))
    def test_changed_input_rejects_old_question_without_losing_evidence(self):
        question=self.ask();(self.root/'request.md').write_text('Changed product request\n')
        with self.assertRaisesRegex(ValueError,'stale_question'):self.answer(question)
        rows=self.c.assess('groom-spec')['questions'];self.assertEqual(len(rows),1);self.assertFalse(rows[0]['current'])
    def test_distinct_second_question_keeps_both_histories(self):
        first=self.ask(text='Which output is required?');self.answer(first)
        second=self.ask(text='Which error behavior is required?')
        self.assertNotEqual(first['sha256'],second['sha256'])
        self.assertIsNone(second['response']);self.assertIn('operator_decision_required',self.c.assess('groom-spec')['blockers'])
    def test_changed_implementation_source_stales_pending_question(self):
        self.groom();question=self.ask('implement')
        (self.root/'app.py').write_text('def answer(): return 2 # changed externally\n')
        with self.assertRaisesRegex(ValueError,'stale_question'):self.answer(question,'implement')
    def test_duplicate_question_and_duplicate_answer_preserve_identity(self):
        first=self.ask();self.assertEqual(first['sha256'],self.ask()['sha256'])
        first_answer=self.answer(first);second_answer=self.answer(first)
        self.assertEqual(first_answer,second_answer)
        with self.assertRaises(ValueError):self.answer(first,text='Conflicting answer')
    def test_network_retry_same_answer_original_binding_is_idempotent(self):
        question=self.ask();binding=self.c.assess('groom-spec')['binding']
        first=self.c.answer('groom-spec',binding,question['sha256'],'','Return exactly two.')
        self.assertEqual(first,self.c.answer('groom-spec',binding,question['sha256'],'','Return exactly two.'))
        self.assertFalse(self.c.state['authorizations']);self.assertFalse(self.worker.calls)
    def test_second_answer_replay_uses_submission_binding_after_first_answer(self):
        first=self.ask(text='Which output?');second=self.ask(text='Which error?')
        self.answer(first)
        binding=self.c.assess('groom-spec')['binding']
        receipt=self.c.answer('groom-spec',binding,second['sha256'],'','Report explicit errors.')
        self.assertEqual(receipt,self.c.answer('groom-spec',binding,second['sha256'],'','Report explicit errors.'))
        self.assertFalse(self.worker.calls)
    def test_worker_question_with_patch_is_rejected_without_question_or_write(self):
        worker=self.worker
        def invalid(operation,packet,route,output,seconds):
            value=worker(operation,packet,route,output,seconds)
            value['results'].update(decision='abstain',question=dict(question='Which result?',reason='Unresolved',options=[]))
            value['artifacts']['diff']='untrusted patch'
            return value
        self.c.worker=invalid;before=(self.root/'spec.md').read_bytes()
        a=self.c.assess('groom-spec');g=self.c.authorize(['groom-spec'],a['binding'],'synthetic','invalid-question')
        result=self.c.execute(g['id'],'groom-spec','invalid-question-run')
        self.assertEqual(result['status'],'failed');self.assertEqual(result['reason'],'invalid_question_effect')
        self.assertFalse(self.c.state.get('questions'));self.assertEqual((self.root/'spec.md').read_bytes(),before)
    def test_pending_question_invalidates_current_result_and_downstream(self):
        self.groom();self.assertEqual(self.c.assess('groom-spec')['status'],'current')
        question=self.ask()
        self.assertEqual(self.c.assess('groom-spec')['status'],'blocked')
        self.assertEqual(self.c.assess('groom')['status'],'blocked')
        self.assertEqual(self.c.assess('implement')['status'],'blocked')
        calls=list(self.worker.calls);self.answer(question)
        self.assertNotEqual(self.c.assess('groom-spec')['status'],'current')
        self.assertNotEqual(self.c.assess('groom')['status'],'current')
        self.assertEqual(self.worker.calls,calls)
    def test_question_history_cap_blocks_before_console_mutation(self):
        with self.c.lease():
            self.c.state['questions']=[dict(operation='review',basis='b'*64,binding='c'*64,task='retained-'+str(i),sha256='d'*64) for i in range(100)]
            self.c.save()
        directory=self.c.directory.parent.parent/'console'
        before={p.name:p.read_bytes() for p in directory.glob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError,'question_history_full'):self.ask()
        after={p.name:p.read_bytes() for p in directory.glob('*') if p.is_file()}
        self.assertEqual(before,after)
    def test_answered_groom_remains_current_after_controlled_patch(self):
        question=self.ask();self.answer(question)
        path=self.root/'spec.md';before=path.read_text();after=before+'Clarified manual behavior.\n'
        self.worker.patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/spec.md',tofile='b/spec.md'))
        a=self.c.assess('groom-spec');g=self.c.authorize(['groom-spec'],a['binding'],'synthetic','clarified')
        self.assertEqual(self.c.execute(g['id'],'groom-spec','clarified-run')['status'],'passed')
        self.assertEqual(self.c.assess('groom-spec')['status'],'current')
        self.assertIn('Return exactly two.',json.dumps(self.c.state['results']['groom-spec']['operator_decisions']))
    def test_completed_worker_recovery_retains_answers_without_redispatch(self):
        question=self.ask();self.answer(question)
        a=self.c.assess('groom-spec');g=self.c.authorize(['groom-spec'],a['binding'],'synthetic','completed-worker')
        with patch.object(self.c,'finish',side_effect=KeyboardInterrupt('synthetic controller crash after completion receipt')):
            with self.assertRaises(KeyboardInterrupt):self.c.execute(g['id'],'groom-spec','completed-worker-run')
        self.assertEqual(len(self.worker.calls),1)
        resumed=m.Operations(self.root,'demo',self.worker)
        self.assertEqual(resumed.execute(g['id'],'groom-spec','completed-worker-run')['status'],'passed')
        self.assertEqual(resumed.state['results']['groom-spec']['operator_decisions'],a['dependencies']['decisions'])
        self.assertEqual(len(self.worker.calls),1)
    def test_worker_question_stops_then_answer_requires_new_explicit_grant(self):
        first=True;worker=self.worker
        def questioning(operation,packet,route,output,seconds):
            nonlocal first
            value=worker(operation,packet,route,output,seconds)
            if first:
                first=False;value['results'].update(decision='abstain',question=dict(question='Which return value?',reason='Unresolved requirement',options=[]))
            return value
        self.c.worker=questioning
        a=self.c.assess('groom-spec');g=self.c.authorize(['groom-spec'],a['binding'],'synthetic','worker-question')
        result=self.c.execute(g['id'],'groom-spec','worker-question-run')
        self.assertEqual(result['status'],'failed');self.assertIn('operator_decision_required',result['reason'])
        self.assertEqual(len(worker.calls),1)
        question=self.c.assess('groom-spec')['questions'][0]['question'];self.answer(question)
        self.assertEqual(len(worker.calls),1);self.assertNotIn('groom-spec',self.c.state['results'])
        self.assertEqual(self.c.assess('groom-spec')['status'],'ready')
        a=self.c.assess('groom-spec');new=self.c.authorize(['groom-spec'],a['binding'],'synthetic','answered')
        self.assertEqual(self.c.execute(new['id'],'groom-spec','answered-run')['status'],'passed')
        self.assertEqual(len(worker.calls),2)

if __name__=='__main__':unittest.main()
