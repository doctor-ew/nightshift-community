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
import time

HERE = Path(__file__).resolve().parent
STAGES = ('product', 'adversarial', 'implement', 'review', 'drift', 'qa')
REVIEW = ('adversarial', 'review', 'drift', 'qa')


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
    except (OSError,ValueError,KeyError):
        state=dict(state,status='stale',next_action='revalidate_changed_evidence')
    return {k:state.get(k) for k in ('version','task','status','next_action','completed','findings','decisions','final_evidence','attempts')}


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


def inputs(project, task, stage, state):
    docs=Path(project)/'docs'/task
    value=dict(command_sha256=sha(HERE.parent/'commands'/('nightshift-'+stage+'.md')),policy=state['plan'],decisions=state['decisions'],ref=state.get('request'),request_sha256=state.get('request_sha256'))
    value['spec']={n:sha(docs/n) if (docs/n).is_file() else None for n in ('SPEC.md','behavior-scenarios.json')}
    if stage in ('review','drift','qa'):value['source']=source(project,task)
    # A source edit requires final review again, not a fresh implementation plan.
    return recovery.digest(value)


def proof(project, task, gate):
    process=subprocess.run([sys.executable,str(HERE/'nightshift-behavior-proof.py'),'gate','--project',str(project),'--task',task,'--gate',gate],capture_output=True,text=True,timeout=30)
    try:return json.loads(process.stdout)
    except ValueError:return dict(status='blocked',reason='proof_gate_unavailable')


def validate_receipt(path, task, stage, project):
    value=read(path)
    if set(value)!={'version','task','stage','status','findings','checks','evidence'} or value['version']!=1 or value['task']!=task or value['stage']!=stage:
        raise ValueError('invalid_stage_receipt')
    if value['status'] not in ('pass','fail') or not isinstance(value['findings'],list) or not isinstance(value['checks'],list) or not isinstance(value['evidence'],list):raise ValueError('invalid_stage_verdict')
    if len(value['findings'])>20:raise ValueError('too_many_findings')
    for finding in value['findings']:
        if set(finding)!={'id','target','problem'} or any(not isinstance(v,str) or not v or len(v)>4000 for v in finding.values()):raise ValueError('invalid_finding')
    if value['status']=='pass':
        if value['findings'] or not value['checks'] or not value['evidence']:raise ValueError('passing_evidence_missing')
        for check in value['checks']:
            if set(check)!={'command','exit_code'} or not isinstance(check['command'],str) or not check['command'].strip() or type(check['exit_code']) is not int or check['exit_code']!=0:raise ValueError('required_check_failed')
        for item in value['evidence']:
            if set(item)!={'path','sha256'}:raise ValueError('invalid_evidence_reference')
            p=Path(project)/item['path']
            if Path(item['path']).is_absolute() or '..' in Path(item['path']).parts or p.resolve()!=p.absolute() or not p.is_file() or sha(p)!=item['sha256']:raise ValueError('stale_stage_evidence')
    return value


