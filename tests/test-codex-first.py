import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('policy',ROOT/'scripts/nightshift-provider-policy.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
class Routing(unittest.TestCase):
 def test_primary_delegate_and_independent_review(self):
  routes=json.loads((ROOT/'routing.json').read_text())
  self.assertEqual(routes['defaults']['provider'],'codex')
  for role in routes['roles']:
   for gear in (1,2,3):self.assertEqual(policy.select_route(routes,role,gear,'standard')['provider'],'codex')
   self.assertEqual(policy.select_route(routes,role,4,'standard')['provider'],'claude')
   self.assertEqual(policy.select_route(routes,role,1,'standard',author='codex',adversarial=True)['provider'],'claude')
   self.assertEqual(policy.select_route(routes,role,1,'standard',author='claude',adversarial=True)['provider'],'codex')
   self.assertEqual(policy.select_route(routes,role,1,'claude-only')['provider'],'claude')
if __name__=='__main__':unittest.main()
