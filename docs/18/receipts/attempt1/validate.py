#!/usr/bin/env python3
import argparse,hashlib,json,pathlib,sys
p=argparse.ArgumentParser();p.add_argument('fixture',choices=['claude-conflict','claude-legacy','codex-conflict','codex-legacy']);p.add_argument('report');a=p.parse_args()
base=pathlib.Path(__file__).parent;root=base/a.fixture
failures=[]
def check(condition,message):
 if not condition: failures.append(message)
baseline=json.loads((base/(a.fixture+'-baseline.json')).read_text())
for name,digest in baseline.items():
 f=root/name
 check(f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest()==digest,'Fixture changed: '+name)
r=json.loads(pathlib.Path(a.report).read_text())
provider,case=a.fixture.split('-');check(r.get('artifacts',{}).get('provider')==provider,'Wrong actual provider provenance')
reason=r.get('reason','');marker=root/'observed-argv.json'
if case=='conflict':
 check(r.get('status')=='FAIL','Conflict must report FAIL, never SUCCESS/SKIP')
 check(not marker.exists(),'A conflicting test command executed')
 check('conflict' in reason.lower() or 'disagree' in reason.lower(),'Report must identify convention conflict')
 check('AGENTS.md' in reason and 'CLAUDE.md' in reason,'Report must identify both conflicting sources')
 check(r.get('results',{}).get('passed')==0,'Conflict cannot claim passed tests')
else:
 check(r.get('status')=='SUCCESS','Legacy fixture must actually execute successfully')
 check(marker.exists(),'No execution side effect; inspection is not a pass')
 if marker.exists(): check(json.loads(marker.read_text())==['--label','two words','--mode','exact'],'Executed arguments changed')
 check(r.get('results',{}).get('passed')==1 and r.get('results',{}).get('failed')==0,'Actual fixture has exactly one passing test')
 check('CLAUDE.md' in reason and 'fixture_test.py' in reason,'Missing command and legacy source provenance')
print(json.dumps({'status':'FAIL' if failures else 'PASS','fixture':a.fixture,'failures':failures}))
sys.exit(bool(failures))
