#!/usr/bin/env python3
"""Source evaluation boundaries, using an actual loopback HTTP fixture transport."""
import sys
sys.dont_write_bytecode = True
import copy
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    result=importlib.util.module_from_spec(spec);sys.modules[name]=result;spec.loader.exec_module(result);return result
p=load('source_proof','scripts/nightshift-behavior-proof.py')
e=p.source_evaluation
fixture=load('source_fixture','tests/nightshift-behavior-fixture.py')

def contract(source='Allowed choice is allow.'):
    return {'version':1,'sources':{'S1':source},'structure':{'headings':[],'terminal':'','citation_section':'','citation_end':''},
            'criteria':[{'id':'grounded','requirement':'Choice must be supported by the source.'},{'id':'complete','requirement':'Assess the whole completion.'}],
            'evaluator':{'provider':'local','model':'fixture-judge','independence':'different-provider'}}
def valid(payload,status='pass'):
    return {'binding_sha256':payload['binding_sha256'],'criteria':[{'id':x['id'],'status':status,'quote':'allow','reason':'Source permits this choice.'} for x in payload['contract']['criteria']]}

class Boundaries(unittest.TestCase):
    def test_source_and_citation_binding(self):
        c=contract();c['structure']={'headings':['## Answer','## Sources','## END'],'terminal':'## END','citation_section':'## Sources','citation_end':'## END'}
        good='## Answer\nChoose allow [S1]\n## Sources\n[S1] Supplied source, "Allowed choice is allow."\n## END'
        self.assertEqual(e.structural(good,c),[])
        for bad in (good+'\nextra',good.replace('## Answer','## Extra'),good.replace('Choose allow [S1]','Choose allow'),good.replace('[S1] Supplied','[S2] Supplied'),good.replace('"Allowed choice is allow."','"forged excerpt"')):
            self.assertTrue(e.structural(bad,c))
        with self.assertRaises(ValueError):e.prepare(c,'[S1] Different source.\n[S2] Allowed choice is allow.',good,'system',[])
        with self.assertRaises(ValueError):e.prepare(c,'Unrelated request.',good,'system',[])
    def test_wrong_explicit_id_and_multiturn_user_only_sources(self):
        c=contract()
        with self.assertRaises(ValueError):e.prepare(c,'[S2] Allowed choice is allow.','allow','system',[])
        request='[S2] Allowed choice is allow.'
        with self.assertRaises(ValueError):e.prepare(contract(request),request,'allow','system',[])
        e.prepare(contract('Whole request.'),'Whole request.','allow','system',[])
        history=[{'role':'user','content':'[S2] Allowed choice is allow.'},{'role':'assistant','content':'[S1] Allowed choice is allow.'},{'role':'user','content':'Continue.'}]
        with self.assertRaises(ValueError):e.prepare(c,p.generation_input(history,True),'allow','system',history)
        split_history=[{'role':'user','content':'[S1] Different content.'},{'role':'assistant','content':'Continue'},{'role':'user','content':'Allowed choice is allow.'}]
        with self.assertRaises(ValueError):e.prepare(c,p.generation_input(split_history,True),'allow','system',split_history)
        history[0]['content']='[S1] Allowed choice is allow.'
        payload=e.prepare(c,p.generation_input(history,True),'allow','system',history)
        self.assertEqual(payload['input'],p.generation_input(history,True))
    def test_null_config_quote_bounds_and_pre_reservation_failures(self):
        c=contract();c['structure']=None
        with self.assertRaises(ValueError):e.validate(c)
        payload=e.prepare(contract(),'[S1] Allowed choice is allow.','allow\n'+'x'*161+'   ','system',[])
        for quote in ('   ','allow\nx','x'*161):
            value=valid(payload);value['criteria'][0]['quote']=quote
            with self.assertRaises(ValueError):e.verdict(value,payload)
        value=valid(payload);value['criteria'][0]['reason']='x'*241
        with self.assertRaises(ValueError):e.verdict(value,payload)
        for routing in (None,{'local':None},{'providers':None}):
            calls=[];value=e.judge(contract(),payload,routing,dict(p.DEFAULTS),lambda:calls.append(True),p)
            self.assertEqual(value['outcome'],'unknown');self.assertEqual(calls,[])
        p.dependencies()
        for mode in ('source','schema','storage'):
            state={};policy=dict(p.DEFAULTS)
            for operation in ('reserve','launch','finalize'):
                p.retry.proof_account(state,policy,operation,'gen',outcome='pass' if operation=='finalize' else None)
            proof=__import__('types').SimpleNamespace(project=ROOT,task='fixture',policy=policy)
            c=contract();c['structure']['terminal']='END' if mode=='storage' else ''
            if mode=='schema':c['structure']=None
            with patch.object(p,'retained_evaluation',side_effect=p.Blocked('storage')), patch.object(p,'provider_policy',return_value='standard'):
                result=p.evaluate_source(proof,state,lambda:None,'development',{'author':{'provider':'codex'}},c,
                    '[S1] Allowed choice is allow.' if mode!='source' else '[S2] Allowed choice is allow.','allow','system',[],'gen')
            self.assertEqual(result['outcome'],'unknown');self.assertEqual(state['budget']['infrastructure_failures'],1)
            self.assertEqual(state['budget']['launches']['development'],1)
            self.assertFalse(any(a['outcome']=='pending' for a in state['budget']['attempts'].values()))
    def test_claude_total_deadline(self):
        c=contract();c['evaluator'].update(provider='claude',independence='fresh-session')
        payload=e.prepare(c,'[S1] Allowed choice is allow.','allow','system',[])
        auth={'reason':None,'returncode':0,'stdout':json.dumps({'loggedIn':True,'authMethod':'claude.ai','apiProvider':'firstParty'}).encode()}
        output={'reason':None,'returncode':0,'stdout':json.dumps({'type':'result','is_error':False,'result':json.dumps(dict(valid(payload),criteria=[dict(x,quote='L1') for x in valid(payload)['criteria']]))}).encode()}
        with patch.object(p,'resolved_runtime',return_value='claude'),patch.object(p,'bounded_process',side_effect=[auth,output]) as process,patch.object(e.time,'monotonic',side_effect=[100,100,109,110]):
            value=e.judge(c,payload,{},dict(p.DEFAULTS,timeout_seconds=10),lambda:None,p)
        self.assertEqual(process.call_args_list[1].args[3],1)
    def test_exact_unique_line_compatibility(self):
        completion='Supported choice: allow.\nRepeated evidence\nRepeated evidence\n   \n'+'x'*160
        payload=e.prepare(contract(),'[S1] Allowed choice is allow.',completion,'system',[])
        permitted={'',*payload['completion_lines'],*e.unique_line_values(payload['completion_lines'],payload['completion'])}
        for reference in ('L1','Supported choice: allow.','x'*160):
            value=valid(payload)
            for item in value['criteria']:item['quote']=reference
            self.assertIn(reference,permitted)
            self.assertEqual(e.verdict(e.resolve_verdict(value,payload),payload),'pass')
        for reference in ('allow','Supported choice: allow','Supported choice: permitted.','Repeated evidence','   ','L999','x'*161,'Supported choice: allow.\nRepeated evidence'):
            value=valid(payload);value['criteria'][0]['quote']=reference
            self.assertNotIn(reference,permitted)
            with self.assertRaises(ValueError,msg=reference):e.resolve_verdict(value,payload)
        truncated=e.prepare(contract(),'[S1] Allowed choice is allow.','x'*161,'system',[])
        value=valid(truncated)
        for item in value['criteria']:item['quote']='x'*160
        with self.assertRaises(ValueError):e.resolve_verdict(value,truncated)
        self.assertNotIn('x'*160,e.unique_line_values(truncated['completion_lines'],truncated['completion']))
        for item in value['criteria']:item['quote']='L1'
        self.assertEqual(e.verdict(e.resolve_verdict(value,truncated),truncated),'pass')
        # A line ID remains unambiguous even when its text occurs more than once.
        value=valid(payload)
        for item in value['criteria']:item['quote']='L2'
        self.assertEqual(e.verdict(e.resolve_verdict(value,payload),payload),'pass')
        value['criteria'][0].update(status='fail',quote='')
        self.assertEqual(e.verdict(e.resolve_verdict(value,payload),payload),'fail')
    def test_requested_line_id_schema_and_reserved_legacy_ids(self):
        payload=e.prepare(contract(),'[S1] Allowed choice is allow.','Supported choice: allow.\nL1\nRepeated\nRepeated','system',[])
        item_schema=e.schema(payload['completion_lines'])['properties']['criteria']['items']
        self.assertEqual(set(item_schema['required']),{'id','status','line_id','reason'})
        self.assertNotIn('quote',item_schema['properties'])
        self.assertEqual(item_schema['properties']['line_id']['enum'],['','L1','L2','L3','L4'])
        for field in ('line_id','quote'):
            value=valid(payload)
            value['criteria']=[{'id':x['id'],'status':x['status'],field:'L1','reason':x['reason']} for x in value['criteria']]
            self.assertEqual(e.resolve_verdict(value,payload)['criteria'][0]['quote'],'Supported choice: allow.')
            for item in value['criteria']:item[field]='L2'
            self.assertEqual(e.resolve_verdict(value,payload)['criteria'][0]['quote'],'L1')
        for reference in ('Supported choice: allow.','Repeated','L999','L1\nL2'):
            value=valid(payload);value['criteria'][0].pop('quote');value['criteria'][0]['line_id']=reference
            with self.assertRaises(ValueError):e.resolve_verdict(value,payload)
        value=valid(payload);value['criteria'][0]['line_id']='L1'
        with self.assertRaises(ValueError):e.resolve_verdict(value,payload)
    def test_verdict_bound_to_actual_complete_matrix(self):
        payload=e.prepare(contract(),'[S1] Allowed choice is allow.','allow','system',[])
        self.assertEqual(e.verdict(valid(payload),payload),'pass')
        self.assertEqual(e.verdict(valid(payload,'unknown'),payload),'unknown')
        for edit in ('binding','missing','duplicate','quote','status','extra'):
            value=valid(payload)
            if edit=='binding':value['binding_sha256']='0'*64
            if edit=='missing':value['criteria']=[]
            if edit=='duplicate':value['criteria']*=2
            if edit=='quote':value['criteria'][0]['quote']='not in completion'
            if edit=='status':value['criteria'][0].pop('status')
            if edit=='extra':value['extra']=True
            with self.assertRaises(ValueError,msg=edit):e.verdict(value,payload)
    def test_blocks_labels_and_denominator(self):
        c=contract();c['structure']['blocks']={'start':'## Blocks','end':'## End','heading_prefix':'### ',
            'fields':['Type:','Status:'],'labels':{'Status:':['supported','unknown']},'count_prefix':'Count: ','count_suffix':' items'}
        good='## Blocks\n### One\nType: requirement\nStatus: supported\n## End\nCount: 1 items'
        self.assertEqual(e.structural(good,c),[])
        for bad in (good.replace('supported','invented'),good.replace('Count: 1','Count: 2'),good.replace('Type: requirement\n','')):
            self.assertTrue(e.structural(bad,c))
    def test_timeout_and_private_symlink(self):
        payload=e.prepare(contract(),'[S1] Allowed choice is allow.','allow','system',[])
        calls=[]
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=TimeoutError()
            value=e.judge(contract(),payload,{'local':{'backend':'omlx'}},dict(p.DEFAULTS),lambda:calls.append(True),p)
        self.assertEqual(calls,[True]);self.assertEqual(value['outcome'],'unknown');self.assertEqual(value['reason'],'evaluation_timeout')
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=__import__('http.client',fromlist=['IncompleteRead']).IncompleteRead(b'partial')
            value=e.judge(contract(),payload,{'local':{'backend':'omlx'}},dict(p.DEFAULTS),lambda:None,p)
        self.assertEqual(value['outcome'],'unknown');self.assertEqual(value['reason'],'evaluation_http_invalid')
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();external=base/'external';external.mkdir()
            (base/'nightshift-evaluation-task').symlink_to(external,target_is_directory=True)
            proof=__import__('types').SimpleNamespace(task='task')
            with self.assertRaises(p.Blocked):p.retained_evaluation(proof,{'seal':{'heldout_path':str(base/'heldout.json')}},'final','attempt',payload,{})
    def test_independence(self):
        c=contract();doc={'author':{'provider':'local'}}
        with self.assertRaises(p.Blocked):p.validate_evaluation(c,doc)
        c['evaluator']['provider']='codex'
        with self.assertRaises(p.Invalid):p.validate_evaluation(c,doc)
    def test_reservation_pending_and_separate_evaluation(self):
        p.dependencies();state={};policy=dict(p.DEFAULTS)
        p.retry.proof_account(state,policy,'reserve','gen')
        p.retry.proof_account(state,policy,'launch','gen')
        with self.assertRaises(ValueError):p.retry.proof_account(state,policy,'reserve','eval',kind='evaluation')
        p.retry.proof_account(state,policy,'finalize','gen',outcome='pass')
        p.retry.proof_account(state,policy,'reserve','eval',kind='evaluation')
        p.retry.proof_account(state,policy,'launch','eval')
        p.retry.proof_account(state,policy,'finalize','eval',outcome='unknown')
        p.retry.proof_validate(state)
        self.assertEqual(state['budget']['launches']['development'],2)
        self.assertEqual(state['budget']['infrastructure_failures'],1)

