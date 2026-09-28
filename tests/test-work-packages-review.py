#!/usr/bin/env python3
"""Independent synthetic checks for package bindings and ownership boundaries."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_review_fixtures', ROOT/'tests/test-work-packages.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m


class PackageReview(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-package-review-')
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.graph = f.fixture(self.project)

    def change_scope(self, child, path):
        child['writes'] = [path]
        child['interfaces'][0]['path'] = path
        plan_path = self.project/child['plan']
        plan = json.loads(plan_path.read_text())
        plan['scope'] = [path]
        plan_path.write_text(json.dumps(plan))

    def test_resolved_binding_changes_for_referenced_content(self):
        baseline = m.validate(self.project, self.graph)['binding']
        for name in ('parent.md', 'rules.md', 'left.py', 'left_test.py', 'docs/left/operations.json'):
            with self.subTest(path=name):
                path = self.project/name
                retained = path.read_bytes()
                path.write_bytes(retained + b'\n')
                self.assertNotEqual(m.validate(self.project, self.graph)['binding'], baseline,
                    'Referenced content changes must invalidate graph authorization')
                path.write_bytes(retained)
                self.assertEqual(m.validate(self.project, self.graph)['binding'], baseline)

    def test_alias_write_cannot_evade_conflict_detection(self):
        self.change_scope(self.graph['children'][1], './left.py')
        with self.assertRaises(ValueError):
            m.validate(self.project, self.graph)

    def test_sibling_plan_cannot_be_owned_source(self):
        self.change_scope(self.graph['children'][0], 'docs/right/operations.json')
        with self.assertRaisesRegex(ValueError, 'package_write_overlaps_contract'):
            m.validate(self.project, self.graph)

    def test_dependency_output_must_have_exported_interface(self):
        left = self.graph['children'][0]
        left['writes'].append('hidden.py')
        (self.project/'hidden.py').write_text('hidden = 1\n')
        plan_path = self.project/left['plan']
        plan = json.loads(plan_path.read_text())
        plan['scope'] = left['writes']
        plan_path.write_text(json.dumps(plan))
        self.graph['children'][2]['reads'].append('hidden.py')
        with self.assertRaisesRegex(ValueError, 'undeclared_package_interface'):
            m.validate(self.project, self.graph)

    def test_parent_reference_alias_cannot_evade_control_protection(self):
        self.graph['parent'] = 'spec:./parent.md'
        self.change_scope(self.graph['children'][0], 'parent.md')
        self.graph['children'][2]['reads'].remove('left.py')
        with self.assertRaises(ValueError):
            m.validate(self.project, self.graph)


if __name__ == '__main__':
    unittest.main()
