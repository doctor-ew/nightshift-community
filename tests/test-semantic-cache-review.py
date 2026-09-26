#!/usr/bin/env python3
"""Independent evaluator-identity cache checks; copied public assets, stub calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
ASSETS=('nightshift-operation-decisions.py','nightshift-decision-engine.py','nightshift-recovery-decisions.py','nightshift-efficiency.py')

class SemanticCacheReview(unittest.TestCase):
    def setUp(self):
        self.home=tempfile.TemporaryDirectory(prefix='nightshift-semantic-cache-review-')
        self.addCleanup(self.home.cleanup)
        directory=Path(self.home.name).resolve()
        env={'HOME':str(directory),'NIGHTSHIFT_HOME':str(directory/'.nightshift'),'XDG_CONFIG_HOME':str(directory/'config'),
             'TMPDIR':str(directory),'PATH':os.environ['PATH'],'GIT_CONFIG_NOSYSTEM':'1',
             'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null','PYTHONDONTWRITEBYTECODE':'1'}
        guard=patch.dict(os.environ,env,clear=True);guard.start();self.addCleanup(guard.stop)
        spec=importlib.util.spec_from_file_location('cache_handoff_fixture',ROOT/'tests/test-semantic-handoffs.py')
        f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
        self.f=f;self.case=f.Handoffs();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.b=f.b;self.c=self.case.c;self.plan=self.case.plan
        self.plan['limits']['groom-adversarial'].update(calls=64,seconds=600)
        self.plan['aggregate'].update(calls=64,seconds=1000)
        (self.case.root/'docs/demo/operations.json').write_text(json.dumps(self.plan))
        self.grant,result=self.case.run_handoff();self.assertEqual(result['status'],'passed',result)
        self.record=self.c.state['results']['groom-adversarial']['semantic']
        self.assets=directory/'assets';self.assets.mkdir()
        for name in ASSETS:(self.assets/name).write_bytes((ROOT/'scripts'/name).read_bytes())
        # Production hashing reads actual copied bytes. Existing helpers remain
        # imported from the public candidate; no alternate runtime is installed.
        modules={name:self.b.load(name) for name in ('operations','recovery-decisions','efficiency')}
        loader=patch.object(self.b,'load',side_effect=lambda name:modules[name]);loader.start();self.addCleanup(loader.stop)
        here=patch.object(self.b,'HERE',self.assets);here.start();self.addCleanup(here.stop)
    def evaluate(self):
        with self.c.lease():
            return self.b.run(self.c,self.plan,self.grant['id'],'groom-adversarial',[],self.c.route('groom-adversarial',self.plan))
    def validate(self,record):return self.b.validate(self.c,self.plan,record,[],'groom-adversarial')
    def test_unchanged_assets_reuse_three_receipts_without_calls(self):
        before=self.c.usage(self.grant['id']);count=len(self.case.calls)
        replay=self.evaluate();self.assertEqual(sum(r['cache_hit'] for r in replay['receipts']),3)
        self.assertEqual(replay['authority'],self.record['authority']);self.assertEqual(self.c.usage(self.grant['id']),before)
        self.assertEqual(len(self.case.calls),count);self.validate(replay)
    def test_every_changed_asset_invalidates_and_reserves_fresh_calls(self):
        for name in ASSETS:
            with self.subTest(asset=name):
                path=self.assets/name;original=path.read_bytes();path.write_bytes(original+b'\n# Synthetic evaluator revision identity.\n')
                try:
                    with self.assertRaisesRegex(ValueError,'semantic_evaluator_assets_changed'):self.validate(self.record)
                    before=self.c.usage(self.grant['id']);count=len(self.case.calls)
                    revised=self.evaluate()
                    self.assertNotEqual(revised['authority'],self.record['authority'])
                    self.assertTrue(all(not r['cache_hit'] for r in revised['receipts']))
                    self.assertEqual(len(self.case.calls)-count,3)
                    self.assertEqual(self.c.usage(self.grant['id'])['calls']-before['calls'],6)
                    self.assertEqual(self.c.usage(self.grant['id'])['unknown'],0)
                    self.validate(revised)
                finally:path.write_bytes(original)
    def test_legacy_record_without_asset_identity_fails_closed(self):
        legacy=copy.deepcopy(self.record);legacy.pop('evaluator_assets')
        before=self.c.usage(self.grant['id'])
        with self.assertRaisesRegex(ValueError,'semantic_evaluator_assets_changed'):self.validate(legacy)
        self.assertEqual(self.c.usage(self.grant['id']),before)
    def test_relabelled_asset_metadata_cannot_validate_old_authority(self):
        path=self.assets/ASSETS[0];path.write_bytes(path.read_bytes()+b'\n# Synthetic identity update.\n')
        relabelled=copy.deepcopy(self.record);relabelled['evaluator_assets']=self.b.evaluator_assets()
        before=self.c.usage(self.grant['id'])
        with self.assertRaisesRegex(ValueError,'authority'):self.validate(relabelled)
        self.assertEqual(self.c.usage(self.grant['id']),before)
    def test_missing_asset_fails_before_any_reservation(self):
        path=self.assets/ASSETS[0];retained=self.assets/'retained-original';path.rename(retained)
        before=self.c.usage(self.grant['id'])
        try:
            with self.assertRaises(OSError):self.validate(self.record)
            with self.assertRaises(OSError):self.evaluate()
            self.assertEqual(self.c.usage(self.grant['id']),before)
        finally:retained.rename(path)
    def test_changed_assets_do_not_bypass_original_call_ceiling(self):
        path=self.assets/ASSETS[0];path.write_bytes(path.read_bytes()+b'\n# Synthetic changed version.\n')
        with self.c.lease():
            self.c.state['authorizations'][self.grant['id']]['aggregate']['calls']=self.c.usage(self.grant['id'])['calls'];self.c.save()
        before=self.c.usage(self.grant['id']);count=len(self.case.calls)
        with self.assertRaisesRegex(ValueError,'provider_call_limit_exhausted'):self.evaluate()
        self.assertEqual(self.c.usage(self.grant['id']),before);self.assertEqual(len(self.case.calls),count)

if __name__=='__main__':unittest.main()
