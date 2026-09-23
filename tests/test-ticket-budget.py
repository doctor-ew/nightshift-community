#!/usr/bin/env python3
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/nightshift-ticket-budget.py'
spec = importlib.util.spec_from_file_location('budget', SCRIPT)
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        subprocess.run(['git', 'init', '-q', self.project], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def call(self, operation, invocation='', **kw):
        return budget.update(self.project, 'test-ticket', operation, invocation, **kw)

    def test_reservations_are_idempotent_but_duplicate_launch_denied(self):
        self.assertTrue(self.call('reserve', 'a', now=10)['allowed'])
        duplicate = self.call('reserve', 'a', now=11)
        self.assertFalse(duplicate['allowed'])
        self.assertEqual(duplicate['calls_reserved'], 1)

    def test_calls_shared_across_finish_and_restart(self):
        self.call('reserve', 'a', max_calls=1, now=10)
        self.call('finish', 'a', now=12, outcome='failed')
        result = self.call('reserve', 'b', now=100)
        self.assertEqual(result['reason'], 'ticket_call_budget_exhausted')
        self.assertEqual(result['active_seconds'], 2)

    def test_time_is_active_not_blocked_wall_time(self):
        self.call('reserve', 'a', max_seconds=5, max_wall_seconds=20000, now=10)
        self.call('finish', 'a', now=12)
        self.assertTrue(self.call('reserve', 'b', now=10000)['allowed'])
        self.assertTrue(self.call('check', now=10002)['allowed'])
        self.assertFalse(self.call('check', now=10003)['allowed'])

    def test_wall_deadline_survives_idle_time_and_restart(self):
        self.call('reserve', 'a', now=10)
        self.call('finish', 'a', now=11)
        self.assertTrue(self.call('check', now=609)['allowed'])
        self.assertEqual(self.call('reserve', 'b', now=610)['reason'], 'ticket_wall_time_budget_exhausted')
        self.assertEqual(self.call('check', now=611)['reason'], 'ticket_wall_time_budget_exhausted')

    def test_explicit_continuation_retains_usage_and_cannot_add_calls(self):
        self.call('reserve', 'a', max_seconds=5, max_calls=2, now=10)
        with self.assertRaises(ValueError):
            self.call('continue', continuation_seconds=600, now=11)
        self.call('finish', 'a', now=15)
        result = self.call('continue', continuation_seconds=600, now=1000)
        self.assertEqual(result['active_seconds'], 5)
        self.assertEqual(result['calls_reserved'], 1)
        self.assertEqual(result['max_active_seconds'], 605)
        self.assertEqual(result['deadline_at'], 1600)
        self.call('reserve', 'b', now=1001)
        self.call('finish', 'b', now=1002)
        with self.assertRaises(ValueError):
            self.call('continue', continuation_seconds=600, now=1003)
        state = json.loads(budget.ledger_path(self.project, 'test-ticket').read_text())
        self.assertEqual(len(state['continuations']), 1)
        self.assertEqual(len(state['reservations']), 2)

    def test_oversized_continuation_and_changed_deadline_fail_closed(self):
        self.call('reserve', 'a', now=10)
        self.call('finish', 'a', now=11)
        with self.assertRaises(ValueError):
            self.call('continue', continuation_seconds=601, now=12)
        with self.assertRaises(ValueError):
            self.call('reserve', 'b', max_wall_seconds=601, now=12)

    def test_unfinished_reservations_remain_charged(self):
        self.call('reserve', 'a', max_seconds=5, now=10)
        self.assertFalse(self.call('reserve', 'b', now=16)['allowed'])

    def test_pinned_limits_and_no_historical_claim(self):
        result = self.call('reserve', 'a', max_calls=2)
        self.assertEqual(result['historical_usage'], 'unknown')
        self.assertEqual(result['coverage'], 'instrumented-dispatches-only')
        with self.assertRaises(ValueError):
            self.call('reserve', 'b', max_calls=3)

    def test_invalid_limits_and_corruption_fail_closed(self):
        with self.assertRaises(ValueError):
            self.call('reserve', 'a', max_calls=0)
        self.call('reserve', 'a')
        budget.ledger_path(self.project, 'test-ticket').write_text('{broken')
        with self.assertRaises(ValueError):
            self.call('reserve', 'b')

    def test_finished_is_idempotent(self):
        self.call('reserve', 'a', now=1)
        self.call('finish', 'a', now=2)
        self.assertEqual(self.call('finish', 'a', now=99)['active_seconds'], 1)

    def test_concurrent_reservations_cannot_overspend(self):
        def reserve(i):
            return subprocess.run(['python3', str(SCRIPT), 'reserve', '--project', str(self.project),
                                   '--task', 'test-ticket', '--invocation', str(i), '--max-calls', '3'],
                                  capture_output=True, text=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(8)))
        self.assertEqual(sum(r.returncode == 0 for r in results), 3)
        state = json.loads(budget.ledger_path(self.project, 'test-ticket').read_text())
        self.assertEqual(len(state['reservations']), 3)

    def test_snapshot_is_read_only_and_reports_deadline(self):
        self.assertIsNone(budget.snapshot(self.project, 'test-ticket', now=10))
        self.call('reserve', 'a', now=10)
        self.call('finish', 'a', now=12)
        path = budget.ledger_path(self.project, 'test-ticket')
        before = path.read_bytes()
        result = budget.snapshot(self.project, 'test-ticket', now=610)
        self.assertTrue(result['exhausted'])
        self.assertEqual(result['active_seconds'], 2)
        self.assertEqual(result['wall_seconds_remaining'], 0)
        self.assertEqual(path.read_bytes(), before)

    def test_same_common_git_shares_budget(self):
        subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                        'commit', '--allow-empty', '-qm', 'fixture'], check=True)
        worktree = self.project / 'child'
        subprocess.run(['git', '-C', str(self.project), 'worktree', 'add', '-qb', 'child', str(worktree)], check=True)
        self.call('reserve', 'a', max_calls=1)
        result = budget.update(worktree, 'test-ticket', 'reserve', 'b')
        self.assertFalse(result['allowed'])


if __name__ == '__main__':
    unittest.main()
