#!/usr/bin/env python3
"""Independent clarification convergence and failure-transport checks; stub only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import sys
sys.dont_write_bytecode=True
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]

class AdditionalReview(unittest.TestCase):
    def setUp(self):
        home=tempfile.TemporaryDirectory(prefix='nightshift-hitl-review-home-');self.addCleanup(home.cleanup)
        env={'HOME':home.name,'NIGHTSHIFT_HOME':home.name+'/.nightshift','XDG_CONFIG_HOME':home.name+'/config',
             'PATH':os.environ['PATH'],'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null','PYTHONDONTWRITEBYTECODE':'1'}
        guard=patch.dict(os.environ,env,clear=True);guard.start();self.addCleanup(guard.stop)
        spec=importlib.util.spec_from_file_location('question_fixture',ROOT/'tests/test-operation-questions-review.py');self.f=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.f)
        self.case=self.f.Questions();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.m=self.f.m;self.c=self.case.c
    def test_same_answered_question_changed_rationale_does_not_reopen(self):
        item=self.case.ask();self.case.answer(item)
        value=dict(question=item['question'],reason='A reworded explanation of the same unchanged need',options=item['options'])
        with self.c.lease():again=self.c.question('groom-spec',self.c.assess('groom-spec')['binding'],value)
        self.assertEqual(again['sha256'],item['sha256'])
        self.assertNotIn('operator_decision_required',self.c.assess('groom-spec')['blockers'])
    def test_missing_pending_question_evidence_fails_closed(self):
        item=self.case.ask();record=self.c.state['questions'][0]
        decisions=self.m.load('console-decisions');path=decisions.location(self.case.root,record['task'])
        path.rename(path.with_suffix('.retained-evidence'))
        with self.assertRaisesRegex(ValueError,'operation_question_evidence_missing'):
            self.c.assess('groom-spec')
        row=next(row for row in self.c.view()['operations'] if row['operation']=='groom-spec')
        self.assertEqual(row['status'],'blocked')
        self.assertIn('operation_question_evidence_missing',row['blockers'][0])
        self.assertFalse(self.case.worker.calls)
    def test_new_unanswered_question_blocks_previously_authorized_operation(self):
        assessed=self.c.assess('groom-spec');grant=self.c.authorize(['groom-spec'],assessed['binding'],'synthetic','before-question')
        self.case.ask()
        with self.assertRaisesRegex(ValueError,'operator_decision_required'):self.c.execute(grant['id'],'groom-spec','cannot-bypass')
        self.assertFalse(self.case.worker.calls)
    def test_normalized_whitespace_case_and_options_reuse_answer(self):
        item=self.case.ask();self.case.answer(item)
        with self.c.lease():
            again=self.c.question('groom-spec',self.c.assess('groom-spec')['binding'],dict(question='  WHICH   behavior is required?  ',reason='New reason',options=[dict(id='new',label='New option',description='Updated suggestion')]))
        self.assertEqual(again['sha256'],item['sha256'])
        self.assertEqual(len(self.c.state['questions']),1)
        self.assertFalse(self.case.worker.calls)
    def test_pre_fix_task_identity_reuses_retained_answer(self):
        a=self.c.assess('groom-spec');basis=self.c.question_basis(a['dependencies'],'groom-spec')
        value=dict(question='Which behavior is required?',reason='Original rationale',options=[])
        task='op-question-'+self.m.digest(dict(project=str(self.c.project),task=self.c.task,operation='groom-spec',basis=basis,question=value))[:32]
        item=self.m.load('console-decisions').request(self.case.root,task,dict(value,continuation='none',decision_key='operation-clarification'))
        with self.c.lease():
            self.c.state['questions']=[dict(operation='groom-spec',basis=basis,binding=a['binding'],task=task,sha256=item['sha256'])];self.c.save()
        self.case.answer(item)
        again=self.case.ask()
        self.assertEqual(again['sha256'],item['sha256'])
        self.assertEqual(self.c.state['questions'][0]['task'],task)
    def test_changed_basis_creates_new_pending_question_retaining_old(self):
        item=self.case.ask();self.case.answer(item)
        (self.case.root/'request.md').write_text('Changed public synthetic product requirement\n')
        again=self.case.ask()
        self.assertNotEqual(again['sha256'],item['sha256'])
        self.assertIsNone(again['response'])
        rows=self.c.assess('groom-spec')['questions']
        self.assertEqual([row['current'] for row in rows],[False,True])
        self.assertIsNotNone(rows[0]['question']['response'])
    def test_new_question_preserves_settled_question(self):
        item=self.case.ask();self.case.answer(item)
        again=self.case.ask(text='Which failure should be reported?')
        self.assertNotEqual(again['sha256'],item['sha256'])
        self.assertIn('operator_decision_required',self.c.assess('groom-spec')['blockers'])
        self.assertEqual(len(self.c.state['questions']),2)
    def test_missing_answered_question_evidence_blocks_new_authority(self):
        item=self.case.ask();self.case.answer(item);a=self.c.assess('groom-spec')
        record=self.c.state['questions'][0];decisions=self.m.load('console-decisions')
        path=decisions.location(self.case.root,record['task']);path.rename(path.with_suffix('.retained-evidence'))
        with self.assertRaisesRegex(ValueError,'operation_question_evidence_missing'):
            self.c.authorize(['groom-spec'],a['binding'],'synthetic','missing-evidence')
        self.assertFalse(self.c.state['authorizations']);self.assertFalse(self.case.worker.calls)
    def test_dispatcher_accepts_bound_fail_only(self):
        assessed=self.c.assess('groom-spec');plan=self.m.plan(self.case.root,'demo');packet=self.c.packet('groom-spec',assessed,plan);route=self.c.route('groom-spec',plan)
        value=self.case.worker('groom-spec',packet,route,None,1);value['status']='FAIL';value['results'].update(decision='repair',findings=['Synthetic semantic failure'])
        output=self.case.root/'failure-response.json';runner=self.m.load('controller-recovery');real_load=self.m.load
        for code,change,accepted in [(1,None,True),(2,None,False),(1,'binding',False),(1,'provider',False)]:
            with self.subTest(code=code,change=change):
                response=copy.deepcopy(value)
                if change=='binding':response['results']['binding']='0'*64
                if change=='provider':response['artifacts']['provider']='unbound-provider'
                def bounded(*args):output.write_text(json.dumps(response));return code
                with patch.object(runner,'bounded',bounded),patch.object(self.m,'load',side_effect=lambda name:runner if name=='controller-recovery' else real_load(name)):
                    if accepted:self.assertEqual(self.c.dispatch('groom-spec',packet,route,output,1),response)
                    else:
                        with self.assertRaisesRegex(ValueError,'provider_exit:'):self.c.dispatch('groom-spec',packet,route,output,1)

if __name__=='__main__':unittest.main()
