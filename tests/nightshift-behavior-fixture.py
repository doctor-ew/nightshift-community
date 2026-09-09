#!/usr/bin/env python3
"""Test-only admitted task builder using ordinary review, seal and RED APIs."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def attest(document):
    semantics = copy.deepcopy(document)
    semantics['applicability']['review'] = None
    for case in semantics['cases']:
        case['applicability']['review'] = None
    identity = hashlib.sha256(canonical(semantics)).hexdigest()
    review = {'reviewer_provider': 'claude', 'reviewer_author_id': 'independent-fixture-reviewer',
              'decision': 'approve', 'reviewed_input_sha256': identity,
              'evidence_sha256': hashlib.sha256(b'Independent synthetic fixture classification reviewed.').hexdigest()}
    document['applicability']['review'] = dict(review)
    for case in document['cases']:
        case['applicability']['review'] = dict(review)
    return document


def prepare(root, project, task='fixture', final=False, require_gate=True):
    root, project = Path(root).resolve(), Path(project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, NIGHTSHIFT_PROJECT_DIR=str(project), PYTHONDONTWRITEBYTECODE='1')
    env.pop('CLAUDE_PROJECT_DIR', None)
    def run(argv, check=True):
        result = subprocess.run([str(v) for v in argv], cwd=project, env=env, capture_output=True, text=True)
        if check and result.returncode:
            raise RuntimeError('Fixture operation failed: '+str(argv[0])+'; '+result.stdout+'; '+result.stderr)
        return result
    def git(*args): return run(['git', '-C', project, *args]).stdout.strip()
    if run(['git', '-C', project, 'rev-parse', '--show-toplevel'], False).returncode:
        git('init', '-q'); git('config', 'user.name', 'fixture'); git('config', 'user.email', 'fixture@local')
        git('commit', '--allow-empty', '-qm', 'fixture baseline')
    directory = project/'docs'/task; directory.mkdir(parents=True, exist_ok=True)
    tests = project/'tests'; tests.mkdir(exist_ok=True)
    source = project/('fixture_source_'+task+'.py')
    test = tests/('test_fixture_'+task+'.py')
    source.write_text('answer = 0\n')
    test.write_text('import pathlib, runpy, unittest\n'
                    'source = pathlib.Path(__file__).resolve().parents[1] / '+repr(source.name)+'\n'
                    'class Contract(unittest.TestCase):\n'
                    '    def test_answer(self):\n'
                    '        self.assertEqual(runpy.run_path(str(source))["answer"], 42)\n'
                    'unittest.main()\n')
    command = [sys.executable, str(test.relative_to(project))]
    convention = project/'AGENTS.md'
    convention.write_text('# Fixture test command\n\n'+ ' '.join(command)+'\n')
    spec = directory/'SPEC.md'
    paths = [str(source.relative_to(project)), str(test.relative_to(project)), 'AGENTS.md']
    spec.write_text('# Fixture contract\n\n## Acceptance Criteria\n\n1. AC-1: answer equals 42.\n\n## Files to Change\n\n| File | Action |\n| --- | --- |\n| '+paths[0]+' | MODIFY |\n| '+paths[1]+' | TEST |\n| AGENTS.md | MODIFY |\n\n## Guardrails\n\nPreserve the exact contract.\n')
    app = {'kind':'deterministic','rationale':'Pure value contract checked by ordinary unittest','risks':['deterministic_logic'],'review':None}
    document = {'version':1,'task':task,'ac_ids':['AC-1'],'author':{'provider':'codex','author_id':'fixture-spec-author'},
                'applicability':dict(app),'runtime':None,'prototype_files':[],
                'cases':[{'id':'case-1','ac_ids':['AC-1'],'required':True,'applicability':dict(app),
                          'given':'An existing answer value','when':'Read answer','then':'Answer equals 42',
                          'forbidden':'Any answer other than 42','input':None,'expected':[], 'prohibited':[],
                          'counterexamples':['An answer value of 0'],'visibility':'public'}], 'heldout':None}
    scenarios = directory/'behavior-scenarios.json'; scenarios.write_bytes(canonical(attest(document)))
    run(['bash',root/'scripts/nightshift-scope-activate.sh',task,'--project',project,'--spec',spec])
    run(['bash',root/'scripts/nightshift-tdd-spec-lock.sh',task])
    red = run(command, False)
    if red.returncode == 0 or 'AssertionError' not in red.stderr:
        raise RuntimeError('Fixture did not produce a relevant RED assertion')
    run(['bash',root/'scripts/nightshift-tdd-red-lock.sh',task])
    red_sha = git('rev-parse', 'HEAD')
    retained = project.parent/('proof-evidence-'+project.name+'-'+task);retained.mkdir(exist_ok=True)
    log = retained/'red.log'; log.write_text(red.stdout+red.stderr)
    proof = root/'scripts/nightshift-behavior-proof.py'
    run([sys.executable,proof,'seal','--project',project,'--task',task,'--scenarios',scenarios])
    evidence = {'version':1,'task':task,'gate':'development','observer':{'provider':'claude','author_id':'independent-test-observer'},
                'scenario_ids':['case-1'],'command':{'argv':command,'source':{'path':'AGENTS.md','line':3,'sha256':digest(convention)}},
                'exit_code':red.returncode,'assertions':{'kind':'relevant_assertion','passed':0,'failed':1},
                'log':{'path':str(log),'sha256':digest(log)},'tests':[{'path':str(test.relative_to(project)),'sha256':digest(test)}],
                'red_lock_sha':red_sha,'source_hashes':{}}
    evidence_path=directory/'red-evidence.json';evidence_path.write_bytes(canonical(evidence))
    run([sys.executable,proof,'record-red','--project',project,'--task',task,'--evidence',evidence_path])
    if require_gate:
        run([sys.executable,proof,'gate','--project',project,'--task',task,'--gate','development'])
    result={'project':str(project),'task':task,'scenario_path':str(scenarios),'evidence_path':str(evidence_path),
            'source':str(source),'test':str(test),'paths':paths,'command':command,'red_lock_sha':red_sha}
    if final:
        source.write_text('answer = 42\n')
        green=run(command)
        final_log=retained/'final.log';final_log.write_text(green.stdout+green.stderr)
        final_evidence=copy.deepcopy(evidence);final_evidence.update(gate='final',exit_code=0,
            assertions={'kind':'relevant_assertion','passed':1,'failed':0},
            log={'path':str(final_log),'sha256':digest(final_log)},source_hashes={p:digest(project/p) for p in paths})
        final_path=directory/'final-evidence.json';final_path.write_bytes(canonical(final_evidence))
        run([sys.executable,proof,'record-final','--project',project,'--task',task,'--evidence',final_path])
        run([sys.executable,proof,'gate','--project',project,'--task',task,'--gate','final'])
        result['final_evidence_path']=str(final_path)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--project',required=True)
    parser.add_argument('--task',default='fixture');parser.add_argument('--final',action='store_true')
    args=parser.parse_args();print(json.dumps(prepare(args.root,args.project,args.task,args.final)))

class PrototypeFixture:
    """Offline transport fixture; all proof state comes from public CLI operations."""
    def __init__(self, root, base, cases=1, output='{"choice":"allow"}', timeout=2, cap=1048576):
        self.root=Path(root).resolve();self.base=Path(base).resolve();self.project=self.base/'project';self.project.mkdir()
        self.task='prototype';self.directory=self.project/'docs'/self.task;self.directory.mkdir(parents=True)
        self.binary=self.base/'bin';self.binary.mkdir();self.calls=self.base/'provider-calls.jsonl'
        self.response=self.base/'response.json';self.response.write_text(output)
        self.prompt=self.project/'reviewer-prompt.md';self.prompt.write_text('Select the correct choice from the supplied synthetic input. Return JSON only.\n')
        (self.project/'surrounding.py').write_text('value = 0\n')
        (self.directory/'SPEC.md').write_text('# Prototype fixture\n\n## Acceptance Criteria\n\n1. AC-1: choose correctly.\n\n## Files to Change\n\n| File | Action |\n| --- | --- |\n| reviewer-prompt.md | MODIFY |\n| surrounding.py | MODIFY |\n')
        (self.project/'.nightshift.toml').write_text('[behavior_proof]\ntimeout_seconds = '+str(timeout)+'\noutput_bytes = '+str(cap)+'\n')
        app={'kind':'prototype','rationale':'Prompt output requires observable text behavior proof','risks':['prompt_behavior'],'review':None}
        runtime={'profile':'claude-subscription-text-v1','model':'sonnet','cli_version':'2.1.265','system_prompt_file':'reviewer-prompt.md'}
        def case(identifier,visibility):
            return {'id':identifier,'ac_ids':['AC-1'],'required':True,'applicability':dict(app),'given':'Synthetic request with explicit allowed choice','when':'Evaluate the prompt','then':'Return the allowed choice','forbidden':'A denial when allowance is required','input':'Choose allow for synthetic request '+identifier,'expected':[{'op':'json_field_equals','field':['choice'],'value':'allow'}],'prohibited':[{'op':'json_field_equals','field':['choice'],'value':'deny'}],'counterexamples':['Returning deny violates this synthetic request'],'visibility':visibility}
        self.private=self.base/'private-scenarios.json'
        private={'version':1,'task':self.task,'ac_ids':['AC-1'],'author':{'provider':'codex','author_id':'independent-private-author'},'applicability':dict(app),'runtime':runtime,'prototype_files':['reviewer-prompt.md'],'cases':[case('private-1','held_out')],'heldout':None}
        self.private.write_bytes(canonical(attest(private)))
        public={'version':1,'task':self.task,'ac_ids':['AC-1'],'author':{'provider':'codex','author_id':'public-prototype-author'},'applicability':dict(app),'runtime':runtime,'prototype_files':['reviewer-prompt.md'],'cases':[case('public-'+str(i+1),'public') for i in range(cases)],'heldout':{'manifest_sha256':digest(self.private),'case_ids':['private-1'],'author':private['author'],'prepared_at':'2026-09-08T00:00:00+00:00'}}
        self.scenarios=self.directory/'behavior-scenarios.json';self.scenarios.write_bytes(canonical(attest(public)))
        self.env=dict(os.environ,NIGHTSHIFT_PROJECT_DIR=str(self.project),PYTHONDONTWRITEBYTECODE='1',NIGHTSHIFT_TELEMETRY_DIR='off',PATH=str(self.binary)+os.pathsep+os.environ['PATH'],FIXTURE_CALLS=str(self.calls),FIXTURE_SCENARIOS=str(self.scenarios),FIXTURE_RESPONSE=str(self.response))
        self.env.pop('CLAUDE_PROJECT_DIR',None);self.env.pop('NIGHTSHIFT_ROLE_CHILD',None)
        routing=self.base/'routing.json';routing.write_bytes((self.root/'routing.json').read_bytes());self.env['NIGHTSHIFT_ROUTING_FILE']=str(routing)
        for forbidden in ('codex','ollama'):
            rejected=self.binary/forbidden;rejected.write_text('#!/bin/sh\nexit 99\n');rejected.chmod(0o755)
        stub=self.binary/'claude'
        stub.write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys,time
args=sys.argv[1:]
with pathlib.Path(os.environ['FIXTURE_CALLS']).open('a') as f:f.write(json.dumps({'argv':args,'billing':bool(os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('OPENAI_API_KEY'))})+'\\n')
if args==['--version']:print('2.1.265 (Claude Code)');sys.exit(0)
if args[:2]==['auth','status']:print(json.dumps({'loggedIn':True,'authMethod':'claude.ai','apiProvider':'firstParty'}));sys.exit(0)
if '--agents' in args or ('--system-prompt' in args and '--json-schema' in args):
 doc=json.loads(pathlib.Path(os.environ['FIXTURE_SCENARIOS']).read_text())
 result={'decision':'approve','scenario_ids':[c['id'] for c in doc['cases']],'findings':[],'reviewed_input_sha256':doc['applicability']['review']['reviewed_input_sha256']}
 if os.environ.get('FIXTURE_REVIEW')=='wrong_digest':result['reviewed_input_sha256']='0'*64
 if os.environ.get('FIXTURE_REVIEW')=='incomplete':result['scenario_ids']=[]
 print(json.dumps({'structured_output':{'status':'SUCCESS','reason':'Independent fixture review','attempts':1,'artifacts':{'provider':'claude','model':'sonnet','branch':'fixture','diff':''},'rules_fired':[],'results':result}}));sys.exit(0)
mode=os.environ.get('FIXTURE_MODE','normal')
if mode=='timeout':time.sleep(10)
if mode=='flood':print('x'*2097152);sys.exit(0)
if mode=='transport':sys.exit(7)
print(json.dumps({'type':'result','is_error':False,'result':pathlib.Path(os.environ['FIXTURE_RESPONSE']).read_text(),'usage':{'input_tokens':3,'output_tokens':2}}))
''');stub.chmod(0o755)
        for args in (['init','-q'],['config','user.name','fixture'],['config','user.email','fixture@local'],['add','.'],['commit','-qm','prototype fixture baseline']):
            subprocess.run(['git','-C',str(self.project),*args],env=self.env,capture_output=True,check=True)
        subprocess.run(['bash',str(self.root/'scripts/nightshift-scope-activate.sh'),self.task,'--project',str(self.project),'--spec',str(self.directory/'SPEC.md')],env=self.env,cwd=self.project,capture_output=True,check=True)
        subprocess.run(['bash',str(self.root/'scripts/nightshift-tdd-spec-lock.sh'),self.task],env=self.env,cwd=self.project,capture_output=True,check=True)
        self.challenge=self.directory/'challenge.json'

    def call(self,operation,*args):
        return subprocess.run([sys.executable,str(self.root/'scripts/nightshift-behavior-proof.py'),operation,'--project',str(self.project),'--task',self.task,*map(str,args)],env=self.env,cwd=self.project,capture_output=True,text=True)

    def seal(self):
        challenge=self.call('challenge','--scenarios',self.scenarios,'--out',self.challenge)
        if challenge.returncode:raise RuntimeError('Fixture challenge failed: '+challenge.stdout+challenge.stderr)
        sealed=self.call('seal','--scenarios',self.scenarios,'--challenge',self.challenge,'--heldout',self.private)
        if sealed.returncode:raise RuntimeError('Fixture seal failed: '+sealed.stdout+sealed.stderr)

    def model_calls(self):
        if not self.calls.exists():return []
        return [r for r in map(json.loads,self.calls.read_text().splitlines()) if r['argv']!=['--version'] and r['argv'][:2]!=['auth','status']]
