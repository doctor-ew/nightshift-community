"""Loopback API fixtures: no provider calls or browser dependency."""
import http.client
import ast
import json
import os
from pathlib import Path
import subprocess
import stat
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.state = self.repo / '.nightshift' / 'batch-20300101-0101.json'
        self.state.parent.mkdir()
        self.write('running')
        self.server = subprocess.Popen(['bash', str(ROOT / 'scripts/nightshift-dashboard.sh'),
            '--project', str(self.repo), '--serve', '--port', '0'], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop)
        line = self.server.stdout.readline()
        self.assertTrue(line.startswith('http://127.0.0.1:'), line)
        self.port = int(line.strip().rsplit(':', 1)[1])

    def stop(self):
        self.server.terminate()
        self.server.communicate(timeout=5)

    def write(self, status):
        self.state.write_text(json.dumps({'batch_id': 'test', 'statuses': {'task-a': {'status': status}}}))

    def request(self, path='/', method='GET', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        conn.request(method, path, headers=headers or {})
        response = conn.getresponse()
        body = response.read()
        result = response.status, body, dict(response.getheaders())
        conn.close()
        return result

    def test_updates_and_local_assets(self):
        agent = self.repo / '.nightshift' / 'agents' / 'dispatch.json'
        agent.parent.mkdir()
        agent.write_text(json.dumps({'role':'engineer','provider':'claude','model':'sonnet',
            'gear':1,'status':'running','pid':123,'started_at':'2030-01-01T00:00:00Z'}))
        original = self.state.read_bytes()
        code, body, headers = self.request('/api/state')
        self.assertEqual(code, 200)
        snapshot = json.loads(body)
        agent_rows = [r for r in snapshot['rows'] if r['source'] == 'agent']
        self.assertEqual(agent_rows[0]['state'], 'running')
        self.assertEqual(agent_rows[0]['model'], 'sonnet')
        self.assertEqual(self.state.read_bytes(), original)
        self.write('complete')
        time.sleep(2.1)
        updated = json.loads(self.request('/api/state')[1])
        self.assertEqual(next(r for r in updated['rows'] if r['source']=='batch')['state'], 'complete')
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/assets/app.js')[0], 200)
        self.assertIn("connect-src 'self'", self.request('/')[2]['Content-Security-Policy'])

    def test_security_boundary(self):
        for method in ['POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']:
            self.assertEqual(self.request('/api/state', method)[0], 405)
        for headers in [{'Host': 'evil.example'}, {'Origin': 'https://evil.example'},
                        {'Origin': 'null'}, {'Sec-Fetch-Site': 'cross-site'}]:
            self.assertEqual(self.request('/api/state', headers=headers)[0], 403)
        for path in ['/../../etc/passwd', '/assets/../server.py', '/api/state?path=/etc/passwd', '/.git/config']:
            self.assertEqual(self.request(path)[0], 404)
        self.assertNotIn('Access-Control-Allow-Origin', self.request('/api/state')[2])


class CollectorRaceTests(unittest.TestCase):
    def test_symlink_retarget_at_open_is_rejected(self):
        source = (ROOT / 'scripts/nightshift-dashboard.sh').read_text()
        embedded = source.split("<<'NIGHTSHIFT_DASHBOARD_PY_EOF'\n", 1)[1].rsplit('\nNIGHTSHIFT_DASHBOARD_PY_EOF', 1)[0]
        tree = ast.parse(embedded)
        helpers = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                                  and n.name in ('within', 'read_bounded')], type_ignores=[])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            state = root / 'state'; state.mkdir()
            target = state / 'record.json'; target.write_text('{}')
            secret = root / 'private.json'; secret.write_text('PRIVATE_SECRET')
            namespace = dict(os=os, stat=stat, MAX_FILE_BYTES=1024, ARTIFACT_ROOTS=[str(state)])
            exec(compile(helpers, '<collector helpers>', 'exec'), namespace)
            original_open = os.open
            def retarget(path, flags, *args, **kwargs):
                if path == 'record.json':
                    target.unlink(); target.symlink_to(secret)
                return original_open(path, flags, *args, **kwargs)
            with patch('os.open', side_effect=retarget):
                text, error = namespace['read_bounded'](str(target))
            self.assertIsNone(text)
            self.assertIsNotNone(error)


if __name__ == '__main__':
    unittest.main(verbosity=2)
