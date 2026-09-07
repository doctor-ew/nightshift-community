#!/usr/bin/env python3
"""Record offline trajectories of the real shell boundaries, with sealed stubs."""
import argparse
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile

SCENARIOS = ('success', 'repaired-success', 'exhausted-failure', 'missing-isolation',
             'needs-decision', 'deny-removal', 'deny-production', 'adversarial-route')
ROOT = Path(__file__).resolve().parents[1]
REASONS = {'normal command inside assigned worktree is unattended',
           'production deployment requires a fresh confirmation token',
           'fresh production confirmation token accepted',
           'permanent-removal is denied by factory policy',
           'history-rewrite is denied by factory policy', 'unknown action'}
MODELS = {'gpt-5.4', 'haiku', 'sonnet', 'opus'}
NEXT = {'continue to the next gate': 'continue',
        'inspect the final gate output and repair the smallest in-scope cause': 'inspect-and-repair',
        'Configure NIGHTSHIFT_WORKER_IMAGE; host execution is disabled.': 'configure-isolation'}


def require(condition):
    if not condition:
        raise ValueError('invalid trajectory evidence')


def enum(value, choices):
    require(isinstance(value, str) and value in choices)
    return value


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= 255)
    return value


def validate(record):
    """Validate baseline as strictly as output: unknown fields never survive."""
    require(type(record) is dict)
    keys = set(record)
    common = {'tool_order'}
    if 'status' in record:
        require(keys == common | {'status', 'gate', 'repair_budget', 'attempts',
                                 'policy_decisions', 'next_action_category'})
        enum(record['status'], {'complete', 'blocked', 'failed', 'needs-decision'})
        enum(record['gate'], {'implement', 'review', 'drift', 'qa'})
        integer(record['repair_budget'], 1)
        enum(record['next_action_category'], set(NEXT.values()))
        require(type(record['attempts']) is list)
        for item in record['attempts']:
            require(type(item) is dict)
            step = set(item) & {'attempt', 'repair_after_attempt'}
            require(len(step) == 1)
            require(set(item) == step | {'exit_code', 'invocation', 'worker_execution'})
            integer(item[next(iter(step))], 1)
            integer(item['exit_code'])
            enum(item['invocation'], {'isolation'})
            enum(item['worker_execution'], {'confirmed', 'unknown'})
    elif 'route' in record:
        require(keys == common | {'route'})
        require(type(record['route']) is dict and set(record['route']) == {'provider', 'model'})
        enum(record['route']['provider'], {'codex', 'claude', 'local'})
        enum(record['route']['model'], MODELS)
    else:
        require(keys == common | {'policy_decisions'})
    if 'policy_decisions' in record:
        require(type(record['policy_decisions']) is list)
        for item in record['policy_decisions']:
            require(type(item) is dict and set(item) == {'action', 'decision', 'reason'})
            enum(item['action'], {'worktree-command', 'permanent-removal', 'production-deploy', 'history-rewrite'})
            enum(item['decision'], {'allow', 'deny'})
            enum(item['reason'], REASONS)
    require(type(record['tool_order']) is list)
    for tool in record['tool_order']:
        enum(tool, {'policy_check', 'isolation_run', 'provider_dispatch'})
    return record


def executable(path, body):
    path.write_text(body)
    path.chmod(0o755)


