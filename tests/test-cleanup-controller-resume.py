#!/usr/bin/env python3
"""Actual owned-worktree preservation after schema-failed Green implementation."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
pipeline=load('resume_pipeline','scripts/nightshift-pipeline.py')
fixture=load('resume_fixture','tests/nightshift-behavior-fixture.py')

class ControllerResume(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='nightshift-controller-resume-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.project=self.base/'primary';self.project.mkdir()
        def git(*args):subprocess.run(['git','-C',str(self.project),*args],check=True,capture_output=True)
        git('init','-q');git('config','user.name','fixture');git('config','user.email','fixture@local')
        (self.project/'README.md').write_text('synthetic owned-worktree fixture')
        shutil.copy(ROOT/'nightshift.toml',self.project/'.nightshift.toml');shutil.copy(ROOT/'routing.json',self.project/'routing.json')
        git('add','.');git('commit','-qm','fixture baseline')
        result=self.work('prepare');self.assertEqual(result.returncode,0,result.stderr)
        self.target=Path(json.loads(result.stdout)['worktree'])
        self.fixture=fixture.prepare(ROOT,self.target,task='sample',final=True)
        self.source=Path(self.fixture['source'])
        self.env={k:v for k,v in os.environ.items() if not k.startswith('NIGHTSHIFT_')}
        self.env['NIGHTSHIFT_ROUTING_FILE']=str(ROOT/'routing.json')
        settings=dict(ref='gh:sample',provider='codex',model='synthetic',policy='standard',auth='subscription',branch='auto',base='',push=False,pr=False)
        with patch.dict(os.environ,self.env,clear=True):
            self.controller=pipeline.Pipeline(self.target,'sample',settings,lambda *args:1)
            self.controller.refresh()
            receipt=self.controller.directory/'adversarial-1.json'
            report=dict(version=1,task='sample',stage='adversarial',status='pass',findings=[],checks=[dict(command='synthetic independently attested classification',exit_code=0)],evidence=[dict(path='docs/sample/behavior-scenarios.json',sha256=pipeline.sha(self.target/'docs/sample/behavior-scenarios.json'))])
            receipt.write_text(json.dumps(report))
            self.controller.state['completed']['adversarial']=dict(receipt=str(receipt),sha256=pipeline.sha(receipt),input_sha256=pipeline.inputs(self.target,'sample','adversarial',self.controller.state))
            failed=self.controller.directory/'implement-1.json'
            failed.write_text(json.dumps(dict(version=1,task='sample',stage='implement',status='pass',findings=[],checks=[dict(command='synthetic retained expected RED',exit_code=1)],evidence=[])))
            self.controller.state['attempts']=[dict(stage='implement',status='fail',category='schema',reason='stage_receipt.checks[0].exit_code:required_check_failed',receipt=str(failed),source_sha256=pipeline.source(self.target,'sample'))]
            self.controller.state.update(status='blocked',next_action='implement',finding_stage='implement')
            self.controller.save()
        self.original_state=self.controller.path.read_bytes();self.original_failed=failed.read_bytes()

    def work(self,operation):
        return subprocess.run(['bash',str(ROOT/'scripts/nightshift-worktree.sh'),operation,'sample','--project',str(self.project)],capture_output=True,text=True,timeout=30)

    def cleanup(self):
        return subprocess.run(['python3',str(ROOT/'scripts/nightshift-cleanup.py'),'sample','--project',str(self.project)],env=self.env,capture_output=True,text=True,timeout=30)

    def test_owned_green_is_preserved_and_reenters_without_approving_review(self):
        self.assertNotEqual(self.work('check').returncode,0)
        result=self.cleanup();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'resumable')
        self.assertEqual(self.work('check').returncode,0)
        self.assertEqual(self.work('prepare').returncode,0)
        self.assertEqual(self.source.read_text(),'answer = 42\n')
        self.assertEqual(self.controller.path.read_bytes(),self.original_state)
        self.assertEqual((self.controller.directory/'implement-1.json').read_bytes(),self.original_failed)
        self.assertNotIn('implement',json.loads(self.controller.path.read_text())['completed'])
        self.assertNotIn('review',json.loads(self.controller.path.read_text())['completed'])
        self.source.write_text('answer = 43\n')
        self.assertNotEqual(self.work('check').returncode,0)
        self.assertNotEqual(self.cleanup().returncode,0)

    def test_unknown_or_non_schema_source_cannot_gain_resume(self):
        self.controller.state['attempts'][-1].update(category='substantive',reason='stage_failed')
        self.controller.save()
        result=self.cleanup();self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertIn('source_changes_require_review',result.stdout)

    def test_changed_frozen_case_or_accepted_evidence_blocks(self):
        scenarios=self.target/'docs/sample/behavior-scenarios.json'
        scenarios.write_text(scenarios.read_text()+'\n')
        result=self.cleanup();self.assertNotEqual(result.returncode,0,result.stdout)

    def test_green_source_without_current_final_proof_blocks(self):
        self.source.write_text('answer = 43\n')
        self.controller.state['attempts'][-1]['source_sha256']=pipeline.source(self.target,'sample')
        self.controller.save()
        result=self.cleanup();self.assertNotEqual(result.returncode,0,result.stdout)

    def test_changed_failed_stage_receipt_blocks(self):
        failed=self.controller.directory/'implement-1.json'
        value=json.loads(failed.read_text());value['checks'][0]['exit_code']=0
        failed.write_text(json.dumps(value))
        result=self.cleanup();self.assertNotEqual(result.returncode,0,result.stdout)

    def test_foreign_worktree_identity_blocks(self):
        self.controller.state['worktree']=str(self.project);self.controller.save()
        result=self.cleanup();self.assertNotEqual(result.returncode,0,result.stdout)

if __name__=='__main__':unittest.main()
