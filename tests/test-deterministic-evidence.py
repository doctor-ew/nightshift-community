#!/usr/bin/env python3
"""Version 2 plans: Nightshift-proven generated artifacts and case-to-assertion traceability. Synthetic only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
import unittest.mock
spec=importlib.util.spec_from_file_location('decisions_fixture',Path(__file__).with_name('test-recovery-decisions.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m


class DeterministicEvidence(f.Decisions):
    def setUp(self):
        super().setUp()
        gen=self.target/'gen';gen.mkdir()
        (gen/'src.txt').write_text('canonical text\n')
        (gen/'build.sh').write_text('#!/bin/sh\nset -eu\ncp gen/src.txt gen/out.txt\n')
        (gen/'out.txt').write_text('canonical text\n')
        (self.target/'evals/unit/test-source.sh').write_text('#!/bin/sh\nset -eu\n# CASE-one: the fixed source is observed\ntest "$(cat source.txt)" = fixed\necho PASS\n')
        self.commit('generated artifact and traced test')

    def commit(self,message):
        subprocess.run(['git','-C',str(self.target),'add','.'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(self.target),'commit','-qm',message],check=True,capture_output=True)

    def plan_v2(self,generated=True,assertion_end=5,cite_generated=False):
        self.env2=__import__('unittest.mock',fromlist=['patch']).patch.dict(os.environ,{'NIGHTSHIFT_JEV_MODEL':'jev-1.13.0','TYPESAFE_API_KEY':'synthetic-only'})
        self.env2.start();self.addCleanup(self.env2.stop)
        self.plan=dict(version=2,checks=[dict(id='test-source.sh',argv=['bash','evals/unit/test-source.sh'])],
                       limits=dict(wall_seconds=600,active_seconds=600,provider_calls=16),decisions=[])
        if generated:self.plan['generated']=[dict(path='gen/out.txt',argv=['bash','gen/build.sh'])]
        self.save_plan()
        value,_=m.evidence(self.project,'T-1')
        skip=set() if cite_generated or not generated else {'gen/out.txt'}
        refs=[]
        for name in value['source_files']:
            if name in skip:continue
            refs.append(dict(id='source-'+str(len(refs)),role='source',path=name,start_line=1,end_line=len((self.target/name).read_text().splitlines())))
        for name in ('docs/T-1/SPEC.md','docs/T-1/behavior-scenarios.json'):
            refs.append(dict(id='requirement-'+str(len(refs)),role='requirement',path=name,start_line=1,end_line=len((self.target/name).read_text().splitlines())))
        refs.append(dict(id='assertion',role='assertion',path='evals/unit/test-source.sh',start_line=1,end_line=assertion_end))
        refs.append(dict(id='observed',role='observation',path='test-source.sh',start_line=1,end_line=1))
        for kind in ('requirement_supported','finding_resolved','scope_matches','oracle_valid'):
            self.plan['decisions'].append(dict(id=kind,kind=kind,case_ids=['CASE-one'],ac_ids=['AC-1'],finding_ids=[x['id'] for x in value['findings']] if kind=='finding_resolved' else [],references=refs,high_risk=False))
        self.save_plan();self.network=[];self.review_calls=[]
        return m.evidence(self.project,'T-1')[0]

    def test_generated_artifact_is_proven_and_excluded_from_review(self):
        value=self.plan_v2()
        self.assertEqual(value['decision_readiness']['status'],'ready',value['decision_readiness'])
        report=m.verify_checks(value,timeout=60)
        self.assertEqual(report['status'],'pass',report)
        self.assertEqual([(g['path'],g['reproduced']) for g in report['generated']],[('gen/out.txt',True)])
        packets=[pk for gate in m.GATES for pk in m.load('recovery-decisions').packets(value,report,gate)]
        self.assertTrue(packets)
        self.assertFalse(any(r['path']=='gen/out.txt' for pk in packets for r in pk['evidence']))

    def test_citing_a_generated_artifact_is_rejected_before_any_call(self):
        value=self.plan_v2(cite_generated=True)
        self.assertEqual(value['decision_readiness']['status'],'blocked')
        self.assertEqual(value['decision_readiness']['reason'],'recovery_decision_generated_not_evidence')

    def test_without_declaration_the_generated_file_still_needs_review_coverage(self):
        value=self.plan_v2(generated=False)
        self.assertEqual(value['decision_readiness']['status'],'ready',value['decision_readiness'])
        self.assertEqual(m.verify_checks(value,timeout=60)['generated'],[])

    def test_stale_generated_artifact_fails_verification(self):
        (self.target/'gen/out.txt').write_text('stale text\n');self.commit('stale embed')
        value=self.plan_v2()
        report=m.verify_checks(value,timeout=60)
        self.assertEqual(report['status'],'fail');self.assertFalse(report['generated'][0]['reproduced']);self.assertEqual(report['checks'],[])

    def test_generator_that_does_not_write_the_file_fails(self):
        (self.target/'gen/build.sh').write_text('#!/bin/sh\nexit 0\n');self.commit('inert generator')
        report=m.verify_checks(self.plan_v2(),timeout=60)
        self.assertEqual(report['status'],'fail');self.assertFalse(report['generated'][0]['reproduced'])

    def test_generator_that_changes_another_tracked_file_fails(self):
        (self.target/'gen/build.sh').write_text('#!/bin/sh\nset -eu\ncp gen/src.txt gen/out.txt\necho changed >> source.txt\n');self.commit('collateral generator')
        report=m.verify_checks(self.plan_v2(),timeout=60)
        self.assertEqual(report['status'],'fail');self.assertFalse(report['generated'][0]['reproduced'])

    def test_case_must_be_named_by_a_cited_assertion(self):
        value=self.plan_v2(assertion_end=2)
        self.assertEqual(value['decision_readiness']['status'],'blocked')
        self.assertTrue(value['decision_readiness']['reason'].startswith('recovery_decision_case_untraced:'),value['decision_readiness'])

    def test_case_token_must_match_exactly(self):
        (self.target/'evals/unit/test-source.sh').write_text('#!/bin/sh\nset -eu\n# CASE-one-extra: a different case\ntest "$(cat source.txt)" = fixed\necho PASS\n');self.commit('lookalike tag')
        value=self.plan_v2()
        self.assertTrue(value['decision_readiness']['reason'].startswith('recovery_decision_case_untraced:'),value['decision_readiness'])

    def test_declaration_mismatch_and_unchanged_generated_paths_are_rejected(self):
        value=self.plan_v2()
        self.plan['generated']=[dict(path='gen/out.txt',argv=['bash','gen/other.sh'])]
        (self.target/'gen/other.sh').write_text('#!/bin/sh\ncp gen/src.txt gen/out.txt\n');self.save_plan()
        self.assertEqual(m.evidence(self.project,'T-1')[0]['decision_readiness']['status'],'ready')
        self.plan['generated']=[dict(path='source.txt',argv=['bash','gen/build.sh'])];self.save_plan()
        with self.assertRaises(ValueError):
            v=m.evidence(self.project,'T-1')[0]
            if v['decision_readiness']['status']!='ready':raise ValueError(v['decision_readiness']['reason'])
            m.verify_checks(v,timeout=60)

class JevClaims(DeterministicEvidence):
    """Version 2 plans reach Jev as narrow claims over shared evidence (synthetic transport)."""
    def setUp(self):
        super().setUp()
        doc=json.loads((self.docs/'behavior-scenarios.json').read_text())
        doc['cases'][0].update(then='The source file reads fixed.',forbidden='Report a pass when the source is broken.')
        (self.docs/'behavior-scenarios.json').write_text(json.dumps(doc));self.commit('case clauses')
        self.score=lambda key:.97

    def transport(self,cfg,key,body):
        request=json.loads(body);self.network.append(request)
        return json.dumps(dict(model=cfg['model'],answers={k:dict(type='noul',noul=self.score(k)) for k in request['questions']},usage=dict(input_tokens=1500,output_tokens=10))).encode()

    def test_v2_plan_runs_as_claims_through_the_controller(self):
        self.plan_v2();a=self.assess();self.assertEqual(a['decisions']['status'],'ready',a['decisions'])
        result=self.compact(expected=a['sha256'])
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(len(self.network),4)  # review reuses adoption's identical judgment
        self.assertEqual(self.review_calls,[])  # confident claims are not escalated
        for request in self.network:
            self.assertNotIn('supported',request['questions'])
            self.assertTrue(all(q['type']=='noul' for q in request['questions'].values()))
        texts=[q['instructions'] for r in self.network for q in r['questions'].values()]
        self.assertTrue(any('The source file reads fixed.' in t for t in texts))
        self.assertTrue(any('does not do the following: Report a pass when the source is broken.' in t for t in texts))

    def test_run_estimate_is_measured_and_proposes_limits(self):
        self.plan_v2()
        first=m.assessment(self.project,'T-1',True)['run_estimate']
        self.assertEqual((first['mode'],first['unique_questions'],first['gate_evaluations'],first['cache_reuses']),('jev',4,5,1))
        self.assertEqual(first['provider_calls']['maximum'],8)
        self.assertEqual(first['provider_calls']['expected'],4+sum(first['provider_calls']['planned_escalations'].values()))
        self.assertNotIn('exception',first['provider_calls']['planned_escalations'])  # v2 claims: confident answers are not re-asked
        self.assertGreater(first['estimated_input_tokens'],0)
        self.assertEqual(first['observed_call_seconds'],{});self.assertIsNone(first['proposed_limits']['wall_seconds'])
        self.assertEqual(self.compact(expected=self.assess()['sha256'])['status'],'pending_manual_acceptance')
        later=m.assessment(self.project,'T-1',True)['run_estimate']
        self.assertEqual(later['observed_call_seconds']['jev']['samples'],4)
        self.assertIsInstance(later['proposed_limits']['wall_seconds'],int)

    def test_interrupted_escalation_resumes_in_jev_mode(self):
        self.score=lambda key:.5 if key=='claim_2' else .97
        self.plan_v2();binding=self.assess()['sha256']
        original=self.escalate;state={'crashed':False}
        def crash(*args,**kwargs):
            if not state['crashed']:state['crashed']=True;raise KeyboardInterrupt('controller process died')
            return original(*args,**kwargs)
        self.escalate=crash
        with self.assertRaises(KeyboardInterrupt):self.compact(expected=binding)
        session=next(iter(m.p.snapshot(self.project,'T-1')['recovery_sessions'].values()))
        self.assertEqual(session['status'],'running')
        done=self.compact(operation='resume',expected=binding)
        self.assertEqual(done['status'],'pending_manual_acceptance',done)
        session=next(iter(m.p.snapshot(self.project,'T-1')['recovery_sessions'].values()))
        kinds={v['kind']+':'+v['status'] for k,v in session['decision_calls'].items() if ':interrupted-' in k}
        self.assertIn('jev:complete',kinds);self.assertIn('exception:interrupted',kinds)

    def test_adopted_evidence_validates_without_the_route_environment(self):
        self.plan_v2();binding=self.assess()['sha256']
        self.assertEqual(self.compact(expected=binding)['status'],'pending_manual_acceptance')
        state=m.p.snapshot(self.project,'T-1');row=next(r for r in state['completed'].values() if r.get('recovery_binding'))
        m.validate_adopted(self.project,'T-1',state,row)
        with unittest.mock.patch.dict(os.environ,{'NIGHTSHIFT_JEV_MODEL':'jev-latest'}):
            m.validate_adopted(self.project,'T-1',state,row)  # route absent/different: recorded route governs
        (self.target/'source.txt').write_text('changed\n');self.commit('real change')
        with unittest.mock.patch.dict(os.environ,{'NIGHTSHIFT_JEV_MODEL':'jev-latest'}),self.assertRaisesRegex(ValueError,'inputs_changed'):
            m.validate_adopted(self.project,'T-1',state,row)

    def test_jev_answers_are_reused_by_a_later_session(self):
        # Two questions complete confidently; the third escalates and the controller dies.
        self.score=lambda key:.5 if key=='claim_2' and len(self.network)>=3 else .97
        self.plan_v2();first=self.assess()['sha256']
        original=self.escalate;state={'crash':True}
        def crash(*args,**kwargs):
            if state['crash']:raise KeyboardInterrupt('controller process died')
            return original(*args,**kwargs)
        self.escalate=crash
        with self.assertRaises(KeyboardInterrupt):self.compact(expected=first)
        asked=len(self.network);self.assertGreater(asked,0)
        state['crash']=False
        self.plan['limits']=dict(self.plan['limits'],provider_calls=self.plan['limits']['provider_calls']+1);self.save_plan()
        second=self.assess()['sha256'];self.assertNotEqual(first,second)
        estimate=m.assessment(self.project,'T-1',True)['run_estimate']
        self.assertEqual(estimate['provider_calls']['reusable_answers'],2)
        self.assertEqual(estimate['provider_calls']['maximum'],2*(estimate['unique_questions']-2))
        done=self.compact(expected=second)
        self.assertEqual(done['status'],'pending_manual_acceptance',done)
        decisions=m.p.root(self.project,'T-1')/('recovery-'+second)/'decisions'
        reused=[r for f in decisions.glob('*.json') if f.name.count('.')==1 for r in [__import__('json').loads(f.read_text())] if r.get('reason')=='decision_reused']
        self.assertTrue(reused);self.assertTrue(all(r['calls']==[] for r in reused))
        # Completed answers were not asked again: only the interrupted packet and later ones were.
        self.assertLess(len(self.network)-asked,4)
        sessions=m.p.snapshot(self.project,'T-1')['recovery_sessions'];self.assertEqual(sessions[first]['status'],'interrupted')
        state_now=m.p.snapshot(self.project,'T-1');row=next(r for r in state_now['completed'].values() if r.get('recovery_binding')==second)
        m.validate_adopted(self.project,'T-1',state_now,row)

    def test_uncertain_claim_escalates_only_that_packet(self):
        self.score=lambda key:.5 if key=='claim_2' else .97
        self.plan_v2();a=self.assess()
        result=self.compact(expected=a['sha256'])
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertTrue(self.review_calls)
        self.assertLess(len(self.review_calls),len(self.network)+1)


# Reuse the fixture, not its tests: those already run in test-recovery-decisions.py.
for _cls in (DeterministicEvidence,JevClaims):
    for _name in [n for n in dir(_cls) if n.startswith('test_') and n not in _cls.__dict__]:
        setattr(_cls,_name,None)

if __name__=='__main__':unittest.main()
