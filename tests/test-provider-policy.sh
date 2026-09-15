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
print('PASS: project/global/inherited policy, invalid modes, worktree inheritance and hosted extraction')
PY
