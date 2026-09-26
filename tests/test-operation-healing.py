#!/usr/bin/env python3
"""Bounded shared-operation repair; synthetic workers only."""
import difflib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('fixtures',Path(__file__).with_name('test-operations.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class Healing(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nightshift-healing-')
        self.root=Path(self.tmp.name);f.fixture(self.root)
        self.worker=f.Worker();self.count=0;self.fail_review=False;self.noop=False
        self.c=m.Operations(self.root,'demo',self.work)
    def tearDown(self):self.tmp.cleanup()
    def work(self,operation,packet,route,output,seconds):
        self.worker.patch='';self.worker.fail=False
        if operation=='implement':
            self.count+=1
            if self.count>1 and not self.noop:
                before=(self.root/'app.py').read_text();after='def answer():\n    return 2 # repaired '+str(self.count)+'\n'
                self.worker.patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/app.py',tofile='b/app.py'))
        if operation=='review' and self.fail_review:self.worker.fail=True
        return self.worker(operation,packet,route,output,seconds)
    def grant(self):
        return self.c.authorize(m.RECIPES['factory'],self.c.assess('groom-spec')['binding'],'synthetic','factory')['id']
    def test_failed_verify_repairs_and_replays_without_dispatch(self):
        (self.root/'app.py').write_text('def answer():\n    return 1\n')
        g=self.grant();deadline=self.c.state['authorizations'][g]['deadline']
        result=self.c.chain(g)
        self.assertEqual(result['view']['status'],'pending_manual_acceptance',result)
        self.assertEqual(self.count,2)
        self.assertEqual(len(self.worker.calls),5)
        failures=[a for a in self.c.state['attempts'] if a['status']=='failed']
        self.assertEqual(len(failures),1);self.assertTrue(failures[0]['evidence'])
        packets=[p for p in self.worker.packets if p['operation']=='implement']
        self.assertTrue(any('AssertionError' in finding for finding in packets[-1]['findings']))
        self.c=m.Operations(self.root,'demo',self.work)
        again=self.c.chain(g)
        self.assertEqual(len(self.worker.calls),5)
        self.assertTrue(all(r['status']=='passed' for r in again['results']))
        self.assertEqual(self.c.state['authorizations'][g]['deadline'],deadline)
    def test_exhaustion_survives_restart_then_external_adoption(self):
        self.fail_review=True;g=self.grant();result=self.c.chain(g)
        self.assertEqual(result['view']['status'],'incomplete');self.assertEqual(self.count,3)
        calls=len(self.worker.calls);self.c=m.Operations(self.root,'demo',self.work)
        self.c.chain(g);self.assertEqual(len(self.worker.calls),calls)
        self.fail_review=False
        (self.root/'app.py').write_text('def answer(): return 2 # external\n')
        assessed=self.c.assess('adopt')
        grant=self.c.authorize(m.RECIPES['external'],assessed['binding'],'synthetic','external',dict(binding=assessed['binding'],identity='external-human',provider='human'))
        result=self.c.chain(grant['id'])
        self.assertEqual(self.count,3)
        self.assertEqual(result['view']['status'],'pending_manual_acceptance',result)
        self.assertEqual(len([a for a in self.c.state['attempts'] if a['operation']=='review' and a['status']=='failed']),3)
    def test_noop_repair_does_not_repeat_failed_review(self):
        self.fail_review=True;self.noop=True
        result=self.c.chain(self.grant())
        self.assertEqual(sum(op=='review' for op,_ in self.worker.calls),1)
        self.assertEqual(self.count,2)
        self.assertEqual(result['view']['status'],'incomplete')
    def test_transport_failure_does_not_schedule_author_repair(self):
        def broken(*args):raise ValueError('provider_exit:1')
        self.c.worker=broken
        result=self.c.chain(self.grant())
        self.assertEqual(len(self.c.state['calls']),1)
        self.assertFalse(self.c.state['authorizations']['factory']['workflow']['repairs'])
        self.assertEqual(result['view']['status'],'incomplete')

if __name__=='__main__':unittest.main()
