#!/usr/bin/env python3
"""Branchless controller visibility does not grant console mutation authority."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('read_only_actions', ROOT / 'scripts/nightshift-console-actions.py')
actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions)


def fixture(project):
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    settings = dict(ref='spec:brief.md', provider='codex', model='', policy='standard', auth='subscription', branch='none', base='HEAD', push=False, pr=False)
    actions.save(project, 'demo', settings)
    directory = project / '.git/nightshift/pipeline/demo'
    directory.mkdir(parents=True)
    (directory / 'state.json').write_text(json.dumps(dict(version=1, task='demo', worktree=str(project), status='blocked', next_action='product', completed={}, findings=[dict(target='product', problem='Synthetic transport failed')], attempts=[dict(stage='product', status='fail', category='infrastructure', reason='worker_exit_75', receipt=str(project / 'receipt.json'), route=dict(provider='codex', model='synthetic-model'))], retry_budgets={}, decisions=[], final_evidence={})))
    return settings


class ReadOnlyTickets(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()

    def test_saved_branchless_controller_is_visible_with_retained_evidence(self):
        settings = fixture(self.project)
        rows = actions.list_tickets(self.project)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['settings'], settings)
        self.assertTrue(row['read_only'])
        self.assertIn('terminal', row['resume_hint'])
        self.assertEqual(row['pipeline']['next_action'], 'product')
        self.assertEqual(row['pipeline']['attempts'][0]['route']['model'], 'synthetic-model')
        before = {str(path): path.read_bytes() for path in (self.project / '.git/nightshift').rglob('*.json')}
        for operation in ('resume', 'repair', 'continue', 'cleanup', 'approve', 'stop'):
            with self.subTest(operation=operation), patch.object(actions.subprocess, 'Popen', wraps=subprocess.Popen) as process:
                with self.assertRaisesRegex(ValueError, 'resume from the terminal'):
                    actions.action(self.project, 'demo', row['sha256'], operation)
                self.assertFalse(any(str(actions.FACTORY) in str(call) for call in process.call_args_list))
        for operation in ('recovery-assess', 'recovery-authorize', 'recovery-resume', 'recovery-accept'):
            with self.assertRaisesRegex(ValueError, 'resume from the terminal'):
                actions.recovery_action(self.project, 'demo', row['sha256'], operation)
        after = {str(path): path.read_bytes() for path in (self.project / '.git/nightshift').rglob('*.json')}
        self.assertEqual(before, after)
        self.assertFalse((self.project / '.git/nightshift/console/demo.lock').exists())

    def test_branchless_publication_is_rejected_and_auto_policy_is_unchanged(self):
        settings = fixture(self.project)
        for publication in (dict(push=True), dict(push=True, pr=True)):
            with self.assertRaisesRegex(ValueError, 'Invalid saved run policy'):
                actions.save(self.project, 'demo', dict(settings, **publication))
        actions.save(self.project, 'auto', dict(settings, branch='auto'))
        row = actions.state(self.project, 'auto')
        self.assertFalse(row['read_only'])


if __name__ == '__main__':
    unittest.main()
