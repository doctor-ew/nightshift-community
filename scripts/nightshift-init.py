"""Explicit, model-free initialization of a Nightshift project and Git baseline."""
import argparse
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
RUNTIMES = ('codex', 'claude', 'local', 'ollama')


def git(project, *args, check=True):
    return subprocess.run(['git', '--literal-pathspecs', '-C', str(project), *args],
                          capture_output=True, text=True, check=check)


def settings(directory):
    path = directory / '.nightshift.toml'
    if not path.exists():
        path = directory / 'nightshift.toml'
    return tomllib.loads(path.read_text()) if path.exists() else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='*', help='Optional runtime/model selector and directory')
    parser.add_argument('--project', type=Path)
    parser.add_argument('--profile', choices=('standard', 'workshop'))
    parser.add_argument('--provider', choices=RUNTIMES)
    parser.add_argument('--model')
    parser.add_argument('--include', action='append', default=[], metavar='FILE',
                        help='Explicit starter file to include in the baseline commit; repeatable')
    parser.add_argument('--mex', choices=('auto', 'off'), default='auto', help='Prepare MEX graph and install the pinned CLI if missing (default: auto)')
    parser.add_argument('--mex-timeout', type=int, default=60, help='Total MEX preparation allowance in seconds (1–600; default: 60)')
    args = parser.parse_args()
    if not 1 <= args.mex_timeout <= 600:
        parser.error('--mex-timeout must be between 1 and 600')
    selector = ''
    directory = args.project
    for value in args.targets:
        if value.split('/', 1)[0] in RUNTIMES and not Path(value).is_dir() and not selector:
            selector = value
        elif directory is None:
            directory = Path(value)
        else:
            parser.error('expected at most one runtime selector and one directory')
    project = (directory or Path.cwd()).resolve()
    if project.exists() and not project.is_dir():
        raise ValueError('project must be a directory')
    provider, separator, suffix = selector.partition('/')
    if separator and not suffix:
        raise ValueError('runtime/model selector requires a model or alias')
    provider = args.provider or provider or ('claude' if args.profile == 'workshop' else '')
    model = args.model or suffix
    current = settings(project)
    home = Path(os.environ.get('NIGHTSHIFT_HOME', str(Path.home() / '.nightshift')))
    aliases = {}
    for config in (tomllib.loads((ROOT / "nightshift.toml").read_text()), settings(home), current):
        aliases.update(config.get('runtime', {}).get('aliases', {}))
    if suffix and args.model is None and suffix in aliases:
        alias = aliases[suffix]
        if not isinstance(alias, dict) or set(alias) != {'provider', 'model'}:
            raise ValueError('invalid model alias')
        selected = alias['provider']
        if provider not in (selected, 'codex') and not (provider == 'ollama' and selected == 'local'):
            raise ValueError('model alias is incompatible with selected runtime')
        provider, model = selected, alias['model']
    if provider == 'ollama':
        provider = 'local'
    if provider and provider not in RUNTIMES:
        raise ValueError('unsupported runtime in alias')
    if model and not provider:
        provider = current.get('runtime', {}).get('provider') or settings(home).get('runtime', {}).get('provider', 'codex')
    includes = []
    for value in args.include:
        path = project / value
        resolved = path.resolve()
        if not resolved.is_relative_to(project) or '.git' in resolved.relative_to(project).parts or path.is_symlink() or not path.is_file():
            raise ValueError('--include must name a regular file within the project, outside .git')
        includes.append(str(path.relative_to(project)))
    if project.exists():
        top = git(project, 'rev-parse', '--show-toplevel', check=False)
        if top.returncode == 0 and Path(top.stdout.strip()).resolve() != project:
            raise ValueError('target is inside another Git repository; use its root or a separate directory')
        if top.returncode == 0:
            if git(project, 'diff', '--cached', '--name-only').stdout.strip():
                raise ValueError('existing staged changes found; commit or unstage them before init')
            if git(project, 'diff', '--name-only', '--', '.nightshift.toml', 'routing.json', *includes).stdout.strip():
                raise ValueError('existing edits to initialization files found; commit them before init')
    # Check identity before creating files; do not invent identity or change Git config.
    for key in ('user.name', 'user.email'):
        result = git(project if project.exists() else Path.cwd(), 'config', key, check=False)
        if not result.stdout.strip() and not os.environ.get('GIT_AUTHOR_' + ('NAME' if key.endswith('name') else 'EMAIL')):
            raise ValueError(f'configure git {key} before init can create a baseline')
    project.mkdir(parents=True, exist_ok=True)
    if git(project, 'rev-parse', '--show-toplevel', check=False).returncode:
        git(project, 'init', '-b', 'main')
    before = {name: (project / name).read_bytes() if (project / name).exists() else None
              for name in ('.nightshift.toml', 'routing.json')}
    command = [sys.executable, str(ROOT / 'scripts/nightshift-setup.py'), '--project', str(project),
               '--defaults', '--ticket-ref', 'spec:starter']
    if args.profile:
        command += ['--workflow-profile', args.profile]
    if provider:
        command += ['--runtime-provider', provider, '--runtime-model', model or '']
    subprocess.run(command, check=True)
    subprocess.run(['bash', str(ROOT / 'scripts/nightshift-manifest-validate.sh'), '--project', str(project)], check=True)
    files = list(includes)
    for name, old in before.items():
        path = project / name
        if path.exists() and (path.read_bytes() != old or git(project, 'ls-files', '--', name).stdout.strip() == ''):
            files.append(name)
    files = sorted(set(files))
    if files:
        git(project, 'add', '--', *files)
        if git(project, 'diff', '--cached', '--name-only').stdout.strip():
            git(project, 'commit', '-m', 'chore: initialize Nightshift project')
    git(project, 'rev-parse', '--verify', 'HEAD^{commit}')
    graph_ignore = project/'.mex/.gitignore'
    graph_ignore_existed = graph_ignore.exists()
    mex = {'status': 'disabled', 'model_started': False}
    if args.mex == 'auto':
        spec = importlib.util.spec_from_file_location('mex', ROOT/'scripts/nightshift-mex.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        print('nightshift init: checking MEX and preparing graph (bounded to '+str(args.mex_timeout)+' seconds).', file=sys.stderr)
        mex = module.prepare(project, args.mex_timeout)
        print('nightshift init: MEX '+mex['status']+' ('+str(mex['elapsed_seconds'])+'s); '+mex.get('reason', mex['action']), file=sys.stderr)
    if not graph_ignore_existed and graph_ignore.is_file() and not graph_ignore.is_symlink():
        git(project, 'add', '--', '.mex/.gitignore')
        git(project, 'commit', '-m', 'chore: ignore derived MEX indexes')
        files.append('.mex/.gitignore')
    print(json.dumps({'status': 'ready', 'project': str(project), 'mex': mex,
                      'baseline': git(project, 'rev-parse', 'HEAD').stdout.strip(),
                      'included_files': files, 'model_started': False}))
    print('Next: nightshift <brief.md or ticket-ref> (add a runtime selector to override saved settings).')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, 'stderr', None) or str(error)
        print('nightshift init: ' + detail.strip(), file=sys.stderr)
        sys.exit(64)
