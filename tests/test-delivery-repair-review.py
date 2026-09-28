#!/usr/bin/env python3
"""CI repair authority regressions: synthetic workers, disposable Git, fake host."""
import copy
import difflib
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('delivery_repair_fixture',ROOT/'tests/test-delivery-review.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.f.m

class DeliveryRepairReview(unittest.TestCase):
    setUp=f.DeliveryReview.setUp
    git=f.DeliveryReview.git
    write_profile=f.DeliveryReview.write_profile
    authority=f.DeliveryReview.authority
    run_action=f.DeliveryReview.run_action
    prepared=f.DeliveryReview.prepared
    published=f.DeliveryReview.published
    pr=f.DeliveryReview.pr
    def child_grant(self,operator='synthetic'):
        self.n+=1;a=self.c.assess('groom-spec')
        return self.c.authorize(m.RECIPES['factory'],a['binding'],operator,'bounded-'+str(self.n),dict(bounded_repair=True))['id']
    def repair_authority(self,operator='synthetic'):
        self.n+=1;a=self.delivery.assess('repair');self.assertEqual(a['status'],'ready',a)
        g=self.delivery.authorize('repair',a['binding'],operator,'repair-parent-'+str(self.n))
        return g['id'],'repair-effect-'+str(self.n)
    def failure(self,index=1):
        self.host.observation=None;row=self.host.ci(self.profile,1)
        row['checks'][0].update(conclusion='failure',id=index,output=dict(title='Synthetic integration failure',summary='Expected two from answer()',text='AssertionError: integration fixture expected two'))
        self.host.observation=row
    def register(self,child=None,operator='synthetic'):
        child=child or self.child_grant(operator);grant,request=self.repair_authority(operator)
        result=self.delivery.execute(grant,request,repair_grant=child)
        return child,grant,request,result
    def patch(self,index):
        before=(self.root/'app.py').read_text();after='def answer():\n    return 2 # synthetic CI repair '+str(index)+'\n'
        self.worker.patch=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='a/app.py',tofile='b/app.py'))
        original=self.worker.__class__.__call__
        class RepairWorker(self.worker.__class__):
            def __call__(worker,operation,*args):
                result=original(worker,operation,*args)
                if operation!='implement':result['artifacts']['diff']=''
                return result
        self.worker.__class__=RepairWorker
    def accept(self):
        self.n+=1;a=self.c.assess('accept');self.assertEqual(a['status'],'ready',a)
        g=self.c.authorize(['accept'],a['binding'],'synthetic','fresh-accept-'+str(self.n),dict(binding=a['binding'],accepted=True))
        self.assertEqual(self.c.execute(g['id'],'accept','fresh-accept-run-'+str(self.n))['status'],'passed')
    def impl_calls(self):return sum(op=='implement' for op,_ in self.worker.calls)
    def test_substantive_ci_invalidates_review_acceptance_without_dispatch(self):
        self.pr();self.failure();before=len(self.worker.calls);self.register()
        self.assertEqual(len(self.worker.calls),before)
        self.assertNotEqual(self.c.assess('implement')['status'],'current')
        self.assertNotEqual(self.c.assess('review')['status'],'current')
        self.assertNotEqual(self.c.assess('accept')['status'],'current')
        self.assertEqual(len(self.delivery.state()['ci_failures']),1)
    def test_same_failure_reordered_rerun_is_idempotent_and_resumable(self):
        self.pr();self.failure();self.host.observation['checks'].append(dict(name='unrequired',app_id=2,id=800,head='c'*40,status='completed',conclusion='success'))
        child=self.child_grant();g1,r1=self.repair_authority();g2,r2=self.repair_authority()
        first=self.delivery.execute(g1,r1,repair_grant=child)
        self.host.observation['checks'].reverse()
        for check in self.host.observation['checks']:check['id']+=1000
        second=self.delivery.execute(g2,r2,repair_grant=child)
        self.assertEqual(first['repair']['trigger'],second['repair']['trigger']);self.assertEqual(len(self.delivery.state()['ci_failures']),1)
        self.assertIn('repair',self.delivery.state()['attempts'][r2])
        before=self.impl_calls();self.patch(1);self.assertEqual(self.delivery.resume_repair(g2,r2)['status'],'needs_acceptance')
        self.assertEqual(self.impl_calls(),before+1)
        self.delivery.resume_repair(g2,r2);self.assertEqual(self.impl_calls(),before+1)
    def test_repair_reruns_verify_review_and_requires_fresh_acceptance(self):
        self.pr();self.failure();child,g,r,_=self.register();before=len(self.worker.calls);self.patch(1)
        self.assertEqual(self.delivery.resume_repair(g,r)['status'],'needs_acceptance')
        operations=[op for op,_ in self.worker.calls[before:]];self.assertEqual(operations,['implement','review'])
        self.assertEqual(self.c.assess('verify')['status'],'current');self.assertEqual(self.c.assess('review')['status'],'current')
        self.assertNotEqual(self.c.assess('accept')['status'],'current')
        with self.assertRaises(ValueError):self.delivery.assess('commit')
        self.accept();self.assertEqual(self.delivery.assess('commit')['status'],'ready')
    def test_existing_authority_deadline_and_parent_cancellation_survive(self):
        self.pr();self.failure();child=self.child_grant();deadline=self.c.state['authorizations'][child]['deadline'];g,r=self.repair_authority()
        self.delivery.execute(g,r,repair_grant=child)
        self.assertLessEqual(self.c.state['authorizations'][child]['deadline'],deadline)
        parent=self.c.state['authorizations'][g];rec=m.load('operation-reconciliation')
        rec.cancel(self.c,g,rec.identity(self.c,parent),'synthetic','cancel-ci-parent')
        before=self.impl_calls()
        with self.assertRaises(ValueError):self.delivery.resume_repair(g,r)
        self.assertEqual(self.impl_calls(),before)
    def test_expired_existing_factory_authority_cannot_be_renewed(self):
        self.pr();self.failure();child=self.child_grant();g,r=self.repair_authority();deadline=self.c.state['authorizations'][child]['deadline']
        self.c.clock=lambda:deadline+1
        with self.assertRaises(ValueError):self.delivery.execute(g,r,repair_grant=child)
        self.assertEqual(self.c.state['authorizations'][child]['deadline'],deadline)
        self.assertFalse(self.delivery.state()['ci_failures'])
    def test_duplicate_parent_keeps_additive_cancellation_and_deadline(self):
        self.pr();self.failure();child=self.child_grant();g1,r1=self.repair_authority();g2,r2=self.repair_authority()
        self.delivery.execute(g1,r1,repair_grant=child);first_deadline=self.c.state['authorizations'][child]['deadline']
        self.delivery.execute(g2,r2,repair_grant=child)
        authority=self.c.state['authorizations'][child];rec=m.load('operation-reconciliation')
        expected={str(rec.location(self.c,g)) for g in (g1,g2)}
        self.assertTrue(expected.issubset({row['path'] for row in authority.get('parent_cancellations',[])}))
        self.assertLessEqual(authority['deadline'],first_deadline)
        rec.cancel(self.c,g2,rec.identity(self.c,self.c.state['authorizations'][g2]),'synthetic','cancel-duplicate-parent')
        with self.assertRaises(ValueError):self.c.cancellation_check(child)
    def test_required_failure_without_diagnostics_cannot_start_repair(self):
        self.pr();self.failure();self.host.observation['checks'][0].pop('output')
        child=self.child_grant();g,r=self.repair_authority();before=self.impl_calls()
        with self.assertRaisesRegex(ValueError,'delivery_ci_diagnostics_required'):self.delivery.execute(g,r,repair_grant=child)
        self.assertEqual(self.impl_calls(),before);self.assertFalse(self.delivery.state()['ci_failures'])
    def test_unknown_ci_never_starts_implementation(self):
        self.pr();before=self.impl_calls()
        for status,conclusion in [('queued',None),('completed','skipped'),('completed','cancelled'),('completed','timed_out'),('completed','action_required')]:
            with self.subTest(status=status,conclusion=conclusion):
                self.failure();self.host.observation['checks'][0].update(status=status,conclusion=conclusion)
                child=self.child_grant();g,r=self.repair_authority()
                with self.assertRaises(ValueError):self.delivery.execute(g,r,repair_grant=child)
                self.assertEqual(self.impl_calls(),before);self.assertFalse(self.delivery.state()['ci_failures'])
    def test_external_adoption_never_repeats_implementation(self):
        self.pr();self.failure();child,g,r,_=self.register()
        (self.root/'app.py').write_text('def answer(): return 2 # external repair\n')
        a=self.c.assess('adopt');grant=self.c.authorize(['adopt'],a['binding'],'synthetic','external-ci-adopt',dict(binding=a['binding'],identity='synthetic-external',provider='human'))
        self.assertEqual(self.c.execute(grant['id'],'adopt','external-ci-adopt-run')['status'],'passed')
        before=self.impl_calls()
        try:self.delivery.resume_repair(g,r)
        except ValueError:pass
        self.assertEqual(self.impl_calls(),before)
        assessed=self.c.assess('verify');remaining=self.c.authorize(['verify','review'],assessed['binding'],'synthetic','external-ci-verify-review')
        result=self.c.chain(remaining['id']);self.assertTrue(all(row['status'] in ('passed','reused') for row in result['results']),result)
        self.assertEqual(self.impl_calls(),before);self.accept()
    def test_three_ci_repairs_remain_ceiling_across_commits_and_grants(self):
        self.pr()
        for index in range(1,4):
            self.failure(index);child,g,r,_=self.register(operator='synthetic-round-'+str(index));self.patch(index)
            self.assertEqual(self.delivery.resume_repair(g,r)['status'],'needs_acceptance');self.accept()
            head=self.prepared();self.run_action('branch');self.host.rows[0]['headRefOid']=head
            self.assertEqual(self.run_action('pr')['status'],'pr_open')
        self.assertEqual(len(self.delivery.state()['ci_failures']),3)
        self.failure(4);child=self.child_grant('synthetic-round-4');g,r=self.repair_authority('synthetic-round-4');before=self.impl_calls()
        with self.assertRaisesRegex(ValueError,'ci_repair_limit_exhausted'):self.delivery.execute(g,r,repair_grant=child)
        self.assertEqual(self.impl_calls(),before);self.assertEqual(len(self.delivery.state()['ci_failures']),3)

if __name__=='__main__':unittest.main()
