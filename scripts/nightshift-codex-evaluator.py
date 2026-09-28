#!/usr/bin/env python3
"""Pinned native Codex subscription evaluator with verified empty tool surface."""
import copy
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
import time

VERSION = 'codex-cli 0.155.1'


def parse(raw, proof):
    if not isinstance(raw,str): raise ValueError('evaluation_codex_response')
    messages=[]; completed=0; started=0; usage=None
    for line in raw.splitlines():
        if not line.strip(): continue
        event=proof.parse_json(line)
        if not isinstance(event,dict): raise ValueError('evaluation_codex_response')
        kind=event.get('type')
        if kind=='thread.started': continue
        if kind=='turn.started':
            started+=1
            if started!=1 or completed: raise ValueError('evaluation_codex_response')
        elif kind in ('item.started','item.updated','item.completed'):
            item=event.get('item')
            if not isinstance(item,dict): raise ValueError('evaluation_codex_response')
            if item.get('type') not in ('agent_message','reasoning') or item.get('tool_calls') or item.get('function_call'):
                raise ValueError('evaluation_tool_request')
            if completed or not started: raise ValueError('evaluation_codex_response')
            if kind=='item.completed' and item['type']=='agent_message':
                if not isinstance(item.get('text'),str): raise ValueError('evaluation_codex_response')
                messages.append(item['text'])
        elif kind=='turn.completed':
            completed+=1
            if completed!=1 or started!=1: raise ValueError('evaluation_codex_response')
            reported=event.get('usage')
            if not isinstance(reported,dict): raise ValueError('evaluation_usage')
            usage={}
            for key in ('input_tokens','output_tokens'):
                value=reported.get(key)
                if value is not None and (type(value) is not int or value<0): raise ValueError('evaluation_usage')
                usage[key]=value
        elif kind in ('error','turn.failed'):
            raise ValueError('evaluation_codex_response')
        else:
            raise ValueError('evaluation_codex_response')
    if completed!=1 or len(messages)!=1: raise ValueError('evaluation_codex_response')
    return proof.parse_json(messages[0]),usage


def feature_flags(raw):
    flags=[]; seen=set()
    for line in raw.decode().splitlines():
        parts=line.split()
        if len(parts)<3 or not re.fullmatch(r'[a-z0-9_.]+',parts[0]) or parts[-1] not in ('true','false'):
            raise ValueError('evaluation_codex_capabilities')
        name=parts[0]
        if name in seen: raise ValueError('evaluation_codex_capabilities')
        seen.add(name)
        if 'deprecated' in parts:
            if parts[-1]!='false': raise ValueError('evaluation_codex_capabilities')
            continue
        if 'removed' not in parts and name!='skip_host_skill_discovery': flags.extend(['--disable',name])
    if 'skip_host_skill_discovery' not in seen: raise ValueError('evaluation_codex_capabilities')
    return flags+['--enable','skip_host_skill_discovery']


