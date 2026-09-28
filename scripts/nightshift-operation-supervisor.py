#!/usr/bin/env python3
"""Bounded repair composition over the shared operation executor."""
import fcntl
import os

SUBSTANTIVE = {'substantive_failure', 'review_obligations_unresolved',
               'case_review_incomplete', 'failed_or_vacuous_tests', 'architecture_constraints_failed'}
REPAIRS = {'groom-adversarial': 'groom-spec', 'verify': 'implement', 'review': 'implement'}


def category(attempt):
    reason = attempt.get('reason', '')
    if reason in SUBSTANTIVE:
        return 'substantive'
    if reason.startswith('provider_exit:'):
        return 'transport'
    if reason.startswith(('invalid_worker', 'worker_identity', 'invalid_shape')):
        return 'schema'
    return 'unknown'


def run(controller, grant, trigger=None):
    """No grants, implicit adoption, acceptance or publication are created here."""
    c = controller
    record_key=grant if trigger is None else grant+'.ci.'+trigger
    c.directory.mkdir(parents=True, exist_ok=True)
    if c.directory.resolve() != c.directory.absolute():
        raise ValueError('unsafe_state_directory')
    fd = os.open(c.directory / 'supervisor.lock', os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('supervisor_busy') from None
        with c.lease():
            g = c.state['authorizations'].get(grant)
            if not g or not (g.get('attestation') or {}).get('bounded_repair'):
                raise ValueError('bounded_repair_authorization_required')
            p, _ = c.context()
            if c.policy_binding(p) != g['policy_binding']:
                raise ValueError('authorized_policy_changed')
            allowed = g['operations']
            if any(op in allowed for op in ('adopt', 'accept', 'publish')):
                raise ValueError('repair_recipe_must_end_at_review')
            if trigger is not None:
                repair=c.state.get('delivery_repair',{})
                if repair.get('trigger')!=trigger or repair.get('grant')!=grant or repair.get('kind')!='delivery-ci':raise ValueError('ci_repair_trigger_not_authorized')
                c.cancellation_check(grant)
                if c.clock()>=g['deadline'] or c.corpus()!=g['baseline'] or c.modes()!=g['baseline_modes']:raise ValueError('repair_authority_changed_or_expired')
                if allowed!=list(c.recipes_factory()):raise ValueError('ci_repair_requires_factory_authority')
            record = c.state.setdefault('supervisors', {}).setdefault(record_key, dict(version=1, grant=grant, trigger=trigger, steps=[], decisions=[], queue=['implement','verify','review'] if trigger else list(allowed), status='running'))
            c.save()
        # The original grant, operation caps and transition ceiling survive restart.
        while True:
            with c.lease():
                g = c.state['authorizations'][grant]
                record = c.state['supervisors'][record_key]
                if record['status'] != 'running':
                    view = c.view()
                    current = all(c.assess(op)['status'] == 'current' for op in g['operations']) if record['status'] == 'passed' else False
                    return dict(status='blocked' if record['status'] == 'passed' and not current else record['status'], supervisor=record, view=view)
                if not record['queue']:
                    current = all(c.assess(op)['status'] == 'current' for op in g['operations'])
                    record['status'] = 'passed' if current else 'blocked'
                    if not current:
                        record['reason'] = 'changed_evidence_requires_assessment'
                    c.save()
                    return dict(status=record['status'], supervisor=record, view=c.view())
                if sum(len(row['steps']) for key,row in c.state['supervisors'].items() if key==grant or row.get('grant')==grant) >= 64:
                    record.update(status='blocked', reason='supervisor_transition_limit')
                    c.save()
                    continue
                if not record['steps'] or record['steps'][-1].get('completed'):
                    operation = record['queue'][0]
                    request = 'supervise-' + c.load_digest([record_key, len(record['steps']), operation])[:48]
                    record['steps'].append(dict(operation=operation, request=request))
                    c.save()
                step = dict(record['steps'][-1])
            try:
                result = c.execute(grant, step['operation'], step['request'], True)
            except (OSError, ValueError) as error:
                with c.lease():
                    record = c.state['supervisors'][record_key]
                    # A completed worker or partial integration keeps its request.
                    attempt = next((a for a in c.state['attempts'] if a['request'] == step['request']), None)
                    if attempt and attempt['status'] in ('pending', 'checkpoint'):
                        return dict(status='blocked', reason=str(error), supervisor=record, view=c.view())
                    record.update(status='blocked', reason=str(error))
                    c.save()
                continue
            with c.lease():
                g = c.state['authorizations'][grant]
                record = c.state['supervisors'][record_key]
                if result['status'] in ('pending', 'checkpoint'):
                    return dict(status='blocked', reason='reconcile_existing_request', supervisor=record, view=c.view())
                record['steps'][-1].update(completed=True, status=result['status'])
                if result['status'] in ('passed', 'reused'):
                    # Current-result reuse has no new invocation to charge.
                    if result['status']=='passed':
                        try:
                            c.retry_account(result,'success')
                        except (OSError,ValueError) as error:
                            record.update(status='blocked',reason='retry_accounting_blocked:'+str(error))
                            c.save()
                            continue
                    record['queue'].pop(0)
                    c.save()
                    continue
                if result['status'] != 'failed':
                    record.update(status='blocked', reason='changed_evidence_requires_assessment')
                    c.save()
                    continue
                failure_class = category(result)
                accounting_error = None
                try:
                    accounting = c.retry_account(result, failure_class)
                except (OSError, ValueError) as error:
                    accounting_error = str(error)
                    accounting = dict(next_action='stop', error=accounting_error)
                operation = REPAIRS.get(step['operation']) if failure_class == 'substantive' else None
                decision = dict(failed_request=step['request'], operation=step['operation'], category=failure_class,
                                binding=result['binding'], signature=result['signature'], findings=result.get('findings', []),
                                eligible_operation=operation, grant=grant, usage=c.usage(grant), accounting=accounting)
                record['decisions'].append(decision)
                p, context = c.context()
                reason = None
                if accounting_error:
                    reason = 'retry_accounting_blocked:' + accounting_error
                elif not operation or operation not in g['operations']:
                    reason = 'explicit_repair_action_required'
                elif c.clock() >= g['deadline'] or c.corpus() != g['baseline'] or c.modes() != g['baseline_modes'] or c.policy_binding(p) != g['policy_binding']:
                    reason = 'repair_authority_changed_or_expired'
                elif accounting['next_action'] == 'stop' or sum(a['status'] == 'failed' and a['operation'] == step['operation'] for a in c.state['attempts']) >= 3:
                    reason = 'repair_limit_exhausted'
                elif operation == 'implement' and c.state['results'].get('implement', {}).get('source') != context['source']:
                    reason = 'external_changes_require_adoption'
                else:
                    assessed = c.assess(operation)
                    if assessed['blockers']:
                        reason = ';'.join(assessed['blockers'])
                    elif assessed['status'] == 'current':
                        reason = 'repair_did_not_change_failed_inputs'
                    else:
                        # Explicit repair authority advances this binding only, not
                        # plan, policy, source scope, corpus or remaining allowance.
                        if operation in g['bindings']:
                            decision['previous_binding'] = g['bindings'][operation]
                            g['bindings'][operation] = assessed['binding']
                        decision['repair_binding'] = assessed['binding']
                        record['queue'] = g['operations'][g['operations'].index(operation):]
                if reason:
                    decision['blocker'] = reason
                    record.update(status='blocked', reason=reason)
                c.save()
