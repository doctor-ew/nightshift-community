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
from urllib.parse import quote
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

    def request(self, path='/', method='GET', headers=None, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        conn.request(method, path, body=body, headers=headers or {})
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

    def test_web_spec_approval_requires_origin_token_and_current_hash(self):
        import hashlib
        task = 'workshop-' + 'a'*16
        directory = self.repo/'.git/nightshift-workshop'; directory.mkdir()
        (self.repo/'brief.md').write_text('Brief')
        (directory/(task+'.json')).write_text(json.dumps(dict(task=task,status='awaiting_spec_approval',worktree=str(self.repo.resolve()), identity={'auth':'subscription','writer':'fixture'}, resume={'ref':'brief.md'}, brief_sha256=hashlib.sha256(b'Brief').hexdigest())))
        folder = self.repo/'docs'/task;folder.mkdir(parents=True)
        content = '# A spec\n'
        (folder/'SPEC.md').write_text(content)
        (self.repo/('NIGHTSHIFT-SPEC-'+task+'.md')).write_text(content)
        data = json.loads(self.request('/api/workshop/reviews')[1])
        digest = hashlib.sha256(content.encode()).hexdigest()
        self.assertEqual(data['reviews'][0]['sha256'],digest)
        body=json.dumps(dict(task=task,sha256=digest))
        headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(self.port),'X-Nightshift-Token':data['token']}
        self.assertEqual(self.request('/api/workshop/approve','POST',{'Content-Type':'application/json'},body)[0],403)
        self.assertEqual(self.request('/api/workshop/approve','POST',headers,json.dumps(dict(task=task,sha256='stale')))[0],409)
        self.assertEqual(self.request('/api/workshop/approve','POST',headers,body)[0],200)
        self.assertEqual(json.loads((directory/(task+'.approval.json')).read_text())['sha256'],digest)
        # While the launched worker is alive, repeat clicks only reuse that launch.
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            job=json.loads((directory/(task+'.launch.json')).read_text())
            if job.get('status')=='exited': break
            time.sleep(.05)
        self.assertEqual(job['status'],'exited')
        (folder/'SPEC.md').write_text('Changed')
        self.assertEqual(self.request('/api/workshop/approve','POST',headers,body)[0],409)

    def test_ticket_action_authentication(self):
        data=json.loads(self.request('/api/tickets')[1])
        self.assertEqual(data['tickets'], [])
        body=json.dumps({'task':'42','sha256':'unknown'})
        headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(self.port),'X-Nightshift-Token':data['token']}
        for endpoint in ('/api/tickets/resume','/api/tickets/cleanup'):
            self.assertEqual(self.request(endpoint,'POST',{'Content-Type':'application/json'},body)[0],403)
            wrong=dict(headers,Origin='https://evil.example')
            self.assertEqual(self.request(endpoint,'POST',wrong,body)[0],403)
            self.assertEqual(self.request(endpoint,'POST',headers,body)[0],409)
            self.assertEqual(self.request(endpoint,'POST',headers,json.dumps({'task':'42','sha256':'unknown','command':'anything'}))[0],409)

    def test_role_failure_is_visible_and_evidence_is_plain_text(self):
        folder = self.repo / 'docs' / 'task-a'
        folder.mkdir(parents=True)
        receipt = folder / 'implementation.out.json'
        receipt.write_text(json.dumps({'status': 'FAIL', 'reason': 'Write permission denied',
                                      'artifacts': {'provider': 'claude'}, 'attempts': 2}))
        snapshot = json.loads(self.request('/api/state')[1])
        row = next(r for r in snapshot['rows'] if r['source'] == 'gate')
        self.assertEqual((row['ticket'], row['state'], row['gate']), ('task-a', 'blocked', 'implementation'))
        self.assertEqual(row['reason'], 'Write permission denied')
        endpoint = '/api/evidence?uri=' + quote(row['links'][0]['href'], safe='')
        code, body, headers = self.request(endpoint)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['reason'], 'Write permission denied')
        self.assertTrue(headers['Content-Type'].startswith('text/plain'))
        self.assertEqual(self.request('/evidence?uri=' + quote(row['links'][0]['href'], safe=''))[0], 200)
        self.assertEqual(self.request(endpoint, headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)
        secret = self.repo / 'secret.txt'
        secret.write_text('PRIVATE')
        self.assertEqual(self.request('/api/evidence?uri=' + quote(secret.as_uri(), safe=''))[0], 404)
        receipt.unlink()
        receipt.symlink_to(secret)
        self.assertEqual(self.request(endpoint)[0], 404)

    def test_evidence_rejects_retargeted_parent(self):
        folder = self.repo / 'docs' / 'task-a'
        folder.mkdir(parents=True)
        (folder / 'SPEC.md').write_text('Public evidence')
        snapshot = json.loads(self.request('/api/state')[1])
        row = next(r for r in snapshot['rows'] if r['source'] == 'artifacts')
        endpoint = '/api/evidence?uri=' + quote(row['links'][0]['href'], safe='')
        folder.rename(self.repo / 'original')
        secret = self.repo / 'private'
        secret.mkdir()
        (secret / 'SPEC.md').write_text('PRIVATE')
        folder.symlink_to(secret, target_is_directory=True)
        self.assertEqual(self.request(endpoint)[0], 404)

    def test_tracker_blocker_survives_finished_ownership(self):
        tracker = self.repo / '.nightshift' / 'task-a.md'
        tracker.write_text('# Task\n## Failure / Block Receipt\n- Stage: implementation\n'
                           '- Outcome: SKIPPED\n- Root cause: prerequisite naming unresolved\n')
        ownership = self.repo / '.git' / 'nightshift' / 'worktrees'
        ownership.mkdir(parents=True)
        (ownership / 'task-a.json').write_text(json.dumps({'task': 'task-a', 'status': 'finished'}))
        rows = json.loads(self.request('/api/state')[1])['rows']
        blocker = next(r for r in rows if r['source'] == 'gate')
        self.assertEqual(blocker['ticket'], 'task-a')
        self.assertEqual(blocker['state'], 'blocked')
        self.assertIn('prerequisite naming unresolved', blocker['reason'])

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
