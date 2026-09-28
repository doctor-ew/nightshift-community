#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
import json, os, pathlib, subprocess, sys, tempfile
root=pathlib.Path(sys.argv[1]); helper=root/'scripts/nightshift-provider-policy.py'
with tempfile.TemporaryDirectory(prefix='nightshift-policy-') as temp:
 base=pathlib.Path(temp).resolve(); project=base/'project';project.mkdir();home=base/'home';home.mkdir()
 env=dict(os.environ,NIGHTSHIFT_HOME=str(home),NIGHTSHIFT_PROVIDER_POLICY='standard',NIGHTSHIFT_PROJECT_DIR=str(project))
 def mode(cwd=project,**changes):
  return subprocess.run([sys.executable,str(helper),'mode'],cwd=cwd,env=dict(env,**changes),text=True,capture_output=True)
 assert mode().stdout.strip()=='standard'
 (project/'.nightshift.toml').write_text('[providers]\npolicy="claude-only"\n')
 assert mode().stdout.strip()=='claude-only'
 assert mode(NIGHTSHIFT_PROVIDER_POLICY='bogus').returncode != 0
 (project/'.nightshift.toml').write_text('[providers]\npolicy="typo"\n')
 assert mode().returncode != 0
 (project/'.nightshift.toml').write_text('[providers]\npolicy="standard"\n')
 assert mode(NIGHTSHIFT_PROVIDER_POLICY='claude-only').stdout.strip()=='claude-only'
 (home/'.nightshift.toml').write_text('[providers]\npolicy="claude-only"\n')
 assert mode().stdout.strip()=='claude-only'
 (home/'.nightshift.toml').write_text('')
 subprocess.run(['git','init','-q',str(project)],check=True)
 subprocess.run(['git','-C',str(project),'-c','user.name=fixture','-c','user.email=fixture@local','commit','--allow-empty','-qm','fixture'],check=True)
 (project/'.nightshift.toml').write_text('[providers]\npolicy="claude-only"\n')
 wt=base/'worktree'
 subprocess.run(['git','-C',str(project),'worktree','add','-q','-b','fixture',str(wt)],check=True)
 nested=wt/'nested';nested.mkdir()
 assert mode(nested,NIGHTSHIFT_PROJECT_DIR=str(nested)).stdout.strip()=='claude-only'
 # Standalone route queries also honor restrictions; no model process runs.
 selected=subprocess.run(['bash',str(root/'scripts/nightshift-route.sh'),'nightshift-code-fact-extractor','low','1','false'],env=env,cwd=project,text=True,capture_output=True,check=True)
 route=json.loads(selected.stdout);assert route['provider']=='claude' and route['gear']==1
import importlib.util
spec=importlib.util.spec_from_file_location('provider_policy',helper);policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
routing=json.loads((root/'routing.json').read_text());routing['allowed_providers']=['claude','codex']
role='nightshift-code-fact-extractor'
route=policy.select_route(routing,role,0,'standard',initial={'provider':'local','model':'fixture','gear':0})
assert route['provider'] in ('claude','codex') and route['gear']>0
route=policy.select_route(routing,role,1,'standard',author='claude',adversarial=True)
assert route['provider']=='codex'
routing['allowed_providers']=['claude']
try: policy.select_route(routing,role,1,'standard',author='claude',adversarial=True)
except ValueError: pass
else: raise AssertionError('cross-provider review must not degrade to self-review')
routing['allowed_providers']=['codex']
try: policy.select_route(routing,role,1,'claude-only')
except ValueError: pass
else: raise AssertionError('conflicting restrictions must fail')
for invalid in ([],['invalid'],['claude','claude'],{'claude':True}):
 routing['allowed_providers']=invalid
 try: policy.select_route(routing,role,1,'standard')
 except ValueError: pass
 else: raise AssertionError('invalid allowed providers accepted')
print('PASS: policy inheritance, frontier-only automatic routing and cross-provider enforcement')
PY
