"""Exercise actual stream handling, failures, private logs, and precedence."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import signal
import time
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/nightshift-output.py'
spec = importlib.util.spec_from_file_location('output', SCRIPT)
output = importlib.util.module_from_spec(spec)
spec.loader.exec_module(output)


class OutputTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.launcher = self.root / 'launcher.sh'
        self.env = dict(os.environ, NIGHTSHIFT_HOME=str(self.root), NIGHTSHIFT_OUTPUT='')

    def launch(self, events, mode='concise', status=0):
        self.launcher.write_text("#!/bin/bash\ncat <<'EVENTS'\n" + '\n'.join(json.dumps(e) for e in events) +
                                 "\nEVENTS\necho 'warning: unrelated MCP unavailable' >&2\nexit " + str(status) + '\n')
        result = subprocess.run(['python3', str(SCRIPT), str(self.launcher), '--output', mode],
                                env=self.env, capture_output=True, text=True, timeout=10)
        directory = next((self.root / 'logs').iterdir())
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((directory / 'stdout.log').stat().st_mode & 0o777, 0o600)
        self.assertIn('unrelated MCP', (directory / 'stderr.log').read_text())
        return result, directory

    def test_model_free_approval_wait_is_not_an_empty_runtime_result(self):
        self.launcher.write_text("echo 'nightshift: awaiting spec approval; open the console. No model started.' >&2\n")
        result = subprocess.run(['python3', str(SCRIPT), str(self.launcher)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn('awaiting spec approval', result.stdout)
        self.assertNotIn('runtime returned no final answer', result.stderr)

    def test_codex_final_without_tool_noise(self):
        result, directory = self.launch([
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Intermediate commentary'}},
            {'type': 'item.completed', 'item': {'type': 'command_execution', 'aggregated_output': 'PRIVATE TOOL BODY'}},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Evidence says FAIL.'}}])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'Evidence says FAIL.')
        self.assertNotIn('PRIVATE TOOL BODY', result.stderr + result.stdout)
        self.assertIn('PRIVATE TOOL BODY', (directory / 'stdout.log').read_text())
        self.assertIn('diagnostic', result.stderr)

    def test_claude_quiet(self):
        result, _ = self.launch([{'type': 'result', 'result': 'Final explanation', 'is_error': False}], 'quiet')
        self.assertEqual(result.stdout.strip(), 'Final explanation')
        self.assertNotIn('working', result.stderr)
        self.assertNotIn('unrelated MCP', result.stderr)
        self.assertIn('full logs:', result.stderr)

    def test_failure_preserves_status_and_details(self):
        result, _ = self.launch([{'type': 'turn.failed', 'error': {'message': 'quota exhausted'}}], 'quiet', 75)
        self.assertEqual(result.returncode, 75)
        self.assertIn('quota exhausted', result.stderr)
        self.assertIn('run failed', result.stderr)

    def test_claude_error_result_even_exit_zero(self):
        result, _ = self.launch([{'type': 'result', 'is_error': True, 'errors': ['budget exhausted']}], 'quiet')
        self.assertEqual(result.returncode, 0)
        self.assertIn('budget exhausted', result.stderr)
        self.assertIn('run failed', result.stderr)

    def test_verbose_retains_stream(self):
        result, _ = self.launch([{'type': 'other', 'text': 'raw output'}], 'verbose')
        self.assertIn('raw output', result.stdout)
        self.assertIn('unrelated MCP', result.stderr)

    def test_claude_verbose_renders_tools_and_keeps_events(self):
        result, directory = self.launch([
            {'type': 'assistant', 'message': {'content': [
                {'type': 'text', 'text': 'Inspecting the brief'},
                {'type': 'tool_use', 'name': 'Read', 'input': {'file_path': 'brief.md'}}]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'content': '# Brief body'}]}},
            {'type': 'result', 'result': 'Finished'}], 'verbose')
        self.assertIn('Inspecting the brief', result.stdout)
        self.assertIn('[tool Read]', result.stdout)
        self.assertIn('# Brief body', result.stdout)
        self.assertIn('Finished', result.stdout)
        self.assertIn('"tool_use"', (directory / 'stdout.log').read_text())

    def test_missing_final_is_not_silent_success(self):
        result, _ = self.launch([{'type': 'thread.started'}])
        self.assertIn('no final answer', result.stderr)

    def test_interruption_preserves_signal_status(self):
        ready = self.root / 'ready'
        self.launcher.write_text('#!/bin/bash\ntouch "' + str(ready) + '"\nsleep 60\n')
        process = subprocess.Popen(['python3', str(SCRIPT), str(self.launcher), '--output', 'quiet'],
                                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(100):
                if ready.exists():
                    break
                time.sleep(0.02)
            self.assertTrue(ready.exists())
            process.send_signal(signal.SIGTERM)
            _, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 143)
            self.assertIn('full logs:', stderr)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_precedence_and_validation(self):
        project = self.root / 'project'
        project.mkdir()
        (self.root / '.nightshift.toml').write_text('[output]\nmode="verbose"\n')
        args = ['--project', str(project), 'codex', 'help']
        self.assertEqual(output.options(args, self.env)[1], 'verbose')
        (project / '.nightshift.toml').write_text('[output]\nmode="quiet"\n')
        self.assertEqual(output.options(args, self.env)[1], 'quiet')
        self.assertEqual(output.options(args, self.env | {'NIGHTSHIFT_OUTPUT': 'verbose'})[1], 'verbose')
        clean, mode, _ = output.options(args + ['--output', 'concise'], self.env | {'NIGHTSHIFT_OUTPUT': 'verbose'})
        self.assertEqual((clean, mode), (args, 'concise'))
        with self.assertRaises(ValueError):
            output.options(args + ['--output', 'bad'], self.env)
        with self.assertRaises(ValueError):
            output.options(args + ['--output'], self.env)


if __name__ == '__main__':
    unittest.main()
