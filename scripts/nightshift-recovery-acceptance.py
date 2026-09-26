#!/usr/bin/env python3
"""Explicit, no-spend acceptance of current retained recovery evidence."""
import json
import os
from pathlib import Path
import re
import time
import tempfile


def payload(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:
        raise ValueError('recovery_acceptance_evidence_invalid')
    with path.open('rb') as stream:raw=stream.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('recovery_acceptance_evidence_invalid')
    return raw


def sha(c,path):
    return c.hashlib.sha256(payload(path)).hexdigest()


def read(path):
    value=json.loads(payload(path))
    if not isinstance(value,dict):raise ValueError('recovery_acceptance_evidence_invalid')
    return value


def verified(c, project, task, state, binding):
    session=state.get('recovery_sessions',{}).get(binding)
    if not session or session['status'] not in ('pending_manual_acceptance','complete'):
        raise ValueError('recovery_not_ready_for_acceptance')
    if session.get('controller_revision')!=c.controller_revision(state):
        raise ValueError('recovery_controller_changed')
    value=c.current_binding(project,task,binding)
    if c.digest(session['evidence'])!=binding:raise ValueError('recovery_session_evidence_changed')
    if session.get('semantic_mode','jev')!=value['decision_readiness'].get('semantic_mode','jev'):
        raise ValueError('recovery_semantic_mode_changed')
    if session.get('decision_mode')!='compact':
        raise ValueError('recovery_operation_mode_changed')
    directory=c.p.root(project,task)/('recovery-'+binding)
    receipts={}
    for stage in ('verify',)+c.GATES:
        step=session['steps'].get(stage)
        if not step or step['status']!='pass' or (stage!='verify' and step.get('adopted') is not True):
            raise ValueError('recovery_approval_missing:'+stage)
        path=directory/(stage+'.json')
        if Path(step['receipt'])!=path or sha(c,path)!=step['sha256']:
            raise ValueError('recovery_receipt_changed')
        receipts[stage]=step['sha256']
        if step['finished_at']>session['allowance']['deadline_at']:
            raise ValueError('recovery_allowance_exhausted')
    if session['allowance']['active_used']>session['allowance']['active_seconds'] or session['allowance']['calls_used']>session['allowance']['provider_calls']:
        raise ValueError('recovery_allowance_exhausted')
    checks=read(directory/'verify.json')
    if checks.get('binding')!=binding or checks.get('status')!='pass' or len(checks.get('checks',[]))!=len(value['checks']):
        raise ValueError('recovery_test_failure')
    for actual,expected in zip(checks['checks'],value['checks']):
        if actual.get('id')!=expected['id'] or actual.get('argv')!=expected['argv'] or actual.get('exit_code')!=0 or not isinstance(actual.get('output'),str) or c.hashlib.sha256(actual['output'].encode()).hexdigest()!=actual.get('output_sha256'):
            raise ValueError('recovery_test_failure')
    for stage in c.GATES:
        step=session['steps'][stage];report=read(directory/(stage+'.json'))
        if (report.get('mode')=='compact')!=(session['decision_mode']=='compact'):
            raise ValueError('recovery_operation_mode_changed')
        c.validate_review(report,value,stage,checks,step['reviewer_id'])
    for stage in c.p.STAGES:
        record=state['completed'].get(stage)
        path=directory/(stage+'-adopted.json')
        if not record or record.get('recovery_binding')!=binding or Path(record['receipt'])!=path or sha(c,path)!=record['sha256'] or record['input_sha256']!=c.p.inputs(value['worktree'],task,stage,state):
            raise ValueError('recovery_adopted_evidence_changed')
        read(path);c.p.validate_receipt(path,task,stage,Path(value['worktree']))
        receipts[stage+'-adopted']=record['sha256']
    return session,value,directory,receipts


def validate(c,project,task,state,binding):
    session,value,directory,receipts=verified(c,project,task,state,binding)
    retained=session.get('acceptance')
    path=directory/'acceptance.json'
    if not retained or retained.get('receipt')!=str(path) or sha(c,path)!=retained.get('sha256'):
        raise ValueError('recovery_acceptance_receipt_changed')
    record=read(path)
    required=[case for case in value['cases'] if case['applicability']['kind']=='manual']
    stored=record['attestation']
    if not isinstance(stored,dict):raise ValueError('recovery_acceptance_receipt_changed')
    raw=dict(binding=stored.get('binding'),cases=stored.get('cases')) if required else dict(binding=stored.get('binding'),accepted=stored.get('accepted'))
    normalized=c.load('manual-acceptance').validate(required,binding,raw)
    if stored!=normalized:raise ValueError('recovery_acceptance_receipt_changed')
    expected=dict(version=1,binding=binding,operator=record.get('operator'),attestation=normalized,receipts=receipts,semantic_mode=session.get('semantic_mode','jev'))
    if not isinstance(expected['operator'],str) or not expected['operator'].strip() or '\0' in expected['operator'] or len(expected['operator'])>200 or record.get('intent')!=c.digest(expected) or any(record.get(k)!=v for k,v in expected.items()) or set(record)!=set(expected)|{'intent','accepted_at'}:
        raise ValueError('recovery_acceptance_receipt_changed')
    if state.get('status')!='complete' or state.get('final_evidence')!=dict(outcome='pass',reason='recovery_explicit_acceptance',recovery_binding=binding,acceptance_sha256=retained['sha256']):
        raise ValueError('recovery_acceptance_state_changed')
    return record


def accept(c,project,task,binding,operator,attestation):
    if not re.fullmatch(r'[0-9a-f]{64}',binding):raise ValueError('recovery_assessment_required')
    if not isinstance(operator,str) or not operator.strip() or '\0' in operator or len(operator)>200:
        raise ValueError('recovery_operator_identity_required')
    with c.action_lock(project,task),c.controller_lock(project,task) as directory:
        _,state,_=c.target_state(project,task)
        session,value,folder,receipts=verified(c,project,task,state,binding)
        required=[case for case in value['cases'] if case['applicability']['kind']=='manual']
        normalized=c.load('manual-acceptance').validate(required,binding,attestation)
        intent=dict(version=1,binding=binding,operator=operator,attestation=normalized,receipts=receipts,semantic_mode=session.get('semantic_mode','jev'))
        path=folder/'acceptance.json'
        if path.exists() or path.is_symlink():
            record=read(path)
            if record.get('intent')!=c.digest(intent) or any(record.get(k)!=v for k,v in intent.items()) or set(record)!=set(intent)|{'intent','accepted_at'}:
                raise ValueError('recovery_acceptance_conflict')
        else:
            record=dict(intent,intent=c.digest(intent),accepted_at=time.time())
            fd,name=tempfile.mkstemp(prefix='.acceptance-',suffix='.json',dir=folder)
            temporary=Path(name)
            try:
                with os.fdopen(fd,'w') as stream:
                    json.dump(record,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
                # link publishes the fully durable file exclusively; existing evidence is never replaced.
                os.link(temporary,path)
                fd=os.open(folder,os.O_RDONLY)
                try:os.fsync(fd)
                finally:os.close(fd)
            finally:
                temporary.unlink(missing_ok=True)
        published=payload(path)
        if json.loads(published)!=record:raise ValueError('recovery_acceptance_receipt_changed')
        published_sha=c.hashlib.sha256(published).hexdigest()
        if session['status']=='complete':
            validate(c,project,task,state,binding)
            return dict(c.summary(session),acceptance=record)
        # Immutable intent precedes the atomic controller transition. Replay can finish a crash here.
        _,_,_,current_receipts=verified(c,project,task,state,binding)
        if current_receipts!=receipts:raise ValueError('recovery_receipt_changed')
        if payload(path)!=published:raise ValueError('recovery_acceptance_receipt_changed')
        retained=dict(receipt=str(path),sha256=published_sha)
        session.update(status='complete',next_action='none',acceptance=retained)
        state.update(status='complete',next_action='none',final_evidence=dict(outcome='pass',reason='recovery_explicit_acceptance',recovery_binding=binding,acceptance_sha256=retained['sha256']))
        session['controller_revision']=c.controller_revision(state)
        c.p.recovery.atomic(directory/'state.json',state)
        return dict(c.summary(session),acceptance=record)
