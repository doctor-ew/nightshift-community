#!/usr/bin/env python3
"""Resolve opt-in provider restrictions before any Nightshift provider launch."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

MODES = ('standard', 'claude-only')


def mode(project=None):
    """Restrictions compose: a child or project cannot relax inherited restrictions."""
    values = [os.environ.get('NIGHTSHIFT_PROVIDER_POLICY', 'standard')]
    project = Path(project or os.environ.get('NIGHTSHIFT_PROJECT_DIR') or os.getcwd()).resolve()
    roots = [Path(os.environ.get('NIGHTSHIFT_HOME', str(Path.home() / '.nightshift'))), project]
    # A directly invoked worker in an isolated worktree must still see the
    # primary checkout's project policy, even without the factory environment.
    result = subprocess.run(['git', '-C', str(project), 'rev-parse', '--path-format=absolute', '--show-toplevel', '--git-common-dir'],
                            capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        lines = result.stdout.splitlines()
        roots.append(Path(lines[0]))
        common = Path(lines[1])
        if common.name == '.git':
            roots.append(common.parent)
    for root in dict.fromkeys(roots):
        canonical = root / '.nightshift.toml'
        path = canonical if canonical.exists() or canonical.is_symlink() else root / 'nightshift.toml'
        if not path.exists() and not path.is_symlink():
            continue
        data = tomllib.loads(path.read_text())
        providers = data.get('providers', {})
        if not isinstance(providers, dict):
            raise ValueError('providers must be a table')
        values.append(providers.get('policy', 'standard'))
    if any(value not in MODES for value in values):
        raise ValueError('provider policy must be standard or claude-only')
    return 'claude-only' if 'claude-only' in values else 'standard'


def select_route(routing, role, gear, policy, author='', adversarial=False, initial=None):
    route = dict(initial or routing['roles'][role]['gears'][str(gear)])
    allowed = routing.get('allowed_providers', ['claude', 'codex', 'local'])
    if (not isinstance(allowed, list) or not allowed or
            any(p not in ('claude', 'codex', 'local') for p in allowed) or
            len(set(allowed)) != len(allowed)):
        raise ValueError('invalid allowed_providers')
    if adversarial and author not in ('claude', 'codex', 'local'):
        raise ValueError('adversarial dispatch requires valid author provenance')
    if policy == 'claude-only':
        if route.get('provider') != 'claude':
            choices = routing['roles'][role]['gears']
            preferred = choices.get(str(gear))
            options = ([preferred] if preferred else []) + [choices[k] for k in sorted(choices)]
            permitted = next((dict(item) for item in options if item.get('provider') == 'claude'), None)
            route = {**route, **permitted} if permitted else None
            if route is not None and route.get('gear') == 0:
                route['gear'] = 1
            if route is None:
                raise ValueError('claude-only policy has no Claude route for this role')
        if not isinstance(route.get('model'), str) or not route['model']:
            raise ValueError('claude-only policy requires a configured Claude model')
    if route is not None and route['provider'] not in allowed:
        choices = routing['roles'][role]['gears']
        permitted = next(((key, item) for key, item in sorted(choices.items())
                          if item['provider'] in allowed and (policy != 'claude-only' or item['provider'] == 'claude')), None)
        if permitted is None:
            raise ValueError('no allowed provider route for role')
        key, replacement = permitted
        route = {**route, **replacement}
        if 'gear' in route:
            route['gear'] = int(key)
    if policy != 'claude-only' and adversarial and routing['adversarial']['cross_provider'] and route['provider'] == author:
        route = next((dict(item) for item in routing['adversarial']['routes'] if item['provider'] != author and item['provider'] in allowed), None)
        if route is None:
            raise ValueError('no different-provider adversarial route available')
    return route


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('mode', 'route'))
    parser.add_argument('--project')
    parser.add_argument('--routing')
    parser.add_argument('--role')
    parser.add_argument('--gear')
    parser.add_argument('--initial')
    parser.add_argument('--author', default='')
    parser.add_argument('--adversarial', action='store_true')
    args = parser.parse_args()
    try:
        policy = mode(args.project)
        if args.action == 'mode':
            print(policy)
        else:
            routing = json.loads(Path(args.routing).read_text())
            initial = json.loads(args.initial) if args.initial else None
            print(json.dumps(select_route(routing, args.role, args.gear, policy,
                                          args.author, args.adversarial, initial)))
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        print('nightshift-provider-policy: invalid policy or no permitted provider route', file=sys.stderr)
        return 64
    return 0


if __name__ == '__main__':
    sys.exit(main())
