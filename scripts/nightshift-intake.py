#!/usr/bin/env python3
"""Model-free source intake and inspectable drafts for the shared operations API."""
from contextlib import contextmanager
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('intake_operations',HERE/'nightshift-operations.py')
ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)
MAX_BYTES=262144


def safe(project,name):
    path=ops.safe(project,name)
    if str(Path(name))!=name or any(part in ('.git','.nightshift','.codex','.claude','.agents') or part.startswith('.env') for part in Path(name).parts):
        raise ValueError('unsafe_intake_path')
    return path


def file_record(project,name):
    path=safe(project,name)
    if not path.exists():return None
    if path.stat().st_size>MAX_BYTES:raise ValueError('intake_input_too_large')
    return dict(sha256=ops.sha(path),mode=stat.S_IMODE(path.stat().st_mode))


def create_artifact(project,name,content,mode):
    """Create through directory descriptors without following parent links."""
    directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in Path(project).parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory);directory=child
        for part in Path(name).parts[:-1]:
            try:os.mkdir(part,dir_fd=directory)
            except FileExistsError:pass
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory);directory=child
        fd=os.open(Path(name).name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode,dir_fd=directory)
        with os.fdopen(fd,'wb') as stream:
            stream.write(content.encode());stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),mode)
    finally:os.close(directory)


def resolve_source(project,ref):
    if not isinstance(ref,str) or not 0<len(ref)<=1000 or '\0' in ref:raise ValueError('source_reference_required')
    if ref.startswith('spec:'):
        name=ref[5:];safe(project,name)
        argv=['python3',str(HERE/'nightshift-spec-source.py'),ref]
    elif re.fullmatch(r'gh:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*',ref):
        argv=['bash',str(HERE/'nightshift-ticket-source.sh'),ref]
    else:raise ValueError('intake_requires_project_spec_or_qualified_github_reference')
    env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GH_PROMPT_DISABLED':'1','PYTHONDONTWRITEBYTECODE':'1'}
    with tempfile.TemporaryDirectory(prefix='nightshift-intake-source-') as folder:
        output=Path(folder)/'source.json'
        try:
            code=ops.load('controller-recovery').bounded(argv,project,env,15,output)
            if code or output.stat().st_size>MAX_BYTES:raise ValueError('source_unavailable_check_reference_authentication_and_tools')
            source=json.loads(output.read_text())
        except (OSError,ValueError,subprocess.SubprocessError):
            raise ValueError('source_unavailable_check_reference_authentication_and_tools') from None
    if not isinstance(source,dict) or not all(isinstance(source.get(key),str) for key in ('source','source_id','external_ref','title','body')):
        raise ValueError('invalid_source_response')
    expected_kind='spec' if ref.startswith('spec:') else 'gh'
    if source['source']!=expected_kind:raise ValueError('source_identity_mismatch')
    if source['source']=='gh':
        expected=re.fullmatch(r'gh:([^#]+)#([0-9]+)',ref)
        if (not expected or source.get('repository')!=expected[1].lower() or str(source['source_id'])!=expected[2]
            or source['external_ref']!='gh-'+expected[2]
            or source.get('url','').lower()!='https://github.com/'+expected[1].lower()+'/issues/'+expected[2]):raise ValueError('source_identity_mismatch')
    else:
        name=ref[5:];body=safe(project,name).read_text()
        if (source.get('source_path')!=name or source['external_ref']!=ref or source['body']!=body
            or source['source_id']!='spec-'+hashlib.sha256(name.encode()).hexdigest()[:16]
            or source.get('source_revision')!=hashlib.sha256(body.encode()).hexdigest()):raise ValueError('source_identity_mismatch')
    return dict(reference=ref,record=source,sha256=ops.digest(source))


def identity(root):
    root=Path(root).resolve()
    try:
        revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],stderr=subprocess.DEVNULL,text=True,timeout=3).strip()
        dirty=bool(subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],stderr=subprocess.DEVNULL,text=True,timeout=3))
    except (OSError,subprocess.SubprocessError):revision=None;dirty=None
    return dict(root=str(root),revision=revision,dirty=dirty)


