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



def selected(controller,plan,operation):
    name=plan['reviewer_policy']['semantic_plan']
    if name is None:return False
    if operation=='review':return True
    operations=load('operations')
    data=operations.read(operations.safe(controller.project,name))
    if not isinstance(data,dict) or not isinstance(data.get('obligations'),list) or any(not isinstance(row,dict) for row in data['obligations']):raise ValueError('invalid_semantic_obligations')
    return data.get('version')==2 and any(row.get('stage')==operation for row in data['obligations'])



def required_files(controller,plan,operation):
    required=set(plan['scope'])|{plan['inputs']['spec'],plan['inputs']['scenarios']}|{c['argv'][1] for c in plan['checks']}
    if operation=='groom-adversarial':
        required=set(plan['inputs'].values())|set(controller.package_inputs(plan))|{c['argv'][1] for c in plan['checks']}
        operations=load('operations')
        try:graph=operations.read(operations.safe(controller.project,plan['inputs']['spec']))
        except ValueError:graph={}
        if isinstance(graph,dict) and graph.get('version')==3 and isinstance(graph.get('artifacts'),dict):
            # The complete manifest is the evidence: inline text is never a fake file.
            required-=set(graph['artifacts'])-set(plan['inputs'].values())
    return required


def bounded_text_file(controller,name):
    operations=load('operations');path=operations.safe(controller.project,name)
    if path.stat().st_size>engine.MAX_BYTES:raise ValueError('semantic_context_too_large:no_truncation')
    return path.read_text()


def generate(controller,plan,operation):
    """Generate complete candidate mappings; independent review judges adequacy."""
    if operation not in ('groom-adversarial','review'):raise ValueError('unsupported_semantic_handoff')
    operations=load('operations');refs=[]
    def append(role,name,text):
        if not text.strip():raise ValueError('semantic_context_missing:'+name)
        refs.append(dict(id='e'+str(len(refs)),role=role,path=name,start_line=1,end_line=len(text.splitlines())))
    required=required_files(controller,plan,operation)
    assertions={c['argv'][1] for c in plan['checks']}
    for name in sorted(required):
        role='assertion' if name in assertions else 'requirement' if name in (plan['inputs']['request'],plan['inputs']['scenarios']) else 'source'
        append(role,name,bounded_text_file(controller,name))
    if operation=='review':
        for row in controller.state['results'].get('verify',{}).get('observations',[]):append('observation',row['id'],row['output'])
    cases=controller.scenarios(plan)
    kinds=['preparation_supported','oracle_valid','requirement_package'] if operation=='groom-adversarial' else ['requirement_supported','scope_matches','oracle_valid','integration_supported']
    questions={
        'preparation_supported':'Do the proposed specification and test design faithfully implement the referenced request and constraints?',
        'requirement_package':'Does the proposed allocation preserve every requirement and interface obligation, including parent integration?',
        'oracle_valid':'Do the referenced assertions distinguish required behavior from plausible incorrect behavior?',
        'requirement_supported':'Do the implementation and actual observations support each referenced requirement?',
        'scope_matches':'Does the implementation remain within the referenced authorized scope and requirements?',
        'integration_supported':'Do the actual observations establish the combined behavior and interfaces required by the specification?',
        'finding_resolved':'Does the current evidence resolve the exact retained failed findings?',
    }
    findings={engine.text_hash(f):f for a in controller.state['attempts'] if a['status']=='failed' for f in a.get('findings',[])}
    if operation=='review' and findings:kinds.append('finding_resolved')
    evidence=[r['id'] for r in refs]
    rows=[dict(id=kind,stage=operation,kind=kind,question=questions[kind],requirements=[dict(id=c['id'],evidence=evidence) for c in cases],findings=[dict(id=f,text=findings[f],evidence=evidence) for f in sorted(findings)] if kind=='finding_resolved' else [],references=refs,high_risk=True) for kind in kinds]
    value=dict(version=2,obligations=rows)
    if len(engine.encoded(value))>operations.MAX_REQUEST:raise ValueError('semantic_mapping_too_large:no_truncation')
    return value


