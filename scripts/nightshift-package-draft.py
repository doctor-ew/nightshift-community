#!/usr/bin/env python3
"""Bounded child-artifact drafting through ordinary Groom operations."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('draft_operations',HERE/'nightshift-operations.py')
ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)


def descriptor(project,plan):
    value=plan.get('package_draft')
    if value is None:return None
    ops.exact(value,'version slots template aggregate max_bytes')
    if type(value['version']) is not int or value['version']!=1:raise ValueError('package_draft_version')
    slots=value['slots']
    if not isinstance(slots,list) or not 2<=len(slots)<=16 or any(not isinstance(s,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,60}',s) for s in slots) or len(set(slots))!=len(slots):
        raise ValueError('package_draft_slots')
    ops.limits(value['aggregate'])
    if type(value['max_bytes']) is not int or not 1<=value['max_bytes']<=65536:raise ValueError('package_draft_size_limit')
    template=ops.safe(project,value['template'])
    if str(Path(value['template']))!=value['template'] or not template.is_file():raise ValueError('package_draft_template_required')
    policy=ops.read(template);ops.exact(policy,'version limits aggregate reviewer_policy environment')
    if type(policy['version']) is not int or policy['version']!=1:raise ValueError('package_template_version')
    ops.exact(policy['limits'],' '.join(ops.OPS))
    for limit in policy['limits'].values():ops.limits(limit)
    ops.limits(policy['aggregate'])
    ops.exact(policy['reviewer_policy'],'version require_different_provider semantic_plan')
    if policy['reviewer_policy']!=dict(version=1,require_different_provider=True,semantic_plan=None):raise ValueError('package_template_independent_review_required')
    outputs=[f'docs/{slot}/{name}' for slot in slots for name in ('operations.json','SPEC.md','scenarios.json','checks.py')]
    protected=set(plan['inputs'].values())|set(plan['scope'])|{value['template']}
    if any(a==b or a.startswith(b+'/') or b.startswith(a+'/') for a in protected for b in outputs):raise ValueError('package_draft_protected_overlap')
    for name in outputs:ops.safe(project,name)
    return dict(configuration=value,template=policy,template_sha256=ops.sha(template),outputs=outputs,
                validator_sha256=ops.sha(Path(__file__)),contract_sha256=ops.sha(HERE/'nightshift-work-packages.py'))


def outputs(project,plan):
    selected=descriptor(project,plan)
    return [plan['inputs']['spec'],plan['inputs']['scenarios']]+(selected['outputs'] if selected else [])


def validate_candidate(controller,plan,changes):
    selected=descriptor(controller.project,plan)
    if selected is None:return None
    allowed=outputs(controller.project,plan)
    if set(changes)-set(allowed):raise ValueError('package_draft_outside_inventory')
    for name,row in changes.items():
        if ops.hashlib.sha256(row['text'].encode()).hexdigest()!=row['after']:raise ValueError('package_draft_content_hash_mismatch')
    with tempfile.TemporaryDirectory(prefix='nightshift-package-draft-') as temporary:
        target=Path(temporary).resolve()
        subprocess.run(['git','init','-q',str(target)],check=True)
        for name in controller.corpus():
            source=ops.safe(controller.project,name)
            if source.exists():
                destination=ops.safe(target,name);destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
        for name,row in changes.items():
            destination=ops.safe(target,name);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(row['text'].encode())
        total=0
        for name in allowed:
            path=ops.safe(target,name)
            if not path.is_file() or not path.read_text().strip():raise ValueError('package_draft_output_missing:'+name)
            total+=path.stat().st_size
        if total>selected['configuration']['max_bytes']:raise ValueError('package_draft_outputs_too_large')
        graph=ops.read(ops.safe(target,plan['inputs']['spec']))
        result=ops.load('work-packages').validate(target,graph,plan['inputs']['spec'])
        if graph['parent']!='spec:'+plan['inputs']['request']:raise ValueError('package_draft_parent_changed')
        if set(c['id'] for c in graph['children'])!=set(selected['configuration']['slots']):raise ValueError('package_draft_slot_mismatch')
        if any(graph['aggregate'][k]>selected['configuration']['aggregate'][k] for k in graph['aggregate']):raise ValueError('package_draft_allowance_expanded')
        parent=ops.Operations(target,controller.task)
        if {c['id'] for c in parent.scenarios(plan)}!=set(graph['requirements']):raise ValueError('package_draft_parent_cases_mismatch')
        for row in result['children']:
            key=row['id'];child=ops.plan(target,key)
            if child.get('package_draft') is not None:raise ValueError('nested_package_draft_unsupported')
            expected=dict(request=plan['inputs']['request'],spec=f'docs/{key}/SPEC.md',scenarios=f'docs/{key}/scenarios.json',rules=plan['inputs']['rules'],architecture=plan['inputs']['architecture'])
            if child['inputs']!=expected:raise ValueError('package_draft_child_inputs_changed')
            if not set(child['scope'])<=set(plan['scope']):raise ValueError('package_draft_source_scope_expanded')
            if any(child[k]!=selected['template'][k] for k in ('limits','aggregate','reviewer_policy','environment')):raise ValueError('package_draft_template_policy_changed')
            if child['checks']!=[dict(id='unit',argv=['python3',f'docs/{key}/checks.py'])]:raise ValueError('package_draft_checks_changed')
            try:ast.parse(ops.safe(target,f'docs/{key}/checks.py').read_text())
            except SyntaxError as error:raise ValueError('package_draft_check_syntax_invalid') from error
        return dict(descriptor=ops.digest(selected),outputs={name:ops.sha(ops.safe(target,name)) for name in allowed},bytes=total)
