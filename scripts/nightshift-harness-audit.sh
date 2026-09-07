#!/usr/bin/env bash
# Static artifact audit; Python's standard library supplies JSON and POSIX locking.
set -euo pipefail
exec python3 - "$0" "$@" <<'PY'
import datetime as dt
import fcntl
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

TRUSTED = Path(sys.argv[1]).resolve().parent
UTC = dt.timezone.utc
RUBRIC = {
    'tool_coverage': {
        'capability_helper': ('scripts/nightshift-capability.sh', ['--has', '--refresh']),
        'provider_dispatch': ('scripts/nightshift-agent.sh', ['routing.json', 'claude)', 'codex|local)'])},
    'context_efficiency': {
        'context_guard': ('scripts/nightshift-context-check.sh', ['CLAUDE_CONTEXT_REMAINING_PERCENT']),
        'digest': ('scripts/nightshift-spec-digest.sh', ['SPEC-DIGEST'])},
    'quality_gates': {
        'review_integrity': ('commands/nightshift-review.md', ['nightshift-tdd-integrity-check.sh']),
        'drift_gate': ('commands/nightshift-drift.md', ['BLOCK'])},
    'memory_persistence': {
        'state_resolver': ('scripts/nightshift-state-dir.sh', ['.nightshift', '.claude/task-progress']),
        'trend_log': ('commands/nightshift-review.md', ['review-history.jsonl', 'timestamp'])},
    'eval_coverage': {
        'state_tests': ('tests/test-state-dir.sh', ['assert_eq', 'nightshift-state-dir.sh']),
        'dispatch_tests': ('tests/test-agent-dispatch.sh', ['nightshift-agent.sh', 'test -f'])},
    'security_guardrails': {
        'scope_guard': ('scripts/nightshift-scope-freeze.sh', ['.active-scope', 'BLOCKED']),
        'spec_guard': ('scripts/nightshift-spec-guardrail.sh', ['## Sources', '## Model Router'])},
    'cost_efficiency': {
        'routing_gears': ('routing.json', []),
        'review_cache': ('commands/nightshift-review.md', ['DIFF_SHA', 'CACHE_HIT'])}}
