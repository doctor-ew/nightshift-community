#!/usr/bin/env python3
"""Explicit optional CI repair composition; synthetic host/providers only."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('handoff_fixture',ROOT/'tests/test-delivery-repair-review.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class Handoff(unittest.TestCase):
    setUp=f.DeliveryRepairReview.setUp
    git=f.DeliveryRepairReview.git
    write_profile=f.DeliveryRepairReview.write_profile
    child_grant=f.DeliveryRepairReview.child_grant
    patch_source=f.DeliveryRepairReview.patch
    impl_calls=f.DeliveryRepairReview.impl_calls
    accept=f.DeliveryRepairReview.accept
    def endpoint(self,child=None,operator='synthetic'):
        self.n+=1;a=self.delivery.assess('deliver')
        g=self.delivery.authorize('deliver',a['binding'],operator,'endpoint-'+str(self.n),repair_grant=child)
        return g['id'],'endpoint-run-'+str(self.n)
    def fail_ci(self,conclusion='failure'):
        original=self.host.ci
        def ci(*args):
            row=original(*args);row['checks'][0].update(conclusion=conclusion,output=dict(summary='Synthetic integration assertion failed',text='Expected answer() == 2'))
            return row
        self.host.ci=ci
    def crash_registration(self,g,r):
        original=self.c.save;stopped=[]
        def save():
            original()
            records=self.delivery.state().get('compositions',{})
            if not stopped and any(row.get('repair') for row in records.values()):
                stopped.append(True);raise KeyboardInterrupt('after durable CI repair registration')
        with patch.object(self.c,'save',side_effect=save):
            with self.assertRaises(KeyboardInterrupt):self.delivery.execute(g,r)
        self.assertTrue(stopped)
    def adopt(self):
        (self.root/'app.py').write_text('def answer(): return 2 # external CI repair\n')
        a=self.c.assess('adopt');g=self.c.authorize(['adopt'],a['binding'],'synthetic','handoff-external',dict(binding=a['binding'],identity='external-synthetic',provider='human'))
        self.assertEqual(self.c.execute(g['id'],'adopt','handoff-external-run')['status'],'passed')
    def verify_review(self):
        a=self.c.assess('verify');g=self.c.authorize(['verify','review'],a['binding'],'synthetic','handoff-external-verify')
        result=self.c.chain(g['id']);self.assertTrue(all(row['status'] in ('passed','reused') for row in result['results']),result)
    def test_explicit_handoff_repairs_once_then_requires_acceptance(self):
        child=self.child_grant();deadline=self.c.state['authorizations'][child]['deadline'];self.fail_ci();g,r=self.endpoint(child);before=self.impl_calls();self.patch_source(1)
        result=self.delivery.execute(g,r);self.assertEqual(result['status'],'needs_acceptance',result)
        self.assertEqual(self.impl_calls(),before+1);self.assertEqual((self.host.pushes,self.host.creates,self.host.merges),(1,1,0))
        self.assertEqual(self.c.assess('verify')['status'],'current');self.assertEqual(self.c.assess('review')['status'],'current');self.assertNotEqual(self.c.assess('accept')['status'],'current')
        self.assertLessEqual(self.c.state['authorizations'][child]['deadline'],deadline)
        count=len(self.worker.calls);replay=self.delivery.execute(g,'new-ui-request');self.assertEqual(replay['status'],'needs_acceptance');self.assertEqual(len(self.worker.calls),count)
        self.assertEqual(self.host.pushes,1)
    def test_unknown_ci_with_repair_authority_does_not_implement(self):
        child=self.child_grant();self.fail_ci('timed_out');g,r=self.endpoint(child);before=self.impl_calls()
        self.assertEqual(self.delivery.execute(g,r)['status'],'ci_unknown');self.assertEqual(self.impl_calls(),before);self.assertFalse(self.delivery.state()['ci_failures'])
    def test_no_repair_authority_stops_at_failed_ci(self):
        self.fail_ci();g,r=self.endpoint();before=self.impl_calls();self.assertEqual(self.delivery.execute(g,r)['status'],'ci_failed');self.assertEqual(self.impl_calls(),before)
    def test_unbound_execute_argument_cannot_create_repair_authority(self):
        g,r=self.endpoint();child=self.child_grant()
        with self.assertRaisesRegex(ValueError,'repair_grant_requires_repair_action'):self.delivery.execute(g,r,repair_grant=child)
        self.assertEqual(self.host.pushes,0)
    def test_wrong_operator_or_missing_repair_grant_rejected_before_effect(self):
        child=self.child_grant()
        for selected,operator in [('missing','synthetic'),(child,'other-operator')]:
            with self.subTest(selected=selected,operator=operator):
                with self.assertRaises(ValueError):self.endpoint(selected,operator)
        self.assertEqual(self.host.pushes,0);self.assertEqual(self.git('rev-parse','HEAD'),self.base)
    def test_crash_registration_replays_without_duplicate_implementation(self):
        child=self.child_grant();self.fail_ci();g,r=self.endpoint(child);before=self.impl_calls();self.crash_registration(g,r)
        self.assertEqual(self.impl_calls(),before);self.patch_source(1)
        self.c=m.Operations(self.root,'demo',self.worker);self.delivery=f.f.d.Delivery(self.c,self.host)
        result=self.delivery.execute(g,r);self.assertEqual(result['status'],'needs_acceptance',result)
        self.assertEqual(self.impl_calls(),before+1);self.assertEqual(self.host.pushes,1);self.assertEqual(len(self.delivery.state()['ci_failures']),1)
    def test_external_adopt_continues_verification_without_implementation(self):
        child=self.child_grant();self.fail_ci();g,r=self.endpoint(child);self.crash_registration(g,r);before=self.impl_calls();self.adopt()
        result=self.delivery.execute(g,r);self.assertEqual(result['status'],'blocked');self.assertEqual(self.impl_calls(),before)
        self.verify_review();result=self.delivery.execute(g,r);self.assertEqual(result['status'],'needs_acceptance',result);self.assertEqual(self.impl_calls(),before)
    def test_parent_cancellation_blocks_handoff_and_bound_child(self):
        child=self.child_grant();self.fail_ci();g,r=self.endpoint(child);original=self.delivery.resume_repair;before=self.impl_calls()
        def cancel(*args):
            rec=m.load('operation-reconciliation');rec.cancel(self.c,g,rec.identity(self.c,self.c.state['authorizations'][g]),'synthetic','cancel-handoff')
            return original(*args)
        with patch.object(self.delivery,'resume_repair',side_effect=cancel):
            with self.assertRaisesRegex(ValueError,'cancelled'):self.delivery.execute(g,r)
        with self.assertRaisesRegex(ValueError,'cancelled'):self.c.cancellation_check(child)
        self.assertEqual(self.impl_calls(),before)
    def test_changed_accepted_source_starts_explicit_new_window_only(self):
        child=self.child_grant();original_factory_deadline=self.c.state['authorizations'][child]['deadline'];g,r=self.endpoint();deadline=self.c.state['authorizations'][g]['deadline']
        self.c.clock=lambda:deadline+1
        duplicate,_=self.endpoint(operator='different-explicit-operator')
        self.assertEqual(self.c.state['authorizations'][duplicate]['deadline'],deadline)
        self.adopt();self.verify_review();self.accept();before=self.impl_calls();fresh,_=self.endpoint()
        self.assertGreater(self.c.state['authorizations'][fresh]['deadline'],deadline)
        self.assertEqual(self.c.state['authorizations'][child]['deadline'],original_factory_deadline);self.assertEqual(self.impl_calls(),before)

if __name__=='__main__':unittest.main()
