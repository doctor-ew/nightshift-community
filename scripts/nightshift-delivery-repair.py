#!/usr/bin/env python3
"""CI repair admission reuses existing bounded operation authority."""


def register(delivery,grant,attempt,result,observation,repair_grant,operations):
    c=delivery.c;m=operations;state=delivery.state()
    if result['status']!='ci_failed':raise ValueError('only_completed_substantive_ci_failure_is_repairable')
    child=c.state['authorizations'].get(repair_grant)
    if not child or child['operations']!=m.RECIPES['factory'] or not (child.get('attestation') or {}).get('bounded_repair') or child['operator']!=grant['operator']:raise ValueError('existing_bounded_factory_authority_required')
    if child['policy_binding']!=c.policy_binding(m.plan(c.project,c.task)) or c.clock()>=child['deadline']:raise ValueError('repair_authority_changed_or_expired')
    if c.corpus()!=child['baseline'] or c.modes()!=child['baseline_modes']:raise ValueError('external_changes_require_adoption')
    if any(row['status'] in ('pending','checkpoint') for row in c.state['attempts']):raise ValueError('reconcile_pending_operation_first')
    p,context=c.context()
    required={(row['name'],row['app_id']) for row in grant['assessment']['snapshot']['profile']['checks']}
    failed=[row for row in observation['checks'] if (row['name'],row['app_id']) in required and row['head']==result['merge'] and row['status']=='completed' and row['conclusion']=='failure']
    if not failed:raise ValueError('only_completed_substantive_ci_failure_is_repairable')
    if any(not isinstance(row.get('output'),dict) or not any(isinstance(row['output'].get(key),str) and row['output'][key].strip() for key in ('summary','text')) for row in failed):raise ValueError('delivery_ci_diagnostics_required')
    # Remote reruns, ordering and unrelated checks cannot restart an unchanged repair.
    signature=m.digest(dict(source=context['source'],base=result['base'],checks=sorted((row['name'],row['app_id'],row['conclusion']) for row in failed)))
    trigger=signature
    reconciliation=m.load('operation-reconciliation')
    delegation=dict(parent_cancellation=dict(path=str(reconciliation.location(c,grant['id'])),binding=reconciliation.identity(c,c.state['authorizations'][grant['id']])),deadline=grant['deadline'])
    existing=next((row for row in state['ci_failures'] if row['trigger']==trigger),None)
    if existing:
        if existing['grant']!=repair_grant:raise ValueError('ci_failure_already_bound_to_repair_authority')
        c.delegate(child,delegation)
        attempt['repair']=dict(grant=repair_grant,trigger=trigger);c.save()
        return existing
    if len(state['ci_failures'])>=3:raise ValueError('ci_repair_limit_exhausted')
    implementation=c.state['results'].get('implement',{})
    if implementation.get('source')!=context['source']:raise ValueError('external_changes_require_adoption')
    c.delegate(child,delegation)
    record=dict(kind='delivery-ci',trigger=trigger,grant=repair_grant,parent=grant['id'],request='delivery-ci-'+trigger,binding=m.digest(result),signature=signature,findings=['Integration CI '+row['name']+' ('+str(row['app_id'])+') '+row['conclusion']+' at '+str(result['merge']) for row in failed],evidence=result['evidence'],attempt_position=len(c.state['attempts']))
    state['ci_failures'].append(record);c.state['delivery_repair']=record
    attempt['repair']=dict(grant=repair_grant,trigger=trigger);c.save()
    return record


def before_dispatch(delivery,grant,attempt,operations):
    """Validate retained failure at every public entrypoint until an attempt exists."""
    d=delivery;c=d.c;m=operations;repair=attempt['repair']
    supervisor=c.state.get('supervisors',{}).get(repair['grant']+'.ci.'+repair['trigger'],{})
    requests={row['request'] for row in supervisor.get('steps',[])}
    if any(row['request'] in requests and row['grant']==repair['grant'] for row in c.state['attempts']):return
    child=c.state['authorizations'].get(repair['grant'])
    if not child:raise ValueError('existing_bounded_factory_authority_required')
    c.cancellation_check(child['id'])
    if c.clock()>=min(grant['deadline'],child['deadline']):raise ValueError('delivery_deadline')
    retained=next((row for row in d.state()['ci_failures'] if row['trigger']==repair['trigger'] and row['grant']==repair['grant']),None)
    if not retained or len(retained['evidence'])!=1:raise ValueError('invalid_ci_repair_evidence')
    name,expected=next(iter(retained['evidence'].items()))
    receipt=m.safe(c.directory,name)
    if m.sha(receipt)!=expected:raise ValueError('stale_repair_evidence')
    observed=m.read(receipt);snapshot=grant['assessment']['snapshot'];p=snapshot['profile']
    if d.snapshot(p,False)!=snapshot or d.local_head()!=observed['head'] or d.local_branch()!=p['branch']:raise ValueError('delivery_composition_inputs_changed')
    d.active_grant=grant['id'];d.read_only=False
    refs=d.host.refs(p)
    if refs!={'head':observed['head'],'base':observed['base']}:raise ValueError('delivery_composition_remote_head_changed')
    pr,_=d.selected_pr(p,observed['head'])
    if not pr:raise ValueError('delivery_pr_required')
    fresh,current=d.observe_ci(p,pr,observed['head'],refs)
    attempt['repair_observation']=fresh;c.save()
    if fresh['status']!='ci_failed':raise ValueError('registered_ci_repair_observation_changed_requires_reassessment')
    required={(row['name'],row['app_id']) for row in p['checks']}
    failures=[row for row in current['checks'] if (row['name'],row['app_id']) in required and row['head']==fresh['merge'] and row['status']=='completed' and row['conclusion']=='failure']
    _,context=c.context()
    signature=m.digest(dict(source=context['source'],base=fresh['base'],checks=sorted((row['name'],row['app_id'],row['conclusion']) for row in failures)))
    if signature!=repair['trigger']:raise ValueError('registered_ci_repair_observation_changed_requires_reassessment')
    registered=register(d,grant,attempt,fresh,current,child['id'],m)
    c.state['delivery_repair']=dict(registered,evidence=fresh['evidence'],binding=m.digest(fresh));c.save()
