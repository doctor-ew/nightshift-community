#!/usr/bin/env python3
"""Actual launcher/browser/Git transport; synthetic workers and local gh fixture only."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('delivery_browser_interfaces',ROOT/'tests/test-operation-interfaces.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
GH='''#!/usr/bin/env python3
import base64,hashlib,io,json,subprocess,sys,zipfile
from pathlib import Path
folder=Path(__file__).resolve().parent
settings=json.loads((folder/'delivery-host.json').read_text());args=sys.argv[1:]
with (folder/'gh-calls.jsonl').open('a') as stream:stream.write(json.dumps(dict(argv=args,request_bytes=sum(len(x.encode()) for x in args)))+'\\n')
def oid(branch):return subprocess.check_output(['git','--git-dir',settings['remote'],'rev-parse','refs/heads/'+branch],text=True).strip()
head=oid(settings['branch']) if args[:2]!=['pr','list'] or (folder/'pr.json').exists() else None
base=oid('main');merge=hashlib.sha256(((head or '')+base).encode()).hexdigest()[:40]
record=folder/'pr.json'
def actions_response(path):
 contract=settings['actions'];repo=dict(id=101,full_name='synthetic/repository')
 run_id=int(head[:8],16)+1000;attempt=2;suite=run_id+10;check_id=run_id+20;job_id=run_id+30;producer_id=run_id+40;artifact_id=run_id+50
 source=subprocess.check_output(['git','--git-dir',settings['remote'],'show',head+':app.py'],text=True)
 failed=settings.get('repair') and 'synthetic CI browser repair' not in source
 conclusion='failure' if failed else 'success'
 check=dict(name=contract['job'],head_sha=head,status='completed',conclusion=conclusion,id=check_id,app={'id':15368},check_suite={'id':suite},output={'summary':'Synthetic integration assertion requires the reviewed repair marker','text':'Synthetic expected repair marker absent'} if failed else {})
 push_check=dict(check,id=check_id+100,check_suite={'id':suite+100},conclusion='success' if failed else 'failure')
 run=dict(id=run_id,run_number=1,run_attempt=attempt,workflow_id=303,event='pull_request',head_sha=head,head_branch=settings['branch'],path=contract['workflow_path'],check_suite_id=suite,repository=repo,head_repository=repo,pull_requests=[dict(head={'sha':'mutable-field-not-proof'},base={'sha':'mutable-field-not-proof'})])
 push_run=dict(run,id=run_id+100,event='push',run_number=2,check_suite_id=suite+100)
 jobs=[dict(id=job_id,run_id=run_id,run_attempt=attempt,head_sha=head,name=contract['job'],check_run_url='https://api.github.com/repos/synthetic/repository/check-runs/'+str(check_id),status='completed',conclusion=conclusion),dict(id=producer_id,run_id=run_id,run_attempt=attempt,head_sha=head,name=contract['producer_job'],check_run_url='https://api.github.com/repos/synthetic/repository/check-runs/'+str(check_id+1),status='completed',conclusion='success')]
 proof=dict(version=1,repository=repo['full_name'],repository_id=101,head_repository_id=101,run_id=run_id,run_attempt=attempt,event='pull_request',pull_request=1,head=head,base=base,merge=merge,checkout=merge,parents=[base,head],workflow_path=contract['workflow_path'],workflow_sha=merge,workflow_sha256=contract['workflow_sha256'],producer_job=contract['producer_job'],ref='refs/pull/1/merge',head_ref=settings['branch'],base_ref='main')
 archive=io.BytesIO()
 with zipfile.ZipFile(archive,'w') as out:out.writestr(zipfile.ZipInfo('nightshift-integration.json'),json.dumps(proof,sort_keys=True).encode())
 blob=archive.getvalue()
 artifact=dict(id=artifact_id,name=contract['artifact_prefix']+'-'+str(run_id)+'-'+str(attempt),expired=False,size_in_bytes=len(blob),digest='sha256:'+hashlib.sha256(blob).hexdigest(),workflow_run=dict(id=run_id,repository_id=101,head_repository_id=101,head_sha=head,head_branch=settings['branch']))
 suffix=path.removeprefix('repos/synthetic/repository/')
 if suffix=='actions/runs?event=pull_request&head_sha='+head+'&per_page=100':return dict(total_count=2,workflow_runs=[push_run,run])
 if suffix=='commits/'+head+'/check-runs?filter=all&per_page=100':return dict(total_count=2,check_runs=[push_check,check])
 if suffix=='actions/runs/'+str(run_id)+'/attempts/'+str(attempt)+'/jobs?per_page=100':return dict(total_count=2,jobs=jobs)
 if suffix=='contents/'+contract['workflow_path']+'?ref='+merge:return dict(path=contract['workflow_path'],type='file',encoding='base64',size=len(base64.b64decode(settings['workflow_b64'])),content=settings['workflow_b64'])
 if suffix=='actions/runs/'+str(run_id)+'/artifacts?per_page=100':return dict(total_count=1,artifacts=[artifact])
 if suffix=='actions/artifacts/'+str(artifact_id)+'/zip':sys.stdout.buffer.write(blob);sys.exit(0)
 raise AssertionError('Unapproved synthetic Actions API: '+path)
if args[:2]==['pr','list']:
 rows=[]
 if record.exists():
  row=json.loads(record.read_text());row.update(headRefOid=head,baseRefOid=base);rows=[row]
 print(json.dumps(rows))
elif args[:2]==['pr','create']:
 assert not record.exists(),'duplicate PR creation'
 body=Path(args[args.index('--body-file')+1]).read_text()
 row=dict(number=1,headRefName=settings['branch'],headRefOid=head,baseRefName='main',baseRefOid=base,body=body,state='OPEN',url='https://example.invalid/synthetic/pr/1',headRepository={'nameWithOwner':'synthetic/repository'})
 record.write_text(json.dumps(row));print(row['url'])
elif args[:1]==['api']:
 path=args[1]
 if path=='repos/synthetic/repository/pulls/1':value=dict(number=1,head={'sha':head,'ref':settings['branch'],'repo':{'id':101,'full_name':'synthetic/repository'}},base={'sha':base,'ref':'main','repo':{'id':101,'full_name':'synthetic/repository'}},merge_commit_sha=merge,state='open',merged=False)
 elif path=='repos/synthetic/repository/git/commits/'+merge:value=dict(sha=merge,parents=[{'sha':base},{'sha':head}])
 elif path=='repos/synthetic/repository/commits/'+merge+'/check-runs':
  source=subprocess.check_output(['git','--git-dir',settings['remote'],'show',head+':app.py'],text=True)
  failed=settings.get('repair') and 'synthetic CI browser repair' not in source
  value=dict(total_count=1,check_runs=[dict(name='synthetic-integration',head_sha=merge,status='completed',conclusion='failure' if failed else 'success',id=1,app={'id':1},output={'summary':'Synthetic integration assertion requires the reviewed repair marker','text':'Synthetic expected repair marker absent'} if failed else {})])
 elif settings.get('actions'):value=actions_response(path)
 else:raise AssertionError('Unapproved synthetic API: '+path)
 print(json.dumps(value))
else:raise AssertionError('Unapproved synthetic gh command: '+repr(args))
'''

def run():
    evidence=Path(os.environ.get('NIGHTSHIFT_DELIVERY_BROWSER_ARTIFACTS',ROOT/'test-output/delivery-browser'));evidence.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nightshift-delivery-browser-') as directory:
        base_dir=Path(directory).resolve();root=base_dir/'project';root.mkdir()
        env=f.isolated(root);bin=root/'.nightshift-fixture-bin'
        runtime_root=ROOT;launcher=['bash',str(ROOT/'scripts/nightshift-factory.sh')];server_script=ROOT/'dashboard/server.py'
        installation=os.environ.get('NIGHTSHIFT_DELIVERY_BROWSER_INSTALL')=='1'
        if installation:
            runtime_root=base_dir/'source'
            subprocess.run(['git','clone','--quiet','--local','--no-hardlinks',str(ROOT),str(runtime_root)],check=True)
            expected=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
            actual=subprocess.check_output(['git','-C',str(runtime_root),'rev-parse','HEAD'],text=True).strip()
            assert actual==expected,'temporary installation must use exact committed HEAD'
            targets={key:base_dir/key for key in ('claude','codex','runtime','bin')}
            env.update(NIGHTSHIFT_HOME=str(targets['runtime']),CODEX_HOME=str(targets['codex']))
            arguments=['--runtime','all','--target',str(targets['claude']),'--codex-target',str(targets['codex']),'--nightshift-target',str(targets['runtime']),'--bin-target',str(targets['bin'])]
            for mode,flags in [('install',[]),('audit',['--check'])]:
                result=subprocess.run(['bash',str(runtime_root/'install.sh'),*flags,*arguments],env=env,capture_output=True,text=True,timeout=90)
                (evidence/(mode+'.log')).write_text(result.stdout+'\n'+result.stderr)
                assert result.returncode==0,mode+' failed; inspect retained local log'
            installed_launcher=targets['bin']/'nightshift'
            assert installed_launcher.resolve()==runtime_root/'scripts/nightshift-factory.sh'
            for name in ('nightshift-delivery.py','nightshift-delivery-compose.py','nightshift-delivery-repair.py','nightshift-delivery-actions.py'):
                assert (targets['runtime']/'scripts'/name).resolve()==runtime_root/'scripts'/name
            launcher=[str(installed_launcher)];server_script=targets['runtime']/'dashboard/server.py'
            assert server_script.resolve()==runtime_root/'dashboard/server.py'
        repair=os.environ.get('NIGHTSHIFT_DELIVERY_BROWSER_REPAIR')=='1'
        actions_mode=os.environ.get('NIGHTSHIFT_DELIVERY_BROWSER_ACTIONS')=='1'
        if repair:
            injection="if packet['operation']=='implement' and packet.get('failed_ci'):\n import difflib\n before=packet['artifacts']['app.py'];after=before+'# synthetic CI browser repair\\n'\n value['artifacts']['diff']=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='a/app.py',tofile='b/app.py'))\n"
            for provider in ('codex','claude'):
                executable=bin/provider;executable.write_text(executable.read_text().replace("if provider=='claude':",injection+"if provider=='claude':"))
        env['PLAYWRIGHT_BROWSERS_PATH']=os.environ.get('PLAYWRIGHT_BROWSERS_PATH',str(Path.home()/('Library/Caches/ms-playwright' if __import__('sys').platform=='darwin' else '.cache/ms-playwright')))
        def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.PIPE,env=env).strip()
        git('checkout','-qb','synthetic-delivery')
        remote=bin/'remote.git';subprocess.run(['git','init','--bare','-q',str(remote)],check=True,env=env)
        git('remote','add','synthetic',str(remote));base=git('rev-parse','HEAD');git('push',str(remote),base+':refs/heads/main')
        host_settings=dict(remote=str(remote),branch='synthetic-delivery',repair=repair)
        gh=bin/'gh';gh.write_text(GH);gh.chmod(0o755)
        profile=dict(version=1,remote='synthetic',remote_url=str(remote),repository='synthetic/repository',branch='synthetic-delivery',base='main',files=['app.py'],checks=[dict(name='synthetic-integration',app_id=1)],endpoint='ci',merge_policy='disabled',commit=dict(message='Synthetic browser delivery',author_name='Synthetic',author_email='synthetic@example.invalid'))
        if actions_mode:
            import base64
            workflow=(runtime_root/'.github/workflows/shellcheck.yml').read_bytes()
            contract=dict(workflow_path='.github/workflows/shellcheck.yml',workflow_sha256=hashlib.sha256(workflow).hexdigest(),job='shellcheck',producer_job='nightshift-integration-evidence',artifact_prefix='nightshift-integration')
            profile['checks']=[dict(name='shellcheck',app_id=15368,actions=contract)]
            host_settings.update(actions=contract,workflow_b64=base64.b64encode(workflow).decode())
        (bin/'delivery-host.json').write_text(json.dumps(host_settings))
        (root/'docs/demo/delivery.json').write_text(json.dumps(profile))
        (root/'app.py').write_text('def answer():\n    return 2 # synthetic reviewed delivery\n')
        (root/'operator.txt').write_text('Preserve synthetic operator staging.\n');git('add','operator.txt')
        original_index=(root/'.git/index').read_bytes()
        def cli(*args):
            p=subprocess.run([*launcher,'ops',*args,'--project',str(root)],env=env,capture_output=True,text=True,timeout=180)
            if p.returncode:raise AssertionError(p.stdout+'\n'+p.stderr)
            return json.loads(p.stdout)
        assessed=cli('assess','demo','groom-spec')
        authority=cli('authorize','demo','--recipe','factory','--binding',assessed['binding'],'--operator','synthetic-delivery-browser','--request','delivery-browser-factory',*(['--attestation','{"bounded_repair":true}'] if repair else []))
        if repair:env['NIGHTSHIFT_DELIVERY_BROWSER_REPAIR_GRANT']=authority['id']
        initial=cli('chain','demo','--grant',authority['id']);assert initial['view']['status']=='pending_manual_acceptance',initial
        initial_calls=(root/'.synthetic-calls.jsonl').read_text();assert len(initial_calls.splitlines())==4
        with (evidence/'server.log').open('w') as errors:
            server=subprocess.Popen(['python3',str(server_script),'--project',str(root),'--port','0'],env=env,stdout=subprocess.PIPE,stderr=errors,text=True)
            try:
                url=server.stdout.readline().strip();assert url.startswith('http://127.0.0.1:'),url
                env.update(NIGHTSHIFT_BROWSER_URL=url,NIGHTSHIFT_BROWSER_PROJECT=str(root),NIGHTSHIFT_DELIVERY_BROWSER_ARTIFACTS=str(evidence))
                subprocess.run(['node',str(ROOT/'dashboard/test-delivery-browser.mjs')],env=env,check=True,timeout=240)
            finally:server.terminate();server.communicate(timeout=10)
        assert (root/'.git/index').read_bytes()==original_index
        assert (root/'operator.txt').read_text()=='Preserve synthetic operator staging.\n'
        head=git('rev-parse','HEAD');assert head!=base
        assert subprocess.check_output(['git','--git-dir',str(remote),'rev-parse','refs/heads/synthetic-delivery'],text=True).strip()==head
        assert git('diff-tree','--no-commit-id','--name-only','-r',head)=='app.py'
        all_calls=(root/'.synthetic-calls.jsonl').read_text();assert all_calls.startswith(initial_calls);assert len(all_calls.splitlines())==(6 if repair else 4)
        ghcalls=[json.loads(line) for line in (bin/'gh-calls.jsonl').read_text().splitlines()]
        assert sum(row['argv'][:2]==['pr','create'] for row in ghcalls)==1
        assert not any(row['argv'][:2]==['pr','merge'] for row in ghcalls)
        view=cli('view','demo');ledger=json.loads((root/'.git/nightshift/operations/demo/state.json').read_text())
        browser=json.loads((evidence/'browser.json').read_text())
        report=dict(synthetic=True,revision=subprocess.check_output(['git','-C',str(runtime_root),'rev-parse','HEAD'],text=True).strip(),installed_mode='temporary_symlink' if installation else 'source_checkout',head=head,base=base,endpoint='ci_passed',provider_calls=len(all_calls.splitlines()),replay_provider_calls=0,requests=[json.loads(line) for line in all_calls.splitlines()],host_requests=ghcalls,pr_creates=1,merges=0,usage=view['usage'],unknown=sum(row['unknown'] for row in view['usage'].values()),browser=browser,delivery=ledger['delivery'],provider_tokens=None,provider_cache_usage=None,billed_cost=None,live_certification=False)
        (evidence/'raw-report.json').write_text(json.dumps(report,indent=2)+'\n')
        public={key:report[key] for key in ('synthetic','revision','installed_mode','endpoint','provider_calls','replay_provider_calls','requests','pr_creates','merges','usage','unknown','browser','provider_tokens','provider_cache_usage','billed_cost','live_certification')}
        public['source_revisions']={'head':head,'base':base,'initial_delivery_head':browser['initial_head']}
        public['repair_mode']=repair
        public['actions_mode']=actions_mode
        runtime_roots=['scripts','agents','contracts','routing.json','dashboard/server.py','dashboard/src','dashboard/dist']
        inventory=subprocess.check_output(['git','-C',str(runtime_root),'ls-files','--cached','--others','--exclude-standard','-z','--',*runtime_roots]).decode().split('\0')
        names=sorted({name for name in inventory if name and '__pycache__' not in Path(name).parts and not name.endswith('.pyc') and (runtime_root/name).is_file()})
        public['runtime_sha256']={name:hashlib.sha256((runtime_root/name).read_bytes()).hexdigest() for name in names}
        committed={}
        for name in names:
            blob=subprocess.run(['git','-C',str(runtime_root),'show','HEAD:'+name],capture_output=True)
            committed[name]=hashlib.sha256(blob.stdout).hexdigest() if blob.returncode==0 else None
        public['runtime_matches_commit']=public['runtime_sha256']==committed
        public['runtime_match_scope']='Runtime scripts, roles, contracts, routing, dashboard server, source and built assets; excludes compiled caches and dependency symlinks.'
        public['runtime_mismatches']=[name for name in names if public['runtime_sha256'][name]!=committed[name]]
        untracked=subprocess.check_output(['git','-C',str(runtime_root),'ls-files','--others','--exclude-standard','-z']).decode().split('\0')
        categories={}
        for name in filter(None,untracked):
            parts=Path(name).parts
            category='compiled_python_cache' if '__pycache__' in parts or name.endswith('.pyc') else 'dependency_symlink' if 'node_modules' in parts and (runtime_root/name).is_symlink() else 'retained_test_evidence' if name.startswith('test-output/') else 'other_untracked_source_or_artifact'
            categories[category]=categories.get(category,0)+1
        public['untracked_artifact_categories']=categories
        public['github_cli_requests']=[dict(command=row['argv'][:2],request_bytes=row['request_bytes']) for row in ghcalls]
        public['metric_scope']={'requests.request_bytes':'Sum UTF-8 bytes of synthetic provider CLI arguments; excludes executable and separators; not network payload or tokens.','requests.packet_bytes':'Serialized operation packet bytes; same scope as controller usage.request_bytes.','github_cli_requests':'Synthetic gh CLI argument bytes only; excludes executable, separators, and Git transport commands; not network payload.','git_transport':'Real disposable local Git transport exercised; invocation count and byte usage not measured.'}
        public['revision_dirty']=bool(subprocess.check_output(['git','-C',str(runtime_root),'status','--porcelain','--untracked-files=normal'],text=True).strip())
        public['delivery_outcomes']=[row['status'] for row in ledger['delivery'].get('compositions',{}).values()]
        if actions_mode:
            ci_receipts=[json.loads(path.read_text()) for path in (root/'.git/nightshift/operations/demo').glob('delivery-ci-*.json')]
            rows=[row for receipt in ci_receipts for row in receipt['checks']]
            assert rows and all(row['reported_head']!=row['head'] and row['actions']['run_attempt']==2 for row in rows)
            assert any(row['conclusion']=='failure' for row in rows)==repair
            assert any(row['conclusion']=='success' for row in rows)
            public['actions_evidence']=[dict(reported_head=row['reported_head'],verified_merge=row['head'],conclusion=row['conclusion'],**row['actions']) for row in rows]
            public['actions_contract']=contract
        (evidence/'report.json').write_text(json.dumps(public,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('revision','provider_calls','replay_provider_calls','unknown','pr_creates','merges','endpoint')}))

if __name__=='__main__':run()
