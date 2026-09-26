#!/usr/bin/env python3
"""Bounded cancellation intents and receipt-only operation reconciliation."""
from contextlib import contextmanager
import fcntl
import os
import re
from pathlib import Path


def identity(c,g):
    return c.load_digest(dict(worktree=str(c.project),task=c.task,grant=g['id'],authority=g['request_digest']))


def location(c,grant):
    return c.directory/('cancel-'+c.load_digest(grant)+'.json')


def intent(c,grant):
    path=location(c,grant)
    if not path.exists():return None
    row=c.recovery_read(path)
    g=c.state['authorizations'].get(grant)
    if not g or row.get('version')!=1 or row.get('payload')!=dict(grant=grant,binding=identity(c,g),operator=g['operator']):raise ValueError('invalid_cancellation_receipt')
    return row


def parents(c,grant):
    authority=c.state['authorizations'][grant]
    return authority.get('parent_cancellations',[])+([authority['parent_cancellation']] if authority.get('parent_cancellation') else [])


def paths(c,grant):
    return [location(c,grant)]+[Path(parent['path']) for parent in parents(c,grant)]


def effective_intent(c,grant):
    own=intent(c,grant)
    if own:return own
    for parent in parents(c,grant):
        if Path(parent['path']).exists():
            value=c.recovery_read(Path(parent['path']))
            if value.get('version')!=1 or value.get('payload',{}).get('binding')!=parent['binding']:raise ValueError('invalid_parent_cancellation_receipt')
            return value
    return None


def check(c,grant):
    if effective_intent(c,grant):raise ValueError('operation_cancelled:inspect_retained_receipts')


@contextmanager
def integration_guard(c,grant):
    locks=[]
    try:
        for path in sorted(set(paths(c,grant)),key=str):
            fd=os.open(str(path)+'.lock',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            lock=os.fdopen(fd,'w');locks.append(lock);fcntl.flock(lock,fcntl.LOCK_EX)
        c.cancellation_check(grant)
        yield
    finally:
        for lock in reversed(locks):lock.close()


def cancel(c,grant,binding,operator,request):
    if os.environ.get('NIGHTSHIFT_ROLE_CHILD')=='1':raise ValueError('worker_cannot_control_operations')
    if not isinstance(request,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',request):raise ValueError('invalid_request_id')
    c.reload();g=c.state['authorizations'].get(grant)
    if not g or g['operator']!=operator:raise ValueError('cancellation_not_authorized')
    if identity(c,g)!=binding:raise ValueError('stale_cancellation_authority')
    path=location(c,grant)
    fd=os.open(str(path)+'.lock',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        payload=dict(grant=grant,binding=binding,operator=operator)
        if path.exists():
            previous=c.recovery_read(path)
            if previous['payload']!=payload:raise ValueError('cancellation_request_conflict')
            return previous
        receipt=dict(version=1,status='cancellation_requested',payload=payload,request=request,created=c.clock(),
                     meaning='Stop owned local execution and future dispatch. Remote effects and usage require retained evidence.')
        c.recovery_write(path,receipt);return receipt


def assessment(c,attempt):
    outputs={}
    for suffix in ('.worker.json','.worker.execution.json','.checkpoint.json'):
        path=c.directory/(attempt['request']+suffix)
        if path.exists():outputs[path.name]=c.file_hash(path)
    binding=c.load_digest(dict(task=c.task,project=str(c.project),attempt=attempt,outputs=outputs))
    return dict(request=attempt['request'],grant=attempt['grant'],status=attempt['status'],binding=binding,outputs=outputs,
                actions=['finalize','preserve'] if attempt['status'] in ('pending','checkpoint') else ['inspect'],
                remote_execution='unknown' if attempt['status']=='pending' else 'see_retained_receipt')


def reconcile(c,request,binding,operator,action):
    if action not in ('finalize','preserve'):raise ValueError('invalid_reconciliation_action')
    with c.lease():
        attempt=next((a for a in c.state['attempts'] if a['request']==request),None)
        if not attempt:raise ValueError('reconciliation_request_missing')
        grant=c.state['authorizations'][attempt['grant']]
        if grant['operator']!=operator:raise ValueError('reconciliation_not_authorized')
        key=c.load_digest(dict(request=request,binding=binding,operator=operator,action=action))
        old=c.state.get('reconciliations',{}).get(key)
        if old:
            if action=='finalize':
                p,context=c.context()
                if not c.valid(attempt['operation'],p,context):raise ValueError('stale_reconciled_result')
            return old
        if assessment(c,attempt)['binding']!=binding:raise ValueError('stale_reconciliation_evidence')
        if attempt['status'] not in ('pending','checkpoint'):raise ValueError('reconciliation_not_pending')
        if action=='preserve':
            if not effective_intent(c,attempt['grant']):raise ValueError('cancel_before_preserving_unknown_execution')
            attempt.update(status='cancelled_unknown',reason='explicit_preservation:remote_effect_and_usage_not_resolved')
            result=dict(status='cancelled_unknown',request=request,unknown_usage_preserved=True)
        else:
            c.reconciling=True
            try:
                if attempt['status']=='checkpoint':result=c.finalize(attempt)
                elif (c.directory/(request+'.worker.execution.json')).exists():result=c.recover_worker(attempt)
                else:raise ValueError('unknown_execution:no_controller_completion_receipt')
            finally:c.reconciling=False
        receipt=dict(action=action,operator=operator,binding=binding,result=result,provider_calls=0)
        c.state.setdefault('reconciliations',{})[key]=receipt;c.save();return receipt