def record(scenario, root=ROOT):
    require(scenario in SCENARIOS)
    with tempfile.TemporaryDirectory(prefix='nightshift-trajectory-') as temporary:
        box = Path(temporary)
        scripts = box / 'scripts'
        scripts.mkdir()
        for name in ('controller.sh', 'policy.sh', 'isolate.sh', 'credentials.sh', 'agent.sh', 'contract.jq'):
            shutil.copyfile(Path(root) / 'scripts' / ('nightshift-' + name), scripts / ('nightshift-' + name))
        # Copy only dispatcher assets, never repository tests or user configuration.
        for directory, name in (('contracts', 'nightshift-engineer.schema.json'),
                                ('agents', 'nightshift-engineer.md')):
            (box / directory).mkdir()
            shutil.copyfile(Path(root) / directory / name, box / directory / name)
        shutil.copyfile(Path(root) / 'routing.json', box / 'routing.json')
        trace = box / 'trace'
        trace.touch()
        for name, event in (('policy', 'policy_check'), ('isolate', 'isolation_run')):
            target = scripts / ('nightshift-' + name + '.sh')
            target.rename(target.with_suffix('.real'))
            executable(target, '#!/bin/bash\nprintf "%s\\n" ' + event + ' >> ' + shlex.quote(str(trace)) + '\nexec bash "${0%.sh}.real" "$@"\n')
        bins = box / 'bin'
        bins.mkdir()
        # PATH is constructed from individual safe tools, never inherited. No real
        # docker, provider, network utility or shell startup file is reachable.
        for name in ('bash', 'jq', 'awk', 'cat', 'chmod', 'cut', 'date', 'dirname',
                     'git', 'id', 'mkdir', 'mktemp', 'mv', 'rm', 'rmdir', 'seq', 'sleep', 'tail', 'tr'):
            target = shutil.which(name, path='/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin')
            require(target is not None)
            (bins / name).symlink_to(target)
        (bins / 'python3').symlink_to(sys.executable)
        # Stable non-root identity also supports root-run offline CI containers.
        (bins / 'id').unlink()
        executable(bins / 'id', '#!/bin/bash\nprintf "1000\\n"\n')
        stub = '''#!PYTHON
import json, pathlib, sys
box = pathlib.Path(__file__).resolve().parent.parent
args = sys.argv[1:]
name = pathlib.Path(sys.argv[0]).name
if name == 'codex' and args == ['login', 'status']:
    print('Logged in using ChatGPT')
    sys.exit(0)
if name == 'claude' and args == ['auth', 'status', '--json']:
    print(json.dumps(dict(loggedIn=True, authMethod='claude.ai', apiProvider='firstParty')))
    sys.exit(0)
if name == 'docker':
    if args and args[0] == 'rm': sys.exit(0)
    if not args or args[0] != 'run': sys.exit(78)
    command = args[-1]
    if command == 'true': sys.exit(0)
    if command == 'false': sys.exit(1)
    if command == 'test -f repaired': sys.exit(0 if (box / 'repaired').exists() else 1)
    if command == 'touch repaired':
        (box / 'repaired').touch()
        sys.exit(0)
    sys.exit(78)
with (box / 'trace').open('a') as trace: trace.write('provider_dispatch\\n')
model = args[args.index('--model') + 1] if '--model' in args else ''
contract = dict(status='SUCCESS', reason='', attempts=1,
    artifacts=dict(branch='', diff='', provider=name, model=model),
    rules_fired=[], results=dict(files_changed=[]))
if name == 'codex':
    pathlib.Path(args[args.index('--output-last-message') + 1]).write_text(json.dumps(contract))
else: print(json.dumps(contract))
'''.replace('PYTHON', sys.executable, 1)
        for name in ('docker', 'codex', 'claude', 'podman'):
            executable(bins / name, stub if name != 'podman' else '#!/bin/bash\nexit 78\n')
        home = box / 'home'
        home.mkdir()
        worktree = box / 'worktree'
        worktree.mkdir()
        env = {'PATH': str(bins), 'HOME': str(home), 'TMPDIR': str(box), 'LC_ALL': 'C',
               'NIGHTSHIFT_CONTAINER_RUNTIME': 'docker', 'NIGHTSHIFT_TELEMETRY_DIR': 'off'}
        receipt = box / 'receipt.json'
        policy_log = box / 'policy-decisions.jsonl'
        if scenario.startswith('deny-'):
            action = 'permanent-removal' if scenario == 'deny-removal' else 'production-deploy'
            command = ['bash', str(scripts / 'nightshift-policy.sh'), 'check', '--action', action,
                       '--worktree', str(worktree), '--log', str(policy_log), '--command', 'private command']
        elif scenario == 'adversarial-route':
            task = box / 'input.json'
            task.write_text('{}')
            command = ['bash', str(scripts / 'nightshift-agent.sh'), 'nightshift-engineer',
                       '--in', str(task), '--out', str(receipt), '--adversarial', '--author-provider', 'claude']
        else:
            budget = 2 if scenario in {'repaired-success', 'exhausted-failure', 'needs-decision'} else 1
            attempt = 'test -f repaired' if scenario == 'repaired-success' else (
                'false' if scenario in {'exhausted-failure', 'needs-decision'} else 'true')
            repair = 'touch repaired' if scenario == 'repaired-success' else ''
            command = ['bash', str(scripts / 'nightshift-controller.sh'), 'run', '--ticket', 'fixture-private',
                       '--gate', 'review', '--provider', 'codex', '--worktree', str(worktree),
                       '--receipt', str(receipt), '--budget', str(budget), '--attempt-command', attempt]
            if repair:
                command += ['--repair-command', repair]
            if scenario == 'needs-decision':
                command += ['--terminal-status', 'needs-decision']
            if scenario != 'missing-isolation':
                env['NIGHTSHIFT_WORKER_IMAGE'] = 'offline-fixture'
        result = subprocess.run(command, cwd=worktree, env=env, capture_output=True, timeout=30)
        require(result.returncode in (0, 1))
        policies = []
        if policy_log.exists():
            for line in policy_log.read_text().splitlines():
                raw = json.loads(line)
                policies.append({key: raw[key] for key in ('action', 'decision', 'reason')})
        if scenario.startswith('deny-'):
            require(len(policies) > 0)
            output = {'policy_decisions': policies}
        elif scenario == 'adversarial-route':
            raw = json.loads(receipt.read_text())
            require(result.returncode == 0 and raw['status'] == 'SUCCESS')
            output = {'route': {key: raw['artifacts'][key] for key in ('provider', 'model')}}
        else:
            raw = json.loads(receipt.read_text())
            # Required evidence must exist and have its promised type even when
            # its private content is intentionally absent from the projection.
            require(enum(raw['provider'], {'codex', 'claude', 'local'}) == 'codex')
            require(raw['gate'] == 'review' and raw['repair_budget'] == budget)
            require(raw['commands'] == {'attempt': attempt, 'repair': repair})
            require(isinstance(raw['output'], str))
            require(type(raw['changed_files']) is list and all(isinstance(x, str) for x in raw['changed_files']))
            require(isinstance(raw['ticket'], str) and raw['ticket'])
            require(isinstance(raw['worktree'], str) and raw['worktree'])
            require(isinstance(raw['generated_at'], str) and raw['generated_at'])
            category = NEXT[raw['next_action']]
            require((result.returncode == 0) == (raw['status'] == 'complete'))
            output = {key: raw[key] for key in ('status', 'gate', 'repair_budget')}
            attempts = []
            for item in raw['attempts']:
                require(isinstance(item['output'], str))
                require(item['command'] == (repair if 'repair_after_attempt' in item else attempt))
                step = set(item) & {'attempt', 'repair_after_attempt'}
                require(len(step) == 1)
                attempts.append({key: item[key] for key in (*step, 'exit_code', 'invocation', 'worker_execution')})
            output.update(attempts=attempts, policy_decisions=policies, next_action_category=category)
        output['tool_order'] = trace.read_text().splitlines()
        return validate(output)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'trajectory: invalid arguments\n')


def main():
    parser = SafeParser(description=__doc__)
    parser.add_argument('--scenario', required=True, choices=SCENARIOS)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(record(args.scenario, args.root), sort_keys=True))
    except Exception:
        print('trajectory: recording failed', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