class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nightshift-source-eval-');self.addCleanup(self.tmp.cleanup)
        self.mode='pass';self.requests=[]
        outer=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if outer.mode=='chunked':
                    self.send_response(200);self.send_header('Transfer-Encoding','chunked');self.end_headers();self.wfile.write(b'zz\r\nbroken\r\n');self.close_connection=True;return
                outer.requests.append(body)
                payload=json.loads(body['messages'][1]['content'])
                value=valid(payload, 'unknown' if outer.mode=='unknown' else 'pass')
                for item in value['criteria']:item['quote']='L1'
                if outer.mode=='literal':
                    for item in value['criteria']:item['quote']=payload['completion_lines']['L1']
                if outer.mode in ('line_id','invalid_line_id'):
                    for item in value['criteria']:item['line_id']=item.pop('quote')
                    if outer.mode=='invalid_line_id':value['criteria'][0]['line_id']='L999999'
                if outer.mode=='bad_reference':value['criteria'][0]['quote']='L999999'
                if outer.mode=='fail':value['criteria'][-1]['status']='fail'
                message={'content':json.dumps(value)}
                if outer.mode in ('fence','chatter','multiple'):
                    message['content']='```json\n'+message['content']+'\n```'
                    if outer.mode=='chatter':message['content']='Here is the result: '+message['content']
                    if outer.mode=='multiple':message['content']+='\n'+message['content']
                if outer.mode=='tool':message['tool_calls']=[{'function':{'name':'escape'}}]
                if outer.mode=='invalid':message['content']='not json'
                if outer.mode=='stale':value['binding_sha256']='0'*64;message['content']=json.dumps(value)
                envelope={'choices':[{'message':message}],'usage':{'prompt_tokens':11,'completion_tokens':7}}
                if outer.mode=='null_message':envelope['choices'][0]['message']=None
                if outer.mode=='null_usage':envelope['usage']=None
                raw=json.dumps(envelope).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.fx=fixture.PrototypeFixture(ROOT,self.tmp.name)
        self.route=Path(self.fx.env['NIGHTSHIFT_ROUTING_FILE'])
        routing=json.loads(self.route.read_text());routing['local']={'backend':'openai-compatible','base_url':f'http://127.0.0.1:{server.server_port}/v1'}
        self.route.write_text(json.dumps(routing))
        public=json.loads(self.fx.scenarios.read_text());private=json.loads(self.fx.private.read_text())
        for doc in (public,private):
            for case in doc['cases']:
                case['input']='[S1] Allowed choice is allow.'
                case['evaluation']=contract()
            fixture.attest(doc)
        self.fx.private.write_bytes(fixture.canonical(private))
        public['heldout']['manifest_sha256']=fixture.digest(self.fx.private)
        self.fx.scenarios.write_bytes(fixture.canonical(fixture.attest(public)))
        subprocess.run(['bash',str(ROOT/'scripts/nightshift-tdd-spec-lock.sh'),self.fx.task],env=self.fx.env,cwd=self.fx.project,capture_output=True,check=True)
        self.fx.seal()
        self.statepath=self.fx.project/'.git/nightshift/behavior-proof/prototype/state.json'
    def state(self):return json.loads(self.statepath.read_text())
    def run_gate(self,gate='development'):
        result=self.fx.call('run','--gate',gate)
        return result,json.loads(result.stdout)
    def test_canonical_pass_private_retention_usage_and_tamper(self):
        result,receipt=self.run_gate();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        state=self.state();obs=state['observations'][-1];ev=obs['evaluations'][0]
        self.assertEqual(state['budget']['launches']['development'],3) # challenge + generation + evaluation
        self.assertEqual(obs['usage'],{'input_tokens':14,'output_tokens':9})
        self.assertEqual(len(receipt['attempt_ids']),3)
        self.assertEqual(self.requests[0]['tools'] if 'tools' in self.requests[0] else [],[])
        result,receipt=self.run_gate('final');self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        ev=self.state()['observations'][-1]['evaluations'][0];path=Path(ev['evidence']['path'])
        self.assertFalse(path.is_relative_to(self.fx.project));self.assertEqual(path.stat().st_mode&0o777,0o600)
        raw=json.loads(path.read_text());self.assertEqual(raw['payload']['completion'],self.fx.response.read_text())
        self.assertNotIn('completion',json.dumps(receipt))
        path.write_text('{}')
        self.assertNotEqual(self.fx.call('gate','--gate','final').returncode,0)
    def test_tool_request_unknown_no_free_retry(self):
        self.mode='tool';result,_=self.run_gate();self.assertNotEqual(result.returncode,0)
        before=self.state()['budget'];self.assertEqual(before['launches']['development'],3)
        self.assertEqual(before['infrastructure_failures'],1)
        self.assertEqual(before['attempts'][self.state()['observations'][-1]['evaluations'][0]['attempt_id']]['outcome'],'unknown')
    def test_removed_verdict_and_changed_routing_block(self):
        result,_=self.run_gate();self.assertEqual(result.returncode,0,result.stdout)
        state=self.state();self.passing_state=copy.deepcopy(state);state['observations'][-1]['evaluations']=[];self.statepath.write_text(json.dumps(state))
        self.assertNotEqual(self.fx.call('gate','--gate','development').returncode,0)
        self.statepath.write_text(json.dumps(self.passing_state))
        self.assertEqual(self.fx.call('gate','--gate','development').returncode,0)
        self.route.write_text(self.route.read_text()+'\n')
        self.assertNotEqual(self.fx.call('gate','--gate','development').returncode,0)
    def test_semantic_mixed_fail_blocks_and_is_terminal(self):
        self.mode='fail';result,receipt=self.run_gate()
        self.assertNotEqual(result.returncode,0);self.assertEqual(receipt['outcome'],'fail')
        state=self.state();self.assertEqual(state['observations'][-1]['evaluations'][0]['outcome'],'fail')
        self.assertNotEqual(self.fx.call('gate','--gate','development').returncode,0)
        before=state['budget'];self.mode='pass';self.run_gate()
        self.assertEqual(self.state()['budget'],before)
    def test_null_provider_envelope_finalizes_reservation(self):
        self.mode='null_message';result,_=self.run_gate()
        self.assertNotEqual(result.returncode,0)
        state=self.state();self.assertEqual(state['budget']['infrastructure_failures'],1)
        self.assertFalse(any(a['outcome']=='pending' for a in state['budget']['attempts'].values()))
    def test_malformed_chunked_transport_finalizes_reservation(self):
        self.mode='chunked';result,_=self.run_gate()
        self.assertNotEqual(result.returncode,0)
        state=self.state();self.assertEqual(state['budget']['infrastructure_failures'],1)
        self.assertEqual(state['observations'][-1]['evaluations'][0]['reason'],'evaluation_http_invalid')
        self.assertFalse(any(a['outcome']=='pending' for a in state['budget']['attempts'].values()))
    def test_private_only_contract_rejected_before_reservation(self):
        public=json.loads(self.fx.scenarios.read_text());public['cases'][0].pop('evaluation')
        self.fx.scenarios.write_bytes(fixture.canonical(fixture.attest(public)))
        subprocess.run(['bash',str(ROOT/'scripts/nightshift-tdd-spec-lock.sh'),self.fx.task],env=self.fx.env,cwd=self.fx.project,capture_output=True,check=True)
        self.assertEqual(self.fx.call('challenge','--scenarios',self.fx.scenarios,'--out',self.fx.challenge).returncode,0)
        before=self.state()['budget']
        result=self.fx.call('seal','--scenarios',self.fx.scenarios,'--challenge',self.fx.challenge,'--heldout',self.fx.private)
        self.assertNotEqual(result.returncode,0);self.assertIn('private_only_evaluation_unsupported',result.stdout)
        self.assertEqual(self.state()['budget'],before)
    def test_generation_and_evaluation_cross_binding_tamper(self):
        result,_=self.run_gate();self.assertEqual(result.returncode,0,result.stdout)
        original=self.state();obs=original['observations'][-1]
        for target in ('private_generation','completion','input','history','system_prompt','raw','evaluator_raw'):
            state=copy.deepcopy(original);item=state['observations'][-1]
            if target=='private_generation':item.pop('private_generation')
            else:
                reference=item['private_generation'] if target=='raw' else item['evaluations'][0]['evidence']
                path=Path(reference['path']);original_bytes=path.read_bytes();stored=json.loads(original_bytes)
                if target=='raw':stored['result']['raw']=stored['result']['raw'].replace('allow','deny')
                elif target=='evaluator_raw':stored['result']['raw']='NOT JSON'
                else:
                    payload=stored['payload']
                    if target=='history':payload[target]=[{'role':'user','content':'forged'}]
                    else:payload[target]='forged allow'
                    payload.pop('binding_sha256');payload['binding_sha256']=e.digest(payload)
                    stored['result']['verdict']['binding_sha256']=payload['binding_sha256']
                    item['evaluations'][0]['binding_sha256']=payload['binding_sha256']
                    item['evaluations'][0]['completion_sha256']=p.digest(payload['completion'])
                raw=fixture.canonical(stored);path.write_bytes(raw);reference['sha256']=hashlib.sha256(raw).hexdigest()
            self.statepath.write_text(json.dumps(state))
            self.assertNotEqual(self.fx.call('gate','--gate','development').returncode,0,target)
            if target!='private_generation':path.write_bytes(original_bytes)
        self.statepath.write_text(json.dumps(original))
        self.assertEqual(self.fx.call('gate','--gate','development').returncode,0)
    def test_literal_transport_replay_and_coherent_substring_tamper(self):
        self.mode='literal';result,_=self.run_gate();self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual(self.fx.call('gate','--gate','development').returncode,0)
        state=self.state();reference=state['observations'][-1]['evaluations'][0]['evidence']
        path=Path(reference['path']);stored=json.loads(path.read_text())
        self.assertEqual(stored['result']['transport_verdict']['criteria'][0]['quote'],self.fx.response.read_text())
        self.assertEqual(stored['result']['verdict']['criteria'][0]['quote'],self.fx.response.read_text())
        # Alter raw and both derived verdicts together and update the file digest.
        # An exact substring is valid quotation text but not a whole-line reference.
        for name in ('transport_verdict','verdict'):
            stored['result'][name]['criteria'][0]['quote']='allow'
        envelope=json.loads(stored['result']['raw'])
        envelope['choices'][0]['message']['content']=json.dumps(stored['result']['transport_verdict'])
        stored['result']['raw']=json.dumps(envelope)
        raw=fixture.canonical(stored);path.write_bytes(raw);reference['sha256']=hashlib.sha256(raw).hexdigest()
        self.statepath.write_text(json.dumps(state))
        self.assertNotEqual(self.fx.call('gate','--gate','development').returncode,0)
    def test_line_id_transport_replay_and_invalid_reference(self):
        self.mode='line_id';result,_=self.run_gate();self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual(self.fx.call('gate','--gate','development').returncode,0)
        state=self.state();reference=state['observations'][-1]['evaluations'][0]['evidence']
        path=Path(reference['path']);stored=json.loads(path.read_text())
        self.assertEqual(stored['result']['transport_verdict']['criteria'][0]['line_id'],'L1')
        self.assertNotIn('line_id',stored['result']['verdict']['criteria'][0])
        stored['result']['transport_verdict']['criteria'][0]['line_id']='L999999'
        envelope=json.loads(stored['result']['raw']);envelope['choices'][0]['message']['content']=json.dumps(stored['result']['transport_verdict'])
        stored['result']['raw']=json.dumps(envelope)
        raw=fixture.canonical(stored);path.write_bytes(raw);reference['sha256']=hashlib.sha256(raw).hexdigest()
        self.statepath.write_text(json.dumps(state))
        self.assertNotEqual(self.fx.call('gate','--gate','development').returncode,0)
        self.mode='invalid_line_id'
        payload=e.prepare(contract(),'[S1] Allowed choice is allow.','allow','system',[])
        result=e.judge(contract(),payload,json.loads(self.route.read_text()),dict(p.DEFAULTS),lambda:None,p)
        self.assertEqual(result['outcome'],'unknown');self.assertEqual(result['reason'],'evaluation_quote_reference')
    def test_multiturn_generation_history_rechecked(self):
        public=json.loads(self.fx.scenarios.read_text());private=json.loads(self.fx.private.read_text())
        for doc in (public,private):
            doc['runtime']['profile']=p.MULTITURN_PROFILE
            for case in doc['cases']:
                case['input']=[{'input':'[S1] Allowed choice is allow.','expected':case['expected'],'prohibited':case['prohibited']},
                               {'input':'Continue using the earlier source.','expected':case['expected'],'prohibited':case['prohibited']}]
            fixture.attest(doc)
        self.fx.private.write_bytes(fixture.canonical(private));public['heldout']['manifest_sha256']=fixture.digest(self.fx.private)
        self.fx.scenarios.write_bytes(fixture.canonical(fixture.attest(public)))
        subprocess.run(['bash',str(ROOT/'scripts/nightshift-tdd-spec-lock.sh'),self.fx.task],env=self.fx.env,cwd=self.fx.project,capture_output=True,check=True)
        self.fx.seal();result,_=self.run_gate();self.assertEqual(result.returncode,0,result.stdout)
        state=self.state();turns=state['observations'][-1]['turns']
        self.assertEqual(len(turns),2);self.assertIsNotNone(turns[0]['private_generation'])
        evidence=json.loads(Path(turns[-1]['evaluations'][0]['evidence']['path']).read_text())
        self.assertEqual(evidence['payload']['history'][1]['role'],'assistant')
        turns[0].pop('private_generation');self.statepath.write_text(json.dumps(state))
        self.assertNotEqual(self.fx.call('gate','--gate','development').returncode,0)
    def test_strict_optin_wrapper_and_null_usage(self):
        payload=e.prepare(contract(),'[S1] Allowed choice is allow.','allow','system',[])
        routing=json.loads(self.route.read_text());routing['local']['evaluation_response_normalization']='json-or-single-fence-v1'
        for mode,expected in (('fence','pass'),('chatter','unknown'),('multiple','unknown'),('null_usage','unknown'),('bad_reference','unknown')):
            self.mode=mode
            value=e.judge(contract(),payload,routing,dict(p.DEFAULTS),lambda:None,p)
            self.assertEqual(value['outcome'],expected,(mode,value))
    def test_configured_reasoning_controls_are_forwarded(self):
        payload=e.prepare(contract(),'[S1] Allowed choice is allow.','allow','system',[])
        routing=json.loads(self.route.read_text())
        routing['local'].update(reasoning_effort='none',evaluation_chat_template_kwargs={'enable_thinking':False})
        result=e.judge(contract(),payload,routing,dict(p.DEFAULTS),lambda:None,p)
        self.assertEqual(result['outcome'],'pass')
        self.assertEqual(self.requests[-1]['reasoning_effort'],'none')
        self.assertEqual(self.requests[-1]['chat_template_kwargs'],{'enable_thinking':False})
        for key,value in (('reasoning_effort',None),('reasoning_effort',True),('reasoning_effort',float('nan')),('evaluation_chat_template_kwargs',{'enable_thinking':'false'}),('evaluation_chat_template_kwargs',{'other':True})):
            bad=copy.deepcopy(routing);bad['local'][key]=value;calls=[]
            result=e.judge(contract(),payload,bad,dict(p.DEFAULTS),lambda:calls.append(True),p)
            self.assertEqual(result['outcome'],'unknown');self.assertEqual(result['reason'],'evaluation_reasoning_config');self.assertEqual(calls,[])
    def test_malformed_and_stale_verdicts_block(self):
        # Direct bounded transports exercise different invalid envelopes without resetting a proof budget.
        payload=e.prepare(contract(),'[S1] Allowed choice is allow.','allow','system',[])
        for mode in ('invalid','stale','unknown'):
            self.mode=mode;calls=[]
            value=e.judge(contract(),payload,json.loads(self.route.read_text()),dict(p.DEFAULTS),lambda:calls.append(True),p)
            self.assertEqual(calls,[True]);self.assertEqual(value['outcome'],'unknown')

if __name__=='__main__':unittest.main(verbosity=2)