def packets(controller, plan, observations, operation='review'):
    name=plan['reviewer_policy']['semantic_plan']
    if name is None:return []
    operations=load('operations')
    data=operations.read(operations.safe(controller.project,name))
    operations.exact(data,'version obligations')
    if type(data['version']) is not int or data['version'] not in (1,2) or not isinstance(data['obligations'],list) or not 1<=len(data['obligations'])<=64:
        raise ValueError('invalid_semantic_obligations')
    if data['version']==1 and operation!='review':return []
    observed={c['id']:c for c in observations}
    corpus=controller.corpus(); result=[]; covered={}; resolved=set(); ids=set(); requirement_ids=set()
    for row in data['obligations']:
        operations.exact(row,'id kind question requirements findings references high_risk'+(' stage' if data['version']==2 else ''))
        if data['version']==2:
            if row['stage'] not in ('groom-adversarial','review'):raise ValueError('unsupported_semantic_handoff')
            if row['stage']!=operation:continue
        if row['id'] in ids:raise ValueError('duplicate_semantic_obligation')
        ids.add(row['id']);refs=[];checks={};reference_bytes=0
        if not isinstance(row['references'],list) or len(row['references'])>64:raise ValueError('semantic_references_too_large')
        for ref in row['references']:
            operations.exact(ref,'id role path start_line end_line')
            name=ref['path'];a=ref['start_line'];b=ref['end_line']
            if type(a) is not int or type(b) is not int or not 1<=a<=b:raise ValueError('invalid_semantic_span')
            if ref['role']=='observation':
                if operation!='review' or name not in observed:raise ValueError('semantic_observation_missing')
                check=observed[name];text=check['output'];file_hash=check['output_sha256']
                if check['exit_code']!=0 or engine.text_hash(text)!=file_hash:raise ValueError('invalid_observation')
                checks.setdefault(name,dict(id=name,exit_code=0,output_sha256=file_hash,evidence=[]))['evidence'].append(ref['id'])
            else:
                path=operations.safe(controller.project,name);text=bounded_text_file(controller,name);file_hash=operations.sha(path)
                if corpus.get(name)!=file_hash:raise ValueError('semantic_evidence_changed')
            lines=text.splitlines(keepends=True)
            if b>len(lines):raise ValueError('missing_semantic_span')
            if ref['role']!='observation':covered.setdefault(name,set()).update(range(a,b+1))
            excerpt=''.join(lines[a-1:b]);reference_bytes+=len(excerpt.encode())
            if reference_bytes>engine.MAX_BYTES:raise ValueError('semantic_context_too_large:no_truncation')
            refs.append(dict(ref,file_sha256=file_hash,sha256=engine.text_hash(excerpt),text=excerpt))
        packet=dict(version=1,id=row['id'],kind=row['kind'],question=row['question'],requirements=row['requirements'],findings=row['findings'],evidence=refs,checks=list(checks.values()),high_risk=row['high_risk'])
        if data['version']==2:packet.update(version=2,stage=operation)
        engine.validate(packet)
        if packet['version']==2:
            retained={engine.text_hash(f):f for a in controller.state['attempts'] if a['status']=='failed' for f in a.get('findings',[])}
            if any(retained.get(f['id'])!=f['text'] for f in packet['findings']):raise ValueError('semantic_finding_not_retained')
        if packet['kind']=='finding_resolved':resolved.update(f['id'] for f in packet['findings'])
        requirement_ids.update(r['id'] for r in packet['requirements'])
        result.append(packet)
    if not result:return []
    required=required_files(controller,plan,operation)
    for name in required:
        lines=bounded_text_file(controller,name).splitlines()
        if covered.get(name,set())!=set(range(1,len(lines)+1)):raise ValueError('semantic_context_incomplete:'+name)
    scenarios=operations.read(operations.safe(controller.project,plan['inputs']['scenarios']))
    if not {c['id'] for c in scenarios['cases']}.issubset(requirement_ids):raise ValueError('semantic_case_mapping_incomplete')
    findings={engine.text_hash(f) for a in controller.state['attempts'] if a['status']=='failed' for f in a.get('findings',[])}
    if operation=='review' and not findings.issubset(resolved):raise ValueError('semantic_findings_unresolved')
    mandatory={'requirement_supported','scope_matches','oracle_valid'} if operation=='review' else {'preparation_supported','oracle_valid'}
    if operation=='groom-adversarial' and controller.package_schema(plan):mandatory.add('requirement_package')
    if not mandatory.issubset({p['kind'] for p in result}):raise ValueError('semantic_obligations_missing')
    return result


def configuration(controller):
    return getattr(controller,'semantic_settings',None) or load('recovery-decisions').configuration(controller.project)


def readiness(controller,plan,observations,operation='review'):
    if plan['reviewer_policy']['semantic_plan'] is None:return None
    selected=packets(controller,plan,observations,operation)
    if not selected:return None
    cfg=configuration(controller)
    for packet in selected:engine.request_body(packet,cfg)
    return dict(settings=cfg,packets=selected)


def run(controller,plan,grant,operation,observations,route):
    prepared=readiness(controller,plan,observations,operation)
    if prepared is None:return None
    starts={};tokens={}
    authority=engine.digest(dict(task=controller.task,worktree=str(controller.project),policy=plan['reviewer_policy'],route=route,operation=operation))
    def escalation_request(packet):
        return dict(version=1,operation='review',binding=engine.digest(packet),artifacts={'semantic-obligation':json.dumps(packet)},scope=[],findings=[],checks=packet['checks'],verification=None)
    def reserve(kind,key,size):
        if kind!='jev':size=len(json.dumps(escalation_request(packet),sort_keys=True).encode())
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
        request=escalation_request(packet)
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
    return dict(operation=operation,authority=authority,settings={k:v for k,v in prepared['settings'].items() if k!='key'},receipts=receipts)


def validate(controller,plan,record,observations,operation='review'):
    if record.get('operation','review')!=operation:raise ValueError('semantic_handoff_changed')
    if record['settings'] != configuration(controller): raise ValueError('semantic_configuration_changed')
    selected=packets(controller,plan,observations,operation)
    if len(selected)!=len(record['receipts']):raise ValueError('semantic_receipts_missing')
    for packet,receipt in zip(selected,record['receipts']):
        if receipt['policy']!=engine.POLICY:raise ValueError('semantic_policy_changed')
        engine.validate_receipt(receipt,packet,record['settings'],record['authority'],controller.directory/'decisions')
        if receipt['decision']!='yes':raise ValueError('semantic_approval_missing')
