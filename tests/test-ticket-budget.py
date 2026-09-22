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
        self.call('reserve', 'a', max_seconds=5, now=10)
        self.call('finish', 'a', now=12)
        self.assertTrue(self.call('reserve', 'b', now=10000)['allowed'])
        self.assertTrue(self.call('check', now=10002)['allowed'])
        self.assertFalse(self.call('check', now=10003)['allowed'])

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
