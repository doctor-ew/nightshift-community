#!/usr/bin/env python3
"""Versioned engineering operations; clients never own admission or transitions."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
VERSION = 1
OPS = ('groom-spec', 'groom-rules', 'groom-adversarial', 'groom', 'implement', 'adopt', 'verify', 'review', 'accept', 'publish')
RECIPES = {'groom': list(OPS[:4]), 'factory': [*OPS[:5], 'verify', 'review'], 'external': ['adopt', 'verify', 'review']}
DEPS = {'groom-spec': (), 'groom-rules': (), 'groom-adversarial': ('groom-spec', 'groom-rules'),
        'groom': ('groom-spec', 'groom-rules', 'groom-adversarial'), 'implement': ('groom',),
        'adopt': ('groom-rules',), 'verify': ('groom-rules',), 'review': ('verify',), 'accept': ('review',), 'publish': ('accept',)}
AI = {'groom-spec', 'groom-adversarial', 'implement', 'review'}
REVIEW = {'groom-adversarial', 'review'}
MAX_REQUEST = 64 * 1024


def load(name):
    spec = importlib.util.spec_from_file_location('operations_' + name, HERE / ('nightshift-' + name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recovery = load('recovery-state')
digest = recovery.digest
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError('invalid_shape:' + keys)


def bounded_text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 4000


def read(path):
    path = Path(path)
    if path.resolve() != path.absolute() or path.stat().st_size > 2_000_000:
        raise ValueError('unsafe_record')
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('record_requires_object')
    return value


def safe(project, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts or name.startswith('.git/'):
        raise ValueError('unsafe_artifact_path')
    path = Path(project) / name
    if path.resolve() != path.absolute() or (path.exists() and not path.is_file()):
        raise ValueError('unsafe_artifact_path')
    return path


def limits(value):
    exact(value, 'calls seconds wall_seconds')
    for key, maximum in [('calls', 64), ('seconds', 3600), ('wall_seconds', 3600)]:
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]) or not 0 < value[key] <= maximum:
            raise ValueError('invalid_allowance')
    if type(value['calls']) is not int:
        raise ValueError('invalid_call_limit')
    return value


def location(project, task):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', task):
        raise ValueError('invalid_task')
    common = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--git-common-dir'], text=True).strip()
    return (Path(project) / common).resolve() / 'nightshift/operations' / task


def plan_path(project, task):
    return safe(project, 'docs/' + task + '/operations.json')


def plan(project, task):
    value = read(plan_path(project, task))
    exact(value, 'version inputs scope checks environment reviewer_policy limits aggregate publication')
    if value['version'] != VERSION:
        raise ValueError('unsupported_plan_version')
    exact(value['inputs'], 'request spec scenarios rules architecture')
    for name in value['inputs'].values():
        safe(project, name)
    if len(set(value['inputs'].values())) != 5:
        raise ValueError('distinct_artifacts_required')
    if not isinstance(value['scope'], list) or not value['scope'] or len(set(value['scope'])) != len(value['scope']):
        raise ValueError('implementation_scope_required')
    for name in value['scope']:
        safe(project, name)
        if name in value['inputs'].values() or name == str(plan_path(project, task).relative_to(project)) or name.startswith('.nightshift'):
            raise ValueError('source_scope_overlaps_control_artifacts')
    if not isinstance(value['checks'], list) or not value['checks']:
        raise ValueError('declared_checks_required')
    ids = set()
    for check in value['checks']:
        exact(check, 'id argv'+(' adapter' if 'adapter' in check else ''))
        if not bounded_text(check['id']) or check['id'] in ids or not isinstance(check['argv'], list) or len(check['argv']) != 2 or check['argv'][0] not in ('python3', 'bash', 'node'):
            raise ValueError('invalid_test_command')
        load('verification-adapters').profile(check)
        safe(project, check['argv'][1]); ids.add(check['id'])
    if not isinstance(value['environment'], dict) or any(not re.fullmatch(r'[A-Z][A-Z0-9_]*', k) or k.startswith(('NIGHTSHIFT_', 'PYTHON', 'LD_', 'DYLD_')) or k in ('PATH', 'HOME', 'TMPDIR', 'BASH_ENV', 'ENV') or not isinstance(v, str) for k, v in value['environment'].items()):
        raise ValueError('invalid_test_environment')
    exact(value['reviewer_policy'], 'version require_different_provider semantic_plan')
    if value['reviewer_policy']['version'] != 1 or type(value['reviewer_policy']['require_different_provider']) is not bool:
        raise ValueError('invalid_reviewer_policy')
    if value['reviewer_policy']['semantic_plan'] is not None:
        safe(project, value['reviewer_policy']['semantic_plan'])
    exact(value['limits'], ' '.join(OPS))
    for item in value['limits'].values(): limits(item)
    limits(value['aggregate'])
    if value['publication'] is not None:
        exact(value['publication'], 'remote branch')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', value['publication']['remote']) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9/_-]+', value['publication']['branch']) or value['publication']['branch'] in ('main', 'master'):
            raise ValueError('invalid_publication_target')
    return value


def scenarios(project,p):
    value=read(safe(project,p['inputs']['scenarios']))
    exact(value,'version cases')
    if value['version']!=1 or not isinstance(value['cases'],list) or not value['cases']:raise ValueError('acceptance_cases_required')
    ids=set()
    for case in value['cases']:
        exact(case,'id requirement manual')
        if not bounded_text(case['id']) or case['id'] in ids or not bounded_text(case['requirement']) or type(case['manual']) is not bool:raise ValueError('invalid_acceptance_case')
        ids.add(case['id'])
    return value['cases']


def manual_acceptance(project,p,binding,attestation):
    if not isinstance(attestation,dict) or attestation.get('binding')!=binding:
        raise ValueError('bound_human_attestation_required')
    required=[case for case in scenarios(project,p) if case['manual']]
    if not required:
        exact(attestation,'binding accepted')
        if attestation['accepted'] is not True:raise ValueError('manual_acceptance_pending')
        return dict(binding=binding,accepted=True,cases=[])
    exact(attestation,'binding cases')
    if len(json.dumps(attestation,ensure_ascii=False).encode())>12000:raise ValueError('manual_acceptance_too_large')
    rows=attestation['cases']
    if not isinstance(rows,list) or len(rows)!=len(required):raise ValueError('manual_cases_incomplete')
    expected={case['id']:digest(case) for case in required};seen=set();normalized=[]
    for row in rows:
        exact(row,'id case_sha256 passed observation evidence')
        if not isinstance(row['id'],str) or row['id'] not in expected or row['id'] in seen or row['case_sha256']!=expected[row['id']]:raise ValueError('manual_case_identity_changed')
        if row['passed'] is not True:raise ValueError('manual_acceptance_pending')
        for key in ('observation','evidence'):
            if not isinstance(row[key],str) or not row[key].strip() or '\0' in row[key] or len(row[key].encode())>2048:raise ValueError('manual_case_observation_required')
        seen.add(row['id']);normalized.append(dict(row))
    return dict(binding=binding,accepted=True,cases=sorted(normalized,key=lambda row:row['id']))


class Operations:
    def __init__(self, project, task, worker=None, clock=time.time):
        self.project = Path(project).resolve()
        self.task = task
        self.directory = location(self.project, task)
        self.path = self.directory / 'state.json'
        self.worker = worker or self.dispatch
        self.clock = clock
        self.mutex = threading.RLock()
        self.reload()

    def reload(self):
        self.state = read(self.path) if self.path.exists() else dict(version=VERSION, task=self.task,
            worktree=str(self.project), repository=str(self.directory.parent.parent.parent), authorizations={}, results={}, attempts=[], calls={}, imports=[])
        if self.state['version'] != VERSION or self.state['worktree'] != str(self.project) or self.state['task'] != self.task:
            raise ValueError('operation_identity_changed')

    def save(self):
        recovery.atomic(self.path, self.state)

    @contextmanager
    def lease(self):
        if os.environ.get('NIGHTSHIFT_ROLE_CHILD') == '1':
            raise ValueError('worker_cannot_control_operations')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.resolve() != self.directory.absolute():
            raise ValueError('unsafe_state_directory')
        fd = os.open(self.directory / 'lease', os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('operation_busy') from None
            self.reload()
            yield

    def corpus(self):
        return recovery.workspace(self.project)['files']

    def modes(self):
        return {k:stat.S_IMODE(safe(self.project,k).stat().st_mode) for k,v in self.corpus().items() if v is not None}

    def package_schema(self,p):
        path=safe(self.project,p['inputs']['spec'])
        if not path.exists():return None
        try:value=read(path)
        except (ValueError,UnicodeError):return None
        if not isinstance(value,dict) or value.get('version')!=3 or 'artifacts' not in value:return None
        schemas=read(HERE.parent/'contracts/nightshift-work-packages.schema.json')['oneOf']
        return next(schema for schema in schemas if schema['properties']['version']['const']==3)

    def package_inputs(self, p):
        """Resolve declared package evidence without granting draft validity."""
        path = safe(self.project, p['inputs']['spec'])
        if not path.exists(): return set()
        try: graph = read(path)
        except (ValueError, UnicodeError): return set()
        if not isinstance(graph, dict) or set(graph)-{'templates','artifacts'} != {'version','parent','requirements','children','aggregate'}: return set()
        names = set()
        for child in graph['children']:
            names.add(child['plan'])
            names.update(child['reads'])
            names.update(child['writes'])
        for name in names:
            if graph.get('version')==3:load('package-bundle').safe_name(self.project,name)
            else:safe(self.project,name)
        return names

    def context(self):
        p = plan(self.project, self.task)
        files = self.corpus()
        artifacts = {k: sha(safe(self.project, n)) if safe(self.project, n).exists() else None for k, n in p['inputs'].items()}
        package_inputs = self.package_inputs(p)
        if package_inputs:
            artifacts['package_contracts'] = digest({name:sha(safe(self.project,name)) if safe(self.project,name).exists() else None for name in sorted(package_inputs)})
        excluded = set(p['inputs'].values()) | {str(plan_path(self.project, self.task).relative_to(self.project))}
        if p['reviewer_policy']['semantic_plan']: excluded.add(p['reviewer_policy']['semantic_plan'])
        source = {k:dict(sha256=v,mode=stat.S_IMODE(safe(self.project,k).stat().st_mode)) if v is not None else None for k,v in files.items() if k not in excluded}
        tests = {c['argv'][1]: sha(safe(self.project, c['argv'][1])) if safe(self.project, c['argv'][1]).exists() else None for c in p['checks']}
        env = dict(declared=p['environment'], python=sys.version, executables={n: sha(shutil.which(n)) for n in ('python3', 'bash', 'node') if shutil.which(n)})
        effective=load('controller-recovery').clean_environment();effective.update(p['environment']);effective['NIGHTSHIFT_ROLE_CHILD']='1'
        env['effective']=effective
        if any(load('verification-adapters').profile(c)=='python-unittest-v1' for c in p['checks']):env['typed_runtime']=load('verification-adapters').identity(effective)
        return p, dict(artifacts=artifacts, source=source, tests=tests, environment=env, accepted_architecture=load('architecture').resolve(self.project))

    def route(self, operation, p):
        policy = load('provider-policy')
        routing = load('routing-path').resolve(HERE.parent, self.project)
        data = read(routing)
        role = 'nightshift-code-fact-extractor' if operation in REVIEW else 'nightshift-spec-writer' if operation == 'groom-spec' else 'nightshift-engineer'
        author = self.provenance(operation).get('provider', 'unknown')
        route = policy.select_route(data, role, 1, policy.mode(self.project), author if author != 'unknown' else '', operation in REVIEW and author in ('codex', 'claude', 'local'))
        if operation in REVIEW and p['reviewer_policy']['require_different_provider'] and author == route['provider']:
            raise ValueError('independent_reviewer_required')
        if not bounded_text(route.get('model')):
            raise ValueError('concrete_worker_model_required')
        return dict(provider=route['provider'], model=route['model'], role=role, routing=str(routing), policy=policy.mode(self.project))

    load_digest = staticmethod(digest)
    recovery_read = staticmethod(read)
    recovery_write = staticmethod(recovery.atomic)
    file_hash = staticmethod(sha)

    def cancellation_check(self,grant):
        if not getattr(self,'reconciling',False):load('operation-reconciliation').check(self,grant)

    def retry_account(self, attempt, category):
        return load('retry-budget').account(self.directory / (attempt['operation'] + '.retry.json'), attempt['request'], category, exclusive=True)

    def repair_evidence(self, operation):
        gates = ('groom-adversarial',) if operation == 'groom-spec' else ('verify', 'review') if operation == 'implement' else ()
        latest = next((a for a in reversed(self.state['attempts']) if a['operation'] in gates and a['status'] == 'failed'), None)
        return {k: latest.get(k, {}) for k in ('request', 'binding', 'signature', 'findings', 'evidence')} if latest else None

    def repair_findings(self, operation):
        evidence = self.repair_evidence(operation)
        return evidence['findings'] if evidence else []

    def provenance(self, operation):
        key = 'groom-spec' if operation == 'groom-adversarial' else 'implement'
        row = self.state['results'].get(key, {})
        return row.get('provenance', {'provider': 'unknown', 'model': 'unknown', 'identity': 'unknown'})

    def question_basis(self,dependencies,operation):
        basis={k:v for k,v in dependencies.items() if k not in ('decisions','repair_findings','repair_evidence')}
        if operation in ('implement','groom-spec'):
            _,context=self.context()
            basis['question_source']=context['source'] if operation=='implement' else {k:context['artifacts'][k] for k in ('spec','scenarios')}
        return digest(basis)

    def decision_rows(self,operation,dependencies):
        if not any(r['operation']==operation for r in self.state.get('questions',[])):return []
        basis=self.question_basis(dependencies,operation);rows=[]
        decisions=load('console-decisions')
        for record in self.state.get('questions',[]):
            if record['operation']!=operation:continue
            history=decisions.read(decisions.location(self.project,record['task']))['requests']
            item=next((r for r in history if r['sha256']==record['sha256']),None)
            if item is None:raise ValueError('operation_question_evidence_missing:restore_retained_record')
            rows.append(dict(record,current=record['basis']==basis,question=item))
        return rows

    def question(self,operation,binding,value):
        assessed=self.assess(operation)
        if assessed.get('binding')!=binding:raise ValueError('stale_question_evidence')
        exact(value,'question reason options')
        if len(json.dumps(value).encode())>6000:raise ValueError('question_context_too_large')
        if not bounded_text(value['question']):raise ValueError('invalid_operation_question')
        normalized=' '.join(value['question'].casefold().split())
        basis=self.question_basis(assessed['dependencies'],operation)
        for retained in self.decision_rows(operation,assessed['dependencies']):
            if retained['current'] and ' '.join(retained['question']['question'].casefold().split())==normalized:return retained['question']
        task='op-question-'+digest(dict(project=str(self.project),task=self.task,operation=operation,basis=basis,question=normalized))[:32]
        rows=self.state.setdefault('questions',[])
        if len(rows)>=100 and not any(row['task']==task for row in rows):raise ValueError('question_history_full:retain_evidence')
        item=load('console-decisions').request(self.project,task,dict(value,continuation='none',decision_key='operation-clarification'))
        if not any(row['sha256']==item['sha256'] for row in rows):
            if len(rows)>=100:raise ValueError('question_history_full:retain_evidence')
            rows.append(dict(operation=operation,basis=basis,binding=binding,task=task,sha256=item['sha256']));self.save()
        return item

    def answer(self,operation,binding,question,choice,answer):
        with self.lease():
            assessed=self.assess(operation)
            rows=self.decision_rows(operation,assessed['dependencies'])
            row=next((r for r in rows if r['sha256']==question and r['current']),None)
            if not row or (assessed.get('binding')!=binding and not row['question'].get('response')):raise ValueError('stale_question_evidence')
            return load('console-decisions').respond(self.project,row['task'],question,choice,answer)

    def dependencies(self, operation, p, context):
        a = context['artifacts']
        base = dict(version=VERSION, task=self.task, worktree=str(self.project), repository=self.state['repository'])
        names = ('request', 'rules', 'architecture') if operation == 'groom-spec' else ('rules', 'architecture') if operation == 'groom-rules' else tuple(a)
        base['artifacts'] = {k: a[k] for k in names}
        base['accepted_architecture'] = context['accepted_architecture']
        base['executor_sha256'] = sha(Path(__file__))
        if self.package_schema(p):base['package_schema_sha256']=sha(HERE.parent/'contracts/nightshift-work-packages.schema.json')
        base['assets'] = {}
        if operation in AI:
            base['assets'] = {name:sha(HERE.parent/name) for name in ('scripts/nightshift-agent.sh','agents/nightshift-operation-worker.md','contracts/nightshift-operation-worker.schema.json')}
        if operation=='verify':
            base['assets']['architecture_checker']=sha(HERE/'nightshift-architecture.py')
            for check in p['checks']:base['assets'].update(load('verification-adapters').assets(check))
            base['assets'].update({name:sha(HERE/name) for name in ('nightshift-controller-recovery.py','nightshift-recovery-exec.py')})
        if load('operation-decisions').selected(self,p,operation):
            base['assets'].update({name:sha(HERE/name) for name in ('nightshift-decision-engine.py','nightshift-operation-decisions.py')})
        if operation in ('groom-spec', 'implement'):
            base['repair_findings'] = self.repair_findings(operation)
            base['repair_evidence'] = self.repair_evidence(operation)
        base['upstream'] = {k: self.state['results'].get(k, {}).get('digest') for k in DEPS[operation]}
        if operation in ('implement', 'adopt'):
            base['scope'] = p['scope']
        if operation in ('adopt', 'verify', 'review', 'accept', 'publish'):
            base['source']=context['source']
        if operation in ('verify','review','accept','publish'):
            base.update(tests=context['tests'],checks=p['checks'],environment=context['environment'])
        if operation in ('review', 'accept', 'publish') or load('operation-decisions').selected(self,p,operation):
            base['reviewer_policy'] = p['reviewer_policy']
            semantic = p['reviewer_policy']['semantic_plan']
            base['semantic_plan'] = sha(safe(self.project, semantic)) if semantic else None
            base['semantic_settings'] = load('operation-decisions').configuration(self) if semantic else None
        if operation in AI:
            base['route'] = self.route(operation, p)
        if operation=='verify':
            base['contract'] = self.state['results'].get('adopt',{}).get('digest') if self.valid('adopt',p,context) else self.state['results'].get('groom',{}).get('digest')
        if operation == 'review':
            base['implementation'] = self.state['results'].get('implement', {}).get('digest')
        if operation == 'publish':
            base['publication'] = p['publication']
            if p['publication']:
                base['publication_target'] = subprocess.check_output(['git','-C',str(self.project),'remote','get-url','--push',p['publication']['remote']],text=True).strip()
                base['publication_head'] = subprocess.check_output(['git','-C',str(self.project),'rev-parse','HEAD'],text=True).strip()
        answers=[dict(sha256=r['sha256'],question=r['question']['question'],reason=r['question']['reason'],response=r['question']['response']) for r in self.decision_rows(operation,base) if r['current'] and r['question'].get('response')]
        if answers:base['decisions']=answers
        return base

    def valid(self, operation, p, context, visiting=None):
        row = self.state['results'].get(operation)
        if not row:
            return False
        try:
            if row['digest'] != digest({k: v for k, v in row.items() if k != 'digest'}):
                return False
            dependencies=self.dependencies(operation,p,context)
            if any(r['current'] and not r['question'].get('response') for r in self.decision_rows(operation,dependencies)):return False
            if row['dependencies'] != dependencies:
                return False
            if operation=='verify' and not (self.valid('groom',p,context) or self.valid('adopt',p,context)):return False
            required = ('adopt',) if operation=='implement' and row.get('external') else DEPS[operation]
            if any(not self.valid(k, p, context) for k in required):
                return False
            for path, expected in row['evidence'].items():
                if sha(self.directory / path) != expected:
                    return False
            if row.get('semantic'):
                load('operation-decisions').validate(self,p,row['semantic'],self.state['results'].get('verify',{}).get('observations',[]) if operation=='review' else [],operation)
            for name, expected in row.get('outputs', {}).items():
                if sha(safe(self.project, name)) != expected:
                    return False
            return True
        except (OSError, ValueError, KeyError):
            return False

    def assess(self, operation, mode='run'):
        if operation not in OPS:
            raise ValueError('unknown_operation')
        p, context = self.context()
        deps = self.dependencies(operation, p, context)
        blockers = []
        if any(r['current'] and not r['question'].get('response') for r in self.decision_rows(operation,deps)):blockers.append('operator_decision_required')
        required = list(deps['artifacts'])
        if any(context['artifacts'][k] is None for k in required):
            blockers.append('missing_input_artifacts')
        missing = [k for k in DEPS[operation] if not self.valid(k, p, context)]
        if missing:
            blockers.append('missing_current_results:' + ','.join(missing))
        if operation not in ('groom-spec','groom-rules') and context['artifacts']['scenarios']:
            try:self.scenarios(p)
            except (ValueError,OSError,KeyError,TypeError) as error:blockers.append(str(error))
        if operation=='verify' and not (self.valid('groom',p,context) or self.valid('adopt',p,context)):
            blockers.append('current_contract_or_explicit_external_adoption_required')
        if operation == 'verify' and any(v is None for v in context['tests'].values()):
            blockers.append('missing_test_scripts')
        if operation == 'review':
            row = self.state['results'].get('implement', {})
            if not self.valid('implement', p, context) or row.get('source') != context['source']:
                blockers.append('current_author_provenance_required:adopt')
            if row.get('provenance', {}).get('identity', 'unknown') == 'unknown':
                blockers.append('unknown_author_identity')
        if operation == 'publish' and p['publication'] is None:
            blockers.append('publication_target_required')
        # Canonical substantive signature deliberately excludes request IDs and finding wording.
        signature_deps = {k:v for k,v in deps.items() if k not in ('upstream','implementation','route','reviewer_policy','semantic_settings','executor_sha256','assets','contract')} if operation in REVIEW or operation == 'verify' else deps
        signature = digest(dict(dependencies=signature_deps, source=context['source'] if operation == 'implement' else {k:context['artifacts'][k] for k in ('spec','scenarios')} if operation=='groom-spec' else None))
        prior = [a for a in self.state['attempts'] if a['operation'] == operation]
        if any(a['status'] in ('pending', 'checkpoint') for a in self.state['attempts']):
            blockers.append('unfinished_operation:resume_existing_request')
        if any(a['status'] == 'failed' and a['signature'] == signature for a in prior):
            blockers.append('unchanged_failure_requires_repair')
        cap_prior = prior
        implementation = self.state['results'].get('implement', {})
        if operation in ('verify', 'review') and implementation.get('external') and self.valid('adopt', p, context):
            # Explicit adoption scopes verification/review to changed external work;
            # historical failures and identical-failure guards remain intact.
            key = 'implementation' if operation == 'review' else 'contract'
            adopted = implementation['digest'] if operation == 'review' else self.state['results']['adopt']['digest']
            cap_prior = [a for a in prior if a.get('prepared', {}).get('assessment', {}).get('dependencies', {}).get(key) == adopted]
        if sum(a['status'] == 'failed' for a in cap_prior) >= 3:
            blockers.append('repair_limit_exhausted')
        current = self.valid(operation, p, context)
        result = dict(version=VERSION, operation=operation, status='current' if current else 'blocked' if blockers else 'ready', blockers=blockers,
            binding=digest(dict(dependencies=deps, source=context['source'] if operation=='implement' else {k:context['artifacts'][k] for k in ('spec','scenarios')} if operation=='groom-spec' else None, mode=mode)),
            dependencies=deps, signature=signature, allowance=p['limits'][operation], aggregate=p['aggregate'],
            findings=sorted({f for a in (self.state['attempts'] if operation=='review' else prior) if a['status']=='failed' for f in a.get('findings',[])}),
            next_action='reuse' if current else blockers[0] if blockers else 'authorize',
            result=self.state['results'].get(operation))
        if operation in AI and not blockers and not current:
            try:
                self.packet(operation, result, p)
                if self.worker==self.dispatch and shutil.which('claude' if deps['route']['provider']=='claude' else 'codex') is None:raise ValueError('worker_runtime_unavailable')
                if operation in ('groom-adversarial','review'):load('operation-decisions').readiness(self,p,self.state['results'].get('verify',{}).get('observations',[]) if operation=='review' else [],operation)
            except (ValueError, OSError) as error:
                result.update(status='blocked', next_action='repair_inputs', blockers=[str(error)])
        result['questions']=self.decision_rows(operation,deps)
        if operation=='accept':result['manual_cases']=[dict(case,case_sha256=digest(case)) for case in self.scenarios(p) if case['manual']]
        return result

    def view(self):
        rows = []
        for operation in OPS:
            try:
                rows.append(self.assess(operation))
            except (OSError, ValueError, KeyError) as error:
                rows.append(dict(operation=operation, status='blocked', blockers=[str(error)], next_action='repair_inputs'))
        return dict(version=VERSION, task=self.task, operations=rows, authorizations=self.state['authorizations'], attempts=self.state['attempts'],
                    cancellations={key:dict(binding=load('operation-reconciliation').identity(self,g),intent=load('operation-reconciliation').intent(self,key)) for key,g in self.state['authorizations'].items()},reconciliation=[load('operation-reconciliation').assessment(self,a) for a in self.state['attempts'] if a['status'] in ('pending','checkpoint','cancelled_unknown')],
                    calls=self.state['calls'], supervisors=self.state.get('supervisors', {}), usage={key:dict(self.usage(key),wall_seconds=max(0,self.clock()-g['created'])) for key,g in self.state['authorizations'].items()}, recipes=RECIPES, next_actions=[r['operation'] for r in rows if r['status']=='ready'],
                    status='accepted' if any(r['operation']=='accept' and r['status']=='current' for r in rows) else 'pending_manual_acceptance' if any(r['operation']=='review' and r['status']=='current' for r in rows) else 'incomplete')

    def policy_binding(self,p):
        routing=load('routing-path').resolve(HERE.parent,self.project)
        return dict(routing_sha256=sha(routing),provider_policy=load('provider-policy').mode(self.project),
                    semantic_settings=load('operation-decisions').configuration(self) if p['reviewer_policy']['semantic_plan'] else None,
                    executor_sha256=sha(Path(__file__)), supervisor_sha256=sha(HERE/'nightshift-operation-supervisor.py'),retry_sha256=sha(HERE/'nightshift-retry-budget.py'), worker_sha256=sha(HERE/'nightshift-agent.sh'),
                    role_sha256=sha(HERE.parent/'agents/nightshift-operation-worker.md'),
                    schema_sha256=sha(HERE.parent/'contracts/nightshift-operation-worker.schema.json'),reconciliation_sha256=sha(HERE/'nightshift-operation-reconciliation.py'),execution_sha256=sha(HERE/'nightshift-controller-recovery.py'),supervisor_execution_sha256=sha(HERE/'nightshift-recovery-exec.py'))

    def delegate(self,grant,delegation):
        if delegation is None:return
        exact(delegation,'parent_cancellation deadline')
        parent=delegation['parent_cancellation'];exact(parent,'path binding')
        if not isinstance(parent['path'],str) or not Path(parent['path']).is_absolute() or Path(parent['path']).resolve()!=Path(parent['path']):raise ValueError('invalid_parent_cancellation_path')
        if not isinstance(parent['binding'],str) or not re.fullmatch(r'[a-f0-9]{64}',parent['binding']):raise ValueError('invalid_parent_cancellation_binding')
        if type(delegation['deadline']) not in (int,float) or not math.isfinite(delegation['deadline']):raise ValueError('invalid_parent_deadline')
        restrictions=grant.setdefault('parent_cancellations',[])
        if parent not in restrictions:restrictions.append(dict(parent))
        grant['deadline']=min(grant['deadline'],delegation['deadline'])

    def authorize(self, operations, expected, operator, request, attestation=None, delegation=None):
        if not bounded_text(operator) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', request):
            raise ValueError('operator_and_request_required')
        if not isinstance(operations, list) or not operations or len(set(operations)) != len(operations) or any(o not in OPS for o in operations):
            raise ValueError('invalid_recipe')
        with self.lease():
            if isinstance(attestation, dict) and 'bounded_repair' in attestation:
                if attestation['bounded_repair'] is not True or operations not in (RECIPES['factory'], RECIPES['groom']):
                    raise ValueError('invalid_bounded_repair_authority')
            if operations==['accept'] and isinstance(attestation,dict) and isinstance(attestation.get('cases'),list):
                attestation=dict(attestation,cases=sorted(attestation['cases'],key=lambda row:str(row.get('id','')) if isinstance(row,dict) else ''))
            old = self.state['authorizations'].get(request)
            payload = dict(operations=operations, expected=expected, operator=operator, attestation=attestation)
            if old:
                if old['request_digest'] != digest(payload):
                    raise ValueError('request_id_conflict')
                if delegation is not None:self.delegate(old,delegation);self.save()
                return old
            for existing in self.state['authorizations'].values():
                if existing['request_digest'] == digest(payload):
                    if delegation is not None:self.delegate(existing,delegation);self.save()
                    return existing
            assessed = self.assess(operations[0])
            if assessed['binding'] != expected:
                raise ValueError('stale_assessment')
            if assessed['status'] == 'blocked':
                raise ValueError(';'.join(assessed['blockers']))
            p, context = self.context()
            if 'accept' in operations:
                if operations!=['accept']:raise ValueError('acceptance_requires_separate_authority')
                normalized=manual_acceptance(self.project,p,expected,attestation)
                if assessed['status']=='current' and normalized!=assessed['result'].get('attestation'):raise ValueError('acceptance_already_current')
            # Exact input baseline; only controller-integrated outputs may advance it.
            policy_binding=self.policy_binding(p)
            grant = dict(version=VERSION,policy_binding=policy_binding, id=request, operations=operations, operator=operator, request_digest=digest(payload),
                         attestation=attestation, created=self.clock(), deadline=self.clock()+p['aggregate']['wall_seconds'],
                         plan_sha256=sha(plan_path(self.project, self.task)), baseline=self.corpus(),baseline_modes=self.modes(),
                         limits={o:p['limits'][o] for o in operations}, aggregate=p['aggregate'], statuses={}, bindings={operations[0]:expected})
            self.delegate(grant,delegation)
            grant['cancellation_binding']=load('operation-reconciliation').identity(self,grant)
            self.state['authorizations'][request] = grant
            self.save()
            return grant

    def usage(self, grant, operation=None):
        calls = [c for c in self.state['calls'].values() if c['grant']==grant and (operation is None or c['operation']==operation)]
        return dict(calls=len(calls), measured_seconds=sum(c['seconds'] for c in calls if c['status']=='finished'), reserved_unknown_seconds=sum(c['reserved_seconds'] for c in calls if c['status']!='finished'), seconds=sum(c['seconds'] if c['status']=='finished' else c['reserved_seconds'] for c in calls),
                    unknown=sum(c['status']!='finished' for c in calls), request_bytes=sum(c['request_bytes'] for c in calls))

    def reserve(self, grant, operation, key, request_bytes, seconds=None):
        with self.mutex:
            g = self.state['authorizations'][grant]
            self.cancellation_check(grant)
            if key in self.state['calls']:
                raise ValueError('invocation_already_reserved')
            remaining = []
            for op, limit in ((None, g['aggregate']), (operation, g['limits'][operation])):
                used = self.usage(grant, op)
                if used['calls'] >= limit['calls']:
                    raise ValueError('provider_call_limit_exhausted')
                remaining.append(limit['seconds']-used['seconds'])
            duration = min(*remaining, g['deadline']-self.clock(), g['limits'][operation]['wall_seconds'])
            if seconds is not None:
                if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<=0: raise ValueError('invalid_call_duration')
                duration=min(duration,seconds)
            if duration <= 0:
                raise ValueError('provider_time_limit_exhausted')
            row = dict(id=key, grant=grant, operation=operation, request_bytes=request_bytes, reserved_seconds=duration, status='pending', started=self.clock(), seconds=None)
            self.state['calls'][key] = row
            self.save()
            return row

    def finish(self, key, duration):
        with self.mutex:
            row = self.state['calls'][key]
            if row['status'] == 'finished':
                if row['seconds'] != duration:
                    raise ValueError('accounting_conflict')
                return
            if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
                raise ValueError('invalid_execution_duration')
            row.update(status='finished', seconds=duration)
            self.save()

    def scenarios(self,p):
        return scenarios(self.project,p)

    def packet(self, operation, assessed, p):
        names = set(p['inputs'].values())
        names.update(self.package_inputs(p))
        if operation in ('implement', 'review'):
            names.update(p['scope']); names.update(c['argv'][1] for c in p['checks'])
        data = {name: safe(self.project, name).read_text() for name in sorted(names) if safe(self.project, name).exists()}
        value = dict(version=VERSION, operation=operation, binding=assessed['binding'], artifacts=data,
            accepted_architecture=assessed['dependencies']['accepted_architecture'],
            scope=p['scope'], cases=self.scenarios(p) if operation!='groom-spec' else [], provenance=self.provenance(operation), findings=sorted(set(assessed['findings'] + self.repair_findings(operation))), checks=p['checks'],
            verification=self.state['results'].get('verify', {}).get('observations') if operation=='review' else None)
        if assessed['dependencies'].get('decisions'):value['operator_decisions']=assessed['dependencies']['decisions']
        package_schema=self.package_schema(p)
        if package_schema:
            value['package_authoring']=dict(schema=package_schema,instruction='Author complete child plans, specs and checks as inline artifact text. Preserve existing project inputs. Do not grant authority. Independent challenge must evaluate semantic requirement coverage, interfaces, test oracles and parent integration, not only IDs.')
        if operation in REVIEW:
            obligations=load('operation-decisions').packets(self,p,self.state['results'].get('verify',{}).get('observations',[]) if operation=='review' else [],operation)
            if obligations:value['semantic_obligations']=obligations
        repair = self.repair_evidence(operation)
        if repair:
            for name, expected in repair.get('evidence', {}).items():
                if sha(self.directory / name) != expected:
                    raise ValueError('stale_repair_evidence')
            tests = next((name for name in repair.get('evidence', {}) if name.endswith('.tests.json')), None)
            if tests:
                value['failed_verification'] = read(self.directory / tests)['observations']
        body = json.dumps(value, sort_keys=True).encode()
        framing = 4096 + 2*(HERE.parent/'agents/nightshift-operation-worker.md').stat().st_size + (HERE.parent/'contracts/nightshift-operation-worker.schema.json').stat().st_size
        if len(body) + framing > MAX_REQUEST:
            raise ValueError('operation_context_too_large:no_truncation')
        return value

    def dispatch(self, operation, packet, route, output, seconds):
        """Direct role transport in a disposable copy; no factory or ticket grant."""
        runner = load('controller-recovery')
        with tempfile.TemporaryDirectory(prefix='nightshift-operation-worker-') as tmp:
            target = Path(tmp).resolve()
            for name in self.corpus():
                path = safe(self.project, name)
                if path.exists():
                    dest = target / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
            routing = read(route['routing'])
            routing['roles']['nightshift-operation-worker'] = dict(prompt='agents/nightshift-operation-worker.md', sandbox='read-only', gears={'1':{k:route[k] for k in ('provider','model')}})
            route_file = target / '.operation-routing.json'; recovery.atomic(route_file, routing)
            input_file = target / '.operation-input.json'; recovery.atomic(input_file, packet)
            env = {k:v for k,v in os.environ.items() if not k.startswith(('NIGHTSHIFT_', 'AUTONOMOUS'))}
            env.update(NIGHTSHIFT_ROUTING_FILE=str(route_file), NIGHTSHIFT_PROJECT_DIR=str(target), NIGHTSHIFT_PROVIDER_POLICY=route['policy'], NIGHTSHIFT_TELEMETRY_DIR='off')
            code = runner.bounded(['bash', str(HERE/'nightshift-agent.sh'), 'nightshift-operation-worker', '--in', str(input_file), '--out', str(output)], target, env, seconds, output.with_suffix('.log'),cancellation=load('operation-reconciliation').paths(self,self.active_grant),ownership=output.with_suffix('.ownership.json'))
            if code:
                value=read(output) if output.exists() else {}
                # The launcher exits one after publishing a validated FAIL contract.
                # Transport failure envelopes have no operation input binding.
                completed_failure=(code==1 and value.get('status')=='FAIL' and isinstance(value.get('results'),dict)
                    and value['results'].get('binding')==packet['binding'] and isinstance(value.get('artifacts'),dict)
                    and all(value['artifacts'].get(key)==route[key] for key in ('provider','model')))
                if not completed_failure:raise ValueError('provider_exit:' + str(code))
        return read(output)

    def validate_worker(self, value, assessed, route):
        exact(value, 'status reason attempts artifacts rules_fired results')
        exact(value['artifacts'], 'branch diff provider model')
        if any(value['artifacts'][k] != route[k] for k in ('provider','model')):
            raise ValueError('worker_identity_mismatch')
        r = value['results']
        exact(r, 'binding decision findings resolved coverage'+(' question' if 'question' in r else ''))
        if r['binding'] != assessed['binding'] or r['decision'] not in ('approve','repair','abstain'):
            raise ValueError('invalid_worker_binding')
        for key in ('findings','resolved','coverage'):
            if not isinstance(r[key], list) or any(not bounded_text(s) for s in r[key]):
                raise ValueError('invalid_worker_findings')
        if r.get('question') is not None:
            if r['decision']!='abstain' or value['artifacts']['diff']:raise ValueError('invalid_question_effect')
            self.question(assessed['operation'],assessed['binding'],r['question'])
            raise ValueError('operator_decision_required')
        if value['status'] != 'SUCCESS' or r['decision'] != 'approve' or r['findings']:
            raise ValueError('substantive_failure')
        if assessed['operation'] in REVIEW:
            required = {'scope', 'rules', 'architecture', 'scenarios', 'correctness'}
            if assessed['operation']=='review': required.add('test_oracles')
            if not required.issubset(r['coverage']) or not set(assessed['findings']).issubset(r['resolved']):
                raise ValueError('review_obligations_unresolved')
        return r

    def test(self, p, seconds):
        runner = load('controller-recovery')
        observations = []
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='nightshift-operation-tests-') as tmp:
            target = Path(tmp).resolve()
            for name in self.corpus():
                src = safe(self.project, name)
                if src.exists():
                    dest = target/name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dest)
            env = runner.clean_environment(); env.update(p['environment']); env['NIGHTSHIFT_ROLE_CHILD']='1'
            adapter=load('verification-adapters')
            for check_index,check in enumerate(p['checks']):
                remaining = seconds-(time.monotonic()-start)
                self.cancellation_check(self.active_grant)
                output = self.directory / (self.active_request+'.observation-'+digest(check)+'.log')
                events=output.with_suffix('.events.json')
                binding=digest(dict(request=self.active_request,grant=self.active_grant,check=check,assets=adapter.assets(check),inputs=self.dependencies('verify',p,self.context()[1])))
                code=-1;reason=None;interrupted=None
                try:
                    if remaining<=0:raise ValueError('verification_deadline')
                    argv,execution_env=adapter.command(check,target,events,binding,env)
                    code = runner.bounded(argv, target, execution_env, remaining, output,cancellation=load('operation-reconciliation').paths(self,self.active_grant),ownership=output.with_suffix('.ownership.json'))
                except (OSError,ValueError,subprocess.SubprocessError) as error:
                    reason=str(error)
                    if 'operation_cancelled' in reason:interrupted=error
                except BaseException as error:
                    reason=type(error).__name__;interrupted=error
                finally:
                    retained={path.name:sha(path) for path in (output,events) if path.is_file() and not path.is_symlink()}
                    recovery.atomic(output.with_suffix('.partial.json'),dict(evidence=retained,request=self.active_request,check=check,termination=reason))
                row=adapter.observe(check,events,binding,code,output,reason)
                row['raw_evidence']=retained
                row['raw_output_sha256']=row['output_sha256']
                row['output']='Controller-validated typed observation:\n'+json.dumps({key:row[key] for key in ('version','adapter','binding','complete','status','reason','counts','events_sha256')},sort_keys=True)+'\nRaw process output:\n'+row['output']
                row['output_sha256']=hashlib.sha256(row['output'].encode()).hexdigest()
                if len(json.dumps(observations+[row],sort_keys=True).encode())>MAX_REQUEST:
                    row.update(tests=0,status='blocked',reason='verification_evidence_too_large',output='Verification evidence exceeds the bounded observation envelope; inspect retained raw evidence.',unexecuted=[item['id'] for item in p['checks'][check_index+1:]])
                    row['output_sha256']=hashlib.sha256(row['output'].encode()).hexdigest()
                observations.append(row)
                recovery.atomic(output.with_suffix('.typed.json'),row)
                if interrupted:raise interrupted
                if row['reason']=='verification_evidence_too_large':break
        return observations

    def patch(self, patch, allowed):
        if not patch:
            return {}
        with tempfile.TemporaryDirectory(prefix='nightshift-operation-patch-') as tmp:
            target = Path(tmp).resolve()
            subprocess.run(['git','init','-q',str(target)], check=True)
            for name in self.corpus():
                src = safe(self.project,name)
                if src.exists():
                    dest=target/name; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dest)
            result = subprocess.run(['git','apply','--numstat','-'], input=patch, text=True, capture_output=True, cwd=target)
            if result.returncode: raise ValueError('invalid_patch')
            names = [line.split('\t')[-1] for line in result.stdout.splitlines()]
            if not names or any(n not in allowed for n in names): raise ValueError('patch_outside_authorized_scope')
            result = subprocess.run(['git','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol','apply','--whitespace=error','-'],input=patch,text=True,capture_output=True,cwd=target)
            if result.returncode: raise ValueError('patch_does_not_apply')
            changes={}
            for name in names:
                path=safe(target,name)
                if not path.is_file(): raise ValueError('removal_requires_separate_authority')
                changes[name]=dict(before=sha(safe(self.project,name)) if safe(self.project,name).exists() else None, text=path.read_bytes().decode('utf-8'), after=sha(path))
            return changes

    def integrate(self, changes):
        for name,row in changes.items():
            dest=safe(self.project,name)
            current=sha(dest) if dest.exists() else None
            if current==row['after']: continue
            if current!=row['before']: raise ValueError('source_changed_before_integration')
            dest.parent.mkdir(parents=True,exist_ok=True)
            mode=stat.S_IMODE(dest.stat().st_mode) & 0o777 if dest.exists() else 0o644
            fd,tmp=tempfile.mkstemp(prefix='.nightshift-write-',dir=dest.parent)
            os.fchmod(fd,mode)
            with os.fdopen(fd,'wb') as stream:
                stream.write(row['text'].encode('utf-8')); stream.flush(); os.fsync(stream.fileno())
            os.replace(tmp,dest)

    def execute(self, grant_id, operation, request, supervised=False):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', request): raise ValueError('invalid_request_id')
        with self.lease():
            g=self.state['authorizations'].get(grant_id)
            if not g or operation not in g['operations']: raise ValueError('operation_not_authorized')
            self.cancellation_check(grant_id)
            if supervised and not (g.get('attestation') or {}).get('bounded_repair'):
                raise ValueError('bounded_repair_authorization_required')
            previous=next((a for a in self.state['attempts'] if a['request']==request),None)
            if previous:
                if previous['grant']!=grant_id or previous['operation']!=operation: raise ValueError('request_id_conflict')
                if previous['status']=='checkpoint': return self.finalize(previous)
                if previous['status']=='pending' and (self.directory/(request+'.worker.execution.json')).exists():
                    try: return self.recover_worker(previous)
                    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
                        previous.update(status='failed',reason=str(error),finished=self.clock())
                        try: previous['findings']=read(self.directory/(request+'.worker.json')).get('results',{}).get('findings',[])
                        except (OSError,ValueError): pass
                        if not previous['findings']:previous['findings']=[str(error)]
                        self.save();return previous
                if previous['status']=='passed':
                    p,ctx=self.context()
                    if not self.valid(operation,p,ctx):return dict(previous,status='stale',next_action='reassess_changed_dependencies')
                return dict(previous, next_action='inspect_unknown_invocation' if previous['status']=='pending' else 'reuse_receipt')
            assessed=self.assess(operation)
            if assessed['status']=='current': return dict(status='reused',result=assessed['result'])
            if assessed['blockers']: raise ValueError(';'.join(assessed['blockers']))
            if self.clock()>=g['deadline']: raise ValueError('authorization_expired')
            if sha(plan_path(self.project,self.task))!=g['plan_sha256'] or self.corpus()!=g['baseline'] or self.modes()!=g['baseline_modes']: raise ValueError('authorized_inputs_changed')
            p,context=self.context()
            if self.policy_binding(p)!=g['policy_binding']: raise ValueError('authorized_policy_changed')
            if operation in g['bindings'] and assessed['binding']!=g['bindings'][operation]: raise ValueError('authorized_binding_changed')
            packet=self.packet(operation,assessed,p) if operation in AI else None
            route=self.route(operation,p) if operation in AI else None
            if operation in ('adopt','accept','publish'):
                att=g['attestation']
                if not isinstance(att,dict) or att.get('binding')!=assessed['binding']: raise ValueError('bound_human_attestation_required')
                if operation=='adopt' and (not bounded_text(att.get('identity')) or att['identity']=='unknown' or att.get('provider') not in ('human','claude','codex','local')): raise ValueError('external_author_provenance_required')
                if operation=='accept':manual_acceptance(self.project,p,assessed['binding'],att)
                if operation=='publish' and att.get('publication')!=p['publication']: raise ValueError('explicit_publication_authority_required')
            if supervised:
                self.retry_account(dict(operation=operation,request=request),'pending')
            attempt=dict(version=VERSION, request=request, operation=operation, grant=grant_id, binding=assessed['binding'], signature=assessed['signature'], status='pending', started=self.clock(), findings=[], prepared=dict(assessment=assessed,baseline=g['baseline'],baseline_modes=g['baseline_modes'],plan_sha256=g['plan_sha256'],route=route))
            self.state['attempts'].append(attempt); self.save()
            self.active_grant=grant_id
            self.active_request=request
            output=self.directory/(request+'.worker.json')
            checkpoint=self.directory/(request+'.checkpoint.json')
            result=dict(evidence={}, outputs={}, provenance={'provider':'controller','model':'none','identity':g['operator']}, source=context['source'])
            if assessed['dependencies'].get('decisions'):result['operator_decisions']=assessed['dependencies']['decisions']
            changes={}
            try:
                if operation in AI:
                    call=self.reserve(grant_id,operation,request+':worker',len(json.dumps(packet,sort_keys=True).encode()))
                    started=time.monotonic()
                    try:
                        value=self.worker(operation,packet,route,output,call['reserved_seconds'])
                        recovery.atomic(output,value)
                        recovery.atomic(output.with_suffix('.execution.json'),dict(call=call['id'],seconds=time.monotonic()-started,sha256=sha(output),finished=self.clock()))
                    finally:
                        completion=output.with_suffix('.execution.json')
                        if completion.exists():self.finish(call['id'],read(completion)['seconds'])
                        elif output.with_suffix('.ownership.json').exists() and read(output.with_suffix('.ownership.json')).get('status')=='not_started':self.finish(call['id'],0)
                    if self.state['calls'][call['id']]['seconds'] > call['reserved_seconds']: raise ValueError('provider_execution_exceeded_allowance')
                    checked=self.validate_worker(value,assessed,route)
                    if operation in REVIEW and not {c['id'] for c in self.scenarios(p)}.issubset(checked['coverage']): raise ValueError('case_review_incomplete')
                    result['provenance']=dict(provider=route['provider'],model=route['model'],identity=call['id'])
                    result['evidence'][output.name]=sha(output)
                    result['review']=checked
                    if operation in ('groom-adversarial','review'):result['semantic']=load('operation-decisions').run(self,p,grant_id,operation,self.state['results'].get('verify',{}).get('observations',[]) if operation=='review' else [],route)
                    if operation in ('groom-spec','implement'):
                        allowed=[p['inputs']['spec'],p['inputs']['scenarios']] if operation=='groom-spec' else p['scope']
                        changes=self.patch(value['artifacts']['diff'],allowed)
                    elif value['artifacts']['diff']: raise ValueError('review_cannot_change_source')
                elif operation=='groom-rules':
                    result['resolved'] = dict(rules=context['artifacts']['rules'], architecture=context['artifacts']['architecture'], accepted=context['accepted_architecture'])
                elif operation=='verify':
                    result['architecture'] = load('architecture').check(self.project,self.task,context['accepted_architecture'])
                    if result['architecture']['status']!='pass': raise ValueError('architecture_constraints_failed')
                    result['observations']=self.test(p,min(g['deadline']-self.clock(),g['limits'][operation]['wall_seconds']))
                    raw=self.directory/(request+'.tests.json'); recovery.atomic(raw,{'observations':result['observations']}); result['evidence'][raw.name]=sha(raw)
                    for observation in result['observations']:result['evidence'].update(observation.get('raw_evidence',{}))
                    if any(r['exit_code']!=0 or r['tests']<=0 for r in result['observations']): raise ValueError('failed_or_vacuous_tests')
                elif operation=='adopt':
                    result['provenance']={k:g['attestation'].get(k,'unknown') for k in ('provider','model','identity')}
                elif operation=='accept':
                    result['attestation']=manual_acceptance(self.project,p,assessed['binding'],g['attestation'])
                    result['operator']=g['operator']
                elif operation=='publish':
                    result['publication']=self.publish(p)
                self.cancellation_check(grant_id)
                # A read/review/test must not move its own evidence baseline.
                if self.corpus()!=g['baseline'] or self.modes()!=g['baseline_modes']: raise ValueError('inputs_changed_during_operation')
                if self.clock() > min(g['deadline'], attempt['started'] + g['limits'][operation]['wall_seconds']): raise ValueError('operation_deadline_exceeded')
                recovery.atomic(checkpoint,dict(result=result,changes=changes,assessment=assessed,baseline=g['baseline'],baseline_modes=g['baseline_modes'],plan_sha256=g['plan_sha256']))
                attempt.update(status='checkpoint',checkpoint=checkpoint.name,checkpoint_sha256=sha(checkpoint)); self.save()
                return self.finalize(attempt)
            except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
                if attempt['status']=='checkpoint': raise
                attempt.update(status='pending' if load('operation-reconciliation').effective_intent(self,grant_id) else 'failed',reason=str(error),finished=self.clock(), evidence=result['evidence'])
                if output.exists():
                    attempt['evidence'][output.name] = sha(output)
                    try: attempt['findings']=read(output).get('results',{}).get('findings',[])
                    except (ValueError,OSError): pass
                if not attempt['findings']: attempt['findings']=[str(error)]
                self.save()
                return attempt

    def recover_worker(self, attempt):
        """Reconcile a controller completion receipt; never relaunch a provider."""
        output=self.directory/(attempt['request']+'.worker.json')
        execution=read(output.with_suffix('.execution.json'))
        prepared=attempt['prepared'];operation=attempt['operation'];g=self.state['authorizations'][attempt['grant']]
        call=self.state['calls'].get(execution['call'])
        if not call or call['id']!=attempt['request']+':worker' or sha(output)!=execution['sha256']:raise ValueError('invalid_execution_checkpoint')
        if self.modes()!=prepared['baseline_modes'] or self.corpus()!=prepared['baseline'] or sha(plan_path(self.project,self.task))!=prepared['plan_sha256']:raise ValueError('checkpoint_inputs_changed')
        if call['status']!='finished': self.finish(call['id'],execution['seconds'])
        if execution['seconds']>call['reserved_seconds'] or execution['finished']>min(g['deadline'],attempt['started']+g['limits'][operation]['wall_seconds']):raise ValueError('checkpoint_execution_exceeded_allowance')
        p,context=self.context();assessed=prepared['assessment'];route=prepared['route']
        if self.policy_binding(p)!=g['policy_binding']:raise ValueError('checkpoint_policy_changed')
        if self.dependencies(operation,p,context)!=assessed['dependencies']:raise ValueError('checkpoint_dependencies_changed')
        value=read(output);checked=self.validate_worker(value,assessed,route)
        if operation in REVIEW and not {c['id'] for c in self.scenarios(p)}.issubset(checked['coverage']):raise ValueError('case_review_incomplete')
        result=dict(evidence={output.name:sha(output)},outputs={},source=context['source'],review=checked,
                    provenance=dict(provider=route['provider'],model=route['model'],identity=call['id']))
        if assessed['dependencies'].get('decisions'):result['operator_decisions']=assessed['dependencies']['decisions']
        changes={}
        if operation in ('groom-spec','implement'):
            allowed=[p['inputs']['spec'],p['inputs']['scenarios']] if operation=='groom-spec' else p['scope']
            changes=self.patch(value['artifacts']['diff'],allowed)
        elif value['artifacts']['diff']:raise ValueError('review_cannot_change_source')
        if getattr(self,'reconciling',False) and load('operation-decisions').selected(self,p,operation):raise ValueError('semantic_reconciliation_requires_retained_complete_checkpoint')
        if operation in ('groom-adversarial','review'):result['semantic']=load('operation-decisions').run(self,p,attempt['grant'],operation,self.state['results'].get('verify',{}).get('observations',[]) if operation=='review' else [],route)
        checkpoint=self.directory/(attempt['request']+'.checkpoint.json')
        recovery.atomic(checkpoint,dict(result=result,changes=changes,assessment=assessed,baseline=prepared['baseline'],baseline_modes=prepared['baseline_modes'],plan_sha256=prepared['plan_sha256']))
        attempt.update(status='checkpoint',checkpoint=checkpoint.name,checkpoint_sha256=sha(checkpoint));self.save()
        return self.finalize(attempt)

    def finalize(self, attempt):
        self.cancellation_check(attempt['grant'])
        checkpoint=self.directory/attempt['checkpoint']
        if sha(checkpoint)!=attempt['checkpoint_sha256']: raise ValueError('checkpoint_tampered')
        data=read(checkpoint); result=data['result']; operation=attempt['operation']
        if sha(plan_path(self.project,self.task)) != data['plan_sha256']: raise ValueError('checkpoint_plan_changed')
        current=self.corpus(); expected=dict(data['baseline'])
        for name,row in data['changes'].items():
            if current.get(name) == row['after']: expected[name]=row['after']
        if current!=expected: raise ValueError('checkpoint_inputs_changed')
        expected_modes=dict(data['baseline_modes'])
        for name,row in data['changes'].items():
            if name not in expected_modes and current.get(name)==row['after']:expected_modes[name]=0o644
        if self.modes()!=expected_modes:raise ValueError('checkpoint_modes_changed')
        for name,expected_hash in result['evidence'].items():
            if sha(self.directory/name)!=expected_hash: raise ValueError('checkpoint_evidence_changed')
        p,ctx=self.context()
        if self.policy_binding(p)!=self.state['authorizations'][attempt['grant']]['policy_binding']:raise ValueError('checkpoint_policy_changed')
        if self.dependencies(operation,p,ctx)!=data['assessment']['dependencies']: raise ValueError('checkpoint_dependencies_changed')
        with load('operation-reconciliation').integration_guard(self,attempt['grant']):
            self.integrate(data['changes'])
        p,context=self.context()
        if operation=='groom-spec':
            for key in ('spec','scenarios'):
                path=safe(self.project,p['inputs'][key])
                if not path.exists() or not path.read_text().strip(): raise ValueError('draft_outputs_missing')
            result['outputs']={p['inputs'][k]:sha(safe(self.project,p['inputs'][k])) for k in ('spec','scenarios')}
        result['source']=context['source']
        result.update(version=VERSION, completed_at=self.clock(), operation=operation, dependencies=self.dependencies(operation,p,context), request=attempt['request'], evidence={**result['evidence'],checkpoint.name:sha(checkpoint)})
        result['digest']=digest(result)
        self.state['results'][operation]=result
        if operation=='adopt':
            implementation=dict(result,operation='implement',external=True,dependencies=self.dependencies('implement',p,context))
            implementation.pop('digest'); implementation['digest']=digest(implementation)
            self.state['results']['implement']=implementation
        attempt.update(status='passed',finished=self.clock(),result=result['digest'])
        self.state['authorizations'][attempt['grant']]['baseline']=self.corpus()
        self.state['authorizations'][attempt['grant']]['baseline_modes']=self.modes()
        self.state['authorizations'][attempt['grant']]['statuses'][operation]='passed'
        self.save()
        return attempt

    def publish(self,p):
        target=p['publication']
        def git(*args): return subprocess.check_output(['git','-C',str(self.project),*args],stderr=subprocess.PIPE,text=True).strip()
        if git('symbolic-ref','--short','HEAD')!=target['branch']: raise ValueError('publication_branch_mismatch')
        if git('status','--porcelain'): raise ValueError('publication_requires_reviewed_commit_clean_tree')
        head=git('rev-parse','HEAD')
        git('push',target['remote'],'HEAD:refs/heads/'+target['branch'])
        return dict(head=head,remote=target['remote'],branch=target['branch'])

    def chain(self, grant):
        self.reload()
        if grant not in self.state['authorizations']: raise ValueError('authorization_required')
        results=[]
        for operation in self.state['authorizations'][grant]['operations']:
            result=self.execute(grant,operation,grant+'.'+operation)
            results.append(result)
            if result['status'] not in ('passed','reused'): break
        return dict(results=results,view=self.view())

    def migrate(self, operator, request):
        """Import an existing draft as draft evidence only; old state stays untouched."""
        with self.lease():
            p,context=self.context()
            if not bounded_text(operator): raise ValueError('operator_required')
            if not all(context['artifacts'].values()): raise ValueError('retained_contract_inputs_missing')
            if self.state['results'].get('groom-spec'): return self.state['results']['groom-spec']
            paths=[self.directory.parent.parent/'pipeline'/self.task/'state.json',load('ticket-budget').ledger_path(self.project,self.task)]
            historical={str(path):sha(path) for path in paths if path.is_file()}
            row=dict(version=VERSION,operation='groom-spec',dependencies=self.dependencies('groom-spec',p,context),request=request,
                     evidence={},outputs={p['inputs'][k]:context['artifacts'][k] for k in ('spec','scenarios')},
                     provenance=dict(provider='unknown',model='unknown',identity='unknown'))
            row['digest']=digest(row);self.state['results']['groom-spec']=row
            self.state['imports'].append(dict(operator=operator,request=request,historical=historical,kind='draft_only'))
            self.save();return row


def factory(project, task):
    controller=Operations(project,task)
    for grant in reversed(list(controller.state['authorizations'].values())):
        if grant['operations']==RECIPES['factory']:
            if (grant.get('attestation') or {}).get('bounded_repair'):
                return load('operation-supervisor').run(controller, grant['id'])
            return controller.chain(grant['id'])
    return dict(status='blocked',reason='factory_recipe_requires_explicit_authorization',recipe=RECIPES['factory'],view=controller.view())


def api(project, body):
    if not isinstance(body,dict) or set(body)-{'task','action','operation','operations','binding','operator','request','grant','attestation','source','choices','question','choice','answer','resolution'}:
        raise ValueError('invalid_operation_request')
    if isinstance(body.get('action'),str) and body['action'].startswith('intake-'):return load('intake').api(project,body)
    if isinstance(body.get('action'),str) and body['action'].startswith('packages-'):
        package_body=dict(body,action=body['action'][len('packages-'):])
        return load('package-controller').api(project,package_body)
    controller=Operations(project,body['task'])
    action=body['action']
    if action=='cancel':return load('operation-reconciliation').cancel(controller,body['grant'],body['binding'],body['operator'],body['request'])
    if action=='reconcile':return load('operation-reconciliation').reconcile(controller,body['request'],body['binding'],body['operator'],body['resolution'])
    if action=='question':
        with controller.lease():return controller.question(body['operation'],body['binding'],body['question'])
    if action=='answer':return controller.answer(body['operation'],body['binding'],body['question'],body.get('choice',''),body.get('answer',''))
    if action=='factory': return factory(project,body['task'])
    if action=='view': return controller.view()
    if action=='semantic-map':return load('operation-decisions').generate(controller,plan(controller.project,controller.task),body['operation'])
    if action=='assess': return controller.assess(body['operation'])
    if action=='authorize': return controller.authorize(body['operations'],body['binding'],body['operator'],body['request'],body.get('attestation'))
    if action=='run': return controller.execute(body['grant'],body['operation'],body['request'])
    if action=='chain': return controller.chain(body['grant'])
    if action=='supervise': return load('operation-supervisor').run(controller, body['grant'])
    if action=='migrate': return controller.migrate(body['operator'],body['request'])
    raise ValueError('unknown_operation_action')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('view','assess','authorize','run','chain','supervise','migrate','factory','semantic-map','question','answer','cancel','reconcile'))
    parser.add_argument('task');parser.add_argument('operation',nargs='?',choices=OPS)
    parser.add_argument('--project',default=os.getcwd());parser.add_argument('--binding');parser.add_argument('--operator');parser.add_argument('--request');parser.add_argument('--grant')
    parser.add_argument('--recipe',choices=RECIPES);parser.add_argument('--attestation',type=json.loads)
    parser.add_argument('--resolution',choices=('finalize','preserve'))
    parser.add_argument('--question',type=json.loads);parser.add_argument('--choice');parser.add_argument('--answer')
    args=parser.parse_args()
    body={k:v for k,v in vars(args).items() if v is not None and k not in ('project','recipe')}
    if args.action=='authorize':body['operations']=RECIPES[args.recipe] if args.recipe else [args.operation]
    try:
        value=api(args.project,body); print(json.dumps(value));return 0 if value.get('status') not in ('blocked','failed','pending') else 1
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='blocked',reason=str(error))));return 1


if __name__=='__main__':raise SystemExit(main())
