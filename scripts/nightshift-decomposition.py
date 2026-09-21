#!/usr/bin/env python3
"""Validate a public epic plan and emit an ordered batch; never approve gates."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def validate(plan, project):
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    def labels(value):
        return (isinstance(value, list) and bool(value)
                and all(isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', v) for v in value)
                and len(value) == len(set(value)))
    def source(ref):
        require(isinstance(ref, str) and ref.startswith('spec:'), 'child and parent refs must be spec: paths')
        relative = Path(ref[5:])
        require(not relative.is_absolute() and '..' not in relative.parts, 'source must be project relative')
        path = project / relative
        require(path.resolve().is_relative_to(project) and not any(p.is_symlink() for p in [path, *path.parents]), 'source symlink or escape')
        require(path.is_file() and path.stat().st_size <= 1024 * 1024, 'source missing or too large')
        return hashlib.sha256(path.read_bytes()).hexdigest()
    require(isinstance(plan, dict) and set(plan) == {'version','parent','requirements','children'}, 'invalid plan keys')
    require(type(plan['version']) is int and plan['version'] == 1, 'invalid plan version')
    parent_hash = source(plan['parent'])
    require(labels(plan['requirements']), 'invalid parent requirement IDs')
    children = plan['children']
    require(isinstance(children, list) and 2 <= len(children) <= 16, 'plan requires 2–16 children')
    by_id, refs, coverage = {}, set(), set()
    for child in children:
        require(isinstance(child, dict) and set(child) == {'id','ref','depends_on','requirements','integration'}, 'invalid child keys')
        require(labels([child['id']]) and child['id'] not in by_id, 'invalid or duplicate child ID')
        require(isinstance(child['depends_on'], list) and (not child['depends_on'] or labels(child['depends_on'])), 'invalid dependencies')
        require(labels(child['requirements']) and set(child['requirements']) <= set(plan['requirements']), 'invalid child coverage')
        require(type(child['integration']) is bool, 'integration must be boolean')
        digest = source(child['ref'])
        require(child['ref'] != plan['parent'] and child['ref'] not in refs, 'duplicate source ref')
        refs.add(child['ref']); coverage.update(child['requirements'])
        by_id[child['id']] = dict(child, source_sha256=digest)
    require(coverage == set(plan['requirements']), 'unassigned parent requirement')
    for child in children:
        require(set(child['depends_on']) <= set(by_id) and child['id'] not in child['depends_on'], 'unknown or self dependency')
    ordered = []
    while len(ordered) < len(children):
        ready = [key for key,c in by_id.items() if key not in ordered and set(c['depends_on']) <= set(ordered)]
        require(bool(ready), 'dependency cycle')
        ordered.extend(ready)
    integration = [c for c in children if c['integration']]
    require(len(integration) == 1, 'exactly one integration child required')
    final = integration[0]
    require(set(final['requirements']) == set(plan['requirements']), 'integration must cover every parent requirement')
    ancestors = set(final['depends_on'])
    while True:
        expanded = ancestors | {d for key in ancestors for d in by_id[key]['depends_on']}
        if expanded == ancestors:
            break
        ancestors = expanded
    require(ancestors == set(by_id) - {final['id']}, 'integration must depend on every other child')
    return dict(status='valid', parent=plan['parent'], parent_sha256=parent_hash,
                children=[by_id[key] for key in ordered],
                admission='Plan validation is not child completion or parent approval.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--plan', required=True)
    args = parser.parse_args()
    try:
        path = Path(args.plan)
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            raise ValueError('invalid plan file')
        result = validate(json.loads(path.read_text()), Path(args.project).resolve(strict=True))
        print(json.dumps(result)); return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps(dict(status='invalid', reason=str(error)))); return 64


if __name__ == '__main__':
    raise SystemExit(main())
