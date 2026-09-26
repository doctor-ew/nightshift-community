#!/usr/bin/env python3
"""Sequential package composition with durable allocations and isolated evidence."""
from contextlib import contextmanager
import fcntl
import importlib.util
import os
import json
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('package_contracts',HERE/'nightshift-work-packages.py')
contracts=importlib.util.module_from_spec(spec);spec.loader.exec_module(contracts)
ops=contracts.ops


class Packages:
    def __init__(self,project,task,worker=None,clock=time.time):
        self.project=Path(project).resolve();self.task=task;self.worker=worker;self.clock=clock
        self.preparation=ops.Operations(self.project,task,worker,clock)
        self.directory=ops.location(self.project,task).parent.parent/'packages'/task
        self.path=self.directory/'state.json';self.reload()

    def reload(self):
        self.state=ops.read(self.path) if self.path.exists() else dict(version=1,project=str(self.project),task=self.task,authorizations={},children={})
        if self.state['version']!=1 or self.state['project']!=str(self.project) or self.state['task']!=self.task:
            raise ValueError('package_controller_identity_changed')

    def save(self):
        if len(json.dumps(self.state).encode())>1800000:
            raise ValueError('package_state_limit:retain_existing_ledger')
        ops.recovery.atomic(self.path,self.state)

    def safe_git(self,target):
        metadata=target/'.git'
        if metadata.is_symlink() or (metadata.exists() and not metadata.is_dir()):
            raise ValueError('unsafe_package_git')
        if metadata.exists():
            for flag,expected in (('--absolute-git-dir',metadata),('--git-common-dir',metadata),('--show-toplevel',target)):
                value=subprocess.check_output(['git','-C',str(target),'rev-parse',flag],text=True).strip()
                if (target/value).resolve()!=expected:
                    raise ValueError('redirected_package_git')


    @contextmanager
    def lease(self):
        if os.environ.get('NIGHTSHIFT_ROLE_CHILD')=='1':raise ValueError('worker_cannot_control_packages')
        if self.directory.resolve()!=self.directory.absolute():raise ValueError('unsafe_package_state')
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(self.directory/'lease',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise ValueError('package_controller_busy') from None
            self.reload();yield

    def assess(self):
        self.preparation.reload()
        p,ctx=self.preparation.context()
        graph=contracts.validate(self.project,ops.read(ops.safe(self.project,p['inputs']['spec'])),p['inputs']['spec'],self.task)
        if p['inputs']['request']!=graph['parent'][5:]:raise ValueError('parent_request_mismatch')
        cases={c['id'] for c in self.preparation.scenarios(p)}
        if cases!=set(graph['requirements']):raise ValueError('parent_requirement_cases_mismatch')
        current=self.preparation.valid('groom',p,ctx)
        routes=ops.load('routing-path').resolve(HERE.parent,self.project)
        policy={str(n):ops.sha(n) for n in (routes,HERE/'nightshift-package-controller.py',HERE/'nightshift-work-packages.py')}
        settings=self.project/'.nightshift.toml'
        policy['project_settings']=ops.sha(settings) if settings.exists() else None
        return dict(status='ready' if current else 'blocked',reason=None if current else 'independent_decomposition_challenge_required',graph=graph,
                    binding=ops.digest(dict(graph=graph,challenge=self.preparation.state['results'].get('groom'),policy=policy)),policy=policy)

    def prepare(self,grant):
        """Author draft, deterministically validate, then independently challenge."""
        self.preparation.reload()
        g=self.preparation.state['authorizations'].get(grant)
        if not g or g['operations']!=ops.RECIPES['groom']:raise ValueError('decomposition_groom_authorization_required')
        p=ops.plan(self.project,self.task)
        ceiling=ops.limits(ops.read(ops.safe(self.project,p['inputs']['spec']))['aggregate'])
        with self.preparation.lease():
            g=self.preparation.state['authorizations'][grant]
            prior=[c for c in self.preparation.state['calls'].values() if c['grant']!=grant]
            available=dict(calls=ceiling['calls']-len(prior),seconds=ceiling['seconds']-sum(c['seconds'] if c['status']=='finished' else c['reserved_seconds'] for c in prior))
            if min(available.values())<=0:raise ValueError('parent_preparation_allowance_exhausted')
            for key in available:g['aggregate'][key]=min(g['aggregate'][key],available[key])
            g['deadline']=min(g['deadline'],g['created']+ceiling['wall_seconds'])
            self.preparation.save()
        result=self.preparation.execute(grant,'groom-spec',grant+'.packages-spec')
        if result['status'] not in ('passed','reused'):return dict(status='blocked',result=result)
        p=ops.plan(self.project,self.task)
        contracts.validate(self.project,ops.read(ops.safe(self.project,p['inputs']['spec'])),p['inputs']['spec'],self.task)
        for operation in ops.RECIPES['groom'][1:]:
            result=self.preparation.execute(grant,operation,grant+'.packages-'+operation)
            if result['status'] not in ('passed','reused'):return dict(status='blocked',result=result)
        return self.assess()

    def authorize(self,binding,operator,request):
        if not ops.bounded_text(operator) or not __import__('re').fullmatch(r'[A-Za-z0-9_.-]{1,100}',request):raise ValueError('operator_and_request_required')
        with self.lease(), self.preparation.lease():
            payload=dict(binding=binding,operator=operator)
            if request in self.state['authorizations']:
                prior=self.state['authorizations'][request]
                if prior['request_digest']!=ops.digest(payload):raise ValueError('request_id_conflict')
                return prior
            assessed=self.assess()
            if assessed['status']!='ready':raise ValueError(assessed['reason'])
            if binding!=assessed['binding']:raise ValueError('stale_package_assessment')
            for prior in self.state['authorizations'].values():
                if prior['request_digest']==ops.digest(payload):return prior
            graph=assessed['graph']
            # Preparation is already charged once; orchestration is never a call.
            prep=self.preparation.state['calls']
            prep_seconds=sum(c['seconds'] if c['status']=='finished' else c['reserved_seconds'] for c in prep.values())
            if len(prep)+sum(c['allowance']['calls'] for c in graph['children'])>graph['aggregate']['calls'] or prep_seconds+sum(c['allowance']['seconds'] for c in graph['children'])>graph['aggregate']['seconds']:
                raise ValueError('parent_allowance_insufficient_after_preparation')
            if any(c['status']!='finished' for c in prep.values()):raise ValueError('unknown_preparation_usage')
            grant=dict(version=1,id=request,request_digest=ops.digest(payload),binding=binding,operator=operator,graph=graph,
                       deadline=self.clock()+graph['aggregate']['wall_seconds'],preparation_calls=prep,
                       allocations={c['id']:dict(limit=c['allowance'],status='reserved') for c in graph['children']},status='authorized')
            self.state['authorizations'][request]=grant;self.save();return grant

    def child(self,key):
        row=self.state['children'][key]
        self.safe_git(Path(row['workspace']))
        return ops.Operations(row['workspace'],key,self.worker,self.clock)

    def usage(self,grant):
        g=self.state['authorizations'][grant]
        self.preparation.reload()
        observed={'preparation:'+key:value for key,value in self.preparation.state['calls'].items()}
        reserved=0
        for key,allocation in g['allocations'].items():
            if key not in self.state['children'] or self.state['children'][key].get('status')=='materializing':
                reserved+=allocation['limit']['seconds'];continue
            c=self.child(key)
            for ident,row in c.state['calls'].items():observed[key+':'+ident]=row
            unknown=sum(row['reserved_seconds'] for row in c.state['calls'].values() if row['status']!='finished')
            if allocation['status']!='complete':
                known=sum(row['seconds'] for row in c.state['calls'].values() if row['status']=='finished')
                reserved+=max(unknown,allocation['limit']['seconds']-known,0)
            else:reserved+=unknown
        return dict(calls=len(observed),execution_seconds=sum(c['seconds'] for c in observed.values() if c['status']=='finished'),
                    unknown_calls=sum(c['status']!='finished' for c in observed.values()),reserved_seconds=reserved,
                    request_bytes=sum(c['request_bytes'] for c in observed.values()),orchestration_provider_calls=0)

    def dependencies(self,child,graph):
        by_id={row['id']:row for row in graph['children']}
        required=set(child['depends_on']);pending=list(required)
        while pending:
            for dep in by_id[pending.pop()]['depends_on']:
                if dep not in required:required.add(dep);pending.append(dep)
        return sorted(required)

    def materialize(self,child,grant):
        g=self.state['authorizations'][grant];key=child['id']
        files={};modes={}
        for name in set(child['reads']+child['writes']+[child['plan']]):
            path=ops.safe(self.project,name)
            if path.is_file():
                files[name]=path.read_bytes();modes[name]=ops.stat.S_IMODE(path.stat().st_mode)
        dependencies={}
        for dep in self.dependencies(child,g['graph']):
            c=self.child(dep);p,context=c.context()
            if not c.valid('review',p,context):raise ValueError('dependency_review_not_current:'+dep)
            exports=next(x['interfaces'] for x in g['graph']['children'] if x['id']==dep)
            dependencies[dep]=dict(review=c.state['results']['review']['digest'],author=c.state['results']['implement']['provenance'],interfaces=exports)
            for interface in exports:
                name=interface['path']
                if name in child['reads']:
                    path=ops.safe(c.project,name);files[name]=path.read_bytes();modes[name]=ops.stat.S_IMODE(path.stat().st_mode)
        # Resolve configuration through the same Community routing mechanism.
        routing=ops.load('routing-path').resolve(HERE.parent,self.project)
        files['routing.json']=Path(routing).read_bytes()
        if (self.project/'.nightshift.toml').exists():files['.nightshift.toml']=(self.project/'.nightshift.toml').read_bytes()
        p=ops.plan(self.project,key)
        # Dependency interfaces/provenance are explicit versioned author inputs.
        architecture=p['inputs']['architecture']
        files[architecture]+=('\n\nDeclared package dependencies:\n'+__import__('json').dumps(dependencies,sort_keys=True)+'\n').encode()
        for name in files:modes.setdefault(name,0o644)
        hashes={name:__import__('hashlib').sha256(data).hexdigest() for name,data in files.items()}
        authority=ops.load('architecture').read(self.project)
        authority_digest=ops.digest(authority)
        row=self.state['children'].get(key)
        target=self.directory/'workspaces'/key
        if target.exists():self.safe_git(target)
        if row and row.get('status')!='materializing':
            c=self.child(key)
            if ops.digest(ops.load('architecture').read(target))!=row['authority']:
                raise ValueError('package_architecture_authority_changed')
            if any(a['status'] in ('pending','checkpoint') for a in c.state['attempts']):
                if hashes!=row['inputs'] or modes!=row['modes'] or authority_digest!=row['authority']:raise ValueError('pending_package_requires_reconciliation')
                return c
            changed={name for name in set(hashes)|set(row['inputs']) if hashes.get(name)!=row['inputs'].get(name) or modes.get(name)!=row['modes'].get(name)}
            if changed.intersection(child['writes']):raise ValueError('external_package_changes_require_adoption')
            if set(row['inputs'])-set(files):raise ValueError('package_input_removal_requires_reconciliation')
            update=row.get('update')
            if update and update!=dict(hashes=hashes,modes=modes):raise ValueError('package_update_requires_reconciliation')
            for name in changed:
                dest=ops.safe(target,name)
                actual=ops.sha(dest) if dest.exists() else None
                mode=ops.stat.S_IMODE(dest.stat().st_mode) if dest.exists() else None
                allowed={(row['inputs'].get(name),row['modes'].get(name))}
                if update:allowed.add((hashes[name],modes[name]))
                if (actual,mode) not in allowed:raise ValueError('package_operator_input_changed:'+name)
            if changed:
                row['update']=dict(hashes=hashes,modes=modes);self.save()
            for name in changed:
                dest=ops.safe(target,name);dest.parent.mkdir(parents=True,exist_ok=True)
                import tempfile
                fd,temporary=tempfile.mkstemp(prefix='.package-',dir=dest.parent)
                with os.fdopen(fd,'wb') as stream:stream.write(files[name]);stream.flush();os.fsync(stream.fileno())
                os.chmod(temporary,modes[name]);os.replace(temporary,dest)
        else:
            if row:
                if row['inputs']!=hashes or row['modes']!=modes or row['authority']!=authority_digest:raise ValueError('materialization_inputs_changed')
            else:
                if target.exists():raise ValueError('untracked_package_workspace')
                self.state['children'][key]=dict(workspace=str(target),inputs=hashes,modes=modes,dependencies=dependencies,authority=authority_digest,status='materializing')
                self.save()
            target.mkdir(parents=True,exist_ok=True)
            for path in target.rglob('*'):
                relative=path.relative_to(target)
                if relative.parts[0]=='.git':continue
                if path.is_symlink() or (path.is_file() and relative.as_posix() not in set(files)|{'.gitignore'}):
                    raise ValueError('unapproved_materialization_input')
            for name,data in files.items():
                dest=ops.safe(target,name)
                if dest.exists() and (dest.read_bytes()!=data or ops.stat.S_IMODE(dest.stat().st_mode)!=modes[name]):raise ValueError('materialization_content_changed:'+name)
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);dest.chmod(modes[name])
            ignore=ops.safe(target,'.gitignore')
            if ignore.exists() and ignore.read_text()!='__pycache__/\n':raise ValueError('materialization_ignore_changed')
            ignore.write_text('__pycache__/\n')
            if (target/'.git').is_symlink():raise ValueError('unsafe_package_git')
            subprocess.run(['git','init','-q',str(target)],check=True)
            subprocess.run(['git','-C',str(target),'add','.'],check=True)
            head=subprocess.run(['git','-C',str(target),'rev-parse','--verify','HEAD'],capture_output=True)
            if head.returncode:
                subprocess.run(['git','-C',str(target),'-c','core.hooksPath=/dev/null','-c','commit.gpgSign=false','-c','user.name=Nightshift','-c','user.email=nightshift@example.invalid','commit','-qm','Package input checkpoint'],check=True)
        # Project accepted records verbatim; this is not a new acceptance.
        authority_path=target/'.git/nightshift/architecture.json'
        if authority_path.resolve()!=authority_path.absolute():raise ValueError('unsafe_package_architecture')
        authority_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        ops.recovery.atomic(authority_path,authority)
        self.state['children'][key]=dict(workspace=str(target),inputs=hashes,modes=modes,dependencies=dependencies,authority=authority_digest,status='ready')
        self.save();return self.child(key)

    def enforce_usage(self,g):
        observed=self.usage(g['id'])
        if observed['unknown_calls']:raise ValueError('unknown_package_usage_requires_reconciliation')
        preparation=self.preparation.state['calls']
        preparation_used=dict(calls=len(preparation),seconds=sum(row['seconds'] for row in preparation.values()))
        if any(preparation_used[key]+sum(a['limit'][key] for a in g['allocations'].values())>g['graph']['aggregate'][key] for key in ('calls','seconds')):
            raise ValueError('parent_allowance_insufficient_after_preparation')
        if observed['calls']>g['graph']['aggregate']['calls'] or observed['execution_seconds']>g['graph']['aggregate']['seconds']:
            raise ValueError('parent_aggregate_exceeded')
        for key,allocation in g['allocations'].items():
            row=self.state['children'].get(key)
            if not row or row.get('status')=='materializing':continue
            calls=self.child(key).state['calls']
            if len(calls)>allocation['limit']['calls'] or sum(c['seconds'] for c in calls.values() if c['status']=='finished')>allocation['limit']['seconds']:
                raise ValueError('package_allocation_exceeded:'+key)

    def run(self,grant):
        # Hold preparation authority while spending its reserved child share.
        with self.lease(), self.preparation.lease():
            g=self.state['authorizations'].get(grant)
            if not g:raise ValueError('package_authorization_required')
            assessed=self.assess()
            if assessed['status']!='ready' or assessed['binding']!=g['binding']:raise ValueError('package_authorized_inputs_changed')
            try:self.enforce_usage(g)
            except ValueError as error:return self.block(g,str(error))
            for child in g['graph']['children']:
                key=child['id'];allocation=g['allocations'][key]
                if self.clock()>=g['deadline']:return self.block(g,'parent_deadline_exhausted')
                try:
                    c=self.materialize(child,grant)
                    p,context=c.context()
                    adopted=c.valid('adopt',p,context)
                    request='package-'+ops.digest([grant,key,self.state['children'][key]['inputs'],self.state['children'][key]['authority'],c.state['results'].get('adopt',{}).get('digest') if adopted else None])[:40]
                    if all(c.assess(op)['status']=='current' for op in ops.RECIPES['factory']):
                        result=dict(status='passed',reused=True)
                    else:
                        if request not in c.state['authorizations']:
                            recipe=['verify','review'] if adopted else ops.RECIPES['factory']
                            a=c.assess(recipe[0])
                            request=c.authorize(recipe,a['binding'],g['operator'],request,None if adopted else {'bounded_repair':True})['id']
                        # Always reconcile this restriction before dispatch, including
                        # a crash after child authorization but before this checkpoint.
                        with c.lease():
                            cg=c.state['authorizations'][request]
                            cg['deadline']=min(cg['deadline'],g['deadline'])
                            prior=[x for x in c.state['calls'].values() if x['grant']!=request]
                            remaining_calls=allocation['limit']['calls']-len(prior)
                            remaining_seconds=allocation['limit']['seconds']-sum(x['seconds'] if x['status']=='finished' else x['reserved_seconds'] for x in prior)
                            if remaining_calls<=0 or remaining_seconds<=0:raise ValueError('package_allocation_exhausted')
                            cg['aggregate'].update(calls=min(cg['aggregate']['calls'],remaining_calls),seconds=min(cg['aggregate']['seconds'],remaining_seconds))
                            c.save()
                        if adopted:
                            result=c.chain(request)
                            result['status']='passed' if all(row['status'] in ('passed','reused') for row in result['results']) else 'blocked'
                        else:result=ops.load('operation-supervisor').run(c,request)
                    if result['status']!='passed':return self.block(g,'package_failed:'+key,result)
                    p,context=c.context()
                    if not c.valid('review',p,context):return self.block(g,'package_review_not_current:'+key)
                    allocation.update(status='complete',review=c.state['results']['review']['digest'],source=context['source'],provenance=c.state['results']['implement']['provenance'])
                    self.save()
                except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
                    return self.block(g,str(error))
            # Integration is an independently verified/reviewed final package, with
            # all dependency provenance retained; child success alone cannot pass.
            if self.assess()['binding']!=g['binding']:return self.block(g,'package_inputs_changed_during_execution')
            for child in g['graph']['children']:
                c=self.child(child['id']);p,ctx=c.context()
                if not c.valid('review',p,ctx):return self.block(g,'stale_child_before_parent_acceptance:'+child['id'])
                if ops.load('architecture').read(c.project)!=ops.load('architecture').read(self.project):
                    return self.block(g,'stale_package_architecture:'+child['id'])
                for dep,evidence in self.state['children'][child['id']]['dependencies'].items():
                    if self.child(dep).state['results']['review']['digest']!=evidence['review']:
                        return self.block(g,'stale_dependency_before_parent_acceptance:'+child['id']+':'+dep)
            try:self.enforce_usage(g)
            except ValueError as error:return self.block(g,str(error))
            integration=next(c for c in g['graph']['children'] if c['integration'])
            g.update(status='pending_manual_acceptance',integration=integration['id']);self.save()
            return dict(status=g['status'],grant=g,usage=self.usage(grant))

    def block(self,g,reason,result=None):
        g.update(status='blocked',reason=reason,result=result);self.save()
        return dict(status='blocked',reason=reason,grant=g,usage=self.usage(g['id']))


def api(project,body):
    if not isinstance(body,dict) or set(body)-{'task','action','binding','operator','request','grant'}:
        raise ValueError('invalid_package_request')
    c=Packages(project,body['task']);action=body['action']
    if action=='assess':return c.assess()
    if action=='view':
        try:assessment=c.assess()
        except (OSError,ValueError,KeyError,TypeError) as error:assessment=dict(status='blocked',reason=str(error))
        return dict(assessment=assessment,state=c.state,usage={key:c.usage(key) for key in c.state['authorizations']})
    if action=='prepare':return c.prepare(body['grant'])
    if action=='authorize':return c.authorize(body['binding'],body['operator'],body['request'])
    if action=='run':return c.run(body['grant'])
    raise ValueError('unknown_package_action')
