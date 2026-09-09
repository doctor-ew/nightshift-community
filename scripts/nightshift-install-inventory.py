#!/usr/bin/env python3
"""Pure, shared source-to-installation mappings. No ownership-file discovery."""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import sys


def make_inventory(project, runtime, targets):
    """Return versioned file/tree operations in installer order."""
    if runtime not in ('codex', 'claude', 'local', 'all'):
        raise ValueError('invalid runtime')
    project = Path(project).resolve(strict=True)
    roots = {key: Path(targets[key]).resolve()
             for key in ('claude', 'codex', 'nightshift', 'bin')}
    entries = []

    def checked(relative):
        path = project / relative
        # Validate each ancestor before any directory enumeration. Internal links
        # are permitted; the scanner applies its stricter per-artifact checks.
        current = project
        pending = deque(Path(relative).parts)
        hops = 0
        while pending:
            part = pending.popleft()
            if part == '..':
                current = current.parent
                if not current.is_relative_to(project):
                    raise ValueError('source escapes project')
                continue
            if part == '.':
                continue
            candidate = current / part
            candidate.lstat()
            if candidate.is_symlink():
                hops += 1
                if hops > 40:
                    raise ValueError('source link cycle')
                target = Path(os.readlink(candidate))
                if target.is_absolute():
                    try:
                        target = target.relative_to(project)
                    except ValueError:
                        raise ValueError('source escapes project') from None
                    current = project
                pending.extendleft(reversed(target.parts))
            else:
                current = candidate
        return path

    def family(directory, suffix, prefix='nightshift-'):
        root = checked(directory)
        names = sorted(os.listdir(root))
        selected = []
        for name in names:
            if not name.endswith(suffix):
                continue
            if not name.startswith(prefix):
                if directory in ('commands', 'agents') or suffix == '.sh':
                    raise ValueError('invalid installed namespace')
                continue
            relative = directory + '/' + name
            path = checked(relative)
            if not path.is_file():
                raise ValueError('unsupported source artifact')
            selected.append(relative)
        if not selected:
            raise ValueError('missing source family')
        return selected

    def add(category, source, root, destination=None, kind='file'):
        path = checked(source)
        if (kind == 'file' and not path.is_file()) or (kind == 'tree' and not path.is_dir()):
            raise ValueError('unsupported source artifact')
        destination = destination or source
        entries.append({'category': category, 'kind': kind,
                        'source': str(path), 'destination': str(roots[root] / destination),
                        'source_relative': source, 'logical_path': root + '/' + destination})

    commands = family('commands', '.md')
    scripts = family('scripts', '.sh')
    helpers = family('scripts', '.py')
    contracts = family('contracts', '.schema.json')
    agents = family('agents', '.md')
    if runtime in ('claude', 'all'):
        for source in commands:
            add('claude_commands', source, 'claude')
    add('shared', 'docs/PROJECT-CONTEXT.md', 'nightshift', 'docs/nightshift-project-context.md')
    add('shared', 'docs/BEHAVIOR-PROOF.md', 'nightshift', 'docs/nightshift-behavior-proof.md')
    add('shared', 'scripts/nightshift-contract.jq', 'nightshift')
    for source in helpers:
        add('shared', source, 'nightshift')
    add('shared', 'scripts/nightshift-branding-policy.json', 'nightshift')
    for source in contracts + scripts:
        add('shared', source, 'nightshift')
    for source in agents + ['routing.json', 'nightshift.toml']:
        add('shared_roles', source, 'nightshift')
    dashboard = checked('dashboard')
    if os.path.lexists(dashboard / 'dist'):
        add('shared_roles', 'dashboard/dist', 'nightshift', kind='tree')
        add('shared_roles', 'dashboard/server.py', 'nightshift')
    if runtime in ('claude', 'all'):
        add('claude_adapters', 'scripts/nightshift-project-context.py', 'claude')
        add('claude_adapters', 'scripts/nightshift-behavior-proof.py', 'claude')
        add('claude_adapters', 'scripts/nightshift-retry-budget.py', 'claude')
        for source in scripts + agents:
            add('claude_adapters', source, 'claude')
        add('claude_adapters', 'routing.json', 'claude', 'nightshift-routing.json')
        add('claude_adapters', 'scripts/nightshift-contract.jq', 'claude')
        for source in contracts:
            add('claude_adapters', source, 'claude')
    if runtime in ('codex', 'local', 'all'):
        add('codex_skill', 'skills/nightshift', 'codex', kind='tree')
    add('launcher', 'scripts/nightshift-factory.sh', 'bin', 'nightshift')
    return {'version': 1, 'entries': entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--runtime', choices=('codex', 'claude', 'local', 'all'), required=True)
    for flag in ('target', 'codex-target', 'nightshift-target', 'bin-target'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--nul', action='store_true')
    args = parser.parse_args()
    try:
        result = make_inventory(args.project, args.runtime,
                                {'claude': args.target, 'codex': args.codex_target,
                                 'nightshift': args.nightshift_target, 'bin': args.bin_target})
    except (OSError, ValueError, RuntimeError, KeyError):
        print(json.dumps({'status': 'error', 'reason': 'invalid_inventory'}))
        return 64
    if args.nul:
        for entry in result['entries']:
            for key in ('category', 'kind', 'source', 'destination'):
                sys.stdout.buffer.write(os.fsencode(entry[key]) + b'\0')
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
