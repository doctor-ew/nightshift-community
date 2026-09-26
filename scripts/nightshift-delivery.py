#!/usr/bin/env python3
"""Reviewed delivery transitions with durable local and remote effect receipts."""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
from urllib.parse import quote

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('delivery_operations',HERE/'nightshift-operations.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ACTIONS=('deliver','commit','branch','pr','ci','repair','merge')
OID=re.compile(r'[0-9a-f]{40,64}')


def git(project,*args,env=None,input=None):
    return subprocess.run(['git','-C',str(project),*args],env=env,input=input,capture_output=True,text=True,check=True,timeout=20).stdout.strip()


def profile(c):
    value=m.read(m.safe(c.project,'docs/'+c.task+'/delivery.json'))
    m.exact(value,'version remote remote_url repository branch base files checks endpoint merge_policy commit')
    if type(value['version']) is not int or value['version']!=1:raise ValueError('unsupported_delivery_version')
    if not re.fullmatch(r'[A-Za-z0-9_-]+',value['remote']) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',value['repository']):raise ValueError('invalid_delivery_repository')
    for key in ('branch','base'):
        git(c.project,'check-ref-format','refs/heads/'+value[key])
        if value[key].startswith('-'):raise ValueError('invalid_delivery_branch')
    if value['branch'] in ('main','master',value['base']):raise ValueError('delivery_requires_topic_branch')
    if value['endpoint'] not in ('branch','pr','ci') or value['merge_policy'] not in ('disabled','protected-squash'):raise ValueError('invalid_delivery_endpoint')
    destinations=git(c.project,'remote','get-url','--push','--all',value['remote']).splitlines()
    if destinations!=[value['remote_url']] or git(c.project,'ls-remote','--get-url',value['remote_url'])!=value['remote_url']:raise ValueError('delivery_remote_identity_changed')
    p=m.plan(c.project,c.task);allowed=set(p['scope'])|{p['inputs'][k] for k in ('request','spec','scenarios')}
    if not isinstance(value['files'],list) or not value['files'] or len(value['files'])!=len(set(value['files'])):raise ValueError('invalid_delivery_files')
    if not set(p['scope']).issubset(value['files']):raise ValueError('delivery_files_must_include_reviewed_source_scope')
    for name in value['files']:
        m.safe(c.project,name)
        if name in ('docs/'+c.task+'/delivery.json',str(m.plan_path(c.project,c.task).relative_to(c.project))):raise ValueError('private_delivery_control_path')
        if name not in allowed or any(part in ('.git','.nightshift','.codex','.claude','.agents') or part.startswith(('.env','.nightshift')) for part in Path(name).parts):raise ValueError('private_or_unreviewed_delivery_path')
    if not isinstance(value['checks'],list):raise ValueError('invalid_required_checks')
    for check in value['checks']:
        m.exact(check,'name app_id')
        if not m.bounded_text(check['name']) or type(check['app_id']) is not int or check['app_id']<=0:raise ValueError('invalid_required_check_identity')
    if len(value['checks'])!=len({m.digest(x) for x in value['checks']}):raise ValueError('duplicate_required_checks')
    if value['endpoint']=='ci' and not value['checks']:raise ValueError('nonempty_required_checks_required')
    m.exact(value['commit'],'message author_name author_email')
    if any(not m.bounded_text(x) or '\0' in x for x in value['commit'].values()) or '\n' in value['commit']['author_email'] or '\n' in value['commit']['author_name']:raise ValueError('invalid_commit_identity')
    return value


class Host:
    """Bounded Git/GitHub transport; tests inject a disposable host instead."""
    def __init__(self,delivery):self.d=delivery
    def call(self,argv,json_output=False,allowed=(0,),observation=False):
        d=self.d;c=d.c;grant=getattr(d,'active_grant',None)
        if getattr(d,'read_only',False):
            if not observation:raise ValueError('reconciliation_cannot_dispatch_remote_mutation')
            grant=None
        seconds=min(30,c.state['authorizations'][grant]['deadline']-c.clock()) if grant else 30
        if seconds<=0:raise ValueError('delivery_deadline')
        output=c.directory/('delivery-transport-'+uuid.uuid4().hex+'.log')
        runner=m.load('controller-recovery');env=runner.clean_environment()
        code=runner.bounded(argv,c.project,env,seconds,output,cancellation=m.load('operation-reconciliation').paths(c,grant) if grant else None,ownership=output.with_suffix('.ownership.json'))
        if code not in allowed:raise ValueError('delivery_transport_exit:'+str(code)+':'+output.name)
        if output.stat().st_size>2000000:raise ValueError('delivery_host_output_too_large:'+output.name)
        text=output.read_text()
        return json.loads(text) if json_output else text.strip()
    def refs(self,p):
        text=self.call(['git','ls-remote',p['remote_url'],'refs/heads/'+p['branch'],'refs/heads/'+p['base']],observation=True);rows={}
        for line in text.splitlines():
            oid,name=line.split();rows[name]=oid
        return dict(head=rows.get('refs/heads/'+p['branch']),base=rows.get('refs/heads/'+p['base']))
    def push(self,p,head,old):
        # The expected-old lease only narrows an already verified fast-forward.
        return self.call(['git','push','--force-with-lease=refs/heads/'+p['branch']+':'+(old or ''),p['remote_url'],head+':refs/heads/'+p['branch']])
    def prs(self,p):return self.call(['gh','pr','list','--repo',p['repository'],'--state','all','--head',p['branch'],'--base',p['base'],'--json','number,headRefName,headRefOid,baseRefName,baseRefOid,body,state,url,headRepository'],True,observation=True)
    def create(self,p,body):
        path=self.d.c.directory/('delivery-pr-'+m.digest(body)+'.md');m.recovery.atomic(path.with_suffix('.json'),{'body':body});path.write_text(body)
        return self.call(['gh','pr','create','--repo',p['repository'],'--head',p['branch'],'--base',p['base'],'--title',p['commit']['message'].splitlines()[0],'--body-file',str(path)])
    def ci(self,p,number):
        pr=self.call(['gh','api','repos/'+p['repository']+'/pulls/'+str(number)],True,observation=True)
        merge=pr.get('merge_commit_sha')
        if not merge:return dict(head=pr['head']['sha'],base=pr['base']['sha'],merge=None,parents=[],checks=[],state=pr['state'],merged=pr.get('merged',False),protected=False)
        commit=self.call(['gh','api','repos/'+p['repository']+'/git/commits/'+merge],True,observation=True)
        checks=self.call(['gh','api','repos/'+p['repository']+'/commits/'+merge+'/check-runs'],True,observation=True)
        # A failed protection query cannot be substituted with an assumed policy.
        branch={}
        if getattr(self.d,'active_action',None)=='merge':branch=self.call(['gh','api','repos/'+p['repository']+'/branches/'+quote(p['base'],safe='')+'/protection'],True,observation=True)
        rows=[dict(name=x['name'],head=x['head_sha'],status=x['status'],conclusion=x.get('conclusion'),id=x['id'],app_id=x['app']['id'],output=x.get('output',{})) for x in checks['check_runs']]
        if checks['total_count']!=len(rows):raise ValueError('ci_check_pagination_requires_adapter')
        return dict(head=pr['head']['sha'],base=pr['base']['sha'],merge=merge,parents=[x['sha'] for x in commit['parents']],checks=rows,state=pr['state'],merged=pr.get('merged',False),protected=branch.get('required_status_checks',{}).get('strict') is True)
    def merge(self,p,number,head):return self.call(['gh','pr','merge',str(number),'--repo',p['repository'],'--squash','--match-head-commit',head])


class Delivery:
    def __init__(self,controller,host=None):
        self.c=controller;self.host=host or Host(self)
    def local_head(self):return git(self.c.project,'rev-parse','HEAD')
    def local_branch(self):return git(self.c.project,'symbolic-ref','--short','HEAD')
    def state(self):return self.c.state.setdefault('delivery',dict(version=1,grants={},attempts={},ci_failures=[]))
    def snapshot(self,p,require_acceptance=True):
        accepted=self.c.assess('accept')
        if require_acceptance and accepted['status']!='current':raise ValueError('delivery_requires_current_acceptance')
        files={name:dict(sha256=m.sha(m.safe(self.c.project,name)),mode=m.safe(self.c.project,name).stat().st_mode&0o777) if m.safe(self.c.project,name).exists() else None for name in p['files']}
        return dict(profile=p,accepted=accepted['result']['digest'],files=files,policy=self.c.policy_binding(m.plan(self.c.project,self.c.task)),delivery_sha256=m.sha(Path(__file__)),repair_sha256=m.sha(HERE/'nightshift-delivery-repair.py'),compose_sha256=m.sha(HERE/'nightshift-delivery-compose.py'))
    def selected_pr(self,p,head=None):
        marker='<!-- nightshift-delivery:'+m.digest([p['repository'],p['branch'],p['base'],self.c.task])+' -->'
        rows=self.host.prs(p)
        if len(rows)>1:raise ValueError('ambiguous_remote_pull_requests')
        if rows:
            row=rows[0]
            if row.get('headRepository',{}).get('nameWithOwner')!=p['repository'] or row['headRefName']!=p['branch'] or row['baseRefName']!=p['base'] or marker not in row['body'] or (head and row['headRefOid']!=head):raise ValueError('remote_pr_identity_mismatch')
            return row,marker
        return None,marker
    def assess(self,action):
        if action not in ACTIONS:raise ValueError('unknown_delivery_action')
        p=profile(self.c);snapshot=self.snapshot(p);head=git(self.c.project,'rev-parse','HEAD')
        if git(self.c.project,'symbolic-ref','--short','HEAD')!=p['branch']:raise ValueError('delivery_branch_mismatch')
        refs=self.host.refs(p)
        if not refs['base']:raise ValueError('delivery_base_missing')
        if refs['head'] and refs['head']!=head:
            git(self.c.project,'cat-file','-e',refs['head']+'^{commit}')
            git(self.c.project,'merge-base','--is-ancestor',refs['head'],head)
        binding=m.digest(dict(action=action,snapshot=snapshot,head=head,refs=refs))
        blockers=[]
        allowed={'branch':{'deliver','commit','branch'},'pr':{'deliver','commit','branch','pr'},'ci':set(ACTIONS)}[p['endpoint']]
        if action not in allowed:blockers.append('outside_authorized_delivery_endpoint')
        if action in ('pr','ci','merge') and refs['head']!=head:blockers.append('publish_exact_branch_first')
        if action=='merge' and p['merge_policy']!='protected-squash':blockers.append('merge_not_enabled')
        return dict(action=action,binding=binding,status='blocked' if blockers else 'ready',blockers=blockers,snapshot=snapshot,head=head,refs=refs)
    def authorize(self,action,binding,operator,request,delegation=None,repair_grant=None):
        c=self.c
        if not m.bounded_text(operator) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',request):raise ValueError('operator_and_request_required')
        with c.lease():
            state=self.state();payload=dict(action=action,binding=binding,operator=operator)
            repair=None
            if repair_grant is not None:
                if action!='deliver' or not isinstance(repair_grant,str):raise ValueError('bound_repair_requires_ci_delivery')
                child=c.state['authorizations'].get(repair_grant)
                if not child:raise ValueError('existing_bounded_factory_authority_required')
                repair=dict(grant=repair_grant,identity=m.load('operation-reconciliation').identity(c,child))
                payload['repair_authority']=repair
            if request in state['grants']:
                g=state['grants'][request]
                if g['request_digest']!=m.digest(payload):raise ValueError('delivery_request_conflict')
                if delegation is not None:
                    c.delegate(c.state['authorizations'][request],delegation);c.delegate(g,delegation);c.save()
                return g
            assessed=self.assess(action)
            if assessed['binding']!=binding or assessed['status']!='ready':raise ValueError('stale_or_blocked_delivery_assessment')
            if request in c.state['authorizations']:raise ValueError('operation_request_conflict')
            plan=m.plan(c.project,c.task);created=c.clock();deadline=created+plan['aggregate']['wall_seconds']
            cycle=m.digest(dict(profile=assessed['snapshot']['profile'],files=assessed['snapshot']['files']))
            prior=[g['deadline'] for g in state['grants'].values() if m.digest(dict(profile=g['assessment']['snapshot']['profile'],files=g['assessment']['snapshot']['files']))==cycle]
            if prior:deadline=min(deadline,*prior)
            if repair is not None:
                if deadline<=created:raise ValueError('delivery_deadline')
                if assessed['snapshot']['profile']['endpoint']!='ci':raise ValueError('bound_repair_requires_ci_delivery')
                if child['operations']!=m.RECIPES['factory'] or not (child.get('attestation') or {}).get('bounded_repair') or child['operator']!=operator:raise ValueError('existing_bounded_factory_authority_required')
                c.cancellation_check(repair_grant)
                if c.clock()>=child['deadline'] or child['policy_binding']!=c.policy_binding(plan) or child['plan_sha256']!=m.sha(m.plan_path(c.project,c.task)):raise ValueError('repair_authority_changed_or_expired')
                if c.corpus()!=child['baseline'] or c.modes()!=child['baseline_modes']:raise ValueError('external_changes_require_adoption')
                deadline=min(deadline,child['deadline'])
            grant=dict(id=request,version=1,operator=operator,request_digest=m.digest(payload),operations=[],created=created,deadline=deadline,aggregate=dict(calls=0,seconds=0,wall_seconds=plan['aggregate']['wall_seconds']),limits={},statuses={},attestation={'delivery_action':action})
            c.delegate(grant,delegation)
            grant['cycle']=cycle
            grant['cancellation_binding']=m.load('operation-reconciliation').identity(c,grant)
            if repair is not None:
                grant['repair_authority']=repair
                reconciliation=m.load('operation-reconciliation')
                c.delegate(child,dict(parent_cancellation=dict(path=str(reconciliation.location(c,request)),binding=grant['cancellation_binding']),deadline=deadline))
            c.state['authorizations'][request]=grant
            state['grants'][request]=dict(grant,assessment=assessed);c.save();return state['grants'][request]
    def ensure_current(self,g,allow_commit=False,observing=False,existing_repair=False):
        p=profile(self.c)
        if self.snapshot(p,not existing_repair)!=g['assessment']['snapshot']:raise ValueError('delivery_evidence_changed')
        if not observing and self.c.clock()>=g['deadline']:raise ValueError('delivery_deadline')
        if git(self.c.project,'symbolic-ref','--short','HEAD')!=p['branch']:raise ValueError('delivery_branch_moved')
        if not allow_commit and git(self.c.project,'rev-parse','HEAD')!=g['assessment']['head']:raise ValueError('delivery_head_moved')
        return p
    def commit(self,g,a,reconcile=False):
        c=self.c;p=self.ensure_current(g,True,reconcile);old=g['assessment']['head']
        if reconcile:
            if a.get('commit') and self.local_head()==a['commit']:
                return dict(status='commit_prepared',head=a['commit'],tree=a['intent']['tree'],files=p['files'],operator_index='preserved')
            raise ValueError('delivery_commit_effect_absent_or_unknown:explicit_new_action_required')
        if 'intent' not in a:
            index=c.directory/('delivery-index-'+m.digest(g['id']));env=dict(os.environ,GIT_INDEX_FILE=str(index))
            git(c.project,'read-tree',old,env=env)
            for name in p['files']:
                source=m.safe(c.project,name)
                if source.exists():
                    blob=git(c.project,'hash-object','-w','--no-filters','--',name)
                    mode='100755' if source.stat().st_mode&0o111 else '100644'
                    git(c.project,'update-index','--add','--cacheinfo',mode,blob,name,env=env)
                else:git(c.project,'update-index','--force-remove','--',name,env=env)
            tree=git(c.project,'write-tree',env=env)
            changed=set(git(c.project,'diff-tree','--no-commit-id','--name-only','-r',old,tree).splitlines())
            if changed-set(p['files']):raise ValueError('delivery_tree_exceeds_reviewed_files')
            a['intent']=dict(parent=old,tree=tree,message=p['commit']['message'],identity=p['commit'],time=str(int(c.clock()))+' +0000');c.save()
        intent=a['intent'];identity=intent['identity'];env=dict(os.environ,GIT_AUTHOR_NAME=identity['author_name'],GIT_AUTHOR_EMAIL=identity['author_email'],GIT_COMMITTER_NAME=identity['author_name'],GIT_COMMITTER_EMAIL=identity['author_email'],GIT_AUTHOR_DATE=intent['time'],GIT_COMMITTER_DATE=intent['time'])
        head=old if intent['tree']==git(c.project,'rev-parse',old+'^{tree}') else git(c.project,'commit-tree',intent['tree'],'-p',old,env=env,input=intent['message']+'\n')
        a['commit']=head;c.save()
        result=dict(status='commit_prepared',head=head,tree=intent['tree'],files=p['files'],operator_index='preserved')
        if git(c.project,'rev-parse','HEAD')==head:return result
        with m.load('operation-reconciliation').integration_guard(c,g['id']):
            self.ensure_current(g,True);current=git(c.project,'rev-parse','HEAD')
            if current!=head:
                if current!=old:raise ValueError('delivery_commit_cas_conflict')
                git(c.project,'update-ref','refs/heads/'+p['branch'],head,old)
        return result
    def require_commit(self,p,head):
        # Compare worktree bytes to the reviewed commit without consulting the real index.
        reviewed=set(p['files'])|{row['argv'][1] for row in m.plan(self.c.project,self.c.task)['checks']}
        for name in sorted(reviewed):
            current=m.safe(self.c.project,name)
            try:blob=git(self.c.project,'rev-parse',head+':'+name)
            except subprocess.CalledProcessError:
                if current.exists():raise ValueError('reviewed_file_not_committed')
                continue
            if not current.exists() or git(self.c.project,'hash-object','--no-filters','--',name)!=blob:raise ValueError('reviewed_file_not_committed')
            mode=git(self.c.project,'ls-tree',head,'--',name).split()[0]
            if mode!=('100755' if current.stat().st_mode&0o111 else '100644'):raise ValueError('reviewed_file_mode_not_committed')
        completed=[a for a in self.state()['attempts'].values() if a.get('result',{}).get('head')==head and a.get('result',{}).get('status')=='commit_prepared']
        if not completed:raise ValueError('reviewed_commit_receipt_required')
    def require_history(self,p,head,base):
        if not isinstance(base,str) or not OID.fullmatch(base):raise ValueError('delivery_base_revision_invalid')
        try:
            git(self.c.project,'cat-file','-e',base+'^{commit}')
            git(self.c.project,'merge-base','--is-ancestor',base,head)
        except subprocess.SubprocessError:raise ValueError('delivery_base_missing_or_not_ancestor') from None
        revisions=git(self.c.project,'rev-list','--max-count=1001',base+'..'+head).splitlines()
        if len(revisions)>1000:raise ValueError('delivery_history_exceeds_review_bound')
        state=self.state();allowed=set(p['files'])
        for revision in revisions:
            if not getattr(self,'read_only',False):
                self.c.cancellation_check(self.active_grant)
                if self.c.clock()>=self.c.state['authorizations'][self.active_grant]['deadline']:raise ValueError('delivery_deadline')
            tree=git(self.c.project,'rev-parse',revision+'^{tree}')
            receipts=[row for row in state['attempts'].values() if row.get('action')=='commit' and row.get('status')=='complete' and row.get('result',{}).get('head')==revision and row['result'].get('tree')==tree]
            if not any(all(state['grants'][row['grant']]['assessment']['snapshot']['profile'][key]==p[key] for key in ('remote_url','repository','branch','base')) for row in receipts):
                raise ValueError('delivery_unreviewed_history_requires_retained_commit_receipt:'+revision)
            # Name/status begins with a status token; NUL delimiters preserve unusual path bytes.
            entries=git(self.c.project,'diff-tree','--root','--no-commit-id','--no-renames','--name-status','-z','-r','-m',revision).split('\0')
            if entries and entries[-1]=='':entries.pop()
            if len(entries)%2 or set(entries[1::2])-allowed:raise ValueError('delivery_history_exceeds_reviewed_files:'+revision)

    def execute(self,grant,request,reconcile=False,repair_grant=None):
        c=self.c
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',request):raise ValueError('invalid_delivery_request')
        c.reload()
        action=self.state()['grants'][grant]['assessment']['action']
        if repair_grant is not None and action!='repair':raise ValueError('repair_grant_requires_repair_action')
        if action=='deliver':return m.load('delivery-compose').run(self,grant,request,m)
        with c.lease():
            state=self.state();g=state['grants'][grant];action=g['assessment']['action'];self.active_grant=grant;self.read_only=reconcile;self.repair_grant=repair_grant;self.active_action=action
            a=state['attempts'].get(request)
            if a and a['grant']!=grant:raise ValueError('delivery_request_conflict')
            if a and a['status']=='complete':
                self.read_only=True
                self.ensure_current(g,action=='commit',True)
                if action=='commit':
                    if git(c.project,'rev-parse','HEAD')!=a['result']['head']:raise ValueError('delivery_head_moved')
                    result=a['result']
                else:result=self.remote(g,a,action,True)
                return dict(result,reused=True)
            if a and not reconcile:raise ValueError('delivery_effect_requires_reconciliation')
            if not a:a=dict(grant=grant,action=action,status='pending',created=c.clock());state['attempts'][request]=a;c.save()
            if not reconcile:c.cancellation_check(grant)
            try:
                if action=='commit':result=self.commit(g,a,reconcile)
                else:result=self.remote(g,a,action,reconcile)
                a.update(status='complete',result=result);c.save();return result
            except BaseException as error:
                a.update(status='unknown' if a.get('intent') else 'blocked',reason=type(error).__name__+':'+str(error));c.save();raise
    def observe_ci(self,p,pr,head,refs):
        c=self.c
        observed=self.host.ci(p,pr['number'])
        if observed['head']!=head or observed['base']!=refs['base'] or self.host.refs(p)!=refs:raise ValueError('ci_revision_changed')
        receipt=c.directory/('delivery-ci-'+m.digest(observed)+'.json');m.recovery.atomic(receipt,observed)
        checks=observed['checks'];identities=[(row['name'],row['app_id']) for row in checks]
        required_ids=[(row['name'],row['app_id']) for row in p['checks']]
        valid=observed['merge'] and set(observed['parents'])=={head,refs['base']} and p['checks'] and all(identities.count(identity)==1 for identity in required_ids)
        required=[row for row in checks if (row['name'],row['app_id']) in required_ids]
        valid=valid and observed['state']=='open' and not observed['merged']
        passed=bool(valid and all(row['head']==observed['merge'] and row['status']=='completed' and row['conclusion']=='success' for row in required))
        terminal=bool(valid and all(row['head']==observed['merge'] and row['status']=='completed' and row['conclusion'] in ('success','failure') for row in required))
        failed=bool(terminal and any(row['conclusion']=='failure' for row in required))
        result=dict(status='ci_passed' if passed else 'ci_failed' if failed else 'ci_unknown',head=head,base=refs['base'],number=pr['number'],merge=observed['merge'],evidence={receipt.name:m.sha(receipt)})
        return result,observed

    def remote(self,g,a,action,reconcile):
        c=self.c
        existing=c.state.get('delivery_repair',{})
        duplicate_repair=action=='repair' and existing.get('grant')==self.repair_grant
        p=self.ensure_current(g,observing=reconcile,existing_repair=duplicate_repair);head=g['assessment']['head'];self.require_commit(p,head)
        refs=self.host.refs(p);expected=g['assessment']['refs']
        if action=='merge' and reconcile and a.get('intent'):
            pr,_=self.selected_pr(p,head)
            if pr:
                observed=self.host.ci(p,pr['number'])
                if observed['merged'] and observed['head']==head:return dict(status='integrated',head=head,base=expected['base'],number=pr['number'],observed_base=observed['base'])
        if refs['base']!=expected['base']:raise ValueError('delivery_base_moved')
        self.require_history(p,head,refs['base'])
        if action=='branch':
            if refs['head']==head:return dict(status='branch_published',head=head,base=refs['base'])
            if refs['head']!=expected['head']:raise ValueError('delivery_remote_head_moved')
            if reconcile:raise ValueError('delivery_effect_absent_requires_new_explicit_request')
            a['intent']=dict(kind='push',old=refs['head'],head=head,base=refs['base']);c.save();c.cancellation_check(g['id'])
            self.host.push(p,head,refs['head'])
            if self.host.refs(p)!=dict(head=head,base=refs['base']):raise ValueError('delivery_push_unconfirmed')
            return dict(status='branch_published',head=head,base=refs['base'])
        if refs['head']!=head:raise ValueError('delivery_remote_head_moved')
        pr,marker=self.selected_pr(p,head)
        if action=='pr':
            if not pr:
                if reconcile:raise ValueError('delivery_pr_effect_unknown')
                a['intent']=dict(kind='pr',head=head,base=refs['base'],marker=marker);c.save();c.cancellation_check(g['id'])
                self.host.create(p,marker+'\n\nReviewed delivery for '+c.task+'.\n');pr,_=self.selected_pr(p,head)
            if not pr or pr['state']!='OPEN' or pr['baseRefOid']!=refs['base']:raise ValueError('delivery_pr_not_current_open')
            return dict(status='pr_open',head=head,base=refs['base'],number=pr['number'],url=pr['url'])
        if not pr:raise ValueError('delivery_pr_required')
        result,observed=self.observe_ci(p,pr,head,refs)
        if action=='ci':return result
        if action=='repair':
            if reconcile:raise ValueError('reconcile_existing_repair_request')
            record=m.load('delivery-repair').register(self,g,a,result,observed,self.repair_grant,m)
            return dict(result,status='repair_prepared',repair=record)
        if action=='merge':
            if observed['merged']:return dict(result,status='integrated')
            if result['status']!='ci_passed' or not observed['protected'] or p['merge_policy']!='protected-squash':raise ValueError('merge_policy_or_checks_blocked')
            if reconcile and a.get('intent'):raise ValueError('merge_effect_unknown_no_automatic_retry')
            a['intent']=dict(kind='merge',head=head,base=refs['base'],number=pr['number']);c.save();c.cancellation_check(g['id'])
            self.host.merge(p,pr['number'],head)
            observed=self.host.ci(p,pr['number'])
            confirmed,_=self.selected_pr(p,head)
            if observed['head']!=head or not confirmed or confirmed['number']!=pr['number']:raise ValueError('merge_revision_or_identity_changed')
            return dict(result,status='integrated' if observed['merged'] and observed['state']=='closed' else 'merge_pending')
        raise ValueError('delivery_repair_requires_existing_factory_authority')
    def profile_current_for_repair(self,g):
        c=self.c;snapshot=g['assessment']['snapshot']
        return profile(c)==snapshot['profile'] and c.policy_binding(m.plan(c.project,c.task))==snapshot['policy'] and m.sha(Path(__file__))==snapshot['delivery_sha256'] and m.sha(HERE/'nightshift-delivery-repair.py')==snapshot['repair_sha256'] and m.sha(HERE/'nightshift-delivery-compose.py')==snapshot['compose_sha256']
    def resume_repair(self,grant,request):
        c=self.c
        with c.lease():
            state=self.state();g=state['grants'][grant];attempt=state['attempts'].get(request) or state.get('compositions',{}).get(request)
            if not attempt or attempt['grant']!=grant or not attempt.get('repair'):raise ValueError('retained_ci_repair_required')
            repair=attempt['repair'];c.cancellation_check(grant)
            if not self.profile_current_for_repair(g):raise ValueError('delivery_policy_changed')
            m.load('delivery-repair').before_dispatch(self,g,attempt,m)
        result=m.load('operation-supervisor').run(c,repair['grant'],repair['trigger'])
        with c.lease():
            retained=self.state()['attempts'].get(request) or self.state().get('compositions',{}).get(request)
            retained['repair_result']=dict(status=result['status'],next_action='fresh_acceptance_and_delivery_assessment' if result['status']=='passed' else 'inspect_retained_repair_evidence')
            c.save()
        return dict(status='needs_acceptance' if result['status']=='passed' else 'blocked',repair=result)

    def view(self):
        c=self.c;c.reload();state=self.state()
        return dict(version=1,state=state,cancellations={key:dict(binding=value['cancellation_binding'],intent=m.load('operation-reconciliation').intent(c,key)) for key,value in state['grants'].items()},endpoints=['commit_prepared','branch_published','pr_open','ci_passed','integrated'])


def api(project,body):
    c=m.Operations(project,body['task']);d=Delivery(c);action=body['action'].removeprefix('delivery-')
    if action=='view':return d.view()
    if action=='assess':return d.assess(body['operation'])
    if action=='authorize':
        if body.get('attestation') is not None:m.exact(body['attestation'],'repair_grant')
        return d.authorize(body['operation'],body['binding'],body['operator'],body['request'],repair_grant=(body.get('attestation') or {}).get('repair_grant'))
    if action in ('run','reconcile'):
        if body.get('attestation') is not None:m.exact(body['attestation'],'repair_grant')
        return d.execute(body['grant'],body['request'],action=='reconcile',(body.get('attestation') or {}).get('repair_grant'))
    if action=='repair':return d.resume_repair(body['grant'],body['request'])
    raise ValueError('unknown_delivery_action')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('view','assess','authorize','run','reconcile','repair'));parser.add_argument('task');parser.add_argument('operation',nargs='?',choices=ACTIONS)
    parser.add_argument('--project',default=os.getcwd())
    parser.add_argument('--attestation',type=json.loads)
    for key in ('binding','operator','request','grant'):parser.add_argument('--'+key)
    args=vars(parser.parse_args());project=args.pop('project');args={k:v for k,v in args.items() if v is not None}
    try:print(json.dumps(api(project,args)));return 0
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:print(json.dumps(dict(status='blocked',reason=str(error))));return 1


if __name__=='__main__':raise SystemExit(main())
