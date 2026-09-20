#!/usr/bin/env bash
set -euo pipefail
python3 - "$(cd "$(dirname "$0")/.." && pwd)" <<'PY'
import importlib.util, json, os, pathlib, subprocess, sys, tempfile, time
root=pathlib.Path(sys.argv[1])
spec=importlib.util.spec_from_file_location('actions',root/'scripts/nightshift-console-actions.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
with tempfile.TemporaryDirectory(prefix='nightshift-actions-') as temp:
    project=pathlib.Path(temp)/'project';project.mkdir()
    def git(*args):subprocess.run(['git','-C',str(project),*args],check=True,capture_output=True)
    git('init','-q');git('config','user.name','fixture');git('config','user.email','fixture@local')
    (project/'README.md').write_text('fixture');git('add','.');git('commit','-qm','fixture')
    receipt=json.loads(subprocess.check_output(['bash',str(root/'scripts/nightshift-worktree.sh'),'prepare','42','--project',str(project)],text=True))
    target=pathlib.Path(receipt['worktree']);docs=target/'docs/42';docs.mkdir(parents=True);(docs/'SPEC.md').write_text('retained spec')
    settings=dict(ref='gh:42',provider='claude',model='sonnet',policy='claude-only',auth='subscription',branch='auto',base='',push=True,pr=True)
    module.save(project,'42',settings)
    state=module.state(project,'42');assert not state['running']
    module.save(project,'fresh',dict(settings,ref='spec:docs/fresh.md'))
    assert module.list_tickets(project)[0]['task']=='fresh', 'newest ticket must precede old failures'
    factory_agents=project/'.nightshift/agents';factory_agents.mkdir(parents=True)
    sleeper=subprocess.Popen(['bash','-c','sleep 3; :','nightshift-factory.sh',settings['ref']])
    try:
        (factory_agents/'factory-test.json').write_text(json.dumps(dict(status='running',pid=sleeper.pid,ticket=dict(source_id='42'))))
        assert module.state(project,'42')['running'], 'CLI factory must be recognized'
        assert module.list_tickets(project)[0]['task']=='42', 'live ticket must appear first'
        assert not module.state(project,'fresh')['running'], 'different ticket must not inherit running status'
    finally:
        sleeper.terminate();sleeper.wait()
    assert not module.state(project,'42')['running'], 'stale lifecycle must not imply running'

    try:module.action(project,'42','stale','resume');raise AssertionError('stale settings accepted')
    except ValueError:pass
    assert module.action(project,'42',state['sha256'],'cleanup')['status']=='ready'
    assert (docs/'SPEC.md').read_text()=='retained spec'
    capture=pathlib.Path(temp)/'argv'
    factory=pathlib.Path(temp)/'factory.sh'
    factory.write_text('printf "%s\\n" "$@" > "'+str(capture)+'"\nsleep 2\n')
    module.FACTORY=factory
    started=module.action(project,'42',state['sha256'],'resume')
    assert started['status']=='running'
    first=module.state(project,'42')['launch']['pid']
    assert module.action(project,'42',state['sha256'],'resume')['status']=='running'
    assert module.state(project,'42')['launch']['pid']==first
    for _ in range(100):
        if capture.exists():break
        time.sleep(.02)
    args=capture.read_text().splitlines()
    assert args[args.index('--provider-policy')+1]=='claude-only'
    assert args[args.index('--provider')+1]=='claude'
    assert args[args.index('--model')+1]=='sonnet'
    assert args[args.index('--auth')+1]=='subscription'
    assert '--push' in args and '--pr' in args
    for _ in range(150):
        if module.state(project,'42')['launch']['status']=='exited':break
        time.sleep(.02)
    assert module.state(project,'42')['launch']['exit_code']==0
    repair=pathlib.Path(temp)/'repair.py'
    repair.write_text('import time\ntime.sleep(30)\n')
    module.REPAIR=repair
    try:module.action(project,'42',state['sha256'],'repair',provider='local');raise AssertionError('restricted provider accepted')
    except ValueError:pass
    try:module.action(project,'42',state['sha256'],'repair',provider='shell');raise AssertionError('unknown provider accepted')
    except ValueError:pass
    started=module.action(project,'42',state['sha256'],'repair',provider='claude')
    assert started['status']=='running'
    job=module.state(project,'42')['launch'];assert job['operation']=='repair' and pathlib.Path(job['evidence']).is_dir()
    assert module.action(project,'42',state['sha256'],'repair',provider='claude')['status']=='running'
    assert module.state(project,'42')['launch']['pid']==job['pid']
    assert module.action(project,'42',state['sha256'],'stop')['status']=='stopping'
    for _ in range(100):
        if not module.state(project,'42')['running']:break
        time.sleep(.02)
    assert not module.state(project,'42')['running']
    agents=target/'.nightshift/agents';agents.mkdir(parents=True)
    (agents/'active.json').write_text(json.dumps(dict(status='running',pid=os.getpid())))
    try:module.action(project,'42',state['sha256'],'resume');raise AssertionError('live worker accepted')
    except ValueError as error:assert 'worker_still_alive' in str(error)
    try:module.state(project,'../escape');raise AssertionError('path traversal accepted')
    except ValueError:pass
print('PASS: console cleanup, unchanged policy, duplicate clicks, stale settings, live workers, and task validation')
PY
