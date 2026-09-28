#!/usr/bin/env python3
"""Endpoint composition regressions using accepted disposable repositories and a fake host."""
import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('delivery_composition_fixture',ROOT/'tests/test-delivery-review.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
d=f.d

class Composition(unittest.TestCase):
    setUp=f.DeliveryReview.setUp
    git=f.DeliveryReview.git
    def write_profile(self):
        if self._testMethodName=='test_merge_response_moved_head_cannot_claim_integrated':self.profile['merge_policy']='protected-squash'
        if self._testMethodName=='test_changed_check_script_cannot_be_omitted':
            check=self.root/'test_app.py';check.write_text(check.read_text()+'# accepted changed check source\n')
        return f.DeliveryReview.write_profile(self)
    authority=f.DeliveryReview.authority
    run_action=f.DeliveryReview.run_action
    prepared=f.DeliveryReview.prepared
    def cancel(self,grant):
        c=f.f.m.Operations(self.root,'demo',self.worker);c.reload();g=c.state['authorizations'][grant];r=f.f.m.load('operation-reconciliation')
        r.cancel(c,grant,r.identity(c,g),'synthetic','cancel-'+grant)
    def test_complete_endpoint_and_duplicate_requests_reuse_children(self):
        g,r=self.authority('deliver');calls=len(self.worker.calls);first=self.delivery.execute(g,r)
        self.assertEqual(first['status'],'ci_passed');self.assertEqual([x['status'] for x in first['results']],['commit_prepared','branch_published','pr_open','ci_passed'])
        self.assertEqual(self.delivery.execute(g,r)['status'],'ci_passed')
        self.assertEqual(self.delivery.execute(g,'different-ui-request')['request'],r)
        self.assertEqual((self.host.pushes,self.host.creates,len(self.worker.calls)),(1,1,calls))
        self.c.reload();parent=self.c.state['authorizations'][g]
        for step in self.delivery.state()['compositions'][r]['steps']:
            child=self.c.state['authorizations'][step['grant']]
            self.assertLessEqual(child['deadline'],parent['deadline']);self.assertEqual(child['parent_cancellations'][0]['binding'],parent['cancellation_binding'])
    def test_parent_deadline_prevents_first_mutation(self):
        g,r=self.authority('deliver');deadline=self.c.state['authorizations'][g]['deadline'];self.c.clock=lambda:deadline+1
        with self.assertRaisesRegex(ValueError,'deadline'):self.delivery.execute(g,r)
        self.assertEqual(self.git('rev-parse','HEAD'),self.base);self.assertEqual(self.host.pushes,0)
    def test_parent_cancel_after_push_stops_pr(self):
        g,r=self.authority('deliver');original=self.host.push
        def push(*args):original(*args);self.cancel(g)
        self.host.push=push
        with self.assertRaisesRegex(ValueError,'cancelled'):self.delivery.execute(g,r)
        self.assertEqual(self.host.pushes,1);self.assertEqual(self.host.creates,0)
    def test_crash_after_remote_push_reconciles_then_continues(self):
        g,r=self.authority('deliver');self.host.crash_push=True
        with self.assertRaises(KeyboardInterrupt):self.delivery.execute(g,r)
        self.host.crash_push=False
        restarted=d.Delivery(f.f.m.Operations(self.root,'demo',self.worker),self.host)
        self.assertEqual(restarted.execute(g,r)['status'],'ci_passed');self.assertEqual(self.host.pushes,1);self.assertEqual(self.host.creates,1)
    def test_rejected_push_stops_dependents_and_does_not_repeat(self):
        g,r=self.authority('deliver');self.host.reject_push=True
        with self.assertRaises(ValueError):self.delivery.execute(g,r)
        with self.assertRaises(ValueError):self.delivery.execute(g,r)
        self.assertEqual(self.host.pushes,1);self.assertEqual(self.host.creates,0)
    def test_base_movement_after_commit_blocks_publication(self):
        g,r=self.authority('deliver');original=self.delivery.execute
        def execute(grant,request,*args,**kwargs):
            result=original(grant,request,*args,**kwargs)
            if result['status']=='commit_prepared':self.host.references['base']='f'*40
            return result
        with patch.object(self.delivery,'execute',side_effect=execute):
            with self.assertRaisesRegex(ValueError,'base_changed'):original(g,r)
        self.assertEqual(self.host.pushes,0);self.assertEqual(self.host.creates,0)
    def test_crash_after_child_authorization_retains_parent_cancel(self):
        g,r=self.authority('deliver');original=self.delivery.authorize;child=[]
        def authorize(action,*args,**kwargs):
            result=original(action,*args,**kwargs)
            if action=='branch':child.append(result['id']);self.cancel(g);raise KeyboardInterrupt('crash after durable delegation')
            return result
        with patch.object(self.delivery,'authorize',side_effect=authorize):
            with self.assertRaises(KeyboardInterrupt):self.delivery.execute(g,r)
        with self.assertRaisesRegex(ValueError,'cancelled'):self.delivery.execute(child[0],'direct-child-run')
        self.assertEqual(self.host.pushes,0)
    def test_ci_failure_is_endpoint_outcome_without_implicit_repair(self):
        g,r=self.authority('deliver');original=self.host.ci
        def ci(*args):
            row=original(*args);row['checks'][0]['conclusion']='failure';return row
        self.host.ci=ci;calls=len(self.worker.calls)
        result=self.delivery.execute(g,r);self.assertEqual(result['status'],'ci_failed');self.assertEqual(len(self.worker.calls),calls)
        self.assertEqual(self.host.merges,0)
    def test_commit_crash_before_cas_reconciliation_never_performs_cas(self):
        g,r=self.authority('commit');original=d.git;updates=[]
        def git(project,*args,**kwargs):
            if args[0]=='update-ref':updates.append(args);raise KeyboardInterrupt('before CAS')
            return original(project,*args,**kwargs)
        with patch.object(d,'git',side_effect=git):
            with self.assertRaises(KeyboardInterrupt):self.delivery.execute(g,r)
        with self.assertRaisesRegex(ValueError,'absent_or_unknown'):self.delivery.execute(g,r,True)
        self.assertEqual(self.git('rev-parse','HEAD'),self.base);self.assertEqual(len(updates),1)
    def test_commit_crash_after_cas_reconciles_without_another_commit(self):
        g,r=self.authority('commit');original=d.git
        def git(project,*args,**kwargs):
            result=original(project,*args,**kwargs)
            if args[0]=='update-ref':raise KeyboardInterrupt('after CAS')
            return result
        with patch.object(d,'git',side_effect=git):
            with self.assertRaises(KeyboardInterrupt):self.delivery.execute(g,r)
        head=self.git('rev-parse','HEAD');self.cancel(g);self.c.clock=lambda:10**12
        self.assertEqual(self.delivery.execute(g,r,True)['head'],head)
    def test_unrelated_committed_operator_history_cannot_be_published(self):
        self.git('commit','--only','-m','Unrelated operator commit','--','operator.txt')
        self.prepared()
        with self.assertRaises(ValueError):self.run_action('branch')
        self.assertEqual(self.host.pushes,0);self.assertEqual((self.root/'operator.txt').read_text(),'unrelated operator contents\n')
    def test_unreviewed_intermediate_commit_in_allowed_file_is_blocked(self):
        accepted=(self.root/'app.py').read_text();(self.root/'app.py').write_text('def answer(): return 99 # synthetic unreviewed intermediate\n')
        self.git('commit','--only','-m','Unreviewed intermediate in allowed path','--','app.py')
        (self.root/'app.py').write_text(accepted);self.prepared()
        with self.assertRaisesRegex(ValueError,'history'):self.run_action('branch')
        self.assertEqual(self.host.pushes,0)
    def test_remote_base_must_be_ancestor_of_prepared_commit(self):
        foreign=self.git('commit-tree',self.git('rev-parse',self.base+'^{tree}'),'-m','Unrelated synthetic root')
        self.host.references['base']=foreign;self.prepared()
        with self.assertRaisesRegex(ValueError,'base'):self.run_action('branch')
        self.assertEqual(self.host.pushes,0)
    def test_private_add_then_delete_history_cannot_hide_in_clean_tree(self):
        private=self.root/'.nightshift/synthetic-private.txt';private.parent.mkdir(exist_ok=True);private.write_text('synthetic private evidence only\n')
        self.git('add','-f','--','.nightshift/synthetic-private.txt');self.git('commit','--only','-m','Synthetic private history','--','.nightshift/synthetic-private.txt')
        self.git('rm','--','.nightshift/synthetic-private.txt');self.git('commit','--only','-m','Remove synthetic private file','--','.nightshift/synthetic-private.txt')
        self.prepared()
        with self.assertRaises(ValueError):self.run_action('branch')
        self.assertEqual(self.host.pushes,0)
    def test_merge_response_moved_head_cannot_claim_integrated(self):
        self.run_action('deliver');g,r=self.authority('merge')
        def merge(*args):
            self.host.merges+=1;row=self.host.ci(self.profile,1);row.update(merged=True,state='closed',head='f'*40);self.host.observation=row
        self.host.merge=merge
        with self.assertRaisesRegex(ValueError,'merge.*revision|merge.*identity'):self.delivery.execute(g,r)
        self.assertEqual(self.host.merges,1)
    def test_oversized_host_output_is_retained_and_not_parsed(self):
        paths=[]
        def bounded(argv,project,env,seconds,output,**kwargs):output.write_bytes(b' '*2000001);paths.append(output);return 0
        runner=SimpleNamespace(clean_environment=lambda:{},bounded=bounded);original=d.m.load
        with patch.object(d.m,'load',side_effect=lambda name:runner if name=='controller-recovery' else original(name)):
            with self.assertRaisesRegex(ValueError,'output_too_large'):d.Host(self.delivery).call(['synthetic-output-only'],True)
        self.assertEqual(paths[0].stat().st_size,2000001)
    def test_deliver_rejects_unbound_repair_grant_instead_of_ignoring_it(self):
        g,r=self.authority('deliver')
        with self.assertRaisesRegex(ValueError,'repair_grant_requires_repair_action'):self.delivery.execute(g,r,repair_grant='not-authorized-here')
        self.assertEqual(self.git('rev-parse','HEAD'),self.base);self.assertEqual(self.host.pushes,0)
    def test_history_walk_observes_cancellation_before_publication(self):
        self.prepared();g,r=self.authority('branch');original=d.git
        def git(project,*args,**kwargs):
            result=original(project,*args,**kwargs)
            if args[0]=='rev-list':self.cancel(g)
            return result
        with patch.object(d,'git',side_effect=git):
            with self.assertRaisesRegex(ValueError,'cancelled'):self.delivery.execute(g,r)
        self.assertEqual(self.host.pushes,0)
    def test_history_walk_observes_deadline_before_publication(self):
        self.prepared();g,r=self.authority('branch');deadline=self.c.state['authorizations'][g]['deadline'];original=d.git
        def git(project,*args,**kwargs):
            result=original(project,*args,**kwargs)
            if args[0]=='rev-list':self.c.clock=lambda:deadline+1
            return result
        with patch.object(d,'git',side_effect=git):
            with self.assertRaisesRegex(ValueError,'deadline'):self.delivery.execute(g,r)
        self.assertEqual(self.host.pushes,0)
    def test_profile_cannot_omit_reviewed_scope(self):
        self.profile['files']=['spec.md'];self.write_profile()
        with self.assertRaisesRegex(ValueError,'must_include_reviewed_source_scope'):d.profile(self.c)
        self.assertEqual(self.host.pushes,0)
    def test_changed_check_script_cannot_be_omitted(self):
        self.prepared()
        with self.assertRaisesRegex(ValueError,'reviewed_file_not_committed'):self.run_action('branch')
        self.assertEqual(self.host.pushes,0)
    def test_fresh_commit_request_does_not_create_empty_commit(self):
        head=self.prepared();self.assertEqual(self.run_action('commit')['head'],head)

if __name__=='__main__':unittest.main()