class Pipeline:
    def __init__(self, project, task, settings, runner=None):
        self.project=Path(project).resolve();self.task=task;self.settings=settings;self.runner=runner or self.dispatch
        self.directory=root(project,task);self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/'state.json'
        self.state=snapshot(project,task) or dict(version=1,task=task,worktree=str(self.project),completed={},attempts=[],findings=[],history=[],next_action='product',status='pending',created_at=time.time())
        if self.state.get('version')!=1 or self.state.get('worktree')!=str(self.project):raise ValueError('pipeline_identity_changed')

    def save(self):recovery.atomic(self.path,self.state)

    def refresh(self):
        selected=routes(self.project,self.settings)  # before any paid work
        decisions=load('console-decisions').read(load('console-decisions').location(self.project,self.task))['requests']
        self.state['decisions']=[dict(sha256=d['sha256'],question=d['question'],response=d['response']) for d in decisions]
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
        self.state['next_action']=next((s for s in STAGES if s not in self.state['completed']),'final_evidence')
        self.save();return True

    def dispatch(self, stage, handoff, receipt):
        route=self.state['plan']['stages'][stage]
        worker_receipt=self.project/'docs'/self.task/('.nightshift-'+receipt.name)
        worker_receipt.parent.mkdir(parents=True,exist_ok=True)
        if worker_receipt.exists():raise ValueError('worker_receipt_already_exists')
        argv=['bash',str(HERE/'nightshift-factory.sh'),self.task,'--project',str(self.project),'--branch','none','--provider',route['provider'],'--model',route['model'],'--provider-policy',self.state['plan']['policy'],'--auth',self.settings['auth'],'--dashboard','off']
        env=dict(os.environ,NIGHTSHIFT_PIPELINE_STAGE=stage,NIGHTSHIFT_PIPELINE_TASK=self.task,NIGHTSHIFT_PIPELINE_TICKET_JSON=os.environ.get('NIGHTSHIFT_TICKET_JSON',''),NIGHTSHIFT_STAGE_RECEIPT=str(worker_receipt),NIGHTSHIFT_STAGE_HANDOFF=str(handoff),NIGHTSHIFT_UPDATE_GUARD='1',NIGHTSHIFT_OUTPUT_CHILD='1',NIGHTSHIFT_ROUTING_FILE=self.state['plan']['routing_path'],NIGHTSHIFT_BUDGET_TASK=os.environ.get('NIGHTSHIFT_BUDGET_TASK',self.task),NIGHTSHIFT_BUDGET_PROJECT=os.environ.get('NIGHTSHIFT_BUDGET_PROJECT',str(self.project)))
        # Existing ticket admission owns the deadline; no replacement allowance.
        budget=load('ticket-budget').snapshot(self.project,self.task)
        timeout=min(600,budget['wall_seconds_remaining']) if budget and budget['wall_seconds_remaining'] is not None else 600
        if timeout<=0:raise ValueError('ticket_budget_exhausted')
        with receipt.with_suffix('.log').open('wb') as log:
            process=subprocess.Popen(argv,cwd=self.project,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                code=process.wait(timeout=timeout)
                if worker_receipt.is_file() and not worker_receipt.is_symlink():
                    recovery.atomic(receipt,read(worker_receipt))
                return code
            except BaseException:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
                raise

    def run(self):
        fd=os.open(self.directory/'controller.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if not self.refresh():return 1
            while self.state['next_action'] in STAGES:
                stage=self.state['next_action']
                budget=load('ticket-budget').snapshot(self.project,self.task)
                if budget and budget['exhausted']:raise ValueError('ticket_budget_exhausted')
                count=sum(a['stage']==stage for a in self.state['attempts'])
                if count>=3:
                    self.state.update(status='blocked',next_action='inspect_exhausted_'+stage);self.save();return 1
                signature=inputs(self.project,self.task,stage,self.state)
                if any(a['stage']==stage and a.get('reason')=='stage_failed' and a['input_sha256']==signature for a in self.state['attempts']):
                    self.state.update(status='blocked',next_action='repair_unchanged_'+stage);self.save();return 1
                if stage=='implement':
                    result=proof(self.project,self.task,'development')
                    if result.get('outcome')!='pass':
                        self.state['completed'].pop('adversarial',None)
                        self.state.update(status='repairing',next_action='adversarial',finding_stage='adversarial',findings=[dict(id='development-proof',target='behavior-scenarios.json',problem=result.get('reason','missing'))]);self.save();continue
                receipt=self.directory/(stage+'-'+str(count+1)+'.json');handoff=receipt.with_suffix('.handoff.json')
                bundle=load('handoff').build(self.project,self.task,stage,self.state,self.task+' '+stage+' '+ ' '.join(f['problem'] for f in self.state['findings']))
                recovery.atomic(handoff,bundle)
                attempt=dict(stage=stage,receipt=str(receipt),input_sha256=inputs(self.project,self.task,stage,self.state),status='running',route=self.state['plan']['stages'][stage],started_at=time.time())
                self.state['attempts'].append(attempt);self.state['status']='running';self.save()
                value=None
                try:
                    code=self.runner(stage,handoff,receipt)
                    value=validate_receipt(receipt,self.task,stage,self.project)
                    if code:raise ValueError('worker_exit_'+str(code))
                    if value['status']!='pass':raise ValueError('stage_failed')
                    if stage=='product':
                        docs=self.project/'docs'/self.task
                        if not (docs/'SPEC.md').is_file() or not (docs/'behavior-scenarios.json').is_file():raise ValueError('draft_artifacts_missing')
                    if stage=='adversarial' and proof(self.project,self.task,'development').get('outcome')!='pass':raise ValueError('development_proof_missing')
                    if stage in REVIEW and attempt['input_sha256'] != inputs(self.project,self.task,stage,self.state):
                        raise ValueError('review_changed_its_inputs')
                    attempt.update(status='pass',finished_at=time.time())
                    self.state['completed'][stage]=dict(receipt=str(receipt),sha256=sha(receipt),input_sha256=inputs(self.project,self.task,stage,self.state))
                    if self.state.get('finding_stage')==stage:self.state['findings']=[]
                    self.save()
                except (OSError,ValueError,subprocess.SubprocessError) as error:
                    attempt.update(status='fail',reason=str(error),finished_at=time.time())
                    self.state['findings']=(value or {}).get('findings',[]) or [dict(id=stage+'-evidence',target=str(receipt),problem=str(error))]
                    self.state.update(status='blocked',next_action=stage,finding_stage=stage);self.save()
                    if str(error)=='stage_failed' and stage in REVIEW and self.state['findings']:
                        repair='product' if stage=='adversarial' else 'implement'
                        self.state['completed'].pop(repair,None)
                        self.state.update(status='repairing',next_action=repair);self.save();continue
                    return 1
                # Recompute dependencies; a writer cannot approve its changed inputs.
                if not self.refresh():return 1
            outcome=proof(self.project,self.task,'final')
            self.state['final_evidence']=outcome
            if outcome.get('reason')=='manual_acceptance_pending':
                self.state.update(status='pending_manual_acceptance',next_action='operator_verify_manual_acceptance')
            elif outcome.get('outcome')=='pass' and all(s in self.state['completed'] for s in STAGES):
                self.state.update(status='verified_pending_publication' if self.settings.get('push') else 'complete',next_action='publish' if self.settings.get('push') else 'none')
            else:self.state.update(status='blocked',next_action='repair_final_evidence')
            self.save();return 0 if self.state['status']=='complete' else 1


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
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--task',required=True);parser.add_argument('--settings',required=True)
    args=parser.parse_args();settings=json.loads(args.settings);pipeline=None
    request=Path(args.project)/settings['ref'].removeprefix('spec:')
    if request.is_file():settings['ref']=str(request.resolve())
    try:
        target=prepare(args.project,args.task,settings)
        if settings['branch']=='auto':load('console-actions').save(args.project,args.task,settings)
        pipeline=Pipeline(target,args.task,settings);code=pipeline.run()
        print(json.dumps(pipeline.state));return code
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        if pipeline:
            pipeline.state.update(status='blocked',next_action='repair_configuration',error=str(error));pipeline.save()
        print(json.dumps(dict(status='blocked',reason=str(error))),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
