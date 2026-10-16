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

    def test_legacy_ticket_requires_explicit_continuation_then_resumes(self):
        self.call('reserve', 'old', max_seconds=3600, now=10)
        self.call('finish', 'old', now=3607)
        path=budget.ledger_path(self.project,'test-ticket')
        legacy=json.loads(path.read_text())
        del legacy['max_wall_seconds']; del legacy['deadline_at']; del legacy['wall_clock']
        path.write_text(json.dumps(legacy))
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'Use explicit continuation'):
            self.call('reserve','plain-rerun',max_wall_seconds=600,now=4000)
        self.assertEqual(path.read_bytes(),before)
        grant=self.call('continue',continuation_seconds=600,now=4000)
        self.assertEqual(grant['active_seconds'],3597)
        self.assertEqual(grant['calls_reserved'],1)
        resumed=self.call('reserve','continued',max_wall_seconds=600,now=4001)
        self.assertTrue(resumed['allowed'])
        self.assertEqual(resumed['deadline_at'],4600)
        self.assertEqual(resumed['max_calls'],64)
        state=json.loads(path.read_text())
        self.assertEqual(state['reservations']['old'],legacy['reservations']['old'])
        self.assertEqual(len(state['continuations']),1)

    def test_wall_deadline_survives_idle_time_and_restart(self):
        self.call('reserve', 'a', max_wall_seconds=600, now=10)
        self.call('finish', 'a', now=11)
        self.assertTrue(self.call('check', now=609)['allowed'])
        self.assertEqual(self.call('reserve', 'b', now=610)['reason'], 'ticket_wall_time_budget_exhausted')
        self.assertEqual(self.call('check', now=611)['reason'], 'ticket_wall_time_budget_exhausted')

    def test_explicit_continuation_retains_usage_and_cannot_add_calls(self):
        self.call('reserve', 'a', max_seconds=5, max_calls=2, max_wall_seconds=600, now=10)
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
        self.call('reserve', 'a', max_wall_seconds=600, now=10)
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
        self.call('reserve', 'a', max_wall_seconds=600, now=10)
        self.call('finish', 'a', now=12)
        path = budget.ledger_path(self.project, 'test-ticket')
        before = path.read_bytes()
        result = budget.snapshot(self.project, 'test-ticket', now=610)
        self.assertTrue(result['exhausted'])
        self.assertEqual(result['active_seconds'], 2)
        self.assertEqual(result['wall_seconds_remaining'], 0)
        self.assertEqual(path.read_bytes(), before)

    def test_new_ticket_has_no_wall_deadline_after_idle(self):
        first = self.call('reserve', 'a', max_seconds=100, now=10)
        self.assertEqual((first['deadline_at'], first['max_wall_seconds']), (None, None))
        self.call('finish', 'a', now=20, outcome='failed')
        self.assertTrue(self.call('reserve', 'b', now=86420)['allowed'])
        result = budget.snapshot(self.project, 'test-ticket', now=86421)
        self.assertEqual(result['wall_clock'], 'none')
        self.assertIsNone(result['wall_seconds_remaining'])
        self.assertFalse(result['exhausted'])

    def test_no_wall_continuation_requires_active_exhaustion_and_retains_no_deadline(self):
        self.call('reserve', 'a', max_seconds=5, max_calls=3, now=10)
        self.call('finish', 'a', now=12, outcome='failed')
        path = budget.ledger_path(self.project, 'test-ticket')
        before = path.read_bytes()
        for revision in (None, budget.snapshot(self.project, 'test-ticket', now=13)['revision']):
            with self.assertRaisesRegex(ValueError, 'Time remains'):
                self.call('continue', continuation_seconds=600, expected_revision=revision, now=13)
            self.assertEqual(path.read_bytes(), before)
        self.call('reserve', 'b', now=14)
        self.call('finish', 'b', now=20, outcome='failed')
        grant = self.call('continue', continuation_seconds=600, now=21)
        self.assertEqual((grant['deadline_at'], grant['max_wall_seconds'], grant['max_active_seconds']), (None, None, 608))
        state = json.loads(path.read_text())
        self.assertEqual(state['reservations']['a']['outcome'], 'failed')
        self.assertEqual(state['continuations'][0]['calls_reserved'], 2)
        self.assertTrue(self.call('reserve', 'c', now=10**6)['allowed'])

    def test_environment_cannot_add_wall_deadline_to_no_wall_ticket(self):
        self.call('reserve', 'a', now=10)
        path = budget.ledger_path(self.project, 'test-ticket')
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'cannot be added'):
            self.call('reserve', 'b', max_wall_seconds=600, now=11)
        self.assertEqual(path.read_bytes(), before)

    def test_legacy_bounded_ledger_retains_deadline_without_policy_marker(self):
        self.call('reserve', 'a', max_wall_seconds=600, now=10)
        self.call('finish', 'a', now=12, outcome='failed')
        path = budget.ledger_path(self.project, 'test-ticket')
        state = json.loads(path.read_text())
        state.pop('wall_clock', None)
        path.write_text(json.dumps(state))
        self.assertEqual(self.call('reserve', 'b', now=610)['reason'], 'ticket_wall_time_budget_exhausted')
        self.assertEqual(json.loads(path.read_text())['deadline_at'], 610)

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
