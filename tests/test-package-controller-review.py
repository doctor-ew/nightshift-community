#!/usr/bin/env python3
"""Independent synthetic budget and restart checks for package composition."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

f = load('package_controller_review_fixtures', 'tests/test-work-packages.py')
m = load('package_controller_review', 'scripts/nightshift-package-controller.py')


class PackageControllerReview(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-package-controller-review-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.graph = f.fixture(self.root)
        self.graph['aggregate'] = dict(calls=32, seconds=240, wall_seconds=240)
        (self.root/'graph.json').write_text(json.dumps(self.graph))
        (self.root/'parent-cases.json').write_text(json.dumps(dict(version=1, cases=[dict(id='R1', requirement='Combine independent functions into a total.', manual=False)])))
        plan_path = self.root/'docs/demo/operations.json'
        plan = json.loads(plan_path.read_text())
        plan['inputs'].update(request='parent.md', spec='graph.json', scenarios='parent-cases.json')
        plan_path.write_text(json.dumps(plan))
        self.worker = f.f.Worker()
        self.c = m.Packages(self.root, 'demo', self.worker)

    def prepare(self):
        assessed = self.c.preparation.assess('groom-spec')
        grant = self.c.preparation.authorize(m.ops.RECIPES['groom'], assessed['binding'], 'synthetic-reviewer', 'prepare-graph')
        result = self.c.prepare(grant['id'])
        self.assertEqual(result['status'], 'ready', result)
        return result

    def authorize(self):
        assessed = self.prepare()
        return self.c.authorize(assessed['binding'], 'synthetic-reviewer', 'graph-grant')['id']

    def test_child_preserves_accepted_architecture_without_new_acceptance(self):
        architecture = m.ops.load('architecture')
        (self.root/'left.py').write_text('def value(): return 1 # FORBIDDEN\n')
        architecture.accept(self.root, dict(id='no-forbidden', decision='Do not use the forbidden literal.',
            operator='synthetic-reviewer', upstream='https://example.invalid/issues/67', scope=['left.py'],
            reference='rules.md', constraints=[dict(kind='forbidden_literal', value='FORBIDDEN')]))
        retained = architecture.location(self.root).read_bytes()
        accepted = architecture.resolve(self.root)
        grant = self.authorize()
        with self.c.lease():
            child = self.c.materialize(self.c.state['authorizations'][grant]['graph']['children'][0], grant)
        _, context = child.context()
        self.assertEqual(context['accepted_architecture'], accepted,
            'Private child contexts must preserve accepted parent authority, not merely architecture prose')
        self.assertEqual(architecture.check(child.project, 'left', context['accepted_architecture'])['status'], 'fail')
        self.assertEqual(architecture.location(self.root).read_bytes(), retained)
        self.assertEqual(len(self.worker.calls), 2)

    def test_malformed_graph_view_retains_authority_and_usage(self):
        grant = self.authorize()
        before = self.c.usage(grant)
        calls = list(self.worker.calls)
        (self.root/'graph.json').write_text('{malformed graph')
        result = m.api(self.root, dict(task='demo', action='view'))
        self.assertEqual(result['assessment']['status'], 'blocked')
        self.assertIn(grant, result['state']['authorizations'])
        self.assertEqual(result['usage'][grant], before)
        self.assertEqual(self.worker.calls, calls)

    def test_preparation_cannot_expand_initial_graph_allowance(self):
        import difflib
        original = json.dumps(dict(self.graph, aggregate=dict(self.graph['aggregate'], calls=1))) + '\n'
        authored = json.dumps(self.graph) + '\n'
        (self.root/'graph.json').write_text(original)
        self.worker.patch = ''.join(difflib.unified_diff(original.splitlines(True), authored.splitlines(True),
            fromfile='a/graph.json', tofile='b/graph.json'))
        assessed = self.c.preparation.assess('groom-spec')
        grant = self.c.preparation.authorize(m.ops.RECIPES['groom'], assessed['binding'],
            'synthetic-reviewer', 'one-call-preparation')
        result = self.c.prepare(grant['id'])
        self.assertEqual(result['status'], 'blocked', result)
        self.assertEqual(len(self.worker.calls), 1)
        self.assertEqual(self.c.preparation.state['authorizations'][grant['id']]['aggregate']['calls'], 1)
        self.assertEqual(json.loads((self.root/'graph.json').read_text())['aggregate']['calls'], 32)
        resumed = m.Packages(self.root, 'demo', self.worker)
        self.assertEqual(resumed.prepare(grant['id'])['status'], 'blocked')
        self.assertEqual(len(self.worker.calls), 1)
        self.assertEqual(resumed.preparation.state['authorizations'][grant['id']]['aggregate']['calls'], 1)
        self.assertFalse(resumed.state['authorizations'])

    def test_preparation_is_inside_parent_call_ceiling(self):
        self.graph['aggregate']['calls'] = sum(child['allowance']['calls'] for child in self.graph['children'])
        (self.root/'graph.json').write_text(json.dumps(self.graph))
        assessed = self.prepare()
        with self.assertRaisesRegex(ValueError, 'parent_allowance_insufficient_after_preparation'):
            self.c.authorize(assessed['binding'], 'synthetic-reviewer', 'insufficient-grant')
        self.assertEqual(len(self.worker.calls), 2)
        self.assertFalse(self.c.state['authorizations'])
        self.assertFalse(self.c.state['children'])

    def test_equivalent_parent_authorizations_reuse_allocations(self):
        assessed = self.prepare()
        first = self.c.authorize(assessed['binding'], 'synthetic-reviewer', 'first-click')
        resumed = m.Packages(self.root, 'demo', self.worker)
        repeated = resumed.authorize(assessed['binding'], 'synthetic-reviewer', 'second-click')
        self.assertEqual(repeated['id'], first['id'])
        self.assertEqual(len(resumed.state['authorizations']), 1)
        self.assertFalse(resumed.state['children'])

    def test_stale_graph_authority_never_launches_child(self):
        grant = self.authorize()
        calls = list(self.worker.calls)
        (self.root/'left_test.py').write_text('raise AssertionError("changed after graph authorization")\n')
        with self.assertRaisesRegex(ValueError, 'package_authorized_inputs_changed'):
            self.c.run(grant)
        self.assertEqual(self.worker.calls, calls)
        self.assertFalse(self.c.state['children'])

    def test_restart_replays_no_implementation_or_accounting(self):
        grant = self.authorize()
        result = self.c.run(grant)
        self.assertEqual(result['status'], 'pending_manual_acceptance', result)
        calls = list(self.worker.calls)
        usage = self.c.usage(grant)
        children = json.loads(json.dumps(self.c.state['children']))
        resumed = m.Packages(self.root, 'demo', self.worker)
        replay = resumed.run(grant)
        self.assertEqual(replay['status'], 'pending_manual_acceptance', replay)
        self.assertEqual(self.worker.calls, calls)
        self.assertEqual(resumed.usage(grant), usage)
        self.assertEqual(resumed.state['children'], children)
        self.assertEqual(usage['calls'], len(calls))
        self.assertEqual(usage['orchestration_provider_calls'], 0)
        self.assertEqual(usage['reserved_seconds'], 0)

    def test_interrupted_input_refresh_resumes_durable_intent(self):
        grant = self.authorize()
        definition = self.c.state['authorizations'][grant]['graph']['children'][0]
        with self.c.lease():
            child = self.c.materialize(definition, grant)
        names = ['left_test.py', definition['plan']]
        for name in names:
            path = self.root/name
            path.write_bytes(path.read_bytes() + b'\n')
        replace = m.os.replace
        def interrupted_replace(source, destination):
            replace(source, destination)
            if Path(source).name.startswith('.package-'):
                raise KeyboardInterrupt('synthetic death after first imported input replacement')
        with patch.object(m.os, 'replace', side_effect=interrupted_replace):
            with self.assertRaises(KeyboardInterrupt):
                with self.c.lease():
                    self.c.materialize(definition, grant)
        resumed = m.Packages(self.root, 'demo', self.worker)
        self.assertIn('update', resumed.state['children']['left'])
        with resumed.lease():
            child = resumed.materialize(definition, grant)
        self.assertNotIn('update', resumed.state['children']['left'])
        for name in names:
            self.assertEqual((child.project/name).read_bytes(), (self.root/name).read_bytes())
        self.assertEqual(len(self.worker.calls), 2)

    def test_changed_import_preserves_operator_child_edits(self):
        grant = self.authorize()
        definition = self.c.state['authorizations'][grant]['graph']['children'][0]
        with self.c.lease():
            child = self.c.materialize(definition, grant)
        name = 'left_test.py'
        operator_bytes = b'# Operator test changes must survive upstream refresh.\n'
        (child.project/name).write_bytes(operator_bytes)
        (self.root/name).write_text('# New upstream test input.\n')
        before = json.loads(json.dumps(self.c.state['children']['left']))
        with self.c.lease():
            with self.assertRaises(ValueError):
                self.c.materialize(definition, grant)
        self.assertEqual((child.project/name).read_bytes(), operator_bytes)
        self.assertEqual(self.c.state['children']['left'], before)
        self.assertEqual(len(self.worker.calls), 2)

    def test_completed_child_retains_standalone_usage_and_blocks_replay(self):
        grant = self.authorize()
        self.assertEqual(self.c.run(grant)['status'], 'pending_manual_acceptance')
        child = self.c.child('left')
        retained = json.loads(json.dumps(child.state['calls']))
        calls = list(self.worker.calls)
        sample = next(iter(retained.values()))
        cases = [('call-cap', 'package_allocation_exceeded:left'),
                 ('seconds-cap', 'package_allocation_exceeded:left'),
                 ('unknown', 'unknown_package_usage_requires_reconciliation')]
        for case, reason in cases:
            with self.subTest(case=case):
                child.state['calls'] = json.loads(json.dumps(retained))
                row = dict(sample, id='standalone-' + case, grant='standalone',
                           seconds=0.01, status='finished', reserved_seconds=7)
                if case == 'call-cap':
                    for index in range(9 - len(retained)):
                        child.state['calls']['standalone-' + str(index)] = dict(row, id='standalone-' + str(index))
                else:
                    if case == 'seconds-cap':
                        row['seconds'] = 61
                    else:
                        row.update(status='pending', seconds=None)
                    child.state['calls'][row['id']] = row
                child.save()
                retained_bytes = child.path.read_bytes()
                resumed = m.Packages(self.root, 'demo', self.worker)
                result = resumed.run(grant)
                self.assertEqual(result['status'], 'blocked', result)
                self.assertEqual(result['reason'], reason)
                self.assertEqual(self.worker.calls, calls)
                self.assertEqual(child.path.read_bytes(), retained_bytes)
                if case == 'unknown':
                    self.assertEqual(result['usage']['unknown_calls'], 1)
                    self.assertGreaterEqual(result['usage']['reserved_seconds'], 7)

    def test_failed_materialization_keeps_reservation_and_can_restart(self):
        grant = self.authorize()
        retained = m.ops.Operations(self.root, 'left', self.worker)
        assessed = retained.assess('groom-spec')
        retained.authorize(['groom-spec'], assessed['binding'], 'synthetic-reviewer', 'unrelated-parent-ledger')
        retained_bytes = retained.path.read_bytes()
        run = m.subprocess.run
        def fail_before_git_init(argv, *args, **kwargs):
            if argv[:3] == ['git', 'init', '-q']:
                raise OSError('synthetic initialization failure')
            return run(argv, *args, **kwargs)
        with patch.object(m.subprocess, 'run', side_effect=fail_before_git_init):
            result = self.c.run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('synthetic initialization failure', result['reason'])
        self.assertEqual(result['usage']['calls'], 2)
        self.assertEqual(result['usage']['reserved_seconds'], 180)
        self.assertEqual(retained.path.read_bytes(), retained_bytes)
        resumed = m.Packages(self.root, 'demo', self.worker)
        self.assertEqual(resumed.run(grant)['status'], 'pending_manual_acceptance')
        self.assertEqual(sum(op == 'implement' for op, _ in self.worker.calls), 3)

    def test_unknown_child_call_keeps_parent_reservation_across_restart(self):
        grant = self.authorize()
        original = self.worker
        def interrupted_worker(operation, packet, route, output, seconds):
            result = original(operation, packet, route, output, seconds)
            if operation == 'groom-spec' and 'docs/left/SPEC.md' in packet['artifacts']:
                raise KeyboardInterrupt('synthetic interrupted child provider')
            return result
        self.c.worker = interrupted_worker
        # Emulate abrupt process death before completion accounting can run.
        with patch.object(m.ops.Operations, 'finish', lambda *args: None):
            with self.assertRaises(KeyboardInterrupt):
                self.c.run(grant)
        resumed = m.Packages(self.root, 'demo', original)
        usage = resumed.usage(grant)
        self.assertEqual(usage['unknown_calls'], 1)
        self.assertEqual(usage['reserved_seconds'], 180)
        calls = list(original.calls)
        result = resumed.run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(original.calls, calls)
        self.assertEqual(resumed.usage(grant), usage)


if __name__ == '__main__':
    unittest.main()
