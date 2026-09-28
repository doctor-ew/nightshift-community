#!/usr/bin/env python3
"""Synthetic reviewer environment isolation; no provider or private config reads."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
m=load(ROOT/'scripts/nightshift-controller-recovery.py','recovery')
f=load(ROOT/'tests/test-decision-engine.py','fixtures')

class ReviewerEnvironment(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name).resolve();self.home=self.base/'home';self.home.mkdir()
        self.runtime=self.base/'public';(self.runtime/'scripts').mkdir(parents=True)
        (self.runtime/'scripts/nightshift-decision-engine.py').write_bytes((ROOT/'scripts/nightshift-decision-engine.py').read_bytes())
        (self.home/'.nightshift').mkdir()
        (self.home/'.nightshift/nightshift.toml').write_text('[providers]\npolicy="poisoned-default"\n')
        route=self.base/'routing.json';route.write_text(json.dumps(dict(roles={})))
        self.value=dict(plan=dict(policy='standard',routing_path=str(route)),reviewer_route=dict(provider='claude',model='synthetic'))
        self.output=self.base/'result.json';self.seen=[]
        env=patch.dict(os.environ,dict(HOME=str(self.home),NIGHTSHIFT_HOME=str(self.home/'.nightshift'),NIGHTSHIFT_PROVIDER_POLICY='standard',NIGHTSHIFT_ROLE_CHILD='0',ANTHROPIC_API_KEY='synthetic-secret'))
        env.start();self.addCleanup(env.stop)
        runtime=patch.object(m,'HERE',self.runtime/'scripts');runtime.start();self.addCleanup(runtime.stop)
    def dispatch(self,argv,cwd,env,timeout,log):
        self.seen.append(env)
        self.assertEqual(env['HOME'],str(self.home))
        self.assertEqual(env['NIGHTSHIFT_HOME'],str(self.runtime))
        self.assertNotIn('ANTHROPIC_API_KEY',env)
        policy=subprocess.run(['python3',str(ROOT/'scripts/nightshift-provider-policy.py'),'mode'],cwd=cwd,env=env,capture_output=True,text=True,check=True).stdout.strip()
        self.assertEqual(policy,env['NIGHTSHIFT_PROVIDER_POLICY'])
        data=json.loads(self.output.with_suffix('.input.json').read_text())
        self.output.write_text(json.dumps(dict(status='SUCCESS',artifacts=self.value['reviewer_route'],results=dict(reviewer_id=data['reviewer_id']))))
        return 0
    def run_review(self):
        with patch.object(m,'bounded',self.dispatch):m.compact_review(self.value,f.packet(),'independent',self.output,2)
    def test_poisoned_default_is_ignored_and_auth_home_preserved(self):
        self.run_review();self.assertEqual(self.seen[0]['NIGHTSHIFT_PROVIDER_POLICY'],'standard')
    def test_stricter_bound_and_inherited_policies_compose(self):
        for bound,inherited in [('claude-only','standard'),('standard','claude-only'),('claude-only','claude-only')]:
            with self.subTest(bound=bound,inherited=inherited),patch.dict(os.environ,NIGHTSHIFT_PROVIDER_POLICY=inherited):
                self.value['plan']['policy']=bound;self.run_review()
                self.assertEqual(self.seen[-1]['NIGHTSHIFT_PROVIDER_POLICY'],'claude-only')
    def test_invalid_policy_blocks_before_dispatch(self):
        for bound,inherited in [('bad','standard'),('standard','bad')]:
            with self.subTest(bound=bound,inherited=inherited),patch.dict(os.environ,NIGHTSHIFT_PROVIDER_POLICY=inherited):
                self.value['plan']['policy']=bound
                with self.assertRaisesRegex(ValueError,'policy_invalid'):self.run_review()
        self.assertEqual(self.seen,[]);self.assertFalse(self.output.with_suffix('.input.json').exists())
    def test_nested_role_guard_is_preserved_and_agent_refuses(self):
        def refuse(argv,cwd,env,timeout,log):
            self.assertEqual(env['NIGHTSHIFT_ROLE_CHILD'],'1')
            result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-agent.sh')],cwd=cwd,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,64);self.assertIn('nested role dispatch',result.stderr)
            return result.returncode
        with patch.dict(os.environ,NIGHTSHIFT_ROLE_CHILD='1'),patch.object(m,'bounded',refuse):
            with self.assertRaisesRegex(ValueError,'exit_64'):m.compact_review(self.value,f.packet(),'independent',self.output,2)
if __name__=='__main__':unittest.main()
