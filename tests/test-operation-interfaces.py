#!/usr/bin/env python3
"""Real CLI/HTTP/dispatcher, exclusively synthetic provider executables."""
import http.client
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixture',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
MOCK='''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:];provider=Path(sys.argv[0]).name
if args[:1]==['auth']:
 print(json.dumps(dict(loggedIn=True,authMethod='claude.ai',apiProvider='firstParty')));sys.exit(0)
if args[:1]==['login']:print('Logged in using ChatGPT');sys.exit(0)
assert os.environ.get('NIGHTSHIFT_ROLE_CHILD')=='1'
prompt=args[-1];packet=json.JSONDecoder().raw_decode(prompt.split('Task input:\\n',1)[1])[0]
model=args[args.index('--model')+1] if '--model' in args else args[args.index('-m')+1]
with open(os.environ['SYNTHETIC_CALLS'],'a') as out:out.write(json.dumps(dict(operation=packet['operation'],request_bytes=sum(len(a.encode()) for a in args),packet_bytes=len(json.dumps(packet,sort_keys=True).encode())))+'\\n')
if os.environ.get('SYNTHETIC_PAUSE'):__import__('time').sleep(float(os.environ['SYNTHETIC_PAUSE']))
value=dict(status='SUCCESS',reason='',attempts=1,artifacts=dict(branch='',diff='',provider=provider,model=model),rules_fired=[],results=dict(binding=packet['binding'],decision='approve',findings=[],resolved=packet['findings'],coverage=['scope','rules','architecture','scenarios','correctness','test_oracles',*[c['id'] for c in packet.get('cases',[])]]))
if provider=='claude':print(json.dumps(dict(structured_output=value)))
else:
 key='--output-last-message' if '--output-last-message' in args else '-o'
 Path(args[args.index(key)+1]).write_text(json.dumps(value))
 print(json.dumps(dict(type='thread.started',thread_id='synthetic-only')))
'''


def isolated(root):
    f.fixture(root)
    bin=root/'.nightshift-fixture-bin';bin.mkdir()
    for name in ('codex','claude'):
        path=bin/name;path.write_text(MOCK);path.chmod(0o755)
    (root/'.gitignore').write_text('__pycache__/\n.nightshift-fixture-bin/\n.synthetic-calls.jsonl\n')
    env=dict(os.environ,PATH=str(bin)+os.pathsep+os.environ['PATH'],SYNTHETIC_CALLS=str(root/'.synthetic-calls.jsonl'),NIGHTSHIFT_UPDATE_GUARD='1',NIGHTSHIFT_OUTPUT_CHILD='1',PYTHONDONTWRITEBYTECODE='1')
    for key in ('NIGHTSHIFT_ROLE_CHILD','NIGHTSHIFT_BUDGET_TASK','NIGHTSHIFT_BUDGET_PROJECT','NIGHTSHIFT_TICKET_JSON','NIGHTSHIFT_ROUTING_FILE','NIGHTSHIFT_PROVIDER_POLICY'):
        env.pop(key,None)
    return env