def runtime_identity():
    installed=Path(os.environ.get('NIGHTSHIFT_HOME',str(Path.home()/'.nightshift')))/'scripts/nightshift-factory.sh'
    return dict(serving=identity(HERE.parent),installed=identity(installed.resolve().parents[1]) if installed.is_file() else dict(root=None,revision=None,dirty=None),
                capabilities=['operations-v1','guided-intake-v1'],activation='unchanged')


class Intake:
    def __init__(self,project,task):
        self.project=Path(project).resolve();self.task=task
        self.directory=ops.location(self.project,task).parent.parent/'intake'/task
        self.path=self.directory/'state.json';self.reload()

    def reload(self):
        self.state=ops.read(self.path) if self.path.exists() else dict(version=1,project=str(self.project),task=self.task,status='new',sources=[],drafts=[],journal={})
        if self.state.get('version')!=1 or self.state.get('project')!=str(self.project) or self.state.get('task')!=self.task:raise ValueError('intake_identity_changed')

    def save(self):
        if len(json.dumps(self.state).encode())>1500000:raise ValueError('intake_history_limit_preserve_evidence')
        ops.recovery.atomic(self.path,self.state)

    @contextmanager
    def lease(self):
        if os.environ.get('NIGHTSHIFT_ROLE_CHILD')=='1':raise ValueError('worker_cannot_control_intake')
        if self.directory.resolve()!=self.directory.absolute():raise ValueError('unsafe_intake_state')
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(self.directory/'lease',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise ValueError('intake_busy') from None
            self.reload();yield

    def live(self):
        if self.state['status']=='cancelled':raise ValueError('intake_cancelled_evidence_retained')

    def context(self,choices):
        names=set(choices['scope']+[choices[k] for k in ('rules','architecture','check')])
        routing=ops.load('routing-path').resolve(HERE.parent,self.project)
        manifest=ops.load('project-context').manifest_path(self.project)
        return dict(files={name:file_record(self.project,name) for name in sorted(names)},routing_sha256=ops.sha(routing),
                    manifest_sha256=ops.sha(manifest) if manifest.exists() else None,
                    decisions=ops.load('console-decisions').snapshot(self.project,self.task),intake_sha256=ops.sha(Path(__file__)))

    def view(self):
        self.reload()
        result=dict(task=self.task,status=self.state['status'],source=self.state['sources'][-1] if self.state['sources'] else None,
                    draft=self.state['drafts'][-1] if self.state['drafts'] else None,decisions=ops.load('console-decisions').snapshot(self.project,self.task),runtime=runtime_identity())
        readiness=dict(manifest='missing',routing='unavailable',authentication='unverified_no_provider_call',tools={tool:bool(shutil.which(tool)) for tool in ('git','python3','bash','jq')},source='resolved_snapshot' if result['source'] else 'unresolved')
        try:
            manifest=ops.load('project-context').manifest_path(self.project)
            if manifest.is_file():
                try:__import__('tomllib').loads(manifest.read_text());readiness['manifest']='present'
                except (OSError,ValueError):readiness['manifest']='invalid'
            if result['source'] and result['source']['record']['source']=='gh':readiness['tools']['gh']=bool(shutil.which('gh'))
            readiness['routing']='configured' if ops.load('routing-path').resolve(HERE.parent,self.project).is_file() else 'unavailable'
        except (OSError,ValueError):pass
        try:branch=subprocess.check_output(['git','-C',str(self.project),'symbolic-ref','--short','HEAD'],text=True,stderr=subprocess.DEVNULL,timeout=3).strip()
        except (OSError,subprocess.SubprocessError):branch=None
        result.update(readiness=readiness,endpoint=dict(kind='local-checkout',project=str(self.project),branch=branch,publish=False))
        if self.state['status']=='materialized':result['operations']=ops.api(self.project,dict(task=self.task,action='view'))
        return result

    def resolve(self,source):
        with self.lease():
            self.live()
            if self.state['status']=='materialized':raise ValueError('intake_already_materialized')
            if not self.state['sources'] or self.state['sources'][-1]['sha256']!=source['sha256']:
                if len(self.state['sources'])>=16:raise ValueError('intake_source_history_limit')
                self.state['sources'].append(source);self.state['status']='resolved';self.save()
        return self.view()

    def draft(self,choices):
        with self.lease():
            self.live()
            if self.state['status']=='materialized':raise ValueError('intake_already_materialized')
            if not self.state['sources']:raise ValueError('resolve_source_first')
            ops.exact(choices,'scope rules architecture check interpreter requirement')
            missing=[key for key,value in choices.items() if not value]
            if missing:
                source=self.state['sources'][-1]
                ops.load('console-decisions').request(self.project,self.task,dict(decision_key='intake-'+source['sha256'][:24],
                    question='Provide the missing intake choices: '+', '.join(missing),reason='The controller cannot invent implementation scope, checks, project guidance or acceptance.',options=[]))
                self.state['status']='needs_choices';self.save()
            else:
                if not isinstance(choices['scope'],list) or not 1<=len(choices['scope'])<=32 or len(set(choices['scope']))!=len(choices['scope']):raise ValueError('explicit_scope_required')
                if choices['interpreter'] not in ('python3','bash') or not ops.bounded_text(choices['requirement']):raise ValueError('explicit_check_and_acceptance_required')
                for name in choices['scope']:safe(self.project,name)
                for key in ('rules','architecture','check'):
                    if file_record(self.project,choices[key]) is None:raise ValueError('intake_input_missing:'+key)
                decisions=ops.load('console-decisions').snapshot(self.project,self.task)
                if decisions['pending']:raise ValueError('answer_pending_intake_choice_first')
                source=self.state['sources'][-1];base='docs/'+self.task+'/'
                plan=dict(version=1,inputs=dict(request=base+'request.md',spec=base+'SPEC.md',scenarios=base+'scenarios.json',rules=choices['rules'],architecture=choices['architecture']),
                    scope=choices['scope'],checks=[dict(id='declared-check',argv=[choices['interpreter'],choices['check']])],environment={},
                    reviewer_policy=dict(version=1,require_different_provider=False,semantic_plan=None),
                    limits={operation:dict(calls=3,seconds=60,wall_seconds=120) for operation in ops.OPS},aggregate=dict(calls=16,seconds=600,wall_seconds=900),publication=None)
                with tempfile.TemporaryDirectory(prefix='nightshift-intake-plan-') as folder:
                    target=Path(folder).resolve();planned=ops.plan_path(target,self.task);planned.parent.mkdir(parents=True);planned.write_text(json.dumps(plan))
                    ops.plan(target,self.task)
                answered='\n\n## Recorded product choices\n\n'+json.dumps(decisions['answered'],sort_keys=True) if decisions['answered'] else ''
                artifacts={base+'request.md':source['record']['body']+answered+'\n',base+'SPEC.md':'# Draft specification\n\n'+source['record']['body']+answered+'\n\n## Declared acceptance\n\n'+choices['requirement']+'\n',
                    base+'scenarios.json':json.dumps(dict(version=1,cases=[dict(id='intake-acceptance',requirement=choices['requirement'],manual=False)]))+'\n',base+'operations.json':json.dumps(plan,indent=2)+'\n'}
                if any(name in artifacts for name in choices['scope']+[choices[k] for k in ('rules','architecture','check')]):raise ValueError('intake_scope_overlaps_generated_artifacts')
                for name in artifacts:
                    if safe(self.project,name).exists():raise ValueError('intake_destination_exists:'+name)
                total=sum(len(content.encode()) for content in artifacts.values())+sum(safe(self.project,name).stat().st_size for name in set(choices['scope']+[choices[k] for k in ('rules','architecture','check')]) if safe(self.project,name).exists())
                if total>ops.MAX_REQUEST//2:raise ValueError('intake_artifacts_too_large:no_truncation')
                draft=dict(source_sha256=source['sha256'],choices=choices,artifacts=artifacts,context=self.context(choices),mode=0o644)
                draft['binding']=ops.digest(draft)
                if not self.state['drafts'] or self.state['drafts'][-1]['binding']!=draft['binding']:
                    if len(self.state['drafts'])>=8:raise ValueError('intake_draft_history_limit')
                    self.state['drafts'].append(draft)
                self.state['status']='draft';self.save()
        return self.view()

    def materialize(self,binding):
        with self.lease():
            self.live()
            if not self.state['drafts']:raise ValueError('intake_draft_required')
            draft=self.state['drafts'][-1]
            if binding!=draft['binding'] or binding!=ops.digest({key:value for key,value in draft.items() if key!='binding'}):raise ValueError('stale_intake_binding')
            if self.state['status']=='materialized':return self.view()
            source=resolve_source(self.project,self.state['sources'][-1]['reference'])
            if source['sha256']!=draft['source_sha256'] or self.context(draft['choices'])!=draft['context']:raise ValueError('intake_inputs_changed')
            journal=self.state['journal']
            for name,content in draft['artifacts'].items():
                path=safe(self.project,name)
                if path.exists() and (journal.get(name)!=dict(binding=binding,sha256=ops.digest(content),mode=draft['mode']) or path.read_bytes()!=content.encode() or stat.S_IMODE(path.stat().st_mode)!=draft['mode']):raise ValueError('intake_destination_changed:'+name)
            for name,content in draft['artifacts'].items():
                path=safe(self.project,name)
                if path.exists():continue
                journal[name]=dict(binding=binding,sha256=ops.digest(content),mode=draft['mode']);self.state['status']='materializing';self.save()
                try:create_artifact(self.project,name,content,draft['mode'])
                except FileExistsError:
                    journal[name]['conflict']=True;self.save()
                    raise ValueError('intake_destination_changed:'+name) from None
            ops.plan(self.project,self.task)
            self.state['status']='materialized';self.save()
        return self.view()

    def cancel(self):
        with self.lease():
            if self.state['status']=='materialized':raise ValueError('materialized_operations_require_operation_cancellation')
            self.state['status']='cancelled';self.save()
        return self.view()


def api(project,body):
    if not isinstance(body,dict):raise ValueError('intake_request_required')
    action=body.get('action');project=Path(project).resolve()
    if action=='resolve':
        ops.exact(body,'action reference');source=resolve_source(project,body['reference'])
        record=source['record'];task='intake-'+ops.digest([str(project),record['source'],record.get('repository'),record['source_id']])[:24]
        return Intake(project,task).resolve(source)
    allowed={'view':'action task','draft':'action task choices','materialize':'action task binding','cancel':'action task','answer':'action task sha256 answer'}
    if action not in allowed:raise ValueError('unknown_intake_action')
    ops.exact(body,allowed[action]);controller=Intake(project,body['task'])
    if action=='view':return controller.view()
    if action=='draft':return controller.draft(body['choices'])
    if action=='materialize':return controller.materialize(body['binding'])
    if action=='cancel':return controller.cancel()
    with controller.lease():
        controller.live();ops.load('console-decisions').respond(project,body['task'],body['sha256'],'',body['answer'])
    return controller.view()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',default='.');parser.add_argument('--request',required=True,help='JSON request file, or - for stdin')
    args=parser.parse_args()
    try:
        text=__import__('sys').stdin.read(MAX_BYTES+1) if args.request=='-' else Path(args.request).open().read(MAX_BYTES+1)
        if len(text.encode())>MAX_BYTES:raise ValueError('intake_request_too_large')
        print(json.dumps(api(args.project,json.loads(text))));return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='blocked',reason=str(error))));return 1

if __name__=='__main__':raise SystemExit(main())
