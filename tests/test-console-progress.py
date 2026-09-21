#!/usr/bin/env python3
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('progress', Path(__file__).resolve().parents[1] / 'scripts/nightshift-console-progress.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.task = 'spec-test'
        self.common = self.root / '.git'
        self.agents = self.root / '.nightshift/agents'
        self.agents.mkdir(parents=True)
        self.console = self.common / 'nightshift/console'
        self.console.mkdir(parents=True)
        owners = self.common / 'nightshift/worktrees'
        owners.mkdir()
        (owners / (self.task + '.json')).write_text(json.dumps(dict(task=self.task, worktree=str(self.root))))
        self.started = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.identity = ('bash /scripts/nightshift-agent.sh --role nightshift-spec-writer --input /repo/docs/spec-test/input.md', self.started.astimezone().strftime('%a %b %d %H:%M:%S %Y'))

    def tearDown(self):
        self.temp.cleanup()

    def agent(self, **changes):
        value = dict(role='nightshift-spec-writer', provider='claude', model='sonnet', status='running', pid=1234, started_at=self.started.isoformat())
        value.update(changes)
        (self.agents / 'dispatch.json').write_text(json.dumps(value))

    def test_live_worker_over_historic_failure(self):
        self.agent()
        (self.agents / 'old.json').write_text(json.dumps(dict(role='nightshift-spec-writer',status='failed',started_at='2020-01-01T00:00:00Z')))
        with patch.object(m, 'process_identity', return_value=self.identity):
            result = m.progress(self.root, self.task)
        self.assertTrue(result['running'])
        self.assertEqual(result['phase'], 'spec writer')
        self.assertEqual(result['action_required'], 'None — worker active')
        self.assertNotIn('failed', result['latest_event'])

    def test_stale_pid_and_hint_not_liveness(self):
        self.agent()
        with patch.object(m, 'process_identity', return_value=('python unrelated.py', self.identity[1])):
            self.assertFalse(m.progress(self.root, self.task, running=True)['running'])
        old = (self.identity[0], 'Sun Sep 20 01:01:01 2020')
        with patch.object(m, 'process_identity', return_value=old):
            self.assertFalse(m.progress(self.root, self.task)['running'])

    def test_task_isolation(self):
        self.agent(ticket={'source_id': 'other-ticket'})
        with patch.object(m, 'process_identity', return_value=self.identity):
            self.assertEqual(m.progress(self.root, self.task)['workers'], [])
        self.agent()
        with patch.object(m, 'process_identity', return_value=(self.identity[0].replace('spec-test', 'other-task'),self.identity[1])):
            self.assertEqual(m.progress(self.root, self.task)['workers'], [])

    def test_log_only_human_message_and_safe_namespace(self):
        log = self.console / 'spec-test-attempt.log'
        log.write_text('\n'.join([json.dumps({'item':{'type':'agent_message','text':'Reviewing candidate'}}), json.dumps({'item':{'type':'command_execution','aggregated_output':'SECRET COMMAND DATA'}})]))
        result = m.progress(self.root, self.task, {'log':str(log)})
        self.assertEqual(result['latest_event'], 'Reviewing candidate')
        other = self.console / 'other-attempt.log'
        other.write_text(log.read_text())
        self.assertIsNone(m.progress(self.root, self.task, {'log':str(other)})['latest_event'])

    def test_symlink_and_oversize_refused(self):
        source = self.root / 'source'
        source.write_text('{}')
        link = self.agents / 'dispatch.json'
        link.symlink_to(source)
        self.assertEqual(m.progress(self.root, self.task)['workers'], [])
        with self.assertRaises(ValueError):
            m.safe_text(link)
        source.write_text('x'*70000)
        with self.assertRaises(ValueError):
            m.safe_text(source)


if __name__ == '__main__':
    unittest.main()
