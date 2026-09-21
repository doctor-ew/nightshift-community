#!/usr/bin/env python3
"""Offline matrix tests; no paid provider calls."""
import http.server
import importlib.util
import io
import shutil
from unittest import mock
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / 'scripts/nightshift-efficiency.py'
SPEC = importlib.util.spec_from_file_location('efficiency', HELPER)
EFFICIENCY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EFFICIENCY)


class Efficiency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, NIGHTSHIFT_EFFICIENCY_DIR=str(self.base / 'receipts'),
                        PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        for key in list(self.env):
            if key.startswith(('NIGHTSHIFT_JEV_', 'NIGHTSHIFT_RTK_', 'NIGHTSHIFT_EXEC_')):
                del self.env[key]
        self.env['TYPESAFE_API_KEY'] = 'offline-secret'

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o700)
        return str(path)

    def run_helper(self, *args, launcher=False):
        command = ['bash', str(ROOT / 'scripts/nightshift-factory.sh')] if launcher else [sys.executable, str(HELPER)]
        result = subprocess.run(command + list(args), cwd=self.base, env=self.env, capture_output=True, timeout=10)
        receipts = list((self.base / 'receipts').glob('*/receipt.json'))
        record = json.loads(max(receipts, key=lambda p:p.stat().st_mtime_ns).read_text()) if receipts else None
        return result, record

    def noisy(self, code=0):
        return self.stub('pytest', "import pathlib, sys\np=pathlib.Path('count')\np.write_text(str(int(p.read_text())+1) if p.exists() else '1')\nprint('passed\\n'*100)\nprint('warning',file=sys.stderr)\nsys.exit(%d)\n" % code)

    def test_filtered_once_private(self):
        self.stub('rtk', "import sys\nassert sys.argv[1:]==['pipe','--filter','pytest']\nsys.stdin.read()\nprint('100 passed')")
        result, record = self.run_helper('exec', '--', self.noisy())
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'100 passed\n')
        self.assertEqual(record['status'], 'filtered')
        self.assertEqual((self.base / 'count').read_text(), '1')
        folder = next((self.base / 'receipts').iterdir())
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        for file in folder.iterdir():
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        self.assertIn(b'warning\n',result.stderr)
        self.assertGreater(record['raw_stdout_bytes'],record['returned_stdout_bytes'])

    def test_failed_command_raw(self):
        self.stub('rtk', "raise RuntimeError('must not run')")
        result, record = self.run_helper('exec', '--', self.noisy(7))
        self.assertEqual(result.returncode,7)
        self.assertEqual(record['reason'],'NONZERO_RAW')
        self.assertEqual(result.stdout, next((self.base/'receipts').glob('*/stdout.raw')).read_bytes())

    def test_filter_failure_timeout_empty_binary(self):
        self.env['NIGHTSHIFT_RTK_TIMEOUT_SECONDS'] = '0.15'
        for body in ("import sys; sys.exit(9)","import time; time.sleep(3)","pass", "import sys; sys.stdout.buffer.write(b'\\xff')"):
            with self.subTest(body=body):
                self.stub('rtk',body)
                result, record = self.run_helper('exec','--',self.noisy())
                self.assertEqual(result.returncode,0)
                self.assertEqual(result.stdout,b'passed\n'*100+b'\n')
                self.assertIn(record['reason'],('FILTER_INVALID','FILTER_UNAVAILABLE'))

    def test_missing_rtk_and_command(self):
        self.env['PATH']=str(self.bin)+':/usr/bin:/bin'
        result,record=self.run_helper('exec','--',self.noisy())
        self.assertEqual(result.returncode,0)
        self.assertEqual(record['reason'],'RTK_UNAVAILABLE')
        self.assertEqual(result.stdout,b'passed\n'*100+b'\n')
        result,record=self.run_helper('exec','--','/nonexistent/nightshift-test-command')
        self.assertEqual(result.returncode,127)
        self.assertEqual(record['reason'],'COMMAND_UNAVAILABLE')

    def test_invalid_endpoint_and_secret_config(self):
        for endpoint in ('http://example.org/', 'https://key@example.org/', 'https://example.org/?key=secret'):
            result,_=self.run_helper('evaluate','--endpoint',endpoint)
            self.assertEqual(result.returncode,64)
            self.assertNotIn(endpoint.encode(),result.stderr)
        (self.base/'.nightshift-efficiency.json').write_text('{"jev":{"api_key":"secret"}}')
        result,_=self.run_helper('evaluate')
        self.assertEqual(result.returncode,64)
        self.assertNotIn(b'secret',result.stderr)

    def test_machine_and_exact_bypass(self):
        self.stub('rtk',"raise RuntimeError('must not run')")
        for argv in ([self.noisy(),'--json'],[self.noisy(),'--reporter=json'],[sys.executable,'-c',"print('exact')"]):
            result, record = self.run_helper('exec','--',*argv)
            self.assertEqual(result.returncode,0)
            self.assertEqual(record['reason'],'COMMAND_BYPASS')

    def test_precedence_and_invalid_config(self):
        (self.base/'.nightshift-efficiency.json').write_text(json.dumps({'rtk':{'enabled':False}}))
        self.env['NIGHTSHIFT_RTK_ENABLED']='true'
        result, record=self.run_helper('exec','--no-enabled','--',self.noisy())
        self.assertEqual(record['reason'],'DISABLED')
        self.env['NIGHTSHIFT_RTK_ENABLED']='"yes"'
        result,_=self.run_helper('exec','--',self.noisy())
        self.assertEqual(result.returncode,64)
        self.assertEqual((self.base/'count').read_text(),'1')

    def test_skipped(self):
        for args, reason in (([], 'NO_INPUT'), (['--no-enabled'], 'DISABLED')):
            result,record=self.run_helper('evaluate',*args)
            self.assertEqual(result.returncode,0)
            self.assertEqual(record['reason'],reason)
        del self.env['TYPESAFE_API_KEY']
        _,record=self.run_helper('evaluate','--input','missing')
        self.assertEqual(record['reason'],'NO_KEY')

    def test_fifo_and_oversize(self):
        fifo=self.base/'fifo';os.mkfifo(fifo)
        _,record=self.run_helper('evaluate','--input',str(fifo))
        self.assertEqual(record['reason'],'INPUT_INVALID')
        evidence=self.base/'input';evidence.write_text('x'*2048)
        _,record=self.run_helper('evaluate','--max-bytes','1024','--input',str(evidence))
        self.assertEqual(record['reason'],'INPUT_LIMIT')

    def test_symlink_receipt_rejected(self):
        target=self.base/'target';target.mkdir(mode=0o700)
        (self.base/'receipts').symlink_to(target)
        result,_=self.run_helper('exec','--',self.noisy())
        self.assertEqual(result.returncode,64)
        self.assertFalse((self.base/'count').exists())
        self.assertEqual(list(target.iterdir()),[])

    def test_command_limits(self):
        self.env['NIGHTSHIFT_EXEC_TIMEOUT_SECONDS']='0.1'
        result,record=self.run_helper('exec','--',sys.executable,'-c','import time; time.sleep(3)')
        self.assertEqual(result.returncode,124)
        self.assertFalse(record['raw_complete'])
        self.env['NIGHTSHIFT_EXEC_MAX_BYTES']='1024'
        result,record=self.run_helper('exec','--',sys.executable,'-c',"print('x'*2000)")
        self.assertEqual(result.returncode,124)
        self.assertEqual(record['reason'],'OUTPUT_LIMIT')
        self.assertEqual(result.stdout, b'x' * 1024)
        self.assertEqual(record['raw_stdout_bytes'], 1024)

    def test_launcher_and_guard(self):
        result,record=self.run_helper('exec','--',sys.executable,'-c',"print('literal $()')",launcher=True)
        self.assertEqual(result.stdout,b'literal $()\n')
        self.assertEqual(result.returncode,0)
        self.env['NIGHTSHIFT_ROLE_CHILD']='1'
        result,_=self.run_helper('evaluate',launcher=True)
        self.assertEqual(result.returncode,64)

    def test_interrupt_reaps_child(self):
        pidfile=self.base/'child.pid'
        proc=subprocess.Popen([sys.executable,str(HELPER),'exec','--',sys.executable,'-c',
            "import os,pathlib,time; pathlib.Path('child.pid').write_text(str(os.getpid())); time.sleep(30)"],
            cwd=self.base,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for _ in range(100):
            if pidfile.exists():break
            time.sleep(0.02)
        self.assertTrue(pidfile.exists())
        proc.send_signal(signal.SIGINT)
        proc.communicate(timeout=3)
        self.assertEqual(proc.returncode,130)
        with self.assertRaises(ProcessLookupError):os.kill(int(pidfile.read_text()),0)

    def test_sigterm_reaps_child(self):
        pidfile=self.base/'term.pid'
        proc=subprocess.Popen([sys.executable,str(HELPER),'exec','--',sys.executable,'-c',
            "import os,pathlib,time; pathlib.Path('term.pid').write_text(str(os.getpid())); time.sleep(30)"],
            cwd=self.base,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for _ in range(100):
            if pidfile.exists():break
            time.sleep(0.02)
        self.assertTrue(pidfile.exists())
        proc.terminate()
        proc.communicate(timeout=3)
        self.assertEqual(proc.returncode,143)
        with self.assertRaises(ProcessLookupError):os.kill(int(pidfile.read_text()),0)
        record=json.loads(next((self.base/'receipts').glob('*/receipt.json')).read_text())
        self.assertEqual(record['reason'],'TERMINATED')
        self.assertEqual(record['command_returncode'],-signal.SIGKILL)

    def test_capture_io_failure_reaps(self):
        class Broken(io.BytesIO):
            def write(self, data):raise OSError('fixture disk failure')
        started=time.monotonic()
        code,reason,_,actual=EFFICIENCY.capture([sys.executable,'-c',
            "import sys,time; print('data',flush=True); time.sleep(30)"],(Broken(),io.BytesIO()),5,1024)
        self.assertLess(time.monotonic()-started,2)
        self.assertEqual((code,reason,actual),(74,'CAPTURE_IO_ERROR',-signal.SIGKILL))

    def test_closed_consumer_retains_receipt(self):
        proc=subprocess.Popen([sys.executable,str(HELPER),'exec','--',self.noisy(7)],
                              cwd=self.base,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        proc.stdout.close()
        proc.stderr.read()
        proc.stderr.close()
        proc.wait(timeout=5)
        self.assertEqual(proc.returncode,141)
        record=json.loads(next((self.base/'receipts').glob('*/receipt.json')).read_text())
        delivery=json.loads(next((self.base/'receipts').glob('*/delivery.json')).read_text())
        self.assertEqual(record['command_returncode'],7)
        self.assertEqual(record['exit_code'],7)
        self.assertEqual(delivery['exit_code'],141)
        self.assertEqual(delivery['reason'],'CONSUMER_CLOSED')

    def test_filter_cancellation_preserves_command_outcome(self):
        self.stub('rtk',"import pathlib,os,time,sys; sys.stdout.buffer.write(bytes([255])); sys.stdout.flush(); pathlib.Path('filter.pid').write_text(str(os.getpid())); time.sleep(30)")
        proc=subprocess.Popen([sys.executable,str(HELPER),'exec','--',self.noisy()],cwd=self.base,
                              env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        pidfile=self.base/'filter.pid'
        for _ in range(100):
            if pidfile.exists():break
            time.sleep(0.02)
        self.assertTrue(pidfile.exists())
        proc.send_signal(signal.SIGINT)
        proc.communicate(timeout=3)
        self.assertEqual(proc.returncode,130)
        record=json.loads(next((self.base/'receipts').glob('*/receipt.json')).read_text())
        self.assertEqual(record['command_returncode'],0)
        self.assertEqual(record['exit_code'],130)
        self.assertEqual(record['reason'],'INTERRUPTED')
        with self.assertRaises(ProcessLookupError):os.kill(int(pidfile.read_text()),0)

    def test_adapter_config_isolation(self):
        path=self.base/'.nightshift-efficiency.json'
        path.write_text(json.dumps({'jev':{'endpoint':'invalid','timeout_seconds':'bad'}}))
        self.env['NIGHTSHIFT_JEV_ENABLED']='not-json'
        result,record=self.run_helper('exec','--',sys.executable,'-c',"print('ok')")
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,b'ok\n')
        del self.env['NIGHTSHIFT_JEV_ENABLED']
        path.write_text(json.dumps({'rtk':{'timeout_seconds':'bad'},'exec':{'max_bytes':False}}))
        self.env['NIGHTSHIFT_RTK_ENABLED']='not-json'
        result,record=self.run_helper('evaluate')
        self.assertEqual(result.returncode,0)
        self.assertEqual(record['reason'],'NO_INPUT')
        path.write_text('{"rtk":{"unknown":1}}')
        result,_=self.run_helper('evaluate')
        self.assertEqual(result.returncode,64)

    def test_exact_listings_raw(self):
        self.stub('rtk',"raise RuntimeError('must not run')")
        for name,args in [('tsc',['--listFilesOnly']),('pytest',['--collect-only']),('cargo',['test','--','--list'])]:
            command=self.stub(name,"print('exact file or test identifier')")
            result,record=self.run_helper('exec','--',command,*args)
            self.assertEqual(result.stdout,b'exact file or test identifier\n')
            self.assertEqual(record['reason'],'COMMAND_BYPASS')

    def test_supported_filter_mappings(self):
        cases=[('pytest',[], 'pytest', 'test_a.py::test_ok PASSED\n1 passed in 0.01s\n'),
               ('pytest3',[], 'pytest', '1 passed in 0.01s\n'),
               ('python3',['-m','pytest'], 'pytest', '1 passed in 0.01s\n'),
               ('cargo',['test'], 'cargo-test', 'running 1 test\ntest test_ok ... ok\ntest result: ok. 1 passed; 0 failed;\n'),
               ('tsc',[], 'tsc', 'src/a.ts(1,1): error TS2322: Type mismatch.\n'),
               ('vitest',['run'], 'vitest', ' Test Files  1 passed (1)\n      Tests  1 passed (1)\n'),
               ('git',['status'], 'git-status', 'On branch main\nChanges not staged for commit:\n  modified: file.txt\n')]
        for name,args,filter_name,content in cases:
            command=self.stub(name,'import sys; sys.stdout.write('+repr(content)+')')
            self.stub('rtk', 'import sys; assert sys.argv[1:]=='+repr(['pipe','--filter',filter_name])+
                      '; assert sys.stdin.read()=='+repr(content)+"; print('ok')")
            result,record=self.run_helper('exec','--',command,*args)
            self.assertEqual(result.returncode,0)
            self.assertEqual(record['filter'],filter_name)
            self.assertEqual(record['status'],'filtered')
            self.assertEqual(result.stdout,b'ok\n')

    def test_unsupported_platform_is_explicit(self):
        for action,code in [('evaluate',0),('exec',69)]:
            with mock.patch.object(EFFICIENCY.os,'name','nt'), mock.patch.object(sys,'argv',['helper',action]), mock.patch.object(sys,'stderr',io.StringIO()) as error:
                self.assertEqual(EFFICIENCY.main(),code)
                self.assertIn('UNSUPPORTED_PLATFORM',error.getvalue())

    def test_factory_evaluation_and_copied_install(self):
        installed=self.base/'installed'
        shutil.copytree(ROOT/'scripts',installed/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'commands',installed/'commands')
        shutil.copy(ROOT/'efficiency.json',installed/'nightshift-efficiency.json')
        for name in ('nightshift.toml','VERSION'):
            shutil.copy(ROOT/name,installed/name)
        project=self.base/'project';project.mkdir()
        subprocess.run(['git','init','-q',str(project)],check=True)
        shutil.copy(ROOT/'nightshift.toml',project/'.nightshift.toml')
        shutil.copy(ROOT/'routing.json',project/'routing.json')
        (project/'prompt.md').write_text('# Fixture\nA bounded test requirement.\n')
        evidence=project/'evidence.txt';evidence.write_text('explicit fixture evidence')
        home=self.base/'home';home.mkdir()
        self.stub('codex',"import sys,os\nif sys.argv[1:3]==['login','status']: print('Logged in using ChatGPT')\nelse: sys.exit(int(os.environ.get('FIXTURE_PROVIDER_STATUS','0')))")
        env=dict(self.env,HOME=str(home),NIGHTSHIFT_HOME=str(home),NIGHTSHIFT_OUTPUT_CHILD='1',
                 NIGHTSHIFT_UPDATE_GUARD='1',NIGHTSHIFT_DASHBOARD='off',NIGHTSHIFT_OUTPUT='verbose',
                 NIGHTSHIFT_JEV_INPUT=str(evidence),NIGHTSHIFT_JEV_ALLOW_LOOPBACK='true')
        calls=[]
        state={'status':200}
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(state['status']);self.end_headers()
                self.wfile.write(json.dumps({'model':'jev-fixture','answers':{
                    name:{'type':'noul','noul':0.5} for name in ('supported','limitations')},
                    'usage':{'input_tokens':17,'output_tokens':3}}).encode())
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.shutdown)
        env['NIGHTSHIFT_JEV_ENDPOINT']=f'http://127.0.0.1:{server.server_port}/v1/systemone'
        for enabled,http_status,provider_status,expected in ((True,200,0,'evaluated'),(False,200,0,'skipped'),(True,503,75,'unavailable')):
            state['status']=http_status
            current=dict(env,NIGHTSHIFT_JEV_ENABLED=json.dumps(enabled),FIXTURE_PROVIDER_STATUS=str(provider_status))
            before=len(calls)
            result=subprocess.run(['bash',str(installed/'scripts/nightshift-factory.sh'),'codex','prompt.md',
                '--project',str(project),'--branch','none'],cwd=project,env=current,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,provider_status,result.stderr.decode())
            self.assertEqual(len(calls)-before,int(enabled))
            paths=list((self.base/'receipts').glob('*/receipt.json'))
            record=json.loads(max(paths,key=lambda p:p.stat().st_mtime_ns).read_text())
            self.assertEqual(record['status'],expected)
            self.assertTrue(record['run_id'])
            self.assertEqual(len(record['implementation_sha256']),64)
            self.assertEqual(len(record['config_sha256']),64)
            self.assertEqual(len(record['endpoint_sha256']),64)
            summary=json.loads((project/'.git/nightshift/runs'/record['run_id']/'summary.json').read_text())
            observations=[item for item in summary['observations'] if item['invocation_id'].startswith('jev-shadow-')]
            self.assertEqual(len(observations),int(enabled))
            if enabled:
                self.assertIsNone(observations[0]['provider'])
                self.assertIsNone(observations[0]['stage'])
                self.assertGreaterEqual(observations[0]['duration_seconds'],0)
                self.assertEqual(observations[0]['status'],'success' if http_status==200 else 'failed')
            if http_status==200 and enabled:
                self.assertEqual(observations[0]['usage'],{'input_tokens':17,'output_tokens':3})
                self.assertEqual(record['reported_model'],'jev-fixture')
        self.assertEqual(calls[0]['state'],'explicit fixture evidence')
        # Copied helper resolves renamed shipped config; no source checkout needed.
        result=subprocess.run([sys.executable,str(installed/'scripts/nightshift-efficiency.py'),
            'exec','--',sys.executable,'-c',"print('installed')"],cwd=project,env=env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,b'installed\n')

    def test_mock_evaluation(self):
        calls=[]
        response={'model':'jev-test','answers':{name:{'type':'noul','noul':0.75} for name in ('supported','limitations')},'usage':{'input_tokens':15,'output_tokens':2}}
        state={'status':200,'body':response,'delay':0}
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                time.sleep(state['delay'])
                self.send_response(state['status']);self.end_headers()
                try:self.wfile.write(json.dumps(state['body']).encode())
                except BrokenPipeError:pass
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.addCleanup(server.server_close)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.shutdown)
        evidence=self.base/'input';evidence.write_text('explicit evidence only')
        args=['evaluate','--input',str(evidence),'--endpoint',f'http://127.0.0.1:{server.server_port}/v1/systemone','--allow-loopback']
        result,record=self.run_helper(*args)
        self.assertEqual(record['status'],'evaluated')
        self.assertEqual(record['usage']['input_tokens'],15)
        self.assertEqual(calls[0]['state'],'explicit evidence only')
        self.assertNotIn('offline-secret',json.dumps(record))
        self.assertNotIn('explicit evidence',json.dumps(record))
        for status,body,reason in ((302,response,'HTTP_STATUS'),(200,{'secret':'offline-secret'},'RESPONSE_SCHEMA'),(200,'x'*300000,'RESPONSE_LIMIT')):
            state.update(status=status,body=body)
            _,record=self.run_helper(*args)
            self.assertEqual(record['reason'],reason)
        state.update(status=200,body=response,delay=1)
        _,record=self.run_helper(*args,'--timeout-seconds','0.15')
        self.assertEqual(record['reason'],'TIMEOUT')
        self.assertLess(record['elapsed_seconds'],1)


if __name__=='__main__':unittest.main()
