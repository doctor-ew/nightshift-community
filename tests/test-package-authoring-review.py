#!/usr/bin/env python3
"""Independent synthetic authority and evidence checks for inline package authoring."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('bundle_review_fixtures', Path(__file__).with_name('test-package-authoring.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m


class BundleReview(unittest.TestCase):
    setUp = f.Authoring.setUp

    def validate(self, graph=None):
        graph = self.graph if graph is None else graph
        (self.root/'graph.json').write_text(json.dumps(graph))
        return m.contracts.validate(self.root, graph, 'graph.json', 'demo')

    def test_control_artifacts_never_gain_bundle_write_authority(self):
        self.validate()
        for name in ('parent.md', 'graph.json', 'docs/demo/operations.json', 'rules.md',
                     'routing.json', '.nightshift.toml', '.git/config', '.agents/instructions.md',
                     'nested/.git/config', '.env.production', 'nested/.env.local'):
            with self.subTest(name=name):
                graph = copy.deepcopy(self.graph)
                graph['children'][0]['reads'].append(name)
                graph['artifacts'][name] = 'synthetic attempted authority override'
                with self.assertRaises(ValueError):
                    self.validate(graph)
        self.assertEqual(self.worker.calls, [])

    def test_alias_and_symlink_artifacts_are_rejected(self):
        self.validate()
        (self.root/'synthetic-target.txt').write_text('retained')
        (self.root/'synthetic-link.txt').symlink_to(self.root/'synthetic-target.txt')
        for name in ('./new.txt', 'docs//new.txt', '../outside.txt', 'synthetic-link.txt'):
            with self.subTest(name=name):
                graph = copy.deepcopy(self.graph)
                graph['children'][0]['reads'].append(name)
                graph['artifacts'][name] = 'synthetic input'
                with self.assertRaises(ValueError):
                    self.validate(graph)
        self.assertEqual((self.root/'synthetic-target.txt').read_text(), 'retained')
        self.assertEqual(self.worker.calls, [])

    def test_oversized_bundle_fails_without_truncation_or_dispatch(self):
        graph = copy.deepcopy(self.graph)
        name = next(iter(graph['artifacts']))
        graph['artifacts'][name] = 'x' * m.ops.MAX_REQUEST
        with self.assertRaisesRegex(ValueError, 'package_bundle_too_large'):
            self.validate(graph)
        self.assertEqual(self.worker.calls, [])
        self.assertFalse(self.c.state['children'])

    def test_external_projection_enforces_file_and_total_byte_bounds(self):
        for size, count in ((m.ops.MAX_REQUEST + 1, 1), (m.ops.MAX_REQUEST // 2, 2)):
            with self.subTest(size=size, count=count):
                graph = copy.deepcopy(self.graph)
                for index in range(count):
                    name = 'synthetic-large-' + str(index) + '.txt'
                    (self.root/name).write_text('x' * size)
                    graph['children'][0]['reads'].append(name)
                with self.assertRaisesRegex(ValueError, 'package_projection_too_large'):
                    self.validate(graph)
        self.assertEqual(self.worker.calls, [])

    def test_bundle_does_not_overwrite_existing_operator_input(self):
        name = 'left_test.py'
        self.assertIn(name, self.graph['artifacts'])
        (self.root/name).write_text('retained operator test')
        with self.assertRaisesRegex(ValueError, 'bundle_overwrites_existing_input'):
            self.validate()
        self.assertEqual((self.root/name).read_text(), 'retained operator test')
        self.assertEqual(self.worker.calls, [])

    def test_external_and_inline_inputs_change_binding(self):
        initial = self.validate()['binding']
        self.assertEqual(self.validate()['binding'], initial)
        path = self.root/'rules.md'
        path.write_bytes(path.read_bytes() + b'\n')
        external = self.validate()['binding']
        self.assertNotEqual(external, initial)
        self.graph['artifacts']['left_test.py'] += '\n'
        self.assertNotEqual(self.validate()['binding'], external)
        self.assertEqual(self.worker.calls, [])

    def test_projection_does_not_copy_undeclared_caller_files(self):
        self.validate()
        (self.root/'synthetic-unrelated.txt').write_text('synthetic retained data')
        bundle = m.ops.load('package-bundle')
        with bundle.projection(self.root, self.graph, 'graph.json', 'demo') as (view, normalized):
            self.assertFalse((view/'synthetic-unrelated.txt').exists())
            self.assertFalse((view/'.git').exists())
            self.assertEqual(normalized['version'], 2)
        self.assertEqual((self.root/'synthetic-unrelated.txt').read_text(), 'synthetic retained data')

    def test_independent_challenge_can_reject_authored_bundle_before_children(self):
        author = self.c.preparation.worker
        def reject(operation, *args):
            self.worker.fail = operation == 'groom-adversarial'
            return author(operation, *args)
        self.c.preparation.worker = reject
        prep = self.c.preparation
        assessed = prep.assess('groom-spec')
        grant = prep.authorize(m.ops.RECIPES['groom'], assessed['binding'], 'synthetic', 'reject-bundle')
        result = self.c.prepare(grant['id'])
        self.assertEqual(result['status'], 'blocked', result)
        self.assertEqual([operation for operation, _ in self.worker.calls], ['groom-spec', 'groom-adversarial'])
        packet = self.worker.packets[-1]
        self.assertIn('left_test.py', json.loads(packet['artifacts']['graph.json'])['artifacts'])
        self.assertIn('rules.md', packet['artifacts'])
        self.assertFalse(self.c.state['children'])
        self.assertFalse(self.c.state['authorizations'])
        self.assertFalse((self.root/'docs/left').exists())


if __name__ == '__main__':
    unittest.main()
