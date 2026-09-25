#!/usr/bin/env python3
"""Compact recovery through the real controller; all provider responses synthetic."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('legacy',Path(__file__).with_name('test-controller-recovery.py'))
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
m=legacy.m

class Decisions(legacy.RecoveryTest):
    # Run only these compact tests, not inherited legacy fixture tests.
    def setup_plan(self):
        self.env2=patch.dict(os.environ,{'NIGHTSHIFT_JEV_MODEL':'jev-1.13.0','TYPESAFE_API_KEY':'synthetic-only'})
        self.env2.start();self.addCleanup(self.env2.stop)
        value,_=m.evidence(self.project,'T-1')
        refs=[]
        for name in value['source_files']:
            refs.append(dict(id='source-'+str(len(refs)),role='source',path=name,start_line=1,end_line=len((self.target/name).read_text().splitlines())))
        for name in ('docs/T-1/SPEC.md','docs/T-1/behavior-scenarios.json'):
            refs.append(dict(id='requirement-'+str(len(refs)),role='requirement',path=name,start_line=1,end_line=len((self.target/name).read_text().splitlines())))
        refs.append(dict(id='assertion',role='assertion',path='evals/unit/test-source.sh',start_line=1,end_line=4))
        refs.append(dict(id='observed',role='observation',path='test-source.sh',start_line=1,end_line=1))
        self.plan=dict(version=1,checks=[dict(id='test-source.sh',argv=['bash','evals/unit/test-source.sh'])],limits=dict(wall_seconds=600,active_seconds=600,provider_calls=16),decisions=[])
        for kind in ('requirement_supported','finding_resolved','scope_matches','oracle_valid'):
            self.plan['decisions'].append(dict(id=kind,kind=kind,case_ids=['CASE-one'],ac_ids=['AC-1'],finding_ids=[f['id'] for f in value['findings']] if kind=='finding_resolved' else [],references=refs,high_risk=False))
        self.save_plan();self.network=[];self.review_calls=[]

    def save_plan(self):
        (self.docs/'recovery-plan.json').write_text(json.dumps(self.plan))
        subprocess.run(['git','-C',str(self.target),'add','docs/T-1/recovery-plan.json'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(self.target),'commit','-qm','explicit evidence plan'],check=True,capture_output=True)

    def transport(self,cfg,key,body):
        self.network.append(json.loads(body))
        return json.dumps(dict(model=cfg['model'],answers=dict(supported=dict(type='noul',noul=.99)))).encode()

    def escalate(self,value,packet,mode,output,timeout):
        self.review_calls.append(packet['id'])
        return dict(decision='yes',packet_sha256=m.load('decision-engine').digest(packet),reviewer_id='independent-fixture',evidence=[r['id'] for r in packet['evidence']])

    def compact(self,operation='authorize',expected=None):
        original=m.compact_verdict
        def invoke(*args,**kwargs):return original(*args,**kwargs,transport=self.transport,escalator=self.escalate)
        with patch.object(m,'compact_verdict',invoke):
            return m.operate(self.project,'T-1',operation,expected or self.assess()['sha256'],'fixture-operator')

    def test_compact_sequence_reuses_obligations_and_preserves_original_evidence(self):
        self.setup_plan();a=self.assess();self.assertEqual(a['decisions']['status'],'ready',a['decisions'])
        before={str(p):p.read_bytes() for p in self.docs.rglob('*') if p.is_file()}
        result=self.compact(expected=a['sha256']);self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(len(self.network),4)  # review reuses adoption's identical requirement judgment
        self.assertTrue(all(len(json.dumps(x).encode())<24576 for x in self.network))
        self.assertTrue(all('corpus' not in x for x in self.network))
        self.assertEqual(m.p.snapshot(self.project,'T-1')['attempts'],self.state['attempts'])
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.docs.rglob('*') if p.is_file()})
        self.assertEqual(m.p.view(self.project,'T-1')['status'],'pending_manual_acceptance')
        again=self.compact(expected=a['sha256']);self.assertEqual(again['allowance'],result['allowance']);self.assertEqual(len(self.network),4)

    def test_missing_plan_blocks_before_grant(self):
        a=self.assess()
        with self.assertRaisesRegex(ValueError,'preflight'):self.compact(expected=a['sha256'])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))

    def test_omitted_source_or_finding_blocks_before_grant(self):
        self.setup_plan()
        self.plan['decisions'][2]['references']=[r for r in self.plan['decisions'][2]['references'] if r['path']!='source.txt']
        self.save_plan();a=self.assess();self.assertEqual(a['decisions']['status'],'blocked')
        with self.assertRaisesRegex(ValueError,'preflight'):self.compact(expected=a['sha256'])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))

    def test_findings_cannot_hide_in_requirement_question(self):
        self.setup_plan()
        self.plan['decisions'][0]['finding_ids']=self.plan['decisions'][1]['finding_ids']
        self.plan['decisions']=[d for d in self.plan['decisions'] if d['kind']!='finding_resolved']
        self.save_plan();a=self.assess();self.assertEqual(a['decisions']['status'],'blocked')
        with self.assertRaisesRegex(ValueError,'preflight'):self.compact(expected=a['sha256'])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))

    def test_oversize_and_missing_credentials_precede_grant(self):
        self.setup_plan()
        with patch.dict(os.environ,{'TYPESAFE_API_KEY':''}):
            a=self.assess();self.assertEqual(a['decisions']['reason'],'decision_credentials_missing')
            with self.assertRaisesRegex(ValueError,'preflight'):self.compact(expected=a['sha256'])
        self.target.joinpath('source.txt').write_text('x'*26000+'\n')
        subprocess.run(['git','-C',str(self.target),'commit','-qam','oversized evidence'],check=True,capture_output=True)
        a=self.assess();self.assertEqual(a['decisions']['status'],'blocked')
        with self.assertRaisesRegex(ValueError,'preflight'):self.compact(expected=a['sha256'])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))

    def test_negative_retained_finding_never_adopts_implementation(self):
        self.setup_plan()
        def negative(cfg,key,body):
            self.network.append(json.loads(body));return json.dumps(dict(model=cfg['model'],answers=dict(supported=dict(type='noul',noul=0)))).encode()
        self.transport=negative;result=self.compact();self.assertEqual(result['status'],'blocked')
        self.assertNotIn('implement',m.p.snapshot(self.project,'T-1')['completed']);self.assertEqual(self.ledger.read_bytes(),self.budget_before)

    def test_real_dispatcher_with_synthetic_tool_free_reviewer(self):
        self.setup_plan();binary=self.project.parent/'bin';binary.mkdir();calls=self.project.parent/'review-calls'
        route=self.assess()['evidence']['reviewer_route']
        stub=binary/'claude'
        stub.write_text("#!/usr/bin/env python3\nimport sys,json\n"+
          "if sys.argv[1:3]==['auth','status']:\n print(json.dumps(dict(loggedIn=True,authMethod='claude.ai',apiProvider='firstParty')));sys.exit(0)\n"+
          "assert '--safe-mode' in sys.argv and '--no-session-persistence' in sys.argv\nassert sys.argv[sys.argv.index('--tools')+1]==''\n"+
          "prompt=sys.argv[-1];data=json.JSONDecoder().raw_decode(prompt.split('Task input:\\n',1)[1])[0]\n".replace('\\n','\\n')+
          "assert len(prompt.encode())<24576\nassert 'corpus' not in data and 'evidence' not in data\n"+
          "r=dict(decision='yes',packet_sha256=data['packet_sha256'],reviewer_id=data['reviewer_id'],evidence=[e['id'] for e in data['packet']['evidence']])\n"+
          "report=dict(status='SUCCESS',reason='Synthetic focused review',attempts=1,artifacts=dict(branch='',diff='',**"+repr(route)+"),rules_fired=[],results=r)\n"+
          "with open("+repr(str(calls)) +",'a') as f:f.write(data['packet']['id']+'\\n')\n"+
          "print(json.dumps(dict(structured_output=report)))\n")
        stub.chmod(0o755)
        with patch.dict(os.environ,{'PATH':str(binary)+os.pathsep+os.environ['PATH']}):
            self.escalate=m.compact_review
            result=self.compact()
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertIn('scope_matches',calls.read_text());self.assertIn('oracle_valid',calls.read_text())
        self.assertEqual(len(self.network),4);self.assertEqual(self.ledger.read_bytes(),self.budget_before)

    def test_stale_plan_and_changed_model_reject_authorization(self):
        self.setup_plan();a=self.assess()
        with patch.dict(os.environ,{'NIGHTSHIFT_JEV_MODEL':'jev-different'}),self.assertRaisesRegex(ValueError,'inputs_changed'):
            self.compact(expected=a['sha256'])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))

    def test_restart_reuses_completed_decisions_with_same_deadline(self):
        self.setup_plan();a=self.assess();original=m.adopt
        def crash(state,session,stage,directory):
            if stage=='adoption':raise KeyboardInterrupt('before atomic transition')
            return original(state,session,stage,directory)
        with patch.object(m,'adopt',crash),self.assertRaises(KeyboardInterrupt):self.compact(expected=a['sha256'])
        allowance=m.p.snapshot(self.project,'T-1')['recovery_sessions'][a['sha256']]['allowance']
        result=self.compact('resume',a['sha256']);self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(len(self.network),4);self.assertEqual(result['allowance']['deadline_at'],allowance['deadline_at'])

# unittest inheritance would otherwise rerun legacy tests with new fixtures.
for name in dir(legacy.RecoveryTest):
    if name.startswith('test_') and name not in Decisions.__dict__:setattr(Decisions,name,None)
if __name__=='__main__':unittest.main()
