#!/usr/bin/env python3
"""Versioned work-package contracts over shared operation plans and evidence."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('package_operations', HERE/'nightshift-operations.py')
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
VERSION = 1


def names(value, label, empty=False):
    if not isinstance(value, list) or (not value and not empty) or any(not isinstance(v, str) or not v for v in value) or len(value) != len(set(value)):
        raise ValueError('invalid_' + label)
    return value


def validate(project, value, graph_path=None, preparation_task=None):
    project = Path(project).resolve()
    version=value.get('version') if isinstance(value,dict) else None
    ops.exact(value, 'version parent requirements children aggregate'+(' templates' if version==2 else ''))
    if type(version) is not int or version not in (1,2):
        raise ValueError('unsupported_package_version')
    if not isinstance(value['parent'], str) or not value['parent'].startswith('spec:') or str(Path(value['parent'][5:])) != value['parent'][5:]:
        raise ValueError('noncanonical_parent_reference')
    templates={}
    if version==2:
        if not isinstance(value['templates'],list) or not 1<=len(value['templates'])<=16:raise ValueError('package_templates_required')
        for template in value['templates']:
            ops.exact(template,'id version operations')
            if not isinstance(template['id'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',template['id']) or template['id'] in templates:
                raise ValueError('invalid_package_template')
            if type(template['version']) is not int or template['version']!=1 or template['operations']!=ops.RECIPES['factory']:
                raise ValueError('unsupported_package_recipe')
            templates[template['id']]=template
    aggregate = ops.limits(value['aggregate'])
    core = {k: value[k] for k in ('version', 'parent', 'requirements')}
    if not isinstance(value['children'], list):
        raise ValueError('children_required')
    core['version']=1
    core['children'] = [{k: c[k] for k in ('id', 'ref', 'depends_on', 'requirements', 'integration')} for c in value['children']]
    ordered = ops.load('decomposition').validate(core, project)
    packages = {}
    owners = {}
    for child in value['children']:
        ops.exact(child, 'id ref depends_on requirements integration plan reads writes interfaces allowance'+(' template' if version==2 else ''))
        if version==2 and child['template'] not in templates:raise ValueError('unknown_package_template')
        if child['id']==preparation_task:raise ValueError('preparation_child_identity_collision')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', child['id']):
            raise ValueError('invalid_package_id')
        expected = 'docs/' + child['id'] + '/operations.json'
        if child['plan'] != expected:
            raise ValueError('package_plan_identity_mismatch')
        plan = ops.plan(project, child['id'])
        allowance = ops.limits(child['allowance'])
        if any(plan['aggregate'][key] > allowance[key] for key in allowance):
            raise ValueError('child_plan_exceeds_package_allowance')
        reads = names(child['reads'], 'package_reads')
        writes = names(child['writes'], 'package_writes')
        for name in reads + writes:
            if str(Path(name)) != name or '.git' in Path(name).parts:
                raise ValueError('noncanonical_package_path')
            ops.safe(project, name)
        if set(writes) != set(plan['scope']):
            raise ValueError('package_scope_mismatch')
        required = set(plan['inputs'].values()) | {c['argv'][1] for c in plan['checks']}
        if not required.issubset(reads) or plan['inputs']['spec'] != child['ref'][5:]:
            raise ValueError('package_inputs_incomplete')
        if plan['publication'] is not None:
            raise ValueError('package_cannot_publish')
        for name in writes:
            if any(name == prior or name.startswith(prior + '/') or prior.startswith(name + '/') for prior in owners):
                raise ValueError('conflicting_package_writes:' + name)
            owners[name] = child['id']
        if not isinstance(child['interfaces'], list) or not child['interfaces']:
            raise ValueError('package_interfaces_required')
        interface_ids = set()
        for interface in child['interfaces']:
            ops.exact(interface, 'id version path contract')
            if not all(ops.bounded_text(interface[k]) for k in ('id', 'version', 'contract')) or interface['id'] in interface_ids or interface['path'] not in writes:
                raise ValueError('invalid_package_interface')
            interface_ids.add(interface['id'])
        packages[child['id']] = dict(child, plan_sha256=ops.sha(project/child['plan']))
    protected = {value['parent'][5:], 'routing.json', '.gitignore'} | {c['plan'] for c in value['children']}
    for child in value['children']:
        protected.update(ops.plan(project, child['id'])['inputs'].values())
    if graph_path:
        protected.add(str(graph_path))
    preparation=None
    if preparation_task is not None:
        p=ops.plan(project,preparation_task)
        if p['publication'] is not None:raise ValueError('preparation_publication_requires_separate_authority')
        protected.update(p['inputs'].values())
        protected.add(str(ops.plan_path(project,preparation_task).relative_to(project)))
        if graph_path is not None and p['inputs']['spec']!=str(graph_path):raise ValueError('preparation_manifest_mismatch')
        if ops.read(ops.safe(project,p['inputs']['spec']))!=value:raise ValueError('preparation_manifest_mismatch')
        preparation=dict(task=preparation_task,plan_sha256=ops.sha(ops.plan_path(project,preparation_task)),inputs={name:ops.sha(ops.safe(project,name)) if ops.safe(project,name).is_file() else None for name in p['inputs'].values()},allocation=p['aggregate'])
    if protected.intersection(owners):
        raise ValueError('package_write_overlaps_contract')
    for key in ('calls', 'seconds'):
        if sum(c['allowance'][key] for c in packages.values()) > aggregate[key]:
            raise ValueError('parent_allowance_insufficient:' + key)
    # Worst-case sequential wall allocation is inspectable before any dispatch.
    if sum(c['allowance']['wall_seconds'] for c in packages.values()) > aggregate['wall_seconds']:
        raise ValueError('parent_allowance_insufficient:wall_seconds')
    ancestors = {}
    for row in ordered['children']:
        child = packages[row['id']]
        deps = set(child['depends_on'])
        ancestors[child['id']] = deps | {a for d in deps for a in ancestors[d]}
        for name in child['reads']:
            owner = owners.get(name)
            if owner and owner != child['id'] and owner not in ancestors[child['id']]:
                raise ValueError('undeclared_package_dependency:' + name)
            if owner and owner != child['id'] and name not in {i['path'] for i in packages[owner]['interfaces']}:
                raise ValueError('undeclared_package_interface:' + name)
            path = ops.safe(project, name)
            if not path.exists() and not owner:
                raise ValueError('package_input_missing:' + name)
        child['input_sha256'] = {name: ops.sha(project/name) if (project/name).is_file() else None for name in sorted(set(child['reads'] + child['writes']))}
    resolved = [packages[c['id']] for c in ordered['children']]
    return dict(version=version, status='valid', parent=ordered['parent'], parent_sha256=ordered['parent_sha256'],
                requirements=value['requirements'], aggregate=aggregate,
                children=resolved,templates=templates,preparation=preparation,
                binding=ops.digest(dict(graph=value, parent_sha256=ordered['parent_sha256'], children=resolved,preparation=preparation)), semantic_approval=False)


def template(value):
    """Export data only; approval, authority and historical usage never travel."""
    ops.exact(value, 'version parent requirements children aggregate'+(' templates' if value.get('version')==2 else ''))
    return json.loads(json.dumps(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'template', 'assess', 'view', 'prepare', 'authorize', 'run'))
    parser.add_argument('--project', default='.')
    parser.add_argument('--graph')
    for name in ('task','binding','operator','request','grant'):parser.add_argument('--'+name)
    args = parser.parse_args()
    try:
        project = Path(args.project).resolve()
        if args.action not in ('validate','template'):
            body={key:value for key,value in vars(args).items() if value is not None and key not in ('project','graph')}
            result=ops.load('package-controller').api(project,body)
            print(json.dumps(result));return 1 if result.get('status') in ('blocked','failed') else 0
        value = ops.read(ops.safe(project, args.graph))
        result = validate(project, value, args.graph,args.task)
        if args.action == 'template':
            result = dict(version=value['version'], template=template(value), authority=None, approval=None)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps(dict(status='blocked', reason=str(error))))
        return 1


if __name__ == '__main__':
    sys.exit(main())
