#!/usr/bin/env python3
"""Bounded inline package artifacts projected only into disposable validation views."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bundle_operations',HERE/'nightshift-operations.py')
ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)


def safe_name(project,name):
    path=ops.safe(project,name)
    if str(Path(name))!=name or any(part in ('.git','.nightshift','.codex','.claude','.agents') or part.startswith('.env') for part in Path(name).parts):
        raise ValueError('unsafe_bundle_path')
    return path


@contextmanager
def projection(project,value,graph_path,preparation_task):
    project=Path(project).resolve()
    ops.exact(value,'version parent requirements children aggregate templates artifacts')
    if type(value['version']) is not int or value['version']!=3:raise ValueError('unsupported_bundle_version')
    artifacts=value['artifacts']
    if not isinstance(artifacts,dict) or not artifacts or any(not isinstance(text,str) for text in artifacts.values()):
        raise ValueError('bundle_text_artifacts_required')
    if len(json.dumps(value,sort_keys=True).encode())>ops.MAX_REQUEST//2:
        raise ValueError('package_bundle_too_large:no_truncation')
    if not isinstance(value['children'],list):raise ValueError('children_required')
    declared=set()
    for child in value['children']:
        declared.update(child['reads']);declared.update(child['writes']);declared.add(child['plan'])
    if not set(artifacts)<=declared:raise ValueError('undeclared_bundle_artifact')
    if not isinstance(value['parent'],str) or not value['parent'].startswith('spec:'):raise ValueError('invalid_bundle_parent')
    protected={value['parent'][5:],'routing.json','.nightshift.toml','.gitignore'}
    required={value['parent'][5:]}|declared
    if graph_path:protected.add(graph_path);required.add(graph_path)
    if preparation_task is not None:
        p=ops.plan(project,preparation_task)
        protected.update(p['inputs'].values())
        protected.add(str(ops.plan_path(project,preparation_task).relative_to(project)))
        required.update(protected-{'routing.json','.nightshift.toml','.gitignore'})
        if graph_path!=p['inputs']['spec'] or ops.read(ops.safe(project,p['inputs']['spec']))!=value:
            raise ValueError('preparation_manifest_mismatch')
    if protected.intersection(artifacts):raise ValueError('bundle_overlaps_authority')
    for name in required|set(artifacts):safe_name(project,name)
    for name,text in artifacts.items():
        path=safe_name(project,name)
        if path.exists() and path.read_bytes()!=text.encode():raise ValueError('bundle_overwrites_existing_input:'+name)
    normalized={key:val for key,val in value.items() if key!='artifacts'};normalized['version']=2
    with tempfile.TemporaryDirectory(prefix='nightshift-package-projection-') as directory:
        target=Path(directory).resolve()
        total=0
        for name in sorted(required):
            source=safe_name(project,name)
            if source.is_file() and source.stat().st_size>ops.MAX_REQUEST:raise ValueError('package_projection_too_large:no_truncation')
            data=artifacts[name].encode() if name in artifacts else source.read_bytes() if source.is_file() else None
            if name==graph_path:data=json.dumps(normalized).encode()
            if data is None:continue
            total+=len(data)
            if total>ops.MAX_REQUEST:raise ValueError('package_projection_too_large:no_truncation')
            destination=ops.safe(target,name);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
            destination.chmod(ops.stat.S_IMODE(source.stat().st_mode) if source.is_file() else 0o644)
        yield target,normalized
