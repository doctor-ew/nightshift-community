#!/usr/bin/env python3
"""Independent offline regressions for repair composition recovery."""
import concurrent.futures
import difflib
import importlib.util
import json
from pathlib import Path
import threading
import unittest

spec = importlib.util.spec_from_file_location('healing_fixture', Path(__file__).with_name('test-operation-healing.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class ReviewRegressions(unittest.TestCase):
    setUp = h.Healing.setUp
    tearDown = h.Healing.tearDown
    work = h.Healing.work
    grant = h.Healing.grant

    def test_restart_after_repair_integration_before_cursor_update(self):
        (self.root / 'app.py').write_text('def answer():\n    return 1\n')
        grant = self.grant()
        deadline = self.c.state['authorizations'][grant]['deadline']
        execute = self.c.execute

        class Crash(BaseException):
            pass

        def interrupted(*args):
            result = execute(*args)
            if args[1] == 'implement' and self.count == 2:
                raise Crash()
            return result

        self.c.execute = interrupted
        with self.assertRaises(Crash):
            self.c.chain(grant)
        self.assertEqual(self.count, 2)
        self.c = h.m.Operations(self.root, 'demo', self.work)
        result = self.c.chain(grant)
        self.assertEqual(result['view']['status'], 'pending_manual_acceptance')
        self.assertEqual(self.count, 2)
        self.assertEqual(len(self.worker.calls), 5)
        self.assertEqual(self.c.state['authorizations'][grant]['deadline'], deadline)
        self.assertEqual(self.c.usage(grant)['calls'], 5)

    def test_adversarial_exhaustion_then_external_validation_never_implements(self):
        authored = 0

        def unresolved(operation, packet, route, output, seconds):
            nonlocal authored
            self.worker.patch = ''
            self.worker.fail = operation == 'groom-adversarial'
            if operation == 'groom-spec':
                authored += 1
                if authored > 1:
                    before = (self.root / 'spec.md').read_text()
                    after = before + 'Clarification attempt ' + str(authored) + '\n'
                    self.worker.patch = ''.join(difflib.unified_diff(
                        before.splitlines(True), after.splitlines(True),
                        fromfile='a/spec.md', tofile='b/spec.md'))
            return self.worker(operation, packet, route, output, seconds)

        self.c.worker = unresolved
        grant = self.grant()
        result = self.c.chain(grant)
        self.assertEqual(result['view']['status'], 'incomplete')
        failures = [a for a in self.c.state['attempts']
                    if a['operation'] == 'groom-adversarial' and a['status'] == 'failed']
        self.assertEqual(len(failures), 3)
        retained = (self.root / 'spec.md').read_bytes()
        calls = len(self.worker.calls)
        self.c = h.m.Operations(self.root, 'demo', self.work)
        self.c.chain(grant)
        self.assertEqual(len(self.worker.calls), calls)
        (self.root / 'app.py').write_text('def answer(): return 2 # external implementation\n')
        assessed = self.c.assess('adopt')
        external = self.c.authorize(h.m.RECIPES['external'], assessed['binding'],
            'synthetic', 'external-review-regression', dict(binding=assessed['binding'],
                identity='external-synthetic-author', provider='human'))
        result = self.c.chain(external['id'])
        self.assertEqual(result['view']['status'], 'pending_manual_acceptance')
        self.assertEqual((self.root / 'spec.md').read_bytes(), retained)
        self.assertEqual(sum(op == 'implement' for op, _ in self.worker.calls), 0)
        self.assertEqual(len([a for a in self.c.state['attempts']
                    if a['operation'] == 'groom-adversarial' and a['status'] == 'failed']), 3)

    def test_concurrent_chain_request_never_duplicates_provider_work(self):
        entered = threading.Event()
        release = threading.Event()
        original = self.work

        def slow(operation, packet, route, output, seconds):
            if operation == 'groom-spec':
                entered.set()
                if not release.wait(10):
                    raise AssertionError('synthetic worker was not released')
            return original(operation, packet, route, output, seconds)

        self.c.worker = slow
        grant = self.grant()
        other = h.m.Operations(self.root, 'demo', self.work)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(self.c.chain, grant)
            try:
                self.assertTrue(entered.wait(10))
                with self.assertRaisesRegex(ValueError, 'operation_busy'):
                    other.chain(grant)
            finally:
                release.set()
            result = running.result(timeout=30)
        self.assertEqual(result['view']['status'], 'pending_manual_acceptance')
        other.chain(grant)
        self.assertEqual([op for op, _ in self.worker.calls],
                         ['groom-spec', 'groom-adversarial', 'implement', 'review'])

    def test_control_character_summary_preserves_identity_within_limit(self):
        row = dict(id='π' * 200, exit_code=1, tests=1,
                   output_sha256='a' * 64, output='\x1b"\\π' * 3000)
        finding = h.m.verification_finding(row, 'synthetic.tests.json')
        self.assertLessEqual(len(finding), 4000)
        summary = json.loads(finding)
        self.assertEqual(summary['output_sha256'], row['output_sha256'])
        self.assertEqual(summary['id'], row['id'])
        self.assertEqual(summary['evidence'], 'synthetic.tests.json')

    def test_large_failure_log_remains_repairable_with_bounded_findings(self):
        (self.root / 'app.py').write_text('def answer():\n    return 1\n')
        original = (self.root / 'test_app.py').read_text()
        (self.root / 'test_app.py').write_text(
            'from app import answer\nif answer() != 2: print("π" * 5000)\n' + original)
        result = self.c.chain(self.grant())
        self.assertEqual(result['view']['status'], 'pending_manual_acceptance')
        failed = [a for a in self.c.state['attempts'] if a['operation'] == 'verify' and a['status'] == 'failed']
        self.assertEqual(len(failed), 1)
        self.assertTrue(all(len(finding) <= 4000 for finding in failed[0]['findings']))
        self.assertTrue(failed[0]['evidence'])
        self.assertEqual(self.count, 2)

    def test_completed_chain_replay_does_not_accept_changed_source(self):
        grant = self.grant()
        self.assertEqual(self.c.chain(grant)['view']['status'], 'pending_manual_acceptance')
        calls = len(self.worker.calls)
        (self.root / 'app.py').write_text('def answer():\n    return 1\n')
        self.c = h.m.Operations(self.root, 'demo', self.work)
        result = self.c.chain(grant)
        self.assertEqual(result['view']['status'], 'incomplete')
        self.assertEqual(len(self.worker.calls), calls)
        self.assertTrue(any(row['status'] == 'stale' for row in result['results']))


if __name__ == '__main__':
    unittest.main()
