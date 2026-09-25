#!/usr/bin/env python3
"""Synthetic compact semantic obligations and raw-cache validation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixture',ROOT/'tests/test-operations.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m
bridge=m.load('operation-decisions')


class Decisions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.plan=f.fixture(self.root);self.w=f.Worker();self.c=m.Operations(self.root,'demo',self.w)
        a=self.c.assess('groom-spec');self.c.authorize(m.RECIPES['factory'][:-1],a['binding'],'synthetic','base');self.c.chain('base')
        observations=self.c.state['results']['verify']['observations'];refs=[]
        for role,name in [('requirement','spec.md'),('requirement','scenarios.json'),('source','app.py'),('assertion','test_app.py'),('observation','unit')]:
            text=observations[0]['output'] if role=='observation' else (self.root/name).read_text()
            refs.append(dict(id=role+str(len(refs)),role=role,path=name,start_line=1,end_line=len(text.splitlines())))
        obligations=[]
        for kind in ('requirement_supported','scope_matches','oracle_valid'):
            obligations.append(dict(id=kind,kind=kind,question='Does the exact mapped evidence support this obligation?',requirements=[dict(id='two',evidence=[r['id'] for r in refs])],findings=[],references=refs,high_risk=kind!='requirement_supported'))
        (self.root/'docs/demo/semantic.json').write_text(json.dumps(dict(version=1,obligations=obligations)))
        self.plan['reviewer_policy']['semantic_plan']='docs/demo/semantic.json';self.plan['limits']['review']['calls']=12;self.plan['limits']['review']['seconds']=120
        (self.root/'docs/demo/operations.json').write_text(json.dumps(self.plan))
        self.c.semantic_settings=dict(enabled=True,endpoint='https://synthetic.invalid/evaluate',model='synthetic-pinned-1',timeout_seconds=2,max_bytes=24576,allow_loopback=False,key_env='SYNTHETIC_SECRET')
        self.calls=[]
        def transport(cfg,key,body):
            self.calls.append(len(body));return json.dumps(dict(model=cfg['model'],answers={'supported':dict(type='noul',noul=.99)})).encode()
        self.c.semantic_transport=transport
    def tearDown(self):self.tmp.cleanup()
    def test_compact_decisions_cache_and_raw_tamper(self):
        a=self.c.assess('review');self.assertEqual(a['status'],'ready',a)
        g=self.c.authorize(['review'],a['binding'],'synthetic','semantic')
        r=self.c.execute(g['id'],'review','review-compact');self.assertEqual(r['status'],'passed',r)
        self.assertEqual(len(self.calls),3);self.assertLess(max(self.calls),24576)
        record=self.c.state['results']['review']['semantic'];self.assertGreaterEqual(sum(len(r['calls']) for r in record['receipts']),5)
        with self.c.lease():
            cached=bridge.run(self.c,self.plan,g['id'],'review',self.c.state['results']['verify']['observations'],self.c.route('review',self.plan))
        self.assertTrue(all(r['cache_hit'] for r in cached['receipts']));self.assertEqual(len(self.calls),3)
        first=next((self.c.directory/'decisions').glob('*.jev.json'));first.write_text('{}')
        self.assertNotEqual(self.c.assess('review')['status'],'current')
        Path('/private/tmp/nightshift-operation-semantic-metrics.json').write_text(json.dumps(dict(synthetic=True,request_bytes=self.calls,jev_calls=len(self.calls),independent_escalations=sum(len(r['calls'])-1 for r in record['receipts']),cache_hits=len(cached['receipts']),usage=self.c.usage(g['id']),live_certification=False),indent=2)+'\n')
    def test_incomplete_mapping_no_grant_or_dispatch(self):
        path=self.root/'docs/demo/semantic.json';data=json.loads(path.read_text());data['obligations'][0]['references'][0]['end_line']=999;path.write_text(json.dumps(data))
        count=len(self.w.calls);a=self.c.assess('review');self.assertEqual(a['status'],'blocked');self.assertEqual(len(self.w.calls),count);self.assertFalse(self.calls)
    def test_contradiction_blocks(self):
        original=self.c.worker
        def worker(op,packet,route,output,seconds):
            result=original(op,packet,route,output,seconds)
            if 'semantic-obligation' in packet.get('artifacts',{}):result['results'].update(decision='repair',findings=['oracle contradicts evidence'])
            return result
        self.c.worker=worker;a=self.c.assess('review');self.c.authorize(['review'],a['binding'],'synthetic','contradiction')
        r=self.c.execute('contradiction','review','contradiction');self.assertEqual(r['status'],'failed');self.assertIn('contradiction',r['reason'])


if __name__=='__main__':unittest.main()
