#!/usr/bin/env python3
"""Exact retained-failure context; synthetic repositories and reviewers only."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('recovery_fixture',Path(__file__).with_name('test-recovery-independent-review.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class Categories(unittest.TestCase):
    def test_only_exact_unique_failed_attempt_supplies_category(self):
        finding=dict(id='kept-id',target='/retained/attempt.json',problem='stage_receipt.task:wrong_type')
        attempt=dict(status='fail',receipt=finding['target'],reason=finding['problem'],category='schema')
        for category in ('schema','transport','substantive'):
            self.assertEqual(m.finding_category(finding,[dict(attempt,category=category)]),category)
        for attempts in ([],[dict(attempt,status='pass')],[dict(attempt,receipt='attempt.json')],[dict(attempt,reason='other')],[dict(attempt,category='success')],[dict(attempt,category=None)],[attempt,attempt],[attempt,dict(attempt,category='transport')]):
            self.assertEqual(m.finding_category(finding,attempts),'unknown')
        self.assertEqual(m.finding_category(dict(finding,target=None),[attempt]),'unknown')

class FindingContext(f.IndependentRecovery):
    def configure(self,category):
        receipt=self.directory/'retained-failure.json';receipt.write_text('{"invalid":"retained unchanged"}')
        finding=dict(id='original-finding',target=str(receipt),problem='original recorded failure')
        self.state['findings']=[finding]
        self.state['attempts'].append(dict(status='fail',receipt=str(receipt),reason=finding['problem'],category=category))
        m.p.recovery.atomic(self.directory/'state.json',self.state)
        self.original_finding=copy.deepcopy(finding);self.failed_receipt=receipt
        self.setup_independent()

    def test_metadata_preserves_stable_finding_identity_and_failed_evidence(self):
        self.configure('schema');before=self.failed_receipt.read_bytes();assessment=self.assess()
        finding=next(row for row in assessment['evidence']['findings'] if row['source']=='controller')
        self.assertEqual(finding['id'],m.digest(self.original_finding))
        self.assertEqual(finding['finding'],self.original_finding)
        self.assertEqual(finding['failure_category'],'schema')
        result=self.recover(expected=assessment['sha256'])
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(self.failed_receipt.read_bytes(),before)
        self.assertEqual(m.p.snapshot(self.project,'T-1')['attempts'],self.state['attempts'])
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)
        question=next(e['packet']['question'] for e in self.envelopes if e['packet']['kind']=='finding_resolved')
        self.assertIn('preserving the original failed receipt',question)
        self.assertIn('"failure_category": "schema"',question)

    def test_metadata_changes_packet_and_authority_cache_identity(self):
        self.configure('transport');value=self.assess()['evidence']
        checks=m.verify_checks(value,timeout=30)
        adapter=m.load('recovery-decisions')
        first=next(p for p in adapter.packets(value,checks,'adoption') if p['kind']=='finding_resolved')
        changed=copy.deepcopy(value)
        next(f for f in changed['findings'] if f['source']=='controller')['failure_category']='unknown'
        second=next(p for p in adapter.packets(changed,checks,'adoption') if p['kind']=='finding_resolved')
        self.assertNotEqual(m.digest(value),m.digest(changed))
        self.assertNotEqual(adapter.engine.digest(first),adapter.engine.digest(second))
        self.assertEqual(first['findings'],second['findings'])

    def test_substantive_finding_negative_never_adopts(self):
        self.configure('substantive');before=self.failed_receipt.read_bytes()
        def reviewer(value,packet,mode,output,timeout,reviewer_id=None):
            result=self.independent_review(value,packet,mode,output,timeout,reviewer_id)
            if packet['kind']=='finding_resolved':
                self.assertIn('Substantive findings require actual resolution',packet['question'])
                self.assertIn('"failure_category": "substantive"',packet['question'])
                result['decision']='no'
            return result
        result=self.recover(review=reviewer)
        self.assertEqual(result['status'],'blocked')
        self.assertNotIn('implement',m.p.snapshot(self.project,'T-1')['completed'])
        self.assertEqual(self.failed_receipt.read_bytes(),before)
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)

for name in dir(f.IndependentRecovery):
    if name.startswith('test_') and name not in FindingContext.__dict__:setattr(FindingContext,name,None)
if __name__=='__main__':unittest.main()
