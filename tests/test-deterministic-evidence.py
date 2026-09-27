#!/usr/bin/env python3
"""Version 2 plans: Nightshift-proven generated artifacts and case-to-assertion traceability. Synthetic only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
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

# Reuse the fixture, not its tests: those already run in test-recovery-decisions.py.
for _name in [n for n in dir(f.Decisions) if n.startswith('test_') and n not in DeterministicEvidence.__dict__]:
    setattr(DeterministicEvidence,_name,None)

if __name__=='__main__':unittest.main()