def write_private(path, value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream: json.dump(value,stream,allow_nan=False)


def run(model, system, payload, schema, routing, policy, on_launch, proof, started):
    """One authenticated CLI launch after an unauthenticated local capability probe."""
    config=routing.get('codex_evaluation',{})
    if not isinstance(config,dict) or set(config)-{'model_catalog_file','auth_file','reasoning_effort'}:
        raise ValueError('evaluation_codex_configuration')
    original_home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
    catalog_path=Path(config.get('model_catalog_file',str(original_home/'models_cache.json')))
    catalog=proof.read_json(catalog_path)
    models=catalog.get('models') if isinstance(catalog,dict) else None
    if not isinstance(models,list): raise ValueError('evaluation_codex_catalog')
    matches=[item for item in models if isinstance(item,dict) and item.get('slug')==model]
    if len(matches)!=1: raise ValueError('evaluation_codex_catalog')
    selected=copy.deepcopy(matches[0])
    selected.update(apply_patch_tool_type=None,shell_type='disabled',experimental_supported_tools=[],tool_mode='direct',
                    use_responses_lite=False,prefer_websockets=False,multi_agent_version=None,include_skills_usage_instructions=False,
                    include_apps_usage_instructions=False,include_plugin_usage_instructions=False,
                    supports_parallel_tool_calls=False,supports_search_tool=False,
                    base_instructions=system,model_messages={'instructions_template':system,'instructions_variables':None})
    executable=proof.resolved_runtime('codex')
    if not executable: raise ValueError('evaluation_codex_runtime')
    executable_hash=proof.file_hash(Path(executable).resolve(strict=True))
    def remaining(cap=None):
        value=policy['timeout_seconds']-(time.monotonic()-started)
        if value<=0: raise ValueError('evaluation_timeout')
        return min(cap,value) if cap else value
    # Explicit allowlist prevents inherited providers, API credentials, proxies,
    # remote sessions, plugins or external runners from altering this adapter.
    env={key:value for key,value in os.environ.items() if key in ('PATH','LANG','LC_ALL','LC_CTYPE','TMPDIR','SYSTEMROOT')}
    with tempfile.TemporaryDirectory(prefix='nightshift-codex-evaluator-') as temporary:
        directory=Path(temporary).resolve(); env.update(HOME=str(directory),CODEX_HOME=str(directory))
        version=proof.bounded_process([executable,'--version'],directory,env,remaining(10),policy['output_bytes'])
        if version['reason'] or version['returncode']!=0 or version['stdout'].decode().strip()!=VERSION:
            raise ValueError('evaluation_codex_version')
        features=proof.bounded_process([executable,'features','list'],directory,env,remaining(10),policy['output_bytes'])
        if features['reason'] or features['returncode']!=0: raise ValueError('evaluation_codex_capabilities')
        flags=feature_flags(features['stdout'])
        model_path=directory/'models.json'; schema_path=directory/'verdict.schema.json'
        write_private(model_path,{'models':[selected]});write_private(schema_path,schema)
        argv=[executable,'exec','--ignore-user-config','--ignore-rules','--skip-git-repo-check','--ephemeral',
              '--sandbox','read-only','--json','--color','never','--model',model,'--output-schema',str(schema_path),
              '-c','model_catalog_json='+json.dumps(str(model_path)),
              '-c','web_search="disabled"','-c','suppress_unstable_features_warning=true','-c','tools.update_plan.enabled=false',
              '-c','tools.experimental_request_user_input.enabled=false',*flags]
        effort=config.get('reasoning_effort')
        if effort is not None:
            allowed={item.get('effort') for item in selected.get('supported_reasoning_levels',[]) if isinstance(item,dict)}
            if not isinstance(effort,str) or effort not in allowed: raise ValueError('evaluation_codex_configuration')
            argv+=['-c','model_reasoning_effort='+json.dumps(effort)]
        captured=[]
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4*1024*1024:
                    self.send_error(400);return
                try: captured.append(proof.parse_json(self.rfile.read(length)))
                except (ValueError,proof.Invalid): pass
                body=b'{"error":{"message":"offline capability probe complete"}}'
                self.send_response(400);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.daemon_threads=True
        worker=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.05},daemon=True);worker.start()
        try:
            probe_argv=argv+['-c','model_provider="nightshift_probe"','-c','model_providers.nightshift_probe.name="Offline capability probe"',
                            '-c',f'model_providers.nightshift_probe.base_url="http://127.0.0.1:{server.server_port}/v1"',
                            '-c','model_providers.nightshift_probe.wire_api="responses"',
                            '-c','model_providers.nightshift_probe.requires_openai_auth=false',
                            '-c','model_providers.nightshift_probe.request_max_retries=0',
                            '-c','model_providers.nightshift_probe.stream_max_retries=0','Return an empty object.']
            proof.bounded_process(probe_argv,directory,env,remaining(15),policy['output_bytes'])
        finally:
            server.shutdown();server.server_close();worker.join(timeout=1)
        if not captured: raise ValueError('evaluation_codex_probe_unavailable')
        if (any(not isinstance(request,dict) or request.get('tools') not in (None,[])
                or request.get('model')!=model for request in captured)):
            raise ValueError('evaluation_codex_tools_unverified')
        # Read credentials only after the unauthenticated wire capability check.
        auth_path=proof.private_file(Path(config.get('auth_file',str(original_home/'auth.json'))).absolute())
        info=auth_path.stat()
        if info.st_uid!=os.geteuid() or info.st_mode & 0o077: raise ValueError('evaluation_auth_permissions')
        auth=proof.read_json(auth_path)
        if (not isinstance(auth,dict) or auth.get('auth_mode')!='chatgpt' or auth.get('OPENAI_API_KEY')
                or not isinstance(auth.get('tokens'),dict) or not isinstance(auth['tokens'].get('access_token'),str)
                or not auth['tokens']['access_token']):
            raise ValueError('evaluation_subscription')
        write_private(directory/'auth.json',{key:auth[key] for key in ('auth_mode','tokens','last_refresh') if key in auth})
        login=proof.bounded_process([executable,'login','status'],directory,env,remaining(10),policy['output_bytes'])
        if login['reason'] or login['returncode']!=0 or b'Logged in using ChatGPT' not in login['stdout']+login.get('stderr',b''):
            raise ValueError('evaluation_subscription')
        if proof.file_hash(Path(executable).resolve(strict=True))!=executable_hash:
            raise ValueError('evaluation_codex_version')
        prompt=json.dumps(payload,ensure_ascii=False)
        if len(prompt.encode())>96000: raise ValueError('evaluation_input_limit')
        transport=proof.bounded_process(argv+['-c','model_provider="openai"','-c','forced_login_method="chatgpt"',
                    prompt],
                    directory,env,remaining(),policy['output_bytes'],on_launch)
        if transport['reason'] or transport['returncode']!=0:
            error=transport.get('stderr',b'').lower()
            category=('evaluation_timeout' if transport['reason']=='runtime_timeout' else
                      'evaluation_output_limit' if transport['reason']=='runtime_output_limit' else
                      'evaluation_codex_configuration' if b'error loading configuration' in error or b'reserved built-in' in error else
                      'evaluation_subscription' if any(x in error for x in (b'not logged',b'unauthorized',b'authentication',b'401')) else
                      'evaluation_capacity' if any(x in error for x in (b'rate limit',b'429',b'quota')) else
                      'evaluation_codex_network' if any(x in error for x in (b'connection',b'certificate',b'tls error')) else
                      'evaluation_transport')
            transport['failure_reason']=category
            transport['diagnostics']={'phase':'execution','returncode':transport['returncode'],
                'category':category,'stderr_sha256':hashlib.sha256(transport.get('stderr',b'')).hexdigest()}
        transport['capability']={'version':VERSION,'executable_sha256':executable_hash,
            'model_catalog_sha256':proof.digest({'models':[selected]}),'features_sha256':hashlib.sha256(features['stdout']).hexdigest(),
            'empty_tool_surface_verified':True,'billing':'subscription','wire_profile':'responses-text-v1'}
        return transport
