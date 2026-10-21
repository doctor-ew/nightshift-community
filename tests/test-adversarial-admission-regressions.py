#!/usr/bin/env python3
"""Reproduce invalid launch charging and missing repair-contract dependencies."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


retry = load('admission_retry', 'scripts/nightshift-retry-budget.py')
pipeline = load('admission_pipeline', 'scripts/nightshift-pipeline.py')
fixture = load('admission_fixture', 'tests/nightshift-behavior-fixture.py')


class InvalidInvocation(unittest.TestCase):
    def test_invalid_routing_options_never_reserve_or_launch(self):
        invalid = [('--attempt', '4'), ('--attempt', '0'), ('--attempt', '-1'),
                   ('--gear', '5'), ('--gear', 'invalid'), ('--risk', 'invalid'),
                   ('--auth', 'invalid'), ('--attempt',),
                   ('--attempt', '1', '--attempt', '2')]
        for options in invalid:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                output = directory / 'report.json'
                output.write_text('retained report')
                args = ['nightshift-code-fact-extractor', '--out', str(output),
                        '--adversarial', *options]
                with patch.object(retry.subprocess, 'run') as provider:
                    with self.assertRaises(ValueError):
                        retry.run_dispatch(args)
                provider.assert_not_called()
                self.assertFalse((directory / '.adversarial-budget.json').exists())
                self.assertEqual(output.read_text(), 'retained report')


class RepairContractInputs(unittest.TestCase):
    def test_repaired_contract_and_registered_evidence_change_only_adversarial_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve() / 'project'
            fixture.prepare(ROOT, project, task='sample', manual=True, final=True)
            settings = dict(ref='jira:sample', provider='codex', model='gpt-6-sol',
                            policy='standard', auth='subscription')
            with patch.dict(os.environ, NIGHTSHIFT_ROUTING_FILE=str(ROOT / 'routing.json')):
                controller = pipeline.Pipeline(project, 'sample', settings)
                self.assertTrue(controller.refresh())
                before_product = pipeline.inputs(project, 'sample', 'product', controller.state)
                before_review = pipeline.inputs(project, 'sample', 'adversarial', controller.state)
                directory = project / 'docs/sample'
                (directory / 'before.json').write_text('{"value":"old"}')
                (directory / 'current.json').write_text('{"value":"fixed"}')
                manifest = directory / 'repair-checks.json'
                manifest.write_text(json.dumps(dict(schema_version=1, findings=[dict(
                    id='source-description', artifact='docs/sample/current.json',
                    prior_artifact='docs/sample/before.json', pointer='/value',
                    expected='fixed', prior_sha256=pipeline.sha(directory / 'before.json'))])))
                registered = pipeline.inputs(project, 'sample', 'adversarial', controller.state)
                self.assertNotEqual(registered, before_review)
                self.assertEqual(pipeline.inputs(project, 'sample', 'product', controller.state), before_product)
                # Generated receipts are outputs; they cannot invalidate themselves.
                (directory / 'repair-check.receipt.json').write_text('{"status":"passed"}')
                self.assertEqual(pipeline.inputs(project, 'sample', 'adversarial', controller.state), registered)
                (directory / 'current.json').write_text('{"value":"fixed","boundary":"new"}')
                self.assertNotEqual(pipeline.inputs(project, 'sample', 'adversarial', controller.state), registered)
                self.assertEqual(pipeline.inputs(project, 'sample', 'product', controller.state), before_product)
                data = json.loads(manifest.read_text())
                data['findings'][0]['artifact'] = '../outside.json'
                manifest.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    pipeline.inputs(project, 'sample', 'adversarial', controller.state)


class StagePause(unittest.TestCase):
    def test_pause_is_before_implementation_and_resume_preserves_passed_planning(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve() / 'project'
            fixture.prepare(ROOT, project, task='sample', manual=True, final=True)
            settings = dict(ref='jira:sample', provider='codex', model='gpt-6-sol',
                            policy='standard', auth='subscription', stop_before='implement')
            calls = []
            allow_implementation = False

            def runner(stage, handoff, receipt):
                if stage == 'implement' and not allow_implementation:
                    self.fail('Implementation dispatched before the presentation boundary')
                calls.append(stage)
                if stage == 'review':
                    return 1  # Retain an interrupted later stage for the boundary check below.
                checked = subprocess.run(['python3', 'tests/test_fixture_sample.py'],
                                         cwd=project, capture_output=True, text=True, check=True)
                log = project / 'docs/sample' / (stage + '.log')
                log.write_text(checked.stdout + checked.stderr)
                receipt.write_text(json.dumps(dict(version=1, task='sample', stage=stage,
                    status='pass', findings=[], checks=[dict(command='python3 tests/test_fixture_sample.py', exit_code=0)],
                    evidence=[dict(path=str(log.relative_to(project)), sha256=pipeline.sha(log))])))
                return 0

            with patch.dict(os.environ, NIGHTSHIFT_ROUTING_FILE=str(ROOT / 'routing.json')):
                controller = pipeline.Pipeline(project, 'sample', settings, runner)
                self.assertEqual(controller.run(), 0)
                self.assertEqual(controller.state['status'], 'paused')
                self.assertEqual(controller.state['next_action'], 'implement')
                self.assertEqual(calls, ['adversarial'])
                self.assertEqual(set(controller.state['completed']), {'product', 'adversarial'})
                planning = dict(controller.state['completed'])
                self.assertEqual(pipeline.Pipeline(project, 'sample', settings, runner).run(), 0)
                self.assertEqual(calls, ['adversarial'])
                allow_implementation = True
                resumed = pipeline.Pipeline(project, 'sample', {k: v for k, v in settings.items()
                                                              if k != 'stop_before'}, runner)
                resumed.run()
                self.assertEqual(calls[:2], ['adversarial', 'implement'])
                self.assertEqual({k: resumed.state['completed'][k] for k in planning}, planning)
                before = list(calls)
                repeated = pipeline.Pipeline(project, 'sample', settings, runner)
                self.assertEqual(repeated.run(), 0)
                self.assertEqual(calls, before)
                self.assertEqual(repeated.state['status'], 'paused')
                self.assertEqual(repeated.state['next_action'], 'review')


if __name__ == '__main__':
    unittest.main()
