#!/usr/bin/env python3
"""Model-free, create-only operation intake through shared source contracts."""
from contextlib import contextmanager
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('intake_operations',HERE/'nightshift-operations.py')
ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)


def runtime():
    revision=subprocess.check_output(['git','-C',str(HERE.parent),'rev-parse','HEAD'],text=True).strip()
    installed=shutil.which('nightshift')
    tools={name:subprocess.run(['bash',str(HERE/'nightshift-capability.sh'),'--presence',name],capture_output=True).returncode==0 for name in ('git','python3','jq','gh','codex','claude','ollama')}
    return dict(tools=tools,serving_revision=revision,controller_sha256=ops.sha(Path(__file__)),operations_sha256=ops.sha(HERE/'nightshift-operations.py'),installed_launcher=str(Path(installed).resolve()) if installed else None,installed_revision='unverified',capabilities=['guided-intake-v1','operations-v1'],endpoint='local-reviewed-worktree',provider_auth='unverified:no_provider_probe')


def resolve(project,reference):
    if not ops.bounded_text(reference) or len(reference)>1024 or reference.startswith('-'):raise ValueError('source_reference_required')
    if reference.startswith('spec:') or (project/reference).is_file():
        ops.safe(project,reference.removeprefix('spec:'))
    elif not re.fullmatch(r'gh:(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#)?[0-9]+',reference):
        raise ValueError('intake_source_profile_unsupported:use_project_markdown_or_github')
    result=subprocess.run(['bash',str(HERE/'nightshift-ticket-source.sh'),reference],cwd=project,capture_output=True,text=True,timeout=30)
    if result.returncode:raise ValueError('source_unavailable:check_reference_tool_and_auth')
    if len(result.stdout.encode())>ops.MAX_REQUEST//2:raise ValueError('source_too_large:no_truncation')
    source=json.loads(result.stdout)
    if not isinstance(source,dict) or not isinstance(source.get('body'),str) or not source['body'].strip():raise ValueError('source_body_required')
    task=str(source['source_id'])
    if source['source']=='gh':task='gh-'+ops.digest(dict(repository=source.get('repository'),id=task))[:16]
    ops.location(project,task)
    return source,task


def readiness(project,reference):
    result=subprocess.run(['bash',str(HERE/'nightshift-preflight-check.sh'),'--project',str(project),'--branch','none','--ref',reference],capture_output=True,text=True,timeout=30)
    try:value=json.loads(result.stdout)
    except ValueError:value=dict(status='blocked',reason='readiness_unavailable',next_action='inspect_project_baseline_and_manifest')
    return dict(admission=value,provider_auth='unverified:no_provider_probe',provider_calls=0)


