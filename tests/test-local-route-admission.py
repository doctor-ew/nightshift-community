#!/usr/bin/env python3
"""Synthetic local inventory admission; never generate provider output."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LocalAdmission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nightshift-local-admission-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'; self.bin.mkdir()
        for tool in ('bash', 'dirname', 'python3', 'jq', 'git'):
            (self.bin / tool).symlink_to(shutil.which(tool))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('NIGHTSHIFT_')}
        self.env.update(PATH=str(self.bin), HOME=str(self.root), NIGHTSHIFT_HOME=str(self.root),
                        NIGHTSHIFT_PROJECT_DIR=str(self.root), NIGHTSHIFT_ROUTING_FILE=str(ROOT / 'routing.json'))
        self.provider('codex', 'exit 99')

    def provider(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/bash\n' + body + '\n'); path.chmod(0o700)

    def route(self, mode='auto', **extra):
        return subprocess.run(['/bin/bash', str(ROOT / 'scripts/nightshift-route.sh'),
                               'nightshift-code-fact-extractor', 'low', '1', 'false', mode],
                              env=dict(self.env, **extra), text=True, capture_output=True, timeout=8)

    def test_missing_local_promotes_with_reason(self):
        result = self.route(); self.assertEqual(result.returncode, 0, result.stderr)
        route = json.loads(result.stdout)
        self.assertEqual((route['gear'], route['provider']), (1, 'codex'))
        self.assertIn('local model unavailable', route['reason'])
        self.assertFalse((self.root / 'capabilities').exists())

    def test_inventory_exact_model_and_missing_model(self):
        self.provider('ollama', '[[ "$*" == list ]] || exit 99\nprintf "NAME ID SIZE MODIFIED\\nqwen2.5-coder:14b fixture 9GB now\\n"')
        route = json.loads(self.route().stdout)
        self.assertEqual((route['gear'], route['provider']), (0, 'local'))
        self.assertEqual(json.loads(self.route(NIGHTSHIFT_LOCAL_MODEL='qwen2.5-coder:7b').stdout)['gear'], 1)

    def test_explicit_unavailable_fails(self):
        result = self.route('explicit')
        self.assertEqual(result.returncode, 64)
        self.assertIn('local model unavailable', result.stderr)

    def test_failed_inventory_promotes(self):
        self.provider('ollama', 'exit 1')
        self.assertEqual(json.loads(self.route().stdout)['gear'], 1)

    def test_policy_restriction_avoids_local_inventory(self):
        marker = self.root / 'called'
        self.provider('ollama', 'echo called > "' + str(marker) + '"; exit 99')
        result = self.route(NIGHTSHIFT_PROVIDER_POLICY='claude-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['provider'], 'claude')
        self.assertFalse(marker.exists())

    def test_unknown_inventory_backend_fails_closed(self):
        routing = json.loads((ROOT / 'routing.json').read_text())
        routing['local'] = {'backend': 'omlx', 'model': 'fixture'}
        path = self.root / 'routing.json'; path.write_text(json.dumps(routing))
        self.env['NIGHTSHIFT_ROUTING_FILE'] = str(path)
        self.assertEqual(json.loads(self.route().stdout)['gear'], 1)
        self.assertEqual(self.route('explicit').returncode, 64)

    def test_inventory_output_is_bounded(self):
        self.provider('ollama', 'printf "NAME ID SIZE MODIFIED\\n"; while :; do printf "%01000d" 0; done')
        result = self.route(); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['gear'], 1)

    def test_public_default_uses_available_model(self):
        routing = json.loads((ROOT / 'routing.json').read_text())
        routes = [route for role in routing['roles'].values() for route in role['gears'].values()]
        routes += routing['adversarial']['routes']
        self.assertTrue(all(route['model'] == 'gpt-6.1-sol' for route in routes if route['provider'] == 'codex'))

    def test_bounded_inventory(self):
        self.provider('ollama', '/bin/sleep 5')
        result = self.route(); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['gear'], 1)


if __name__ == '__main__': unittest.main()
