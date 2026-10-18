#!/usr/bin/env python3
"""Deterministic stage selection and evidence-gated factory continuation."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
STAGES = ('product', 'adversarial', 'implement', 'review', 'drift', 'qa')
REVIEW = ('adversarial', 'review', 'drift', 'qa')
UNSEALED = ('proof_state_unavailable', 'proof_unsealed')


def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/('nightshift-'+name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


recovery=load('recovery-state')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path=Path(path)
    if path.resolve()!=path.absolute() or path.stat().st_size>2000000:
        raise ValueError('unsafe_pipeline_record')
    value=json.loads(path.read_text())
    if not isinstance(value,dict):raise ValueError('pipeline_record_requires_object')
    return value


def root(project, task):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,150}',task):raise ValueError('invalid_task')
    common=subprocess.check_output(['git','-C',str(project),'rev-parse','--git-common-dir'],text=True).strip()
    return (Path(project)/common).resolve()/'nightshift/pipeline'/task


def snapshot(project, task):
    path=root(project,task)/'state.json'
    return read(path) if path.exists() else None


def view(project, task):
    state=snapshot(project,task)
    if state is None:return None
    try:
        target=Path(state['worktree'])
        for stage,row in state['completed'].items():
            if sha(row['receipt'])!=row['sha256'] or inputs(target,task,stage,state)!=row['input_sha256']:
                raise ValueError('stale_stage_evidence')
            validate_receipt(row['receipt'],task,stage,target)
            if row.get('recovery_binding'):load('controller-recovery').validate_adopted(project,task,state,row)
    except (OSError,ValueError,KeyError):
        state=dict(state,status='stale',next_action='revalidate_changed_evidence')
    # Enrich historical transport failures for display without rewriting receipts.
    for attempt in state.get('attempts', []):
        old = attempt.get('reason', '')
        match = re.fullmatch(r'worker_exit_(\d+)', old)
        if match and attempt.get('receipt'):
            detail = worker_failure(Path(attempt['receipt']), int(match[1]))
            if detail != old:
                attempt['reason'] = detail
                for finding in state.get('findings', []):
                    if finding.get('problem') == old and finding.get('target') == attempt['receipt']:
                        finding['problem'] = detail
    sessions=state.get('recovery_sessions',{})
    if sessions:
        latest=max(sessions.values(),key=lambda row:row['authorized_at'])
        state['recovery_status']={key:latest.get(key) for key in ('binding','status','next_action','reason','allowance','decision_calls','awaiting')}
        steps=latest.get('steps',{})
        if not isinstance(steps,dict):steps={}
        state['recovery_status']['steps']={stage:{key:row.get(key) for key in ('status','started_at','finished_at')} for stage in ('verify','adoption','review','drift','qa') if isinstance((row:=steps.get(stage)),dict)}
    return {k:state.get(k) for k in ('recovery_status','version','task','status','next_action','completed','findings','decisions','final_evidence','attempts','retry_budgets','architecture','architecture_check','beads')}


def routes(project, settings):
    route_path=load('routing-path').resolve(HERE.parent,project)
    routing=read(route_path);policy=load('provider-policy')
    mode=policy.mode(project)
    if settings['policy']=='claude-only':mode='claude-only'
    author=policy.select_route(routing,'nightshift-architect',1,mode)
    # The factory's explicit author selection remains authoritative.
    if settings['provider'] not in routing.get('allowed_providers',['claude','codex','local']):raise ValueError('author_provider_not_allowed')
    if mode=='claude-only' and settings['provider']!='claude':raise ValueError('author_policy_conflict')
    choices=list(routing['roles']['nightshift-architect']['gears'].values())+routing.get('adversarial',{}).get('routes',[])
    selected=next((r for r in choices if r.get('provider')==settings['provider']),None)
    author=dict(provider=settings['provider'],model=settings.get('model') or (selected or {}).get('model'))
    if not author['model']:raise ValueError('author_model_missing')
    reviewer=policy.select_route(routing,'nightshift-code-fact-extractor',1,mode,author['provider'],True)
    if mode!='claude-only' and reviewer['provider']==author['provider']:raise ValueError('independent_reviewer_missing')
    if not reviewer.get('model'):raise ValueError('reviewer_model_missing')
    return dict(policy=mode,routing_path=str(route_path),routing_sha256=sha(route_path),
                stages={s:(reviewer if s in REVIEW else author) for s in STAGES})


def source(project, task):
    value=recovery.workspace(project)
    # Stage-generated artifacts are explicit dependencies, not arbitrary source.
    value['files']={k:v for k,v in value['files'].items() if not k.startswith('docs/'+task+'/')}
    return recovery.digest(value['files'])


RUNTIME_SCRIPTS = ('nightshift-pipeline.py', 'nightshift-agent.sh', 'nightshift-factory.sh',
                   'nightshift-contract.jq', 'nightshift-provider-policy.py',
                   'nightshift-route.sh', 'nightshift-capability.sh',
                   'nightshift-dispatch-bounded.sh', 'nightshift-handoff.py',
                   'nightshift-behavior-proof.py', 'nightshift-retry-budget.py', 'nightshift-repair-check.py',
                   'nightshift-routing-path.py', 'nightshift-source-evaluation.py',
                   'nightshift-spec-repair-brief.py', 'nightshift-review-reuse.py',
                   'nightshift-recovery-state.py', 'nightshift-ticket-budget.py')


def runtime_digest():
    root = HERE.parent
    files = [HERE/name for name in RUNTIME_SCRIPTS]
    for folder, pattern in (('agents', '*.md'), ('contracts', '*.json')):
        files += sorted((root/folder).glob(pattern))
    return recovery.digest({str(path.relative_to(root)): sha(path) for path in files})


def stage_policy(plan, stage):
    stages = plan.get('stages') or {}
    dependencies = STAGES[:STAGES.index(stage)+1] if stage in STAGES else tuple(stages)
    return dict(policy=plan.get('policy'), stages={name: stages[name] for name in dependencies if name in stages})


def nested_routing(plan, stage):
    routing = read(plan['routing_path'])
    roles = {
        'product': ('nightshift-code-fact-extractor', 'nightshift-spec-writer', 'nightshift-behavior-reviewer'),
        'adversarial': ('nightshift-code-fact-extractor', 'nightshift-behavior-reviewer'),
        'implement': ('nightshift-engineer', 'nightshift-architect', 'nightshift-run-all-tests', 'nightshift-behavior-reviewer'),
        'review': ('nightshift-code-fact-extractor', 'nightshift-architect', 'nightshift-engineer'),
        'drift': ('nightshift-code-fact-extractor',),
        'qa': ('nightshift-run-all-tests',),
    }
    dependencies = STAGES[:STAGES.index(stage)+1] if stage in STAGES else STAGES
    selected = {role for dependency in dependencies for role in roles[dependency]}
    return dict(configuration={key: routing.get(key) for key in
                               ('providers', 'allowed_providers', 'defaults', 'local', 'adversarial')},
                roles={role: routing['roles'].get(role) for role in sorted(selected)})


def inputs(project, task, stage, state):
    docs=Path(project)/'docs'/task
    value=dict(command_sha256=sha(HERE.parent/'commands'/('nightshift-'+stage+'.md')),runtime=runtime_digest(),policy=stage_policy(state['plan'],stage),decisions=state['decisions'],ref=state.get('request'),request_sha256=state.get('request_sha256'))
    value['architecture']=load('architecture').resolve(project)
    value['architecture_checker']=sha(HERE/'nightshift-architecture.py')
    value['nested_routing'] = recovery.digest(nested_routing(state['plan'], stage))
    if stage == 'adversarial':
        # A source-repair contract is an input; its generated receipt is not.
        # Bind registered evidence as well as the manifest so content repairs
        # can resume without rewriting an otherwise accepted specification.
        manifest = docs / 'repair-checks.json'
        value['repair_contract'] = None
        if manifest.exists() or manifest.is_symlink():
            checker = load('repair-check')
            manifest = checker.confined(Path(project).resolve(), 'docs/' + task + '/repair-checks.json')
            contract, identity = checker.read_json(manifest)
            findings = contract.get('findings') if isinstance(contract, dict) else None
            if not isinstance(findings, list) or not 1 <= len(findings) <= 256:
                raise ValueError('invalid repair contract findings')
            artifacts = {}
            for finding in findings:
                for key in ('artifact', 'prior_artifact'):
                    name = finding[key]
                    path = checker.confined(Path(project).resolve(), name)
                    _, artifacts[name] = checker.read_json(path)
            value['repair_contract'] = dict(manifest=identity, artifacts=artifacts)
    value['spec']={n:sha(docs/n) if (docs/n).is_file() else None for n in ('SPEC.md','behavior-scenarios.json')}
    if (docs/'behavior-scenarios.json').is_file():
        # Classification attestations are review output, not authored requirements.
        value['spec']['behavior-scenarios.json']=load('behavior-proof').semantics(read(docs/'behavior-scenarios.json'))
    if stage in ('review','drift','qa'):value['source']=source(project,task)
    # A source edit requires final review again, not a fresh implementation plan.
    return recovery.digest(value)


def proof(project, task, gate):
    process=subprocess.run([sys.executable,str(HERE/'nightshift-behavior-proof.py'),'gate','--project',str(project),'--task',task,'--gate',gate],capture_output=True,text=True,timeout=30)
    try:return json.loads(process.stdout)
    except ValueError:return dict(status='blocked',reason='proof_gate_unavailable')


def validate_product_scope(project, task):
    """Parse literal scope paths without activating a scope lease or changing files."""
    helper=load('behavior-proof')
    try:
        return helper.scope_table(Path(project),task)
    except (OSError,ValueError,helper.Invalid,helper.Blocked) as error:
        raise ValueError('product_scope_invalid:'+str(error)) from None


def record_classification_review(project, task, route, receipt, policy='standard'):
    """Reuse independent adversarial evidence bound to the current scenarios."""
    path = Path(project)/'docs'/task/'behavior-scenarios.json'
    helper = load('behavior-proof')
    try:
        original = path.read_text(); doc = json.loads(original)
        provider = (route or {}).get('provider'); model = (route or {}).get('model')
        if (not provider or not model or
                (provider == doc['author']['provider'] and not (policy == 'claude-only' and provider == 'claude'))):
            return False
        report = validate_receipt(receipt, task, 'adversarial', project)
        if report['status'] != 'pass':
            return False
        classifications = [Path(project)/row['path'] for row in report['evidence']
                           if (Path(row['path']).parent == path.relative_to(project).parent
                               and Path(row['path']).name.startswith('classification-review-')
                               and Path(row['path']).suffix == '.json')]
        if len(classifications) != 1:
            return False
        classification = classifications[0]
        helper.validate_doc(doc, Path(project), task)
        digest = helper.semantics(doc)
        observed = read(classification)
        if (set(observed) != {'version', 'task', 'decision', 'reviewed_input_sha256', 'case_ids'}
                or type(observed['version']) is not int or observed['version'] != 1
                or observed['task'] != task or observed['decision'] != 'approve'
                or observed['reviewed_input_sha256'] != digest
                or not isinstance(observed['case_ids'], list)
                or any(not isinstance(case, str) for case in observed['case_ids'])
                or len(observed['case_ids']) != len(doc['cases'])
                or set(observed['case_ids']) != {case['id'] for case in doc['cases']}):
            return False
        missing = [a for a in [doc['applicability']]+[case['applicability'] for case in doc['cases']]
                   if (a.get('review') is None or a['review']['decision'] != 'approve'
                       or a['review']['reviewed_input_sha256'] != digest
                       or (a['review']['reviewer_provider'], a['review']['reviewer_author_id']) ==
                          (doc['author']['provider'], doc['author']['author_id']))]
        if not missing:
            return False
        # Attestation output must not mutate an artifact already hash-bound by
        # this receipt. The immutable classification artifact binds semantics.
        if any(row['path'] == str(path.relative_to(project)) for row in report['evidence']):
            return False
        review = dict(reviewer_provider=provider,
                      reviewer_author_id='nightshift-adversarial:'+str(model)+':'+sha(receipt),
                      decision='approve', reviewed_input_sha256=digest, evidence_sha256=sha(receipt))
        for applicability in missing:
            applicability['review'] = dict(review)
        helper.validate_doc(doc, Path(project), task)
        if helper.semantics(doc) != digest:
            return False
        recovery.atomic(path, doc)
        return True
    except (OSError, ValueError, KeyError, TypeError, helper.Invalid, helper.Blocked):
        return False


def receipt_object(path):
    path=Path(path)
    if path.resolve()!=path.absolute():raise ValueError('stage_receipt.file:unsafe')
    if not path.exists():raise ValueError('stage_receipt.file:missing')
    if not path.is_file():raise ValueError('stage_receipt.file:unsafe')
    if path.stat().st_size>2000000:raise ValueError('stage_receipt.file:oversized')
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('stage_receipt.json:duplicate_key')
            value[key]=item
        return value
    with path.open('rb') as stream:raw=stream.read(2000001)
    if len(raw)>2000000:raise ValueError('stage_receipt.file:oversized')
    try:value=json.loads(raw,object_pairs_hook=unique)
    except (json.JSONDecodeError,UnicodeError,RecursionError):raise ValueError('stage_receipt.json:invalid_json') from None
    if not isinstance(value,dict):raise ValueError('stage_receipt.root:expected_object')
    return value


def validate_receipt(path, task, stage, project):
    value=receipt_object(path)
    def require(condition,field,reason):
        if not condition:raise ValueError('stage_receipt.'+field+':'+reason)
    require(set(value)=={'version','task','stage','status','findings','checks','evidence'},'fields','exact_fields_required')
    require(type(value['version']) is int,'version','expected_integer')
    require(value['version']==1,'version','unsupported_version')
    for field,expected in (('task',task),('stage',stage)):
        require(isinstance(value[field],str),field,'expected_string')
        require(value[field]==expected,field,'identity_mismatch')
    require(isinstance(value['status'],str),'status','expected_string')
    require(value['status'] in ('pass','fail'),'status','expected_pass_or_fail')
    for field in ('findings','checks','evidence'):require(isinstance(value[field],list),field,'expected_array')
    require(len(value['findings'])<=20,'findings','too_many_findings')
    for index,finding in enumerate(value['findings']):
        field='findings['+str(index)+']'
        require(isinstance(finding,dict),field,'expected_object')
        require(set(finding)=={'id','target','problem'},field,'exact_fields_required')
        for key,item in finding.items():require(isinstance(item,str) and bool(item.strip()) and len(item)<=4000,field+'.'+key,'expected_nonempty_bounded_string')
    for index,check in enumerate(value['checks']):
        field='checks['+str(index)+']'
        require(isinstance(check,dict),field,'expected_object')
        require(set(check)=={'command','exit_code'},field,'exact_fields_required')
        require(isinstance(check['command'],str) and bool(check['command'].strip()),field+'.command','expected_nonempty_string')
        require(type(check['exit_code']) is int,field+'.exit_code','expected_integer')
        if value['status']=='pass':require(check['exit_code']==0,field+'.exit_code','required_check_failed')
    for index,item in enumerate(value['evidence']):
        field='evidence['+str(index)+']'
        require(isinstance(item,dict),field,'expected_object')
        require(set(item)=={'path','sha256'},field,'exact_fields_required')
        require(isinstance(item['path'],str) and bool(item['path']) and '\0' not in item['path'],field+'.path','expected_nonempty_string')
        require(isinstance(item['sha256'],str) and bool(re.fullmatch(r'[0-9a-f]{64}',item['sha256'])),field+'.sha256','expected_sha256')
        p=Path(project)/item['path']
        require(not Path(item['path']).is_absolute() and '..' not in Path(item['path']).parts and p.resolve()==p.absolute(),field+'.path','unsafe_path')
        if value['status']=='pass':require(p.is_file() and sha(p)==item['sha256'],field,'stale_stage_evidence')
    if value['status']=='pass' and (value['findings'] or not value['checks'] or not value['evidence']):raise ValueError('passing_evidence_missing')
    return value


def retain_diagnostic(receipt, task, stage, project, reason):
    """Retain bounded untrusted observations; these never become repair findings."""
    receipt=Path(receipt);target=receipt.with_suffix('.diagnostic.json')
    if target.exists():
        if target.resolve()!=target.absolute():return None
        try:record=read(target)
        except RecursionError:raise ValueError('invalid_diagnostic_record') from None
        rows=record.get('reported_findings')
        if record.get('label')!='UNVALIDATED_WORKER_DIAGNOSTIC' or not isinstance(rows,list) or len(rows)>3 or any(not isinstance(row,dict) or not set(row)<= {'id','target','problem'} or any(not isinstance(item,str) or len(item)>1024 for item in row.values()) for row in rows) or (record.get('validation_error') is not None and (not isinstance(record['validation_error'],str) or len(record['validation_error'])>512)):
            raise ValueError('invalid_diagnostic_record')
    else:
        worker=Path(project)/'docs'/task/('.nightshift-'+receipt.name)
        source=worker if worker.exists() or worker.is_symlink() else receipt
        record=dict(version=1,label='UNVALIDATED_WORKER_DIAGNOSTIC',reason=reason[:512],source_path=str(source),source_bytes=None,source_sha256=None,preview='',preview_truncated=False,reported_findings=[])
        if source.resolve()!=source.absolute():record['validation_error']='stage_receipt.file:unsafe'
        elif not source.exists():record['validation_error']='stage_receipt.file:missing'
        elif not source.is_file():record['validation_error']='stage_receipt.file:unsafe'
        else:
            record['source_bytes']=source.stat().st_size
            if record['source_bytes']>2000000:record['validation_error']='stage_receipt.file:oversized';record['preview_truncated']=True
            else:
                with source.open('rb') as stream:raw=stream.read(2000001)
                if len(raw)>2000000:raise ValueError('stage_receipt.file:changed_during_diagnostic')
                record['source_bytes']=len(raw);record['source_sha256']=hashlib.sha256(raw).hexdigest()
                record['preview']=raw[:8192].decode('utf-8',errors='replace');record['preview_truncated']=len(raw)>8192
                try:
                    value=receipt_object(source)
                    findings=value.get('findings')
                    if isinstance(findings,list):
                        for finding in findings[:3]:
                            if isinstance(finding,dict):record['reported_findings'].append({key:item[:1024] for key,item in finding.items() if key in ('id','target','problem') and isinstance(item,str)})
                    validate_receipt(source,task,stage,project)
                except (OSError,ValueError) as error:record['validation_error']=str(error)[:512]
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(record,stream,sort_keys=True)
    return dict(path=str(target),sha256=sha(target),label=record['label'],validation_error=record.get('validation_error'),reported_findings=record['reported_findings'])


class Pipeline:
    def __init__(self, project, task, settings, runner=None):
        self.project=Path(project).resolve();self.task=task;self.settings=settings;self.runner=runner or self.dispatch
        self.directory=root(project,task);self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/'state.json'
        self.state=snapshot(project,task) or dict(version=1,task=task,worktree=str(self.project),completed={},attempts=[],findings=[],history=[],next_action='product',status='pending',created_at=time.time())
        if self.state.get('version')!=1 or self.state.get('worktree')!=str(self.project):raise ValueError('pipeline_identity_changed')

    def save(self):recovery.atomic(self.path,self.state)

    def accept_classification(self, reviewer):
        """Revalidate physical receipts after an attestation-only scenario edit."""
        path=self.project/'docs'/self.task/'behavior-scenarios.json'
        original=path.read_bytes(); name=str(path.relative_to(self.project))
        affected={}
        for stage,row in self.state['completed'].items():
            if sha(row['receipt'])!=row['sha256'] or row['input_sha256']!=inputs(self.project,self.task,stage,self.state):
                raise ValueError('classification_revalidation_stale_stage')
            report=validate_receipt(row['receipt'],self.task,stage,self.project)
            if any(item['path']==name for item in report['evidence']):
                affected[stage]=(dict(row),report)
        if not record_classification_review(self.project,self.task,reviewer.get('route'),
                                            Path(self.state['completed']['adversarial']['receipt']),
                                            self.state['plan']['policy']):
            return False
        completed=dict(self.state['completed']); history=list(self.state['history'])
        try:
            helper=load('behavior-proof'); helper.reviewed(read(path))
            argv=[sys.executable,str(HERE/'nightshift-behavior-proof.py'),'validate',
                  '--project',str(self.project),'--task',self.task,'--scenarios',str(path)]
            checked=subprocess.run(argv,capture_output=True,text=True,timeout=30)
            if checked.returncode:raise ValueError('classification_revalidation_failed')
            for stage,(row,report) in affected.items():
                if row['input_sha256']!=inputs(self.project,self.task,stage,self.state):
                    raise ValueError('classification_changed_stage_semantics')
                value=dict(report,checks=report['checks']+[dict(command=' '.join(argv),exit_code=0)],
                           evidence=[dict(item,sha256=sha(path)) if item['path']==name else item
                                     for item in report['evidence']])
                receipt=self.directory/(stage+'-classification-'+recovery.digest(value)+'.json')
                if receipt.exists():
                    if read(receipt)!=value:raise ValueError('classification_receipt_changed')
                else:recovery.atomic(receipt,value)
                validate_receipt(receipt,self.task,stage,self.project)
                self.state['completed'][stage]=dict(row,receipt=str(receipt),sha256=sha(receipt))
                self.state['history'].append(dict(stage=stage,record=row,
                    reason='classification_attestations_revalidated',receipt=str(receipt)))
            self.save()
            return True
        except BaseException:
            # Preserve the previous physical bindings if revalidation cannot finish.
            fd,temporary=tempfile.mkstemp(prefix='.classification-',dir=path.parent)
            with os.fdopen(fd,'wb') as stream:
                stream.write(original);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,path)
            self.state['completed']=completed;self.state['history']=history
            raise

    def refresh(self):
        selected=routes(self.project,self.settings)  # before any paid work
        # Draft authorship survives runtime changes. Never infer it from today's default.
        docs=self.project/'docs'/self.task
        if (docs/'SPEC.md').is_file() and (docs/'behavior-scenarios.json').is_file():
            author=read(docs/'behavior-scenarios.json').get('author', {})
            provider=author.get('provider')
            if provider not in ('codex','claude','local') or not author.get('author_id'):
                raise ValueError('existing_draft_author_missing')
            marker=docs/'spec-author-provider.txt'
            writer=docs/'spec-writer.out.json'
            if marker.exists() and marker.read_text().strip()!=provider:
                raise ValueError('existing_draft_author_conflict')
            if writer.exists():
                report=read(writer)
                recorded=report.get('_provenance', report.get('artifacts', {})).get('provider')
                if recorded!=provider:raise ValueError('existing_draft_author_conflict')
            selected['spec_author']=author
            selected['stages']['adversarial']=load('provider-policy').select_route(
                read(selected['routing_path']),'nightshift-code-fact-extractor',1,
                selected['policy'],provider,True)
        decisions=load('console-decisions').read(load('console-decisions').location(self.project,self.task))['requests']
        self.state['decisions']=[dict(sha256=d['sha256'],question=d['question'],response=d['response']) for d in decisions]
        self.state['architecture']=load('architecture').resolve(self.project)
        self.state['beads']=load('architecture').mirror(self.project,self.state['architecture'],self.state.get('beads',{}),dict(external_ref=self.settings['ref']+'#nightshift-architecture-links',title='Architecture links for '+self.task,body='Ticket: '+self.settings['ref'],source='nightshift',source_id=self.task))
        self.state['plan']=selected
        self.state['request']=self.settings['ref']
        request=Path(self.settings['ref'].removeprefix('spec:'))
        if request.is_file():self.state['request_sha256']=sha(request)
        if any(d['response'] is None for d in decisions):
            self.state.update(status='needs-decision',next_action='answer_recorded_question');self.save();return False
        for stage in STAGES:
            record=self.state['completed'].get(stage)
            if not record:continue
            try:
                valid=record['input_sha256']==inputs(self.project,self.task,stage,self.state) and sha(record['receipt'])==record['sha256']
                if valid:validate_receipt(record['receipt'],self.task,stage,self.project)
            except (OSError,ValueError):valid=False
            if not valid:
                self.state['history'].append(dict(stage=stage,record=record,reason='relevant_inputs_changed'))
                del self.state['completed'][stage]
        self.import_draft()
        self.state['next_action']=next((s for s in STAGES if s not in self.state['completed']),'final_evidence')
        self.save();return True

    def import_draft(self):
        # Import only the drafting stage, never a legacy review or completion claim.
        if 'product' in self.state['completed']:
            return
        if self.state['attempts'] or self.state['history']:
            imported=any(h.get('reason')=='existing_draft_validated_without_dispatch' for h in self.state['history'])
            if not imported or (self.state.get('finding_stage')=='adversarial' and self.state['findings']):
                return
        docs=self.project/'docs'/self.task
        if not all((docs/name).is_file() for name in ('SPEC.md','behavior-scenarios.json')):
            return
        try:validate_product_scope(self.project,self.task)
        except ValueError as error:
            self.state['findings']=[dict(id='existing-draft-scope',target='SPEC.md',problem=str(error))]
            return
        argv=[sys.executable,str(HERE/'nightshift-behavior-proof.py'),'validate','--project',str(self.project),'--task',self.task,'--scenarios',str(docs/'behavior-scenarios.json')]
        result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
        if result.returncode:
            self.state['findings']=[dict(id='existing-draft-schema',target='behavior-scenarios.json',problem='Existing draft requires schema repair; preserve it and resolve the validator failure.')]
            return
        value=dict(version=1,task=self.task,stage='product',status='pass',findings=[],checks=[dict(command=' '.join(argv),exit_code=0)],evidence=[dict(path=str((docs/name).relative_to(self.project)),sha256=sha(docs/name)) for name in ('SPEC.md','behavior-scenarios.json')])
        receipt=self.directory/('product-import-'+recovery.digest(value)+'.json')
        if receipt.exists():
            if read(receipt)!=value:raise ValueError('import_receipt_changed')
        else:
            recovery.atomic(receipt,value)
        validate_receipt(receipt,self.task,'product',self.project)
        self.state['completed']['product']=dict(receipt=str(receipt),sha256=sha(receipt),input_sha256=inputs(self.project,self.task,'product',self.state))
        self.state['history'].append(dict(stage='product',reason='existing_draft_validated_without_dispatch'))

    def dispatch(self, stage, handoff, receipt):
        route=self.state['plan']['stages'][stage]
        worker_receipt=self.project/'docs'/self.task/('.nightshift-'+receipt.name)
        worker_receipt.parent.mkdir(parents=True,exist_ok=True)
        if worker_receipt.exists():raise ValueError('worker_receipt_already_exists')
        # Product needs source identity before any retained contract exists.
        # Later stages keep the canonical task key and all existing ownership.
        reference=self.settings['ref'] if stage=='product' else self.task
        argv=['bash',str(HERE/'nightshift-factory.sh'),reference,'--project',str(self.project),'--branch','none','--provider',route['provider'],'--model',route['model'],'--provider-policy',self.state['plan']['policy'],'--auth',self.settings['auth'],'--dashboard','off']
        env=dict(os.environ,NIGHTSHIFT_PIPELINE_STAGE=stage,NIGHTSHIFT_PIPELINE_TASK=self.task,NIGHTSHIFT_PIPELINE_TICKET_JSON=os.environ.get('NIGHTSHIFT_TICKET_JSON',''),NIGHTSHIFT_STAGE_RECEIPT=str(worker_receipt),NIGHTSHIFT_STAGE_HANDOFF=str(handoff),NIGHTSHIFT_UPDATE_GUARD='1',NIGHTSHIFT_OUTPUT_CHILD='1',NIGHTSHIFT_ROUTING_FILE=self.state['plan']['routing_path'],NIGHTSHIFT_BUDGET_TASK=os.environ.get('NIGHTSHIFT_BUDGET_TASK',self.task),NIGHTSHIFT_BUDGET_PROJECT=os.environ.get('NIGHTSHIFT_BUDGET_PROJECT',str(self.project)))
        # Existing ticket admission owns the deadline; no replacement allowance.
        budget=load('ticket-budget').snapshot(self.project,self.task)
        timeout=budget['wall_seconds_remaining'] if budget and budget['wall_seconds_remaining'] is not None else None
        if timeout is not None and timeout<=0:raise ValueError('ticket_budget_exhausted')
        with receipt.with_suffix('.log').open('wb') as log:
            process=subprocess.Popen(argv,cwd=self.project,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            completed=False
            try:
                code=process.wait(timeout=timeout);completed=True
                if worker_receipt.is_file() and not worker_receipt.is_symlink():
                    try:recovery.atomic(receipt,receipt_object(worker_receipt))
                    except (OSError,ValueError):
                        if not code:raise
                return code
            except BaseException:
                if not completed:
                    try:os.killpg(process.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:os.killpg(process.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                        process.wait()
                raise

    def publish(self):
        def git(*args):
            return subprocess.check_output(['git','-C',str(self.project),*args],stderr=subprocess.PIPE).decode().strip()
        branch=git('symbolic-ref','--short','HEAD')
        if branch in ('main','master'):raise ValueError('publication_requires_ticket_branch')
        helper=load('behavior-proof')
        scope,_=helper.scope_table(self.project,self.task)
        changed=set(git('diff','--name-only','HEAD','-z').split('\0'))
        changed.update(git('ls-files','--others','--exclude-standard','-z').split('\0'))
        changed={name for name in changed if name and not name.startswith('.nightshift/')}
        # Local workflow locks and receipts stay in place; they are not source publication.
        if any(name not in scope and not name.startswith('docs/'+self.task+'/') for name in changed):
            raise ValueError('publication_out_of_scope_changes:'+','.join(sorted(name for name in changed if name not in scope and not name.startswith('docs/'+self.task+'/'))))
        if any(not (self.project/name).is_file() or (self.project/name).resolve()!=(self.project/name).absolute() for name in changed):
            raise ValueError('publication_deleted_or_unsafe_file')
        if changed:
            git('add','--',*sorted(changed))
            git('commit','--only','-m','Complete verified Nightshift task '+self.task,'--',*sorted(changed))
        if view(self.project,self.task)['status']=='stale' or proof(self.project,self.task,'final').get('outcome')!='pass':
            raise ValueError('publication_evidence_changed')
        head=git('rev-parse','HEAD')
        publication=self.state.setdefault('publication',{})
        if publication.get('pushed_head')!=head:
            git('push','--set-upstream','origin',branch)
            publication.update(pushed_head=head,branch=branch);self.save()
        if self.settings.get('pr') and not publication.get('url'):
            result=subprocess.run(['gh','pr','list','--head',branch,'--state','open','--json','url'],cwd=self.project,capture_output=True,text=True,check=True,timeout=30)
            existing=json.loads(result.stdout)
            if existing:publication['url']=existing[0]['url']
            else:
                body=self.directory/'publication.md'
                body.write_text('Complete task '+self.task+'.\n\nAll required controller stages and final automated/manual acceptance evidence pass. Retained task evidence is in docs/'+self.task+'/.\n')
                result=subprocess.run(['gh','pr','create','--head',branch,'--title','Complete task '+self.task,'--body-file',str(body)],cwd=self.project,capture_output=True,text=True,check=True,timeout=30)
                publication['url']=result.stdout.strip()
            self.save()

    def run(self):
        stop_before = self.settings.get('stop_before')
        if stop_before is not None and stop_before not in STAGES:
            raise ValueError('stop_before must name a canonical stage')
        fd=os.open(self.directory/'controller.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.state=snapshot(self.project,self.task) or self.state
            if self.state.get('recovery_sessions'):
                raise ValueError('Use the explicit recovery operation; normal resume cannot repeat adopted implementation or renew recovery')
            if not self.refresh():return 1
            while self.state['next_action'] in STAGES:
                stage=self.state['next_action']
                if stop_before is not None and STAGES.index(stage) >= STAGES.index(stop_before):
                    self.state.update(status='paused', next_action=stage,
                                      pause_reason='operator_stage_boundary')
                    self.save()
                    return 0
                self.state.pop('pause_reason', None)
                budget=load('ticket-budget').snapshot(self.project,self.task)
                if budget and budget['exhausted']:raise ValueError('ticket_budget_exhausted')
                count=sum(a['stage']==stage for a in self.state['attempts'])
                retry=load('retry-budget');budget_path=self.directory/(stage+'-budget.json')
                for prior in (a for a in self.state['attempts'] if a['stage']==stage):
                    category=prior.get('category') or ('success' if prior['status']=='pass' else 'substantive' if prior.get('reason')=='stage_failed' else 'schema' if prior['status']=='fail' else 'pending')
                    retry.account(budget_path,prior['receipt'],category)
                accounting=read(budget_path) if budget_path.exists() else None
                if accounting and (accounting['next_action']=='stop' or 'pending' in accounting['attempts'].values()):
                    self.state.update(status='blocked',next_action='inspect_exhausted_or_interrupted_'+stage);self.save();return 1
                recorded = False
                if stage == 'implement' and 'adversarial' in self.state['completed']:
                    reviewer = next((a for a in reversed(self.state['attempts'])
                                     if a['stage'] == 'adversarial' and a['status'] == 'pass'), None)
                    if reviewer:
                        recorded = self.accept_classification(reviewer)
                signature=inputs(self.project,self.task,stage,self.state)
                current_source=source(self.project,self.task)
                if not recorded and any(a['stage']==stage and a.get('reason')=='stage_failed' and a['input_sha256']==signature and a.get('source_sha256',current_source)==current_source for a in self.state['attempts']):
                    self.state.update(status='blocked',next_action='repair_unchanged_'+stage);self.save();return 1
                if stage=='implement':
                    result=proof(self.project,self.task,'development')
                    if result.get('outcome')!='pass' and result.get('reason') not in UNSEALED:
                        self.state['completed'].pop('adversarial',None)
                        self.state.update(status='repairing',next_action='adversarial',finding_stage='adversarial',findings=[dict(id='development-proof',target='behavior-scenarios.json',problem=result.get('reason','missing'))]);self.save();continue
                receipt=self.directory/(stage+'-'+str(count+1)+'.json');handoff=receipt.with_suffix('.handoff.json')
                bundle=load('handoff').build(self.project,self.task,stage,self.state,self.task+' '+stage+' '+ ' '.join(f['problem'] for f in self.state['findings']))
                recovery.atomic(handoff,bundle)
                attempt=dict(stage=stage,receipt=str(receipt),input_sha256=inputs(self.project,self.task,stage,self.state),status='running',route=self.state['plan']['stages'][stage],started_at=time.time())
                self.state['attempts'].append(attempt);self.state['status']='running';self.save()
                retry.account(budget_path,str(receipt),'pending')
                value=None
                try:
                    code=self.runner(stage,handoff,receipt)
                    if code:raise ValueError(worker_failure(receipt,code))
                    value=validate_receipt(receipt,self.task,stage,self.project)
                    if value['status']!='pass':raise ValueError('stage_failed')
                    if load('architecture').resolve(self.project)!=self.state['architecture']:
                        raise ValueError('architecture_changed_during_dispatch')
                    if stage in ('implement','review','drift','qa') and self.state['architecture']:
                        checked=load('architecture').check(self.project,self.task,self.state['architecture'])
                        self.state['architecture_check']=checked
                        recovery.atomic(receipt.with_suffix('.architecture.json'),checked)
                        if checked['status']!='pass':
                            if len(checked['findings'])>20:
                                raise ValueError('architecture_findings_exceed_stage_limit; full findings retained in architecture receipt')
                            value=dict(value,status='fail',findings=checked['findings'])
                            raise ValueError('stage_failed')
                    if stage=='product':
                        docs=self.project/'docs'/self.task
                        if not (docs/'SPEC.md').is_file() or not (docs/'behavior-scenarios.json').is_file():raise ValueError('draft_artifacts_missing')
                        validate_product_scope(self.project,self.task)
                    if stage in REVIEW and attempt['input_sha256'] != inputs(self.project,self.task,stage,self.state):
                        raise ValueError('review_changed_its_inputs')
                    attempt.update(status='pass',category='success',finished_at=time.time())
                    self.state.setdefault('retry_budgets',{})[stage]=retry.account(budget_path,str(receipt),'success')
                    self.state['completed'][stage]=dict(receipt=str(receipt),sha256=sha(receipt),input_sha256=inputs(self.project,self.task,stage,self.state))
                    if self.state.get('finding_stage')==stage:self.state['findings']=[]
                    self.save()
                except (OSError,ValueError,subprocess.SubprocessError) as error:
                    attempt.update(status='fail',source_sha256=source(self.project,self.task),reason=str(error),category='substantive' if str(error)=='stage_failed' else 'transport' if str(error).startswith(('worker_exit_', 'preflight_')) else 'schema',finished_at=time.time())
                    try:attempt['diagnostic']=retain_diagnostic(receipt,self.task,stage,self.project,str(error))
                    except (OSError,ValueError):attempt['diagnostic_unavailable']=True
                    self.state.setdefault('retry_budgets',{})[stage]=retry.account(budget_path,str(receipt),attempt['category'])
                    self.state['findings']=(value or {}).get('findings',[]) or [dict(id=stage+'-evidence',target=str(receipt),problem=str(error))]
                    self.state.update(status='blocked',next_action=stage,finding_stage=stage);self.save()
                    if str(error)=='stage_failed' and stage in REVIEW and self.state['findings']:
                        repair='product' if stage=='adversarial' else 'implement'
                        self.state['completed'].pop(repair,None)
                        self.state.update(status='repairing',next_action=repair);self.save();continue
                    return 1
                # Recompute dependencies; a writer cannot approve its changed inputs.
                if not self.refresh():return 1
            if stop_before is not None:
                # Preparation must not publish an already implemented ticket.
                self.state.update(status='paused', pause_reason='operator_stage_boundary')
                self.save()
                return 0
            outcome=proof(self.project,self.task,'final')
            self.state['final_evidence']=outcome
            if outcome.get('reason')=='manual_acceptance_pending':
                self.state.update(status='pending_manual_acceptance',next_action='operator_verify_manual_acceptance')
            elif outcome.get('outcome')=='pass' and all(s in self.state['completed'] for s in STAGES):
                self.state.update(status='verified_pending_publication',next_action='publish');self.save()
                if self.settings.get('push'):
                    try:self.publish()
                    except (OSError,ValueError,subprocess.SubprocessError) as error:
                        self.state.update(error=str(error));self.save();return 1
                self.state.update(status='complete',next_action='none')
            else:self.state.update(status='blocked',next_action='repair_final_evidence')
            self.save();return 0 if self.state['status']=='complete' else 1


def worker_failure(receipt, code):
    """Expose bounded typed admission failures without copying raw provider output."""
    log = receipt.with_suffix('.log')
    if 64 <= code <= 71 and log.is_file():
        with log.open('rb') as handle:
            handle.seek(max(0, log.stat().st_size - 16384))
            lines = handle.read(16384).decode('utf-8', errors='replace').splitlines()
        for line in reversed(lines):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if (isinstance(value, dict) and value.get('schema_version') == 1
                    and value.get('status') == 'blocked' and isinstance(value.get('checks'), dict)
                    and re.fullmatch(r'[A-Z_]{1,80}', str(value.get('reason', '')))
                    and re.fullmatch(r'[a-z_]{1,80}', str(value.get('next_action', '')))):
                return 'preflight_' + value['reason'] + ': ' + value['next_action'] + ' (worker_exit_' + str(code) + '; log=' + str(log) + ')'
    return 'worker_exit_' + str(code)



def continuation_routes(project, target):
    """Validate launcher configuration with the shared parser and route policy."""
    home = Path(os.environ.get('NIGHTSHIFT_HOME', str(Path.home()/'.nightshift')))
    configurations = []
    for location in (home, Path(project)):
        result = subprocess.run(['bash', str(HERE/'nightshift-setup.sh'), '--project', str(location), '--read'],
                                capture_output=True, text=True, check=True)
        configurations.append(json.loads(result.stdout))
    global_runtime, project_runtime = (value.get('runtime', {}) for value in configurations)
    mode = load('provider-policy').mode(project)
    configured_provider = project_runtime.get('provider', global_runtime.get('provider', 'codex'))
    provider = 'claude' if mode == 'claude-only' else configured_provider
    canonical = lambda value: 'local' if value == 'ollama' else value
    provider = canonical(provider)
    # Match the factory's provider-specific model precedence; a different
    # provider must never inherit another runtime's legacy model.
    model = ''
    for runtime, default_provider in ((project_runtime, configured_provider), (global_runtime, 'codex')):
        models = runtime.get('models', {})
        selected = models.get(provider)
        if selected is None and provider == 'local':selected = models.get('ollama')
        if selected is None and canonical(runtime.get('provider', default_provider)) == provider:
            selected = runtime.get('model')
        if selected is not None:
            model = selected
            break
    settings = dict(provider=provider, model=model, policy=mode)
    routes(project, settings)
    routes(target, settings)


def continuation_preflight(project, task):
    """Validate the registered target without preparing, saving or granting anything."""
    root(project, task)  # validate identity before passing it to the worktree helper
    result = subprocess.run(['bash', str(HERE/'nightshift-worktree.sh'), 'check', task,
                             '--project', str(project)], capture_output=True, text=True)
    if result.returncode:
        print(result.stderr or result.stdout, file=sys.stderr)
        return result.returncode
    registered = json.loads(result.stdout)
    if not registered.get('registered'):
        raise ValueError('retained_worktree_missing')
    target = Path(registered['worktree']).resolve(strict=True)
    if root(target, task) != root(project, task):
        raise ValueError('pipeline_repository_changed')
    existing = snapshot(project, task)
    if existing and Path(existing['worktree']).resolve() != target:
        raise ValueError('pipeline_identity_changed')
    admission = subprocess.run(['bash', str(HERE/'nightshift-preflight-check.sh'),
                                '--project', str(target), '--branch', 'none', '--ref', 'jira:'+task],
                               capture_output=True, text=True)
    if admission.returncode:
        print(admission.stdout or admission.stderr, file=sys.stderr)
        return admission.returncode
    # Parse all runtime settings too; a syntactically invalid manifest cannot earn time.
    settings = subprocess.run(['bash', str(HERE/'nightshift-setup.sh'), '--project', str(target), '--read'],
                              capture_output=True, text=True)
    if settings.returncode:
        print(settings.stdout or settings.stderr, file=sys.stderr)
        return settings.returncode
    # Use the same operation-route and provider-policy validation as preparation.
    # The launcher resumes from the primary project; a retained worktree override
    # must also admit those routes before a new allowance is recorded.
    continuation_routes(project, target)
    print(target)
    return 0



def prepare(project, task, settings):
    project=Path(project).resolve()
    routes(project,settings)
    existing=snapshot(project,task)
    if existing:
        target=Path(existing['worktree']).resolve()
        if root(target,task)!=root(project,task):raise ValueError('pipeline_repository_changed')
        return target
    owner=load('console-actions').directory(project).parent/'worktrees'/(task+'.json')
    if owner.exists():
        result=subprocess.run(['bash',str(HERE/'nightshift-worktree.sh'),'check',task,'--project',str(project)],capture_output=True,text=True,check=True)
        return Path(json.loads(result.stdout)['worktree'])
    if settings['branch']=='none':return project
    if settings['branch']!='auto':raise ValueError('named_branch_requires_existing_registered_worktree')
    argv=['bash',str(HERE/'nightshift-worktree.sh'),'prepare',task,'--project',str(project)]
    if settings.get('base'):argv+=['--base',settings['base']]
    result=subprocess.run(argv,capture_output=True,text=True,check=True)
    return Path(json.loads(result.stdout)['worktree'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--task',required=True);parser.add_argument('--settings')
    parser.add_argument('--continuation-preflight', action='store_true')
    parser.add_argument('--review-spec', action='store_true')
    args=parser.parse_args();pipeline=None
    if not args.continuation_preflight and not args.settings:parser.error('--settings is required')
    try:
        if args.continuation_preflight:return continuation_preflight(args.project,args.task)
        settings=json.loads(args.settings)
        if args.review_spec and settings['branch'] != 'auto':
            raise ValueError('Spec review requires automatic ticket branching')
        if settings['branch']=='auto':
            console=load('console-actions')
            # Keep the saved invocation stable: resolving the worker's input path
            # must not invalidate the operator's approval of that invocation.
            console.save(args.project,args.task,settings,review_spec=args.review_spec)
            review=console.state(args.project,args.task).get('review')
            if review is not None and not review['approved']:
                print('nightshift: awaiting spec approval; open the console and choose Approve and continue. No model started.',file=sys.stderr)
                return 0
        elif settings['branch'] == 'none':
            load('console-actions').save(args.project, args.task, settings)
        request=Path(args.project)/settings['ref'].removeprefix('spec:')
        if request.is_file():settings['ref']=str(request.resolve())
        target=prepare(args.project,args.task,settings)
        pipeline=Pipeline(target,args.task,settings);code=pipeline.run()
        print(json.dumps(pipeline.state));return code
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        if pipeline and not pipeline.state.get('recovery_sessions'):
            pipeline.state.update(status='blocked',next_action='repair_configuration',error=str(error));pipeline.save()
        print(json.dumps(dict(status='blocked',reason=str(error))),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
