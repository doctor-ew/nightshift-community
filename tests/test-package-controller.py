#!/usr/bin/env python3
"""Composed operations in disposable repositories using synthetic workers."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
f=load('package_fixture','tests/test-work-packages.py')
m=load('package_controller','scripts/nightshift-package-controller.py')


def fixture(root):
    graph=f.fixture(root)
    graph['aggregate']=dict(calls=32,seconds=300,wall_seconds=300)
    (root/'graph.json').write_text(json.dumps(graph))
    (root/'scenarios.json').write_text(json.dumps(dict(version=1,cases=[dict(id='R1',requirement='Combine functions',manual=False)])))
    plan=json.loads((root/'docs/demo/operations.json').read_text())
    plan['inputs'].update(request='parent.md',spec='graph.json')
    (root/'docs/demo/operations.json').write_text(json.dumps(plan))
    return graph


class Controller(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='nightshift-package-controller-');self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.graph=fixture(self.root);self.worker=f.f.Worker()
        self.c=m.Packages(self.root,'demo',self.worker)
    def prepare(self):
        prep=self.c.preparation;a=prep.assess('groom-spec')
        prep.authorize(m.ops.RECIPES['groom'],a['binding'],'synthetic','prepare')
        result=self.c.prepare('prepare');self.assertEqual(result['status'],'ready',result)
        return self.c.authorize(result['binding'],'synthetic','compose')
    def test_composed_factory_reuses_current_children_on_restart(self):
        self.prepare();result=self.c.run('compose')
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(result['usage']['calls'],14)
        calls=list(self.worker.calls)
        restarted=m.Packages(self.root,'demo',self.worker)
        again=restarted.run('compose')
        self.assertEqual(again['status'],'pending_manual_acceptance',again)
        self.assertEqual(self.worker.calls,calls)
        self.assertEqual(again['usage'],result['usage'])
    def test_external_child_adoption_invalidates_descendant_only(self):
        self.prepare();self.assertEqual(self.c.run('compose')['status'],'pending_manual_acceptance')
        right=self.c.child('right');retained=(right.directory/'state.json').read_bytes()
        left=self.c.child('left');(left.project/'left.py').write_text('def value(): return 1 # external revision\n')
        a=left.assess('adopt')
        g=left.authorize(['adopt'],a['binding'],'synthetic','external',dict(binding=a['binding'],identity='external-author',provider='human'))
        self.assertEqual(left.execute(g['id'],'adopt','external-adoption')['status'],'passed')
        prior=len(self.worker.calls)
        result=self.c.run('compose');self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual((right.directory/'state.json').read_bytes(),retained)
        self.assertEqual(sum(op=='implement' for op,_ in self.worker.calls[prior:]),1)
        left=self.c.child('left')
        self.assertEqual(sum(a['operation']=='implement' for a in left.state['attempts']),1)
        self.assertTrue(left.state['results']['implement']['external'])
        integration=self.c.child('integration')
        self.assertIn('external revision',(integration.project/'left.py').read_text())
        self.assertEqual(len(self.worker.calls)-prior,5)
        calls=list(self.worker.calls);self.assertEqual(self.c.run('compose')['status'],'pending_manual_acceptance')
        self.assertEqual(self.worker.calls,calls)

    def test_semantic_challenge_can_reject_id_complete_graph(self):
        original=self.worker
        def worker(operation,*args):
            original.fail=operation=='groom-adversarial'
            return original(operation,*args)
        self.c.preparation.worker=worker
        prep=self.c.preparation;a=prep.assess('groom-spec')
        prep.authorize(m.ops.RECIPES['groom'],a['binding'],'synthetic','prepare')
        result=self.c.prepare('prepare')
        self.assertEqual(result['status'],'blocked',result)
        packet=original.packets[-1]
        self.assertIn('docs/left/operations.json',packet['artifacts'])
        self.assertIn('left_test.py',packet['artifacts'])
        self.assertFalse(self.c.state['authorizations'])
        self.assertFalse(self.c.state['children'])

    def test_invalid_graph_does_not_dispatch(self):
        self.graph['children'][0]['depends_on']=['integration']
        (self.root/'graph.json').write_text(json.dumps(self.graph))
        with self.assertRaises(ValueError):self.c.assess()
        self.assertEqual(self.worker.calls,[])
    def test_parent_integration_failure_cannot_pass(self):
        (self.root/'integration.py').write_text('import left, right\ndef value(): return left.value() + right.value()\n')
        (self.root/'integration_test.py').write_text('import unittest\nfrom integration import value\nclass T(unittest.TestCase):\n def test_parent_total(self): self.assertEqual(value(), 3)\nunittest.main()\n')
        self.prepare();result=self.c.run('compose')
        self.assertEqual(result['status'],'blocked',result)
        self.assertEqual(result['reason'],'package_failed:integration')
        self.assertEqual(result['grant']['allocations']['left']['status'],'complete')
        self.assertEqual(result['grant']['allocations']['right']['status'],'complete')
        calls=list(self.worker.calls)
        self.assertEqual(self.c.run('compose')['status'],'blocked')
        self.assertEqual(self.worker.calls,calls)

if __name__=='__main__':unittest.main()
