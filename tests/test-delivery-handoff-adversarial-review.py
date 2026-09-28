#!/usr/bin/env python3
"""Independent authorization-boundary review of the optional CI handoff."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('handoff_adversarial_fixture',ROOT/'tests/test-delivery-handoff-review.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class HandoffAuthority(unittest.TestCase):
    setUp=f.Handoff.setUp
    git=f.Handoff.git
    def write_profile(self):
        if self._testMethodName=='test_mixed_failed_and_pending_ci_does_not_implement':self.profile['checks'].append(dict(name='other-required',app_id=2))
        return f.Handoff.write_profile(self)
    child_grant=f.Handoff.child_grant
    endpoint=f.Handoff.endpoint
    fail_ci=f.Handoff.fail_ci
    impl_calls=f.Handoff.impl_calls
    crash_registration=f.Handoff.crash_registration
    def test_duplicate_authorization_cannot_replace_bound_factory_grant(self):
        first=self.child_grant();a=self.c.assess('groom-spec')
        second=self.c.authorize(m.RECIPES['factory'],a['binding'],'synthetic','different-explicit-factory',dict(bounded_repair=True,synthetic_case='different-explicit-authority'))['id']
        self.assertNotEqual(first,second)
        assessed=self.delivery.assess('deliver');g=self.delivery.authorize('deliver',assessed['binding'],'synthetic','fixed-parent-request',repair_grant=first)
        with self.assertRaisesRegex(ValueError,'delivery_request_conflict'):
            self.delivery.authorize('deliver',assessed['binding'],'synthetic','fixed-parent-request',repair_grant=second)
        self.c.reload();self.assertEqual(self.delivery.state()['grants'][g['id']]['repair_authority']['grant'],first)
        self.assertEqual(self.host.pushes,0)
    def test_crash_after_parent_authorization_already_binds_child_cancellation(self):
        child=self.child_grant();assessed=self.delivery.assess('deliver');save=self.c.save
        def crash():save();raise KeyboardInterrupt('after atomic parent and delegated child persistence')
        with patch.object(self.c,'save',side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):self.delivery.authorize('deliver',assessed['binding'],'synthetic','parent-before-any-effect',repair_grant=child)
        restarted=m.Operations(self.root,'demo',self.worker);restarted.reload();parent=restarted.state['authorizations']['parent-before-any-effect']
        delegated=restarted.state['authorizations'][child];self.assertLessEqual(delegated['deadline'],parent['deadline'])
        reconciliation=m.load('operation-reconciliation');reconciliation.cancel(restarted,parent['id'],reconciliation.identity(restarted,parent),'synthetic','cancel-after-parent-crash')
        with self.assertRaisesRegex(ValueError,'cancelled'):restarted.cancellation_check(child)
        self.assertEqual(self.host.pushes,0);self.assertEqual(self.git('rev-parse','HEAD'),self.base)

    def stale_handoff(self,queued=False):
        child=self.child_grant();original_ci=self.host.ci;self.fail_ci();g,r=self.endpoint(child);before=self.impl_calls();save=self.c.save;stopped=[]
        def crash():
            save()
            if not stopped and any(row.get('repair_handoff') and not row.get('repair') for row in self.delivery.state().get('compositions',{}).values()):
                stopped.append(True);raise KeyboardInterrupt('after failed CI intent before repair registration')
        with patch.object(self.c,'save',side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):self.delivery.execute(g,r)
        self.assertTrue(stopped);self.host.ci=original_ci
        if queued:
            self.host.observation=original_ci(self.profile,1);self.host.observation['checks'][0].update(status='queued',conclusion=None)
        try:self.delivery.execute(g,r)
        except ValueError:pass
        self.assertEqual(self.impl_calls(),before);self.assertFalse(self.delivery.state()['ci_failures'])
    def test_passing_ci_rerun_invalidates_unregistered_failed_handoff(self):self.stale_handoff()
    def test_queued_ci_rerun_does_not_authorize_repair_from_old_failure(self):self.stale_handoff(True)
    def test_expired_delivery_cycle_cannot_shorten_new_factory_grant(self):
        g,r=self.endpoint();self.c.clock=lambda:self.delivery.state()['grants'][g]['deadline']+1
        child=self.child_grant();deadline=self.c.state['authorizations'][child]['deadline'];parents=list(self.c.state['authorizations'][child].get('parent_cancellations',[]))
        with self.assertRaisesRegex(ValueError,'deadline|expired'):self.endpoint(child)
        self.c.reload();self.assertEqual(self.c.state['authorizations'][child]['deadline'],deadline)
        self.assertEqual(self.c.state['authorizations'][child].get('parent_cancellations',[]),parents)

    def registered_handoff_changed(self,move_base=False,move_branch=False,direct=False):
        child=self.child_grant();original_ci=self.host.ci;self.fail_ci();g,r=self.endpoint(child);before=self.impl_calls();self.crash_registration(g,r)
        if move_base:self.host.references['base']='f'*40
        elif move_branch:self.git('checkout','-qb','operator-other-branch')
        else:self.host.ci=original_ci
        try:
            if direct:self.delivery.resume_repair(g,r)
            else:self.delivery.execute(g,r)
        except ValueError:pass
        self.assertEqual(self.impl_calls(),before)
        self.assertEqual(len(self.delivery.state()['ci_failures']),1)
    def test_registered_undispatched_handoff_rechecks_passing_ci(self):self.registered_handoff_changed()
    def test_registered_undispatched_handoff_rechecks_remote_base(self):self.registered_handoff_changed(True)
    def test_registered_undispatched_handoff_rechecks_local_branch(self):self.registered_handoff_changed(move_branch=True)
    def test_direct_resume_cannot_bypass_registered_handoff_freshness(self):self.registered_handoff_changed(direct=True)
    def test_active_delivery_profile_cannot_publish_itself(self):
        name='docs/demo/delivery.json';self.plan['scope'].append(name);self.profile['files'].append(name)
        (self.root/'docs/demo/operations.json').write_text(json.dumps(self.plan));self.write_profile()
        with self.assertRaisesRegex(ValueError,'private|control|profile'):m.load('delivery').profile(self.c)
    def test_active_operation_plan_cannot_publish_as_request_artifact(self):
        name='docs/demo/operations.json';self.plan['inputs']['request']=name;self.profile['files'].append(name)
        (self.root/name).write_text(json.dumps(self.plan));self.write_profile()
        with self.assertRaisesRegex(ValueError,'private|control|plan'):m.load('delivery').profile(self.c)

    def standalone_changed(self,move_base=False,move_branch=False):
        g,r=self.endpoint();self.assertEqual(self.delivery.execute(g,r)['status'],'ci_passed')
        child=self.child_grant();original_ci=self.host.ci;self.fail_ci();assessed=self.delivery.assess('repair')
        grant=self.delivery.authorize('repair',assessed['binding'],'synthetic','standalone-adversarial-repair')
        self.delivery.execute(grant['id'],'standalone-adversarial-run',repair_grant=child)
        if move_base:self.host.references['base']='f'*40
        elif move_branch:self.git('checkout','-qb','operator-standalone-branch')
        else:self.host.ci=original_ci
        before=self.impl_calls()
        try:self.delivery.resume_repair(grant['id'],'standalone-adversarial-run')
        except ValueError:pass
        self.assertEqual(self.impl_calls(),before);self.assertEqual(len(self.delivery.state()['ci_failures']),1)

    def test_standalone_registered_repair_rechecks_current_ci_before_dispatch(self):self.standalone_changed()
    def test_standalone_registered_repair_rechecks_remote_base(self):self.standalone_changed(move_base=True)
    def test_standalone_registered_repair_rechecks_local_branch(self):self.standalone_changed(move_branch=True)

    def test_mixed_failed_and_pending_ci_does_not_implement(self):
        child=self.child_grant();self.fail_ci();original=self.host.ci
        def ci(*args):
            row=original(*args);row['checks'].append(dict(name='other-required',app_id=2,id=8,head=row['merge'],status='queued',conclusion=None));return row
        self.host.ci=ci;g,r=self.endpoint(child);before=self.impl_calls()
        result=self.delivery.execute(g,r);self.assertEqual(result['status'],'ci_unknown')
        self.assertEqual(self.impl_calls(),before);self.assertFalse(self.delivery.state()['ci_failures'])

if __name__=='__main__':unittest.main()
