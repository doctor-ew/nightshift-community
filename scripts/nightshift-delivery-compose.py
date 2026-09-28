#!/usr/bin/env python3
"""Bounded endpoint composition over independently callable delivery actions."""
import fcntl
import os
import re


def run(delivery,grant,request,operations):
    d=delivery;c=d.c;m=operations
    if not isinstance(request,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',request):raise ValueError('invalid_delivery_request')
    with c.lease():
        if d.state()['grants'][grant]['assessment']['action']!='deliver':raise ValueError('delivery_endpoint_authority_required')
    fd=os.open(c.directory/'delivery-composition.lock',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('delivery_composition_busy') from None
        try:return compose(d,grant,request,m)
        except BaseException as error:
            with c.lease():
                record=next((row for row in d.state().get('compositions',{}).values() if row['grant']==grant),None)
                if record is not None:record.update(status='blocked',reason=type(error).__name__+':'+str(error));c.save()
            raise


def compose(d,grant,request,m):
    c=d.c
    with c.lease():
        state=d.state();g=state['grants'][grant];p=g['assessment']['snapshot']['profile']
        actions=['commit','branch']+(['pr'] if p['endpoint'] in ('pr','ci') else [])+(['ci'] if p['endpoint']=='ci' else [])
        records=state.setdefault('compositions',{})
        if request in records and records[request]['grant']!=grant:raise ValueError('delivery_composition_request_conflict')
        # One authorized endpoint has one durable chain, including retries with new UI request IDs.
        request=next((key for key,row in records.items() if row['grant']==grant),request)
        record=records.setdefault(request,dict(grant=grant,actions=actions,steps=[],status='running'))
        if record['actions']!=actions:raise ValueError('delivery_composition_request_conflict')
        c.save()
        repairing=bool(record.get('repair_handoff'))
    if repairing:return handoff(d,grant,request,m)
    results=[]
    for index,action in enumerate(actions):
        with c.lease():
            state=d.state();g=state['grants'][grant];record=state['compositions'][request]
            c.cancellation_check(grant)
            if c.clock()>=g['deadline']:raise ValueError('delivery_deadline')
            if d.snapshot(p)!=g['assessment']['snapshot']:raise ValueError('delivery_composition_inputs_changed')
            current=d.local_head()
            first=record['steps'][0] if record['steps'] else None
            retained=state['attempts'].get(first['request'],{}) if first else {}
            expected=(first.get('result',{}).get('head') or retained.get('commit') or g['assessment']['head']) if first else g['assessment']['head']
            if current!=expected:raise ValueError('delivery_composition_head_changed')
            if len(record['steps'])<=index:
                key='delivery-child-'+m.digest([grant,request,index])[:48]
                record['steps'].append(dict(action=action,grant=key,request=key+'-run'));c.save()
            step=dict(record['steps'][index]);existing=state['grants'].get(step['grant'])
            restriction=dict(parent_cancellation=dict(path=str(m.load('operation-reconciliation').location(c,grant)),binding=g['cancellation_binding']),deadline=g['deadline'])
        # Remote base is an endpoint-wide binding, not a new choice at each child action.
        d.active_grant=grant;d.read_only=False
        refs=d.host.refs(p)
        if refs['base']!=g['assessment']['refs']['base']:raise ValueError('delivery_composition_base_changed')
        if not existing:
            assessed=d.assess(action)
            if assessed['snapshot']!=g['assessment']['snapshot'] or assessed['head']!=expected or assessed['refs']['base']!=g['assessment']['refs']['base']:raise ValueError('delivery_composition_inputs_changed')
            if action in ('commit','branch') and assessed['refs']['head']!=g['assessment']['refs']['head']:raise ValueError('delivery_composition_remote_head_changed')
            d.authorize(action,assessed['binding'],g['operator'],step['grant'],delegation=restriction)
        with c.lease():
            retained=d.state()['attempts'].get(step['request'])
            reconcile=bool(retained and retained['status']!='complete')
        result=d.execute(step['grant'],step['request'],reconcile=reconcile)
        with c.lease():
            record=d.state()['compositions'][request];record['steps'][index]['result']=result
            results.append(result);record['status']=result['status'];record.pop('reason',None);c.save()
        if result['status']=='ci_failed' and g.get('repair_authority'):
            with c.lease():
                record=d.state()['compositions'][request]
                record.setdefault('repair_handoff',dict(result=result,adopt_before=c.state['results'].get('adopt',{}).get('digest')))
                record['status']='repair_pending';c.save()
            return handoff(d,grant,request,m)
        if result['status'] not in ('commit_prepared','branch_published','pr_open','ci_passed'):
            return dict(status=result['status'],results=results,grant=grant,request=request)
    return dict(status=results[-1]['status'],results=results,grant=grant,request=request)


def handoff(d,grant,request,m):
    """Resume one durable CI handoff; changed source never renews factory authority."""
    c=d.c
    with c.lease():
        state=d.state();g=state['grants'][grant];record=state['compositions'][request]
        authority=g.get('repair_authority');child=c.state['authorizations'].get((authority or {}).get('grant'))
        reconciliation=m.load('operation-reconciliation')
        if not child or reconciliation.identity(c,child)!=authority['identity'] or child['operator']!=g['operator']:raise ValueError('bound_repair_authority_changed')
        snapshot=g['assessment']['snapshot']
        if d.profile_current_for_repair(g) is False:raise ValueError('delivery_policy_changed')
        intent=record['repair_handoff'];adopt=c.assess('adopt')
        external=adopt['status']=='current' and adopt['result']['digest']!=intent['adopt_before']
        current_review=c.assess('review')['status']=='current'
        completed=record.get('repair_result',{}).get('status')=='passed'
        if external or completed:
            status='needs_acceptance' if current_review else 'blocked'
            next_action='fresh_acceptance_and_delivery_assessment' if current_review else 'verify_and_review_external_adoption' if external else 'reassess_changed_repair_evidence'
            record.update(status=status,next_action=next_action);c.save()
            return dict(status=status,next_action=next_action,grant=grant,request=request,reused=True,external_adoption=external,results=[row['result'] for row in record['steps'] if 'result' in row])
        c.cancellation_check(grant);c.cancellation_check(child['id'])
        if c.clock()>=min(g['deadline'],child['deadline']):raise ValueError('delivery_deadline')
        repair=record.get('repair')
        if not repair:
            if d.snapshot(snapshot['profile'],not bool(repair))!=snapshot or d.local_head()!=intent['result']['head'] or d.local_branch()!=snapshot['profile']['branch']:raise ValueError('delivery_composition_inputs_changed')
            d.active_grant=grant;d.read_only=False
            refs=d.host.refs(snapshot['profile'])
            if refs!={'head':intent['result']['head'],'base':intent['result']['base']}:raise ValueError('delivery_composition_remote_head_changed')
            evidence=intent['result']['evidence']
            if len(evidence)!=1:raise ValueError('invalid_ci_repair_evidence')
            name,expected=next(iter(evidence.items()))
            if m.sha(c.directory/name)!=expected:raise ValueError('stale_repair_evidence')
            pr,_=d.selected_pr(snapshot['profile'],intent['result']['head'])
            if not pr:raise ValueError('delivery_pr_required')
            fresh,observed=d.observe_ci(snapshot['profile'],pr,intent['result']['head'],refs)
            intent['result']=fresh;record['steps'][-1]['result']=fresh;c.save()
            if fresh['status']!='ci_failed':
                record['status']='blocked' if repair else fresh['status']
                if repair:record['reason']='registered_ci_repair_observation_changed_requires_reassessment'
                c.save()
                return dict(status=record['status'],reason=record.get('reason'),grant=grant,request=request,results=[row['result'] for row in record['steps'] if 'result' in row])
            registered=m.load('delivery-repair').register(d,g,record,fresh,observed,child['id'],m)
            # Retain the original failure ledger while using current diagnostics before dispatch.
            c.state['delivery_repair']=dict(registered,evidence=fresh['evidence'],binding=m.digest(fresh));c.save()
    result=d.resume_repair(grant,request)
    with c.lease():
        record=d.state()['compositions'][request];record['status']=result['status'];c.save()
    return dict(status=result['status'],repair=result,grant=grant,request=request,results=[row['result'] for row in record['steps'] if 'result' in row])
