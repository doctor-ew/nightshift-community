#!/usr/bin/env python3
"""Independent preparation-contract regressions retained from public PR convergence."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('convergence_fixtures', Path(__file__).with_name('test-package-controller-review.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m


class PreparationContracts(unittest.TestCase):
    setUp = f.PackageControllerReview.setUp

    def validate(self):
        return m.contracts.validate(self.root, self.graph, 'graph.json', preparation_task='demo')

    def change_preparation(self, change):
        path = self.root/'docs/demo/operations.json'
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def own(self, name):
        child = self.graph['children'][0]
        child['writes'] = [name]
        child['interfaces'][0]['path'] = name
        path = self.root/child['plan']
        plan = json.loads(path.read_text())
        plan['scope'] = [name]
        path.write_text(json.dumps(plan))
        self.graph['children'][2]['reads'].remove('left.py')
        (self.root/'graph.json').write_text(json.dumps(self.graph))

    def test_preparation_plan_is_protected(self):
        self.validate()
        self.own('docs/demo/operations.json')
        with self.assertRaises(ValueError):
            self.validate()
        self.assertEqual(self.worker.calls, [])

    def test_preparation_only_input_is_protected(self):
        self.validate()
        self.own('parent-cases.json')
        with self.assertRaises(ValueError):
            self.validate()
        self.assertEqual(self.worker.calls, [])

    def test_preparation_and_child_identity_must_differ(self):
        self.validate()
        child = self.graph['children'][0]
        plan = json.loads((self.root/'docs/demo/operations.json').read_text())
        child.update(id='demo', plan='docs/demo/operations.json', ref='spec:graph.json',
            reads=list(plan['inputs'].values()) + ['test_app.py'], writes=plan['scope'],
            allowance=plan['aggregate'])
        child['interfaces'][0]['path'] = 'app.py'
        self.graph['children'][2]['depends_on'][0] = 'demo'
        self.graph['children'][2]['reads'].remove('left.py')
        self.graph['aggregate'] = dict(calls=100, seconds=1000, wall_seconds=1000)
        (self.root/'graph.json').write_text(json.dumps(self.graph))
        with self.assertRaises(ValueError):
            self.validate()
        self.assertEqual(self.worker.calls, [])

    def test_preparation_publication_requires_separate_authority(self):
        self.validate()
        self.change_preparation(lambda p: p.update(publication=dict(remote='synthetic', branch='synthetic-publication')))
        with self.assertRaises(ValueError):
            self.validate()
        self.assertEqual(self.worker.calls, [])

    def test_preparation_plan_and_input_changes_invalidate_binding(self):
        initial = self.validate()['binding']
        self.change_preparation(lambda p: p['aggregate'].update(calls=19))
        changed = self.validate()['binding']
        self.assertNotEqual(changed, initial)
        path = self.root/'parent-cases.json'
        path.write_bytes(path.read_bytes() + b'\n')
        self.assertNotEqual(self.validate()['binding'], changed)
        self.assertEqual(self.worker.calls, [])

    def test_preparation_manifest_must_match_validated_graph(self):
        self.validate()
        supplied = json.loads(json.dumps(self.graph))
        supplied['aggregate']['calls'] += 1
        self.graph = supplied
        with self.assertRaises(ValueError):
            self.validate()
        self.assertEqual(self.worker.calls, [])

    def test_missing_preparation_plan_is_rejected(self):
        self.validate()
        path = self.root/'docs/demo/operations.json'
        path.rename(path.with_suffix('.retained'))
        with self.assertRaises((ValueError, OSError)):
            self.validate()
        self.assertEqual(self.worker.calls, [])


if __name__ == '__main__':
    unittest.main()
