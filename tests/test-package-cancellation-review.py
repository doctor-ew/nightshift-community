#!/usr/bin/env python3
"""Independent parent cancellation propagation through synthetic package operations."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('package_cancel_fixture',ROOT/'tests/test-package-controller.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m;r=m.ops.load('operation-reconciliation')

class ParentCancellation(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-parent-cancel-review-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();f.fixture(self.root);self.worker=f.f.f.Worker()
        self.c=m.Packages(self.root,'demo',self.worker)
        a=self.c.preparation.assess('groom-spec')
        self.c.preparation.authorize(m.ops.RECIPES['groom'],a['binding'],'synthetic','prepare')
        result=self.c.prepare('prepare');self.assertEqual(result['status'],'ready',result)
        self.g=self.c.authorize(result['binding'],'synthetic','compose')
    def cancel(self):
        other=m.Packages(self.root,'demo',self.worker)
        return r.cancel(other,self.g['id'],self.g['cancellation_binding'],'synthetic','parent-cancel')
    def blocked_run(self):
        try:result=self.c.run(self.g['id'])
        except ValueError as error:self.assertIn('cancel',str(error));return
        self.assertEqual(result['status'],'blocked',result)
    def test_cancel_before_children_prevents_all_dispatch_on_restart(self):
        calls=list(self.worker.calls);receipt=self.cancel();self.assertEqual(receipt,self.cancel())
        self.c=m.Packages(self.root,'demo',self.worker);self.blocked_run()
        self.assertFalse(self.c.state['children']);self.assertEqual(self.worker.calls,calls)
    def test_parent_cancel_during_active_child_blocks_result_and_later_children(self):
        worker=self.worker;before=len(worker.calls);cancelled=False
        def cancelling(*args):
            nonlocal cancelled
            value=worker(*args)
            if not cancelled:cancelled=True;self.cancel()
            return value
        self.c.worker=cancelling;self.blocked_run()
        self.assertEqual(len(worker.calls),before+1)
        self.assertEqual(len(self.c.state['children']),1)
        child=self.c.child(next(iter(self.c.state['children'])))
        self.assertNotIn('groom-spec',child.state['results'])
        grant=next(iter(child.state['authorizations']))
        self.assertIsNotNone(r.effective_intent(child,grant))
        with self.assertRaisesRegex(ValueError,'cancel'):child.execute(grant,'groom-spec','fresh-child-request')
        self.assertNotEqual(self.c.state['authorizations'][self.g['id']]['status'],'pending_manual_acceptance')
    def test_crash_after_child_authorization_cannot_escape_parent_cancellation(self):
        authorize=m.ops.Operations.authorize;created=[]
        def crash_after_authorize(controller,*args,**kwargs):
            grant=authorize(controller,*args,**kwargs)
            if controller.task!='demo':
                created.append((controller.task,grant['id']))
                raise KeyboardInterrupt('synthetic crash after durable child authorization')
            return grant
        with patch.object(m.ops.Operations,'authorize',new=crash_after_authorize):
            with self.assertRaises(KeyboardInterrupt):self.c.run(self.g['id'])
        self.assertEqual(len(created),1);self.cancel();calls=list(self.worker.calls)
        child=self.c.child(created[0][0])
        with self.assertRaisesRegex(ValueError,'cancel'):
            child.execute(created[0][1],'groom-spec','direct-child-after-crash')
        self.assertEqual(self.worker.calls,calls)
    def test_existing_cancelled_parent_restriction_survives_child_grant_reuse(self):
        prior=self.root/'.git'/'prior-parent-cancel.json';binding='b'*64
        prior.write_text(json.dumps(dict(version=1,payload=dict(grant='prior-parent',binding=binding,operator='synthetic'))))
        authorize=m.ops.Operations.authorize;injected=[];calls=list(self.worker.calls)
        def retained_grant(controller,*args,**kwargs):
            grant=authorize(controller,*args,**kwargs)
            if controller.task!='demo' and not injected:
                with controller.lease():
                    controller.state['authorizations'][grant['id']]['parent_cancellations']=[dict(path=str(prior),binding=binding)]
                    controller.save()
                injected.append(controller.task)
            return grant
        with patch.object(m.ops.Operations,'authorize',new=retained_grant):self.blocked_run()
        self.assertEqual(len(injected),1);self.assertEqual(self.worker.calls,calls)
        child=self.c.child(injected[0]);grant=next(iter(child.state['authorizations'].values()))
        parents=grant['parent_cancellations']
        self.assertTrue(any(parent['binding']==binding for parent in parents))
        self.assertTrue(any(parent['binding']==self.g['cancellation_binding'] for parent in parents))
        self.assertIsNotNone(r.effective_intent(child,grant['id']))
    def test_cancel_after_first_completed_child_prevents_next_materialization(self):
        save=self.c.save;cancelled=False
        def save_then_cancel():
            nonlocal cancelled
            save();allocations=self.c.state['authorizations'][self.g['id']]['allocations']
            if not cancelled and any(a['status']=='complete' for a in allocations.values()):
                cancelled=True;self.cancel()
        with patch.object(self.c,'save',side_effect=save_then_cancel):self.blocked_run()
        self.assertTrue(cancelled);self.assertEqual(len(self.c.state['children']),1)
        child=self.c.child(next(iter(self.c.state['children'])))
        self.assertEqual(child.assess('review')['status'],'current')
        calls=list(self.worker.calls);self.blocked_run();self.assertEqual(self.worker.calls,calls)
    def test_cancel_before_parent_acceptance_retains_completed_integration(self):
        save=self.c.save;cancelled=False
        def save_then_cancel():
            nonlocal cancelled
            save();allocations=self.c.state['authorizations'][self.g['id']]['allocations']
            if not cancelled and all(a['status']=='complete' for a in allocations.values()):
                cancelled=True;self.cancel()
        with patch.object(self.c,'save',side_effect=save_then_cancel):self.blocked_run()
        self.assertTrue(cancelled)
        self.assertEqual(self.c.child('integration').assess('review')['status'],'current')
        self.assertNotEqual(self.c.state['authorizations'][self.g['id']]['status'],'pending_manual_acceptance')
        calls=list(self.worker.calls);self.blocked_run();self.assertEqual(self.worker.calls,calls)

if __name__=='__main__':unittest.main()
