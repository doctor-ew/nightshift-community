"""Offline contracts: budgets, isolated calls, explicit approval, evidence and no Beads."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
args=sys.argv[1:]
if args==['--version']: print('fixture 1');sys.exit()
if args[:2]==['auth','status']:
 print(json.dumps(dict(loggedIn=True,authMethod='claude.ai',apiProvider='firstParty')));sys.exit()
system=args[args.index('--system-prompt')+1]; payload=args[-1]
with open(os.environ['CALL_LOG'],'a') as f:
 f.write(json.dumps(dict(args=args,cwd=os.getcwd(),api=bool(os.getenv('ANTHROPIC_API_KEY'))))+'\n')
mode=os.getenv('FIXTURE_MODE','')
if mode=='hang': time.sleep(30)
if mode=='no-receipt': print('{}');sys.exit()
if system.startswith('Return {'): value={'ready':True}
elif 'Specify a small' in system: value={'title':'Coach','scope':'standalone_prompt','requirements':[{'id':'AC-1','criterion':'Coach respectfully'}],'exclusions':['applications']}
elif 'Independently author' in system:
 value={'cases':[dict(slot,input='Scenario '+str(i),expected='Respectful response') for i,slot in enumerate(json.loads(payload)['slots'])]}
elif 'Implement only' in system: value={'lines':['Coach respectfully. '+str(i) for i in range(20)]}
elif 'Grade observed' in system:
 value={'results':[dict(id='case-'+str(i+1),passed=mode!='reject',reason='Observed') for i in range(8)]}
elif 'independent reviewer' in system: value={'approved':True,'issues':[]}
else: value='What would you like to explore?'
print(json.dumps(dict(result=json.dumps(value) if isinstance(value,dict) else value,is_error=False,total_cost_usd=3 if mode=='overcost' else .01,usage=dict(input_tokens=100,cache_read_input_tokens=20,cache_creation_input_tokens=10,output_tokens=20),session_id='fixture')))
'''

class WorkshopTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.project=self.base/'project';self.project.mkdir()
        self.bin=self.base/'bin';self.bin.mkdir()
        (self.bin/'claude').write_text(FAKE);(self.bin/'claude').chmod(0o755)
        # If a stage touches Beads, fail loudly instead of using a real database.
        (self.bin/'bd').write_text('#!/bin/sh\necho beads-was-called >> "$CALL_LOG"\nexit 99\n');(self.bin/'bd').chmod(0o755)
        self.log=self.base/'calls'
        self.env=dict(os.environ,PATH=str(self.bin)+os.pathsep+os.environ['PATH'],HOME=str(self.base),
            NIGHTSHIFT_HOME=str(self.base/'home'),GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_NOSYSTEM='1',
            GIT_AUTHOR_NAME='Test',GIT_AUTHOR_EMAIL='test@example.invalid',GIT_COMMITTER_NAME='Test',
            GIT_COMMITTER_EMAIL='test@example.invalid',CALL_LOG=str(self.log),NIGHTSHIFT_UPDATE_GUARD='1')
        (self.project/'brief.md').write_text('# Brief\nCreate a respectful coach prompt.\n')
        self.command(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'init','--project',str(self.project),'--profile','workshop','--include','brief.md'])

    def command(self,argv,status=0):
        r=subprocess.run(argv,env=self.env,cwd=self.project,capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,status,r.stdout+r.stderr);return r

    def run_workshop(self,*args,status=0):
        return self.command([sys.executable,str(ROOT/'scripts/nightshift-workshop.py'),'--project',str(self.project),'--ref','brief.md',*args],status)

    def state(self):
        return json.loads(next((self.project/'.git/nightshift-workshop').glob('*.json')).read_text())

    def approve(self,**kw):
        s=self.state();spec=Path(s['worktree'])/'docs'/s['task']/'SPEC.md'
        return self.run_workshop('--approve-spec',hashlib.sha256(spec.read_bytes()).hexdigest(),**kw)

    def limits(self,text):
        with (self.project/'.nightshift.toml').open('a') as f:f.write('\n[workshop]\n'+text+'\n')

    def test_complete_resume_isolation_and_drift(self):
        self.run_workshop();s=self.state()
        self.assertEqual(s['status'],'awaiting_spec_approval');self.assertEqual(len(s['calls']),4)
        dashboard = self.command(['bash', str(ROOT/'scripts/nightshift-dashboard.sh'), '--project', str(self.project), '--json'])
        self.assertIn('needs-decision', dashboard.stdout)
        self.assertIn('nightshift-workshop', dashboard.stdout)
        self.assertFalse((Path(s['worktree'])/'prompts/workshop-agent.md').exists())
        self.run_workshop('--approve-spec','incorrect');self.assertEqual(len(self.state()['calls']),4)
        self.approve();s=self.state();self.assertEqual(s['status'],'complete');self.assertEqual(len(s['calls']),17)
        self.assertEqual(s['input_tokens'],17*130);self.assertEqual(s['output_tokens'],340)
        self.run_workshop();self.assertEqual(len(self.state()['calls']),17)
        self.assertFalse((self.project/'prompts').exists())
        for line in self.log.read_text().splitlines():
            c=json.loads(line);a=c['args'];self.assertEqual(a[a.index('--tools')+1],'')
            self.assertEqual(a[a.index('--setting-sources')+1],'');self.assertNotIn(str(self.project),c['cwd'])
            self.assertIn('--safe-mode',a);self.assertIn('--no-session-persistence',a);self.assertFalse(c['api'])
        (Path(s['worktree'])/'prompts/workshop-agent.md').write_text('tampered')
        self.run_workshop(status=1);self.assertEqual(self.state()['status'],'failed')

    def test_web_approval_continues_without_hash(self):
        self.run_workshop(); s=self.state()
        import importlib.util
        module_spec=importlib.util.spec_from_file_location('review',ROOT/'scripts/nightshift-workshop-review.py')
        review=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(review)
        info=review.review(self.project,s['task'])
        self.assertTrue(Path(info['copy_path']).exists())
        review.approve(self.project,s['task'],info['sha256'])
        self.run_workshop();self.assertEqual(self.state()['status'],'complete')

    def test_call_budget_survives_resume(self):
        self.limits('calls = 4');self.run_workshop();self.approve(status=1)
        self.assertEqual(self.state()['status'],'budget_exhausted');self.assertEqual(len(self.state()['calls']),4)
        self.run_workshop(status=1);self.assertEqual(len(self.state()['calls']),4)

    def test_one_repair_retains_evidence(self):
        self.env['FIXTURE_MODE']='reject';self.run_workshop();self.approve(status=1)
        s=self.state();self.assertEqual(s['repairs'],1);self.assertEqual(len(s['calls']),28)
        evidence=Path(s['worktree'])/'docs'/s['task'];self.assertTrue((evidence/'EVALUATION-0.json').exists());self.assertTrue((evidence/'EVALUATION-1.json').exists())

    def test_missing_receipt_is_charged_and_terminal(self):
        self.env['FIXTURE_MODE']='no-receipt';self.run_workshop(status=1)
        self.assertEqual(self.state()['cost_usd'],.25);self.run_workshop(status=1)
        self.assertEqual(len(self.log.read_text().splitlines()),1)

    def test_timeout_is_bounded_and_terminal(self):
        self.env['FIXTURE_MODE']='hang';self.limits('call_seconds = 1');self.run_workshop(status=1)
        self.assertEqual(self.state()['status'],'failed');self.assertLess(self.state()['elapsed_seconds'],10)

    def test_reported_cost_overrun_stops_and_retains_receipt(self):
        self.env['FIXTURE_MODE']='overcost';self.run_workshop(status=1)
        self.assertEqual(self.state()['status'],'budget_exhausted')
        self.assertEqual(self.state()['cost_usd'],3)
        self.assertEqual(len(self.state()['calls']),1)

    def test_api_does_not_use_subscription(self):
        self.env['ANTHROPIC_API_KEY']='fixture-not-a-key';self.run_workshop('--auth','api')
        for line in self.log.read_text().splitlines():
            c=json.loads(line);self.assertTrue(c['api']);self.assertIn('--bare',c['args'])

    def test_factory_dispatch(self):
        self.command(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'brief.md','--project',str(self.project),'--dashboard','off','--output','concise'])
        self.assertEqual(self.state()['status'],'awaiting_spec_approval')

if __name__=='__main__': unittest.main()
