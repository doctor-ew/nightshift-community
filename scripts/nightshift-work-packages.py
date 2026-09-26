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


def validate(project, value):
    project = Path(project).resolve()
    ops.exact(value, 'version parent requirements children aggregate')
    if type(value['version']) is not int or value['version'] != VERSION:
        raise ValueError('unsupported_package_version')
    aggregate = ops.limits(value['aggregate'])
    core = {k: value[k] for k in ('version', 'parent', 'requirements')}
    if not isinstance(value['children'], list):
        raise ValueError('children_required')
    core['children'] = [{k: c[k] for k in ('id', 'ref', 'depends_on', 'requirements', 'integration')} for c in value['children']]
    ordered = ops.load('decomposition').validate(core, project)
    packages = {}
    owners = {}
    for child in value['children']:
        ops.exact(child, 'id ref depends_on requirements integration plan reads writes interfaces allowance')
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
            ops.safe(project, name)
        if set(writes) != set(plan['scope']):
            raise ValueError('package_scope_mismatch')
        required = set(plan['inputs'].values()) | {c['argv'][1] for c in plan['checks']}
        if not required.issubset(reads) or plan['inputs']['spec'] != child['ref'][5:]:
            raise ValueError('package_inputs_incomplete')
        if plan['publication'] is not None:
            raise ValueError('package_cannot_publish')
        for name in writes:
            if name in owners:
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
            path = ops.safe(project, name)
            if not path.exists() and not owner:
                raise ValueError('package_input_missing:' + name)
    return dict(version=VERSION, status='valid', parent=ordered['parent'], parent_sha256=ordered['parent_sha256'],
                requirements=value['requirements'], aggregate=aggregate,
                children=[packages[c['id']] for c in ordered['children']],
                binding=ops.digest(value), semantic_approval=False)


def template(value):
    """Export data only; approval, authority and historical usage never travel."""
    ops.exact(value, 'version parent requirements children aggregate')
    return json.loads(json.dumps(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'template'))
    parser.add_argument('--project', default='.')
    parser.add_argument('--graph', required=True)
    args = parser.parse_args()
    try:
        project = Path(args.project).resolve()
        value = ops.read(ops.safe(project, args.graph))
        result = validate(project, value)
        if args.action == 'template':
            result = dict(version=VERSION, template=template(value), authority=None, approval=None)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps(dict(status='blocked', reason=str(error))))
        return 1


if __name__ == '__main__':
    sys.exit(main())
