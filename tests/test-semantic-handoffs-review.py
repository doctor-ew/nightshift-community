#!/usr/bin/env python3
"""Independent bounded semantic handoff and inline-evidence regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

f = load('semantic_review_fixtures', 'test-semantic-handoffs.py')
m = f.m
b = f.b


class HandoffReview(unittest.TestCase):
    setUp = f.Handoffs.setUp
    prepare = f.Handoffs.prepare
    run_handoff = f.Handoffs.run_handoff

    def test_malformed_obligation_selection_has_explicit_bounded_error(self):
        for obligations in (None, {}, [1], [None]):
            with self.subTest(obligations=obligations):
                self.path.write_text(json.dumps(dict(version=2, obligations=obligations)))
                with self.assertRaises(ValueError):
                    b.selected(self.c, self.plan, 'groom-adversarial')
        self.assertFalse(self.calls)
        self.assertFalse(self.worker.calls)

    def test_stage_transplant_and_wrong_kind_cannot_validate(self):
        packets = b.packets(self.c, self.plan, [], 'groom-adversarial')
        transplanted = copy.deepcopy(packets[0])
        transplanted['stage'] = 'review'
        with self.assertRaisesRegex(ValueError, 'handoff_kind'):
            b.engine.validate(transplanted)
        data = json.loads(self.path.read_text())
        data['obligations'][0]['kind'] = 'integration_supported'
        self.path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'handoff_kind'):
            b.packets(self.c, self.plan, [], 'groom-adversarial')
        self.assertFalse(self.calls)

    def test_removed_constraint_context_cannot_pass_complete_role_mapping(self):
        data = json.loads(self.path.read_text())
        for row in data['obligations']:
            removed = {ref['id'] for ref in row['references'] if ref['path'] == 'rules.md'}
            row['references'] = [ref for ref in row['references'] if ref['id'] not in removed]
            for requirement in row['requirements']:
                requirement['evidence'] = [ref for ref in requirement['evidence'] if ref not in removed]
        self.path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'semantic_context_incomplete:rules.md'):
            b.packets(self.c, self.plan, [], 'groom-adversarial')
        self.assertFalse(self.calls)

    def test_oversized_evidence_blocks_before_evaluator(self):
        (self.root/'request.md').write_text('x' * (b.engine.MAX_BYTES + 1) + '\n')
        with self.assertRaisesRegex(ValueError, 'too_large'):
            b.readiness(self.c, self.plan, [], 'groom-adversarial')
        self.assertFalse(self.calls)

    def test_invalid_span_is_rejected_before_materializing_coverage_range(self):
        data = json.loads(self.path.read_text())
        data['obligations'][0]['references'][0]['end_line'] = 10**12
        self.path.write_text(json.dumps(data))
        def bounded_range(*args):
            if args[-1] > 100000:
                raise AssertionError('Untrusted out-of-file span allocated before validation')
            return range(*args)
        with patch.object(b, 'range', bounded_range, create=True):
            with self.assertRaises(ValueError):
                b.packets(self.c, self.plan, [], 'groom-adversarial')
        self.assertFalse(self.calls)

    def test_missing_reference_blocks_without_evaluator(self):
        data = json.loads(self.path.read_text())
        data['obligations'][0]['references'][0]['path'] = 'missing-public-evidence.txt'
        self.path.write_text(json.dumps(data))
        with self.assertRaises((ValueError, OSError)):
            b.readiness(self.c, self.plan, [], 'groom-adversarial')
        self.assertFalse(self.calls)

    def test_reference_cardinality_is_bounded_before_dispatch(self):
        data = json.loads(self.path.read_text())
        row = data['obligations'][0]
        original = row['references'][0]
        while len(row['references']) < 65:
            row['references'].append(dict(original, id='extra-' + str(len(row['references']))))
        self.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            b.readiness(self.c, self.plan, [], 'groom-adversarial')
        self.assertFalse(self.calls)

    def test_independent_reviewer_rejection_never_calls_evaluator(self):
        base = self.c.worker
        def reject(operation, *args):
            self.worker.fail = operation == 'groom-adversarial'
            return base(operation, *args)
        self.c.worker = reject
        _, result = self.run_handoff()
        self.assertEqual(result['status'], 'failed', result)
        self.assertFalse(self.calls)
        self.assertEqual(len(self.worker.calls), 2)
        self.assertNotIn('groom-adversarial', self.c.state['results'])

    def test_all_actual_worker_and_evaluator_request_bytes_are_charged(self):
        grant, result = self.run_handoff()
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len(self.worker.calls), 5)
        measured = sum(size for _, size in self.worker.calls) + sum(self.calls)
        usage = self.c.usage(grant['id'])
        self.assertEqual(usage['calls'], len(self.worker.calls) + len(self.calls))
        self.assertEqual(usage['request_bytes'], measured)
        retained = dict(usage)
        self.c.execute(grant['id'], 'groom-adversarial', 'challenge')
        self.assertEqual(self.c.usage(grant['id']), retained)

    def test_changed_mapping_policy_invalidates_cached_handoff(self):
        _, result = self.run_handoff()
        self.assertEqual(result['status'], 'passed', result)
        before = list(self.calls)
        data = json.loads(self.path.read_text())
        data['obligations'][0]['question'] += ' Include the revised constraint.'
        self.path.write_text(json.dumps(data))
        plan, context = self.c.context()
        self.assertFalse(self.c.valid('groom-adversarial', plan, context))
        self.assertEqual(self.calls, before)


class InlineGraphReview(unittest.TestCase):
    def setUp(self):
        authoring = load('semantic_inline_fixtures', 'test-package-authoring.py')
        authoring.Authoring.setUp(self)
        self.root = self.c.project

    def test_inline_graph_maps_all_artifacts_without_materializing_caller_files(self):
        (self.root/'graph.json').write_text(json.dumps(self.graph))
        controller = self.c.preparation
        plan = m.plan(self.root, 'demo')
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.git' not in p.parts}
        generated = b.generate(controller, plan, 'groom-adversarial')
        target = self.root/'docs/demo/semantic.json'
        target.write_text(json.dumps(generated))
        plan['reviewer_policy']['semantic_plan'] = 'docs/demo/semantic.json'
        packets = b.packets(controller, plan, [], 'groom-adversarial')
        self.assertIn('requirement_package', {p['kind'] for p in packets})
        rendered = json.dumps(packets)
        for name in self.graph['artifacts']:
            self.assertIn(name, rendered)
        for name, data in before.items():
            self.assertEqual((self.root/name).read_bytes(), data)
        self.assertFalse((self.root/'docs/left').exists())
        original_binding = b.engine.digest(packets)
        self.graph['artifacts']['docs/left/SPEC.md'] += '\nChanged inline requirement.\n'
        (self.root/'graph.json').write_text(json.dumps(self.graph))
        changed = b.packets(controller, plan, [], 'groom-adversarial')
        self.assertNotEqual(b.engine.digest(changed), original_binding)
        self.assertFalse(self.worker.calls)


if __name__ == '__main__':
    unittest.main()
