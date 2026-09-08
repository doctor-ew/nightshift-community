#!/usr/bin/env bash
# Contract and admission tests; exact fixture sources remain outside GREEN context.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
from pathlib import Path
import json,os,subprocess,sys,tempfile,unittest
ROOT=Path(sys.argv.pop(1)).resolve()
class BehaviorProofAdmission(unittest.TestCase):
    def test_green_without_task_proof_never_launches_provider(self):
        with tempfile.TemporaryDirectory(prefix='nightshift-proof-admission-') as tmp:
            base=Path(tmp).resolve();binary=base/'bin';binary.mkdir();calls=base/'calls'
            stub=binary/'claude'
            stub.write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys
with pathlib.Path(os.environ['FIXTURE_CALLS']).open('a') as log:log.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1:2]==['auth']:
 print(json.dumps({'loggedIn':True,'authMethod':'claude.ai','apiProvider':'firstParty'}));sys.exit(0)
print(json.dumps({'structured_output':{'status':'SUCCESS','reason':'','attempts':1,'artifacts':{'branch':'fixture','diff':'','provider':'claude','model':'fixture'},'rules_fired':[],'results':{'files_changed':[]}}}))
''');stub.chmod(0o755)
            source=base/'input.md';source.write_text('Implement the approved public acceptance contract. Required behavioral proof has not been established.')
            route=json.loads((ROOT/'routing.json').read_text());route['roles']['nightshift-engineer']['gears']['1']={'provider':'claude','model':'fixture'}
            routing=base/'routing.json';routing.write_text(json.dumps(route))
            env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],FIXTURE_CALLS=str(calls),NIGHTSHIFT_ROUTING_FILE=str(routing),NIGHTSHIFT_PROJECT_DIR=str(base),NIGHTSHIFT_TELEMETRY_DIR='off')
            for key in ('CLAUDE_PROJECT_DIR','NIGHTSHIFT_ROLE_CHILD','NIGHTSHIFT_RUN_DIR'):env.pop(key,None)
            result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-agent.sh'),'nightshift-engineer','--gear','1','--auth','subscription','--in',str(source),'--out',str(base/'report.json')],env=env,cwd=base,capture_output=True,text=True)
            if calls.exists():
                print('Observed provider/auth calls before proof admission:',len(calls.read_text().splitlines()))
            self.assertNotEqual(result.returncode,0,'GREEN dispatcher accepted work without mandatory task-bound proof')
            self.assertFalse(calls.exists(),'Missing required task/proof launched provider authentication or execution')
class BehaviorProofSchema(unittest.TestCase):
    def setUp(self):
        self.helper=ROOT/'scripts/nightshift-behavior-proof.py'
        if not self.helper.is_file():self.skipTest('UNIMPLEMENTED helper; missing file is not behavioral RED')
        self.temp=tempfile.TemporaryDirectory(prefix='nightshift-proof-schema-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.task='fixture'
        self.path=self.base/'docs'/self.task;self.path.mkdir(parents=True)
        self.scenarios=self.path/'behavior-scenarios.json'
        self.app={'kind':'deterministic','rationale':'Observable pure logic contract','risks':['deterministic_logic'],'review':None}
        self.document={'version':1,'task':self.task,'ac_ids':['AC-1'],'author':{'provider':'codex','author_id':'fixture-author'},'applicability':dict(self.app),'runtime':None,'prototype_files':[],'cases':[{'id':'case-1','ac_ids':['AC-1'],'required':True,'applicability':dict(self.app),'given':'An input outside the accepted range','when':'Validate the input','then':'Reject the input','forbidden':['Accept the invalid input'],'input':None,'expected':[],'prohibited':[],'counterexamples':['The exact boundary immediately beyond the accepted range'],'visibility':'public'}],'heldout':None}
        self.env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        self.env.pop('CLAUDE_PROJECT_DIR',None);self.env.pop('NIGHTSHIFT_PROJECT_DIR',None)

    def invoke(self,*args,task=True):
        command=[sys.executable,str(self.helper),*args,'--project',str(self.base)]
        if task:command+=['--task',self.task]
        result=subprocess.run(command,capture_output=True,text=True,env=self.env,cwd=self.base)
        self.assertNotIn(str(self.base),result.stdout+result.stderr)
        self.assertIsInstance(json.loads(result.stdout),dict)
        return result

    def write(self):self.scenarios.write_text(json.dumps(self.document))

    def test_schema_only_validates_before_review(self):
        self.write();result=self.invoke('validate','--scenarios',str(self.scenarios))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_missing_coverage_and_optional_coverage_rejected(self):
        self.document['ac_ids'].append('AC-2');self.write()
        self.assertNotEqual(self.invoke('validate','--scenarios',str(self.scenarios)).returncode,0)
        self.document['cases'][0]['ac_ids'].append('AC-2');self.document['cases'][0]['required']=False;self.write()
        self.assertNotEqual(self.invoke('validate','--scenarios',str(self.scenarios)).returncode,0)

    def test_duplicate_json_keys_and_unknown_schema_fields(self):
        self.write();text=self.scenarios.read_text();self.scenarios.write_text(text[:-1]+',"version":1}')
        self.assertEqual(self.invoke('validate','--scenarios',str(self.scenarios)).returncode,64)
        self.document['unknown_field']='must reject';self.write()
        self.assertEqual(self.invoke('validate','--scenarios',str(self.scenarios)).returncode,64)

    def test_risk_cannot_be_downgraded(self):
        self.document['cases'][0]['applicability']['risks']=['prompt_behavior'];self.write()
        self.assertNotEqual(self.invoke('validate','--scenarios',str(self.scenarios)).returncode,0)

    def test_config_defaults_and_finite_bounds(self):
        result=self.invoke('validate','--config-only',task=False);self.assertEqual(result.returncode,0,result.stdout)
        config=self.base/'.nightshift.toml'
        for value in ('development_calls = true','development_calls = 0','final_calls = 65','repairs = 3','infrastructure_failures = 3','timeout_seconds = 121','output_bytes = 1048577','force_prompt = 1','unknown = 1','version = 2'):
            with self.subTest(value=value):
                config.write_text('[behavior_proof]\n'+value+'\n')
                self.assertEqual(self.invoke('validate','--config-only',task=False).returncode,64)

    def test_canonical_invalid_manifest_never_falls_back(self):
        (self.base/'nightshift.toml').write_text('[behavior_proof]\nversion=1\n')
        (self.base/'.nightshift.toml').write_text('broken = [')
        self.assertEqual(self.invoke('validate','--config-only',task=False).returncode,64)

    def test_unsafe_task_and_non_git_gate_block(self):
        result=self.invoke('gate','--gate','development');self.assertNotEqual(result.returncode,0)
        self.task='../escape';self.write()
        self.assertEqual(self.invoke('validate','--scenarios',str(self.scenarios)).returncode,64)

unittest.main(verbosity=2)
PY
