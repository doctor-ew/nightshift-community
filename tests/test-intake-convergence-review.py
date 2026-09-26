#!/usr/bin/env python3
"""Independent convergence regressions adapted from public intake hardening."""
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('intake_convergence_fixture',ROOT/'tests/test-intake-review.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class IntakeConvergence(unittest.TestCase):
    def setUp(self):
        self.fixture=f.IntakeReview();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.c=self.fixture.c
    def preview(self):return self.fixture.preview()
    def apply(self,row):return self.c.apply(row['binding'],'synthetic','convergence')
    def test_input_mode_change_invalidates_preview(self):
        row=self.preview();path=self.root/'app.py';path.chmod(path.stat().st_mode ^ 0o100)
        with self.assertRaises(ValueError):self.apply(row)
        self.assertFalse((self.root/'docs'/self.c.task).exists())
    def test_manifest_change_invalidates_preview(self):
        row=self.preview();(self.root/'.nightshift.toml').write_text('[providers]\npolicy="local-only"\n')
        with self.assertRaises(ValueError):self.apply(row)
        self.assertFalse((self.root/'docs'/self.c.task).exists())
    def test_retained_payload_cannot_add_uninspected_file(self):
        row=self.preview();state=json.loads(self.c.path.read_text())
        state['drafts'][row['binding']]['files']['uninspected.txt']='Not in inspected preview\n'
        self.c.path.write_text(json.dumps(state))
        with self.assertRaises(ValueError):self.apply(row)
        self.assertFalse((self.root/'uninspected.txt').exists())
        self.assertFalse((self.root/'docs'/self.c.task).exists())
    def test_canonical_and_private_control_paths_rejected(self):
        for name in ('nested/.git/config','nested/.codex/config','.env.production','nested/.agents/context','./app.py'):
            with self.subTest(name=name):
                path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
                if name!='./app.py':path.write_text('Synthetic private control\n')
                choices=copy.deepcopy(self.fixture.choices);choices['scope']=[name]
                with self.assertRaises(ValueError):self.fixture.preview(choices)
    def test_changed_product_decision_invalidates_preview(self):
        row=self.preview();decisions=m.ops.load('console-decisions')
        question=decisions.request(self.root,self.c.task,dict(question='Choose behavior',reason='Synthetic decision',options=[],continuation='none',decision_key='convergence'))
        decisions.respond(self.root,self.c.task,question['sha256'],'','Changed product choice')
        with self.assertRaises(ValueError):self.apply(row)
        self.assertFalse((self.root/'docs'/self.c.task).exists())
    def test_parent_symlink_race_never_writes_outside_project(self):
        row=self.preview();outside=self.root/'outside';outside.mkdir()
        real=m.create_artifact
        def raced(project,name,content,mode):
            (self.root/'docs').symlink_to(outside,target_is_directory=True)
            return real(project,name,content,mode)
        with patch.object(m,'create_artifact',side_effect=raced):
            with self.assertRaises((OSError,ValueError)):self.apply(row)
        self.assertEqual(list(outside.iterdir()),[])
    def test_identical_destination_race_remains_unowned_on_retry(self):
        row=self.preview();real=m.create_artifact;names=[]
        def raced(project,name,content,mode):
            names.append(name);path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(content.encode());path.chmod(mode)
            return real(project,name,content,mode)
        with patch.object(m,'create_artifact',side_effect=raced):
            with self.assertRaises((OSError,ValueError)):self.apply(row)
        first=self.root/names[0];inode=first.stat().st_ino;saved=first.read_bytes()
        with self.assertRaises(ValueError):self.apply(row)
        self.assertEqual(first.stat().st_ino,inode);self.assertEqual(first.read_bytes(),saved)
    def test_complete_journaled_file_replays_without_replacement(self):
        row=self.preview();real=m.create_artifact;created=[]
        def crashing(project,name,content,mode):
            if created:raise KeyboardInterrupt('synthetic crash before second creation')
            value=real(project,name,content,mode);created.append(name);return value
        with patch.object(m,'create_artifact',side_effect=crashing):
            with self.assertRaises(KeyboardInterrupt):self.apply(row)
        path=self.root/created[0];inode=path.stat().st_ino
        self.assertEqual(self.apply(row)['status'],'prepared')
        self.assertEqual(path.stat().st_ino,inode)
        self.assertFalse(m.ops.Operations(self.root,self.c.task).state['authorizations'])

    def test_later_identical_destination_race_is_not_adopted(self):
        row=self.preview();names=list(row['files']);real=m.create_artifact
        def raced(project,name,content,mode):
            result=real(project,name,content,mode)
            if name==names[0]:
                path=self.root/names[1];path.write_bytes(row['files'][names[1]].encode());path.chmod(mode)
            return result
        with patch.object(m,'create_artifact',side_effect=raced):
            with self.assertRaises(ValueError):self.apply(row)
        with self.assertRaises(ValueError):self.apply(row)
    def test_completed_artifact_mutation_cannot_be_sealed_as_prepared(self):
        row=self.preview();names=list(row['files']);real=m.create_artifact
        def raced(project,name,content,mode):
            result=real(project,name,content,mode)
            if name==names[-1]:(self.root/names[0]).write_text('Concurrent operator change\n')
            return result
        with patch.object(m,'create_artifact',side_effect=raced):
            with self.assertRaises(ValueError):self.apply(row)
        self.assertEqual((self.root/names[0]).read_text(),'Concurrent operator change\n')
    def test_source_change_during_materialization_blocks_success(self):
        row=self.preview();names=list(row['files']);real=m.create_artifact
        def raced(project,name,content,mode):
            result=real(project,name,content,mode)
            if name==names[-1]:self.fixture.source['body']='Changed during materialization\n'
            return result
        with patch.object(m,'create_artifact',side_effect=raced):
            with self.assertRaises(ValueError):self.apply(row)
        state=json.loads(self.c.path.read_text())
        self.assertNotEqual(state['drafts'][row['binding']]['status'],'prepared')
    def test_configuration_change_during_materialization_blocks_success(self):
        row=self.preview();names=list(row['files']);real=m.create_artifact
        def raced(project,name,content,mode):
            result=real(project,name,content,mode)
            if name==names[-1]:(self.root/'.nightshift.toml').write_text('[providers]\npolicy="local-only"\n')
            return result
        with patch.object(m,'create_artifact',side_effect=raced):
            with self.assertRaises(ValueError):self.apply(row)
        state=json.loads(self.c.path.read_text())
        self.assertNotEqual(state['drafts'][row['binding']]['status'],'prepared')
    def test_prepared_replay_rejects_changed_external_test_input(self):
        row=self.preview();self.apply(row)
        path=self.root/'test_app.py';path.write_text('Changed test after preparation\n')
        with self.assertRaises(ValueError):self.apply(row)
        self.assertEqual(path.read_text(),'Changed test after preparation\n')
    def resolve_fake(self,reference,source):
        module_spec=importlib.util.spec_from_file_location('intake_convergence_source',ROOT/'scripts/nightshift-intake.py')
        module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
        recovery=module.ops.load('controller-recovery');load=module.ops.load
        def bounded(argv,project,env,timeout,output):
            output.write_text(json.dumps(source));return 0
        recovery.bounded=bounded
        with patch.object(module.ops,'load',side_effect=lambda name:recovery if name=='controller-recovery' else load(name)):
            return module.resolve(self.root,reference)
    def test_local_source_identifier_and_external_reference_must_match(self):
        import hashlib
        body=(self.root/'request.md').read_text()
        source=dict(source='spec',source_id='spec-'+hashlib.sha256(b'request.md').hexdigest()[:16],external_ref='spec:request.md',
            source_path='request.md',source_revision=hashlib.sha256(body.encode()).hexdigest(),body=body,title='Synthetic')
        for key,value in [('source_id','unrelated-task'),('external_ref','spec:unrelated.md')]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'identity'):
                self.resolve_fake('spec:request.md',dict(source,**{key:value}))
    def test_shorthand_github_reference_cannot_resolve_other_issue_number(self):
        source=dict(source='gh',source_id='47',external_ref='gh-47',repository='example/repo',
            url='https://github.com/example/repo/issues/47',body='Synthetic body',title='Synthetic')
        with self.assertRaisesRegex(ValueError,'identity'):
            self.resolve_fake('gh:7',source)

if __name__=='__main__':unittest.main()
