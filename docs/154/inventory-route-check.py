import importlib.util,json,tempfile,subprocess,os
from pathlib import Path
root=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('inventory154',root/'scripts/nightshift-pipeline.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
with tempfile.TemporaryDirectory() as temporary:
    project=Path(temporary).resolve();subprocess.run(['git','-C',str(project),'init','-q'],check=True)
    (project/'routing.json').write_bytes((root/'routing.json').read_bytes())
    (project/'.nightshift.toml').write_text('[runtime]\nprovider="codex"\nmodel="fixture-default"\n')
    settings=dict(ref='gh:doctor-ew/nightshift-community#154',provider='claude',model='sonnet',policy='standard',auth='subscription',branch='auto',base='',push=False,pr=False)
    p.load('console-actions').save(project,'154',settings)
    result=p.inventory_routes(project,'154')
    assert result['stages']['product']==dict(provider='claude',model='sonnet'),result
    env={k:v for k,v in os.environ.items() if not k.startswith('NIGHTSHIFT_') and k!='CLAUDE_PROJECT_DIR'}
    env.update(NIGHTSHIFT_HOME=str(project/'home'),NIGHTSHIFT_SYNC_CHECK='off',NIGHTSHIFT_UPDATE_GUARD='1',NIGHTSHIFT_OUTPUT='verbose')
    r=subprocess.run(['bash',str(root/'scripts/nightshift-factory.sh'),'inventory','--project',str(project),'--task','154'],env=env,capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    report=json.loads(r.stdout)
    assert report['effective_stage_runtime']['product']==dict(provider='claude',model='sonnet'),report
    assert report['runtime_origin']=='saved-task-invocation'
print('Saved explicit author route overrides current project default in task inventory: pass.')