DIAGNOSTICS = ('provider_cli', 'instructions', 'hooks', 'manifest', 'git_worktree', 'stale_instructions')


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        raise ValueError('timestamp must be UTC YYYY-MM-DDTHH:MM:SSZ')
    return dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def parse_json(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON number')))


def validate(row):
    required = {'schema_version', 'task', 'timestamp', 'mode', 'cache_hit', 'counts', 'scores', 'deltas', 'checks', 'doctor', 'bead'}
    if not isinstance(row, dict) or not required <= row.keys():
        raise ValueError('missing envelope fields')
    if type(row['schema_version']) is not int or row['schema_version'] != 1 or row['task'] != 'harness-audit' or row['mode'] not in ('audit', 'monthly') or row['cache_hit'] is not False:
        raise ValueError('invalid envelope')
    timestamp(row['timestamp'])
    for field in ('counts', 'scores', 'deltas', 'checks'):
        if not isinstance(row[field], dict) or set(row[field]) != set(RUBRIC):
            raise ValueError('invalid ' + field + ' categories')
    for category, predicates in RUBRIC.items():
        score = row['scores'][category]
        delta = row['deltas'][category]
        checks = row['checks'][category]
        counts = row['counts'][category]
        if not number(score) or not 0 <= score <= 10:
            raise ValueError('invalid score')
        if delta is not None and (not number(delta) or not -10 <= delta <= 10):
            raise ValueError('invalid delta')
        if not isinstance(checks, dict) or set(checks) != set(predicates) or any(type(v) is not bool for v in checks.values()):
            raise ValueError('invalid checks')
        if not isinstance(counts, dict) or set(counts) != {'BLOCK', 'WARN', 'NOTE'} or any(type(v) is not int for v in counts.values()) or counts['BLOCK'] != 0 or counts['NOTE'] != 0 or not 0 <= counts['WARN'] <= 2:
            raise ValueError('invalid counts')
    doctor = row['doctor']
    if not isinstance(doctor, dict) or type(doctor.get('ok')) is not bool:
        raise ValueError('invalid doctor')
    for name in DIAGNOSTICS:
        record = doctor.get(name)
        if not isinstance(record, dict) or type(record.get('ok')) is not bool or not isinstance(record.get('explanation'), str):
            raise ValueError('invalid doctor diagnostic ' + name)
    bead = row['bead']
    if not isinstance(bead, dict) or bead.get('status') not in ('not_requested', 'not_needed', 'created', 'existing', 'pending'):
        raise ValueError('invalid bead')
    if row['mode'] == 'audit':
        if bead['status'] != 'not_requested':
            raise ValueError('invalid audit bead status')
    else:
        month = row['timestamp'][:7]
        if bead['status'] == 'not_requested' or bead.get('month') != month or bead.get('external_ref') != 'nightshift:harness-audit:' + month:
            raise ValueError('invalid monthly receipt')
    if bead['status'] in ('created', 'existing') and not bead_id(bead.get('id')):
        raise ValueError('invalid bead id')
    if bead['status'] == 'pending' and (not isinstance(bead.get('error'), str) or not bead['error']):
        raise ValueError('missing pending error')


def bead_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', value))


def run(args, cwd):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(args, 1, '', str(error))


def helper(name, args, project):
    return run(['bash', str(TRUSTED / name)] + args, project)


def content(project, relative):
    try:
        path = (project / relative).resolve()
        path.relative_to(project)
        if not path.is_file():
            return ''
        return path.read_text(encoding='utf-8')
    except (OSError, ValueError, UnicodeError, RuntimeError):
        return ''


def diagnose(project, routing, refresh):
    records = {}
    def record(name, ok, explanation):
        records[name] = {'ok': bool(ok), 'explanation': explanation}
    refresh_result = helper('nightshift-capability.sh', ['--refresh'], project) if refresh else None
    providers = routing.get('providers', {}) if isinstance(routing, dict) else {}
    availability = {}
    if isinstance(providers, dict):
        for provider in providers:
            tools = {'claude': ['claude'], 'codex': ['codex'], 'local': ['codex', 'ollama']}.get(provider, [])
            availability[provider] = bool(tools) and all(helper('nightshift-capability.sh', ['--has', tool], project).returncode == 0 for tool in tools)
    record('provider_cli', bool(availability) and all(availability.values()) and (refresh_result is None or refresh_result.returncode == 0),
           'Fixed capability probes (routing commands are never executed): ' + json.dumps(availability, sort_keys=True))
    home = Path(os.environ.get('HOME', str(Path.home())))
    codex = Path(os.environ.get('CODEX_HOME', str(home / '.codex')))
    claude = home / '.claude'
    installs = [codex / 'skills' / 'nightshift' / 'SKILL.md']
    installs += list((claude / 'commands').glob('nightshift-*.md'))
    installs += list((codex / 'commands').glob('nightshift-*.md'))
    present = [p for p in installs if p.is_file()]
    record('instructions', bool(present), 'Installed nightshift skills/commands: ' + ', '.join(map(str, present)) if present else 'No installed nightshift skill or commands found')
    hooks = []
    for base in (codex, claude):
        for name in ('settings.json', 'config.toml'):
            try:
                value = (base / name).read_text()
                if 'nightshift-' in value and ('hooks' in value or 'hook' in value):
                    hooks.append(str(base / name))
            except (OSError, UnicodeError):
                pass
    record('hooks', bool(hooks), 'Hook references inspected without execution: ' + ', '.join(hooks) if hooks else 'No installed nightshift hook references found')
    conflicts = []
    for base in (codex, claude):
        for old in (base / 'commands').glob('*.md'):
            if old.name.startswith('nightshift-') or '-' not in old.stem:
                continue
            replacement = old.with_name('nightshift-' + old.name.split('-', 1)[1])
            if not replacement.is_file():
                continue
            try:
                text = old.read_text()
                # Other products may use the same stage suffix. Only inspect
                # aliases that explicitly claim to delegate to this runtime.
                if 'nightshift' not in text.lower():
                    continue
                # Shipped migration adapters explicitly delegate to Nightshift.
                compatibility = 'nightshift' in text.lower() and any(word in text.lower() for word in ('compatib', 'deprecated', 'delegate', 'migration', 'migrat', 'alias'))
                if not compatibility and text != replacement.read_text():
                    conflicts.append(str(old))
            except (OSError, UnicodeError):
                conflicts.append(str(old))
    record('stale_instructions', not conflicts, 'Conflicting legacy instruction copies: ' + ', '.join(conflicts) if conflicts else 'No conflicting legacy instruction copies found; compatibility adapters are allowed')
    manifest = helper('nightshift-manifest-validate.sh', ['--project', str(project)], project)
    record('manifest', manifest.returncode == 0, (manifest.stdout or manifest.stderr).strip() or 'Manifest validator returned no explanation')
    git = run(['git', 'worktree', 'list', '--porcelain'], project)
    record('git_worktree', git.returncode == 0, 'Fixed git worktree list succeeded' if git.returncode == 0 else git.stderr.strip() or 'Git worktree support unavailable')
    return {'ok': all(value['ok'] for value in records.values()), **records}


def filing(project, month, regressions, history):
    ref = 'nightshift:harness-audit:' + month
    receipt = {'status': 'not_needed', 'month': month, 'external_ref': ref}
    if not regressions:
        return receipt
    for row in reversed(history):
        previous = row['bead']
        if row['mode'] == 'monthly' and previous.get('external_ref') == ref and previous['status'] in ('created', 'existing'):
            return {**receipt, 'status': 'existing', 'id': previous['id']}
    try:
        if helper('nightshift-capability.sh', ['--has', 'bd'], project).returncode:
            raise ValueError('bd is missing or unusable according to capability helper')
        resolved = helper('nightshift-capability.sh', ['--which', 'bd'], project)
        executable = resolved.stdout.strip()
        if resolved.returncode or not executable or '\n' in executable:
            raise ValueError('capability helper could not resolve bd')
        # The capability cache returns an executable path, never a shell command.
        result = run([executable, 'list', '--all', '--limit', '0', '--json'], project)
        if result.returncode:
            raise ValueError('bd lookup failed: ' + result.stderr.strip())
        rows = parse_json(result.stdout)
        if not isinstance(rows, list) or any(
                not isinstance(row, dict) or not bead_id(row.get('id')) or
                (row.get('external_ref') is not None and not isinstance(row['external_ref'], str))
                for row in rows):
            raise ValueError('bd lookup did not return valid bead objects')
        matches = [row for row in rows if row.get('external_ref') == ref]
        if matches:
            if not bead_id(matches[0].get('id')):
                raise ValueError('exact-ref lookup has no verifiable bead ID')
            return {**receipt, 'status': 'existing', 'id': matches[0]['id']}
        description = 'Static harness artifact regressions for ' + month + ':\n' + '\n'.join(
            '{}: current={}, prior={}, delta={}'.format(category, current, prior, delta)
            for category, current, prior, delta in regressions)
        result = run([executable, 'create', '--title', 'Harness audit regressions ' + month,
                      '--description', description, '--external-ref', ref, '--json'], project)
        if result.returncode:
            raise ValueError('bd create failed: ' + result.stderr.strip())
        created = parse_json(result.stdout)
        if not isinstance(created, dict) or not bead_id(created.get('id')) or created.get('external_ref', ref) != ref:
            raise ValueError('bd create succeeded without a verifiable bead ID')
        return {**receipt, 'status': 'created', 'id': created['id']}
    except (ValueError, TypeError) as error:
        return {**receipt, 'status': 'pending', 'error': str(error)}


def main():
    args = sys.argv[2:]
    project_arg = None
    refresh = monthly = False
    while args:
        option = args.pop(0)
        if option == '--project' and args and project_arg is None:
            project_arg = args.pop(0)
        elif option == '--refresh' and not refresh:
            refresh = True
        elif option == '--monthly' and not monthly:
            monthly = True
        else:
            raise ValueError('usage: nightshift-harness-audit.sh --project DIR [--refresh] [--monthly]')
    if project_arg is None or not project_arg or '\n' in project_arg or '\r' in project_arg:
        raise ValueError('--project requires a directory')
    project = Path(project_arg).resolve()
    if not project.is_dir():
        raise ValueError('project directory does not exist')
    now_text = os.environ.get('NIGHTSHIFT_AUDIT_NOW', dt.datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'))
    now = timestamp(now_text)
    try:
        routing = parse_json(content(project, 'routing.json'))
    except ValueError:
        routing = {}
    roles = routing.get('roles') if isinstance(routing, dict) else None
    valid_gears = isinstance(roles, dict) and bool(roles) and all(isinstance(role, dict) and isinstance(role.get('gears'), dict) and bool(role['gears']) for role in roles.values())
    checks = {category: {check: bool(valid_gears) if check == 'routing_gears' else bool(value := content(project, path)) and all(token in value for token in tokens)
                         for check, (path, tokens) in predicates.items()}
              for category, predicates in RUBRIC.items()}
    scores = {category: 5 * sum(values.values()) for category, values in checks.items()}
    state_result = helper('nightshift-state-dir.sh', ['--project', str(project)], project)
    if state_result.returncode or not state_result.stdout.strip():
        raise ValueError('state directory resolution failed: ' + state_result.stderr.strip())
    state = Path(state_result.stdout.strip())
    state.mkdir(parents=True, exist_ok=True)
    history_path = state / 'harness-history.jsonl'
    with (state / 'harness-history.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        history = []
        if history_path.exists():
            with history_path.open() as source:
                for line_number, line in enumerate(source, 1):
                    try:
                        if not line.endswith('\n'):
                            raise ValueError('truncated physical line')
                        row = parse_json(line)
                        validate(row)
                    except (ValueError, TypeError, KeyError) as error:
                        raise ValueError('invalid history line {}: {}'.format(line_number, error)) from error
                    history.append(row)
        earlier = [row for row in history if timestamp(row['timestamp']) < now]
        if monthly:
            previous_month = (now.replace(day=1) - dt.timedelta(days=1)).strftime('%Y-%m')
            earlier = [row for row in earlier if row['timestamp'][:7] == previous_month and row['bead']['status'] != 'pending']
        baseline = max(earlier, key=lambda row: row['timestamp'], default=None)
        deltas = {category: scores[category] - baseline['scores'][category] if baseline else None for category in RUBRIC}
        regressions = [(category, scores[category], baseline['scores'][category], delta) for category, delta in deltas.items() if delta is not None and delta < -1]
        doctor = diagnose(project, routing, refresh)
        bead = filing(project, now.strftime('%Y-%m'), regressions, earlier if not monthly else [row for row in history if timestamp(row['timestamp']) <= now]) if monthly else {'status': 'not_requested'}
        row = {'schema_version': 1, 'task': 'harness-audit', 'timestamp': now_text,
               'mode': 'monthly' if monthly else 'audit', 'cache_hit': False,
               'counts': {category: {'BLOCK': 0, 'WARN': 2 - sum(values.values()), 'NOTE': 0} for category, values in checks.items()},
               'scores': scores, 'deltas': deltas, 'checks': checks, 'doctor': doctor, 'bead': bead}
        validate(row)
        encoded = json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
        with history_path.open('a') as destination:
            destination.write(encoded)
            destination.flush()
            os.fsync(destination.fileno())
        sys.stdout.write(encoded)
        return 1 if bead['status'] == 'pending' else 0


try:
    sys.exit(main())
except (OSError, ValueError, RuntimeError) as error:
    print('nightshift-harness-audit: ' + str(error), file=sys.stderr)
    sys.exit(1)
PY
