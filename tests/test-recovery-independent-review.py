#!/usr/bin/env python3
"""Explicit independent recovery over existing authority; synthetic reviews only."""
import importlib.util
import json
import hashlib
import tempfile
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('compact_fixtures',Path(__file__).with_name('test-recovery-decisions.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m


class IndependentRecovery(f.Decisions):
    def setup_independent(self):
        self.setup_plan()
        self.plan['semantic_mode']='independent'
        self.save_plan()
        self.env_independent=patch.dict(os.environ,{'TYPESAFE_API_KEY':'','NIGHTSHIFT_JEV_ENABLED':'false','NIGHTSHIFT_JEV_MODEL':'jev-latest'})
        self.env_independent.start();self.addCleanup(self.env_independent.stop)
        self.envelopes=[]

    def independent_review(self,value,packet,mode,output,timeout,reviewer_id=None,missing_roles=None):
        self.assertEqual(mode,'independent')
        self.review_calls.append(packet['id'])
        self.envelopes.append(m.load('decision-engine').independent_envelope(packet,reviewer_id,missing_roles))
        return dict(decision='yes',packet_sha256=m.load('decision-engine').digest(packet),reviewer_id=reviewer_id,evidence=[r['id'] for r in packet['evidence']])

    def recover(self,operation='authorize',expected=None,review=None):
        original=m.compact_verdict
        def forbidden_jev(*args,**kwargs):raise AssertionError('independent mode attempted Jev')
        def invoke(*args,**kwargs):return original(*args,**kwargs,transport=forbidden_jev,escalator=review or self.independent_review)
        with patch.object(m,'compact_verdict',invoke):
            return m.operate(self.project,'T-1',operation,expected or self.assess()['sha256'],'synthetic-independent-operator')

    def test_independent_without_jev_key_preserves_evidence_and_exact_accounting(self):
        self.setup_independent();a=self.assess()
        self.assertEqual(a['decisions']['status'],'ready',a['decisions'])
        self.assertEqual(a['decisions']['semantic_mode'],'independent')
        before={str(path):path.read_bytes() for path in self.docs.rglob('*') if path.is_file()}
        result=self.recover(expected=a['sha256'])
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(result['allowance']['calls_used'],4)
        self.assertEqual(len(self.review_calls),4)
        calls=list(result['decision_calls'].values())
        sizes=[len(m.load('decision-engine').encoded(envelope)) for envelope in self.envelopes]
        self.assertEqual([c['request_bytes'] for c in calls],sizes)
        self.assertTrue(all(c['kind']=='independent' for c in calls))
        self.assertEqual(before,{str(path):path.read_bytes() for path in self.docs.rglob('*') if path.is_file()})
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)
        self.assertEqual(m.p.snapshot(self.project,'T-1')['attempts'],self.state['attempts'])
        session=m.p.snapshot(self.project,'T-1')['recovery_sessions'][a['sha256']]
        self.assertEqual(session['semantic_mode'],'independent')
        self.assertEqual(session['decision_mode'],'compact')
        duplicate=self.recover(expected=a['sha256'])
        self.assertEqual(duplicate['allowance'],result['allowance'])
        self.assertEqual(len(self.review_calls),4)

    def add_manual_case(self, shared=False):
        if not shared:self.document['ac_ids'].append('AC-manual')
        self.document['cases'].append(dict(id='CASE-manual',ac_ids=['AC-1' if shared else 'AC-manual'],applicability=dict(kind='manual')))
        self.docs.joinpath('behavior-scenarios.json').write_text(json.dumps(self.document))
        subprocess.run(['git','-C',str(self.target),'commit','-qam','synthetic manual requirement'],check=True,capture_output=True)

    def test_distinct_manual_ac_stays_pending_without_automatic_obligation(self):
        self.add_manual_case();self.setup_independent()
        a=self.assess();self.assertEqual(a['decisions']['status'],'ready',a['decisions'])
        self.assertEqual(a['evidence']['ac_ids'],['AC-1','AC-manual'])
        result=self.recover(expected=a['sha256'])
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(len(self.review_calls),4)
        self.assertTrue(all([r['id'] for r in e['packet']['requirements'] if r['id'].startswith('ac:')]==['ac:AC-1'] for e in self.envelopes))

    def test_shared_manual_ac_remains_pending(self):
        self.add_manual_case(shared=True);self.setup_independent()
        self.assertEqual(self.recover()['status'],'pending_manual_acceptance')

    def test_manual_only_ac_cannot_be_claimed_by_automatic_decision(self):
        self.add_manual_case();self.setup_independent()
        self.plan['decisions'][0]['ac_ids'].append('AC-manual');self.save_plan()
        a=self.assess();self.assertEqual(a['decisions']['status'],'blocked')
        self.assertIn('obligation_invalid',a['decisions']['reason'])
        self.assertEqual(self.review_calls,[])

    def test_unclassified_or_unknown_scenario_ac_blocks(self):
        self.setup_independent()
        value=self.assess()['evidence']
        for invalid,reason in ((dict(value,ac_ids=['AC-1','AC-orphan']),'ac_unclassified'),
                               (dict(value,ac_ids=['AC-other']),'case_ac_invalid')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):
                m.load('recovery-decisions').plan(invalid)

    def test_manual_report_cannot_omit_or_claim_pass(self):
        self.add_manual_case();self.setup_independent()
        original=m.validate_compact
        def validate(report,value,stage,checks):
            self.assertEqual(report['manual_cases'],['CASE-manual'])
            for forged in ([],[dict(id='CASE-manual',status='verified')]):
                with self.subTest(forged=forged),self.assertRaisesRegex(ValueError,'manual_case_cannot_pass'):
                    original(dict(report,manual_cases=forged),value,stage,checks)
            return original(report,value,stage,checks)
        with patch.object(m,'validate_compact',validate):
            self.assertEqual(self.recover()['status'],'pending_manual_acceptance')

    def test_assess_verify_independent_does_not_require_jev_settings(self):
        self.setup_independent()
        result=m.assessment(self.project,'T-1',True)
        self.assertEqual(result['verification']['status'],'pass')
        self.assertEqual(self.review_calls,[])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))

    def test_failed_assessment_check_preserves_output_without_semantic_calls(self):
        self.setup_independent()
        script=self.target/'evals/unit/test-source.sh'
        script.write_text('#!/bin/sh\nset -eu\necho synthetic-assertion-failed\nexit 1\n')
        subprocess.run(['git','-C',str(self.target),'commit','-qam','synthetic failing verification'],check=True,capture_output=True)
        result=m.assessment(self.project,'T-1',True)
        self.assertEqual(result['verification']['status'],'fail')
        self.assertEqual(result['verification']['checks'][0]['exit_code'],1)
        self.assertIn('synthetic-assertion-failed',result['verification']['checks'][0]['output'])
        self.assertEqual(self.review_calls,[])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))

    def test_default_mode_still_requires_jev_and_never_falls_back(self):
        self.setup_independent();del self.plan['semantic_mode'];self.save_plan()
        a=self.assess();self.assertEqual(a['decisions']['status'],'blocked')
        self.assertIn('enabled_pinned_model',a['decisions']['reason'])
        with self.assertRaisesRegex(ValueError,'preflight'):self.recover(expected=a['sha256'])
        self.assertEqual(self.review_calls,[])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))

    def test_assisted_failure_never_dispatches_independent_fallback(self):
        self.setup_independent();self.plan['semantic_mode']='jev';self.save_plan()
        original=m.compact_verdict
        def fail_jev(*args):raise ValueError('synthetic_jev_transport_failed')
        def forbidden_review(*args,**kwargs):raise AssertionError('fallback must not run')
        def invoke(*args,**kwargs):return original(*args,**kwargs,transport=fail_jev,escalator=forbidden_review)
        with patch.dict(os.environ,{'NIGHTSHIFT_JEV_ENABLED':'true','NIGHTSHIFT_JEV_MODEL':'jev-1.13.0','TYPESAFE_API_KEY':'synthetic-only'}),patch.object(m,'compact_verdict',invoke):
            result=m.operate(self.project,'T-1','authorize',self.assess()['sha256'],'synthetic-operator')
        self.assertEqual(result['status'],'blocked')
        self.assertIn('synthetic_jev_transport_failed',result['reason'])
        self.assertEqual(result['allowance']['calls_used'],1)
        self.assertEqual(self.review_calls,[])

    def test_wall_exhaustion_blocks_after_charged_review(self):
        self.setup_independent();assessment=self.assess();clock=m.time.time;advanced=[None]
        def slow_review(*args,**kwargs):
            result=self.independent_review(*args,**kwargs);advanced[0]=clock()+601;return result
        with patch.object(m.time,'time',side_effect=lambda:advanced[0] if advanced[0] is not None else clock()):
            result=self.recover(expected=assessment['sha256'],review=slow_review)
        self.assertEqual(result['status'],'blocked')
        self.assertIn('allowance_exhausted',result['reason'])
        self.assertEqual(result['allowance']['calls_used'],1)
        self.assertEqual(len(self.review_calls),1)

    def test_invalid_mode_blocks_before_authority(self):
        self.setup_independent();self.plan['semantic_mode']='auto';self.save_plan()
        a=self.assess();self.assertEqual(a['decisions']['reason'],'recovery_semantic_mode_invalid')
        with self.assertRaisesRegex(ValueError,'preflight'):self.recover(expected=a['sha256'])

    def test_resume_needs_explicit_authorization(self):
        self.setup_independent()
        with self.assertRaisesRegex(ValueError,'authorization_missing'):self.recover('resume')
        self.assertEqual(self.review_calls,[])

    def test_changed_mode_invalidates_assessment(self):
        self.setup_independent();a=self.assess();self.plan['semantic_mode']='jev';self.save_plan()
        with self.assertRaisesRegex(ValueError,'inputs_changed'):self.recover(expected=a['sha256'])
        self.assertEqual(self.review_calls,[])

    def test_negative_and_abstaining_reviews_do_not_adopt(self):
        self.setup_independent()
        def negative(*args,**kwargs):
            result=self.independent_review(*args,**kwargs);result['decision']='no';return result
        result=self.recover(review=negative)
        self.assertEqual(result['status'],'blocked')
        self.assertNotIn('implement',m.p.snapshot(self.project,'T-1')['completed'])
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)
        again=self.recover();self.assertEqual(again['allowance'],result['allowance'])
        self.assertEqual(len(self.review_calls),1)

    def test_missing_role_coverage_blocks(self):
        self.setup_independent()
        def missing(*args,**kwargs):
            result=self.independent_review(*args,**kwargs);result['evidence']=['observed'];return result
        result=self.recover(review=missing)
        self.assertEqual(result['status'],'blocked')
        self.assertIn('evidence_incomplete',result['reason'])
        self.assertNotIn('implement',m.p.snapshot(self.project,'T-1')['completed'])

    def test_response_reviewer_id_cannot_be_swapped(self):
        self.setup_independent()
        def stale(*args,**kwargs):
            result=self.independent_review(*args,**kwargs);result['reviewer_id']='another-reviewer';return result
        result=self.recover(review=stale)
        self.assertEqual(result['status'],'blocked')
        self.assertIn('result_invalid',result['reason'])

    def test_exhaustion_does_not_repeat_implementation_or_mint_budget(self):
        self.setup_independent();self.plan['limits']['provider_calls']=1;self.save_plan()
        result=self.recover();self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['allowance']['calls_used'],1)
        self.assertIn('allowance_exhausted',result['reason'])
        self.assertNotIn('implement',m.p.snapshot(self.project,'T-1')['completed'])
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)

    def test_unknown_interrupted_review_never_relaunches(self):
        self.setup_independent();a=self.assess()
        def crash(*args,**kwargs):
            self.review_calls.append('unknown');raise KeyboardInterrupt('synthetic provider interruption')
        with self.assertRaises(KeyboardInterrupt):self.recover(expected=a['sha256'],review=crash)
        resumed=self.recover('resume',a['sha256'])
        self.assertEqual(resumed['status'],'blocked')
        self.assertIn('unfinished_step',resumed['reason'])
        self.assertEqual(self.review_calls,['unknown'])
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)

    def test_restart_reuses_completed_independent_decisions(self):
        self.setup_independent();a=self.assess();original=m.adopt
        def crash(state,session,stage,directory):
            if stage=='adoption':raise KeyboardInterrupt('before adoption transition')
            return original(state,session,stage,directory)
        with patch.object(m,'adopt',crash),self.assertRaises(KeyboardInterrupt):self.recover(expected=a['sha256'])
        deadline=m.p.snapshot(self.project,'T-1')['recovery_sessions'][a['sha256']]['allowance']['deadline_at']
        result=self.recover('resume',a['sha256'])
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(len(self.review_calls),4)
        self.assertEqual(result['allowance']['deadline_at'],deadline)

    def test_oversized_plan_blocks_before_authority(self):
        self.setup_independent();self.target.joinpath('source.txt').write_text('x'*26000+'\n')
        subprocess.run(['git','-C',str(self.target),'commit','-qam','oversized source'],check=True,capture_output=True)
        a=self.assess();self.assertEqual(a['decisions']['status'],'blocked')
        with self.assertRaisesRegex(ValueError,'preflight'):self.recover(expected=a['sha256'])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))

    def test_real_dispatcher_with_synthetic_subscription_reviewer(self):
        self.setup_independent();binary=self.project.parent/'bin';binary.mkdir();calls=self.project.parent/'review-calls';route=self.assess()['evidence']['reviewer_route']
        stub=binary/'claude'
        stub.write_text('#!/usr/bin/env python3\nimport sys,json\n'+
            'if sys.argv[1:3]==["auth","status"]:\n print(json.dumps(dict(loggedIn=True,authMethod="claude.ai",apiProvider="firstParty")));sys.exit(0)\n'+
            'assert "--safe-mode" in sys.argv and "--no-session-persistence" in sys.argv\nassert sys.argv[sys.argv.index("--tools")+1]==""\n'+
            'data=json.JSONDecoder().raw_decode(sys.argv[-1].split("Task input:\\n",1)[1])[0]\nassert data["mode"]=="independent"\n'+
            'g={}\nfor r in data["packet"]["evidence"]:g.setdefault(r["role"],[]).append(r["id"])\n'+
            'result=dict(decision="yes",packet_sha256=data["packet_sha256"],reviewer_id=data["reviewer_id"],grounding=g)\n'+
            'with open('+repr(str(calls))+',"a") as stream:stream.write(data["packet"]["id"]+"\\n")\n'+
            'print(json.dumps(dict(structured_output=dict(status="SUCCESS",reason="Synthetic independent review",attempts=1,artifacts=dict(branch="",diff="",**'+repr(route)+'),rules_fired=[],results=result))))\n')
        stub.chmod(0o755)
        with patch.dict(os.environ,{'PATH':str(binary)+os.pathsep+os.environ['PATH']}):
            result=m.operate(self.project,'T-1','authorize',self.assess()['sha256'],'synthetic-operator')
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(len(calls.read_text().splitlines()),4)
        session_directory=self.directory/('recovery-'+result['sha256'])
        actual_inputs={json.loads(path.read_text())['reviewer_id']:path.read_bytes() for path in session_directory.glob('*.input.json')}
        self.assertEqual(len(actual_inputs),4)
        engine=m.load('decision-engine')
        for key,call in result['decision_calls'].items():
            retained=json.loads((session_directory/'decisions'/(key+'.json')).read_text())
            data=actual_inputs[retained['reviewer_id']]
            self.assertEqual(len(data),call['request_bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(),retained['artifacts']['request'])
            self.assertEqual(data,(session_directory/'decisions'/(key+'.request.json')).read_bytes())
        self.assertEqual(result['allowance']['calls_used'],4)
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)

class IndependentCache(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name)
        spec=importlib.util.spec_from_file_location('engine_fixture',Path(__file__).with_name('test-decision-engine.py'))
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
        self.engine_module=fixture.e;self.packet=fixture.packet()
        self.settings=dict(semantic_mode='independent',provider='claude',model='configured-fixture',timeout_seconds=120,max_bytes=24576)
        self.calls=[];self.reviews=[]

    def reserve(self,kind,request_id,size):
        self.calls.append((kind,request_id,size));return request_id

    def review(self,packet,reviewer_id):
        self.reviews.append(reviewer_id)
        return dict(decision='yes',packet_sha256=self.engine_module.digest(packet),reviewer_id=reviewer_id,evidence=[ref['id'] for ref in packet['evidence']])

    def engine(self,review=None,settings=None):
        return self.engine_module.IndependentEngine(self.directory,'explicit-authority',settings or self.settings,self.reserve,lambda token,outcome:None,review or self.review)

    def test_review_and_request_artifact_tamper_rejected(self):
        for suffix in ('review','request'):
            with self.subTest(suffix=suffix):
                packet=dict(self.packet,id=suffix)
                result=self.engine().decide(packet)
                path=self.directory/(result['key']+'.'+suffix+'.json')
                path.write_text('{}')
                with self.assertRaisesRegex(ValueError,'artifact_changed'):self.engine().decide(packet)
        self.assertEqual(len(self.reviews),2)

    def test_changed_reviewer_route_uses_distinct_cache(self):
        original=self.engine().decide(self.packet)
        changed=self.engine(settings=dict(self.settings,model='different-fixture')).decide(self.packet)
        self.assertNotEqual(original['key'],changed['key'])
        self.assertEqual(len(self.reviews),2)

    def test_pending_cache_never_relaunches(self):
        def interrupted(*args):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.engine(review=interrupted).decide(self.packet)
        result=self.engine().decide(self.packet)
        self.assertEqual(result['reason'],'decision_unfinished_reservation')
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.reviews,[])

    def test_abstain_and_stale_packet_response_block_and_cache(self):
        for kind in ('abstain','stale'):
            packet=dict(self.packet,id=kind)
            def invalid(p,reviewer_id):
                result=self.review(p,reviewer_id)
                if kind=='abstain':result['decision']='abstain'
                else:result['packet_sha256']='0'*64
                return result
            result=self.engine(review=invalid).decide(packet)
            self.assertEqual((result['status'],result['decision']),('blocked','abstain'))
            self.assertTrue(self.engine().decide(packet)['cache_hit'])
        self.assertEqual(len(self.reviews),2)

    def test_wrong_mode_cannot_reuse_independent_engine(self):
        with self.assertRaisesRegex(ValueError,'settings_invalid'):self.engine(settings=dict(self.settings,semantic_mode='jev'))
        self.assertEqual(self.calls,[])


# Avoid inheriting unrelated fixture test methods.
for name in dir(f.Decisions):
    if name.startswith('test_') and name not in IndependentRecovery.__dict__:setattr(IndependentRecovery,name,None)
if __name__=='__main__':unittest.main()
