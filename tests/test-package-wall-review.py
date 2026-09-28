#!/usr/bin/env python3
"""Independent synthetic-clock checks for cumulative preparation wall allowances."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('wall_review_fixtures', Path(__file__).with_name('test-package-controller-review.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m


class WallReview(unittest.TestCase):
    def setUp(self):
        f.PackageControllerReview.setUp(self)
        self.now = 1000.0
        self.clock = lambda: self.now
        self.c = m.Packages(self.root, 'demo', self.worker, self.clock)

    def grant(self, request='wall-prepare'):
        assessed = self.c.preparation.assess('groom-spec')
        return self.c.preparation.authorize(m.ops.RECIPES['groom'], assessed['binding'],
            'synthetic', request)['id']

    def prepare_with_validation_time(self, seconds):
        grant = self.grant()
        validate = m.contracts.validate
        def measured(*args, **kwargs):
            result = validate(*args, **kwargs)
            self.now += seconds
            return result
        with patch.object(m.contracts, 'validate', side_effect=measured):
            result = self.c.prepare(grant)
        self.assertEqual(result['status'], 'ready', result)
        return grant, result

    def test_standalone_groom_cannot_acquire_zero_duration_wall_receipt(self):
        grant = self.grant()
        worker = self.worker
        def measured(*args):
            self.now += 10
            return worker(*args)
        self.c.preparation.worker = measured
        self.c.preparation.chain(grant)
        self.assertEqual(self.now, 1020)
        self.assertEqual(self.c.assess()['status'], 'ready')
        retained = self.c.preparation.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'unmeasured_preparation_wall_requires_reconciliation'):
            self.c.prepare(grant)
        self.assertEqual(len(self.worker.calls), 2)
        self.assertEqual(self.c.preparation.path.read_bytes(), retained)
        self.assertFalse(self.c.state.get('preparations'))
        self.assertFalse(self.c.state['authorizations'])

    def test_old_receipt_cannot_cover_new_standalone_groom_evidence(self):
        original, _ = self.prepare_with_validation_time(2)
        (self.root/'rules.md').write_text('Synthetic changed rule requires fresh preparation.\n')
        grant = self.grant('standalone-new-groom')
        self.c.preparation.chain(grant)
        current = self.c.assess()
        self.assertEqual(current['status'], 'ready')
        calls = list(self.worker.calls)
        with self.subTest(boundary='cached phase replay'):
            self.assertEqual(self.c.prepare(original)['status'], 'blocked')
        with self.subTest(boundary='new composition authority'):
            with self.assertRaisesRegex(ValueError, 'preparation_wall_receipt_not_current'):
                self.c.authorize(current['binding'], 'synthetic', 'compose')
        self.assertEqual(self.worker.calls, calls)
        self.assertFalse(self.c.state['authorizations'])

    def test_post_authorization_unmeasured_work_blocks_child_dispatch(self):
        _, ready = self.prepare_with_validation_time(0)
        grant = self.c.authorize(ready['binding'], 'synthetic', 'compose')
        prep = self.c.preparation
        assessed = prep.assess('implement')
        standalone = prep.authorize(['implement'], assessed['binding'], 'synthetic', 'standalone-implement')
        self.assertEqual(prep.execute(standalone['id'], 'implement', 'standalone-implement-run')['status'], 'passed')
        self.assertEqual(self.c.assess()['binding'], grant['binding'])
        retained = prep.path.read_bytes()
        with patch.object(self.c, 'materialize', side_effect=AssertionError('Unmeasured preparation must block before child dispatch')):
            result = self.c.run(grant['id'])
        self.assertEqual(result['status'], 'blocked', result)
        self.assertEqual(result['usage']['calls'], 3)
        self.assertEqual(len(self.worker.calls), 3)
        self.assertEqual(prep.path.read_bytes(), retained)
        self.assertFalse(self.c.state['children'])

    def test_validation_time_is_charged_and_reduces_composition_deadline(self):
        grant, result = self.prepare_with_validation_time(7)
        phase = self.c.state['preparations'][grant]
        self.assertEqual(phase['elapsed_seconds'], 14)
        composition = self.c.authorize(result['binding'], 'synthetic', 'compose')
        self.assertEqual(composition['preparation_wall']['elapsed_seconds'], 14)
        self.assertEqual(composition['deadline'], self.now + 240 - 14)
        self.assertLess(sum(row['seconds'] for row in self.c.preparation.state['calls'].values()), 1)

    def test_cached_idle_does_not_charge_preparation_again(self):
        grant, result = self.prepare_with_validation_time(3)
        before = json.loads(json.dumps(self.c.state['preparations']))
        calls = list(self.worker.calls)
        self.now += 10000
        resumed = m.Packages(self.root, 'demo', self.worker, self.clock)
        replay = resumed.prepare(grant)
        self.assertEqual(replay['status'], 'ready')
        self.assertEqual(resumed.state['preparations'], before)
        self.assertEqual(self.worker.calls, calls)
        composition = resumed.authorize(replay['binding'], 'synthetic', 'compose')
        self.assertEqual(composition['deadline'], self.now + 234)

    def test_crash_retains_unknown_reservation_and_resumes_original_phase(self):
        grant = self.grant()
        started = self.now
        def interrupted(_):
            self.now += 5
            raise KeyboardInterrupt('synthetic preparation crash')
        with patch.object(self.c, '_prepare', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.c.prepare(grant)
        retained = json.loads(json.dumps(self.c.state['preparations'][grant]))
        self.assertEqual(self.c.preparation_wall()['unknown_phases'], 1)
        self.assertEqual(self.c.preparation_wall()['reserved_seconds'], 240)
        self.now += 10
        resumed = m.Packages(self.root, 'demo', self.worker, self.clock)
        self.assertEqual(resumed.prepare(grant)['status'], 'ready')
        phase = resumed.state['preparations'][grant]
        self.assertEqual(phase['started'], started)
        self.assertEqual(phase['deadline'], retained['deadline'])
        self.assertEqual(phase['elapsed_seconds'], 15)
        self.assertEqual(resumed.preparation_wall()['unknown_phases'], 0)
        self.assertEqual(len(self.worker.calls), 2)

    def test_expired_crashed_phase_cannot_refresh_deadline(self):
        grant = self.grant()
        with patch.object(self.c, '_prepare', side_effect=KeyboardInterrupt('synthetic crash')):
            with self.assertRaises(KeyboardInterrupt):
                self.c.prepare(grant)
        deadline = self.c.state['preparations'][grant]['deadline']
        self.now = deadline + 1
        resumed = m.Packages(self.root, 'demo', self.worker, self.clock)
        with self.assertRaisesRegex(ValueError, 'parent_preparation_wall_exhausted'):
            resumed.prepare(grant)
        self.assertEqual(self.worker.calls, [])
        self.assertEqual(resumed.state['preparations'][grant]['deadline'], deadline)
        self.assertGreaterEqual(resumed.preparation_wall()['elapsed_seconds'], deadline - 1000)

    def test_duplicate_composition_authorization_does_not_refresh_deadline(self):
        _, result = self.prepare_with_validation_time(2)
        initial = self.c.authorize(result['binding'], 'synthetic', 'first-click')
        deadline = initial['deadline']
        self.now += 30
        resumed = m.Packages(self.root, 'demo', self.worker, self.clock)
        repeated = resumed.authorize(result['binding'], 'synthetic', 'second-click')
        self.assertEqual(repeated['id'], initial['id'])
        self.assertEqual(repeated['deadline'], deadline)
        self.assertEqual(len(resumed.state['authorizations']), 1)

    def test_children_cannot_reserve_wall_already_spent_in_preparation(self):
        _, result = self.prepare_with_validation_time(31)
        self.assertEqual(self.c.preparation_wall()['elapsed_seconds'], 62)
        with self.assertRaisesRegex(ValueError, 'parent_wall_allocation_insufficient_after_preparation'):
            self.c.authorize(result['binding'], 'synthetic', 'compose')
        self.assertEqual(len(self.worker.calls), 2)
        self.assertFalse(self.c.state['children'])
        self.assertFalse(self.c.state['authorizations'])


if __name__ == '__main__':
    unittest.main()
