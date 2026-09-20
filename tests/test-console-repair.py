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
    def test_worker_requires_review_and_verification_before_resume(self):
        docs=self.p/'docs/42';docs.mkdir(parents=True)
        (docs/'BLOCKED.md').write_text('actual failure evidence')
        settings=dict(ref='spec:brief.md',provider='codex',model='',policy='standard',auth='subscription',branch='auto',base='HEAD',push=False,pr=False)
        m.actions.save(self.p,'42',settings)
        owner=m.actions.directory(self.p).parent/'worktrees';owner.mkdir()
        (owner/'42.json').write_text(json.dumps({'worktree':str(self.p)}))
        routing=json.loads((ROOT/'routing.json').read_text());(self.p/'routing.json').write_text(json.dumps(routing))
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
            os.environ.update(ORDER=str(self.p/'order'),PATCH=self.patch,FAIL_PHASE='verification')
            evidence=m.actions.directory(self.p)/'repair-one';evidence.mkdir()
            with self.assertRaises(ValueError):m.worker(self.p,'42','auto',evidence)
            self.assertNotIn('resumed',(self.p/'order').read_text())
            self.assertEqual((self.p/'file.txt').read_text(),'after\n') # retained, not silently rolled back
            (self.p/'file.txt').write_text('before\n');os.environ.pop('FAIL_PHASE')
            evidence=m.actions.directory(self.p)/'repair-two';evidence.mkdir()
            self.assertEqual(m.worker(self.p,'42','auto',evidence),0)
            self.assertTrue((self.p/'order').read_text().endswith('proposal\nreview\nverification\nresumed\n'))
        finally:
            m.HERE,m.actions.FACTORY=previous;os.environ.clear();os.environ.update(old)

if __name__=='__main__':unittest.main()
