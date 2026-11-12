#!/usr/bin/env python3
"""Offline routing persistence checks; no provider or factory execution."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('routing_resume_pipeline', ROOT/'scripts/nightshift-pipeline.py')
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class RoutingResume(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-routing-resume-')
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.console = pipeline.load('console-actions')
        self.settings = dict(ref='gh:fixture/repository#154', provider='codex', model='fixture',
                             policy='standard', auth='subscription', branch='none', base='',
                             push=False, pr=False)

    def save(self, **values):
        self.console.save(self.project, '154', dict(self.settings, **values))

    def test_legacy_defaults_and_explicit_reselection(self):
        self.save()
        legacy = pipeline.retained_stage_routing(self.project, '154', self.settings)
        self.assertEqual((legacy['gear'], legacy['risk']), ('auto', 'standard'))
        self.save(gear='4', risk='high')
        implicit = dict(self.settings, gear='auto', risk='standard',
                        gear_explicit=False, risk_explicit=False)
        retained = pipeline.retained_stage_routing(self.project, '154', implicit)
        self.assertEqual((retained['gear'], retained['risk']), ('4', 'high'))
        self.assertNotIn('gear_explicit', retained)
        changed = pipeline.retained_stage_routing(self.project, '154',
                    dict(implicit, gear='2', risk='low', gear_explicit=True, risk_explicit=True))
        self.assertEqual((changed['gear'], changed['risk']), ('2', 'low'))
        for gear, risk in [('5', 'high'), ('4', 'unknown'), (4, 'high')]:
            with self.subTest(gear=gear, risk=risk), self.assertRaises(ValueError):
                pipeline.retained_stage_routing(self.project, '154', dict(self.settings, gear=gear, risk=risk))

    def test_terminal_resume_command_replays_saved_selections(self):
        self.save(gear='4', risk='high')
        report = pipeline.inspect_recovery(self.project, '154', str(ROOT/'scripts/nightshift-factory.sh'))
        argv = shlex.split(report['resume_command'])
        self.assertEqual(argv[argv.index('--gear')+1], '4')
        self.assertEqual(argv[argv.index('--risk')+1], 'high')
        self.assertEqual(argv[argv.index('--auth')+1], 'subscription')

    def test_implicit_console_resume_resolves_before_saving(self):
        self.save(gear='4', risk='high')
        incoming = dict(self.settings, gear='auto', risk='standard', gear_explicit=False, risk_explicit=False)
        argv = ['pipeline', '--project', str(self.project), '--task', '154', '--settings', json.dumps(incoming)]
        with patch.object(sys, 'argv', argv), patch.object(pipeline, 'prepare', return_value=self.project), patch.object(pipeline, 'Pipeline') as controller:
            controller.return_value.run.return_value = 0
            controller.return_value.state = {}
            self.assertEqual(pipeline.main(), 0)
            actual = controller.call_args.args[2]
            self.assertEqual((actual['gear'], actual['risk']), ('4', 'high'))
        saved = self.console.read(self.console.directory(self.project)/'154.json')['settings']
        self.assertEqual((saved['gear'], saved['risk']), ('4', 'high'))

    def test_worker_dispatch_explicitly_passes_pinned_routing(self):
        self.save(gear='4', risk='high')
        controller = pipeline.Pipeline(self.project, '154', self.settings)
        controller.state['plan'] = dict(stages={'product': dict(provider='codex', model='fixture')},
                                       policy='standard', routing_path=str(ROOT/'routing.json'))
        receipt = controller.directory/'routing-check.json'
        handoff = controller.directory/'routing-check.handoff.json'; handoff.write_text('{}')
        original = subprocess.Popen
        worker = MagicMock(); worker.wait.return_value = 0
        observed = []
        def spawn(argv, *args, **kwargs):
            if argv[:2] == ['bash', str(ROOT/'scripts/nightshift-factory.sh')]:
                observed.append(argv)
                return worker
            return original(argv, *args, **kwargs)
        with patch.object(pipeline.subprocess, 'Popen', side_effect=spawn):
            self.assertEqual(controller.dispatch('product', handoff, receipt), 0)
        argv = observed[0]
        self.assertEqual(argv[argv.index('--gear')+1], '4')
        self.assertEqual(argv[argv.index('--risk')+1], 'high')


if __name__ == '__main__':
    unittest.main()
