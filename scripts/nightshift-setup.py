"""Lossless additive setup for the documented scalar manifest schema."""
import argparse
import json
import os
from pathlib import Path
import sys
import tomllib
import tempfile
import stat

parser = argparse.ArgumentParser()
parser.add_argument('--project', default=os.getcwd())
parser.add_argument('--read', action='store_true')
parser.add_argument('--migrate', action='store_true')
args = parser.parse_args()
project = Path(args.project)
canonical = project / '.nightshift.toml'
legacy = project / 'nightshift.toml'
source = canonical if canonical.exists() else legacy

def fail(code, message, missing=None):
    print(json.dumps(dict(status='failed', code=code, message=message, missing=missing or [])))
    sys.exit(1)

try:
    original = source.read_text() if source.exists() else ''
    data = tomllib.loads(original)
except (OSError, ValueError) as error:
    fail('CONFIG_INVALID', str(error))

defaults = {
    'ticket_source': {'provider': 'beads'},
    'providers': {'routing_file': 'routing.json'},
    'deployments.production': {'name': 'production', 'url': 'https://example.invalid', 'health_path': '/health'},
    'repair_budgets': dict.fromkeys(('implement', 'review', 'drift', 'qa'), 3),
    'policy': {'require_production_confirmation': True, 'require_removal_confirmation': True, 'allow_heuristic_production_target': False},
}
def section(name):
    result = data
    for part in name.split('.'):
        result = result.get(part, {})
        if not isinstance(result, dict):
            fail('CONFIG_INVALID', f'{name} must be a table')
    return result

missing = [(table, key, default) for table, fields in defaults.items()
           for key, default in fields.items() if section(table).get(key) in (None, '')]
runtime = section('runtime')
for key in ('provider', 'model', 'auth'):
    if key in runtime and not isinstance(runtime[key], str):
        fail('CONFIG_INVALID', f'runtime.{key} must be a string')
if runtime.get('provider', 'codex') not in ('codex', 'claude', 'local', 'ollama'):
    fail('CONFIG_INVALID', 'runtime.provider must be codex, claude, local, or ollama')
for key in ('local_model', 'file'):
    if key in section('routing') and not isinstance(section('routing')[key], str):
        fail('CONFIG_INVALID', f'routing.{key} must be a string')
if args.read:
    print(json.dumps(data))
    sys.exit(0)
if missing and not sys.stdin.isatty():
    fail('CONFIG_INCOMPLETE', 'Run nightshift setup in an interactive terminal', [f'{t}.{k}' for t, k, _ in missing])
route_file = section('providers').get('routing_file')
if route_file and not (project / route_file).is_file():
    fail('CONFIG_INCOMPLETE', 'Configured routing file does not exist; create it or update providers.routing_file', ['providers.routing_file'])
additions = {}
for table, key, default in missing:
    answer = input(f'{table}.{key} [{default}]: ').strip()
    if isinstance(default, bool) and answer and answer not in ('true', 'false'):
        fail('CONFIG_INVALID', f'{table}.{key} requires true or false')
    try:
        value = (answer.lower() == 'true') if isinstance(default, bool) and answer in ('true', 'false') else (int(answer) if isinstance(default, int) and not isinstance(default, bool) and answer else answer or default)
    except ValueError:
        fail('CONFIG_INVALID', f'{table}.{key} requires an integer')
    if table == 'repair_budgets' and value < 1:
        fail('CONFIG_INVALID', f'{table}.{key} requires a positive integer')
    additions.setdefault(table, {})[key] = value
if sys.stdin.isatty() and not args.migrate:
    provider = input(f'Runtime codex/claude/ollama [{runtime.get("provider", "codex")}]: ').strip() or runtime.get('provider', 'codex')
    if provider not in ('codex', 'claude', 'ollama', 'local'):
        fail('CONFIG_INVALID', 'Unknown runtime provider')
    additions.setdefault('runtime', {})['provider'] = provider
    additions.setdefault('runtime', {})['model'] = input(f'Model [{runtime.get("model", "runtime default")}]: ').strip() or runtime.get('model', '')
    if 'auth' not in runtime:
        additions.setdefault('runtime', {})['auth'] = 'subscription'

# Insert missing keys directly into existing tables, preserving every original line.
lines = original.splitlines(keepends=True)
for table, fields in additions.items():
    # Replace only explicitly configured scalar fields, leaving unrelated content intact.
    active = ''
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            active = stripped[1:-1]
        if active == table and '=' in line:
            key = line.split('=', 1)[0].strip()
            if key in fields:
                lines[i] = f'{key} = {json.dumps(fields.pop(key))}\n'
    block = ''.join(f'{key} = {json.dumps(value)}\n' for key, value in fields.items())
    index = next((i + 1 for i, line in enumerate(lines) if line.strip() == f'[{table}]'), None)
    if index is None:
        lines.extend([f'\n[{table}]\n', block])
    else:
        lines.insert(index, block)
content = ''.join(lines)
if content and not content.endswith('\n'):
    content += '\n'
try:
    completed = tomllib.loads(content)
    routing_path = project / completed.get('providers', {}).get('routing_file', 'routing.json')
    if not routing_path.is_file():
        template = Path(__file__).resolve().parent.parent / 'routing.json'
        if sys.stdin.isatty() and template.is_file() and routing_path == project / 'routing.json':
            with routing_path.open('x') as handle:
                handle.write(template.read_text())
        else:
            fail('CONFIG_INCOMPLETE', 'Configured routing file does not exist', ['providers.routing_file'])
    def private_file(text, prefix):
        fd, name = tempfile.mkstemp(prefix=prefix, dir=project)
        with os.fdopen(fd, 'w') as handle:
            mode = stat.S_IMODE(source.stat().st_mode) & 0o600 if source.exists() else 0o600
            os.fchmod(handle.fileno(), mode)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return Path(name)
    if not canonical.exists() or content != original:
        if canonical.exists():
            private_file(original, '.nightshift.toml.setup-backup-')
        temporary = private_file(content, '.nightshift.toml.setup-new-')
        try:
            if canonical.exists():
                if canonical.read_text() != original:
                    fail('CONFIG_CONFLICT', 'Configuration changed during setup; retry')
                os.replace(temporary, canonical)
            else:
                os.link(temporary, canonical)  # atomic no-clobber publication
        finally:
            temporary.unlink(missing_ok=True)
except (OSError, ValueError) as error:
    fail('CONFIG_WRITE_FAILED', str(error))
print(json.dumps(dict(status='ok', manifest=str(canonical), auth='subscription', legacy_preserved=legacy.exists())))
