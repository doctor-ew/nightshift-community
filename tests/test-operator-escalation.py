#!/usr/bin/env python3
"""Escalation to the operator instead of ending the session. Synthetic reviewers only."""
import importlib.util
import json
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('independent_fixture',Path(__file__).with_name('test-recovery-independent-review.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m


class OperatorEscalation(f.IndependentRecovery):
    def unsure_on(self,target):
        def review(value,packet,mode,output,timeout,reviewer_id=None,missing_roles=None):
            result=self.independent_review(value,packet,mode,output,timeout,reviewer_id,missing_roles)
            if packet['id']==target:result['decision']='abstain'
            return result
        return review

    def start(self):
        self.setup_independent();a=self.assess();first=m.load('recovery-decisions').packets
        result=self.recover(expected=a['sha256'],review=self.unsure_on('requirement_supported'))
        return a['sha256'],result

    def test_abstention_waits_for_the_operator_without_ending_the_session(self):
        binding,result=self.start()
        self.assertEqual((result['status'],result['next_action']),('awaiting_operator','operator_decision'),result)
        self.assertEqual(result['awaiting']['packet_id'],'requirement_supported')
        self.assertEqual(result['awaiting']['reason'],'decision_abstained')
        again=self.recover(operation='authorize',expected=binding,review=self.unsure_on('requirement_supported'))
        self.assertEqual(again['status'],'awaiting_operator');self.assertEqual(len(self.review_calls),1)

    def test_operator_yes_resumes_without_re_asking(self):
        binding,result=self.start();calls=len(self.review_calls)
        m.operator_decide(self.project,'T-1',binding,'synthetic-operator',result['awaiting']['packet_sha256'],'yes','Assertion and output inspected directly.')
        done=self.recover(operation='resume',expected=binding,review=self.unsure_on('requirement_supported'))
        self.assertEqual(done['status'],'pending_manual_acceptance',done)
        self.assertEqual(self.review_calls.count('requirement_supported'),1)  # decided question is never re-asked
        self.assertEqual(done['allowance']['calls_used'],len(self.review_calls))
        session=next(iter(m.p.snapshot(self.project,'T-1')['recovery_sessions'].values()))
        self.assertEqual([d['decision'] for d in session['operator_decisions']],['yes'])
        self.assertEqual(len(session['allowance']['operator_pauses']),1)
        self.assertTrue(session['operator_waits'])

    def test_operator_no_fails_the_gate(self):
        binding,result=self.start()
        m.operator_decide(self.project,'T-1',binding,'synthetic-operator',result['awaiting']['packet_sha256'],'no','Evidence does not show it.')
        done=self.recover(operation='resume',expected=binding,review=self.unsure_on('requirement_supported'))
        self.assertEqual(done['status'],'blocked');self.assertIn('operator_rejected',done['reason'])

    def test_operator_decision_is_bound_and_single(self):
        binding,result=self.start();sha=result['awaiting']['packet_sha256']
        with self.assertRaisesRegex(ValueError,'packet_mismatch'):m.operator_decide(self.project,'T-1',binding,'op','0'*64,'yes','r')
        with self.assertRaisesRegex(ValueError,'identity'):m.operator_decide(self.project,'T-1',binding,'  ',sha,'yes','r')
        with self.assertRaisesRegex(ValueError,'decision_invalid'):m.operator_decide(self.project,'T-1',binding,'op',sha,'maybe','r')
        m.operator_decide(self.project,'T-1',binding,'op',sha,'yes','ok')
        with self.assertRaisesRegex(ValueError,'already_decided'):m.operator_decide(self.project,'T-1',binding,'op',sha,'no','changed mind')

    def test_decision_when_nothing_is_awaited_is_refused(self):
        self.setup_independent();a=self.assess()
        self.assertEqual(self.recover(expected=a['sha256'])['status'],'pending_manual_acceptance')
        with self.assertRaisesRegex(ValueError,'not_awaited'):m.operator_decide(self.project,'T-1',a['sha256'],'op','0'*64,'yes','r')

    def test_tampered_operator_record_is_rejected_on_validation(self):
        binding,result=self.start();sha=result['awaiting']['packet_sha256']
        m.operator_decide(self.project,'T-1',binding,'op',sha,'yes','ok')
        self.assertEqual(self.recover(operation='resume',expected=binding,review=self.unsure_on('requirement_supported'))['status'],'pending_manual_acceptance')
        path=m.operator_record(m.p.root(self.project,'T-1')/('recovery-'+binding),sha)
        record=json.loads(path.read_text());record['decision']='yes';record['reason']='edited later';path.write_text(json.dumps(record))
        session=next(iter(m.p.snapshot(self.project,'T-1')['recovery_sessions'].values()))
        report=m.p.read(session['steps']['adoption']['receipt']);checks=m.p.read(m.p.root(self.project,'T-1')/('recovery-'+binding)/'verify.json')
        with self.assertRaisesRegex(ValueError,'unapproved'):m.validate_compact(report,session['evidence'],'adoption',checks)


for _name in [n for n in dir(OperatorEscalation) if n.startswith('test_') and n not in OperatorEscalation.__dict__]:
    setattr(OperatorEscalation,_name,None)

if __name__=='__main__':unittest.main()
