#!/usr/bin/env python3
"""Independent synthetic adversarial checks for bounded operation repair."""
import concurrent.futures
import difflib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('supervisor_review_fixtures', ROOT/'tests/test-operations.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
s = f.m.load('operation-supervisor')


class SupervisorReview(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-supervisor-review-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        f.fixture(self.root)
        self.worker = f.Worker()
        self.c = f.m.Operations(self.root, 'demo', self.worker)

    def grant(self, operations=None):
        operations = operations or f.m.RECIPES['factory']
        assessed = self.c.assess(operations[0])
        return self.c.authorize(operations, assessed['binding'], 'synthetic-reviewer', 'review-grant', {'bounded_repair': True})['id']

    def test_source_change_after_final_operation_never_reports_passed(self):
        execute = self.c.execute
        def change_after_review(grant, operation, request, supervised=False):
            result = execute(grant, operation, request, supervised)
            if operation == 'review' and result['status'] == 'passed':
                (self.root/'app.py').write_text('def answer(): return 999 # concurrent external change\n')
            return result
        self.c.execute = change_after_review
        result = s.run(self.c, self.grant())
        self.assertEqual(result['status'], 'blocked', 'Initial supervisor completion must revalidate the same evidence as replay')
        self.assertNotEqual(result['view']['status'], 'pending_manual_acceptance')

    def test_completed_step_crash_reuses_request_and_accounting(self):
        grant = self.grant()
        execute = self.c.execute
        def interrupt_after_completion(*args):
            execute(*args)
            raise KeyboardInterrupt('synthetic crash before supervisor acknowledgement')
        self.c.execute = interrupt_after_completion
        with self.assertRaises(KeyboardInterrupt):
            s.run(self.c, grant)
        self.c.reload()
        step = self.c.state['supervisors'][grant]['steps'][0]
        self.assertFalse(step.get('completed'))
        self.assertEqual(len(self.worker.calls), 1)
        resumed = f.m.Operations(self.root, 'demo', self.worker)
        self.assertEqual(s.run(resumed, grant)['status'], 'passed')
        self.assertEqual(sum(operation == 'groom-spec' for operation, _ in self.worker.calls), 1)
        self.assertEqual(len(self.worker.calls), 4)
        self.assertEqual(resumed.usage(grant)['calls'], 4)
        self.assertEqual(resumed.state['supervisors'][grant]['steps'][0]['request'], step['request'])

    def test_stopped_retry_ledger_produces_durable_blocker(self):
        grant = self.grant()
        path = self.c.directory/'groom-spec.retry.json'
        retry = f.m.load('retry-budget')
        for index in range(3):
            retry.account(path, 'retained-transport-' + str(index), 'transport')
        before = path.read_bytes()
        self.worker.fail = True
        result = s.run(self.c, grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('budget exhausted', json.dumps(result))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.worker.calls), 0)
        resumed = f.m.Operations(self.root, 'demo', self.worker)
        self.assertEqual(resumed.state['supervisors'][grant]['status'], 'blocked')
        self.assertIn('budget exhausted', resumed.state['supervisors'][grant]['reason'])
        self.assertEqual(s.run(resumed, grant)['status'], 'blocked')
        self.assertEqual(len(self.worker.calls), 0)
        self.assertEqual(path.read_bytes(), before)

    def test_symlink_state_directory_rejected_before_lock_creation(self):
        grant = self.grant()
        original = self.c.directory
        retained = original.with_name(original.name + '-retained')
        original.rename(retained)
        original.symlink_to(retained, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'unsafe_state_directory'):
            s.run(self.c, grant)
        self.assertFalse((retained/'supervisor.lock').exists(),
            'Supervisor must reject a symlink state directory before creating its lock in the target')
        self.assertEqual(self.worker.calls, [])

    def test_stale_grant_never_dispatches(self):
        grant = self.grant()
        (self.root/'rules.md').write_text('Changed rules after authorization.\n')
        result = s.run(self.c, grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.worker.calls, [])
        self.assertEqual(self.c.usage(grant)['calls'], 0)

    def test_recipe_cannot_omit_final_verification_and_review(self):
        with self.assertRaisesRegex(ValueError, 'invalid_bounded_repair_authority'):
            self.grant(['groom-spec', 'groom-rules', 'groom-adversarial', 'groom', 'implement'])
        self.assertFalse(self.c.state['authorizations'])
        self.assertEqual(self.worker.calls, [])

    def test_implementation_repair_receives_actual_verification_failure(self):
        (self.root/'app.py').write_text('def answer():\n    return 1\n')
        s.run(self.c, self.grant())
        repairs = [packet for packet in self.worker.packets if packet['operation'] == 'implement' and packet['findings']]
        self.assertEqual(len(repairs), 1)
        self.assertIn('AssertionError: 1 != 2', json.dumps(repairs[0]),
            'A targeted repair needs the retained failing assertion, not only the generic failed_or_vacuous_tests reason')

    def test_tampered_failure_evidence_blocks_repair_dispatch(self):
        (self.root/'app.py').write_text('def answer():\n    return 1\n')
        execute = self.c.execute
        def tamper_after_verification(grant, operation, request, supervised=False):
            result = execute(grant, operation, request, supervised)
            if operation == 'verify' and result['status'] == 'failed':
                (self.c.directory/(request + '.tests.json')).write_text('{"observations": []}\n')
            return result
        self.c.execute = tamper_after_verification
        result = s.run(self.c, self.grant())
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('stale_repair_evidence', result['supervisor']['reason'])
        self.assertEqual(sum(op == 'implement' for op, _ in self.worker.calls), 1)

    def test_concurrent_supervisors_do_not_duplicate_dispatch(self):
        entered = threading.Event()
        release = threading.Event()
        original = self.worker
        def wait_worker(*args):
            entered.set()
            if not release.wait(10):
                raise ValueError('synthetic fixture release timed out')
            return original(*args)
        self.c.worker = wait_worker
        grant = self.grant()
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            future = pool.submit(s.run, self.c, grant)
            try:
                self.assertTrue(entered.wait(10))
                other = f.m.Operations(self.root, 'demo', original)
                with self.assertRaisesRegex(ValueError, 'supervisor_busy'):
                    s.run(other, grant)
            finally:
                release.set()
            self.assertEqual(future.result(timeout=40)['status'], 'passed')
        self.assertEqual(len(original.calls), 4)
        self.assertEqual(self.c.usage(grant)['calls'], 4)

    def test_verification_exhaustion_allows_changed_external_verification(self):
        (self.root/'app.py').write_text('def answer(): return 1\n')
        original = self.worker
        def ineffective_repair(operation, packet, route, output, seconds):
            original.patch = ''
            if operation == 'implement' and packet['findings']:
                before = packet['artifacts']['app.py']
                after = before + '# attempted repair ' + str(len(original.calls)) + '\n'
                original.patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/app.py', tofile='b/app.py'))
            return original(operation, packet, route, output, seconds)
        self.c.worker = ineffective_repair
        result = s.run(self.c, self.grant())
        self.assertEqual(result['supervisor']['reason'], 'repair_limit_exhausted')
        self.assertEqual(sum(a['operation'] == 'verify' and a['status'] == 'failed' for a in self.c.state['attempts']), 3)
        calls = list(original.calls)
        (self.root/'app.py').write_text('def answer(): return 2 # corrected externally\n')
        original.patch = ''
        resumed = f.m.Operations(self.root, 'demo', original)
        assessed = resumed.assess('adopt')
        external = resumed.authorize(f.m.RECIPES['external'], assessed['binding'], 'synthetic-reviewer', 'external-verify',
            dict(binding=assessed['binding'], identity='external-human', provider='human'))
        result = resumed.chain(external['id'])
        self.assertEqual(result['view']['status'], 'pending_manual_acceptance')
        self.assertEqual(sum(op == 'implement' for op, _ in original.calls), sum(op == 'implement' for op, _ in calls))

    def test_repeated_findings_exhaust_then_external_adoption(self):
        original = self.worker
        def fail_review(operation, packet, route, output, seconds):
            original.fail = operation == 'review'
            original.patch = ''
            if operation == 'implement' and packet['findings']:
                before = packet['artifacts']['app.py']
                after = before + '# synthetic repair ' + str(len(original.calls)) + '\n'
                original.patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/app.py', tofile='b/app.py'))
            return original(operation, packet, route, output, seconds)
        self.c.worker = fail_review
        grant = self.grant()
        result = s.run(self.c, grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['supervisor']['reason'], 'repair_limit_exhausted')
        failures = [a for a in self.c.state['attempts'] if a['operation'] == 'review' and a['status'] == 'failed']
        self.assertEqual(len(failures), 3)
        calls = list(original.calls)
        resumed = f.m.Operations(self.root, 'demo', fail_review)
        self.assertEqual(s.run(resumed, grant)['status'], 'blocked')
        self.assertEqual(original.calls, calls)
        unchanged = resumed.assess('adopt')
        unchanged_grant = resumed.authorize(f.m.RECIPES['external'], unchanged['binding'], 'synthetic-reviewer', 'unchanged-external',
            dict(binding=unchanged['binding'], identity='external-human', provider='human'))
        with self.assertRaisesRegex(ValueError, 'unchanged_failure_requires_repair'):
            resumed.chain(unchanged_grant['id'])
        self.assertEqual(original.calls, calls, 'Re-adopting unchanged failed source must not purchase another Review')
        retained = json.loads(json.dumps(resumed.state['attempts']))
        (self.root/'app.py').write_text('def answer(): return 2 # external implementation\n')
        original.fail = False
        original.patch = ''
        resumed.worker = original
        assessed = resumed.assess('adopt')
        external = resumed.authorize(f.m.RECIPES['external'], assessed['binding'], 'synthetic-reviewer', 'external-review',
            dict(binding=assessed['binding'], identity='external-human', provider='human'))
        outcome = resumed.chain(external['id'])
        self.assertEqual(outcome['view']['status'], 'pending_manual_acceptance')
        self.assertEqual(sum(op == 'implement' for op, _ in original.calls), sum(op == 'implement' for op, _ in calls))
        self.assertEqual(resumed.state['attempts'][:len(retained)], retained)


if __name__ == '__main__':
    unittest.main()
