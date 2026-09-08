#!/usr/bin/env bash
# AC1-3: deterministic admission before any provider invocation; no ownership repair.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
import json, os, pathlib, shutil, subprocess, sys, tempfile
root = pathlib.Path(sys.argv[1])
failures = []
with tempfile.TemporaryDirectory(prefix='nightshift-preflight-test-') as temp:
    base = pathlib.Path(temp)
    binary = base/'bin'; binary.mkdir()
    calls = base/'calls'
    stub = binary/'codex'
    stub.write_text('#!/usr/bin/env python3\nimport os,pathlib,sys\np=pathlib.Path(os.environ["STUB_CALLS"])\nwith p.open("a") as f:f.write("call\\n")\nif sys.argv[1:3]==["login","status"]: print("Logged in using ChatGPT")\n')
    stub.chmod(0o755)
    env = dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'], STUB_CALLS=str(calls), NIGHTSHIFT_SYNC_CHECK='off', NIGHTSHIFT_DASHBOARD='off', NIGHTSHIFT_HOME=str(base/'home'))
    def git(p,*args):
        return subprocess.run(['git','-C',str(p),*args],check=True,capture_output=True,text=True).stdout
    def project(name, commit=True):
        p=base/name;p.mkdir();git(p,'init','-q');git(p,'config','user.name','fixture');git(p,'config','user.email','fixture@local')
        (p/'README.md').write_text('# fixture\n')
        (p/'.gitignore').write_text('.nightshift/\n')
        shutil.copy(root/'nightshift.toml',p/'.nightshift.toml');shutil.copy(root/'routing.json',p/'routing.json')
        if commit:git(p,'add','.');git(p,'commit','-qm','baseline')
        return p
    def inventory(p):
        return {str(f.relative_to(p)):f.read_bytes() for f in p.rglob('*') if f.is_file() and '.git' not in f.relative_to(p).parts}
    def run(p,ref,branch='auto',extra=()):
        calls.write_text('')
        before=inventory(p)
        r=subprocess.run(['bash',str(root/'scripts/nightshift-factory.sh'),ref,'--project',str(p),'--auth','subscription','--provider','codex','--branch',branch,*extra],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        assert inventory(p)==before,'AC2 caller source changed during admission'
        return r,calls.read_text()
    def blocked(label,p,ref,reason,branch='auto',extra=()):
        try:
            r,count=run(p,ref,branch,extra)
            assert r.returncode!=0,f'{label}: invalid input accepted'
            assert not count,f'{label}: provider invoked before local rejection'
            records=[]
            for line in (r.stdout+'\n'+r.stderr).splitlines():
                try:records.append(json.loads(line))
                except ValueError:pass
            assert any(isinstance(v,dict) and v.get('status')=='blocked' and v.get('reason')==reason for v in records),f'{label}: missing typed {reason} receipt'
        except (AssertionError,subprocess.TimeoutExpired) as e:failures.append(str(e))
    p=project('spec-invalid')
    blocked('AC1 missing spec',p,'spec:missing.md','SPEC_INPUT_INVALID')
    (p/'empty.md').write_text('')
    blocked('AC1 empty spec',p,'spec:empty.md','SPEC_INPUT_INVALID')
    (p/'wrong.txt').write_text('not markdown')
    blocked('AC1 wrong suffix',p,'spec:wrong.txt','SPEC_INPUT_INVALID')
    (p/'large.md').write_text('x'*(1024*1024+1))
    blocked('AC1 oversized spec',p,'spec:large.md','SPEC_INPUT_INVALID')
    blocked('AC1 no baseline',project('unborn',False),'gh:1','BASE_MISSING')
    missing=project('manifest-missing');(missing/'.nightshift.toml').unlink()
    blocked('AC1 missing manifest',missing,'gh:1','MANIFEST_MISSING')
    dirty=project('retained-dirty')
    prep=subprocess.run(['bash',str(root/'scripts/nightshift-worktree.sh'),'prepare','7','--project',str(dirty)],capture_output=True,text=True,check=True)
    receipt=json.loads(prep.stdout);target=pathlib.Path(receipt['worktree']);(target/'retained.txt').write_text('keep me')
    metadata=dirty/'.git/nightshift/worktrees/7.json';before_receipt=metadata.read_bytes();before_target=inventory(target)
    blocked('AC1 retained dirty',dirty,'gh:7','WORKTREE_COLLISION')
    assert metadata.read_bytes()==before_receipt and inventory(target)==before_target,'AC2 retained ownership/artifacts changed'
    unowned=project('unowned');git(unowned,'branch','nightshift/9')
    blocked('AC1 unowned branch',unowned,'gh:9','WORKTREE_COLLISION')
    good=project('valid-markdown');(good/'valid.markdown').write_text('# valid\nBuild the fixture.\n')
    try:
        result,count=run(good,'spec:valid.markdown',branch='none')
        assert result.returncode==0 and count,'AC1 valid .markdown did not reach stub provider'
    except (AssertionError,subprocess.TimeoutExpired) as e:failures.append(str(e))
    # The coordinator is an explicit typed boundary, independently usable from
    # any caller directory. Exercise its declared parser contract without models.
    coordinator=['bash',str(root/'scripts/nightshift-preflight-check.sh'),'--project',str(good),'--branch','none']
    for args,expected,reason in [(['--ref','gh:1','--ref','gh:2'],0,None),(['--ref','gh:1','--project',str(good)],64,'USAGE'),(['--ref','gh:1','--resume','unused'],64,'USAGE')]:
        response=subprocess.run(coordinator+args,env=env,capture_output=True,text=True)
        try:
            value=json.loads(response.stdout)
            assert response.returncode==expected and value.get('reason')==reason,'AC3 repeated-ref/singleton/mode contract mismatch'
        except (AssertionError,ValueError) as e:failures.append(str(e))
    invalid_resume=base/'batch-20260908-0000.json';invalid_resume.write_text('[]')
    response=subprocess.run(coordinator+['--resume',str(invalid_resume)],env=env,capture_output=True,text=True)
    try:
        value=json.loads(response.stdout)
        assert response.returncode!=0 and value.get('status')=='blocked','AC3 malformed resume must not silently admit zero tasks'
    except (AssertionError,ValueError) as e:failures.append(str(e))
if failures:
    for failure in failures:print('FAIL:',failure,file=sys.stderr)
    raise SystemExit(1)
print('PASS: factory admission and retained-state invariants')
PY
