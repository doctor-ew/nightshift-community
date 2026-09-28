#!/usr/bin/env bash
set -euo pipefail
python3 - "$(cd "$(dirname "$0")/.." && pwd)" <<'PY'
import json, pathlib, subprocess, sys, tempfile, os, shutil
root=pathlib.Path(sys.argv[1])
with tempfile.TemporaryDirectory(prefix='nightshift-cleanup-test-') as temp:
    project=pathlib.Path(temp)/'repo';project.mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(project),*args],stderr=subprocess.DEVNULL)
    git('init','-q');git('config','user.name','fixture');git('config','user.email','fixture@local')
    (project/'source.txt').write_text('original');git('add','.');git('commit','-qm','base')
    def work(operation):return subprocess.run(['bash',str(root/'scripts/nightshift-worktree.sh'),operation,'42','--project',str(project)],capture_output=True,text=True)
    prepared=work('prepare');assert prepared.returncode==0,prepared.stderr
    target=pathlib.Path(json.loads(prepared.stdout)['worktree'])
    docs=target/'docs/42';docs.mkdir(parents=True);spec=docs/'SPEC.md';spec.write_text('unfinished spec')
    def cleanup():return subprocess.run(['python3',str(root/'scripts/nightshift-cleanup.py'),'42','--project',str(project)],capture_output=True,text=True)
    assert work('check').returncode!=0
    result=cleanup();assert result.returncode==0,result.stdout
    snapshot=pathlib.Path(json.loads(result.stdout)['snapshot'])
    assert (snapshot/'docs/42/SPEC.md').read_bytes()==spec.read_bytes()
    assert work('check').returncode==0
    assert work('prepare').returncode==0
    spec.write_text('changed');assert work('check').returncode!=0
    # The launcher performs the same reconciliation before its stub provider starts.
    shutil.copy(root/'nightshift.toml',project/'.nightshift.toml')
    shutil.copy(root/'routing.json',project/'routing.json')
    binary=pathlib.Path(temp)/'bin';binary.mkdir()
    stub=binary/'claude'
    stub.write_text('#!/bin/sh\nif [ "$1" = auth ]; then echo \'{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"firstParty"}\'; else echo \'{"type":"result","subtype":"success"}\'; fi\n')
    stub.chmod(0o755)
    # Exercise cleanup before one controller-selected worker, not pipeline completion.
    handoff=pathlib.Path(temp)/'handoff.json';handoff.write_text('{}')
    env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],NIGHTSHIFT_OUTPUT_CHILD='1',NIGHTSHIFT_UPDATE_GUARD='1',NIGHTSHIFT_DASHBOARD='off',NIGHTSHIFT_HOME=str(pathlib.Path(temp)/'home'),NIGHTSHIFT_PIPELINE_STAGE='product',NIGHTSHIFT_PIPELINE_TASK='42',NIGHTSHIFT_STAGE_HANDOFF=str(handoff),NIGHTSHIFT_STAGE_RECEIPT=str(pathlib.Path(temp)/'receipt.json'))
    env['HOME']=str(pathlib.Path(temp)/'home');pathlib.Path(env['HOME']).mkdir()
    result=subprocess.run(['bash',str(root/'scripts/nightshift-factory.sh'),'gh:42','--project',str(project),'--provider','claude','--branch','auto'],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert 'resumable' in result.stderr,result.stderr
    assert spec.read_text()=='changed'
    (target/'source.txt').write_text('unreviewed source')
    assert cleanup().returncode!=0
    assert (target/'source.txt').read_text()=='unreviewed source'
    (target/'source.txt').write_text('original')
    agents=target/'.nightshift/agents';agents.mkdir(parents=True)
    (agents/'live.json').write_text(json.dumps({'status':'running','pid':os.getpid()}))
    assert cleanup().returncode!=0
    assert work('check').returncode!=0
    # Unknown tasks never acquire ownership via cleanup.
    result=subprocess.run(['python3',str(root/'scripts/nightshift-cleanup.py'),'unowned','--project',str(project)],capture_output=True)
    assert result.returncode!=0
print('PASS: preserved artifact recovery, unchanged reuse, changed-source rejection, live-worker refusal, ownership boundary')
PY