class Intake:
    def __init__(self,project,task):
        self.project=Path(project).resolve();self.task=task
        self.directory=ops.location(self.project,task).parent.parent/'intake'/task
        self.path=self.directory/'state.json'
    @contextmanager
    def lease(self):
        if os.environ.get('NIGHTSHIFT_ROLE_CHILD')=='1':raise ValueError('worker_cannot_prepare_intake')
        if self.directory.resolve()!=self.directory.absolute():raise ValueError('unsafe_intake_state')
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(self.directory/'lease',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX)
            self.state=ops.read(self.path) if self.path.exists() else dict(version=1,project=str(self.project),task=self.task,drafts={},requests={})
            if self.state['project']!=str(self.project) or self.state['task']!=self.task:raise ValueError('intake_identity_changed')
            yield
    def save(self):
        if len(json.dumps(self.state).encode())>1000000:raise ValueError('intake_history_full:retain_evidence')
        ops.recovery.atomic(self.path,self.state)
    def proposal(self,source,options):
        allowed={'scope','checks','requirements','rules','architecture','allowance'}
        if not isinstance(options,dict) or set(options)-allowed:raise ValueError('invalid_intake_choices')
        if len(json.dumps(options,sort_keys=True))>4000:raise ValueError('intake_choices_too_large:no_truncation')
        missing=[key for key in allowed if not options.get(key)]
        if missing:return {},None,sorted(missing)
        for key in ('rules','architecture'):
            path=ops.safe(self.project,options[key])
            if not path.is_file() or path.stat().st_size>ops.MAX_REQUEST or not path.read_text().strip():raise ValueError('intake_context_missing:'+key)
        checks=options['checks'];cases=options['requirements'];scope=options['scope']
        if not isinstance(cases,list) or not cases:raise ValueError('intake_requirements_required')
        ids=set()
        for case in cases:
            ops.exact(case,'id requirement manual')
            if not ops.bounded_text(case['id']) or case['id'] in ids or not ops.bounded_text(case['requirement']) or type(case['manual']) is not bool:raise ValueError('invalid_intake_requirement')
            ids.add(case['id'])
        allowance=ops.limits(options['allowance'])
        prefix='docs/'+self.task+'/'
        inputs=dict(request=prefix+'REQUEST.md',spec=prefix+'SPEC.md',scenarios=prefix+'scenarios.json',rules=options['rules'],architecture=options['architecture'])
        plan=dict(version=1,inputs=inputs,scope=scope,checks=checks,environment={},reviewer_policy=dict(version=1,require_different_provider=True,semantic_plan=None),limits={op:dict(allowance) for op in ops.OPS},aggregate=allowance,publication=None)
        files={inputs['request']:source['body'],inputs['spec']:source['body'],inputs['scenarios']:json.dumps(dict(version=1,cases=cases),indent=2)+'\n',prefix+'operations.json':json.dumps(plan,indent=2)+'\n',prefix+'ticket.json':json.dumps(source,indent=2)+'\n'}
        for name in scope:
            path=ops.safe(self.project,name)
            if name in files:raise ValueError('intake_scope_overlaps_artifacts')
        for check in checks:
            ops.exact(check,'id argv')
            if not isinstance(check['argv'],list) or len(check['argv'])!=2:raise ValueError('invalid_intake_check')
            path=ops.safe(self.project,check['argv'][1])
            if not path.is_file():raise ValueError('intake_test_oracle_missing')
        with tempfile.TemporaryDirectory(prefix='nightshift-intake-validation-') as directory:
            target=Path(directory).resolve()
            for name,text in files.items():
                path=ops.safe(target,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            ops.plan(target,self.task)
        if len(json.dumps(files).encode())>ops.MAX_REQUEST:raise ValueError('intake_proposal_too_large:no_truncation')
        return files,plan,[]
    def preview(self,reference,source,options):
        with self.lease():
            files,plan,missing=self.proposal(source,options)
            dependencies={name:ops.sha(ops.safe(self.project,name)) if ops.safe(self.project,name).is_file() else None for name in files}
            if plan:
                for name in [plan['inputs']['rules'],plan['inputs']['architecture'],*plan['scope'],*(c['argv'][1] for c in plan['checks'])]:
                    path=ops.safe(self.project,name);dependencies[name]=ops.sha(path) if path.is_file() else None
            payload=dict(source=source,reference=reference,options=options,files=files,dependencies=dependencies,runtime=runtime())
            binding=ops.digest(payload)
            prior=self.state['drafts'].get(binding)
            if prior:return prior
            decision=None
            if missing:
                decisions=ops.load('console-decisions');decision_task='intake-'+self.task+'-'+ops.digest(source)[:12]
                decision=decisions.request(self.project,decision_task,dict(question='Provide the unresolved intake choices: '+', '.join(missing),reason='These choices determine scope, evidence and allowance. An answer prepares a draft only; it cannot run a worker.',options=[],continuation='none',decision_key='intake-choices'))
            row=dict(version=1,task=self.task,binding=binding,status='needs_decision' if missing else 'preview',missing=missing,decision=decision,plan=plan,**payload,readiness=readiness(self.project,reference),provider_calls=0)
            self.state['drafts'][binding]=row;self.save();return row
    def apply(self,binding,operator,request,cancel=False):
        if not ops.bounded_text(operator) or not isinstance(request,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',request):raise ValueError('intake_operator_and_request_required')
        with self.lease():
            payload=dict(binding=binding,operator=operator,cancel=cancel)
            previous=self.state['requests'].get(request)
            if previous:
                if previous['payload']!=payload:raise ValueError('request_id_conflict')
                if previous['status']=='cancelled':return previous
            row=self.state['drafts'].get(binding)
            if not row:raise ValueError('intake_preview_missing')
            if cancel:
                if row['status']=='prepared':raise ValueError('intake_already_prepared:no_execution_to_cancel')
                result=dict(status='cancelled',payload=payload,task=self.task,provider_calls=0)
                row['status']='cancelled';self.state['requests'][request]=result;self.save();return result
            if row['status']=='cancelled':raise ValueError('intake_cancelled')
            if row['status']=='prepared':
                source,task=resolve(self.project,row['reference'])
                if source!=row['source'] or task!=self.task or runtime()!=row['runtime']:raise ValueError('intake_preview_stale')
                receipt=next(value for value in self.state['requests'].values() if value['payload']['binding']==binding and value['status']=='prepared')
                if any(ops.sha(ops.safe(self.project,name))!=digest for name,digest in receipt['files'].items()):raise ValueError('prepared_intake_changed')
                return receipt
            if row['missing']:raise ValueError('intake_decisions_required')
            source,task=resolve(self.project,row['reference'])
            if source!=row['source'] or task!=self.task or runtime()!=row['runtime']:raise ValueError('intake_preview_stale')
            for name,expected in row['dependencies'].items():
                path=ops.safe(self.project,name);actual=ops.sha(path) if path.is_file() else None
                desired=__import__('hashlib').sha256(row['files'][name].encode()).hexdigest() if name in row['files'] else None
                if actual!=expected and not (previous and name in row['files'] and actual==desired):raise ValueError('intake_input_changed:'+name)
                if name in row['files'] and expected is not None and actual!=desired:raise ValueError('intake_preserves_existing_file:'+name)
            result=dict(status='applying',payload=payload,task=self.task,provider_calls=0)
            self.state['requests'][request]=result;self.save()
            for name,text in row['files'].items():
                path=ops.safe(self.project,name);path.parent.mkdir(parents=True,exist_ok=True)
                if path.exists():
                    if path.read_bytes()!=text.encode():raise ValueError('intake_input_changed:'+name)
                    continue
                fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
                with os.fdopen(fd,'wb') as stream:stream.write(text.encode());stream.flush();os.fsync(stream.fileno())
            result.update(status='prepared',files={name:ops.sha(ops.safe(self.project,name)) for name in row['files']})
            row['status']='prepared';self.save();return result


def api(project,body):
    project=Path(project).resolve();action=body['action']
    if action=='intake-bootstrap':return dict(runtime=runtime(),provider_calls=0)
    if action=='intake-preview':
        source,task=resolve(project,body['source'])
        return Intake(project,task).preview(body['source'],source,body.get('choices',{}))
    if action=='intake-answer':
        intake=Intake(project,body['task'])
        with intake.lease():
            row=intake.state['drafts'].get(body['binding'])
            if not row or row['status']!='needs_decision':raise ValueError('intake_question_not_current')
            source,task=resolve(project,row['reference'])
            if source!=row['source'] or task!=intake.task:raise ValueError('intake_source_changed')
            _,_,missing=intake.proposal(source,body['choices'])
            if missing:raise ValueError('intake_choices_incomplete:'+','.join(missing))
            decisions=ops.load('console-decisions')
            decisions.respond(project,row['decision']['task'],row['decision']['sha256'],'',json.dumps(body['choices'],sort_keys=True))
            reference=row['reference']
        return intake.preview(reference,source,body['choices'])
    if action in ('intake-apply','intake-cancel'):
        return Intake(project,body['task']).apply(body['binding'],body['operator'],body['request'],action=='intake-cancel')
    raise ValueError('unknown_intake_action')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['bootstrap','preview','answer','apply','cancel'])
    parser.add_argument('--project',default=os.getcwd())
    for key in ('task','source','binding','operator','request'):parser.add_argument('--'+key)
    parser.add_argument('--choices',type=json.loads,default={})
    args=vars(parser.parse_args());project=args.pop('project');args['action']='intake-'+args['action']
    try:print(json.dumps(api(project,{k:v for k,v in args.items() if v is not None})))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='blocked',reason=str(error))));raise SystemExit(1)
