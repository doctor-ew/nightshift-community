#!/usr/bin/env python3
"""Synthetic labeled semantic handoffs; no real evaluator or billing claims."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('handoff_fixture',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m;b=m.load('operation-decisions')

class Handoffs(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nightshift-handoff-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.plan=f.fixture(self.root);self.worker=f.Worker();self.c=m.Operations(self.root,'demo',self.worker)
        self.path=self.root/'docs/demo/semantic.json'
        self.path.write_text(json.dumps(b.generate(self.c,self.plan,'groom-adversarial')))
        self.plan['reviewer_policy']['semantic_plan']='docs/demo/semantic.json'
        self.plan['limits']['groom-adversarial'].update(calls=12,seconds=120)
        self.plan['aggregate'].update(calls=30,seconds=300)
        (self.root/'docs/demo/operations.json').write_text(json.dumps(self.plan))
        self.c.semantic_settings=dict(enabled=True,endpoint='https://synthetic.invalid/evaluate',model='synthetic-pinned-1',timeout_seconds=2,max_bytes=24576,allow_loopback=False,key_env='SYNTHETIC_SECRET')
        self.calls=[];self.score=.99
        def transport(cfg,key,body):
            self.calls.append(len(body));return json.dumps(dict(model=cfg['model'],answers={'supported':dict(type='noul',noul=self.score)})).encode()
        self.c.semantic_transport=transport
    def prepare(self):
        a=self.c.assess('groom-spec');g=self.c.authorize(m.RECIPES['groom'],a['binding'],'synthetic','prep')
        for op in ('groom-spec','groom-rules'):
            self.assertEqual(self.c.execute(g['id'],op,op)['status'],'passed')
        return g
    def run_handoff(self):
        g=self.prepare();return g,self.c.execute(g['id'],'groom-adversarial','challenge')
    def test_positive_preparation_mappings_reviewed_and_cache_reused(self):
        packets=[];base=self.c.worker
        def worker(op,packet,*args):
            packets.append(packet);return base(op,packet,*args)
        self.c.worker=worker;g,result=self.run_handoff();self.assertEqual(result['status'],'passed',result)
        self.assertEqual(len(self.calls),3)
        independent=next(p for p in packets if p['operation']=='groom-adversarial')
        self.assertEqual(len(independent['semantic_obligations']),3)
        self.assertTrue(all(p['version']==2 and p['stage']=='groom-adversarial' and not p['checks'] for p in independent['semantic_obligations']))
        count=len(self.worker.calls);again=self.c.execute(g['id'],'groom-adversarial','challenge')
        self.assertEqual(again['status'],'passed');self.assertEqual(len(self.worker.calls),count)
        with self.c.lease():cached=b.run(self.c,self.plan,g['id'],'groom-adversarial',[],self.c.route('groom-adversarial',self.plan))
        self.assertEqual(sum(r['cache_hit'] for r in cached['receipts']),3);self.assertEqual(len(self.calls),3)
        record=self.c.state['results']['groom-adversarial']['semantic']
        with self.assertRaisesRegex(ValueError,'handoff_changed'):b.validate(self.c,self.plan,record,[],'review')
        if os.environ.get('NIGHTSHIFT_HANDOFF_METRICS'):
            Path(os.environ['NIGHTSHIFT_HANDOFF_METRICS']).write_text(json.dumps(dict(synthetic=True,stage='groom-adversarial',evaluator_request_bytes=self.calls,worker_requests=[dict(operation=op,request_bytes=size) for op,size in self.worker.calls],evaluator_calls=len(self.calls),independent_escalations=sum(len(r['calls'])-1 for r in record['receipts']),cache_hits=sum(r['cache_hit'] for r in cached['receipts']),replay_calls=0,usage=self.c.usage(g['id']),provider_tokens=None,provider_cache_usage=None,billed_cost=None,live_certification=False),indent=2)+'\n')
    def test_negative_id_complete_mapping_cannot_pass(self):
        self.score=.01;_,result=self.run_handoff()
        self.assertEqual(result['status'],'failed');self.assertIn('semantic_decision_blocked',result['reason'])
        self.assertNotIn('groom-adversarial',self.c.state['results'])
    def test_abstain_requires_budgeted_independent_escalation(self):
        self.score=.5;_,result=self.run_handoff();self.assertEqual(result['status'],'passed',result)
        record=self.c.state['results']['groom-adversarial']['semantic']
        self.assertEqual(sum(len(r['calls'])-1 for r in record['receipts']),3)
    def test_unavailable_evaluator_has_no_fallback(self):
        def unavailable(*args):raise OSError('synthetic unavailable')
        self.c.semantic_transport=unavailable;_,result=self.run_handoff()
        self.assertEqual(result['status'],'failed');self.assertIn('unavailable',result['reason'])
        self.assertEqual(len(self.worker.calls),2)
    def test_missing_evidence_refuses_before_evaluator(self):
        self.prepare();data=json.loads(self.path.read_text());data['obligations'][0]['references'][0]['end_line']=999;self.path.write_text(json.dumps(data))
        assessed=self.c.assess('groom-adversarial');self.assertEqual(assessed['status'],'blocked');self.assertFalse(self.calls)
    def test_observation_fabrication_in_preparation_rejected(self):
        self.prepare();data=json.loads(self.path.read_text());data['obligations'][0]['references'][0].update(role='observation',path='unit');self.path.write_text(json.dumps(data))
        assessed=self.c.assess('groom-adversarial');self.assertEqual(assessed['status'],'blocked');self.assertFalse(self.calls)
    def test_source_policy_and_evaluator_invalidate_current_handoff(self):
        _,result=self.run_handoff();self.assertEqual(result['status'],'passed',result)
        p,ctx=self.c.context();self.assertTrue(self.c.valid('groom-adversarial',p,ctx))
        self.c.semantic_settings['model']='synthetic-pinned-2';self.assertFalse(self.c.valid('groom-adversarial',p,ctx))
        self.c.semantic_settings['model']='synthetic-pinned-1'
        source=self.root/self.plan['inputs']['request'];source.write_text(source.read_text()+'\nChanged requirement\n')
        p,ctx=self.c.context();self.assertFalse(self.c.valid('groom-adversarial',p,ctx))
    def test_disabled_policy_has_no_evaluator_dependency(self):
        self.plan['reviewer_policy']['semantic_plan']=None;(self.root/'docs/demo/operations.json').write_text(json.dumps(self.plan))
        _,result=self.run_handoff();self.assertEqual(result['status'],'passed',result)
        self.assertFalse(self.calls);self.assertEqual(len(self.worker.calls),2)
    def test_generated_mapping_read_only_api_matches_cli_contract(self):
        before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.git' not in p.parts}
        generated=m.api(self.root,dict(task='demo',action='semantic-map',operation='groom-adversarial'))
        self.assertEqual(generated,json.loads(self.path.read_text()))
        after={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.git' not in p.parts}
        self.assertEqual(before,after);self.assertFalse(self.calls)

class ReviewHandoffs(unittest.TestCase):
    def test_generated_review_and_finding_text_are_exact(self):
        spec=importlib.util.spec_from_file_location('legacy_decisions_fixture',ROOT/'tests/test-operation-decisions.py')
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
        case=fixture.Decisions('test_compact_decisions_cache_and_raw_tamper');case.setUp();self.addCleanup(case.tearDown)
        controller=case.c;bridge=b
        value=bridge.generate(controller,case.plan,'review')
        case.root.joinpath('docs/demo/semantic.json').write_text(json.dumps(value))
        assessed=controller.assess('review');self.assertEqual(assessed['status'],'ready',assessed)
        grant=controller.authorize(['review'],assessed['binding'],'synthetic','v2-review')
        result=controller.execute(grant['id'],'review','v2-review');self.assertEqual(result['status'],'passed',result)
        self.assertEqual(len(case.calls),4)
        packets=bridge.packets(controller,case.plan,controller.state['results']['verify']['observations'],'review')
        self.assertIn('integration_supported',{p['kind'] for p in packets})
        controller.state['attempts'].append(dict(status='failed',findings=['Exact negative case was previously absent']))
        value=bridge.generate(controller,case.plan,'review')
        case.root.joinpath('docs/demo/semantic.json').write_text(json.dumps(value))
        packets=bridge.packets(controller,case.plan,controller.state['results']['verify']['observations'],'review')
        finding=next(p for p in packets if p['kind']=='finding_resolved')
        self.assertEqual(finding['findings'][0]['text'],'Exact negative case was previously absent')
        finding['findings'][0]['text']='Invented resolution'
        with self.assertRaisesRegex(ValueError,'finding_hash'):bridge.engine.validate(finding)

if __name__=='__main__':unittest.main()
