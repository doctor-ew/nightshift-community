#!/usr/bin/env bash
# Exercise the real launcher with captured provider argv and isolated settings.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
with tempfile.TemporaryDirectory(prefix='nightshift-cli-') as temp:
    base = Path(temp)
    project = base / 'project'
    project.mkdir()
    home = base / 'home'
    home.mkdir()
    binary = base / 'bin'
    binary.mkdir()
    # A copy installation exercises the updater and symlink entrypoint too,
    # while keeping every lock and fixture write inside the temporary tree.
    installed = base / 'installed'
    shutil.copytree(root / 'scripts', installed / 'scripts')
    shutil.copytree(root / 'commands', installed / 'commands')
    for name in ('nightshift.toml', 'VERSION'):
        shutil.copy(root / name, installed / name)
    (binary / 'nightshift').symlink_to(installed / 'scripts/nightshift-factory.sh')
    calls = base / 'calls.jsonl'
    for name in ('codex', 'claude', 'ollama', 'bd'):
        stub = binary / name
        stub.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
with open(os.environ['CLI_CALLS'], 'a') as f:
    f.write(json.dumps({'name': name, 'args': sys.argv[1:]}) + '\\n')
if sys.argv[1:3] == ['login', 'status']:
    print('Logged in using ChatGPT')
elif name == 'claude' and sys.argv[1:2] == ['auth']:
    print(json.dumps({'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty'}))
elif name == 'bd':
    print(json.dumps({'id': 'bead-123', 'title': 'Fixture', 'status': 'open'}))
elif name in ('codex', 'claude'):
    if os.environ.get('CLI_HANG') == '1':
        import signal, time
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
    sys.exit(int(os.environ.get('CLI_EXIT', '0')))
