#!/usr/bin/env python3
"""Controller-owned, complete evidence selection for compact semantic decisions.

A committed plan maps obligations to exact line spans. It cannot author approvals.
The controller reopens every reference and requires full coverage of the changed
source, specification, scenarios and executed test assertions across each gate.
"""
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/('nightshift-'+name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

engine=load('decision-engine')
KINDS={'adoption':('requirement_supported','finding_resolved'), 'review':('requirement_supported',),
       'drift':('scope_matches',), 'qa':('oracle_valid',)}

def safe(target, name):
    path=Path(target)/name
    if Path(name).is_absolute() or '..' in Path(name).parts or path.absolute()!=path.resolve() or not path.is_file():
        raise ValueError('decision_unsafe_reference:'+name)
    if path.stat().st_size>2_000_000:raise ValueError('decision_reference_too_large')
    return path


def configuration(target):
    cfg=load('efficiency').config(SimpleNamespace(project=str(target),action='evaluate'))['jev']
    # Concrete model identity is mandatory; aliases cannot bind an approval.
    if not cfg['enabled'] or re.search(r'(^|[-/:])latest($|[-/:])',cfg['model'],re.I):
        raise ValueError('decision_requires_enabled_pinned_model')
    if not os.environ.get(cfg['key_env']):raise ValueError('decision_credentials_missing')
    cfg=dict(cfg,timeout_seconds=min(20,cfg['timeout_seconds']),max_bytes=min(engine.MAX_BYTES,cfg['max_bytes']))
    return cfg


# Timing is not evidence. Test runners print durations that differ on every run,
# which changed every packet and discarded every earlier answer. This view
# replaces only duration tokens, line for line, so evidence spans stay exact.
OBSERVATION_VIEW='timing-normalized-v1'
# Only spec-reporter result lines (TAP reports time in duration_ms fields), and
# only the final parenthetical: runners
# append the measured time after the title, so a title ending in (5s) keeps it.
_DURATION_SUFFIX=re.compile(r'^(\s*(?:✔|✖|✓|✗)\s.*) \((?:\d+(?:\.\d+)?) ?(?:ns|us|µs|ms|s)\)$')
_UNITTEST_RAN=re.compile(r'^(Ran \d+ tests? in )\d+(?:\.\d+)?s$')
_PYTEST_SUMMARY=re.compile(r'( in )\d+(?:\.\d+)?s( \(\d+:\d\d:\d\d\))?( =+)$')
_DURATION_FIELD=re.compile(r'^(\s*(?:ℹ |# )?duration_ms:? )\d+(?:\.\d+)?$')
# A unit suffix is required; a bare "duration" may be a configured threshold.
_JSON_TIMING=re.compile(r'("(?:elapsed|duration)_(?:ms|s|seconds)"\s*:\s*)\d+(?:\.\d+)?')


def observation_view(text):
    lines=text.split('\n')
    out=[]
    for line in lines:
        line=_DURATION_SUFFIX.sub(r'\1 (<duration>)',line)
        line=_UNITTEST_RAN.sub(r'\1<duration>',line)
        line=_PYTEST_SUMMARY.sub(r'\1<duration>\3',line)
        line=_DURATION_FIELD.sub(r'\1<duration>',line)
        line=_JSON_TIMING.sub(r'\1"<duration>"',line)
        out.append(line)
    return '\n'.join(out)


# Upper bounds on what a plan may request. The per-run allowance itself is the
# plan's limits, which the operator approves through the assessment binding.
# Reviewer calls run sequentially (~30 s each measured with Claude Haiku), so
# the former 600 s bound could not fit a 31-question plan in one session.
MAX_ALLOWANCE_SECONDS=3600
MAX_PROVIDER_CALLS=64


def validate_limits(limits):
    if not isinstance(limits,dict) or set(limits)!={'wall_seconds','active_seconds','provider_calls'} or any(type(v) is not int or v<=0 for v in limits.values()):
        raise ValueError('recovery_decision_limits_invalid')
    if limits['wall_seconds']>MAX_ALLOWANCE_SECONDS or limits['active_seconds']>MAX_ALLOWANCE_SECONDS or limits['provider_calls']>MAX_PROVIDER_CALLS:
        raise ValueError('recovery_decision_limits_invalid')
    return limits


def plan(value):
    target=Path(value['worktree']);name='docs/'+value['task']+'/recovery-plan.json'
    if not (target/name).exists() and not (target/name).is_symlink():raise ValueError('recovery_decision_plan_missing:'+name)
    path=safe(target,name)
    data=json.loads(path.read_text())
    allowed={'version','checks','decisions','limits','environment','semantic_mode'}|({'generated'} if data.get('version')==2 else set())
    if set(data)-allowed or not {'version','checks','decisions','limits'}<=set(data) or data['version'] not in (1,2) or not data['decisions'] or len(data['decisions'])>64:
        raise ValueError('recovery_decision_plan_invalid')
    # Version 2: generated artifacts are proven by verification, not reviewed, and
    # every case must be traceable to an assertion span that names it.
    generated=set()
    if data['version']==2:
        declared=[(g.get('path'),g.get('argv')) for g in data.get('generated',[]) if isinstance(g,dict)]
        if declared!=[(g['path'],g['argv']) for g in value.get('generated',[])]:raise ValueError('recovery_decision_generated_changed')
        generated={g['path'] for g in value.get('generated',[])}
        if not generated<=set(value['source_files']):raise ValueError('recovery_decision_generated_not_a_changed_file')
    if data.get('semantic_mode','jev') not in ('jev','independent'):raise ValueError('recovery_semantic_mode_invalid')
    environment=data.get('environment',{})
    if not isinstance(environment,dict) or any(not re.fullmatch(r'[A-Z][A-Z0-9_]{0,80}',k) or k in ('PATH','HOME','TMPDIR','SYSTEMROOT') or k.startswith(('GIT_','LD_','DYLD_','NIGHTSHIFT_')) or not isinstance(v,str) or len(v)>4096 for k,v in environment.items()):
        raise ValueError('recovery_decision_environment_invalid')
    if value['verification_environment']!={'NIGHTSHIFT_PYTHON3':__import__('shutil').which('python3'),**environment}:raise ValueError('recovery_decision_environment_changed')
    validate_limits(data['limits'])
    # Every executable check is independently rerun. Existing report exits are ignored.
    checks=data['checks']
    if not checks or len(checks)>20 or len({c['id'] for c in checks})!=len(checks):raise ValueError('recovery_decision_checks_invalid')
    for c in checks:
        if set(c)!={'id','argv'} or len(c['argv'])!=2 or c['argv'][0] not in ('bash','python3') or not c['id']:
            raise ValueError('recovery_decision_checks_invalid')
        safe(target,c['argv'][1])
    if [(c['id'],c['argv']) for c in checks]!=[(c['id'],c['argv']) for c in value['checks']]:
        raise ValueError('recovery_decision_checks_changed')
    ids=set();case_ids={c['id'] for c in value['cases'] if c['applicability']['kind']=='deterministic'}
    findings={f['id'] for f in value['findings']}
    declared=set(value['ac_ids']);acs=set();classified=set()
    for case in value['cases']:
        case_acs=case.get('ac_ids')
        if not isinstance(case_acs,list) or not case_acs or any(not isinstance(a,str) for a in case_acs) or not set(case_acs)<=declared:
            raise ValueError('recovery_decision_case_ac_invalid')
        classified.update(case_acs)
        if case['applicability']['kind']=='deterministic':acs.update(case_acs)
    if classified!=declared:raise ValueError('recovery_decision_ac_unclassified')
    spec='docs/'+value['task']+'/SPEC.md';scenarios='docs/'+value['task']+'/behavior-scenarios.json'
    required=(set(value['source_files'])-generated)|{spec,scenarios}|{c['argv'][1] for c in checks}
    files={name:safe(target,name).read_text().splitlines(keepends=True) for name in required}
    coverage={g:{} for g in KINDS};obligations={g:dict(cases=set(),acs=set(),findings=set()) for g in KINDS}
    for row in data['decisions']:
        if set(row)!={'id','kind','case_ids','ac_ids','finding_ids','references','high_risk'} or row['id'] in ids or not isinstance(row['id'],str) or not row['id'] or type(row['high_risk']) is not bool:
            raise ValueError('recovery_decision_mapping_invalid')
        ids.add(row['id'])
        if row['kind'] not in set(sum(KINDS.values(),())) or not set(row['case_ids'])<=case_ids or not set(row['ac_ids'])<=acs or not set(row['finding_ids'])<=findings or not (row['case_ids'] or row['ac_ids']):
            raise ValueError('recovery_decision_obligation_invalid')
        roles=set();refs=set()
        for ref in row['references']:
            if set(ref)!={'id','role','path','start_line','end_line'} or ref['id'] in refs or not ref['id']:
                raise ValueError('recovery_decision_reference_invalid')
            refs.add(ref['id']);roles.add(ref['role'])
            if ref['role']=='observation':
                if ref['path'] not in {c['id'] for c in checks}:raise ValueError('recovery_decision_observation_unknown')
            else:
                name=ref['path']
                if name in generated:raise ValueError('recovery_decision_generated_not_evidence')
                if name not in files:raise ValueError('recovery_decision_source_unknown')
                if ref['role']=='requirement' and name not in (spec,scenarios):raise ValueError('recovery_decision_requirement_invalid')
                if ref['role']=='assertion' and name not in set(value['source_files'])|{c['argv'][1] for c in checks}:raise ValueError('recovery_decision_assertion_invalid')
                if ref['role']=='source' and name not in value['source_files']:raise ValueError('recovery_decision_source_invalid')
            a,b=ref['start_line'],ref['end_line']
            if type(a) is not int or type(b) is not int or not 1<=a<=b or (ref['role']!='observation' and b>len(files[ref['path']])):
                raise ValueError('recovery_decision_span_invalid')
            for gate,kinds in KINDS.items():
                if row['kind'] in kinds and ref['role']!='observation':coverage[gate].setdefault(ref['path'],set()).update(range(a,b+1))
        if roles!=engine.ROLES:raise ValueError('recovery_decision_roles_missing')
        if data['version']==2:
            for case in row['case_ids']:
                token=re.compile(r'(?<![A-Za-z0-9_-])'+re.escape(case)+r'(?![A-Za-z0-9_-])')
                if not any(ref['role']=='assertion' and token.search(''.join(files[ref['path']][ref['start_line']-1:ref['end_line']])) for ref in row['references']):
                    raise ValueError('recovery_decision_case_untraced:'+row['id']+':'+case)
        for gate,kinds in KINDS.items():
            if row['kind'] in kinds:
                obligations[gate]['cases'].update(row['case_ids']);obligations[gate]['acs'].update(row['ac_ids']);obligations[gate]['findings'].update(row['finding_ids'])
    resolved={i for row in data['decisions'] if row['kind']=='finding_resolved' for i in row['finding_ids']}
    if resolved!=findings or any(row['kind']=='finding_resolved' and not row['finding_ids'] for row in data['decisions']):
        raise ValueError('recovery_decision_finding_resolution_missing')
    for gate in KINDS:
        if obligations[gate]['cases']!=case_ids or obligations[gate]['acs']!=acs or (gate=='adoption' and obligations[gate]['findings']!=findings):
            raise ValueError('recovery_decision_obligation_missing:'+gate)
        for name,lines in files.items():
            if coverage[gate].get(name,set())!=set(range(1,len(lines)+1)):
                raise ValueError('recovery_decision_context_incomplete:'+gate+':'+name)
    return data


def claims(definitions, question):
    """Narrow statements taken verbatim from the obligations; nothing is paraphrased.

    Each case contributes its then clause, its forbidden clause and each expected
    or prohibited item; each retained finding contributes one claim.
    """
    out=[]
    def text(value):return value if isinstance(value,str) else json.dumps(value,sort_keys=True)
    for case in definitions['cases']:
        if isinstance(case.get('then'),str) and case['then'].strip():out.append(dict(id=case['id']+':then',text=case['then'].strip()))
        if isinstance(case.get('forbidden'),str) and case['forbidden'].strip():
            out.append(dict(id=case['id']+':forbidden',text='The implementation does not do the following: '+case['forbidden'].strip()))
        for i,item in enumerate(case.get('expected') or [],1):out.append(dict(id=case['id']+':expected-'+str(i),text=text(item)))
        for i,item in enumerate(case.get('prohibited') or [],1):
            out.append(dict(id=case['id']+':prohibited-'+str(i),text='The implementation does not do the following: '+text(item)))
    for finding in definitions['findings']:
        out.append(dict(id='finding:'+finding['id'],text=text(finding.get('finding',finding))))
    return out or [dict(id='question',text=question)]


def packets(value, verification, gate):
    data=plan(value);target=Path(value['worktree'])
    outputs={c['id']:c for c in verification['checks']}
    result=[]
    for row in data['decisions']:
        if row['kind'] not in KINDS[gate]:continue
        refs=[];checks={}
        for ref in row['references']:
            name=ref['path']
            if ref['role']=='observation':
                check=outputs[name]
                if engine.text_hash(check['output'])!=check['output_sha256'] or check['exit_code']!=0:raise ValueError('recovery_decision_output_unverified')
                # Reviewers see a timing-normalized view; raw output and hash stay in verify.json.
                text=observation_view(check['output']);sha=engine.text_hash(text)
                checks.setdefault(name,dict(id=name,exit_code=0,output_sha256=sha,evidence=[]))['evidence'].append(ref['id'])
            else:
                path=safe(target,name);text=path.read_text();sha=hashlib.sha256(path.read_bytes()).hexdigest()
                if value['workspace']['files'].get(name)!=sha:raise ValueError('recovery_decision_source_changed')
            lines=text.splitlines(keepends=True);a,b=ref['start_line'],ref['end_line']
            if b>len(lines):raise ValueError('recovery_decision_observation_span_missing')
            excerpt=''.join(lines[a-1:b])
            refs.append(dict(ref,path='observations/'+name if ref['role']=='observation' else name,
                             file_sha256=sha,sha256=engine.text_hash(excerpt),text=excerpt))
        mapped=[r['id'] for r in refs]
        obligations=[dict(id='case:'+i,evidence=mapped) for i in row['case_ids']]+[dict(id='ac:'+i,evidence=mapped) for i in row['ac_ids']]
        definitions=dict(cases=[c for c in value['cases'] if c['id'] in row['case_ids']],
                         findings=[f for f in value['findings'] if f['id'] in row['finding_ids']])
        question={'requirement_supported':'Do source, test assertions and observed results establish these requirements and deterministic scenario classifications?',
                  'finding_resolved':'Do current source, assertions and observations resolve every listed retained finding? Substantive findings require actual resolution in current work. Only when controller-bound failure_category demonstrates schema or transport failure, evaluate whether current external implementation evidence supports adoption while preserving the original failed receipt; do not claim the old receipt passed or was repaired. Unknown or ambiguous provenance requires abstention if resolution cannot be established.',
                  'scope_matches':'Does the supplied implementation conform to the supplied requirements without unexplained scope drift?',
                  'oracle_valid':'Do the assertions and observed results provide valid, nonvacuous evidence for these requirements?'}[row['kind']]
        packet=dict(version=1,id=row['id'],kind=row['kind'],question=question+' Obligations: '+json.dumps(definitions,sort_keys=True),
                    requirements=obligations,findings=[dict(id=i,evidence=mapped) for i in row['finding_ids']],
                    evidence=refs,checks=list(checks.values()),high_risk=row['high_risk'] or row['kind'] in ('scope_matches','oracle_valid') or len({r['path'] for r in refs if r['role']=='source'}-{r['path'] for r in refs if r['role']=='assertion'})>1)
        if data['version']==2:
            packet.update(version=3,claims=claims(definitions,question))
        engine.validate(packet);result.append(packet)
    return result


def review_framing(value,packet,mode=None):
    """Largest framing this packet can need: first ask or the worst-case single re-ask."""
    mode=mode or value.get('decision_readiness',{}).get('semantic_mode','jev')
    render=load('decision-render');route=value['reviewer_route']
    reviewer='decision-review-'+'0'*32
    if mode=='independent':
        raws=[engine.encoded(engine.independent_envelope(packet,reviewer)),
              engine.encoded(engine.independent_envelope(packet,reviewer,sorted(engine.required_roles(packet))))]
    else:
        raws=[json.dumps(dict(packet=packet,packet_sha256=engine.digest(packet),reviewer_id=reviewer,mode='exception'),sort_keys=True).encode()]
    return max((render.render(HERE.parent,raw,route['provider'],route['model']) for raw in raws),key=lambda r:r['argument_content_bytes'])


def readiness(value):
    try:
        data=plan(value);mode=data.get('semantic_mode','jev')
        if value['reviewer_route']['provider']!='claude':raise ValueError('decision_reviewer_tool_free_transport_unavailable')
        cfg=(dict(semantic_mode='independent',provider=value['reviewer_route']['provider'],model=value['reviewer_route']['model'],timeout_seconds=120,max_bytes=engine.MAX_BYTES) if mode=='independent' else configuration(value['worktree']))
        if mode=='independent':engine.independent_identity(cfg)
        observed={}
        for row in data['decisions']:
            for ref in row['references']:
                if ref['role']=='observation':observed[ref['path']]=max(observed.get(ref['path'],0),ref['end_line'])
        if any(n>1024 for n in observed.values()):raise ValueError('recovery_decision_observation_too_large')
        placeholder=dict(checks=[dict(id=k,exit_code=0,output='X\n'*n,output_sha256=engine.text_hash('X\n'*n)) for k,n in observed.items()])
        framing=[]
        for gate in KINDS:
            for packet in packets(value,placeholder,gate):
                framing.append(review_framing(value,packet,mode)['argument_content_bytes'])
                # Reserve 4 KiB for observed output and transport framing. No truncation.
                body=(engine.encoded(engine.independent_envelope(packet,'decision-review-'+'0'*32)) if mode=='independent' else engine.request_body(packet,cfg))
        return dict(status='ready',semantic_mode=mode,review_argument_content_bytes=max(framing),review_argument_scope='sum_utf8_system_prompt_user_prompt_json_schema_arguments',plan_sha256=engine.digest(data),settings=cfg,limits=data['limits'],decisions=len(data['decisions']),request_token_budget=engine.REQUEST_TOKEN_BUDGET,state_question_token_budget=engine.STATE_QUESTION_TOKEN_BUDGET)
    except (OSError,ValueError,KeyError,TypeError) as error:
        return dict(status='blocked',reason=str(error),request_token_budget=engine.REQUEST_TOKEN_BUDGET,state_question_token_budget=engine.STATE_QUESTION_TOKEN_BUDGET)
