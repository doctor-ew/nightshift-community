#!/usr/bin/env python3
"""Independent synthetic restart, integration and evidence acceptance checks."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('integrated_fixtures', ROOT/'tests/test-operations.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class IntegratedAcceptance(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-integrated-acceptance-')
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        fixtures.fixture(self.project)
        self.worker = fixtures.Worker()
        self.sequence = 0
        self.restart()

    def restart(self):
        self.controller = fixtures.m.Operations(self.project, 'demo', self.worker)

    def run_operation(self, operation, attestation=None):
        self.sequence += 1
        request = 'acceptance-' + str(self.sequence)
        assessed = self.controller.assess(operation)
        grant = self.controller.authorize([operation], assessed['binding'], 'synthetic-reviewer', request, attestation)
        return self.controller.execute(grant['id'], operation, request + '-run')

    def test_exhaustion_restart_external_adoption_and_replay(self):
        self.run_operation('groom-rules')
        for index in range(3):
            self.restart()
            (self.project/'spec.md').write_text('Return two. Clarification ' + str(index) + '\n')
            self.worker.fail = False
            self.assertEqual(self.run_operation('groom-spec')['status'], 'passed')
            self.worker.fail = True
            self.assertEqual(self.run_operation('groom-adversarial')['status'], 'failed')
        retained_attempts = json.loads(json.dumps(self.controller.state['attempts']))
        retained_draft = (self.project/'spec.md').read_bytes()
        self.restart()
        self.assertIn('repair_limit_exhausted', self.controller.assess('groom-adversarial')['blockers'])
        (self.project/'app.py').write_text('def answer(): return 2 # externally implemented\n')
        self.worker.fail = False
        assessed = self.controller.assess('adopt')
        grant = self.controller.authorize(fixtures.m.RECIPES['external'], assessed['binding'],
            'synthetic-reviewer', 'external-grant', dict(binding=assessed['binding'], identity='external-human', provider='human'))
        result = self.controller.chain(grant['id'])
        self.assertEqual(result['view']['status'], 'pending_manual_acceptance')
        calls = list(self.worker.calls)
        usage = self.controller.usage(grant['id'])
        self.restart()
        self.assertEqual(self.controller.chain(grant['id'])['view']['status'], 'pending_manual_acceptance')
        self.assertEqual(self.worker.calls, calls)
        self.assertEqual(self.controller.usage(grant['id']), usage)
        self.assertEqual(sum(operation == 'implement' for operation, _ in calls), 0)
        self.assertEqual(self.controller.state['attempts'][:len(retained_attempts)], retained_attempts)
        self.assertEqual((self.project/'spec.md').read_bytes(), retained_draft)

    def test_parent_integration_failure_restarts_without_worker(self):
        (self.project/'second.py').write_text('second = 1\n')
        plan_path = self.project/'docs/demo/operations.json'
        plan = json.loads(plan_path.read_text())
        plan['scope'].append('second.py')
        plan_path.write_text(json.dumps(plan))
        for operation in fixtures.m.RECIPES['groom']:
            self.assertEqual(self.run_operation(operation)['status'], 'passed')
        self.worker.patch = ('--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n def answer():\n-    return 2\n+    return 2 # reviewed patch\n'
            '--- a/second.py\n+++ b/second.py\n@@ -1 +1 @@\n-second = 1\n+second = 2\n')
        integrate = self.controller.integrate
        def fail_integration(changes):
            integrate({'app.py': changes['app.py']})
            raise OSError('synthetic parent integration unavailable')
        self.controller.integrate = fail_integration
        with self.assertRaisesRegex(OSError, 'parent integration unavailable'):
            self.run_operation('implement')
        attempt = self.controller.state['attempts'][-1]
        self.assertEqual(attempt['status'], 'checkpoint')
        self.assertIn('reviewed patch', (self.project/'app.py').read_text())
        self.assertEqual((self.project/'second.py').read_text(), 'second = 1\n')
        calls = list(self.worker.calls)
        usage = self.controller.usage(attempt['grant'])
        self.restart()
        result = self.controller.execute(attempt['grant'], 'implement', attempt['request'])
        self.assertEqual(result['status'], 'passed')
        self.assertIn('reviewed patch', (self.project/'app.py').read_text())
        self.assertEqual((self.project/'second.py').read_text(), 'second = 2\n')
        self.assertEqual(self.worker.calls, calls)
        self.assertEqual(self.controller.usage(attempt['grant']), usage)

    def test_review_evidence_tamper_invalidates_acceptance_only(self):
        for operation in fixtures.m.RECIPES['factory']:
            self.assertEqual(self.run_operation(operation)['status'], 'passed')
        assessed = self.controller.assess('accept')
        self.assertEqual(self.run_operation('accept', dict(binding=assessed['binding'], accepted=True))['status'], 'passed')
        review = self.controller.state['results']['review']
        evidence = next(name for name in review['evidence'] if name.endswith('.worker.json'))
        (self.controller.directory/evidence).write_text('{}\n')
        self.restart()
        self.assertEqual(self.controller.assess('groom')['status'], 'current')
        self.assertEqual(self.controller.assess('implement')['status'], 'current')
        self.assertEqual(self.controller.assess('verify')['status'], 'current')
        self.assertNotEqual(self.controller.assess('review')['status'], 'current')
        self.assertNotEqual(self.controller.assess('accept')['status'], 'current')


if __name__ == '__main__':
    unittest.main()
