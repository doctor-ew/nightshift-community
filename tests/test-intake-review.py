#!/usr/bin/env python3
"""Independent intake regressions; disposable repositories and synthetic adapters."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('intake_independent',ROOT/'scripts/nightshift-intake.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class IntakeReview(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nightshift-intake-review-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()/'repo';self.root.mkdir()
        home=Path(self.tmp.name)/'home';home.mkdir()
        env={'HOME':str(home),'NIGHTSHIFT_HOME':str(home/'.nightshift'),'XDG_CONFIG_HOME':str(home/'config'),
             'PATH':os.environ['PATH'],'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null',
             'GIT_CONFIG_SYSTEM':'/dev/null','PYTHONDONTWRITEBYTECODE':'1','GIT_TERMINAL_PROMPT':'0'}
        self.env=patch.dict(os.environ,env,clear=True);self.env.start();self.addCleanup(self.env.stop)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        for key,value in [('user.name','Synthetic'),('user.email','synthetic@example.invalid')]:
            subprocess.run(['git','-C',str(self.root),'config',key,value],check=True)
        for name,text in {'request.md':'# Synthetic request\nReturn two.\n','rules.md':'Use explicit tests.\n',
            'architecture.md':'No extra architecture choice has been approved.\n','app.py':'value=2\n',
            'test_app.py':'raise SystemExit("must not execute during intake")\n',
            '.nightshift.toml':'[providers]\npolicy="standard"\n'}.items(): (self.root/name).write_text(text)
        subprocess.run(['git','-C',str(self.root),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.root),'commit','-qm','Synthetic baseline'],check=True)
        self.choices=dict(scope=['app.py'],rules='rules.md',architecture='architecture.md',check='test_app.py',interpreter='python3',requirement='Return two.')
        result=m.api(self.root,dict(action='resolve',reference='spec:request.md'));self.task=result['task']
    def call(self,action,**extra):return m.api(self.root,dict(action=action,task=self.task,**extra))
    def draft(self):return self.call('draft',choices=self.choices)['draft']
    def test_duplicate_draft_and_materialization(self):
        first=self.draft();second=self.draft();self.assertEqual(first['binding'],second['binding'])
        a=self.call('materialize',binding=first['binding']);b=self.call('materialize',binding=first['binding'])
        self.assertEqual(a['status'],'materialized');self.assertEqual(b['status'],'materialized')
        self.assertEqual(len(m.Intake(self.root,self.task).state['drafts']),1)
        self.assertFalse(a['operations']['authorizations'])
    def test_cancel_preserves_files_and_has_no_worker_authority(self):
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        draft=self.draft();result=self.call('cancel');self.assertEqual(result['status'],'cancelled')
        with self.assertRaisesRegex(ValueError,'cancelled'):self.call('materialize',binding=draft['binding'])
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.iterdir() if p.is_file()})
        self.assertFalse((self.root/'docs'/self.task).exists())
    def test_all_destinations_preflight_before_first_write(self):
        draft=self.draft();names=list(draft['artifacts']);last=self.root/names[-1];last.parent.mkdir(parents=True)
        last.write_text('Operator file retained')
        with self.assertRaisesRegex(ValueError,'destination_changed'):self.call('materialize',binding=draft['binding'])
        self.assertFalse((self.root/names[0]).exists());self.assertEqual(last.read_text(),'Operator file retained')
    def test_identical_unowned_destination_is_not_adopted(self):
        draft=self.draft();name=next(iter(draft['artifacts']));dest=self.root/name;dest.parent.mkdir(parents=True);dest.write_text(draft['artifacts'][name]);dest.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'destination_changed'):self.call('materialize',binding=draft['binding'])
    def test_crash_after_first_write_replays_journal(self):
        draft=self.draft();names=list(draft['artifacts']);real_open=os.open
        def crashing(path,*args,**kwargs):
            if str(path)==Path(names[1]).name and args and args[0]&os.O_CREAT:raise KeyboardInterrupt('synthetic crash')
            return real_open(path,*args,**kwargs)
        with patch.object(m.os,'open',side_effect=crashing):
            with self.assertRaises(KeyboardInterrupt):self.call('materialize',binding=draft['binding'])
        first=self.root/names[0];before=first.stat().st_ino
        self.assertEqual(self.call('materialize',binding=draft['binding'])['status'],'materialized')
        self.assertEqual(first.stat().st_ino,before)
    def test_changed_owned_partial_file_is_preserved(self):
        draft=self.draft();names=list(draft['artifacts']);real_open=os.open
        def crashing(path,*args,**kwargs):
            if str(path)==Path(names[1]).name and args and args[0]&os.O_CREAT:raise KeyboardInterrupt()
            return real_open(path,*args,**kwargs)
        with patch.object(m.os,'open',side_effect=crashing):
            with self.assertRaises(KeyboardInterrupt):self.call('materialize',binding=draft['binding'])
        first=self.root/names[0];first.write_text('operator edit')
        with self.assertRaisesRegex(ValueError,'destination_changed'):self.call('materialize',binding=draft['binding'])
        self.assertEqual(first.read_text(),'operator edit')
    def test_source_and_mode_changes_invalidate_draft(self):
        draft=self.draft();(self.root/'request.md').write_text('# Changed request\n')
        with self.assertRaisesRegex(ValueError,'inputs_changed'):self.call('materialize',binding=draft['binding'])
        self.assertFalse((self.root/'docs'/self.task).exists())
    def test_decision_after_draft_invalidates_binding(self):
        draft=self.draft();dec=m.ops.load('console-decisions')
        row=dec.request(self.root,self.task,dict(question='Choose behavior',reason='Synthetic requirement uncertainty',options=[],decision_key='review-choice'))
        dec.respond(self.root,self.task,row['sha256'],'','Use two')
        with self.assertRaisesRegex(ValueError,'inputs_changed'):self.call('materialize',binding=draft['binding'])
    def test_missing_choices_one_persisted_decision_no_legacy_ticket(self):
        choices=dict(self.choices,scope=[],requirement='')
        a=self.call('draft',choices=choices);b=self.call('draft',choices=choices)
        self.assertEqual(len(a['decisions']['pending']),1);self.assertEqual(a['decisions'],b['decisions'])
        row=a['decisions']['pending'][0]
        self.call('answer',sha256=row['sha256'],answer='app.py; Return two')
        result=self.call('draft',choices=self.choices);self.assertEqual(result['status'],'draft')
        for name,content in result['draft']['artifacts'].items():
            if name.endswith(('request.md','SPEC.md')):self.assertIn('app.py; Return two',content)
        self.assertFalse((self.root/'docs'/self.task).exists())
    def test_path_rejection(self):
        for name in ('nested/.git/config','../outside','a/../app.py','.env.production','nested/.codex/config','./app.py'):
            with self.subTest(name=name),self.assertRaises(ValueError):self.call('draft',choices=dict(self.choices,scope=[name]))
        outside=Path(self.tmp.name)/'outside';outside.write_text('retained');(self.root/'link').symlink_to(outside)
        with self.assertRaises(ValueError):self.call('draft',choices=dict(self.choices,rules='link'))
        self.assertEqual(outside.read_text(),'retained')
    def test_github_namespaces_remain_distinct(self):
        def source(project,ref):
            repo,number=ref[3:].split('#');record=dict(source='gh',repository=repo,source_id=number,external_ref='gh-'+number,title='Synthetic',body='Return two')
            return dict(reference=ref,record=record,sha256=m.ops.digest(record))
        with patch.object(m,'resolve_source',side_effect=source):
            a=m.api(self.root,dict(action='resolve',reference='gh:one/repo#7'))
            b=m.api(self.root,dict(action='resolve',reference='gh:two/repo#7'))
        self.assertNotEqual(a['task'],b['task'])
    def test_scope_mode_change_invalidates_draft(self):
        draft=self.draft();path=self.root/'app.py';path.chmod(path.stat().st_mode ^ 0o100)
        with self.assertRaisesRegex(ValueError,'inputs_changed'):self.call('materialize',binding=draft['binding'])
    def test_same_task_in_another_worktree_rejects_ledger_reuse(self):
        self.draft();other=Path(self.tmp.name).resolve()/'other'
        subprocess.run(['git','-C',str(self.root),'worktree','add','-q','-b','synthetic-other',str(other)],check=True)
        with self.assertRaisesRegex(ValueError,'identity_changed'):m.Intake(other,self.task)
    def test_cancel_partial_materialization_preserves_owned_evidence(self):
        draft=self.draft();names=list(draft['artifacts']);real_open=os.open
        def crashing(path,*args,**kwargs):
            if str(path)==Path(names[1]).name and args and args[0]&os.O_CREAT:raise KeyboardInterrupt()
            return real_open(path,*args,**kwargs)
        with patch.object(m.os,'open',side_effect=crashing):
            with self.assertRaises(KeyboardInterrupt):self.call('materialize',binding=draft['binding'])
        first=self.root/names[0];saved=first.read_bytes();self.call('cancel')
        with self.assertRaisesRegex(ValueError,'cancelled'):self.call('materialize',binding=draft['binding'])
        self.assertEqual(first.read_bytes(),saved);self.assertFalse((self.root/names[1]).exists())
    def test_changed_retained_draft_rejects_original_binding(self):
        draft=self.draft();controller=m.Intake(self.root,self.task)
        state=json.loads(controller.path.read_text());name=next(iter(draft['artifacts']))
        state['drafts'][-1]['artifacts'][name]='Changed retained evidence\n';controller.path.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError,'binding|integrity|tamper'):self.call('materialize',binding=draft['binding'])
        self.assertFalse((self.root/name).exists())
    def test_conflicting_github_source_identity_rejected(self):
        module=m.ops.load('controller-recovery');real_load=m.ops.load
        def bounded(argv,cwd,env,timeout,output):
            output.write_text(json.dumps(dict(source='gh',repository='one/repo',source_id='7',external_ref='gh-999',url='https://github.com/two/repo/issues/7',title='Synthetic',body='Return two')));return 0
        module.bounded=bounded
        with patch.object(m.ops,'load',side_effect=lambda name:module if name=='controller-recovery' else real_load(name)):
            with self.assertRaisesRegex(ValueError,'source_identity_mismatch'):m.resolve_source(self.root,'gh:one/repo#7')
    def test_oversized_artifacts_are_rejected_without_truncation(self):
        (self.root/'app.py').write_text('x'*m.ops.MAX_REQUEST)
        with self.assertRaisesRegex(ValueError,'too_large:no_truncation'):self.draft()
        self.assertFalse((self.root/'docs'/self.task).exists())
    def test_malformed_manifest_is_explicit_in_readiness(self):
        (self.root/'.nightshift.toml').write_text('not [valid toml')
        result=self.call('view');self.assertEqual(result['readiness']['manifest'],'invalid')
        self.assertFalse((self.root/'docs'/self.task).exists())
    def test_parent_symlink_race_never_writes_outside_repository(self):
        draft=self.draft();outside=Path(self.tmp.name).resolve()/'outside-directory';outside.mkdir()
        real_create=m.create_artifact
        def raced(project,name,content,mode):
            (self.root/'docs').symlink_to(outside,target_is_directory=True)
            return real_create(project,name,content,mode)
        with patch.object(m,'create_artifact',side_effect=raced):
            with self.assertRaises(OSError):self.call('materialize',binding=draft['binding'])
        self.assertEqual(list(outside.iterdir()),[])
        self.assertEqual(m.Intake(self.root,self.task).state['status'],'materializing')
    def test_identical_destination_race_cannot_be_adopted_on_retry(self):
        draft=self.draft();first=next(iter(draft['artifacts']));real_create=m.create_artifact
        def raced(project,name,content,mode):
            path=self.root/name;path.parent.mkdir(parents=True);path.write_bytes(content.encode());path.chmod(mode)
            return real_create(project,name,content,mode)
        with patch.object(m,'create_artifact',side_effect=raced):
            with self.assertRaisesRegex(ValueError,'destination_changed'):self.call('materialize',binding=draft['binding'])
        controller=m.Intake(self.root,self.task);self.assertTrue(controller.state['journal'][first]['conflict'])
        path=self.root/first;inode=path.stat().st_ino
        with self.assertRaisesRegex(ValueError,'destination_changed'):self.call('materialize',binding=draft['binding'])
        self.assertEqual(path.stat().st_ino,inode);self.assertEqual(path.read_text(),draft['artifacts'][first])
    def test_wrong_source_kind_rejected(self):
        module=m.ops.load('controller-recovery');real_load=m.ops.load
        def bounded(argv,cwd,env,timeout,output):
            output.write_text(json.dumps(dict(source='spec',source_id='spec-fake',external_ref='spec:request.md',title='Synthetic',body='Return two')));return 0
        module.bounded=bounded
        with patch.object(m.ops,'load',side_effect=lambda name:module if name=='controller-recovery' else real_load(name)):
            with self.assertRaisesRegex(ValueError,'source_identity_mismatch'):m.resolve_source(self.root,'gh:one/repo#7')

if __name__=='__main__':unittest.main()
