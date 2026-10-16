#!/usr/bin/env python3
"""Provider transport retries retain budgets without inventing substantive findings."""
import importlib.util
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('transport_fixtures', ROOT / 'tests/test-operations.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class TransportRetry(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.Operations()
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.controller = self.case.c
        self.case.run_op('groom-spec')
        self.case.run_op('groom-rules')

    def retry(self, operation):
        grant = self.case.grant([operation])
        return self.controller.execute(grant, operation, 'retry-' + str(self.case.n))

    def fail_transport(self, operation, packet, route, output, seconds):
        # The synthetic transport fails before launch; controller-owned proof releases
        # its time reservation while the call and failed-attempt charges remain.
        import json
        output.with_suffix('.ownership.json').write_text(json.dumps(dict(status='not_started')))
        raise ValueError('provider_exit:75')

    def test_transport_retry_keeps_inputs_and_calls_without_repair_findings(self):
        before = self.controller.assess('groom-spec')['binding']
        self.controller.worker = self.fail_transport
        failure = self.retry('groom-adversarial')
        self.assertEqual(failure['reason'], 'provider_exit:75')
        self.assertEqual(self.controller.usage(failure['grant'])['calls'], 1)
        retained = self.controller.state['attempts'][-1].copy()
        retry = self.controller.assess('groom-adversarial')
        self.assertNotIn('unchanged_failure_requires_repair', retry['blockers'])
        self.assertEqual(retry['findings'], [])
        self.assertIsNone(self.controller.repair_evidence('groom-spec'))
        self.assertEqual(self.controller.assess('groom-spec')['binding'], before)
        self.assertEqual(self.controller.assess('groom-spec')['status'], 'current')
        self.controller.worker = self.case.worker
        self.assertEqual(self.retry('groom-adversarial')['status'], 'passed')
        self.assertEqual(self.controller.state['attempts'][-2], retained)

    def test_transport_failures_still_exhaust_three_failure_cap(self):
        self.controller.worker = self.fail_transport
        for _ in range(3):
            self.assertEqual(self.retry('groom-adversarial')['reason'], 'provider_exit:75')
        assessed = self.controller.assess('groom-adversarial')
        self.assertIn('repair_limit_exhausted', assessed['blockers'])
        self.assertNotIn('unchanged_failure_requires_repair', assessed['blockers'])
        attempts = [a for a in self.controller.state['attempts'] if a['operation'] == 'groom-adversarial']
        self.assertEqual(len(attempts), 3)
        self.assertEqual(len([c for c in self.controller.state['calls'].values() if c['operation'] == 'groom-adversarial']), 3)

    def test_transport_review_preserves_external_adoption_and_implementation_binding(self):
        self.case.full()
        (self.case.root / 'app.py').write_text('def answer(): return 2 # external change\n')
        adopted = self.controller.assess('adopt')
        self.case.run_op('adopt', dict(binding=adopted['binding'], identity='external', provider='human'))
        self.case.run_op('verify')
        implementation = self.controller.assess('implement')
        adoption = self.controller.assess('adopt')
        self.controller.worker = self.fail_transport
        self.assertEqual(self.retry('review')['reason'], 'provider_exit:75')
        self.assertIsNone(self.controller.repair_evidence('implement'))
        self.assertEqual(self.controller.assess('implement')['binding'], implementation['binding'])
        self.assertEqual(self.controller.assess('adopt')['binding'], adoption['binding'])
        self.assertEqual(self.controller.assess('adopt')['status'], 'current')
        self.controller.worker = self.case.worker
        self.assertEqual(self.retry('review')['status'], 'passed')

    def test_bound_semantic_fail_with_nonzero_provider_remains_substantive(self):
        runtime = tempfile.TemporaryDirectory(prefix='nightshift-sealed-operation-runtime-')
        self.addCleanup(runtime.cleanup)
        for provider in ('codex', 'claude'):
            executable = Path(runtime.name) / provider
            executable.write_text('#!/bin/sh\nexit 99\n')
            executable.chmod(0o755)
        runtime_path = patch.dict(os.environ, {'PATH': runtime.name + os.pathsep + os.environ['PATH']})
        runtime_path.start()
        self.addCleanup(runtime_path.stop)
        # Admission sees only these provider stubs; bounded transport below owns
        # every response, and accidental stub execution fails closed.
        for provider in ('codex', 'claude'):
            self.assertEqual(fixtures.m.shutil.which(provider), str(Path(runtime.name) / provider))
        self.controller.worker = self.controller.dispatch
        runner = fixtures.m.load('controller-recovery')
        def bounded(argv, target, env, seconds, logfile, **kw):
            import json
            packet = json.loads(Path(argv[argv.index('--in') + 1]).read_text())
            output = Path(argv[argv.index('--out') + 1])
            routing = json.loads(Path(env['NIGHTSHIFT_ROUTING_FILE']).read_text())
            route = routing['roles']['nightshift-operation-worker']['gears']['1']
            self.case.worker.fail = True
            output.write_text(json.dumps(self.case.worker('groom-adversarial', packet, route, output, seconds)))
            return 1
        real_load = fixtures.m.load
        with patch.object(runner, 'bounded', bounded), patch.object(fixtures.m, 'load', side_effect=lambda name: runner if name == 'controller-recovery' else real_load(name)):
            failure = self.retry('groom-adversarial')
        self.assertEqual(failure['reason'], 'substantive_failure')
        self.assertIn('classification unclear', self.controller.repair_findings('groom-spec'))
        self.assertIn('unchanged_failure_requires_repair', self.controller.assess('groom-adversarial')['blockers'])


if __name__ == '__main__':
    unittest.main()