''')
        stub.chmod(0o755)
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    shutil.copy(root / 'routing.json', project / 'routing.json')
    manifest = (root / 'nightshift.toml').read_text()
    manifest = re.sub(r'(?ms)^\[runtime[^\n]*\]\n.*?(?=^\[|\Z)', '', manifest)
    (project / 'prompt.md').write_text('# Fixture\nA bounded test requirement.\n')
    (project / 'prompt with spaces.md').write_text('# Spaces\nA second requirement.\n')
    env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
               HOME=str(home), NIGHTSHIFT_HOME=str(home), CLI_CALLS=str(calls),
               NIGHTSHIFT_SYNC_CHECK='off', NIGHTSHIFT_UPDATE_GUARD='',
               NIGHTSHIFT_DASHBOARD='off', NIGHTSHIFT_OUTPUT='verbose')

    def config(extra='', global_extra=''):
        (project / '.nightshift.toml').write_text(manifest + '\n' + extra)
        (home / '.nightshift.toml').write_text(global_extra)

    def run(*args, status=0, extra_env=None, cwd=None):
        calls.write_text('')
        result = subprocess.run([str(binary / 'nightshift'),
                                 *args, '--project', str(project), '--branch', 'none'],
                                cwd=cwd or project, env=env | (extra_env or {}),
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == status, (args, result.returncode, result.stdout, result.stderr)
        return [json.loads(line) for line in calls.read_text().splitlines()]

    def worker(records, name='codex'):
        selected = [r['args'] for r in records if r['name'] == name
                    and r['args'][:2] != ['login', 'status'] and r['args'][:1] != ['auth']]
        assert len(selected) == 1, records
        return selected[0]

    config()
    for mode in ('help', 'explain', 'architect', 'dev', 'pm', 'ux-designer',
                 'architecture', 'ux', 'bmad'):
        args = worker(run('codex', mode, 'Explain', 'this change'))
        assert f'# Nightshift {mode}' in args[-1]
        assert 'ARGUMENTS: Explain this change' in args[-1]
        assert 'inner Nightshift factory worker' not in args[-1]
        assert args[args.index('--sandbox') + 1] == (
            'workspace-write' if mode in ('architecture', 'ux') else 'read-only')
    assert '--json' in worker(run('codex', 'help', '--output', 'concise'))
    assert '--json' not in worker(run('codex', 'help', '--output', 'verbose'))
    assert '--output-format' in worker(run('claude', 'help', '--output', 'quiet'), 'claude')
    args = worker(run('codex', 'help'))
    assert '# Nightshift help' in args[-1]
    for model in ('qwen', 'devstral'):
        args = worker(run('codex/' + model, 'explain', 'bd:bead-123'))
        assert '--oss' in args and '# Nightshift explain' in args[-1]
    args = worker(run('claude', 'architect', 'Compare designs'), 'claude')
    assert '--tools' in args and 'Read,Grep,Glob' in args
    assert '--dangerously-skip-permissions' not in args
    assert '# Nightshift architect' in args[-1]
    assert '--output-format' in args and 'stream-json' in args
    assert not run('help', '--push', status=64)
    # Advisory questions work without a ticket baseline or generated manifest.
    (project / '.nightshift.toml').unlink()
    args = worker(run('codex', 'pm', 'Who is the user?'))
    assert '# Nightshift pm' in args[-1]
    assert not (project / '.nightshift.toml').exists()

    config('[runtime]\nprovider="codex"\nmodel="configured-codex"\n')
    args = worker(run('prompt.md'))
    assert args[args.index('--model') + 1] == 'configured-codex'
    assert '$nightshift prompt.md' in args[-1]
    assert str(installed / 'commands/nightshift-eng.md') in args[-1]
    args = worker(run('codex', 'prompt with spaces.md'))
    assert "$nightshift 'prompt with spaces.md'" in args[-1]
    config('[runtime]\nprovider="claude"\nmodel="configured-claude"\n'
           '[runtime.models]\ncodex="configured-codex"\n')
    args = worker(run('codex', 'gh:123'))
    assert args[args.index('--model') + 1] == 'configured-codex'
    args = worker(run('prompt.md'), 'claude')
    assert args[args.index('--model') + 1] == 'configured-claude'
    config('[runtime]\nprovider="claude"\nmodel="configured-claude"\n')
    assert '--model' not in worker(run('codex', 'prompt.md'))
    args = worker(run('codex', 'prompt.md', '--model', 'explicit'))
    assert args[args.index('--model') + 1] == 'explicit'
    worker(run('codex', 'prompt.md', '--provider', 'claude'), 'claude')
    config('[runtime.models]\ncodex="project-model"\n',
           '[runtime]\nprovider="codex"\n[runtime.models]\ncodex="global-model"\n')
    args = worker(run('prompt.md'))
    assert args[args.index('--model') + 1] == 'project-model'
    config('[runtime]\nprovider="claude"\n',
           '[runtime]\nprovider="codex"\nmodel="global-codex"\n')
    assert '--model' not in worker(run('prompt.md'), 'claude')
    config('[runtime]\nmodel="project-legacy"\n',
           '[runtime.models]\ncodex="global-model"\n')
    args = worker(run('codex', 'prompt.md'))
    assert args[args.index('--model') + 1] == 'project-legacy'
    config()
    worker(run('codex', 'bd:bead-123'))
    args = worker(run('codex', 'batch', 'gh:12,gh:13'))
    assert '$nightshift batch gh:12,gh:13 --branch none' in args[-1]
    assert run('codex', status=64) == []
    assert run('codex', 'prompt.md', 'extra.md', status=64) == []
    assert run('codex', 'spec:missing.md', status=65) == []
    records = run('codex', 'prompt.md', status=75, extra_env={'CLI_EXIT': '75'})
    worker(records)
    assert not any(r['name'] == 'claude' for r in records)
    config('[runtime.models]\ncodex=12\n')
    assert run('codex', 'prompt.md', status=1) == []
    alias = '[runtime.aliases.qwen]\nprovider="local"\nmodel="fixture-qwen:30b"\n'
    config(alias)
    records = run('codex/qwen', 'bd:bead-123')
    args = worker(records)
    assert args[args.index('--model') + 1] == 'fixture-qwen:30b'
    assert '--oss' in args and args[args.index('--local-provider') + 1] == 'ollama'
    assert not any(r['args'][:2] == ['login', 'status'] for r in records)
    assert not any('model_provider="openai"' in a for a in args)
    assert 'omit sandbox_permissions or set it to use_default' in args[-1]
    assert run('claude/qwen', 'prompt.md', status=64) == []
    args = worker(run('codex/qwen', 'prompt.md', '--model', 'explicit-hosted'))
    assert args[args.index('--model') + 1] == 'explicit-hosted' and '--oss' not in args
    config('', alias)
    assert '--oss' in worker(run('codex/qwen', 'prompt.md'))
    config(alias.replace('fixture-qwen:30b', 'project-qwen'), alias)
    args = worker(run('codex/qwen', 'prompt.md'))
    assert args[args.index('--model') + 1] == 'project-qwen'
    config()
    args = worker(run('codex/qwen', 'prompt.md'))
    assert args[args.index('--model') + 1] == 'qwen3-coder:30b' and '--oss' in args
    args = worker(run('codex/devstral', 'prompt.md'))
    assert args[args.index('--model') + 1] == 'devstral-small-2:24b' and '--oss' in args
    config('[runtime.aliases.my_coder]\nprovider="local"\nmodel="custom/model:tag"\n')
    args = worker(run('codex/my_coder', 'bd:bead-123'))
    assert args[args.index('--model') + 1] == 'custom/model:tag' and '--oss' in args
    config()
    args = worker(run('codex/org/model-name', 'prompt.md'))
    assert args[args.index('--model') + 1] == 'org/model-name'
    args = worker(run('claude/sonnet', 'gh:123'), 'claude')
    assert args[args.index('--model') + 1] == 'sonnet'
    args = worker(run('local/fixture-model', 'prompt.md'))
    assert '--oss' in args
    assert '--oss' in worker(run('ollama/fixture-model', 'prompt.md'))
    assert run('local', 'prompt.md', status=64) == []
    assert run('codex/', 'prompt.md', status=64) == []
    assert run('codex/qwen', status=64) == []
    (project / 'codex').mkdir()
    (project / 'codex' / 'prompt.md').write_text('# File, not runtime\nRequirement.\n')
    args = worker(run('codex/prompt.md', cwd=base))
    assert '--model' not in args and '$nightshift codex/prompt.md' in args[-1]
    for invalid in ('[runtime.aliases.qwen]\nprovider="local"\nmodel=12\n',
                    '[runtime.aliases.qwen]\nprovider="other"\nmodel="m"\n',
                    '[runtime.aliases]\nqwen="string"\n'):
        config(invalid)
        assert run('codex/qwen', 'prompt.md', status=1) == []
    config()
    (project / 'budget-test.md').write_text('# Budget termination fixture\nBounded task.\n')
    budget_env = {'NIGHTSHIFT_TICKET_MAX_ACTIVE_SECONDS': '1', 'CLI_HANG': '1'}
    worker(run('codex', 'budget-test.md', status=143, extra_env=budget_env))
    # Restart retains exhausted allowance and never invokes another worker.
    records = run('codex', 'budget-test.md', status=75, extra_env=budget_env)
    assert not [r for r in records if r['name'] == 'codex' and r['args'][:2] != ['login', 'status']]
print('PASS: factory shorthand, runtime defaults, argv preservation, and failure boundaries')
PY
