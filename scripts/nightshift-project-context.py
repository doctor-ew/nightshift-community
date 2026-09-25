#!/usr/bin/env python3
"""Read-only project identity and convention discovery; never execute project text."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tomllib


class ContextError(ValueError):
    pass


def directory(value):
    try:
        path = Path(value).resolve(strict=True)
    except (OSError, ValueError, RuntimeError) as exc:
        raise ContextError('PROJECT_INVALID') from exc
    if not path.is_dir() or any(c in str(path) for c in '\n\r\0'):
        raise ContextError('PROJECT_INVALID')
    return path


def resolve_project(explicit=None, cwd_default=False):
    if explicit is not None:
        return directory(explicit)
    neutral = os.environ.get('NIGHTSHIFT_PROJECT_DIR')
    legacy = os.environ.get('CLAUDE_PROJECT_DIR')
    if neutral and legacy and directory(neutral) != directory(legacy):
        raise ContextError('PROJECT_CONFLICT')
    if neutral or legacy:
        return directory(neutral or legacy)
    if not cwd_default:
        result = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                                capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return directory(result.stdout.strip())
    return directory(Path.cwd())


def manifest_path(project):
    """Prefer checkout configuration; inherit the primary checkout only when absent.

    Relative configuration paths belong to this manifest's directory. Workspace
    paths (source, tests and evidence) still belong to the requested worktree.
    A dangling canonical path is an error, never permission to fall back.
    """
    project = Path(project).resolve()
    roots = [project]
    result = subprocess.run(['git', '-C', str(project), 'rev-parse',
                             '--path-format=absolute', '--show-toplevel', '--git-common-dir'],
                            capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        top, common = map(Path, result.stdout.splitlines())
        roots.append(top)
        if common.name == '.git':
            roots.append(common.parent)
    for root in dict.fromkeys(roots):
        for name in ('.nightshift.toml', 'nightshift.toml'):
            path = root / name
            if path.exists() or path.is_symlink():
                return path
    return project / 'nightshift.toml'


def discover(project, scope=None):
    target = directory(project / scope if scope else project)
    if not target.is_relative_to(project):
        raise ContextError('SCOPE_OUTSIDE_PROJECT')
    ancestors = [project]
    for part in target.relative_to(project).parts:
        ancestors.append(ancestors[-1] / part)
    conventions = []
    for ancestor in ancestors:
        for name in ('AGENTS.md', 'CLAUDE.md'):
            path = ancestor / name
            if path.exists() or path.is_symlink():
                try:
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(project) or not resolved.is_file():
                        raise ContextError('CONVENTION_INVALID')
                    # Validate readability without interpreting instructions as code.
                    resolved.read_text(encoding='utf-8')
                except (OSError, UnicodeError, RuntimeError) as exc:
                    raise ContextError('CONVENTION_INVALID') from exc
                conventions.append(str(path))
    manifest = manifest_path(project)
    command = None
    if manifest.exists() or manifest.is_symlink():
        try:
            data = tomllib.loads(manifest.read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeError) as exc:
            raise ContextError('MANIFEST_INVALID') from exc
        tests = data.get('tests', {})
        if not isinstance(tests, dict):
            raise ContextError('TEST_COMMAND_INVALID')
        if 'command' in tests:
            command = tests['command']
            if (not isinstance(command, str) or not command.strip()
                    or any(c in command for c in '\0\r\n')):
                raise ContextError('TEST_COMMAND_INVALID')
    else:
        manifest = None
    return dict(status='ok', project=str(project), conventions=conventions,
                manifest=str(manifest) if manifest else None, test_command=command,
                test_command_source=str(manifest) if command is not None else None,
                convention_policy='runtime_review_required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project')
    parser.add_argument('--scope')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--root-only', action='store_true')
    modes.add_argument('--shell', action='store_true')
    parser.add_argument('--cwd-default', action='store_true')
    args = parser.parse_args()
    try:
        project = resolve_project(args.project, args.cwd_default)
        if args.root_only:
            print(project)
        elif args.shell:
            print('export NIGHTSHIFT_PROJECT_DIR=' + shlex.quote(str(project)))
            print('unset CLAUDE_PROJECT_DIR')
        else:
            print(json.dumps(discover(project, args.scope)))
    except (ContextError, OSError) as exc:
        code = str(exc) if isinstance(exc, ContextError) else 'CONTEXT_UNAVAILABLE'
        print(json.dumps(dict(status='blocked', code=code)),
              file=sys.stderr if args.root_only or args.shell else sys.stdout)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
