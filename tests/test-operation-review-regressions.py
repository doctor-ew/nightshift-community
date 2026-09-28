#!/usr/bin/env python3
"""Independent review regressions; all workers/transports are synthetic."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixtures = load('tests/test-operations.py', 'review_operation_fixtures')
decisions = load('scripts/nightshift-operation-decisions.py', 'review_operation_decisions')
engine_fixtures = load('tests/test-decision-engine.py', 'review_decision_fixtures')


class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nightshift-independent-review-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = fixtures.fixture(self.root)
        self.worker = fixtures.Worker()
        self.controller = fixtures.m.Operations(self.root, 'demo', self.worker)

    def test_changed_authorized_route_cannot_dispatch(self):
        controller = self.controller
        assessed = controller.assess('groom-spec')
        grant = controller.authorize(['groom-spec'], assessed['binding'], 'synthetic-operator', 'route-grant')
        original_route = controller.route

        def changed_route(operation, plan):
            return dict(original_route(operation, plan), model='synthetic-unapproved-model-v2')

        # Routing may live outside the target repository, so its change need not
        # change the authorized source corpus.
        controller.route = changed_route
        try:
            result = controller.execute(grant['id'], 'groom-spec', 'changed-route')
        except ValueError:
            result = {'status': 'blocked'}
        self.assertEqual(self.worker.calls, [], 'An unapproved route dispatched a worker')
        self.assertNotEqual(result['status'], 'passed')

    def test_semantic_receipt_rejects_current_model_change(self):
        engine = decisions.engine
        packet = engine_fixtures.packet()
        settings = dict(endpoint='https://example.invalid/evaluate', model='fixture-v1',
                        key_env='SYNTHETIC_UNUSED', timeout_seconds=1, max_bytes=24576,
                        allow_loopback=False, enabled=True)
        directory = self.controller.directory / 'decisions'
        directory.mkdir(parents=True)

        def transport(current, key, body):
            return engine.encoded(dict(model=current['model'], answers={
                'supported': dict(type='noul', noul=1)}))

        evaluator = engine.Engine(directory, 'synthetic-authority', settings,
                                  lambda *args: 'synthetic-call', lambda *args: None,
                                  transport=transport, policy=dict(engine.POLICY, shadow_percent=0))
        receipt = evaluator.decide(packet)
        record = dict(authority='synthetic-authority', settings=settings, receipts=[receipt])
        self.controller.semantic_settings = dict(settings, model='fixture-v2')
        # Packet construction is orthogonal to the cached-configuration boundary.
        with patch.object(decisions, 'packets', return_value=[packet]):
            with self.assertRaises(ValueError):
                decisions.validate(self.controller, self.plan, record, [])

    def interrupt_after_completed_output(self, failed=False):
        controller = self.controller
        self.worker.fail = failed
        assessed = controller.assess('groom-spec')
        grant = controller.authorize(['groom-spec'], assessed['binding'], 'synthetic-operator', 'crash-grant')

        def die_before_accounting(*args):
            raise KeyboardInterrupt('synthetic controller interruption')

        controller.finish = die_before_accounting
        with self.assertRaises(KeyboardInterrupt):
            controller.execute(grant['id'], 'groom-spec', 'completed-worker')
        return grant['id']

    def test_completed_worker_restart_accounts_once_without_dispatch(self):
        grant = self.interrupt_after_completed_output()
        controller = fixtures.m.Operations(self.root, 'demo', self.worker)
        result = controller.execute(grant, 'groom-spec', 'completed-worker')
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(len(self.worker.calls), 1)
        usage = controller.usage(grant)
        self.assertEqual((usage['calls'], usage['unknown']), (1, 0))
        controller.execute(grant, 'groom-spec', 'completed-worker')
        self.assertEqual(controller.usage(grant), usage)
        self.assertEqual(len(self.worker.calls), 1)

    def test_completed_failed_worker_restart_preserves_terminal_failure(self):
        grant = self.interrupt_after_completed_output(failed=True)
        controller = fixtures.m.Operations(self.root, 'demo', self.worker)
        try:
            controller.execute(grant, 'groom-spec', 'completed-worker')
        except ValueError:
            pass
        controller.reload()
        attempt = controller.state['attempts'][-1]
        self.assertEqual(attempt['status'], 'failed', 'Known failed output must not remain an unknown invocation')
        self.assertIn('classification unclear', attempt['findings'])
        self.assertEqual(len(self.worker.calls), 1)
        self.assertEqual(controller.usage(grant)['unknown'], 0)

    def test_integration_preserves_existing_executable_mode(self):
        path = self.root / 'app.py'
        path.chmod(0o755)
        before = fixtures.m.sha(path)
        content = 'def answer():\n    return 3\n'
        after = decisions.engine.text_hash(content)
        self.controller.integrate({'app.py': dict(before=before, text=content, after=after)})
        self.assertEqual(path.stat().st_mode & 0o777, 0o755)
        self.assertEqual(path.read_text(), content)

    def test_all_skipped_tests_do_not_pass_verification(self):
        (self.root / 'test_app.py').write_text(
            'import unittest\n'
            'class Test(unittest.TestCase):\n'
            '    @unittest.skip("not implemented")\n'
            '    def test_answer(self): self.fail("must execute")\n'
            'unittest.main()\n')
        controller = self.controller
        for operation in [*fixtures.m.RECIPES['factory'][:5], 'verify']:
            assessed = controller.assess(operation)
            grant = controller.authorize([operation], assessed['binding'],
                                         'synthetic-operator', 'skipped-' + operation)
            controller.execute(grant['id'], operation, 'skipped-run-' + operation)
        verification = next(a for a in controller.state['attempts'] if a['operation'] == 'verify')
        self.assertEqual(verification['status'], 'failed', 'A discovered but skipped test is not executed evidence')

    def test_checkpoint_restart_rejects_changed_dispatch_policy(self):
        controller = self.controller
        assessed = controller.assess('groom-spec')
        grant = controller.authorize(['groom-spec'], assessed['binding'],
                                     'synthetic-operator', 'checkpoint-policy')

        def interrupt_finalize(attempt):
            raise KeyboardInterrupt('synthetic checkpoint interruption')

        controller.finalize = interrupt_finalize
        with self.assertRaises(KeyboardInterrupt):
            controller.execute(grant['id'], 'groom-spec', 'checkpoint-policy-worker')
        resumed = fixtures.m.Operations(self.root, 'demo', self.worker)
        original_policy = resumed.policy_binding
        resumed.policy_binding = lambda plan: dict(original_policy(plan), routing_sha256='0' * 64)
        # A routing-file change can preserve the selected model while changing
        # provider transport settings; the full authorization policy still binds it.
        with self.assertRaisesRegex(ValueError, 'policy_changed'):
            resumed.execute(grant['id'], 'groom-spec', 'checkpoint-policy-worker')
        self.assertEqual(len(self.worker.calls), 1)


if __name__ == '__main__':
    unittest.main()
