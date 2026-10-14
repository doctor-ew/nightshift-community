#!/usr/bin/env python3
"""Read-only controller card through actual HTTP API and built browser UI; no models."""
import http.client
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('read_only_fixtures', ROOT/'tests/test-console-read-only.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)


class ReadOnlyBrowser(unittest.TestCase):
    def test_api_and_browser_preserve_read_only_controller_evidence(self):
        with tempfile.TemporaryDirectory(prefix='nightshift-read-only-browser-') as directory:
            project=Path(directory).resolve()
            fixtures.fixture(project)
            budget=fixtures.actions._recovery.load('ticket-budget')
            budget.update(project,'demo','reserve','original',max_wall_seconds=600,now=10)
            budget.update(project,'demo','finish','original',now=11,outcome='failed')
            before={str(path):path.read_bytes() for path in (project/'.git/nightshift').rglob('*.json')}
            with tempfile.TemporaryFile(mode='w+') as errors:
                server=subprocess.Popen(['python3',str(ROOT/'dashboard/server.py'),'--project',str(project),'--port','0'],stdout=subprocess.PIPE,stderr=errors,text=True)
                try:
                    url=server.stdout.readline().strip()
                    self.assertTrue(url.startswith('http://127.0.0.1:'),url)
                    port=int(url.rsplit(':',1)[1])
                    def request(path,body=None,token=''):
                        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=20)
                        connection.request('GET' if body is None else 'POST',path,body=None if body is None else json.dumps(body),headers={} if body is None else {'Content-Type':'application/json','Origin':url,'X-Nightshift-Token':token})
                        response=connection.getresponse();result=response.status,json.loads(response.read());connection.close();return result
                    status,data=request('/api/tickets')
                    self.assertEqual(status,200)
                    row=data['tickets'][0]
                    self.assertTrue(row['read_only'])
                    self.assertEqual(row['pipeline']['next_action'],'product')
                    for action in ('resume','repair','continue','cleanup','approve','stop','recovery-assess','chat','decision'):
                        body=dict(task='demo',sha256=row['sha256'])
                        if action=='repair':body['provider']='auto'
                        if action=='continue':body['budget_revision']=row['budget']['revision']
                        if action=='chat':body.update(provider='auto',message='Synthetic action must not launch')
                        if action=='decision':body.update(decision_sha256='a'*64,choice='synthetic',answer='')
                        code,result=request('/api/tickets/'+action,body,data['token'])
                        self.assertEqual(code,409,(action,result))
                        self.assertIn('terminal',result['error'])
                    (ROOT/'.nightshift/133-browser').mkdir(parents=True,exist_ok=True)
                    subprocess.run(['node',str(ROOT/'dashboard/test-read-only-browser.mjs')],env=dict(os.environ,NIGHTSHIFT_READ_ONLY_URL=url,NIGHTSHIFT_READ_ONLY_ARTIFACTS=str(ROOT/'.nightshift/133-browser')),check=True,timeout=60)
                    after={str(path):path.read_bytes() for path in (project/'.git/nightshift').rglob('*.json')}
                    self.assertEqual(before,after)
                finally:
                    server.terminate();server.communicate(timeout=10)


if __name__=='__main__':unittest.main()
