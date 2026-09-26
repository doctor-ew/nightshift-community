#!/usr/bin/env python3
"""Versioned work-package contracts over the existing decomposition and operations."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('packages_' + name, HERE / ('nightshift-' + name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


operations = load('operations')
decomposition = load('decomposition')
VERSION = 1
INTEGRATION = ['groom-rules', 'adopt', 'verify', 'review']


def labels(value, empty=False):
    if not isinstance(value, list) or (not value and not empty) or any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', v) for v in value) or len(set(value)) != len(value):
        raise ValueError('invalid_package_labels')
    return value


def paths(project, value, empty=False):
    if not isinstance(value, list) or (not value and not empty) or len(set(value)) != len(value):
        raise ValueError('invalid_package_paths')
    for name in value:
        operations.safe(project, name)
        if Path(name).as_posix()!=name:
            raise ValueError('noncanonical_package_path')
        if name in ('.git','.nightshift') or name.startswith(('.git/', '.nightshift/')):
            raise ValueError('package_control_path')
    return value


def validate(value, project):
    """Read-only structural validation; never semantic approval or authorization."""
    project = Path(project).resolve()
    operations.exact(value, 'version decomposition templates packages aggregate preparation_task')
    if type(value['version']) is not int or value['version'] != VERSION:
        raise ValueError('unsupported_package_version')
    labels([value['preparation_task']])
    ordered = decomposition.validate(value['decomposition'], project)
    paths(project,[value['decomposition']['parent'][5:],*[child['ref'][5:] for child in ordered['children']]])
    aggregate = operations.limits(value['aggregate'])
    preparation=operations.plan(project,value['preparation_task'])
    paths(project,list(preparation['inputs'].values()))
    if preparation['publication'] is not None:
        raise ValueError('preparation_publication_requires_separate_authority')
    templates = {}
    if not isinstance(value['templates'], list) or not value['templates']:
        raise ValueError('package_templates_required')
    for template in value['templates']:
        operations.exact(template, 'id version operations')
        labels([template['id']])
        if template['id'] in templates or type(template['version']) is not int or template['version'] != 1:
            raise ValueError('invalid_package_template')
        if template['operations'] not in (operations.RECIPES['factory'], INTEGRATION):
            raise ValueError('unsupported_package_recipe')
        templates[template['id']] = template
    if not isinstance(value['packages'], list):
        raise ValueError('packages_required')
    packages = {}
    tasks = set()
    owners = {}
    providers = {}
    plans = {}
    for package in value['packages']:
        operations.exact(package, 'id task template reads writes requires provides')
        labels([package['id'], package['task']] if package['id'] != package['task'] else [package['id']])
        labels(package['requires'], empty=True); labels(package['provides'], empty=True)
        paths(project, package['reads']); paths(project, package['writes'], empty=True)
        if package['id'] in packages or package['task'] in tasks or package['task'] == value['preparation_task']:
            raise ValueError('duplicate_package_identity')
        if package['template'] not in templates:
            raise ValueError('unknown_package_template')
        p = operations.plan(project, package['task'])
        paths(project,list(p['inputs'].values()));paths(project,p['scope'])
        for check in p['checks']:paths(project,[check['argv'][1]])
        plans[package['id']] = p
        if p['publication'] is not None:
            raise ValueError('package_publication_requires_separate_authority')
        for name in package['writes']:
            if any(name==owned or name.startswith(owned+'/') or owned.startswith(name+'/') for owned in owners):
                raise ValueError('conflicting_package_writes:' + name)
            owners[name] = package['id']
        for interface in package['provides']:
            if interface in providers:
                raise ValueError('duplicate_interface_provider:' + interface)
            providers[interface] = package['id']
        packages[package['id']] = package
        tasks.add(package['task'])
    if set(packages) != {child['id'] for child in ordered['children']}:
        raise ValueError('package_decomposition_mismatch')
    control_inputs={name for p in plans.values() for name in p['inputs'].values()}
    control_inputs.update(str(operations.plan_path(project,p['task']).relative_to(project)) for p in packages.values())
    control_inputs.update(preparation['inputs'].values())
    control_inputs.add(str(operations.plan_path(project,value['preparation_task']).relative_to(project)))
    control_inputs.add(value['decomposition']['parent'][5:])
    if set(owners)&control_inputs:
        raise ValueError('package_writes_overlap_control_inputs')
    ancestors = {}
    allocations = {key:preparation['aggregate'][key] for key in ('calls','seconds')}
    if preparation['aggregate']['wall_seconds']>aggregate['wall_seconds']:
        raise ValueError('preparation_deadline_exceeds_parent')
    records = []
    for child in ordered['children']:
        key = child['id']; package = packages[key]; p = plans[key]
        inherited = set(child['depends_on'])
        for dependency in child['depends_on']:
            inherited.update(ancestors[dependency])
        ancestors[key] = inherited
        recipe = templates[package['template']]['operations']
        if child['integration']:
            if recipe != INTEGRATION or package['writes']:
                raise ValueError('integration_requires_read_only_validation')
        elif recipe != operations.RECIPES['factory'] or set(package['writes']) != set(p['scope']):
            raise ValueError('package_scope_mismatch')
        if p['inputs']['spec'] != child['ref'][5:]:
            raise ValueError('package_spec_mismatch')
        required_reads = set(p['inputs'].values()) | {check['argv'][1] for check in p['checks']} | set(p['scope'])
        if not required_reads <= set(package['reads']):
            raise ValueError('package_inputs_not_declared')
        for name in package['reads']:
            if not operations.safe(project,name).is_file() and owners.get(name) not in inherited|{key}:
                raise ValueError('missing_package_input:'+name)
            if name in owners and owners[name] != key and owners[name] not in inherited:
                raise ValueError('undeclared_source_dependency:' + name)
        for interface in package['requires']:
            if interface not in providers or providers[interface] not in inherited:
                raise ValueError('missing_interface_dependency:' + interface)
        for counter in allocations:
            allocations[counter] += p['aggregate'][counter]
        if p['aggregate']['wall_seconds'] > aggregate['wall_seconds']:
            raise ValueError('child_deadline_exceeds_parent')
        records.append(dict(package=package, decomposition=child, recipe=recipe,
                            plan_sha256=operations.sha(operations.plan_path(project,package['task'])),
                            input_sha256={name:operations.sha(operations.safe(project,name)) if operations.safe(project,name).is_file() else None for name in package['reads']},
                            allocation=p['aggregate']))
    if any(allocations[key] > aggregate[key] for key in allocations):
        raise ValueError('child_allocations_exceed_parent')
    if operations.read(operations.safe(project,preparation['inputs']['spec'])) != value:
        raise ValueError('preparation_manifest_mismatch')
    result = dict(version=VERSION, status='valid', manifest_sha256=operations.digest(value), parent_sha256=ordered['parent_sha256'],
                packages=records, aggregate=aggregate, allocations=allocations,
                preparation_task=value['preparation_task'],
                preparation_plan_sha256=operations.sha(operations.plan_path(project,value['preparation_task'])),
                preparation_inputs={name:operations.sha(operations.safe(project,name)) for name in preparation['inputs'].values()},
                preparation_allocation=preparation['aggregate'],
                semantic_approval=False, authorized=False,
                limitations=['sequential_only', 'no_nested_graphs', 'independent_preparation_review_required'])
    result['binding']=operations.digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--plan', required=True)
    args = parser.parse_args()
    try:
        value = operations.read(Path(args.plan).absolute())
        print(json.dumps(validate(value,args.project)));return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps(dict(status='blocked',reason=str(error))));return 1


if __name__ == '__main__':raise SystemExit(main())
