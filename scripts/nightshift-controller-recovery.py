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
import hashlib
import json
import math
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
# No fixed number of recovery sessions: each one requires the operator's explicit
# authorization of its binding and limits, and later sessions reuse identical
# answers, so a count limit adds no protection. Every session is retained.
# Operator decision on #65: when the independent reviewer abstains or disagrees,
# the question goes to the operator instead of ending the session.
OPERATOR_REASONS = ('decision_abstained', 'decision_reviewer_contradiction', 'decision_independent_evidence_incomplete')
# Files that shape what an independent decision reviewer sees and returns.
# An earlier session's answer is reusable only when all are byte-identical.
REVIEWER_ASSETS = ('agents/nightshift-decision-reviewer.md', 'contracts/nightshift-decision-reviewer.schema.json',
                   'scripts/nightshift-decision-render.py', 'scripts/nightshift-agent.sh', 'scripts/nightshift-contract.jq')
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


def finding_category(finding, attempts):
    """Expose only an unambiguous retained controller classification; never infer one."""
    if not isinstance(finding,dict) or not isinstance(finding.get('target'),str) or not isinstance(finding.get('problem'),str):
        return 'unknown'
    matches=[attempt for attempt in attempts if isinstance(attempt,dict)
             and attempt.get('status')=='fail' and attempt.get('receipt')==finding['target']
             and attempt.get('reason')==finding['problem']]
    if len(matches)!=1 or matches[0].get('category') not in ('schema','transport','substantive'):
        return 'unknown'
    return matches[0]['category']


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
    plan_document = report if decision_plan.exists() else None
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
    generated = generated_artifacts(target, plan_document)
    # Preserve every controller and classification finding with a stable identity.
    findings = []
    origin=state.get('recovery_origin',state)
    for row in origin.get('findings', []):
        findings.append(dict(id=digest(row), finding=row, source='controller',
                             failure_category=finding_category(row,origin.get('attempts',[]))))
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
              'scripts/nightshift-provider-policy.py', 'scripts/nightshift-project-context.py', 'scripts/nightshift-checkout-identity.py',
              'scripts/nightshift-routing-path.py', 'scripts/nightshift-architecture.py']
    assets += ['scripts/nightshift-manual-acceptance.py','scripts/nightshift-recovery-acceptance.py']
    assets += ['scripts/nightshift-decision-engine.py','scripts/nightshift-recovery-decisions.py','scripts/nightshift-decision-render.py',
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
    if generated is not None:
        if any(value['workspace']['files'].get(g['path']) is None for g in generated):raise ValueError('recovery_generated_unbound')
        value['generated']=generated
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
        if result['verification']['status']=='pass' and value['decision_readiness']['status']=='ready':
            adapter=load('recovery-decisions')
            result['review_framing']=[]
            for gate in GATES:
                for packet in adapter.packets(value,result['verification'],gate):
                    framing=adapter.review_framing(value,packet)
                    result['review_framing'].append(dict(stage=gate,packet_id=packet['id'],**{k:v for k,v in framing.items() if k not in ('role','prompt','schema')}))
                    if value['decision_readiness'].get('semantic_mode','jev')=='independent':
                        adapter.engine.independent_envelope(packet,'decision-review-'+'0'*32)
                    else:
                        adapter.engine.request_body(packet,value['decision_readiness']['settings'])
            result['run_estimate']=estimate_run(value,state,result['verification'])
    return result


def estimate_run(value, state, verification):
    """A measured run proposal for the operator; nothing is spent and nothing is applied.

    Counts come from the actual packets; durations only from calls this ticket has
    already made. Without observations a duration is reported as unknown.
    """
    adapter=load('recovery-decisions');engine=adapter.engine
    mode=value['decision_readiness'].get('semantic_mode','jev');settings=value['decision_readiness']['settings']
    unique={};evaluations=0
    for gate in GATES:
        for packet in adapter.packets(value,verification,gate):
            evaluations+=1;unique.setdefault(engine.digest(packet),packet)
    questions=list(unique.values())
    # Answers an earlier authorized session already settled are reused at no call cost.
    root=p.root(value['worktree'],value['task']);prior=reusable_sessions(value,dict(binding=digest(value)),root)
    def reusable(packet):
        for authority in prior:
            origin=root/('recovery-'+authority)/'decisions'
            if mode=='independent':
                key=engine.digest(dict(authority=authority,packet=packet,settings=engine.independent_identity(settings),rubric=engine.RUBRIC,semantic_mode='independent'))
                check=lambda r:engine.validate_independent_receipt(r,packet,settings,authority,origin)
            else:
                identity={k:settings[k] for k in ('endpoint','model','timeout_seconds','max_bytes','allow_loopback','enabled','key_env')}
                key=engine.digest(dict(authority=authority,packet=packet,policy=engine.default_policy(packet),settings=identity,rubric=engine.RUBRIC))
                check=lambda r:engine.validate_receipt(r,packet,settings,authority,origin)
            try:
                record=json.loads((origin/(key+'.json')).read_text())
                if record.get('status')=='complete' and record.get('decision') in ('yes','no') and record.get('reused_from') is None:
                    check(record);return True
            except (OSError,ValueError,KeyError,TypeError):continue
        return False
    reused=[packet for packet in questions if reusable(packet)]
    fresh=[packet for packet in questions if packet not in reused]
    if mode=='independent':
        tokens=sum(adapter.review_framing(value,packet)['estimated_tokens'] for packet in fresh)
        planned={};kinds=('independent','reask')
    else:
        tokens=sum(engine.estimated_tokens(len(engine.request_body(packet,settings)),engine.SEED_BYTES_PER_TOKEN) for packet in fresh)
        # Escalations the policy will make even when Jev is confident (deterministic).
        planned={}
        for packet in fresh:
            kind=engine.escalation_mode('yes',packet,engine.default_policy(packet))
            if kind:planned[kind]=planned.get(kind,0)+1
        kinds=('jev','exception','shadow')
    durations={}
    for session in state.get('recovery_sessions',{}).values():
        for call in (session.get('decision_calls') or {}).values():
            if isinstance(call,dict) and call.get('kind') in kinds and call.get('status')=='complete' and all(type(call.get(k)) in (int,float) for k in ('started_at','finished_at')):
                durations.setdefault(call['kind'],[]).append(call['finished_at']-call['started_at'])
    observed={kind:dict(samples=len(v),median=round(sorted(v)[len(v)//2],3),maximum=round(max(v),3)) for kind,v in sorted(durations.items())}
    expected=len(fresh)+sum(planned.values());maximum=2*len(fresh)
    slowest=max((row['maximum'] for row in observed.values()),default=None)
    seconds=None if slowest is None else min(adapter.MAX_ALLOWANCE_SECONDS,math.ceil(slowest*maximum))
    return dict(mode=mode,unique_questions=len(questions),gate_evaluations=evaluations,cache_reuses=evaluations-len(questions),
                provider_calls=dict(expected=expected,maximum=maximum,planned_escalations=planned,reusable_answers=len(reused)),
                estimated_input_tokens=tokens,token_budget=dict(request=engine.REQUEST_TOKEN_BUDGET,state_question=engine.STATE_QUESTION_TOKEN_BUDGET),
                observed_call_seconds=observed,
                proposed_limits=dict(provider_calls=min(adapter.MAX_PROVIDER_CALLS,maximum),wall_seconds=seconds,active_seconds=seconds),
                basis='Counts from the actual packets, excluding answers reusable from earlier authorized sessions; maximum allows one escalation or re-ask per fresh question; seconds = slowest observed call on this ticket x maximum calls (unknown without observations). A proposal for operator approval; nothing is applied.')


def clean_environment():
    # Tests execute copied source; never inherit target paths, secrets or a parent budget.
    keep = ('PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'SYSTEMROOT')
    return {key:os.environ[key] for key in keep if key in os.environ}


def bounded(argv, cwd, env, timeout, output, cancellation=None, ownership=None):
    cancellation_paths=[] if cancellation is None else cancellation if isinstance(cancellation,list) else [cancellation]
    if any(path.exists() for path in cancellation_paths):
        if ownership is not None:p.recovery.atomic(ownership,dict(status='not_started',reason='cancelled_before_spawn'))
        raise ValueError('operation_cancelled:before_spawn')
    with output.open('wb') as log:
        supervised=[sys.executable,str(HERE/'nightshift-recovery-exec.py'),str(os.getpid()),str(timeout),str(output),*argv]
        child = subprocess.Popen(supervised, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        started = time.monotonic()
        cancelled=False
        try:
            if ownership is not None:p.recovery.atomic(ownership,dict(status='running',pid=child.pid,controller=os.getpid(),started=time.time(),argv_sha256=hashlib.sha256(json.dumps(argv).encode()).hexdigest()))
            while child.poll() is None:
                if any(path.exists() for path in cancellation_paths):
                    cancelled=True
                    raise ValueError('operation_cancelled:owned_execution_stopping')
                if time.monotonic() - started >= timeout or output.stat().st_size > 2_000_000:
                    raise ValueError('recovery_execution_bound_exceeded')
                time.sleep(.05)
            return child.returncode
        finally:
            # The supervisor owns descendant cleanup; signal only our live child.
            if child.poll() is None:
                try: os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL); child.wait()
            if ownership is not None:p.recovery.atomic(ownership,dict(status='stopped',pid=child.pid,controller=os.getpid(),cancelled=cancelled,exit_code=child.returncode,local_seconds=time.monotonic()-started))


def generated_artifacts(target, plan_document):
    """Version 2 plans declare files that a generator reproduces from committed source.

    Nightshift proves each one itself during verification: the file is removed
    from an isolated copy, the generator must recreate it byte for byte, and no
    tracked file may change. Proven artifacts are never sent to a reviewer.
    """
    if not isinstance(plan_document, dict) or plan_document.get('version') != 2:
        return None
    rows = plan_document.get('generated', [])
    if not isinstance(rows, list) or len(rows) > 20:
        raise ValueError('recovery_generated_invalid')
    out = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'path', 'argv'} or not isinstance(row['argv'], list) or len(row['argv']) != 2 or row['argv'][0] not in ('bash', 'python3'):
            raise ValueError('recovery_generated_invalid')
        if row['path'] == row['argv'][1] or row['path'] in {r['path'] for r in out}:
            raise ValueError('recovery_generated_invalid')
        safe_file(target, row['path']); script = safe_file(target, row['argv'][1])
        out.append(dict(path=row['path'], argv=row['argv'], sha256=p.sha(script)))
    return out


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
        proofs = []
        for artifact in value.get('generated', []):
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0: raise ValueError('recovery_allowance_exhausted')
            produced = copied / artifact['path']; produced.unlink()
            output = base / 'generate.log'
            code = bounded(artifact['argv'], copied, env, min(120, remaining), output)
            tracked = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=copied, env=env, capture_output=True, text=True, timeout=30)
            reproduced = (code == 0 and produced.is_file() and not produced.is_symlink()
                          and p.sha(produced) == value['workspace']['files'][artifact['path']] and tracked.returncode == 0 and tracked.stdout == '')
            proofs.append(dict(path=artifact['path'], argv=artifact['argv'], exit_code=code, reproduced=reproduced,
                               output=output.read_text(errors='replace'), output_sha256=p.sha(output)))
            if not reproduced: break
        for check in value['checks']:
            if any(not proof['reproduced'] for proof in proofs): break
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0: raise ValueError('recovery_allowance_exhausted')
            output = base / 'check.log'
            code = bounded(check['argv'], copied, env, min(120, remaining), output)
            results.append(dict(id=check['id'], argv=check['argv'], exit_code=code,
                                output=output.read_text(errors='replace'), output_sha256=p.sha(output)))
            if sum(len(r['output'].encode()) for r in results)>500_000: raise ValueError('recovery_test_output_limit')
            if code: break
    passed = len(results)==len(value['checks']) and all(r['exit_code']==0 for r in results) and len(proofs)==len(value.get('generated', [])) and all(r['reproduced'] for r in proofs)
    report = dict(binding=digest(value), status='pass' if passed else 'fail', checks=results)
    if 'generated' in value: report['generated'] = proofs
    return report


def compact_review(value,packet,mode,output,timeout,reviewer_id=None,missing_roles=None):
    """One isolated reviewer sees only the obligation; primary answer is withheld."""
    policies=(value['plan']['policy'],os.environ.get('NIGHTSHIFT_PROVIDER_POLICY','standard'))
    if any(policy not in ('standard','claude-only') for policy in policies):
        raise ValueError('decision_reviewer_policy_invalid')
    effective_policy='claude-only' if 'claude-only' in policies else 'standard'
    role_child=os.environ.get('NIGHTSHIFT_ROLE_CHILD')
    decision=load('decision-engine');reviewer_id=reviewer_id or 'decision-review-'+uuid.uuid4().hex
    envelope=(decision.independent_envelope(packet,reviewer_id,missing_roles) if mode=='independent' else dict(packet=packet,packet_sha256=decision.digest(packet),reviewer_id=reviewer_id,mode=mode))
    request=output.with_suffix('.input.json')
    if mode=='independent':decision.atomic(request,envelope)
    else:p.recovery.atomic(request,envelope)
    routing=p.read(value['plan']['routing_path'])
    routing['roles']['nightshift-decision-reviewer']=dict(prompt='agents/nightshift-decision-reviewer.md',sandbox='read-only',gears={'1':value['reviewer_route']})
    route_file=output.with_suffix('.routing.json');p.recovery.atomic(route_file,routing)
    env=dict(os.environ)
    for key in list(env):
        if key.startswith('NIGHTSHIFT_') or key in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','OPENAI_API_KEY'):
            env.pop(key)
    env.update(NIGHTSHIFT_ROUTING_FILE=str(route_file),NIGHTSHIFT_UPDATE_GUARD='1',
               NIGHTSHIFT_HOME=str(HERE.parent),NIGHTSHIFT_PROVIDER_POLICY=effective_policy)
    if role_child is not None:env['NIGHTSHIFT_ROLE_CHILD']=role_child
    with tempfile.TemporaryDirectory(prefix='nightshift-decision-review-') as tmp:
        code=bounded(['bash',str(HERE/'nightshift-agent.sh'),'nightshift-decision-reviewer','--gear','1',
                      '--in',str(request),'--out',str(output),'--auth','subscription'],tmp,env,timeout,output.with_suffix('.log'))
    if code:raise ValueError('decision_reviewer_exit_'+str(code))
    report=p.read(output)
    if report.get('status')!='SUCCESS' or any(report.get('artifacts',{}).get(k)!=value['reviewer_route'][k] for k in ('provider','model')):
        raise ValueError('decision_reviewer_identity_mismatch')
    result=report['results']
    if result.get('reviewer_id')!=reviewer_id:raise ValueError('decision_reviewer_identity_mismatch')
    # The original dispatcher report remains on disk; only its citation view changes.
    return decision.review_from_grounding(result,packet)


def reusable_sessions(value,session,root):
    """Earlier authorized sessions of this ticket with identical reviewer framing."""
    try:state=p.read(root/'state.json')
    except (OSError,ValueError):return []
    return [binding for binding,other in sorted(state.get('recovery_sessions',{}).items())
            if binding!=session['binding'] and isinstance(other,dict)
            and all(other.get('evidence',{}).get('assets',{}).get(name) is not None
                    and other['evidence']['assets'].get(name)==value['assets'].get(name) for name in REVIEWER_ASSETS)]


def recover_interruption(session, session_dir):
    """Resume a session whose controller process died mid-stage.

    Called only from `resume` while this process holds the controller lock, so no
    other controller is alive. The interrupted step and any unfinished decision
    record are retained (never rewritten), calls whose outcome was never recorded
    stay counted against the allowance and are marked interrupted, and the stage
    is asked again. Completed answers are reused from the cache.
    """
    recovered=dict(recovered_at=time.time(),steps=[],decisions=[])
    for stage in list(session['steps']):
        if session['steps'][stage].get('status')=='pending':
            recovered['steps'].append(dict(stage=stage,step=session['steps'].pop(stage)))
    decisions=session_dir/'decisions'
    for path in sorted(decisions.glob('*.json')) if decisions.is_dir() else []:
        if path.name.count('.')!=1 or path.is_symlink():continue
        try:record=json.loads(path.read_text())
        except (OSError,ValueError):continue
        if not isinstance(record,dict) or record.get('status')!='pending':continue
        key=path.stem;n=1+len(list(decisions.glob(key+'.interrupted-*.json')))
        for artifact in sorted(decisions.glob(key+'.*.json')):
            suffix=artifact.name[len(key)+1:-len('.json')]
            if suffix=='packet' or suffix.startswith('interrupted-'):continue
            artifact.rename(decisions/(key+'.interrupted-'+str(n)+'.'+suffix+'.json'))
        path.rename(decisions/(key+'.interrupted-'+str(n)+'.json'))
        calls=session.setdefault('decision_calls',{})
        # Every call of the retired record is re-keyed so a fresh attempt can reserve;
        # all stay counted. Calls whose outcome was never recorded become interrupted.
        for call_id in [c for c in calls if c==key or c.startswith(key+':') or c.startswith(key+'-')]:
            if ':interrupted-' in call_id:continue
            row=calls.pop(call_id)
            if row.get('status') in ('pending','error'):row.update(status='interrupted')
            calls[call_id+':interrupted-'+str(n)]=row
        recovered['decisions'].append(dict(key=key,retained=key+'.interrupted-'+str(n)+'.json'))
    if recovered['steps'] or recovered['decisions']:
        session.setdefault('interruptions',[]).append(recovered)
    return recovered


def operator_record(directory, packet_sha256):
    # Keyed by packet, not gate: an identical question asked by two gates (e.g.
    # adoption and review) shares one decision, like the decision cache itself.
    return directory/'operator'/(packet_sha256+'.json')


def valid_operator_decision(record, binding, packet, receipt):
    """An operator answer is bound to this session, this exact packet and the blocked receipt."""
    return (isinstance(record,dict) and set(record)=={'binding','packet_id','packet_sha256','receipt_sha256','decision','reason','operator','decided_at'}
            and record['binding']==binding and record['packet_id']==packet['id'] and record['packet_sha256']==load('decision-engine').digest(packet)
            and record['receipt_sha256']==receipt.get('receipt_sha256') and record['decision'] in ('yes','no')
            and isinstance(record['reason'],str) and record['reason'].strip() and isinstance(record['operator'],str) and record['operator'].strip())


def operator_decide(project, task, expected, operator, packet_sha256, decision_value, reason):
    if not re.fullmatch(r'[0-9a-f]{64}', expected or ''): raise ValueError('recovery_assessment_required')
    if not operator.strip() or len(operator)>200: raise ValueError('recovery_operator_identity_required')
    if decision_value not in ('yes','no') or not reason.strip() or len(reason)>2000: raise ValueError('recovery_operator_decision_invalid')
    with action_lock(project, task), controller_lock(project, task) as directory:
        target, state, _ = target_state(project, task)
        session = state.get('recovery_sessions',{}).get(expected)
        if not session or session.get('status')!='awaiting_operator': raise ValueError('recovery_operator_not_awaited')
        waiting = session.get('awaiting') or {}
        if waiting.get('packet_sha256')!=packet_sha256: raise ValueError('recovery_operator_packet_mismatch')
        record = dict(binding=expected, packet_id=waiting['packet_id'], packet_sha256=packet_sha256, receipt_sha256=waiting['receipt_sha256'],
                      decision=decision_value, reason=reason.strip(), operator=operator.strip(), decided_at=time.time())
        path = operator_record(directory/('recovery-'+expected), packet_sha256)
        if path.exists(): raise ValueError('recovery_operator_already_decided')
        path.parent.mkdir(mode=0o700, exist_ok=True); p.recovery.atomic(path, record)
        session.setdefault('operator_decisions',[]).append(dict(packet_id=record['packet_id'],packet_sha256=packet_sha256,decision=decision_value,sha256=p.sha(path)))
        session['next_action']='resume'; p.recovery.atomic(directory / 'state.json', state)
        return summary(session)


def compact_verdict(value,stage,checks,session,directory,save,step,transport=None,escalator=None):
    adapter=load('recovery-decisions');decision=adapter.engine
    packets=adapter.packets(value,checks,stage)
    settings=value['decision_readiness']['settings'];budget=session['allowance']
    def remaining():
        return min(budget['deadline_at']-time.time(),budget['active_seconds']-budget['active_used']-(time.time()-step['started_at']))
    def reserve(kind,request_id,request_bytes):
        if kind in ('exception','shadow'):
            envelope=dict(packet=packet,packet_sha256=decision.digest(packet),reviewer_id='decision-review-'+'0'*32,mode=kind)
            request_bytes=len(json.dumps(envelope,sort_keys=True).encode())
        if remaining()<=0 or budget['calls_used']>=budget['provider_calls']:raise ValueError('recovery_allowance_exhausted')
        calls=session.setdefault('decision_calls',{})
        if request_id in calls:raise ValueError('decision_duplicate_reservation')
        budget['calls_used']+=1
        calls[request_id]=dict(kind=kind,request_bytes=request_bytes,status='pending',started_at=time.time())
        if kind in ('independent','reask','exception','shadow'):calls[request_id]['request_bytes_scope']='exact serialized reviewer input envelope; excludes CLI role/schema framing'
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
    semantic_mode=value['decision_readiness'].get('semantic_mode','jev')
    if semantic_mode=='independent':
        def independent_review(packet,reviewer_id,missing_roles=None):
            # A re-ask writes beside, never over, the retained first report.
            output=directory/('decision-'+decision.digest(packet)+('.reask' if missing_roles else '')+'.review.json')
            extra=dict(missing_roles=missing_roles) if missing_roles else {}
            return (escalator or compact_review)(value,packet,'independent',output,max(.001,min(120,remaining())),reviewer_id=reviewer_id,**extra)
        evaluator=decision.IndependentEngine(directory/'decisions',session['binding'],settings,reserve,finish,independent_review,
                                             prior=reusable_sessions(value,session,directory.parent))
    else:
        evaluator=decision.Engine(directory/'decisions',session['binding'],settings,reserve,finish,
                                  transport=invoke_jev,escalate=escalate,prior=reusable_sessions(value,session,directory.parent))
    receipts=[]
    for packet in packets:
        current_binding(value['worktree'],value['task'],session['binding'])
        adapter.review_framing(value,packet)
        receipt=evaluator.decide(packet)
        if receipt['status']!='complete' and receipt['reason'] in OPERATOR_REASONS:
            path=operator_record(directory,decision.digest(packet))
            if not path.exists():
                session['awaiting']=dict(stage=stage,packet_id=packet['id'],packet_sha256=decision.digest(packet),
                                         receipt_sha256=receipt.get('receipt_sha256'),reason=receipt['reason'])
                save()
                raise ValueError('recovery_decision_operator_required:'+packet['id']+':'+receipt['reason'])
            record=p.read(path)
            if not valid_operator_decision(record,session['binding'],packet,receipt):raise ValueError('recovery_operator_decision_invalid')
            session.pop('awaiting',None)
            if record['decision']!='yes':raise ValueError('recovery_decision_blocked:'+packet['id']+':operator_rejected')
            receipt=dict(receipt,operator=dict(sha256=p.sha(path)))
        receipts.append(receipt)
        if receipt.get('operator') is None and (receipt['status']!='complete' or receipt['decision']!='yes'):
            # The detailed negative/abstention receipt stays durable in decisions/.
            raise ValueError('recovery_decision_blocked:'+packet['id']+':'+receipt['reason'])
    return dict(mode='compact',semantic_mode=semantic_mode,binding=digest(value),stage=stage,decisions=receipts,
                manual_cases=[c['id'] for c in value['cases'] if c['applicability']['kind']=='manual'])


def validate_compact(report,value,stage,checks):
    adapter=load('recovery-decisions');decision=adapter.engine
    if report.get('binding')!=digest(value) or report.get('stage')!=stage:raise ValueError('recovery_stale_approval')
    semantic_mode=value['decision_readiness'].get('semantic_mode','jev')
    if report.get('semantic_mode','jev')!=semantic_mode:raise ValueError('recovery_semantic_mode_changed')
    packets=adapter.packets(value,checks,stage)
    if len(report.get('decisions',[]))!=len(packets):raise ValueError('recovery_incomplete_decisions')
    session_dir=p.root(value['worktree'],value['task'])/('recovery-'+digest(value))
    for packet,receipt in zip(packets,report['decisions']):
        validator=decision.validate_independent_receipt if semantic_mode=='independent' else decision.validate_receipt
        operator=receipt.get('operator')
        stored={k:v for k,v in receipt.items() if k!='operator'}
        validator(stored,packet,value['decision_readiness']['settings'],digest(value),session_dir/'decisions')
        if operator is not None:
            path=operator_record(session_dir,decision.digest(packet))
            if stored['status']=='complete' or stored['reason'] not in OPERATOR_REASONS or not isinstance(operator,dict) or set(operator)!={'sha256'} or not path.is_file() or p.sha(path)!=operator['sha256']:
                raise ValueError('recovery_unapproved_decision')
            record=p.read(path)
            if not valid_operator_decision(record,digest(value),packet,stored) or record['decision']!='yes':raise ValueError('recovery_unapproved_decision')
            continue
        if receipt.get('packet_sha256')!=decision.digest(packet) or receipt.get('status')!='complete' or receipt.get('decision')!='yes':
            raise ValueError('recovery_unapproved_decision')
        if semantic_mode=='jev' and receipt.get('reported_model')!=value['decision_readiness']['settings']['model']:
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
    if state['recovery_sessions'][binding].get('status')=='complete':
        return load('recovery-acceptance').validate(self_module(),project,task,state,binding)
    session=state['recovery_sessions'][binding]
    current_binding(project,task,binding,session['evidence'])
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


def current_binding(project, task, expected, recorded=None):
    value, _ = evidence(project, task)
    if digest(value) != expected and recorded is not None:
        # After authorization the reviewer route (model, key variable) that produced the
        # receipts is part of the recorded evidence. It may come from the environment,
        # so a later process without it must not see the evidence as changed. Only the
        # route and its allowance are taken from the record, and only for the same plan.
        adapter=load('recovery-decisions')
        try: plan_sha=adapter.engine.digest(adapter.plan(value))
        except (OSError,ValueError,KeyError,TypeError): plan_sha=None
        prior=recorded.get('decision_readiness',{})
        if plan_sha and prior.get('plan_sha256')==plan_sha:
            value=dict(value,decision_readiness=prior,limits=recorded['limits'])
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
                reason=session.get('reason',''), awaiting=session.get('awaiting') if session['status']=='awaiting_operator' else None, message='Recovery ' + session['status'] + '; original budgets and failed evidence retained.' + (' '+session['reason'] if session.get('reason') else ''))


def self_module():
    from types import SimpleNamespace
    return SimpleNamespace(**globals())


def operate(project, task, operation='assess', expected='', operator='', runner=None, verifier=None, attestation=None):
    if operation == 'assess': return assessment(project, task)
    if operation == 'accept': return load('recovery-acceptance').accept(self_module(),project,task,expected,operator,attestation)
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
            # This process holds the controller lock, so a session still recorded as
            # running belongs to a controller that is no longer alive: close it, retained.
            for other in sessions.values():
                if other.get('status')=='running':
                    other.update(status='interrupted',next_action='superseded_after_interruption',
                                 reason='controller_process_ended',closed_at=time.time(),superseded_by=expected)
            now = time.time()
            session = dict(binding=expected, operator=operator, authorized_at=now, evidence=value,
                allowance=dict(value['limits'], started_at=now, deadline_at=now+value['limits']['wall_seconds'], active_used=0, calls_used=0),
                decision_mode='compact' if compact else 'legacy_fixture', semantic_mode=value['decision_readiness'].get('semantic_mode','jev'),
                steps={}, status='running', next_action='verify')
            sessions[expected] = session
            state.setdefault('recovery_origin', copy.deepcopy({k:v for k,v in state.items() if k not in ('recovery_sessions','recovery_origin')}))
            session['controller_revision']=controller_revision(state)
            p.recovery.atomic(directory / 'state.json', state)
        elif session['status'] in ('blocked','pending_manual_acceptance','interrupted') or (session['status']=='awaiting_operator' and operation!='resume'):
            return summary(session)
        if compact and session.get('semantic_mode','jev')!=value['decision_readiness'].get('semantic_mode','jev'):
            raise ValueError('recovery_semantic_mode_changed')
        if compact != (session.get('decision_mode')=='compact'):
            raise ValueError('recovery_operation_mode_changed')
        session_dir = directory / ('recovery-' + expected)
        session_dir.mkdir(mode=0o700, exist_ok=True)
        def save():
            session['controller_revision']=controller_revision(state)
            p.recovery.atomic(directory / 'state.json', state)
        try:
            # Decision-based sessions only; the legacy stage runner keeps never-relaunch.
            if operation=='resume' and session['status']=='running' and session.get('decision_mode')=='compact':
                # This process holds the controller lock, so the recorded run is not alive.
                recover_interruption(session,session_dir);save()
            if session.get('paused_at'):
                # Time waiting for the operator is not run time; the extension is recorded.
                pause=time.time()-session.pop('paused_at')
                session['allowance']['deadline_at']+=pause
                session['allowance'].setdefault('operator_pauses',[]).append(round(pause,3))
                session['status']='running'; save()
            for stage in ('verify',) + GATES:
                old = session['steps'].get(stage)
                if old and old['status']=='awaiting_operator':
                    session.setdefault('operator_waits',[]).append(dict(stage=stage,step=old)); session['steps'].pop(stage); old=None
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
                    waiting=str(error).startswith('recovery_decision_operator_required:')
                    step.update(status='awaiting_operator' if waiting else 'fail',reason=str(error),finished_at=time.time())
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
            if str(error).startswith('recovery_decision_operator_required:'):
                session.update(status='awaiting_operator',next_action='operator_decision',reason=str(error),paused_at=time.time())
                state.update(status='blocked',next_action='operator_decision')
            else:
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


def resolve_retained_ref(project, ref):
    """Resolve only recorded invocation identities; never query a ticket provider."""
    if not isinstance(ref, str) or not ref or any(c in ref for c in '\0\r\n'):
        raise ValueError('recovery_invalid_reference')
    console = load('console-actions')
    matches = set()
    for path in sorted(console.directory(project).glob('*.json')):
        try:
            record = console.read(path)
        except (OSError, ValueError):
            if path.stem == ref:
                raise ValueError('recovery_invalid_retained_invocation')
            continue
        if not isinstance(record, dict) or not isinstance(record.get('settings'), dict):
            continue
        if path.stem != ref and record['settings'].get('ref') != ref:
            continue
        if record.get('task') != path.stem:
            raise ValueError('recovery_retained_identity_changed')
        console.validate(path.stem, record['settings'])
        matches.add(path.stem)
    if not matches:
        raise ValueError('recovery_retained_reference_not_found')
    if len(matches) != 1:
        raise ValueError('recovery_retained_reference_ambiguous')
    return matches.pop()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['assess','authorize','resume','accept','operator-decide']);parser.add_argument('ref')
    parser.add_argument('--packet',help='operator-decide: the exact awaited packet sha256');parser.add_argument('--decision',choices=['yes','no'])
    parser.add_argument('--reason',default='')
    parser.add_argument('--project',default=os.getcwd());parser.add_argument('--expected',default='')
    parser.add_argument('--operator',default='');parser.add_argument('--verify',action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--attestation',help='JSON file containing the exact binding and required manual case observations')
    args=parser.parse_args()
    try:
        task=resolve_retained_ref(args.project,args.ref)
        if args.verify and args.operation!='assess':raise ValueError('--verify requires assess')
        attestation=None
        if args.attestation:
            if args.operation!='accept':raise ValueError('--attestation requires accept')
            with open(args.attestation,'rb') as stream:raw=stream.read(12001)
            if len(raw)>12000:raise ValueError('manual_acceptance_too_large')
            attestation=json.loads(raw)
        if args.operation=='operator-decide':
            result=operator_decide(args.project,task,args.expected,args.operator,args.packet or '',args.decision or '',args.reason)
        else:
            result=assessment(args.project,task,True) if args.verify else operate(args.project,task,args.operation,args.expected,args.operator,attestation=attestation)
        content=json.dumps(result,indent=2)
        if args.output:
            with open(args.output,'x') as stream:stream.write(content+'\n')
        print(content)
        return 1 if result['status']=='blocked' else 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='blocked',reason=str(error))));return 1

if __name__=='__main__':raise SystemExit(main())
