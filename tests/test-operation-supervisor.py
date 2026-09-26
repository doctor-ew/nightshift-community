#!/usr/bin/env python3
"""Synthetic bounded repair over independently callable operations."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fixtures', ROOT/'tests/test-operations.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
s = f.m.load('operation-supervisor')


class Supervisor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nightshift-supervisor-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        f.fixture(self.root)
        self.worker = f.Worker()
        self.c = f.m.Operations(self.root, 'demo', self.worker)

    def grant(self, operations=None, repair=True):
        operations = operations or f.m.RECIPES['factory']
        a = self.c.assess(operations[0])
        return self.c.authorize(operations, a['binding'], 'synthetic', 'grant', {'bounded_repair': True} if repair else None)['id']

    def test_verify_failure_repair_full_verification_review_and_noop(self):
        (self.root/'app.py').write_text('def answer():\n    return 1\n')
        original = self.worker
        def worker(op, packet, route, output, seconds):
            original.patch = ''
            if op == 'implement' and packet['findings']:
                original.patch = '--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n def answer():\n-    return 1\n+    return 2\n'
            return original(op, packet, route, output, seconds)
        self.c.worker = worker
        g = self.grant()
        result = s.run(self.c, g)
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(result['view']['status'], 'pending_manual_acceptance')
        self.assertEqual([a['operation'] for a in self.c.state['attempts']], ['groom-spec','groom-rules','groom-adversarial','groom','implement','verify','implement','verify','review'])
        self.assertEqual(len(result['supervisor']['decisions']), 1)
        self.assertEqual(result['supervisor']['decisions'][0]['category'], 'substantive')
        calls = list(original.calls)
        usage = self.c.usage(g)
        restarted = f.m.Operations(self.root, 'demo', worker)
        self.assertEqual(s.run(restarted, g)['status'], 'passed')
        self.assertEqual(original.calls, calls)
        self.assertEqual(restarted.usage(g), usage)
        (self.root/'app.py').write_text('def answer(): return 3\n')
        self.assertEqual(s.run(restarted, g)['status'], 'blocked')
        self.assertEqual(original.calls, calls)

    def test_unchanged_repair_stops_before_repeated_judgment(self):
        (self.root/'app.py').write_text('def answer(): return 1\n')
        result = s.run(self.c, self.grant())
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('unchanged_failure', result['supervisor']['reason'])
        self.assertEqual(sum(a['operation'] == 'verify' for a in self.c.state['attempts']), 1)
        self.assertEqual(sum(op == 'implement' for op, _ in self.worker.calls), 2)
        calls = list(self.worker.calls)
        self.assertEqual(s.run(f.m.Operations(self.root,'demo',self.worker), 'grant')['status'], 'blocked')
        self.assertEqual(self.worker.calls, calls)

    def test_old_grant_does_not_acquire_repair_authority(self):
        g = self.grant(repair=False)
        with self.assertRaisesRegex(ValueError, 'bounded_repair_authorization_required'):
            s.run(self.c, g)
        self.assertEqual(self.worker.calls, [])

    def test_transport_failure_requires_explicit_action_and_keeps_charge(self):
        def fail(*args): raise ValueError('provider_exit:75')
        self.c.worker = fail
        result = s.run(self.c, self.grant())
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['supervisor']['decisions'][0]['category'], 'transport')
        self.assertEqual(result['supervisor']['decisions'][0]['accounting']['infrastructure_failures'], 1)
        self.assertEqual(result['supervisor']['decisions'][0]['accounting']['substantive_failures'], 0)
        self.assertEqual(self.c.usage('grant')['calls'], 1)

    def test_adversarial_failure_repairs_spec_within_original_grant(self):
        original = self.worker
        def worker(op, packet, route, output, seconds):
            original.fail = op == 'groom-adversarial' and not any(x['operation'] == 'groom-adversarial' for x in original.packets)
            original.patch = ''
            if op == 'groom-spec' and packet['findings']:
                original.patch = '--- a/spec.md\n+++ b/spec.md\n@@ -1 +1 @@\n-Return two.\n+Return exactly the integer two.\n'
            return original(op, packet, route, output, seconds)
        self.c.worker = worker
        result = s.run(self.c, self.grant())
        self.assertEqual(result['status'], 'passed', result)
        decision = result['supervisor']['decisions'][0]
        self.assertEqual(decision['eligible_operation'], 'groom-spec')
        self.assertNotEqual(decision['previous_binding'], decision['repair_binding'])
        self.assertEqual(len(self.c.state['authorizations']), 1)


if __name__ == '__main__': unittest.main()
