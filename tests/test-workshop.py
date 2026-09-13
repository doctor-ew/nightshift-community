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
elif 'independent reviewer' in system: value={'evidence_audit':'No source claims in this fixture.','approved':True,'oracle_valid':not ((mode=='invalid-oracle' and 'implemented prompt' in system) or (mode=='invalid-scenarios' and 'proposed scenarios' in system)),'issues':[]}
else: value='What would you like to explore?'
if mode=='broken-json' and 'Review the implemented prompt' in system: value='truncated JSON response'
if mode=='missing-oracle' and isinstance(value,dict) and 'oracle_valid' in value: value.pop('oracle_valid')
print(json.dumps(dict(result=json.dumps(value) if isinstance(value,dict) else value,is_error=False,subtype='success',total_cost_usd=3 if mode=='overcost' else .01,usage=dict(input_tokens=100,cache_read_input_tokens=20,cache_creation_input_tokens=10,output_tokens=20),session_id='fixture')))
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
        return json.loads(next((self.project/'.git/nightshift-workshop').glob('workshop-????????????????.json')).read_text())

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

    def test_web_approval_launches_and_completes_once(self):
        self.run_workshop(); s=self.state()
        import importlib.util, time
        from unittest.mock import patch
        module_spec=importlib.util.spec_from_file_location('review',ROOT/'scripts/nightshift-workshop-review.py')
        review=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(review)
        info=review.review(self.project,s['task'])
        with patch.dict(os.environ,self.env,clear=True):
            first=review.approve_and_continue(self.project,s['task'],info['sha256'])
            second=review.approve_and_continue(self.project,s['task'],info['sha256'])
        self.assertEqual(first['pid'],second['pid'])
        deadline=time.monotonic()+15
        while time.monotonic()<deadline and self.state()['status'] not in ('complete','failed','budget_exhausted'):
            time.sleep(.1)
        self.assertEqual(self.state()['status'],'complete')
        self.assertEqual(len(self.state()['calls']),17)

    def test_call_budget_survives_resume(self):
        self.limits('calls = 4');self.run_workshop();self.approve(status=1)
        self.assertEqual(self.state()['status'],'budget_exhausted');self.assertEqual(len(self.state()['calls']),4)
        self.run_workshop(status=1);self.assertEqual(len(self.state()['calls']),4)

    def test_one_repair_retains_evidence(self):
        self.env['FIXTURE_MODE']='reject';self.run_workshop();self.approve(status=1)
        s=self.state();self.assertEqual(s['repairs'],1);self.assertEqual(len(s['calls']),28)
        evidence=Path(s['worktree'])/'docs'/s['task'];self.assertTrue((evidence/'EVALUATION-0.json').exists());self.assertTrue((evidence/'EVALUATION-1.json').exists())

    def test_invalid_oracle_stops_without_repair(self):
        self.env['FIXTURE_MODE']='invalid-oracle'
        self.run_workshop(); self.approve(status=1)
        s=self.state()
        self.assertEqual(s['repairs'],0)
        self.assertEqual(len(s['calls']),17)
        self.assertIn('invalid test oracle',s['failure'])
        review_calls=[json.loads(line)['args'] for line in self.log.read_text().splitlines()
                      if 'Review the implemented prompt' in line]
        payload=json.loads(review_calls[0][-1])
        self.assertEqual(len(payload['observations']),8)
        self.assertEqual(len(payload['cases']),8)
        self.assertTrue(all(r['passed'] for r in payload['grade']['results']))
        self.run_workshop(status=1)
        self.assertEqual(len(self.state()['calls']),17)

    def test_invalid_scenarios_retained_before_implementation(self):
        self.env['FIXTURE_MODE']='invalid-scenarios'
        self.run_workshop();self.approve(status=1)
        s=self.state();artifacts=Path(s['worktree'])/'docs'/s['task']
        self.assertTrue((artifacts/'CASES.json').exists())
        self.assertFalse(json.loads((artifacts/'scenario-review.json').read_text())['oracle_valid'])
        self.assertEqual(len(s['calls']),6)
        self.assertEqual(s['repairs'],0)
        self.assertFalse((Path(s['worktree'])/'prompts/workshop-agent.md').exists())

    def test_review_missing_oracle_decision_fails_closed(self):
        self.env['FIXTURE_MODE']='missing-oracle'
        self.run_workshop(status=1)
        self.assertIn('invalid review schema',self.state()['failure'])
        self.assertEqual(self.state()['repairs'],0)

    def test_malformed_review_reports_stage_and_receipt(self):
        self.env['FIXTURE_MODE']='broken-json'
        self.run_workshop();self.approve(status=1)
        s=self.state()
        self.assertIn('code-review-0: runtime returned malformed JSON',s['failure'])
        self.assertIn('code-review-0.stdout.json',s['failure'])
        lifecycle=Path(s['worktree'])/'.nightshift/agents'/ (s['task']+'.json')
        self.assertEqual(json.loads(lifecycle.read_text())['failure'],s['failure'])
        result=self.command(['bash',str(ROOT/'scripts/nightshift-dashboard.sh'),'--project',str(self.project),'--json'])
        self.assertIn('runtime returned malformed JSON',result.stdout)

    def test_retry_final_review_preserves_history_and_costs(self):
        self.env['FIXTURE_MODE']='broken-json'
        self.run_workshop();self.approve(status=1)
        before=self.state();artifacts=Path(before['worktree'])/'docs'/before['task']
        raw=(artifacts/'calls/code-review-0.stdout.json').read_bytes()
        self.env.pop('FIXTURE_MODE')
        self.command(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'claude','brief.md','--retry-review','--dashboard','off'])
        s=self.state();self.assertEqual(s['status'],'complete');self.assertEqual(len(s['calls']),18)
        self.assertAlmostEqual(s['cost_usd'],.18)
        self.assertEqual(s['calls'][16]['status'],'failed')
        self.assertEqual((artifacts/'calls/code-review-0.stdout.json').read_bytes(),raw)
        self.assertTrue((artifacts/'calls/code-review-0.retry-1.stdout.json').exists())
        self.assertTrue((artifacts/'FAILED-code-review-0.json').exists())

    def test_retry_refuses_drift_and_semantic_failure(self):
        self.env['FIXTURE_MODE']='broken-json';self.run_workshop();self.approve(status=1)
        s=self.state();artifact=Path(s['worktree'])/'prompts/workshop-agent.md'
        artifact.write_text('changed')
        self.run_workshop('--retry-review',status=1)
        self.assertEqual(len(self.state()['calls']),17)

    def test_retry_cannot_bypass_rejected_review(self):
        self.env['FIXTURE_MODE']='invalid-oracle';self.run_workshop();self.approve(status=1)
        result=self.run_workshop('--retry-review',status=1)
        self.assertIn('not failed behavior or safety gates',result.stdout)
        self.assertEqual(len(self.state()['calls']),17)

    def test_retry_cannot_repeat_forever(self):
        self.env['FIXTURE_MODE']='broken-json';self.run_workshop();self.approve(status=1)
        self.run_workshop('--retry-review',status=1)
        self.assertEqual(len(self.state()['calls']),18)
        self.run_workshop('--retry-review',status=1)
        self.assertEqual(len(self.state()['calls']),18)

    def test_prior_evidence_policy_cannot_reuse_cached_results(self):
        self.run_workshop()
        path=next((self.project/'.git/nightshift-workshop').glob('workshop-????????????????.json'))
        s=json.loads(path.read_text());s['identity'].pop('evidence_policy');path.write_text(json.dumps(s))
        result=self.run_workshop(status=1)
        self.assertIn('evidence policy',result.stdout)
        self.assertEqual(len(self.state()['calls']),4)

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
