#!/usr/bin/env python3
"""Independent delivery regressions; disposable Git and an in-memory synthetic host only."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
f=load('delivery_review_fixture',ROOT/'tests/test-operations.py')
d=load('delivery_review_subject',ROOT/'scripts/nightshift-delivery.py')

class Host:
    def __init__(self,base):
        self.references=dict(head=None,base=base);self.rows=[];self.pushes=0;self.creates=0;self.merges=0
        self.crash_push=False;self.crash_create=False;self.reject_push=False;self.observation=None
    def refs(self,p):return dict(self.references)
    def push(self,p,head,old):
        self.pushes+=1
        if self.reject_push:raise ValueError('synthetic_rejected_push')
        if self.references['head']!=old:raise ValueError('synthetic_lease_conflict')
        self.references['head']=head
        if self.crash_push:raise KeyboardInterrupt('synthetic crash after push')
    def prs(self,p):return copy.deepcopy(self.rows)
    def create(self,p,body):
        self.creates+=1
        self.rows.append(dict(number=1,headRefName=p['branch'],headRefOid=self.references['head'],baseRefName=p['base'],baseRefOid=self.references['base'],body=body,state='OPEN',url='https://example.invalid/pr/1',headRepository={'nameWithOwner':'owner/repo'}))
        if self.crash_create:raise KeyboardInterrupt('synthetic crash after PR creation')
    def ci(self,p,number):
        return copy.deepcopy(self.observation or dict(head=self.references['head'],base=self.references['base'],merge='c'*40,parents=[self.references['head'],self.references['base']],checks=[dict(name='integration',head='c'*40,status='completed',conclusion='success',id=1,app_id=1)],state='open',merged=False,protected=True))
    def merge(self,*args):self.merges+=1;raise AssertionError('merge must not be called')

class DeliveryReview(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='nightshift-delivery-review-');self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve();self.plan=f.fixture(self.root);self.worker=f.Worker();self.n=0
        self.git('checkout','-qb','synthetic-delivery');self.git('remote','add','synthetic','https://example.invalid/owner/repo.git')
        self.base=self.git('rev-parse','HEAD')
        self.profile=dict(version=1,remote='synthetic',remote_url='https://example.invalid/owner/repo.git',repository='owner/repo',branch='synthetic-delivery',base='main',files=['app.py'],checks=[dict(name='integration',app_id=1)],endpoint='ci',merge_policy='disabled',commit=dict(message='Synthetic reviewed change',author_name='Synthetic',author_email='synthetic@example.invalid'))
        if self._testMethodName=='test_branch_endpoint_rejects_pr_action':self.profile['endpoint']='branch'
        self.write_profile()
        (self.root/'app.py').write_text('def answer():\n    return 2 # reviewed change\n')
        if self._testMethodName=='test_commit_preserves_reviewed_executable_mode':(self.root/'app.py').chmod(0o755)
        (self.root/'operator.txt').write_text('unrelated operator contents\n');self.git('add','operator.txt')
        self.c=f.m.Operations(self.root,'demo',self.worker)
        a=self.c.assess('groom-spec');g=self.c.authorize(f.m.RECIPES['factory'],a['binding'],'synthetic','factory');result=self.c.chain(g['id'])
        self.assertTrue(all(row['status'] in ('passed','reused') for row in result['results']),result)
        a=self.c.assess('accept');g=self.c.authorize(['accept'],a['binding'],'synthetic','accept',dict(binding=a['binding'],accepted=True));self.assertEqual(self.c.execute(g['id'],'accept','accept-run')['status'],'passed')
        self.host=Host(self.base);self.delivery=d.Delivery(self.c,self.host)
    def git(self,*args):return subprocess.check_output(['git','-C',str(self.root),*args],text=True,stderr=subprocess.PIPE).strip()
    def write_profile(self):(self.root/'docs/demo/delivery.json').write_text(json.dumps(self.profile))
    def authority(self,action):
        self.n+=1;a=self.delivery.assess(action);self.assertEqual(a['status'],'ready',a)
        g=self.delivery.authorize(action,a['binding'],'synthetic','delivery-'+str(self.n));return g['id'],'effect-'+str(self.n)
    def run_action(self,action):
        g,r=self.authority(action);return self.delivery.execute(g,r)
    def prepared(self):return self.run_action('commit')['head']
    def published(self):self.prepared();return self.run_action('branch')
    def pr(self):self.published();return self.run_action('pr')
    def test_commit_preserves_index_and_excludes_unrelated_files(self):
        before=(self.root/'.git/index').read_bytes();head=self.prepared()
        self.assertEqual(before,(self.root/'.git/index').read_bytes())
        self.assertEqual(self.git('diff-tree','--no-commit-id','--name-only','-r',head),'app.py')
        self.assertNotIn('operator.txt',self.git('ls-tree','--name-only',head))
        self.assertEqual((self.root/'operator.txt').read_text(),'unrelated operator contents\n')
    def test_commit_does_not_transform_reviewed_bytes_with_clean_filter(self):
        self.git('config','filter.synthetic.clean','sed s/reviewed/transformed/g')
        (self.root/'.git/info/attributes').write_text('app.py filter=synthetic\n')
        head=self.prepared()
        self.assertEqual(self.git('show',head+':app.py'),(self.root/'app.py').read_text().strip())
        self.assertEqual(self.run_action('branch')['status'],'branch_published')
    def test_private_path_denied_even_when_declared_scope(self):
        self.profile['files']=['.env'];self.plan['scope'].append('.env');(self.root/'.env').write_text('synthetic-only')
        (self.root/'docs/demo/operations.json').write_text(json.dumps(self.plan));self.write_profile()
        with self.assertRaises(ValueError):d.profile(self.c)
    def test_duplicate_commit_reuses_exact_head(self):
        g,r=self.authority('commit');first=self.delivery.execute(g,r);second=self.delivery.execute(g,r)
        self.assertEqual(first['head'],second['head']);self.assertTrue(second['reused'])
    def test_changed_source_cannot_reuse_acceptance(self):
        g,r=self.authority('commit');(self.root/'app.py').write_text('def answer(): return 999\n')
        with self.assertRaises(ValueError):self.delivery.execute(g,r)
        self.assertEqual(self.git('rev-parse','HEAD'),self.base)
    def test_branch_replay_detects_remote_force_move(self):
        self.prepared();g,r=self.authority('branch');self.delivery.execute(g,r);self.host.references['head']='f'*40
        with self.assertRaises((ValueError,subprocess.SubprocessError)):self.delivery.execute(g,r)
        self.assertEqual(self.host.pushes,1)
    def test_commit_replay_detects_local_branch_move(self):
        g,r=self.authority('commit');result=self.delivery.execute(g,r);self.git('update-ref','refs/heads/synthetic-delivery',self.base,result['head'])
        with self.assertRaises(ValueError):self.delivery.execute(g,r)
    def test_base_movement_blocks_push(self):
        self.prepared();g,r=self.authority('branch');self.host.references['base']='f'*40
        with self.assertRaises(ValueError):self.delivery.execute(g,r)
        self.assertEqual(self.host.pushes,0)
    def test_rejected_push_requires_explicit_new_action(self):
        self.prepared();g,r=self.authority('branch');self.host.reject_push=True
        with self.assertRaises(ValueError):self.delivery.execute(g,r)
        with self.assertRaises(ValueError):self.delivery.execute(g,r,True)
        self.assertEqual(self.host.pushes,1)
    def test_crash_after_push_reconciles_without_repeating(self):
        self.prepared();g,r=self.authority('branch');self.host.crash_push=True
        with self.assertRaises(KeyboardInterrupt):self.delivery.execute(g,r)
        restarted=d.Delivery(f.m.Operations(self.root,'demo',self.worker),self.host)
        self.assertEqual(restarted.execute(g,r,True)['status'],'branch_published');self.assertEqual(self.host.pushes,1)
    def test_cancelled_expired_push_can_be_confirmed_read_only(self):
        self.prepared();g,r=self.authority('branch');self.host.crash_push=True
        with self.assertRaises(KeyboardInterrupt):self.delivery.execute(g,r)
        self.c.reload();authority=self.c.state['authorizations'][g];rec=f.m.load('operation-reconciliation');rec.cancel(self.c,g,rec.identity(self.c,authority),'synthetic','cancel-push')
        self.c.clock=lambda:authority['deadline']+1
        self.assertEqual(self.delivery.execute(g,r,True)['status'],'branch_published');self.assertEqual(self.host.pushes,1)
    def test_crash_after_pr_reconciles_without_duplicate(self):
        self.published();g,r=self.authority('pr');self.host.crash_create=True
        with self.assertRaises(KeyboardInterrupt):self.delivery.execute(g,r)
        self.assertEqual(self.delivery.execute(g,r,True)['status'],'pr_open');self.assertEqual(self.host.creates,1)
    def test_pr_marker_and_ambiguity_rejected(self):
        self.pr();self.host.rows[0]['body']='unowned PR'
        with self.assertRaises(ValueError):self.run_action('pr')
        self.host.rows.append(copy.deepcopy(self.host.rows[0]))
        with self.assertRaises(ValueError):self.run_action('pr')
        self.assertEqual(self.host.creates,1)
    def test_ci_pass_failed_empty_stale_and_skipped(self):
        self.pr();baseline=self.host.ci(self.profile,1)
        self.assertEqual(self.run_action('ci')['status'],'ci_passed')
        for status,change in [('ci_failed',dict(conclusion='failure')),('ci_unknown',dict(conclusion='skipped')),('ci_unknown',dict(head='e'*40)),('ci_unknown',dict(status='queued'))]:
            with self.subTest(change=change):
                self.host.observation=copy.deepcopy(baseline);self.host.observation['checks'][0].update(change)
                self.assertEqual(self.run_action('ci')['status'],status)
        self.host.observation=copy.deepcopy(baseline);self.host.observation['checks']=[]
        self.assertEqual(self.run_action('ci')['status'],'ci_unknown')
    def test_closed_unmerged_pr_cannot_pass_ci(self):
        self.pr();self.host.rows[0]['state']='CLOSED';self.host.observation=self.host.ci(self.profile,1);self.host.observation['state']='closed'
        try:result=self.run_action('ci')
        except ValueError:return
        self.assertNotEqual(result['status'],'ci_passed')
    def test_spoofed_check_app_cannot_pass(self):
        self.pr();self.host.observation=self.host.ci(self.profile,1);self.host.observation['checks'][0]['app_id']=999
        self.assertNotEqual(self.run_action('ci')['status'],'ci_passed')
    def test_fork_repository_pr_is_rejected(self):
        self.pr();self.host.rows[0]['headRepository']={'nameWithOwner':'attacker/repo'}
        with self.assertRaises(ValueError):self.run_action('pr')
        self.assertEqual(self.host.creates,1)
    def test_branch_endpoint_rejects_pr_action(self):
        self.published()
        try:a=self.delivery.assess('pr')
        except ValueError:return
        self.assertEqual(a['status'],'blocked')
        with self.assertRaises(ValueError):self.delivery.authorize('pr',a['binding'],'synthetic','over-endpoint')
        self.assertEqual(self.host.creates,0)
    def test_commit_preserves_reviewed_executable_mode(self):
        head=self.prepared();self.assertTrue(self.git('ls-tree',head,'app.py').startswith('100755 '))
    def test_real_transport_observes_push_destination_not_fetch_remote(self):
        fetch=self.root/'.git/synthetic-fetch.git';push=self.root/'.git/synthetic-push.git'
        for target in (fetch,push):subprocess.run(['git','init','--bare','-q',str(target)],check=True)
        self.git('remote','set-url','synthetic',str(fetch));self.git('remote','set-url','--push','synthetic',str(push))
        self.git('push',str(push),self.base+':refs/heads/synthetic-delivery',self.base+':refs/heads/main')
        p=dict(self.profile,remote_url=str(push))
        observed=d.Host(self.delivery).refs(p)
        self.assertEqual(observed,dict(head=self.base,base=self.base))
    def test_merge_disabled_is_separate_blocked_action(self):
        self.pr();a=self.delivery.assess('merge');self.assertEqual(a['status'],'blocked')
        with self.assertRaises(ValueError):self.delivery.authorize('merge',a['binding'],'synthetic','forbidden-merge')
        self.assertEqual(self.host.merges,0)

if __name__=='__main__':unittest.main()
