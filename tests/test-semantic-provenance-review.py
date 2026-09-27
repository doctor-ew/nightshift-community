#!/usr/bin/env python3
"""Independent typed evidence and escalation regressions, synthetic providers only."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

class SemanticProvenanceReview(unittest.TestCase):
    def setUp(self):
        home=tempfile.TemporaryDirectory(prefix='nightshift-semantic-provenance-');self.addCleanup(home.cleanup)
        directory=Path(home.name).resolve()
        env={'HOME':str(directory),'NIGHTSHIFT_HOME':str(directory/'.nightshift'),'XDG_CONFIG_HOME':str(directory/'config'),
             'PATH':os.environ['PATH'],'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null','PYTHONDONTWRITEBYTECODE':'1'}
        guard=patch.dict(os.environ,env,clear=True);guard.start();self.addCleanup(guard.stop)
        spec=importlib.util.spec_from_file_location('provenance_fixture',ROOT/'tests/test-semantic-handoffs.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
        self.f=f;self.case=f.Handoffs();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.b=f.b;self.c=self.case.c;self.plan=self.case.plan
    def edit(self,fn):
        data=json.loads(self.case.path.read_text());fn(data);self.case.path.write_text(json.dumps(data))
    def packets(self):return self.b.packets(self.c,self.plan,[],'groom-adversarial')
    def worker_edit(self,fn):
        original=self.c.worker
        def worker(operation,packet,*args):
            value=original(operation,packet,*args)
            return fn(value,packet) if 'semantic-obligation' in packet.get('artifacts',{}) else value
        self.c.worker=worker
    def assert_blocked(self):
        grant,result=self.case.run_handoff()
        self.assertEqual(result['status'],'failed',result);self.assertNotIn('groom-adversarial',self.c.state['results'])
        usage=self.c.usage(grant['id']);self.assertEqual(usage['unknown'],0)
        self.assertLessEqual(usage['calls'],grant['aggregate']['calls'])
        return grant,result
    def test_permuted_roles_rejected_before_evaluator(self):
        def mutate(data):
            for row in data['obligations']:
                for ref in row['references']:ref['role']={'requirement':'assertion','assertion':'source','source':'requirement'}[ref['role']]
        self.edit(mutate)
        with self.assertRaisesRegex(ValueError,'reference_role_mismatch'):self.packets()
        self.assertFalse(self.case.calls)
    def test_one_obligation_cannot_borrow_other_rows_constraint_context(self):
        def mutate(data):
            row=data['obligations'][0];removed={r['id'] for r in row['references'] if r['path']=='rules.md'}
            row['references']=[r for r in row['references'] if r['id'] not in removed]
            for requirement in row['requirements']:requirement['evidence']=[r for r in requirement['evidence'] if r not in removed]
        self.edit(mutate)
        with self.assertRaisesRegex(ValueError,'semantic_context_incomplete:rules.md'):self.packets()
        self.assertFalse(self.case.calls)
    def test_each_obligation_requires_exact_case_identity(self):
        self.edit(lambda data:data['obligations'][0]['requirements'][0].update(id='unrelated-case'))
        with self.assertRaisesRegex(ValueError,'semantic_case_mapping_incomplete'):self.packets()
        self.assertFalse(self.case.calls)
    def test_noncontract_file_cannot_be_labelled_requirement(self):
        def mutate(data):
            for ref in data['obligations'][0]['references']:
                if ref['path']=='rules.md':ref['role']='requirement'
        self.edit(mutate)
        with self.assertRaisesRegex(ValueError,'reference_role_mismatch'):self.packets()
    def test_generic_coverage_does_not_attest_all_evidence(self):
        def mutate(value,packet):
            value['results']['coverage']=[x for x in value['results']['coverage'] if not x.startswith(('evidence:','requirement:','finding:'))];return value
        self.worker_edit(mutate);self.assert_blocked()
        reviews=[json.loads(p.read_text()) for p in (self.c.directory/'decisions').glob('*.review.json')]
        self.assertTrue(reviews);self.assertEqual(reviews[0]['evidence'],[])
    def test_partial_returned_evidence_is_retained_without_invention(self):
        missing=[]
        def mutate(value,packet):
            evidence=next(x for x in packet['semantic_coverage'] if x.startswith('evidence:'));missing.append(evidence.split(':',1)[1])
            value['results']['coverage'].remove(evidence);return value
        self.worker_edit(mutate);self.assert_blocked()
        reviews=[json.loads(p.read_text()) for p in (self.c.directory/'decisions').glob('*.review.json')]
        self.assertTrue(reviews[0]['evidence']);self.assertNotIn(missing[0],reviews[0]['evidence'])
    def test_missing_requirement_coverage_blocks_even_with_all_references(self):
        def mutate(value,packet):
            value['results']['coverage']=[x for x in value['results']['coverage'] if not x.startswith('requirement:')];return value
        self.worker_edit(mutate);self.assert_blocked()
    def test_missing_finding_coverage_blocks_even_with_all_references(self):
        text='Retained synthetic finding'
        with self.c.lease():
            self.c.state['attempts'].append(dict(operation='review',status='failed',findings=[text],signature='synthetic-old',request='synthetic-finding'))
            self.c.save()
        def mapping(data):
            for row in data['obligations']:
                row['findings']=[dict(id=self.b.engine.text_hash(text),text=text,evidence=[ref['id'] for ref in row['references']])]
        self.edit(mapping)
        def mutate(value,packet):
            self.assertTrue(any(x.startswith('finding:') for x in packet['semantic_coverage']))
            value['results']['coverage']=[x for x in value['results']['coverage'] if not x.startswith('finding:')];return value
        self.worker_edit(mutate);self.assert_blocked()
    def test_malformed_entire_escalation_response_is_bounded(self):
        self.worker_edit(lambda value,packet:None);self.assert_blocked()
    def test_positive_and_abstaining_evaluator_use_explicit_coverage(self):
        self.case.score=.5;grant,result=self.case.run_handoff();self.assertEqual(result['status'],'passed',result)
        record=self.c.state['results']['groom-adversarial']['semantic']
        self.assertEqual(len(self.case.calls),3);self.assertEqual(self.c.usage(grant['id'])['calls'],8)
        packets=self.packets()
        for packet,receipt in zip(packets,record['receipts']):self.assertEqual(receipt['escalation']['evidence'],[r['id'] for r in packet['evidence']])
    def test_negative_evaluator_cannot_be_overridden_by_positive_review(self):
        self.case.score=.01;self.assert_blocked()
    def test_missing_escalation_allowance_never_launches_reviewer(self):
        self.plan['limits']['groom-adversarial']['calls']=2
        (self.case.root/'docs/demo/operations.json').write_text(json.dumps(self.plan))
        grant,result=self.assert_blocked();self.assertIn('provider_call_limit_exhausted',result['reason'])
        self.assertEqual(len(self.case.worker.calls),2);self.assertEqual(len(self.case.calls),1)
    def test_malformed_escalation_results_fail_with_bounded_outcome(self):
        self.worker_edit(lambda value,packet:dict(value,results=None));self.assert_blocked()

if __name__=='__main__':unittest.main()
