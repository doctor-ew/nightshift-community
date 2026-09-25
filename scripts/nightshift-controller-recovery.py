#!/usr/bin/env python3
"""Hash-bound, explicitly authorized adoption of externally completed work.

Assessment is read-only. Recovery uses its own nonrenewable allowance and the
pipeline controller lock. Original attempts, receipts and budgets remain intact.
"""
import argparse
from contextlib import contextmanager
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid

HERE = Path(__file__).resolve().parent

def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / ('nightshift-' + name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

p = load('pipeline')
digest = p.recovery.digest
LIMITS = dict(wall_seconds=600, active_seconds=600, provider_calls=4)
GATES = ('adoption', 'review', 'drift', 'qa')


def git(target, *args):
    return subprocess.check_output(['git', '-C', str(target), *args], stderr=subprocess.PIPE).decode().strip()


def safe_file(target, name, maximum=2_000_000):
    path = Path(target) / name
    if Path(name).is_absolute() or '..' in Path(name).parts or path.absolute() != path.resolve() or not path.is_file():
        raise ValueError('recovery_unsafe_file:' + str(name))
    if path.stat().st_size > maximum:
        raise ValueError('recovery_file_too_large:' + str(name))
    return path


def target_state(project, task):
    state = p.snapshot(project, task)
    if state is None:
        raise ValueError('recovery_requires_retained_controller')
    target = Path(state['worktree']).resolve(strict=True)
    owner = p.read(p.root(project, task).parent.parent / 'worktrees' / (task + '.json'))
    if Path(owner['worktree']).resolve() != target or p.root(target, task) != p.root(project, task):
        raise ValueError('recovery_worktree_identity_changed')
    return target, state, owner


def evidence(project, task):
    target, state, owner = target_state(project, task)
    # Exact bytes, including attestations and externally edited tests, are bound.
    manifest=load('project-context').manifest_path(target)
    tomllib.loads(manifest.read_text())
    subprocess.run(['git','-C',str(target),'merge-base','--is-ancestor',owner['base_sha'],'HEAD'],check=True,capture_output=True,timeout=10)
    workspace = p.recovery.workspace(target)
    docs = target / 'docs' / task
    scenarios = p.read(docs / 'behavior-scenarios.json')
    if git(target, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('recovery_requires_committed_source')
    if scenarios.get('task') != task or scenarios.get('applicability', {}).get('kind') != 'deterministic':
        raise ValueError('recovery_requires_deterministic_scenarios')
    cases = scenarios.get('cases', [])
    if not cases or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('recovery_invalid_cases')
    if any(c.get('applicability', {}).get('kind') not in ('deterministic', 'manual') for c in cases):
        raise ValueError('recovery_model_dependent_evidence_not_supported')
    # Reports identify candidate test commands only; their claimed exits do not pass gates.
    decision_plan = docs / 'recovery-plan.json'
    report_path = safe_file(target, 'docs/' + task + '/direct-verification/results.json') if not decision_plan.exists() else safe_file(target, 'docs/' + task + '/recovery-plan.json')
    report = json.loads(report_path.read_text())
    if decision_plan.exists(): report = report.get('checks', [])
    if not isinstance(report, list) or not 1 <= len(report) <= 20:
        raise ValueError('recovery_test_plan_missing')
    checks = []
    for row in report:
        if decision_plan.exists():
            argv=row.get('argv',[])
            if len(argv)!=2 or argv[0] not in ('bash','python3'): raise ValueError('recovery_invalid_test_command')
            path=safe_file(target,argv[1]); checks.append(dict(id=row['id'],argv=argv,sha256=p.sha(path))); continue
        name = row.get('test', '')
        if not re.fullmatch(r'test-[A-Za-z0-9_.-]+\.sh', name):
            raise ValueError('recovery_invalid_test_name')
        rel = 'evals/unit/' + name
        path = safe_file(target, rel)
        checks.append(dict(id=name, argv=['bash', rel], sha256=p.sha(path)))
    if len({c['id'] for c in checks}) != len(checks):
        raise ValueError('recovery_duplicate_test')
    # Preserve every controller and classification finding with a stable identity.
    findings = []
    for row in state.get('recovery_origin', state).get('findings', []):
        findings.append(dict(id=digest(row), finding=row, source='controller'))
    receipts = {}
    for path in sorted(docs.glob('classification-review*.out.json')):
        record = p.read(path); receipts[str(path.relative_to(target))] = p.sha(path)
        for index, finding in enumerate(record.get('results', {}).get('findings', [])):
            findings.append(dict(id=digest([str(path.name), index, finding]), finding=finding, source=path.name))
    common = p.root(project, task).parent.parent
    original = {}
    for folder in ('ticket-budgets', 'classification-budgets'):
        candidate = (load('ticket-budget').ledger_path(project, task) if folder == 'ticket-budgets'
                     else common / folder / (task + '.json'))
        original[str(candidate)] = p.sha(candidate) if candidate.exists() else None
    for path in sorted(p.root(project, task).glob('*')):
        if path.is_file() and path.name not in ('state.json', 'controller.lock'):
            original[str(path)] = p.sha(path)
    settings_path = common / 'console' / (task + '.json')
    settings = p.read(settings_path)['settings']
    if settings.get('auth') != 'subscription':
        raise ValueError('recovery_requires_subscription_auth')
    plan = p.routes(target, settings)
    route = plan['stages']['review']
    # The independent route is selected by the effective provider policy.
    if route['provider'] not in ('claude','codex'):
        raise ValueError('recovery_requires_tool_free_independent_reviewer')
    decisions = load('console-decisions').snapshot(project, task)
    if decisions.get('pending'):
        raise ValueError('recovery_pending_operator_decision')
    author = git(target, 'show', '-s', '--format=%an%x00%ae', 'HEAD').split('\0')
    changed = git(target, 'diff', '--name-only', owner['base_sha'], 'HEAD').splitlines()
    source_files = [name for name in changed if not name.startswith(('docs/' + task + '/', '.nightshift/'))]
    if not source_files:
        raise ValueError('recovery_external_implementation_missing')
    authorship={}
    for name in source_files+['docs/'+task+'/SPEC.md','docs/'+task+'/behavior-scenarios.json']:
        fields=git(target,'log','-1','--format=%H%x00%an%x00%ae','--',name).split('\0')
        if len(fields)!=3: raise ValueError('recovery_author_provenance_missing:'+name)
        authorship[name]=dict(commit=fields[0],name=fields[1],email=fields[2],execution_identity='not_recorded')
    assets = ['scripts/nightshift-controller-recovery.py', 'scripts/nightshift-agent.sh',
              'scripts/nightshift-contract.jq', 'scripts/nightshift-pipeline.py', 'scripts/nightshift-recovery-exec.py',
              'agents/nightshift-recovery-reviewer.md', 'contracts/nightshift-recovery-reviewer.schema.json',
              'scripts/nightshift-provider-policy.py', 'scripts/nightshift-project-context.py',
              'scripts/nightshift-routing-path.py', 'scripts/nightshift-architecture.py']
    assets += ['scripts/nightshift-decision-engine.py','scripts/nightshift-recovery-decisions.py',
               'agents/nightshift-decision-reviewer.md','contracts/nightshift-decision-reviewer.schema.json',
               'scripts/nightshift-efficiency.py']
    assets += ['commands/nightshift-'+stage+'.md' for stage in p.STAGES]
    verification_environment=dict(NIGHTSHIFT_PYTHON3=shutil.which('python3'))
    if decision_plan.exists(): verification_environment.update(json.loads(decision_plan.read_text()).get('environment',{}))
    value = dict(version=1, task=task, worktree=str(target), workspace=workspace,
                 spec_sha256=p.sha(docs / 'SPEC.md'), scenario_sha256=p.sha(docs / 'behavior-scenarios.json'),
                 source_sha256=p.source(target, task), manifest=dict(path=str(manifest),sha256=p.sha(manifest)), findings=findings, failed_receipts=receipts,
                 original_evidence=original, controller_origin_sha256=digest(state.get('recovery_origin', {k:v for k,v in state.items() if k!='recovery_sessions'})), settings_sha256=p.sha(settings_path),
                 decisions=decisions, architecture=load('architecture').resolve(target), plan=plan,
                 cases=cases, ac_ids=scenarios['ac_ids'], checks=checks, source_files=source_files,
                 author=dict(kind='git_commit_author', name=author[0], email=author[1],
                             commit=workspace['head'], execution_identity='not_recorded'),
                 retained_spec_author=scenarios['author'], current_file_authorship=authorship, reviewer_route=route,
                 assets={name:p.sha(HERE.parent / name) for name in assets},
                 verification_environment=verification_environment, limits=LIMITS)
    value['decision_readiness']=load('recovery-decisions').readiness(value)
    if value['decision_readiness']['status']=='ready': value['limits']=value['decision_readiness']['limits']
    return value, {}


def assessment(project, task, verify=False):
    value, corpus = evidence(project, task)
    binding = digest(value)
    _, state, _ = target_state(project, task)
    session = state.get('recovery_sessions', {}).get(binding)
    result = dict(status='assessment', sha256=binding, evidence=value,
                  next_step='Independently verify and review current work; adopt only passing evidence, then review, drift and QA. Manual acceptance remains pending.',
                  requested_allowance=value['limits'] if not session and value['decision_readiness']['status']=='ready' else None, session=session,
                  decisions=value['decision_readiness'],
                  message='Read-only recovery assessment. No allowance granted or provider invoked.')
    if verify:
        result['verification'] = verify_checks(value, timeout=600)
        current_binding(project,task,binding)
        if value['decision_readiness']['status']=='ready':
            adapter=load('recovery-decisions')
            for gate in GATES:
                for packet in adapter.packets(value,result['verification'],gate):
                    adapter.engine.request_body(packet,value['decision_readiness']['settings'])
    return result


def clean_environment():
    # Tests execute copied source; never inherit target paths, secrets or a parent budget.
    keep = ('PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'SYSTEMROOT')
    return {key:os.environ[key] for key in keep if key in os.environ}


def bounded(argv, cwd, env, timeout, output):
    with output.open('wb') as log:
        supervised=[sys.executable,str(HERE/'nightshift-recovery-exec.py'),str(os.getpid()),str(timeout),str(output),*argv]
        child = subprocess.Popen(supervised, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        started = time.monotonic()
        try:
            while child.poll() is None:
                if time.monotonic() - started >= timeout or output.stat().st_size > 2_000_000:
                    raise ValueError('recovery_execution_bound_exceeded')
                time.sleep(.05)
            return child.returncode
        finally:
            # Kill descendants even if the immediate command has already exited.
            try: os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait()


def verify_checks(value, timeout):
    started = time.monotonic()
    target = Path(value['worktree'])
    results = []
    with tempfile.TemporaryDirectory(prefix='nightshift-recovery-checks-', ignore_cleanup_errors=True) as tmp:
        base = Path(tmp).resolve(); copied = base / 'source'; copied.mkdir()
        for name, sha in value['workspace']['files'].items():
            if sha is None: continue
            source = safe_file(target, name, 64*1024*1024)
            if p.sha(source) != sha: raise ValueError('recovery_inputs_changed')
            path = copied / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.read_bytes()); path.chmod(source.stat().st_mode & 0o777)
        env = clean_environment(); env.update(value['verification_environment']); env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_0='gc.auto', GIT_CONFIG_VALUE_0='0', GIT_CONFIG_KEY_1='maintenance.auto', GIT_CONFIG_VALUE_1='false'); env['HOME'] = str(base / 'home'); Path(env['HOME']).mkdir()
        for argv in (['git', 'init', '-q', '--initial-branch=main'], ['git', 'config', 'user.name', 'Recovery verification'],
                     ['git', 'config', 'user.email', 'recovery@localhost'], ['git', 'add', '.'],
                     ['git', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Bound recovery snapshot']):
            subprocess.run(argv, cwd=copied, env=env, check=True, capture_output=True, timeout=30)
        for check in value['checks']:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0: raise ValueError('recovery_allowance_exhausted')
            output = base / 'check.log'
            code = bounded(check['argv'], copied, env, min(120, remaining), output)
            results.append(dict(id=check['id'], argv=check['argv'], exit_code=code,
                                output=output.read_text(errors='replace'), output_sha256=p.sha(output)))
            if sum(len(r['output'].encode()) for r in results)>500_000: raise ValueError('recovery_test_output_limit')
            if code: break
    return dict(binding=digest(value), status='pass' if len(results)==len(value['checks']) and all(r['exit_code']==0 for r in results) else 'fail', checks=results)


def compact_review(value,packet,mode,output,timeout):
    """One isolated reviewer sees only the obligation; primary answer is withheld."""
    decision=load('decision-engine');reviewer_id='decision-review-'+uuid.uuid4().hex
    envelope=dict(packet=packet,packet_sha256=decision.digest(packet),reviewer_id=reviewer_id,mode=mode)
    if len(decision.encoded(envelope))>decision.MAX_BYTES:raise ValueError('decision_review_request_too_large')
    request=output.with_suffix('.input.json');p.recovery.atomic(request,envelope)
    routing=p.read(value['plan']['routing_path'])
    routing['roles']['nightshift-decision-reviewer']=dict(prompt='agents/nightshift-decision-reviewer.md',sandbox='read-only',gears={'1':value['reviewer_route']})
    route_file=output.with_suffix('.routing.json');p.recovery.atomic(route_file,routing)
    env=dict(os.environ)
    for key in list(env):
        if key.startswith('NIGHTSHIFT_') or key in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','OPENAI_API_KEY'):
            env.pop(key)
    env.update(NIGHTSHIFT_ROUTING_FILE=str(route_file),NIGHTSHIFT_UPDATE_GUARD='1')
    with tempfile.TemporaryDirectory(prefix='nightshift-decision-review-') as tmp:
        code=bounded(['bash',str(HERE/'nightshift-agent.sh'),'nightshift-decision-reviewer','--gear','1',
                      '--in',str(request),'--out',str(output),'--auth','subscription'],tmp,env,timeout,output.with_suffix('.log'))
    if code:raise ValueError('decision_reviewer_exit_'+str(code))
    report=p.read(output)
    if report.get('status')!='SUCCESS' or any(report.get('artifacts',{}).get(k)!=value['reviewer_route'][k] for k in ('provider','model')):
        raise ValueError('decision_reviewer_identity_mismatch')
    result=report['results']
    if result.get('reviewer_id')!=reviewer_id:raise ValueError('decision_reviewer_identity_mismatch')
    return result


def compact_verdict(value,stage,checks,session,directory,save,step,transport=None,escalator=None):
    adapter=load('recovery-decisions');decision=adapter.engine
    packets=adapter.packets(value,checks,stage)
    settings=value['decision_readiness']['settings'];budget=session['allowance']
    def remaining():
        return min(budget['deadline_at']-time.time(),budget['active_seconds']-budget['active_used']-(time.time()-step['started_at']))
    def reserve(kind,request_id,request_bytes):
        if remaining()<=0 or budget['calls_used']>=budget['provider_calls']:raise ValueError('recovery_allowance_exhausted')
        if request_bytes>decision.MAX_BYTES:raise ValueError('decision_request_too_large')
        calls=session.setdefault('decision_calls',{})
        if request_id in calls:raise ValueError('decision_duplicate_reservation')
        budget['calls_used']+=1
        calls[request_id]=dict(kind=kind,request_bytes=request_bytes,status='pending',started_at=time.time())
        save();return request_id
    def finish(request_id,outcome):
        session['decision_calls'][request_id].update(status=outcome,finished_at=time.time())
        save()
        if remaining()<=0:raise ValueError('recovery_allowance_exhausted')
    def invoke_jev(cfg,key,body):
        actual=dict(cfg,timeout_seconds=max(.001,min(cfg['timeout_seconds'],remaining())))
        return (transport or load('efficiency').bounded_request)(actual,key,body)
    def escalate(packet,primary,mode):
        output=directory/('decision-'+decision.digest(packet)+'.review.json')
        return (escalator or compact_review)(value,packet,mode,output,max(.001,min(120,remaining())))
    evaluator=decision.Engine(directory/'decisions',session['binding'],settings,reserve,finish,
                              transport=invoke_jev,escalate=escalate)
    receipts=[]
    for packet in packets:
        current_binding(value['worktree'],value['task'],session['binding'])
        receipt=evaluator.decide(packet);receipts.append(receipt)
        if receipt['status']!='complete' or receipt['decision']!='yes':
            # The detailed negative/abstention receipt stays durable in decisions/.
            raise ValueError('recovery_decision_blocked:'+packet['id']+':'+receipt['reason'])
    return dict(mode='compact',binding=digest(value),stage=stage,decisions=receipts,
                manual_cases=[c['id'] for c in value['cases'] if c['applicability']['kind']=='manual'])


def validate_compact(report,value,stage,checks):
    adapter=load('recovery-decisions');decision=adapter.engine
    if report.get('binding')!=digest(value) or report.get('stage')!=stage:raise ValueError('recovery_stale_approval')
    packets=adapter.packets(value,checks,stage)
    if len(report.get('decisions',[]))!=len(packets):raise ValueError('recovery_incomplete_decisions')
    for packet,receipt in zip(packets,report['decisions']):
        decision.validate_receipt(receipt,packet,value['decision_readiness']['settings'],digest(value),p.root(value['worktree'],value['task'])/('recovery-'+digest(value))/'decisions')
        if receipt.get('packet_sha256')!=decision.digest(packet) or receipt.get('status')!='complete' or receipt.get('decision')!='yes':
            raise ValueError('recovery_unapproved_decision')
        if receipt.get('reported_model')!=value['decision_readiness']['settings']['model']:
            raise ValueError('recovery_decision_model_changed')
    if report.get('manual_cases')!=[c['id'] for c in value['cases'] if c['applicability']['kind']=='manual']:
        raise ValueError('recovery_manual_case_cannot_pass')
    return report


def validate_review(report, value, stage, checks, reviewer_id):
    if report.get('mode')=='compact':
        return validate_compact(report,value,stage,checks)
    if report.get('status') != 'SUCCESS': raise ValueError('recovery_review_failed')
    if report.get('artifacts', {}).get('provider') != value['reviewer_route']['provider'] or report['artifacts'].get('model') != value['reviewer_route']['model']:
        raise ValueError('recovery_reviewer_identity_mismatch')
    r = report.get('results', {})
    if set(r) != {'binding','stage','reviewer_id','decision','findings','dispositions','cases','ac_ids'}:
        raise ValueError('recovery_incomplete_review')
    if r['binding'] != digest(value) or r['stage'] != stage or r['reviewer_id'] != reviewer_id:
        raise ValueError('recovery_stale_approval')
    if r['decision'] != 'approve' or r['findings']:
        raise ValueError('recovery_unresolved_findings')
    if sorted(r['ac_ids']) != sorted(value['ac_ids']): raise ValueError('recovery_ac_coverage_missing')
    ids = [f['id'] for f in value['findings']]
    if sorted(d.get('id','') for d in r['dispositions']) != sorted(ids):
        raise ValueError('recovery_finding_disposition_missing')
    for d in r['dispositions']:
        if set(d) != {'id','resolution','reason'} or d['resolution'] not in ('resolved','superseded') or not d['reason'].strip():
            raise ValueError('recovery_unresolved_findings')
    if sorted(c.get('id','') for c in r['cases']) != sorted(c['id'] for c in value['cases']):
        raise ValueError('recovery_case_coverage_missing')
    passed = {c['id']:c['output_sha256'] for c in checks['checks'] if c['exit_code']==0}
    for c in r['cases']:
        manual = next(item for item in value['cases'] if item['id']==c['id'])['applicability']['kind']=='manual'
        if manual:
            if c.get('status')!='pending_manual_acceptance' or c.get('checks') or not c.get('reason'): raise ValueError('recovery_manual_case_cannot_pass')
            continue
        if set(c) != {'id','status','reason','checks'} or c['status'] != 'verified' or not c['reason'].strip() or not c['checks']:
            raise ValueError('recovery_case_evidence_missing')
        if any(set(ref) != {'id','sha256'} or passed.get(ref['id']) != ref['sha256'] for ref in c['checks']):
            raise ValueError('recovery_unverified_test_reference')
    return report


@contextmanager
def controller_lock(project, task):
    directory = p.root(project, task)
    if not directory.is_dir(): raise ValueError('recovery_requires_existing_controller')
    fd = os.open(directory / 'controller.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield directory


@contextmanager
def action_lock(project, task):
    console=load('console-actions'); path=console.directory(project)/(task+'.lock')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock, console.continuation_runtime_lock(project,'continue'):
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def validate_adopted(project, task, state, record):
    binding=record['recovery_binding']
    session=state['recovery_sessions'][binding]
    current_binding(project,task,binding)
    for stage,step in session['steps'].items():
        if step['status']=='pass' and p.sha(step['receipt'])!=step['sha256']:
            raise ValueError('recovery_receipt_changed')
    for stage in GATES:
        step=session['steps'].get(stage)
        if step and step['status']=='pass':
            validate_review(p.read(step['receipt']),session['evidence'],stage,p.read(session['steps']['verify']['receipt']),step['reviewer_id'])
    adoption=session['steps']['adoption']
    if adoption['status']!='pass': raise ValueError('recovery_approval_missing')
    checks=p.read(session['steps']['verify']['receipt'])
    validate_review(p.read(adoption['receipt']),session['evidence'],'adoption',checks,adoption['reviewer_id'])


def current_binding(project, task, expected):
    value, _ = evidence(project, task)
    if digest(value) != expected: raise ValueError('recovery_inputs_changed; reassess before authorization')
    return value


def admissible(project, task, state):
    current = load('console-actions').state(project, task)
    budget = load('ticket-budget').snapshot(project, task)
    if current['running'] or (budget or {}).get('unfinished') or any(a.get('status')=='running' for a in state['attempts']):
        raise ValueError('recovery_active_or_unfinished_work')
    if state.get('status') in ('complete', 'pending_manual_acceptance'):
        raise ValueError('recovery_manual_acceptance_or_complete')
    if current.get('review') and not current['review']['approved']:
        raise ValueError('recovery_spec_approval_required')


def controller_revision(state):
    return digest({k:v for k,v in state.items() if k!='recovery_sessions'})


def summary(session):
    return dict(status=session['status'], sha256=session['binding'], next_action=session['next_action'],
                allowance=session['allowance'], steps=session['steps'], decision_calls=session.get('decision_calls',{}),
                reason=session.get('reason',''), message='Recovery ' + session['status'] + '; original budgets and failed evidence retained.' + (' '+session['reason'] if session.get('reason') else ''))


def operate(project, task, operation='assess', expected='', operator='', runner=None, verifier=None):
    if operation == 'assess': return assessment(project, task)
    if operation not in ('authorize','resume'): raise ValueError('invalid_recovery_operation')
    if not re.fullmatch(r'[0-9a-f]{64}', expected): raise ValueError('recovery_assessment_required')
    compact = runner is None
    verifier = verifier or verify_checks
    with action_lock(project, task), controller_lock(project, task) as directory:
        target, state, _ = target_state(project, task)
        sessions = state.setdefault('recovery_sessions', {})
        session = sessions.get(expected)
        if session and session.get('controller_revision')!=controller_revision(state):
            raise ValueError('recovery_controller_changed')
        value = current_binding(project, task, expected)
        if compact and value['decision_readiness']['status']!='ready':
            raise ValueError('recovery_decision_preflight:'+value['decision_readiness']['reason'])
        # Duplicate authorization returns the durable outcome; it cannot mint time or execute twice.
        if session and operation == 'authorize': return summary(session)
        admissible(project, task, state)
        if session is None:
            if operation != 'authorize': raise ValueError('recovery_authorization_missing')
            if not operator.strip() or len(operator)>200: raise ValueError('recovery_operator_identity_required')
            if len(sessions)>=3: raise ValueError('recovery_session_limit_exhausted')
            if any(s['status']=='running' for s in sessions.values()): raise ValueError('recovery_already_running')
            now = time.time()
            session = dict(binding=expected, operator=operator, authorized_at=now, evidence=value,
                allowance=dict(value['limits'], started_at=now, deadline_at=now+value['limits']['wall_seconds'], active_used=0, calls_used=0),
                decision_mode='compact' if compact else 'legacy_fixture',
                steps={}, status='running', next_action='verify')
            sessions[expected] = session
            state.setdefault('recovery_origin', copy.deepcopy({k:v for k,v in state.items() if k not in ('recovery_sessions','recovery_origin')}))
            session['controller_revision']=controller_revision(state)
            p.recovery.atomic(directory / 'state.json', state)
        elif session['status'] in ('blocked','pending_manual_acceptance'):
            return summary(session)
        if compact != (session.get('decision_mode')=='compact'):
            raise ValueError('recovery_operation_mode_changed')
        session_dir = directory / ('recovery-' + expected)
        session_dir.mkdir(mode=0o700, exist_ok=True)
        def save():
            session['controller_revision']=controller_revision(state)
            p.recovery.atomic(directory / 'state.json', state)
        try:
            for stage in ('verify',) + GATES:
                old = session['steps'].get(stage)
                if old:
                    if old['status'] != 'pass': raise ValueError('recovery_unfinished_step:' + stage)
                    if old['finished_at']>session['allowance']['deadline_at'] or session['allowance']['active_used']>session['allowance']['active_seconds']:
                        raise ValueError('recovery_allowance_exhausted')
                    if p.sha(old['receipt']) != old['sha256']: raise ValueError('recovery_receipt_changed')
                    if stage!='verify' and not old.get('adopted'):
                        validate_review(p.read(old['receipt']),value,stage,p.read(session_dir/'verify.json'),old['reviewer_id'])
                        adopt(state,session,stage,directory);old['adopted']=True;save()
                    continue
                value = current_binding(project, task, expected)
                budget = session['allowance']
                remaining = min(budget['deadline_at']-time.time(), budget['active_seconds']-budget['active_used'])
                if remaining <= 0 or (stage!='verify' and not compact and budget['calls_used']>=budget['provider_calls']):
                    raise ValueError('recovery_allowance_exhausted')
                if stage != 'verify' and not compact: budget['calls_used'] += 1
                reviewer_id = 'recovery-review-' + uuid.uuid4().hex
                output = session_dir / (stage + '.json')
                step = dict(status='pending', started_at=time.time(), receipt=str(output),
                            reviewer_id=reviewer_id if stage!='verify' else None, route=value['reviewer_route'] if stage!='verify' else None)
                session['steps'][stage] = step; session['next_action']=stage; save()
                try:
                    if stage == 'verify':
                        report = verifier(value, timeout=remaining)
                        p.recovery.atomic(output, report)
                        if report.get('binding')!=expected or report.get('status')!='pass' or len(report.get('checks',[]))!=len(value['checks']):
                            raise ValueError('recovery_test_failure')
                        architecture = load('architecture').check(target, task, value['architecture']) if value['architecture'] else dict(status='pass')
                        if architecture['status']!='pass': raise ValueError('recovery_architecture_failure')
                    else:
                        checks=p.read(session_dir/'verify.json')
                        report=(compact_verdict(value,stage,checks,session,session_dir,save,step) if compact else runner(value,stage,checks,reviewer_id,output,min(120,remaining)))
                        if not output.exists(): p.recovery.atomic(output,report)
                        validate_review(report,value,stage,checks,reviewer_id)
                    current_binding(project,task,expected)
                    step.update(status='pass',sha256=p.sha(output),finished_at=time.time())
                except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:
                    step.update(status='fail',reason=str(error),finished_at=time.time())
                    if output.exists(): step['sha256']=p.sha(output)
                    raise
                finally:
                    budget['active_used'] += time.time()-step['started_at']
                    save()
                if budget['active_used']>budget['active_seconds'] or time.time()>budget['deadline_at']:
                    raise ValueError('recovery_allowance_exhausted')
                if stage!='verify':
                    adopt(state,session,stage,directory)
                    step['adopted']=True
                    save()  # one atomic controller transition with its evidence and next action
            session.update(status='pending_manual_acceptance',next_action='operator_verify_manual_acceptance')
            state.update(status='pending_manual_acceptance',next_action='operator_verify_manual_acceptance',
                         final_evidence=dict(outcome='pending',reason='manual_acceptance_pending',recovery_binding=expected))
            save()
        except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:
            session.update(status='blocked',next_action='inspect_recovery_evidence',reason=str(error))
            state.update(status='blocked',next_action='inspect_recovery_evidence')
            save()
        return summary(session)


def adopt(state, session, stage, directory):
    value = session['evidence']; target=Path(value['worktree']); task=value['task']
    state['plan']=value['plan']; state['architecture']=value['architecture']
    if stage=='adoption':
        for name in ('review','drift','qa'):
            old=state['completed'].pop(name,None)
            if old: state['history'].append(dict(stage=name,record=old,reason='recovery_dependency_revalidation_required'))
    adopted = ('product','adversarial','implement') if stage=='adoption' else (stage,)
    checks=p.read(directory/('recovery-'+session['binding'])/'verify.json')
    for name in adopted:
        old=state['completed'].get(name)
        if old: state['history'].append(dict(stage=name,record=old,reason='revalidated_by_independent_recovery'))
        record=dict(version=1,task=task,stage=name,status='pass',findings=[],
                    checks=[dict(command=' '.join(c['argv']),exit_code=c['exit_code']) for c in checks['checks']],
                    evidence=[dict(path=f,sha256=value['workspace']['files'][f]) for f in
                              value['source_files']+['docs/'+task+'/SPEC.md','docs/'+task+'/behavior-scenarios.json']])
        receipt=directory/('recovery-'+session['binding'])/(name+'-adopted.json')
        p.recovery.atomic(receipt,record); p.validate_receipt(receipt,task,name,target)
        state['completed'][name]=dict(receipt=str(receipt),sha256=p.sha(receipt),
            input_sha256=p.inputs(target,task,name,state),recovery_binding=session['binding'])
    state['history'].append(dict(reason='independently_verified_recovery',stage=stage,
                                binding=session['binding'],author=value['author'],review=session['steps'][stage]))
    session['next_action']=next((s for s in p.STAGES if s not in state['completed']),'operator_verify_manual_acceptance')
    state.update(next_action=session['next_action'],status='recovering')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['assess','authorize','resume']);parser.add_argument('ref')
    parser.add_argument('--project',default=os.getcwd());parser.add_argument('--expected',default='')
    parser.add_argument('--operator',default='');parser.add_argument('--verify',action='store_true')
    parser.add_argument('--output')
    args=parser.parse_args()
    try:
        task=args.ref.removeprefix('jira:')
        if args.verify and args.operation!='assess':raise ValueError('--verify requires assess')
        result=assessment(args.project,task,True) if args.verify else operate(args.project,task,args.operation,args.expected,args.operator)
        content=json.dumps(result,indent=2)
        if args.output:
            with open(args.output,'x') as stream:stream.write(content+'\n')
        print(content)
        return 1 if result['status']=='blocked' else 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='blocked',reason=str(error))));return 1

if __name__=='__main__':raise SystemExit(main())
