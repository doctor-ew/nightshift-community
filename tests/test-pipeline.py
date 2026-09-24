#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load('pipeline','scripts/nightshift-pipeline.py')
f=load('fixture','tests/nightshift-behavior-fixture.py')

class PipelineTest(unittest.TestCase):
 def test_saved_answers_missing_routes_failed_evidence_resume_and_manual_boundary(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp).resolve()/'project';f.prepare(ROOT,p,task='sample',manual=True,final=True)
   settings=dict(ref='gh:sample',provider='claude',model='fixture',policy='claude-only',auth='subscription',branch='none',base='',push=False,pr=False)
   decisions=m.load('console-decisions');q=decisions.request(p,'sample',dict(question='Reviewer?',reason='Policy',options=[],decision_key='reviewer'))
   decisions.respond(p,'sample',q['sha256'],'','Separate Claude; retain existing draft.')
   ledger=m.load('ticket-budget');ledger.update(p,'sample','reserve','existing',max_calls=10);ledger.update(p,'sample','finish','existing',outcome='failed')
   before=ledger.ledger_path(p,'sample').read_bytes();calls=[]
   def run(stage,handoff,receipt):
    calls.append(stage);bundle=json.loads(handoff.read_text());self.assertIn('Separate Claude',json.dumps(bundle['decisions']))
    if stage=='review' and calls.count(stage)==1:return 0 # process success without evidence
    log=p/'docs/sample'/(stage+'-check.log')
    result=subprocess.run(['python3','tests/test_fixture_sample.py'],cwd=p,capture_output=True,text=True)
    self.assertEqual(result.returncode,0);log.write_text(result.stdout+result.stderr)
    receipt.write_text(json.dumps(dict(version=1,task='sample',stage=stage,status='pass',findings=[],checks=[dict(command='python3 tests/test_fixture_sample.py',exit_code=result.returncode)],evidence=[dict(path=str(log.relative_to(p)),sha256=m.sha(log))])))
    return 0
   with patch.dict(os.environ,{'NIGHTSHIFT_ROUTING_FILE':str(p/'missing.json')},clear=False):
    controller=m.Pipeline(p,'sample',settings,run)
    with self.assertRaisesRegex(ValueError,'routing file is missing'):controller.run()
    self.assertEqual(calls,[]);self.assertEqual(ledger.ledger_path(p,'sample').read_bytes(),before)
   with patch.dict(os.environ,{'NIGHTSHIFT_ROUTING_FILE':str(ROOT/'routing.json')},clear=False):
    controller=m.Pipeline(p,'sample',settings,run);self.assertEqual(controller.run(),1)
    self.assertEqual(controller.state['next_action'],'review');self.assertEqual(calls,['product','adversarial','implement','review'])
    resumed=m.Pipeline(p,'sample',settings,run);self.assertEqual(resumed.run(),1)
    self.assertEqual(calls,['product','adversarial','implement','review','review','drift','qa'])
    self.assertEqual(resumed.state['status'],'pending_manual_acceptance')
    self.assertEqual(ledger.ledger_path(p,'sample').read_bytes(),before)
    repeated=m.Pipeline(p,'sample',settings,run);self.assertEqual(repeated.run(),1)
    self.assertEqual(len(calls),7)
    self.assertEqual(len(decisions.read(decisions.location(p,'sample'))['requests']),1)
    self.assertTrue(all(a['route']['provider']=='claude' for a in repeated.state['attempts']))
    # A changed implementation invalidates relevant reviews, not the existing draft.
    (p/'fixture_source_sample.py').write_text('answer = 43\n')
    refreshed=m.Pipeline(p,'sample',settings,run);refreshed.refresh()
    self.assertIn('product',refreshed.state['completed']);self.assertIn('implement',refreshed.state['completed'])
    self.assertNotIn('review',refreshed.state['completed']);self.assertNotIn('qa',refreshed.state['completed'])
    self.assertEqual(len(refreshed.state['attempts']),7)

 def test_real_worker_dispatch_retains_budget_and_rejects_empty_success(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp).resolve();p=base/'project';p.mkdir()
   import shutil
   shutil.copy(ROOT/'nightshift.toml',p/'.nightshift.toml')
   shutil.copy(ROOT/'routing.json',p/'routing.json')
   f.prepare(ROOT,p,task='sample',manual=True,final=True)
   binary=base/'bin';binary.mkdir();home=base/'home';home.mkdir()
   stub=binary/'claude'
   stub.write_text('''#!/usr/bin/env python3
import hashlib,json,os,pathlib,subprocess,sys
if sys.argv[1:2]==['auth']:
 print(json.dumps(dict(loggedIn=True,authMethod='claude.ai',apiProvider='firstParty')));sys.exit(0)
p=pathlib.Path.cwd();stage=os.environ['NIGHTSHIFT_PIPELINE_STAGE'];receipt=pathlib.Path(os.environ['NIGHTSHIFT_STAGE_RECEIPT'])
marker=p/'docs/sample/empty-review'
if stage=='review' and not marker.exists():
 marker.write_text('Process exited zero without evidence.');sys.exit(0)
result=subprocess.run([sys.executable,'tests/test_fixture_sample.py'],capture_output=True,text=True)
log=p/'docs/sample'/(stage+'-real-worker.log');log.write_text(result.stdout+result.stderr)
receipt.write_text(json.dumps(dict(version=1,task='sample',stage=stage,status='pass',findings=[],checks=[dict(command='python3 tests/test_fixture_sample.py',exit_code=result.returncode)],evidence=[dict(path=str(log.relative_to(p)),sha256=hashlib.sha256(log.read_bytes()).hexdigest())])))
''');stub.chmod(0o755)
   mex=binary/'mex';mex.write_text('#!/bin/sh\nexit 1\n');mex.chmod(0o755)
   settings=dict(ref='gh:sample',provider='claude',model='fixture',policy='claude-only',auth='subscription',branch='none',base='',push=False,pr=False)
   env=dict(PATH=str(binary)+os.pathsep+os.environ['PATH'],HOME=str(home),NIGHTSHIFT_HOME=str(home),NIGHTSHIFT_ROUTING_FILE=str(ROOT/'routing.json'),NIGHTSHIFT_SYNC_CHECK='off',NIGHTSHIFT_DASHBOARD='off',NIGHTSHIFT_OUTPUT='verbose',NIGHTSHIFT_TICKET_JSON=json.dumps(dict(source='github',repository='fixture/repo',source_id='sample')))
   with patch.dict(os.environ,env,clear=False):
    first=m.Pipeline(p,'sample',settings);self.assertEqual(first.run(),1)
    self.assertEqual(first.state['next_action'],'review',json.dumps(first.state)+'\n'+''.join(x.read_text() for x in first.directory.glob('*.log')))
    ledger=m.load('ticket-budget');before=ledger.snapshot(p,'sample');deadline=json.loads(ledger.ledger_path(p,'sample').read_text())['deadline_at'];self.assertEqual(before['calls_reserved'],4)
    second=m.Pipeline(p,'sample',settings);self.assertEqual(second.run(),1)
    self.assertEqual(second.state['status'],'pending_manual_acceptance')
    after=ledger.snapshot(p,'sample');self.assertEqual(after['calls_reserved'],7)
    self.assertEqual(json.loads(ledger.ledger_path(p,'sample').read_text())['deadline_at'],deadline)
    third=m.Pipeline(p,'sample',settings);self.assertEqual(third.run(),1)
    self.assertEqual(ledger.snapshot(p,'sample')['calls_reserved'],7)
    self.assertEqual([a['stage'] for a in third.state['attempts']],['product','adversarial','implement','review','review','drift','qa'])

 def test_no_completion_from_prose_or_forged_hash(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp).resolve();receipt=p/'result.json';log=p/'log';log.write_text('passed')
   value=dict(version=1,task='t',stage='review',status='pass',findings=[],checks=[],evidence=[])
   receipt.write_text(json.dumps(value))
   with self.assertRaisesRegex(ValueError,'passing_evidence_missing'):m.validate_receipt(receipt,'t','review',p)
   value.update(checks=[dict(command='true',exit_code=0)],evidence=[dict(path='log',sha256='0'*64)]);receipt.write_text(json.dumps(value))
   with self.assertRaisesRegex(ValueError,'stale_stage_evidence'):m.validate_receipt(receipt,'t','review',p)

if __name__=='__main__':unittest.main()
