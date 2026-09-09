"""Exercise interactive setup deterministically without a provider or terminal."""
import contextlib
import io
import os
from pathlib import Path
import runpy
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class SetupUX(unittest.TestCase):
    def exercise(self, path, answers, *flags):
        prompts = []
        def respond(prompt):
            prompts.append(prompt)
            return next(answers)
        with patch.object(sys, 'argv', ['setup', '--project', str(path), *flags]), \
                patch.object(sys.stdin, 'isatty', return_value=True), \
                patch('builtins.input', side_effect=respond), \
                contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(ROOT / 'scripts/nightshift-setup.py'), run_name='__main__')
        return prompts, tomllib.loads((path / '.nightshift.toml').read_text())

    def test_inferred_source_and_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            prompts, data = self.exercise(path, iter(['claude', '']), '--ticket-ref', 'spec:docs/input.md')
            self.assertEqual(len(prompts), 2)
            self.assertTrue(prompts[0].startswith('Model/runtime'))
            self.assertEqual(data['ticket_source']['provider'], 'spec')
            self.assertEqual(data['runtime']['provider'], 'claude')
            self.assertEqual(data['runtime']['auth'], 'subscription')
            self.assertEqual(data['repair_budgets']['implement'], 3)
            self.assertTrue(data['policy']['require_production_confirmation'])
            self.assertTrue((path / 'routing.json').exists())

    def test_explicit_source_and_customization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            replies = iter(['gh', 'ollama:qwen:test', 'customize', '', '', '', '', '2', '', '', '', '', '', ''])
            prompts, data = self.exercise(path, replies)
            self.assertTrue(prompts[0].startswith('Ticket source'))
            self.assertTrue(prompts[1].startswith('Model/runtime'))
            self.assertEqual(data['runtime']['model'], 'qwen:test')
            self.assertEqual(data['repair_budgets']['implement'], 2)

    def test_defaults_preserve_existing_custom_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / '.nightshift.toml').write_text('# retain\n[repair_budgets]\nimplement = 7\n')
            _, data = self.exercise(path, iter(['claude', '']), '--ticket-ref', 'gh:12')
            self.assertEqual(data['repair_budgets']['implement'], 7)
            self.assertIn('# retain', (path / '.nightshift.toml').read_text())


if __name__ == '__main__':
    unittest.main()
