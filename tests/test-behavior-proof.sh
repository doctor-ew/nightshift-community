#!/usr/bin/env bash
# Contract and admission tests; exact fixture sources remain outside GREEN context.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
from pathlib import Path
import concurrent.futures,copy,hashlib,importlib.util,json,os,subprocess,sys,tempfile,unittest
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
            for task_args in ([],['--task','fixture']):
                with self.subTest(task_supplied=bool(task_args)):
                    if calls.exists():calls.unlink()
                    result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-agent.sh'),'nightshift-engineer',*task_args,'--gear','1','--auth','subscription','--in',str(source),'--out',str(base/'report.json')],env=env,cwd=base,capture_output=True,text=True)
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
        self.document={'version':1,'task':self.task,'ac_ids':['AC-1'],'author':{'provider':'codex','author_id':'fixture-author'},'applicability':dict(self.app),'runtime':None,'prototype_files':[],'cases':[{'id':'case-1','ac_ids':['AC-1'],'required':True,'applicability':dict(self.app),'given':'An input outside the accepted range','when':'Validate the input','then':'Reject the input','forbidden':'Accept the invalid input','input':None,'expected':[],'prohibited':[],'counterexamples':['The exact boundary immediately beyond the accepted range'],'visibility':'public'}],'heldout':None}
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

