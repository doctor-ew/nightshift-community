#!/usr/bin/env python3
"""Exact mapped semantic obligations for the operation controller."""
import hashlib
import importlib.util
import json
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent


def load(name):
    spec=importlib.util.spec_from_file_location('operation_decision_'+name,HERE/('nightshift-'+name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


engine=load('decision-engine')


def packets(controller, plan, observations):
    name=plan['reviewer_policy']['semantic_plan']
    if name is None:return []
    operations=load('operations')
    data=operations.read(operations.safe(controller.project,name))
    operations.exact(data,'version obligations')
    if data['version']!=1 or not isinstance(data['obligations'],list) or not 1<=len(data['obligations'])<=64:
        raise ValueError('invalid_semantic_obligations')
    observed={c['id']:c for c in observations}
    corpus=controller.corpus(); result=[]; covered={}; resolved=set(); ids=set(); requirement_ids=set()
    for row in data['obligations']:
        operations.exact(row,'id kind question requirements findings references high_risk')
        if row['id'] in ids:raise ValueError('duplicate_semantic_obligation')
        ids.add(row['id']);refs=[];checks={}
        for ref in row['references']:
            operations.exact(ref,'id role path start_line end_line')
            name=ref['path'];a=ref['start_line'];b=ref['end_line']
            if type(a) is not int or type(b) is not int or not 1<=a<=b:raise ValueError('invalid_semantic_span')
            if ref['role']=='observation':
                check=observed[name];text=check['output'];file_hash=check['output_sha256']
                if check['exit_code']!=0 or engine.text_hash(text)!=file_hash:raise ValueError('invalid_observation')
                checks.setdefault(name,dict(id=name,exit_code=0,output_sha256=file_hash,evidence=[]))['evidence'].append(ref['id'])
            else:
                path=operations.safe(controller.project,name);text=path.read_text();file_hash=operations.sha(path)
                if corpus.get(name)!=file_hash:raise ValueError('semantic_evidence_changed')
                covered.setdefault(name,set()).update(range(a,b+1))
            lines=text.splitlines(keepends=True)
            if b>len(lines):raise ValueError('missing_semantic_span')
            excerpt=''.join(lines[a-1:b]);refs.append(dict(ref,file_sha256=file_hash,sha256=engine.text_hash(excerpt),text=excerpt))
        packet=dict(version=1,id=row['id'],kind=row['kind'],question=row['question'],requirements=row['requirements'],findings=row['findings'],evidence=refs,checks=list(checks.values()),high_risk=row['high_risk'])
        engine.validate(packet)
        if packet['kind']=='finding_resolved':resolved.update(f['id'] for f in packet['findings'])
        requirement_ids.update(r['id'] for r in packet['requirements'])
        result.append(packet)
    required=set(plan['scope'])|{plan['inputs']['spec'],plan['inputs']['scenarios']}|{c['argv'][1] for c in plan['checks']}
    for name in required:
        lines=operations.safe(controller.project,name).read_text().splitlines()
        if covered.get(name,set())!=set(range(1,len(lines)+1)):raise ValueError('semantic_context_incomplete:'+name)
    scenarios=operations.read(operations.safe(controller.project,plan['inputs']['scenarios']))
    if not {c['id'] for c in scenarios['cases']}.issubset(requirement_ids):raise ValueError('semantic_case_mapping_incomplete')
    findings={engine.text_hash(f) for a in controller.state['attempts'] if a['status']=='failed' for f in a.get('findings',[])}
    if not findings.issubset(resolved):raise ValueError('semantic_findings_unresolved')
    if not {'requirement_supported','scope_matches','oracle_valid'}.issubset({p['kind'] for p in result}):raise ValueError('semantic_obligations_missing')
    return result


def configuration(controller):
    return getattr(controller,'semantic_settings',None) or load('recovery-decisions').configuration(controller.project)


def readiness(controller,plan,observations):
    if plan['reviewer_policy']['semantic_plan'] is None:return None
    cfg=configuration(controller)
    selected=packets(controller,plan,observations)
    for packet in selected:engine.request_body(packet,cfg)
    return dict(settings=cfg,packets=selected)


def run(controller,plan,grant,operation,observations,route):
    prepared=readiness(controller,plan,observations)
    if prepared is None:return None
    starts={};tokens={}
    authority=engine.digest(dict(task=controller.task,worktree=str(controller.project),policy=plan['reviewer_policy'],route=route))
    def reserve(kind,key,size):
        row=controller.reserve(grant,operation,'decision:'+key,size)
        tokens[key]=row;starts[key]=time.monotonic();return key
    def finish(key,outcome):
        elapsed=time.monotonic()-starts[key];controller.finish('decision:'+key,elapsed)
        if elapsed>tokens[key]['reserved_seconds']:raise ValueError('decision_allowance_exceeded')
    def transport(settings,key,body):
        pending=next(row for row in reversed(list(tokens.values())) if controller.state['calls'][row['id']]['status']=='pending')
        settings=dict(settings,timeout_seconds=min(settings['timeout_seconds'],pending['reserved_seconds']))
        return (getattr(controller,'semantic_transport',None) or load('efficiency').bounded_request)(settings,key,body)
    def escalate(packet,primary,mode):
        binding=engine.digest(packet)
        # The independent worker gets evidence, never the primary judgment.
        request=dict(version=1,operation='review',binding=binding,artifacts={'semantic-obligation':json.dumps(packet)},scope=[],findings=[],checks=packet['checks'],verification=None)
        key=binding+':'+mode;output=controller.directory/('semantic-'+key.replace(':','-')+'.json')
        remaining=next(row['reserved_seconds'] for row in reversed(list(tokens.values())) if controller.state['calls'][row['id']]['status']=='pending')
        value=controller.worker('review',request,route,output,remaining)
        engine.atomic(output,value)
        assessed=dict(operation='review',binding=binding,findings=[])
        try:
            controller.validate_worker(value,assessed,route);decision='yes'
        except ValueError:
            if value.get('results',{}).get('decision')=='repair':decision='no'
            else:decision='abstain'
        return dict(decision=decision,packet_sha256=binding,reviewer_id=route['provider']+':'+route['model'],evidence=[r['id'] for r in packet['evidence']])
    evaluator=engine.Engine(controller.directory/'decisions',authority,prepared['settings'],reserve,finish,transport=transport,escalate=escalate)
    receipts=[]
    for packet in prepared['packets']:
        receipt=evaluator.decide(packet);receipts.append(receipt)
        if receipt['status']!='complete' or receipt['decision']!='yes':raise ValueError('semantic_decision_blocked:'+receipt['reason'])
    return dict(authority=authority,settings={k:v for k,v in prepared['settings'].items() if k!='key'},receipts=receipts)


def validate(controller,plan,record,observations):
    if record['settings'] != configuration(controller): raise ValueError('semantic_configuration_changed')
    selected=packets(controller,plan,observations)
    if len(selected)!=len(record['receipts']):raise ValueError('semantic_receipts_missing')
    for packet,receipt in zip(selected,record['receipts']):
        if receipt['policy']!=engine.POLICY:raise ValueError('semantic_policy_changed')
        engine.validate_receipt(receipt,packet,record['settings'],record['authority'],controller.directory/'decisions')
        if receipt['decision']!='yes':raise ValueError('semantic_approval_missing')
