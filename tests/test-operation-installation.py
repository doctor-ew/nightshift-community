#!/usr/bin/env python3
"""Temporary symlink installation acceptance; synthetic provider executables only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('interfaces', ROOT / 'tests/test-operation-interfaces.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class Installation(unittest.TestCase):
    def test_installed_launcher_and_shared_dashboard(self):
        with tempfile.TemporaryDirectory(prefix='nightshift-install-acceptance-') as temporary:
            base = Path(temporary).resolve()
            source = base / 'source'
            subprocess.run(['git', 'clone', '--quiet', '--local', '--no-hardlinks', str(ROOT), str(source)], check=True)
            project = base / 'project'
            project.mkdir()
            env = f.isolated(project)
            targets = {key: base / key for key in ('claude', 'codex', 'runtime', 'bin')}
            env.update(NIGHTSHIFT_HOME=str(targets['runtime']), CODEX_HOME=str(targets['codex']))
            args = ['--runtime', 'all', '--target', str(targets['claude']), '--codex-target', str(targets['codex']),
                    '--nightshift-target', str(targets['runtime']), '--bin-target', str(targets['bin'])]
            installed = subprocess.run(['bash', str(source / 'install.sh'), *args], env=env, text=True, capture_output=True, timeout=90)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            audited = subprocess.run(['bash', str(source / 'install.sh'), '--check', *args], env=env, text=True, capture_output=True, timeout=90)
            self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)
            launcher = targets['bin'] / 'nightshift'
            self.assertEqual(launcher.resolve(), source / 'scripts/nightshift-factory.sh')
            self.assertEqual((targets['runtime'] / 'scripts/nightshift-operations.py').resolve(), source / 'scripts/nightshift-operations.py')
            def cli(*arguments):
                result = subprocess.run([str(launcher), 'ops', *arguments, '--project', str(project)], env=env, text=True, capture_output=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return json.loads(result.stdout)
            assessment = cli('assess', 'demo', 'groom-spec')
            grant = cli('authorize', 'demo', '--recipe', 'factory', '--binding', assessment['binding'], '--operator', 'synthetic-install', '--request', 'installed')
            result = cli('chain', 'demo', '--grant', grant['id'])
            self.assertEqual(result['view']['status'], 'pending_manual_acceptance')
            calls = (project / '.synthetic-calls.jsonl').read_text()
            self.assertEqual(len(calls.splitlines()), 4)
            replay = cli('chain', 'demo', '--grant', grant['id'])
            self.assertEqual((project / '.synthetic-calls.jsonl').read_text(), calls)
            server = subprocess.Popen(['python3', str(targets['runtime'] / 'dashboard/server.py'), '--project', str(project), '--port', '0'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                url = server.stdout.readline().strip()
                self.assertTrue(url.startswith('http://127.0.0.1:'), url)
                import http.client
                conn = http.client.HTTPConnection('127.0.0.1', int(url.rsplit(':', 1)[1]), timeout=10)
                conn.request('GET', '/api/operations?task=demo')
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                view = json.loads(response.read())['view']
                conn.close()
                view.pop('usage')
                replay['view'].pop('usage')
                self.assertEqual(view, replay['view'])
            finally:
                server.terminate()
                server.communicate(timeout=10)
            revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
            self.assertEqual(revision, subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip())
            report = dict(synthetic=True, revision=revision,
                          endpoint='review_pending_manual_acceptance', installed_mode='temporary_symlink',
                          provider_calls=4, requests=[json.loads(row) for row in calls.splitlines()],
                          cache_reused_operations=len(replay['results']), usage=result['view']['usage'],
                          live_certification=False, activated=False)
            if os.environ.get('NIGHTSHIFT_INSTALL_ACCEPTANCE_REPORT'):
                Path(os.environ['NIGHTSHIFT_INSTALL_ACCEPTANCE_REPORT']).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
