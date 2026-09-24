import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('repair',ROOT/'scripts/nightshift-console-repair.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name).resolve()
        for args in [('init','-q'),('config','user.name','test'),('config','user.email','test@local')]:self.git(*args)
        (self.p/'file.txt').write_text('before\n');self.git('add','.');self.git('commit','-qm','fixture')
        self.patch='diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-before\n+after\n'
    def tearDown(self):self.temp.cleanup()
    def git(self,*args):return subprocess.check_output(['git','-C',str(self.p),*args],text=True)
    def test_patch_is_checked_without_mutation(self):
        self.assertEqual(m.checked_patch(self.p,self.patch),['file.txt'])
        self.assertEqual((self.p/'file.txt').read_text(),'before\n')
    def test_structural_and_escape_patches_rejected(self):
        for patch in [self.patch+'deleted file mode 100644\n',self.patch.replace('file.txt','../escape'),self.patch.replace('file.txt','.git/config'),self.patch+'new mode 100755\n','not a patch']:
            with self.subTest(patch=patch),self.assertRaises(ValueError):m.checked_patch(self.p,patch)
    def test_symlink_rejected(self):
        (self.p/'link').symlink_to(self.p/'file.txt')
        with self.assertRaises(ValueError):m.checked_patch(self.p,self.patch.replace('file.txt','link'))
    def test_bundle_contains_bounded_numbered_public_evidence(self):
        docs=self.p/'docs/42';docs.mkdir(parents=True)
        (docs/'BLOCKED.md').write_text('missing review manifest\n')
        (docs/'scenario-validation.json').write_text('{"error":"schema_keys"}')
        (docs/'heldout.json').write_text('PRIVATE_CASE')
        (docs/'SPEC.md').symlink_to(self.p/'file.txt')
        (self.p/'scripts').mkdir()
        (self.p/'scripts/check.py').write_text('print("check")\n')
        self.git('add','scripts/check.py')
        bundle=m.evidence_bundle(self.p,'42')
        self.assertIn('1: missing review manifest',bundle)
        self.assertIn('schema_keys',bundle)
        self.assertIn('scripts/check.py',bundle)
        self.assertNotIn('PRIVATE_CASE',bundle)
        self.assertNotIn('FILE: docs/42/SPEC.md',bundle)
    def child_context(self, status='blocked', task='parent'):
        child='child'
        docs=self.p/'docs'/task;docs.mkdir(parents=True,exist_ok=True)
        (docs/'decomposition.json').write_text(json.dumps({'children':[{'id':'part','ref':'spec:child.md'}]}))
        (self.p/'.nightshift').mkdir(exist_ok=True)
        (self.p/'.nightshift/batch-current.json').write_text(json.dumps({'parent_task':task,'decomposition_plan':f'docs/{task}/decomposition.json','child_tasks':{'part':child},'statuses':{'spec:child.md':{'status':status}}}))
        root=self.p/'child-worktree';self.git('worktree','add','-qb','child',str(root))
        owner=self.p/'.git/nightshift/worktrees';owner.mkdir(parents=True,exist_ok=True)
        (owner/'child.json').write_text(json.dumps({'task':child,'worktree':str(root)}))
        (root/'docs/child').mkdir(parents=True)
        return root,owner/'child.json'
    def test_parent_resolves_owned_child_and_prioritizes_public_inputs(self):
        root,_=self.child_context()
        docs=root/'docs/child'
        (docs/'SPEC.md').write_text('actual child specification')
        (docs/'calibration-fixtures.json').write_text('{"fixture":"known good"}')
        (docs/'latest-failure.json').write_text('{"reason":"c05 request count"}')
        (self.p/'.nightshift/parent.md').write_text('history\n'*30000)
        context=m.evidence_context(self.p,'parent')
        self.assertEqual(context['repair_target']['task'],'child')
        bundle=m.evidence_bundle(self.p,'parent')
        self.assertIn('actual child specification',bundle)
        self.assertIn('known good',bundle)
        self.assertIn('c05 request count',bundle)
        self.assertLess(bundle.index('actual child specification'),bundle.index('history'))
        self.assertLessEqual(len(bundle),100000)
    def test_parent_exposes_child_decision_and_active_repair_spends_nothing(self):
        root,_=self.child_context('in_progress')
        settings=dict(ref='spec:brief.md',provider='codex',model='',policy='standard',auth='subscription',branch='auto',base='',push=False,pr=False)
        m.actions.save(self.p,'parent',settings)
        owner=m.actions.directory(self.p).parent/'worktrees/parent.json'
        owner.write_text(json.dumps({'task':'parent','worktree':str(self.p),'base_sha':self.git('rev-parse','HEAD').strip()}))
        spec=importlib.util.spec_from_file_location('decisions',ROOT/'scripts/nightshift-console-decisions.py')
        decisions=importlib.util.module_from_spec(spec);spec.loader.exec_module(decisions)
        current=m.actions.state(self.p,'parent')
        result=m.actions.action(self.p,'parent',current['sha256'],'repair')
        self.assertEqual(result['status'],'blocked')
        self.assertFalse((m.actions.directory(self.p)/'parent.repair-budget.json').exists())
        q=decisions.request(self.p,'child',dict(question='Choose export',reason='Required format is unspecified',options=[]))
        parent=m.actions.state(self.p,'parent')
        self.assertEqual(parent['decisions']['pending'][0]['task'],'child')
        with self.assertRaises(ValueError):m.actions.action(self.p,'parent',parent['sha256'],'resume')
        decisions.respond(self.p,'child',q['sha256'],'','Markdown')
        self.assertEqual(m.actions.state(self.p,'parent')['decisions']['answered'][0]['response']['answer'],'Markdown')

    def test_active_child_is_context_only(self):
        self.child_context('in_progress')
        context=m.evidence_context(self.p,'parent')
        self.assertNotIn('repair_target',context)
        self.assertEqual(context['candidate_targets'][0]['status'],'in_progress')
    def test_foreign_repo_and_owner_mismatch_excluded(self):
        root,owner=self.child_context()
        owner.write_text(json.dumps({'task':'wrong','worktree':str(root)}))
        self.assertEqual(m.evidence_context(self.p,'parent')['candidate_targets'],[])
        foreign=self.p/'foreign';foreign.mkdir();subprocess.run(['git','init','-q',str(foreign)],check=True)
        owner.write_text(json.dumps({'task':'child','worktree':str(foreign)}))
        self.assertEqual(m.evidence_context(self.p,'parent')['candidate_targets'],[])
    def test_private_ancestors_symlinks_and_task_traversal_excluded(self):
        docs=self.p/'docs/42';docs.mkdir(parents=True)
        (docs/'private-failure.json').write_text('PRIVATE_PAYLOAD')
        (docs/'embedded-failure.json').write_text(json.dumps({'private_cases':{'text':'PRIVATE_PAYLOAD'}},indent=2))
        (docs/'failure.json').symlink_to(self.p/'file.txt')
        hidden=self.p/'scripts/private';hidden.mkdir(parents=True)
        (hidden/'fixture.json').write_text('PRIVATE_PAYLOAD')
        (self.p/'scripts/public.py').write_text('api_key = "DO_NOT_SEND"\nprint("safe")')
        self.git('add','scripts')
        bundle=m.evidence_bundle(self.p,'42')
        self.assertNotIn('PRIVATE_PAYLOAD',bundle)
        self.assertNotIn('DO_NOT_SEND',bundle)
        self.assertIn('print("safe")',bundle)
        with self.assertRaises(ValueError):m.evidence_bundle(self.p,'../escape')
    def test_recent_receipts_precede_old_and_limit_is_rendered_size(self):
        docs=self.p/'docs/42';docs.mkdir(parents=True)
        for i in range(30):
            f=docs/f'failure-{i}.json';f.write_text(json.dumps({'public_details':['x']*12000},indent=2));os.utime(f,(100+i,100+i))
        bundle=m.evidence_bundle(self.p,'42')
        self.assertLessEqual(len(bundle),100000)
        self.assertIn('failure-29.json',bundle)
        self.assertNotIn('failure-0.json',bundle)
        self.assertIn('Excerpt truncated',bundle)

    def test_public_projection_keeps_late_cases_and_drops_protected_subtrees(self):
        docs=self.p/'docs/42';docs.mkdir(parents=True)
        cases=[]
        for i in range(1,7):
            cases.append(dict(id=f'c0{i}-public-case',visibility='public',given='A synthetic public input',
                input=[f'C0{i}_TURN_{turn}_PUBLIC '+('x'*8000) for turn in range(6)],
                then=f'C0{i}_PUBLIC_ORACLE '+('y'*8000),
                forbidden='Do not invent claims',expected=['public expectation']))
        cases.append(dict(id='hidden-case',visibility='private',input='DO_NOT_FORWARD_PRIVATE_BODY'))
        value=dict(cases=cases,heldout={'cases':['DO_NOT_FORWARD_HELDOUT_BODY']},
            metadata={'api_key':'DO_NOT_FORWARD_CREDENTIAL'})
        (docs/'behavior-scenarios.json').write_text(json.dumps(value,indent=2))
        bundle=m.evidence_bundle(self.p,'42')
        for text in ('c05-public-case','c06-public-case','C05_TURN_0_PUBLIC','C06_TURN_5_PUBLIC','C06_PUBLIC_ORACLE','JSON POINTER /cases/5'):
            self.assertIn(text,bundle)
        for text in ('DO_NOT_FORWARD_PRIVATE_BODY','DO_NOT_FORWARD_HELDOUT_BODY','DO_NOT_FORWARD_CREDENTIAL'):
            self.assertNotIn(text,bundle)
        self.assertLessEqual(len(bundle),100000)

    def test_worker_requires_review_and_verification_before_resume(self):
        docs=self.p/'docs/42';docs.mkdir(parents=True)
        (docs/'BLOCKED.md').write_text('actual failure evidence')
        settings=dict(ref='spec:brief.md',provider='codex',model='',policy='standard',auth='subscription',branch='auto',base='HEAD',push=False,pr=False)
        m.actions.save(self.p,'42',settings)
        owner=m.actions.directory(self.p).parent/'worktrees';owner.mkdir()
        (owner/'42.json').write_text(json.dumps({'worktree':str(self.p), 'base_sha':self.git('rev-parse','HEAD').strip()}))
        routing=json.loads((ROOT/'routing.json').read_text());(self.p/'routing.json').write_text(json.dumps(routing))
        (self.p/'.nightshift.toml').write_text('[providers]\nrouting_file = "routing.json"\n')
        helpers=self.p/'helpers';helpers.mkdir()
        (helpers/'nightshift-run-metrics.py').write_text('print("{}")')
        (helpers/'nightshift-cleanup.py').write_text('print("{}")')
        # Simulates only transport; exercises the real worker's patch/review/verify/resume ordering.
        script='''import json,os,sys
from pathlib import Path
a=sys.argv
if 'verification.json' not in a[a.index('--out')+1]:
    assert '1: actual failure evidence' in Path(a[a.index('--in')+1]).read_text(), 'diagnosis and review must receive evidence'
assert a[1] == ('nightshift-run-all-tests' if 'verification.json' in a[a.index('--out')+1] else 'nightshift-repair-analyst'), 'repair must not dispatch proof-gated implementation roles'
out=Path(a[a.index('--out')+1]);kind=out.stem
with open(os.environ['ORDER'],'a') as f:f.write(kind+'\\n')
if kind==os.environ.get('FAIL_PHASE'):out.write_text(json.dumps({'status':'FAIL'}));sys.exit(1)
out.write_text(json.dumps({'status':'SUCCESS','artifacts':{'provider':'claude','diff':os.environ['PATCH']},'results':{'files_changed':['file.txt']}}))
'''
        (helpers/'dispatch.py').write_text(script)
        (helpers/'nightshift-agent.sh').write_text('exec python3 "'+str(helpers/'dispatch.py')+'" "$@"\n')
        factory=helpers/'factory.sh';factory.write_text('echo resumed >> "$ORDER"\n')
        previous=m.HERE,m.actions.FACTORY;m.HERE=helpers;m.actions.FACTORY=factory
        old=dict(os.environ)
        try:
            os.environ.pop('NIGHTSHIFT_ROUTING_FILE', None)
            os.environ.update(ORDER=str(self.p/'order'),PATCH=self.patch,FAIL_PHASE='verification')
            evidence=m.actions.directory(self.p)/'repair-one';evidence.mkdir()
            with self.assertRaises(ValueError):m.worker(self.p,'42','auto',evidence)
            self.assertNotIn('resumed',(self.p/'order').read_text())
            self.assertEqual((self.p/'file.txt').read_text(),'after\n') # retained, not silently rolled back
            (self.p/'file.txt').write_text('before\n');os.environ.pop('FAIL_PHASE')
            evidence=m.actions.directory(self.p)/'repair-two';evidence.mkdir()
            self.assertEqual(m.worker(self.p,'42','auto',evidence),0)
            self.assertTrue((self.p/'order').read_text().endswith('proposal\nreview\nverification\nresumed\n'))
            (self.p/'file.txt').write_text('before\n')
            child,_=self.child_context(task='42')
            self.assertFalse((child/'routing.json').exists())
            self.assertFalse((child/'.nightshift.toml').exists())
            (child/'docs/child/BLOCKED.md').write_text('actual failure evidence')
            evidence=m.actions.directory(self.p)/'repair-child';evidence.mkdir()
            self.assertEqual(m.worker(self.p,'42','auto',evidence),0)
            self.assertEqual((self.p/'file.txt').read_text(),'before\n')
            self.assertEqual((child/'file.txt').read_text(),'after\n')
            receipt=json.loads((evidence/'status.json').read_text())
            self.assertEqual(receipt['task'],'child')
            self.assertEqual(receipt['parent_task'],'42')
            batch=self.p/'.nightshift/batch-current.json'
            value=json.loads(batch.read_text());value['statuses']['spec:child.md']['status']='in_progress';batch.write_text(json.dumps(value))
            evidence=m.actions.directory(self.p)/'repair-active';evidence.mkdir()
            before_order=(self.p/'order').read_text()
            self.assertEqual(m.worker(self.p,'42','auto',evidence),1)
            self.assertEqual((self.p/'order').read_text(),before_order)
            self.assertEqual(json.loads((evidence/'status.json').read_text())['phase'],'blocked')


        finally:
            m.HERE,m.actions.FACTORY=previous;os.environ.clear();os.environ.update(old)

if __name__=='__main__':unittest.main()
