#!/usr/bin/env bash
# AC4-6: factory-generated per-run records, concurrency, unknowns and secret exclusion.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
import concurrent.futures, json, os, pathlib, shutil, subprocess, sys, tempfile
root=pathlib.Path(sys.argv[1]);secret='SECRETFIXTURE_CREDENTIAL_981734';prompt='PRIVATE_SOURCE_SENTINEL_56421'
with tempfile.TemporaryDirectory(prefix='nightshift-metrics-test-') as temp:
    base=pathlib.Path(temp);project=base/'project';project.mkdir();binary=base/'bin';binary.mkdir()
    def git(*args):return subprocess.run(['git','-C',str(project),*args],check=True,capture_output=True,text=True)
    git('init','-q');git('config','user.name','fixture');git('config','user.email','fixture@local')
    (project/'README.md').write_text('# fixture\n');(project/'.gitignore').write_text('.nightshift/\n')
    shutil.copy(root/'nightshift.toml',project/'.nightshift.toml');shutil.copy(root/'routing.json',project/'routing.json')
    git('add','.');git('commit','-qm','fixture')
    (project/'requirements.md').write_text('# task\n'+prompt)
    stub=binary/'codex'
    stub.write_text('''#!/usr/bin/env python3
import os,pathlib,subprocess,sys
if sys.argv[1:3]==["login","status"]: print("Logged in using ChatGPT");sys.exit(0)
assert not os.environ.get("OPENAI_API_KEY"),"billing key escaped"
if os.environ.get("STUB_ROLE_RUN")=="yes":
    project=pathlib.Path(os.environ["FIXTURE_PROJECT"]);os.chdir(project)
    state=project/".nightshift";state.mkdir(exist_ok=True)
    (state/"input.md").write_text("Do not expose PRIVATE_SOURCE_SENTINEL_56421")
    scripts=pathlib.Path(os.environ["FIXTURE_ROOT"])/"scripts"
    subprocess.run(["bash",str(scripts/"nightshift-agent.sh"),"nightshift-engineer","--gear","1","--auth","subscription","--in",str(state/"input.md"),"--out",str(state/"output.json")],check=True)
    subprocess.run(["bash",str(scripts/"nightshift-retry-increment.sh"),"fixture","RETRY_IMPLEMENT"],check=True)
print("SECRETFIXTURE_CREDENTIAL_981734")
sys.exit(int(os.environ.get("STUB_EXIT","0")))
''')
    stub.chmod(0o755)
    claude=binary/'claude'
    claude.write_text('''#!/usr/bin/env python3
import json,sys
if sys.argv[1:2]==["auth"]:
    print(json.dumps({"loggedIn":True,"authMethod":"claude.ai","apiProvider":"firstParty"}));sys.exit(0)
print(json.dumps({"type":"result","usage":{"input_tokens":7,"output_tokens":3},"result":"SECRETFIXTURE_CREDENTIAL_981734","structured_output":{"status":"SUCCESS","reason":"","attempts":1,"artifacts":{"provider":"claude","model":"sonnet","branch":"fixture","diff":""},"rules_fired":[],"results":{"files_changed":[]}}}))
''');claude.chmod(0o755)
    env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],NIGHTSHIFT_SYNC_CHECK='off',NIGHTSHIFT_DASHBOARD='off',NIGHTSHIFT_HOME=str(base/'home'),OPENAI_API_KEY=secret,FIXTURE_PROJECT=str(project),FIXTURE_ROOT=str(root))
    def run(code=0,roles=False):
        r=subprocess.run(['bash',str(root/'scripts/nightshift-factory.sh'),'spec:requirements.md','--project',str(project),'--branch','none','--auth','subscription','--provider','codex'],env=dict(env,STUB_EXIT=str(code),STUB_ROLE_RUN='yes' if roles else 'no'),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        assert r.returncode==code,f'AC6 original provider exit changed: {r.returncode} expected{code}'
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,[0,75]))
    directory=project/'.git/nightshift/runs'
    assert directory.is_dir(),'AC4 no per-run measurements persisted after actual provider executions'
    runs=[p for p in directory.iterdir() if p.is_dir()]
    assert len(runs)==2,'AC4 concurrent calls shared/clobbered a run'
    terminals=[]
    for run_dir in runs:
        records=[]
        for path in run_dir.rglob('*.json'):
            text=path.read_text();assert secret not in text and prompt not in text,'AC5 sensitive input leaked to measurements'
            data=json.loads(text)
            if isinstance(data,dict) and data.get('terminal_status') in ('provider_exited_0','provider_exited_nonzero'):records.append(data)
        assert records,'AC4 missing terminal run record'
        record=records[-1];terminals.append(record['terminal_status'])
        assert record.get('schema_version')==1,'AC4 metrics version absent'
        assert isinstance(record.get('elapsed_seconds'),(int,float)) and record['elapsed_seconds']>=0,'AC4 elapsed time not measured'
        assert record.get('preflight_reason') is None,'AC4 success fabricated preflight failure'
        assert record.get('repair_count') is None,'AC4 no observation must not invent zero repairs'
        usage=record.get('usage');assert usage is None or (usage.get('input_tokens') is None and usage.get('output_tokens') is None),'AC4 opaque stdout fabricated reported usage'
        assert record.get('run_id')==run_dir.name,'AC4 run identity mismatch'
    assert set(terminals)=={'provider_exited_0','provider_exited_nonzero'},'AC4 incorrect terminal states'
    before={p.name for p in runs}
    run(0,roles=True)
    linked=[p for p in directory.iterdir() if p.is_dir() and p.name not in before]
    assert len(linked)==1,'AC4 role work created a second unrelated run'
    records=[json.loads(p.read_text()) for p in linked[0].rglob('*.json')]
    summaries=[v for v in records if v.get('terminal_status')=='provider_exited_0']
    assert summaries and summaries[-1].get('repair_count')==1,'AC4 successful persisted repair not linked to run'
    observations=summaries[-1].get('observations',[])
    assert any(v.get('provider')=='claude' and v.get('stage')=='implement' and v.get('model')=='sonnet' for v in observations),'AC4 actual role stage/provider/model omitted'
    def reported(value):
        if isinstance(value,dict):
            if value.get('input_tokens')==7 and value.get('output_tokens')==3:return True
            return any(reported(v) for v in value.values())
        return isinstance(value,list) and any(reported(v) for v in value)
    assert reported(summaries[-1]),'AC4 genuinely reported structured usage was dropped'
    for p in linked[0].rglob('*'):
        if p.is_file():assert secret not in p.read_text() and prompt not in p.read_text(),'AC5 nested provider data leaked'
print('PASS: concurrent run metrics, unknowns, exit preservation and privacy')
PY
