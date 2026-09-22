#!/usr/bin/env python3
"""Isolated ownership/CLI regression tests; no provider calls."""
from datetime import datetime, timezone
import fcntl
import threading
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/nightshift-console-lease.py'
spec = importlib.util.spec_from_file_location('lease', SCRIPT)
lease = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lease)


class Leases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.state = lease.directory(self.project)
        self.state.mkdir(parents=True)

    def command(self):
        return ['python3', str(SCRIPT), '--project', str(self.project), '--task', 'child', '--', 'python3', '-c', "from pathlib import Path; Path('MUTATED').touch()"]

    def test_exclusion_and_release_before_resume(self):
        with lease.Lease(self.project, 'child', 'parent', self.project):
            self.assertEqual(lease.active(self.project, 'child')['owner_parent'], 'parent')
            result = subprocess.run(self.command(), cwd=self.project, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.project / 'MUTATED').exists())
        self.assertIsNone(lease.active(self.project, 'child'))
        self.assertEqual(json.loads((self.state / 'child.repair-lease.json').read_text())['status'], 'finished')
        self.assertEqual(subprocess.run(self.command(), cwd=self.project).returncode, 0)

    def test_failed_worker_releases(self):
        with self.assertRaises(RuntimeError):
            with lease.Lease(self.project, 'child', 'parent', self.project):
                raise RuntimeError('verification failed')
        with lease.Lease(self.project, 'child', 'parent', self.project):
            self.assertIsNotNone(lease.active(self.project, 'child'))

    def test_reused_pid_is_not_live_lease(self):
        record = dict(task='child', status='running', pid=os.getpid(), started_identity='old process')
        lease.atomic(self.state / 'child.repair-lease.json', record)
        self.assertIsNone(lease.active(self.project, 'child'))
        with lease.Lease(self.project, 'child', 'parent', self.project):
            self.assertIsNotNone(lease.active(self.project, 'child'))

    def test_active_console_worker_rejected_before_mutation(self):
        process = subprocess.Popen(['sleep', '30'])
        self.addCleanup(process.wait)
        self.addCleanup(process.terminate)
        lease.atomic(self.state / 'child.launch.json', dict(status='running', pid=process.pid, started_identity=lease.identity(process.pid)))
        with self.assertRaisesRegex(ValueError, 'active console worker'):
            with lease.Lease(self.project, 'child', 'parent', self.project):
                self.fail('entered mutation region')
        self.assertFalse((self.state / 'child.repair-lease.json').exists())

    def canonical_process(self):
        script = self.project / 'nightshift-factory.sh'
        script.write_text('read -r ignored\n')
        process = subprocess.Popen(['bash', str(script)], stdin=subprocess.PIPE)
        self.addCleanup(process.stdin.close)
        self.addCleanup(process.wait)
        self.addCleanup(process.terminate)
        return process

    def canonical_record(self, process, started=None):
        return dict(status='running', role='nightshift-factory', ticket=dict(source_id='child'),
                    pid=process.pid, started_at=started or datetime.now(timezone.utc).isoformat())

    def write_canonical(self, record):
        agents = self.project / '.nightshift/agents'
        agents.mkdir(parents=True, exist_ok=True)
        lease.atomic(agents / 'factory-1.json', record)

    def test_canonical_worker_rejected(self):
        process = self.canonical_process()
        self.write_canonical(self.canonical_record(process))
        with self.assertRaisesRegex(ValueError, 'canonical worker'):
            lease.Lease(self.project, 'child', 'parent', self.project).acquire()

    def test_stale_canonical_pid_reused_by_unrelated_process(self):
        process = subprocess.Popen(['sleep', '30'])
        self.addCleanup(process.wait)
        self.addCleanup(process.terminate)
        # Even a timestamp in the same second cannot make sleep a factory.
        self.write_canonical(self.canonical_record(process))
        with lease.Lease(self.project, 'child', 'parent', self.project):
            self.assertIsNotNone(lease.active(self.project, 'child'))

    def test_stale_canonical_pid_reused_by_new_factory(self):
        process = self.canonical_process()
        self.write_canonical(self.canonical_record(process, '2000-01-01T00:00:00Z'))
        with lease.Lease(self.project, 'child', 'parent', self.project):
            self.assertIsNotNone(lease.active(self.project, 'child'))

    def test_launch_startup_lock_handoff(self):
        with (self.state / 'child.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            timer = threading.Timer(.15, lambda: fcntl.flock(lock, fcntl.LOCK_UN))
            timer.start()
            try:
                with lease.Lease(self.project, 'child', 'parent', self.project):
                    self.assertIsNotNone(lease.active(self.project, 'child'))
            finally:
                timer.join()

    def test_reused_console_pid_does_not_block(self):
        lease.atomic(self.state / 'child.launch.json', dict(status='running', pid=os.getpid(), started_identity='old process'))
        with lease.Lease(self.project, 'child', 'parent', self.project):
            self.assertIsNotNone(lease.active(self.project, 'child'))

    def test_actual_prepare_rejects_lease_without_worktree_changes(self):
        with lease.Lease(self.project, 'child', 'parent', self.project):
            run = subprocess.run(['bash', str(SCRIPT.with_name('nightshift-worktree.sh')), 'prepare', 'child', '--project', str(self.project)], capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('busy', run.stderr)
        self.assertFalse((self.state.parent / 'worktrees').exists())


if __name__ == '__main__':
    unittest.main()
