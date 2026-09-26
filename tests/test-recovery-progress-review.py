#!/usr/bin/env python3
"""Read-only recorded progress projection; no provider or consumer evidence."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('progress_pipeline',ROOT/'scripts/nightshift-pipeline.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Projection(unittest.TestCase):
    def test_steps_are_bounded_metadata_and_original_failures_remain(self):
        state=dict(worktree='/synthetic',status='blocked',completed={},findings=[dict(problem='retained failure')],recovery_sessions={'binding':dict(binding='binding',authorized_at=1,status='running',next_action='adoption',steps={'verify':dict(status='pass',finished_at=2,receipt='/private/not-exposed'),'adoption':dict(status='pending',started_at=3),'injected':dict(status='pass')})})
        before=copy.deepcopy(state)
        with patch.object(m,'snapshot',side_effect=lambda *_:copy.deepcopy(state)):view=m.view('/synthetic','task')
        self.assertEqual(state,before);self.assertEqual(view['status'],'blocked');self.assertEqual(view['findings'],state['findings'])
        self.assertEqual(set(view['recovery_status']['steps']),{'verify','adoption'})
        self.assertNotIn('receipt',view['recovery_status']['steps']['verify'])
        self.assertNotIn('running',view)
    def test_stale_stage_evidence_stays_stale_with_recorded_running_recovery(self):
        state=dict(worktree='/synthetic',status='blocked',completed={'product':dict(receipt='/nonexistent/synthetic-receipt',sha256='missing')},recovery_sessions={'binding':dict(authorized_at=1,status='running',steps={})})
        with patch.object(m,'snapshot',return_value=state):view=m.view('/synthetic','task')
        self.assertEqual(view['status'],'stale');self.assertEqual(view['recovery_status']['status'],'running')
if __name__=='__main__':unittest.main()
