#!/usr/bin/env python3
"""Actual spawned HTTP transport and launcher; all endpoints are loopback fixtures."""
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
f=module('semantic_interface_fixture',ROOT/'tests/test-operation-interfaces.py')
e=module('unimportable_transport_fixture',ROOT/'scripts/nightshift-efficiency.py')

class Transport(unittest.TestCase):
    def setUp(self):
        self.requests=[];self.mode='pass';owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=self.rfile.read(int(self.headers['Content-Length']))
                owner.requests.append(dict(request_bytes=len(body),authorization=self.headers.get('Authorization')))
                if owner.mode=='slow':time.sleep(.5)
                raw=b'x'*3000 if owner.mode=='large' else json.dumps(dict(model='synthetic-pinned-1',answers={'supported':dict(type='noul',noul=.99)})).encode()
                self.send_response(503 if owner.mode=='unavailable' else 200);self.end_headers()
                try:self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.settings=dict(endpoint='http://127.0.0.1:'+str(self.server.server_port)+'/evaluate',timeout_seconds=2,max_bytes=2048)
    def test_dynamic_import_and_repeated_transport(self):
        before={c.pid for c in multiprocessing.active_children()}
        for _ in range(3):
            result=json.loads(e.bounded_request(self.settings,'synthetic-only',b'{}'))
            self.assertEqual(result['model'],'synthetic-pinned-1')
        self.assertEqual({c.pid for c in multiprocessing.active_children()},before)
        self.assertEqual(len(self.requests),3)
        self.assertTrue(all(r['authorization']=='Bearer synthetic-only' for r in self.requests))
    def test_timeout_stops_child(self):
        self.mode='slow';settings=dict(self.settings,timeout_seconds=.1);start=time.monotonic()
        with self.assertRaises(e.Invalid):e.bounded_request(settings,'synthetic-only',b'{}')
        self.assertLess(time.monotonic()-start,2);self.assertFalse(multiprocessing.active_children())
    def test_oversize_and_http_failure_stay_closed(self):
        for mode,reason in [('large','RESPONSE_LIMIT'),('unavailable','HTTP_STATUS')]:
            self.mode=mode
            with self.assertRaisesRegex(e.Invalid,reason):e.bounded_request(self.settings,'synthetic-only',b'{}')
    def test_spawn_failure_closes_pipes_without_join(self):
        from unittest.mock import Mock
        for construction in (False,True):
            context=Mock();reader=Mock();writer=Mock();worker=Mock();worker.pid=None;context.Pipe.return_value=(reader,writer)
            if construction:context.Process.side_effect=OSError('synthetic-only')
            else:context.Process.return_value=worker;worker.start.side_effect=OSError('synthetic-only')
            with patch.object(e.multiprocessing,'get_context',return_value=context):
                with self.assertRaisesRegex(e.Invalid,'^REQUEST_FAILED$'):e.bounded_request(self.settings,'synthetic-only',b'{}')
            reader.close.assert_called_once();writer.close.assert_called_once();worker.join.assert_not_called();worker.is_alive.assert_not_called()
    def test_post_spawn_interrupt_and_error_reap_owned_worker(self):
        from unittest.mock import Mock
        for failure in (KeyboardInterrupt('synthetic post-spawn interruption'),OSError('synthetic post-spawn error')):
            with self.subTest(failure=type(failure).__name__):
                context=Mock();reader=Mock();writer=Mock();worker=Mock()
                context.Pipe.return_value=(reader,writer);context.Process.return_value=worker
                worker.pid=424242;worker.is_alive.return_value=True;worker.start.side_effect=failure
                with patch.object(e.multiprocessing,'get_context',return_value=context):
                    expected=KeyboardInterrupt if isinstance(failure,KeyboardInterrupt) else e.Invalid
                    with self.assertRaises(expected):e.bounded_request(self.settings,'synthetic-only',b'{}')
                worker.kill.assert_called_once();worker.join.assert_called_once();worker.close.assert_called_once()
                reader.close.assert_called_once();writer.close.assert_called_once()
    def test_cleanup_error_still_closes_both_pipe_ends(self):
        from unittest.mock import Mock
        context=Mock();reader=Mock();writer=Mock();worker=Mock()
        context.Pipe.return_value=(reader,writer);context.Process.return_value=worker
        worker.pid=424242;worker.is_alive.return_value=True;worker.start.side_effect=KeyboardInterrupt('synthetic post-spawn interruption')
        worker.kill.side_effect=OSError('synthetic cleanup failure')
        with patch.object(e.multiprocessing,'get_context',return_value=context):
            with self.assertRaises(BaseException):e.bounded_request(self.settings,'synthetic-only',b'{}')
        reader.close.assert_called_once();writer.close.assert_called_once();worker.close.assert_called_once()
    def test_actual_launcher_semantic_handoff_and_replay(self):
        with tempfile.TemporaryDirectory(prefix='nightshift-semantic-launcher-') as temporary:
            root=Path(temporary);env=f.isolated(root)
            env["PLAYWRIGHT_BROWSERS_PATH"]=os.environ.get("PLAYWRIGHT_BROWSERS_PATH",str(Path.home()/("Library/Caches/ms-playwright" if __import__("sys").platform=="darwin" else ".cache/ms-playwright")))
            env.update(NIGHTSHIFT_JEV_ENDPOINT=self.settings['endpoint'],NIGHTSHIFT_JEV_MODEL='synthetic-pinned-1',NIGHTSHIFT_JEV_ALLOW_LOOPBACK='true',NIGHTSHIFT_JEV_KEY_ENV='SYNTHETIC_JEV_KEY',SYNTHETIC_JEV_KEY='synthetic-only')
            p=root/'docs/demo/operations.json';plan=json.loads(p.read_text());controller=f.f.m.Operations(root,'demo');bridge=f.f.m.load('operation-decisions')
            (root/'docs/demo/semantic.json').write_text(json.dumps(bridge.generate(controller,plan,'groom-adversarial')))
            plan['reviewer_policy']['semantic_plan']='docs/demo/semantic.json';plan['limits']['groom-adversarial'].update(calls=12,seconds=120);plan['aggregate'].update(calls=30,seconds=300);p.write_text(json.dumps(plan))
            def cli(*args):
                result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'ops',*args,'--project',str(root)],env=env,capture_output=True,text=True,timeout=120)
                self.assertTrue(result.stdout,result.stderr);self.assertEqual(result.returncode,0,result.stdout+result.stderr);return json.loads(result.stdout)
            browser_report=None
            if os.environ.get('NIGHTSHIFT_SEMANTIC_BROWSER')=='1':
                with tempfile.TemporaryFile(mode='w+') as errors:
                    server=subprocess.Popen(['python3',str(ROOT/'dashboard/server.py'),'--project',str(root),'--port','0'],env=env,stdout=subprocess.PIPE,stderr=errors,text=True)
                    try:
                        url=server.stdout.readline().strip();self.assertTrue(url.startswith('http://127.0.0.1:'),url)
                        env.update(NIGHTSHIFT_BROWSER_URL=url,NIGHTSHIFT_BROWSER_PROJECT=str(root))
                        subprocess.run(['node',str(ROOT/'dashboard/test-semantic-browser.mjs')],env=env,check=True,timeout=120)
                        browser_report=json.loads((root/'.nightshift-fixture-bin/browser-report.json').read_text());grant=browser_report['grant'];first=cli('view','demo')
                    finally:server.terminate();server.communicate(timeout=10)
            else:
                assessed=cli('assess','demo','groom-spec');grant=cli('authorize','demo','--recipe','groom','--binding',assessed['binding'],'--operator','synthetic','--request','semantic-http')['id']
                chain=cli('chain','demo','--grant',grant);self.assertTrue(all(r['status']=='passed' for r in chain['results']),chain);first=chain['view']
            calls=(root/'.synthetic-calls.jsonl').read_text();self.assertEqual(len(calls.splitlines()),5);self.assertEqual(len(self.requests),3)
            replay=cli('chain','demo','--grant',grant);self.assertEqual((root/'.synthetic-calls.jsonl').read_text(),calls);self.assertEqual(len(self.requests),3)
            ledger=json.loads((root/'.git/nightshift/operations/demo/state.json').read_text());receipts=ledger['results']['groom-adversarial']['semantic']['receipts']
            self.assertEqual(sum(len(r['calls'])-1 for r in receipts),3)
            self.assertTrue(all(r['decision']=='yes' for r in receipts));self.assertEqual(first['usage'][grant]['calls'],8);self.assertEqual(first['usage'][grant]['unknown'],0)
            # Endpoint identity changes invalidate the semantic judgment, without dispatch.
            env['NIGHTSHIFT_JEV_MODEL']='synthetic-pinned-2';changed=cli('view','demo')
            judgment=next(r for r in changed['operations'] if r['operation']=='groom-adversarial');self.assertNotEqual(judgment['status'],'current');self.assertEqual(len(self.requests),3)
            report=dict(synthetic=True,revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),worker_calls=5,evaluator_calls=3,independent_escalations=3,replay_calls=0,reused_operations=len(replay['results']),requests=[json.loads(r) for r in calls.splitlines()],evaluator_request_bytes=[r['request_bytes'] for r in self.requests],usage=first['usage'],browser=browser_report,provider_tokens=None,provider_cache_usage=None,billed_cost=None,live_certification=False)
            if os.environ.get('NIGHTSHIFT_SEMANTIC_TRANSPORT_REPORT'):Path(os.environ['NIGHTSHIFT_SEMANTIC_TRANSPORT_REPORT']).write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':unittest.main()
