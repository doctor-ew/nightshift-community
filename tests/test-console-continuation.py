"""Budget-button acceptance: retained worktrees, no-spend rejection, duplicate requests."""
import importlib.util
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('actions', ROOT / 'scripts/nightshift-console-actions.py')
actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions)
budget = actions._recovery.load('ticket-budget')


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.project), *args], text=True).strip()
        git('init', '-q'); git('config', 'user.name', 'fixture'); git('config', 'user.email', 'fixture@local')
        (self.project / 'README.md').write_text('baseline')
        git('add', '.'); git('commit', '-qm', 'baseline')
        owner = json.loads(subprocess.check_output(['bash', str(ROOT / 'scripts/nightshift-worktree.sh'),
            'prepare', '42', '--project', str(self.project)], text=True))
        self.target = Path(owner['worktree'])
        docs = self.target / 'docs/42'
        docs.mkdir(parents=True)
        (docs / 'SPEC.md').write_text('retained specification')
        subprocess.run(['git', '-C', str(self.target), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.target), 'commit', '-qm', 'retained draft'], check=True)
        # Reproduce the retained-worktree failure: config exists only at the primary.
        shutil.copy(ROOT / 'nightshift.toml', self.project / '.nightshift.toml')
        shutil.copy(ROOT / 'routing.json', self.project / 'routing.json')
        self.settings = dict(ref='gh:42', provider='codex', model='', policy='standard',
                             auth='subscription', branch='auto', base=git('rev-parse', 'HEAD'), push=False, pr=False)
        actions.save(self.project, '42', self.settings)
        budget.update(self.project, '42', 'reserve', 'original', now=10)
        budget.update(self.project, '42', 'finish', 'original', now=20)
        self.ledger = budget.ledger_path(self.project, '42')

    def click(self, displayed=None):
        current = displayed or actions.state(self.project, '42')
        return actions.action(self.project, '42', current['sha256'], 'continue',
                              budget_revision=current['budget']['revision'])

    def test_missing_worktree_manifest_grants_nothing_and_starts_no_worker(self):
        before = self.ledger.read_bytes()
        with patch.object(actions.subprocess, 'Popen', wraps=subprocess.Popen) as process:
            with self.assertRaisesRegex(ValueError, 'MANIFEST_MISSING'):
                self.click()
            self.assertFalse(any(str(actions.FACTORY) in str(call) for call in process.call_args_list))
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertFalse((actions.directory(self.project) / '42.launch.json').exists())

    def test_bad_routing_grants_nothing(self):
        for name in ('.nightshift.toml', 'routing.json'):
            shutil.copy(self.project / name, self.target / name)
        before = self.ledger.read_bytes()
        # Test the routing gate separately from the legacy dirty-worktree gate.
        real_run = subprocess.run
        def run(argv, **kwargs):
            if str(ROOT / 'scripts/nightshift-preflight-check.sh') in argv:
                return subprocess.CompletedProcess(argv, 0, '{"status":"ok"}')
            return real_run(argv, **kwargs)
        with patch.object(actions.subprocess, 'run', side_effect=run):
            (self.target / 'routing.json').write_text('{}')
            with self.assertRaises((ValueError, KeyError)):
                actions.continuation_preflight(self.project, '42', actions.state(self.project, '42'), self.settings)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_grant_preserves_history_and_duplicate_after_exit_is_rejected(self):
        displayed = actions.state(self.project, '42')
        old = json.loads(self.ledger.read_text())
        factory = Path(self.temp.name) / 'factory.sh'
        capture = Path(self.temp.name) / 'arguments'
        factory.write_text('printf "%s\\n" "$@" > "' + str(capture) + '"\nsleep 0.2\n')
        for name in ('.nightshift.toml', 'routing.json'):
            shutil.copy(self.project / name, self.target / name)
        subprocess.run(['git', '-C', str(self.target), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.target), 'commit', '-qm', 'ready configuration'], check=True)
        with patch.object(actions, 'FACTORY', factory):
            result = self.click(displayed)
            self.assertTrue(result['launched'])
            self.assertFalse(self.click(displayed)['launched'])
            for _ in range(100):
                if actions.state(self.project, '42')['launch']['status'] == 'exited':
                    break
                time.sleep(.02)
            with self.assertRaisesRegex(ValueError, 'Budget changed'):
                self.click(displayed)
        new = json.loads(self.ledger.read_text())
        self.assertEqual(new['reservations'], old['reservations'])
        self.assertEqual(new['max_calls'], old['max_calls'])
        self.assertEqual(len(new['continuations']), 1)
        self.assertIn('--provider\ncodex\n', capture.read_text())
        self.assertNotIn('--push', capture.read_text())

    def test_concurrent_ledger_grants_allow_only_one_displayed_revision(self):
        import concurrent.futures
        revision = budget.snapshot(self.project, '42')['revision']
        def grant():
            try:
                budget.update(self.project, '42', 'continue', continuation_seconds=600, expected_revision=revision)
                return True
            except ValueError:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(lambda _: grant(), range(2))), 1)
        self.assertEqual(len(json.loads(self.ledger.read_text())['continuations']), 1)

    def test_existing_allowance_cannot_be_replaced_from_browser_or_ledger(self):
        budget.update(self.project, '42', 'continue', continuation_seconds=600)
        current = actions.state(self.project, '42')
        before = self.ledger.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Time remains'):
            self.click(current)
        with self.assertRaisesRegex(ValueError, 'Time remains'):
            budget.update(self.project, '42', 'continue', continuation_seconds=600,
                          expected_revision=current['budget']['revision'])
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_controller_target_mismatch_cannot_grant(self):
        pipeline = actions._recovery.load('pipeline')
        folder = pipeline.root(self.project, '42')
        folder.mkdir(parents=True)
        (folder / 'state.json').write_text(json.dumps({'worktree':str(self.project)}))
        before = self.ledger.read_bytes()
        with self.assertRaisesRegex(ValueError, 'worktree disagree'):
            actions.continuation_preflight(self.project, '42', {}, self.settings)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_manual_acceptance_cannot_grant(self):
        before = self.ledger.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Manual acceptance'):
            actions.continuation_preflight(self.project, '42', {'pipeline':{'status':'pending_manual_acceptance'}}, self.settings)
        self.assertEqual(self.ledger.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
