#!/usr/bin/env python3
"""Independent synthetic checks for admission before supervised dispatch."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('admission_fixtures', ROOT / 'tests/test-operations.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
s = f.m.load('operation-supervisor')


class AdmissionReview(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-admission-review-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        f.fixture(self.root)
        self.worker = f.Worker()
        self.c = f.m.Operations(self.root, 'demo', self.worker)

    def grant(self):
        assessed = self.c.assess('groom-spec')
        return self.c.authorize(f.m.RECIPES['factory'], assessed['binding'],
            'synthetic-reviewer', 'admission-review', {'bounded_repair': True})['id']

    def test_exhausted_retained_ledger_blocks_before_dispatch(self):
        grant = self.grant()
        path = self.c.directory / 'groom-spec.retry.json'
        retry = f.m.load('retry-budget')
        for index in range(3):
            retry.account(path, 'retained-transport-' + str(index), 'transport')
        retained = path.read_bytes()
        result = s.run(self.c, grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.worker.calls, [])
        self.assertEqual(self.c.usage(grant)['calls'], 0)
        self.assertEqual(path.read_bytes(), retained)
        resumed = f.m.Operations(self.root, 'demo', self.worker)
        self.assertEqual(s.run(resumed, grant)['status'], 'blocked')
        self.assertEqual(self.worker.calls, [])
        self.assertEqual(path.read_bytes(), retained)

    def test_unresolved_other_request_blocks_before_dispatch(self):
        grant = self.grant()
        path = self.c.directory / 'groom-spec.retry.json'
        f.m.load('retry-budget').account(path, 'retained-unknown-invocation', 'pending')
        retained = path.read_bytes()
        result = s.run(self.c, grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.worker.calls, [])
        self.assertEqual(self.c.usage(grant)['calls'], 0)
        self.assertEqual(path.read_bytes(), retained)
        resumed = f.m.Operations(self.root, 'demo', self.worker)
        self.assertEqual(s.run(resumed, grant)['status'], 'blocked')
        self.assertEqual(self.worker.calls, [])

    def test_stale_authorization_does_not_leave_orphan_retry_reservation(self):
        grant = self.grant()
        (self.root / 'rules.md').write_text('Changed rule before execution.\n')
        self.assertEqual(s.run(self.c, grant)['status'], 'blocked')
        self.assertEqual(self.worker.calls, [])
        path = self.c.directory / 'groom-spec.retry.json'
        self.assertFalse(path.exists(), 'Refused authority must not reserve a nonexistent invocation')
        assessed = self.c.assess('groom-spec')
        fresh = self.c.authorize(f.m.RECIPES['factory'], assessed['binding'],
            'synthetic-reviewer', 'fresh-admission-review', {'bounded_repair': True})['id']
        self.assertEqual(s.run(self.c, fresh)['status'], 'passed')
        self.assertEqual(len(self.worker.calls), 4)

    def test_expired_authorization_does_not_charge_retry_ledger(self):
        grant = self.grant()
        expired = self.c.state['authorizations'][grant]['deadline'] + 1
        self.c.clock = lambda: expired
        self.assertEqual(s.run(self.c, grant)['status'], 'blocked')
        self.assertEqual(self.worker.calls, [])
        self.assertFalse((self.c.directory / 'groom-spec.retry.json').exists())

    def test_success_is_accounted_once_and_replay_is_free(self):
        grant = self.grant()
        self.assertEqual(s.run(self.c, grant)['status'], 'passed')
        self.assertEqual(len(self.worker.calls), 4)
        retained = {}
        for operation in ('groom-spec', 'groom-adversarial', 'implement', 'review'):
            path = self.c.directory / (operation + '.retry.json')
            self.assertTrue(path.is_file(), operation)
            ledger = json.loads(path.read_text())
            self.assertEqual(ledger['total'], 1, operation)
            self.assertEqual(list(ledger['attempts'].values()), ['success'], operation)
            self.assertEqual(ledger['infrastructure_failures'], 0)
            self.assertEqual(ledger['substantive_failures'], 0)
            retained[path] = path.read_bytes()
        resumed = f.m.Operations(self.root, 'demo', self.worker)
        self.assertEqual(s.run(resumed, grant)['status'], 'passed')
        self.assertEqual(len(self.worker.calls), 4)
        self.assertEqual(resumed.usage(grant)['calls'], 4)
        for path, content in retained.items():
            self.assertEqual(path.read_bytes(), content)

    def test_crash_after_execution_reconciles_own_pending_reservation(self):
        grant = self.grant()
        execute = self.c.execute

        def interrupted(*args):
            result = execute(*args)
            if args[1] == 'groom-spec':
                raise KeyboardInterrupt('synthetic crash before supervisor accounting')
            return result

        self.c.execute = interrupted
        with self.assertRaises(KeyboardInterrupt):
            s.run(self.c, grant)
        self.assertEqual(len(self.worker.calls), 1)
        path = self.c.directory / 'groom-spec.retry.json'
        self.assertTrue(path.is_file())
        pending = json.loads(path.read_text())
        self.assertEqual(list(pending['attempts'].values()), ['pending'])
        resumed = f.m.Operations(self.root, 'demo', self.worker)
        self.assertEqual(s.run(resumed, grant)['status'], 'passed')
        reconciled = json.loads(path.read_text())
        self.assertEqual(reconciled['total'], 1)
        self.assertEqual(list(reconciled['attempts'].values()), ['success'])
        self.assertEqual(list(reconciled['attempts']), list(pending['attempts']))
        self.assertEqual(sum(op == 'groom-spec' for op, _ in self.worker.calls), 1)
        self.assertEqual(len(self.worker.calls), 4)


if __name__ == '__main__':
    unittest.main()
