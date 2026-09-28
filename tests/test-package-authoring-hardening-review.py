#!/usr/bin/env python3
"""Independent checks where inline authoring meets Git and mode hardening."""
import importlib.util
from pathlib import Path
import stat
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('authoring_hardening_fixtures', Path(__file__).with_name('test-package-authoring-review.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m


class AuthoringHardeningReview(unittest.TestCase):
    setUp = f.BundleReview.setUp
    validate = f.BundleReview.validate

    def test_bundle_validation_does_not_construct_ledger_controller(self):
        with patch.object(m.contracts.ops, 'Operations', side_effect=AssertionError('Read-only projection must not construct a Git-backed ledger')):
            result = self.validate()
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(len(result['children']), 3)
        self.assertFalse((self.root/'docs/left').exists())
        self.assertEqual(self.worker.calls, [])

    def test_existing_identical_inline_file_keeps_mode_in_binding(self):
        name = 'left_test.py'
        path = self.root/name
        path.write_text(self.graph['artifacts'][name])
        path.chmod(0o755)
        first = self.validate()
        child = first['children'][0]
        self.assertEqual(child['input_modes'][name], 0o755)
        self.assertEqual(child['input_modes']['left.py'], 0o644)
        self.assertEqual(child['input_modes'][child['plan']], 0o644)
        path.chmod(0o644)
        second = self.validate()
        self.assertNotEqual(second['binding'], first['binding'])
        self.assertEqual(second['children'][0]['input_modes'][name], 0o644)
        self.assertEqual(path.read_text(), self.graph['artifacts'][name])
        self.assertEqual(self.worker.calls, [])

    def test_materialization_preserves_external_and_new_inline_modes(self):
        name = 'left_test.py'
        path = self.root/name
        path.write_text(self.graph['artifacts'][name])
        path.chmod(0o755)
        prep = self.c.preparation
        assessed = prep.assess('groom-spec')
        grant = prep.authorize(m.ops.RECIPES['groom'], assessed['binding'], 'synthetic', 'author-modes')
        ready = self.c.prepare(grant['id'])
        self.assertEqual(ready['status'], 'ready', ready)
        parent = self.c.authorize(ready['binding'], 'synthetic', 'compose-modes')
        definition = parent['graph']['children'][0]
        with self.c.lease():
            child = self.c.materialize(definition, parent['id'])
        for relative, expected in ((name, 0o755), ('left.py', 0o644), (definition['plan'], 0o644)):
            self.assertEqual(stat.S_IMODE((child.project/relative).stat().st_mode), expected)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)
        self.assertFalse((self.root/'docs/left').exists())
        self.assertEqual(len(self.worker.calls), 2)


if __name__ == '__main__':
    unittest.main()