class Interfaces(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nightshift-interface-synthetic-');self.root=Path(self.tmp.name);self.env=isolated(self.root)
        self.server=subprocess.Popen(['python3',str(ROOT/'dashboard/server.py'),'--project',str(self.root),'--port','0'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=self.env)
        line=self.server.stdout.readline();self.assertTrue(line.startswith('http://'),line);self.port=int(line.strip().rsplit(':',1)[1])
        status,data=self.http('/api/operations?task=demo');self.assertEqual(status,200,data);self.token=data['token']
    def tearDown(self):
        self.server.terminate();self.server.communicate(timeout=10);self.tmp.cleanup()
    def http(self,path,body=None,token=True):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=120)
        headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(self.port)}
        if token:headers['X-Nightshift-Token']=getattr(self,'token','')
        conn.request('POST' if body is not None else 'GET',path,body=json.dumps(body) if body is not None else None,headers=headers)
        response=conn.getresponse();raw=response.read();status=response.status;conn.close()
        try:return status,json.loads(raw)
        except ValueError:return status,raw.decode()
    def cli(self,*args,fish=False):
        argv=['bash',str(ROOT/'scripts/nightshift-factory.sh'),'ops',*args,'--project',str(self.root)]
        if fish:
            import shlex
            argv=['fish','-c',' '.join(shlex.quote(x) for x in argv)]
        result=subprocess.run(argv,env=self.env,capture_output=True,text=True,timeout=120)
        return result.returncode,json.loads(result.stdout)
    def test_http_cli_fish_factory_parity_and_duplicate_reservations(self):
        code,a=self.cli('assess','demo','groom-spec',fish=bool(shutil.which('fish')));self.assertEqual(code,0,a)
        status,b=self.http('/api/operations',dict(action='assess',task='demo',operation='groom-spec'));self.assertEqual(a,b)
        status,g=self.http('/api/operations',dict(action='authorize',task='demo',operations=f.m.RECIPES['factory'],binding=a['binding'],operator='synthetic',request='shared'))
        self.assertEqual(status,200,g)
        code,result=self.cli('factory','demo');self.assertEqual(code,0,result)
        self.assertEqual(result['view']['status'],'pending_manual_acceptance',result)
        calls=(self.root/'.synthetic-calls.jsonl').read_text().splitlines();self.assertEqual(len(calls),4)
        status,view=self.http('/api/operations?task=demo');code,cli=self.cli('view','demo')
        # Wall elapsed is intentionally observational and increases between clients.
        view['view'].pop('usage');cli.pop('usage');self.assertEqual(view['view'],cli)
        status,replayed=self.http('/api/operations',dict(action='chain',task='demo',grant='shared'));self.assertEqual(status,200,replayed)
        self.assertEqual((self.root/'.synthetic-calls.jsonl').read_text().splitlines(),calls)
        metrics=[json.loads(row) for row in calls]
        Path(os.environ.get('NIGHTSHIFT_SYNTHETIC_METRICS','/private/tmp/nightshift-operation-metrics.json')).write_text(json.dumps(dict(synthetic=True,provider_calls=len(calls),requests=metrics,cache_reused_operations=len(replayed['results']),usage=result['view']['usage'],live_certification=False),indent=2)+'\n')
    def test_killed_controller_retains_unknown_call_without_redispatch(self):
        code,a=self.cli('assess','demo','groom-spec');self.assertEqual(code,0,a)
        code,g=self.cli('authorize','demo','groom-spec','--binding',a['binding'],'--operator','synthetic','--request','crash-grant');self.assertEqual(code,0,g)
        env=dict(self.env,SYNTHETIC_PAUSE='10')
        process=subprocess.Popen(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'ops','run','demo','groom-spec','--grant',g['id'],'--request','crash-call','--project',str(self.root)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+8
            while not (self.root/'.synthetic-calls.jsonl').exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue((self.root/'.synthetic-calls.jsonl').exists())
            process.kill();process.communicate(timeout=5)
            code,result=self.cli('run','demo','groom-spec','--grant',g['id'],'--request','crash-call')
            self.assertEqual(result['status'],'pending',result)
            code,result=self.cli('run','demo','groom-spec','--grant',g['id'],'--request','crash-other')
            self.assertIn('unfinished_operation',result['reason'])
            code,view=self.cli('view','demo');self.assertEqual(view['usage'][g['id']]['unknown'],1)
            self.assertEqual(len((self.root/'.synthetic-calls.jsonl').read_text().splitlines()),1)
        finally:
            if process.poll() is None:process.kill();process.communicate(timeout=5)
    def test_legacy_ticket_entry_uses_authorized_recipe_without_ticket_provider(self):
        (self.root/'docs/123').mkdir();shutil.copyfile(self.root/'docs/demo/operations.json',self.root/'docs/123/operations.json')
        forbidden=self.root/'.nightshift-fixture-bin/gh';forbidden.write_text('#!/usr/bin/env python3\nraise SystemExit(99)\n');forbidden.chmod(0o755)
        code,a=self.cli('assess','123','groom-spec');self.assertEqual(code,0,a)
        code,g=self.cli('authorize','123','--recipe','factory','--binding',a['binding'],'--operator','synthetic','--request','compatibility');self.assertEqual(code,0,g)
        result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'gh:fixture/repo#123','--project',str(self.root),'--dashboard','off','--branch','none'],env=self.env,capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['view']['status'],'pending_manual_acceptance')
        self.assertEqual(len((self.root/'.synthetic-calls.jsonl').read_text().splitlines()),4)
        self.assertFalse((self.root/'.git/nightshift/ticket-budgets').exists())
    def test_browser_failure_reasons_and_csrf(self):
        code,a=self.cli('assess','demo','implement');self.assertEqual(code,1)
        status,b=self.http('/api/operations',dict(action='assess',task='demo',operation='implement'));self.assertEqual(a,b)
        body=dict(action='authorize',task='demo',operations=['implement'],binding=a['binding'],operator='synthetic',request='blocked')
        status,b=self.http('/api/operations',body);self.assertEqual(status,409);self.assertIn('missing_current_results',b['error'])
        self.assertEqual(self.http('/api/operations',body,token=False)[0],403)
        self.assertFalse((self.root/'.synthetic-calls.jsonl').exists())


if __name__=='__main__':unittest.main()