class BehaviorProofEvidence(unittest.TestCase):
    def setUp(self):
        self.helper=ROOT/'scripts/nightshift-behavior-proof.py'
        if not self.helper.is_file():self.skipTest('UNIMPLEMENTED helper; not behavioral RED')
        sys.dont_write_bytecode=True
        spec=importlib.util.spec_from_file_location('fixture_builder',ROOT/'tests/nightshift-behavior-fixture.py')
        self.builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.builder)
        self.temp=tempfile.TemporaryDirectory(prefix='nightshift-proof-evidence-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.project=self.base/'project'
        self.fixture=self.builder.prepare(ROOT,self.project,require_gate=False)
        self.env=dict(os.environ,NIGHTSHIFT_PROJECT_DIR=str(self.project),PYTHONDONTWRITEBYTECODE='1');self.env.pop('CLAUDE_PROJECT_DIR',None)
        self.evidence=json.loads(Path(self.fixture['evidence_path']).read_text())

    def invoke(self,operation,*args):
        result=subprocess.run([sys.executable,str(self.helper),operation,'--project',str(self.project),'--task','fixture',*args],env=self.env,cwd=self.project,capture_output=True,text=True)
        self.assertNotIn(str(self.base),result.stdout+result.stderr)
        self.assertIsInstance(json.loads(result.stdout),dict)
        return result

    def evidence_file(self,value,name='candidate.json'):
        path=self.project/'docs/fixture'/name;path.write_text(json.dumps(value));return str(path)

    def test_relevant_red_admits_development_but_never_final(self):
        self.assertEqual(self.invoke('gate','--gate','development').returncode,0)
        self.assertNotEqual(self.invoke('gate','--gate','final').returncode,0)

    def test_evidence_rejects_forged_integrity_and_irrelevant_failure(self):
        mutations=[('observer',{'provider':'codex','author_id':'fixture-spec-author'}),
                   ('scenario_ids',['unreviewed-case']),('red_lock_sha','0'*40),
                   ('assertions',{'kind':'import_error','passed':0,'failed':1}),
                   ('assertions',{'kind':'relevant_assertion','passed':0,'failed':0}),
                   ('tests',[{'path':'tests/test_fixture_fixture.py','sha256':'0'*64}]),
                   ('log',{'path':self.evidence['log']['path'],'sha256':'0'*64})]
        for field,value in mutations:
            with self.subTest(field=field,value=value):
                evidence=copy.deepcopy(self.evidence);evidence[field]=value
                self.assertNotEqual(self.invoke('record-red','--evidence',self.evidence_file(evidence)).returncode,0)

    def test_log_symlink_and_oversize_are_rejected(self):
        link=self.base/'linked.log';link.symlink_to(self.evidence['log']['path'])
        large=self.base/'large.log';large.write_bytes(b'x'*(4*1024*1024+1))
        for path in (link,large):
            with self.subTest(path=path.name):
                evidence=copy.deepcopy(self.evidence);evidence['log']={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                self.assertNotEqual(self.invoke('record-red','--evidence',self.evidence_file(evidence)).returncode,0)

    def test_unreviewed_and_same_author_seals_block(self):
        path=Path(self.fixture['scenario_path']);original=json.loads(path.read_text())
        for same_author in (False,True):
            with self.subTest(same_author=same_author):
                document=copy.deepcopy(original)
                for app in [document['applicability'],*[c['applicability'] for c in document['cases']]]:
                    if not same_author:app['review']=None
                    else:app['review'].update(reviewer_provider='codex',reviewer_author_id='fixture-spec-author')
                path.write_text(json.dumps(document))
                self.assertNotEqual(self.invoke('seal','--scenarios',str(path)).returncode,0)

    def test_changed_spec_and_locked_test_invalidate_admission(self):
        for path in (self.project/'docs/fixture/SPEC.md',Path(self.fixture['test'])):
            with self.subTest(path=path.name):
                original=path.read_bytes();path.write_bytes(original+b'\n# changed contract\n')
                self.assertNotEqual(self.invoke('gate','--gate','development').returncode,0)
                path.write_bytes(original)

    def test_readonly_missing_status_does_not_create_state(self):
        fresh=self.base/'fresh';fresh.mkdir()
        subprocess.run(['git','init','-q',str(fresh)],check=True)
        before=set(fresh.rglob('*'))
        result=subprocess.run([sys.executable,str(self.helper),'status','--project',str(fresh),'--task','absent'],env=self.env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(set(fresh.rglob('*')),before)

    def final_evidence(self):
        Path(self.fixture['source']).write_text('answer = 42\n')
        result=subprocess.run(self.fixture['command'],cwd=self.project,env=self.env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0)
        log=self.base/'final.log';log.write_text(result.stdout+result.stderr)
        evidence=copy.deepcopy(self.evidence);evidence.update(gate='final',exit_code=0,
            assertions={'kind':'relevant_assertion','passed':1,'failed':0},
            log={'path':str(log),'sha256':self.builder.digest(log)},
            source_hashes={p:self.builder.digest(self.project/p) for p in self.fixture['paths']})
        return evidence

    def test_final_requires_exact_current_source_snapshot(self):
        evidence=self.final_evidence();valid=copy.deepcopy(evidence)
        evidence['source_hashes']={}
        self.assertNotEqual(self.invoke('record-final','--evidence',self.evidence_file(evidence)).returncode,0)
        self.assertEqual(self.invoke('record-final','--evidence',self.evidence_file(valid,'valid-final.json')).returncode,0)
        self.assertEqual(self.invoke('gate','--gate','final').returncode,0)
        Path(self.fixture['source']).write_text('answer = 43\n')
        self.assertNotEqual(self.invoke('gate','--gate','final').returncode,0)

class BehaviorProofPrototype(unittest.TestCase):
    def setUp(self):
        if not (ROOT/'scripts/nightshift-behavior-proof.py').is_file():self.skipTest('UNIMPLEMENTED helper; not behavioral RED')
        sys.dont_write_bytecode=True
        spec=importlib.util.spec_from_file_location('prototype_fixture_builder',ROOT/'tests/nightshift-behavior-fixture.py')
        self.builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.builder)
        self.temp=tempfile.TemporaryDirectory(prefix='nightshift-proof-prototype-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve()

    def fixture(self,**kwargs):return self.builder.PrototypeFixture(ROOT,self.base,**kwargs)

    def test_real_stub_execution_oracle_and_idempotent_reuse(self):
        fixture=self.fixture();fixture.seal()
        initial=len(fixture.model_calls())
        result=fixture.call('run','--gate','development');self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(len(fixture.model_calls()),initial+1)
        self.assertEqual(fixture.call('gate','--gate','development').returncode,0)
        self.assertEqual(fixture.call('run','--gate','development').returncode,0)
        self.assertEqual(len(fixture.model_calls()),initial+1,'Accepted current proof must not resample')
        argv=fixture.model_calls()[-1]['argv']
        self.assertIn('--safe-mode',argv);self.assertIn('--no-session-persistence',argv)
        self.assertEqual(argv[argv.index('--tools')+1],'')
        self.assertNotIn('--agents',argv,'Prototype must not receive the dispatcher wrapper')
        self.assertNotIn(str(fixture.private),' '.join(argv))

    def test_wrong_behavior_requires_prompt_revision_before_retry(self):
        fixture=self.fixture(output='{"choice":"deny"}');fixture.seal()
        self.assertNotEqual(fixture.call('run','--gate','development').returncode,0)
        after=len(fixture.model_calls());fixture.response.write_text('{"choice":"allow"}')
        self.assertNotEqual(fixture.call('run','--gate','development').returncode,0)
        self.assertEqual(len(fixture.model_calls()),after,'Unchanged failed prompt cannot be resampled')
        fixture.prompt.write_text(fixture.prompt.read_text()+'Clarify the allowed choice.\n')
        self.assertEqual(fixture.call('run','--gate','development').returncode,0)
        self.assertEqual(len(fixture.model_calls()),after+1)

    def test_minimum_remaining_budget_blocks_partial_case_set(self):
        fixture=self.fixture(cases=2)
        with (fixture.project/'.nightshift.toml').open('a') as f:f.write('development_calls = 2\n')
        fixture.seal();before=len(fixture.model_calls())
        self.assertNotEqual(fixture.call('run','--gate','development').returncode,0)
        self.assertEqual(len(fixture.model_calls()),before,'Insufficient whole-suite budget must not start a partial suite')

    def test_billing_environment_stripped_and_transport_unknown(self):
        fixture=self.fixture();fixture.env.update(OPENAI_API_KEY='private-billing-fixture',ANTHROPIC_API_KEY='private-billing-fixture')
        fixture.seal();fixture.env['FIXTURE_MODE']='transport'
        result=fixture.call('run','--gate','development');self.assertNotEqual(result.returncode,0)
        self.assertNotIn('private-billing-fixture',result.stdout+result.stderr)
        self.assertFalse(any(r['billing'] for r in fixture.model_calls()))
        self.assertNotEqual(fixture.call('gate','--gate','development').returncode,0)

    def test_timeout_and_output_cap_never_admit(self):
        fixture=self.fixture(timeout=1);fixture.seal();fixture.env['FIXTURE_MODE']='timeout'
        result=fixture.call('run','--gate','development');self.assertNotEqual(result.returncode,0)
        self.assertNotEqual(fixture.call('gate','--gate','development').returncode,0)
        fixture.env['FIXTURE_MODE']='flood'
        self.assertNotEqual(fixture.call('run','--gate','development').returncode,0)
        self.assertNotEqual(fixture.call('gate','--gate','development').returncode,0)

    def test_premature_surrounding_edit_blocks_before_launch(self):
        fixture=self.fixture();fixture.seal();before=len(fixture.model_calls())
        (fixture.project/'surrounding.py').write_text('value = 1\n')
        self.assertNotEqual(fixture.call('run','--gate','development').returncode,0)
        self.assertEqual(len(fixture.model_calls()),before)

    def test_concurrent_runs_do_not_double_reserve_case(self):
        fixture=self.fixture();fixture.seal();before=len(fixture.model_calls())
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:fixture.call('run','--gate','development'),range(2)))
        self.assertTrue(any(r.returncode==0 for r in results))
        self.assertEqual(len(fixture.model_calls()),before+1,'Concurrent launches overspent one pending/accepted case')

    def test_challenge_rejects_wrong_digest_or_missing_case_ids(self):
        fixture=self.fixture()
        for mode in ('wrong_digest','incomplete'):
            with self.subTest(mode=mode):
                fixture.env['FIXTURE_REVIEW']=mode
                result=fixture.call('challenge','--scenarios',fixture.scenarios,'--out',fixture.challenge)
                self.assertNotEqual(result.returncode,0)
                self.assertNotEqual(fixture.call('seal','--scenarios',fixture.scenarios,'--challenge',fixture.challenge,'--heldout',fixture.private).returncode,0)

    def test_json_oracle_preserves_boolean_integer_distinction(self):
        fixture=self.fixture(output='{"choice":true}')
        document=json.loads(fixture.scenarios.read_text());document['cases'][0]['expected'][0]['value']=1
        fixture.scenarios.write_bytes(self.builder.canonical(self.builder.attest(document)))
        subprocess.run(['bash',str(fixture.root/'scripts/nightshift-tdd-spec-lock.sh'),fixture.task],env=fixture.env,cwd=fixture.project,capture_output=True,check=True)
        fixture.seal()
        self.assertNotEqual(fixture.call('run','--gate','development').returncode,0,'JSON boolean must not satisfy integer oracle')
        self.assertNotEqual(fixture.call('gate','--gate','development').returncode,0)

    def test_heldout_exposure_invalidates_final_freshness(self):
        fixture=self.fixture();fixture.seal()
        self.assertEqual(fixture.call('run','--gate','development').returncode,0)
        self.assertEqual(fixture.call('run','--gate','final').returncode,0)
        self.assertEqual(fixture.call('gate','--gate','final').returncode,0)
        result=fixture.call('expose','--case','private-1');self.assertEqual(result.returncode,0)
        self.assertNotIn(str(fixture.private),result.stdout+result.stderr)
        self.assertNotEqual(fixture.call('gate','--gate','final').returncode,0)

unittest.main(verbosity=2)
PY
