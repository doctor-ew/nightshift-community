#!/usr/bin/env python3
"""Local ticket recovery actions using recorded invocation policy."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading

HERE = Path(__file__).resolve().parent
FACTORY = HERE / 'nightshift-factory.sh'
REPAIR = HERE / 'nightshift-console-repair.py'


def directory(project):
    common = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--git-common-dir'], text=True).strip()
    path = (Path(project) / common).resolve() / 'nightshift/console'
    if path.resolve() != path.absolute():
        raise ValueError('Unsafe console state directory')
    return path


def read(path):
    if path.resolve() != path.absolute() or path.stat().st_size > 65536:
        raise ValueError('Unsafe console record')
    return json.loads(path.read_text())


def atomic(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.console-', dir=path.parent)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)
    os.replace(temporary, path)


def validate(task, settings):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', task):
        raise ValueError('Invalid task')
    if (settings.get('provider') not in ('claude', 'codex', 'local')
            or settings.get('policy') not in ('standard', 'claude-only')
            or settings.get('auth') not in ('subscription', 'api')
            or settings.get('branch') != 'auto'
            or type(settings.get('push')) is not bool or type(settings.get('pr')) is not bool
            or (settings['pr'] and not settings['push'])):
        raise ValueError('Invalid saved run policy')
    for key in ('ref', 'model', 'base'):
        value = settings.get(key)
        if not isinstance(value, str) or len(value) > 1024 or any(c in value for c in '\n\r\0'):
            raise ValueError('Invalid saved run argument')
    if not settings['ref'] or settings['ref'].startswith('-'):
        raise ValueError('Invalid saved ticket reference')


def save(project, task, settings):
    validate(task, settings)
    path = directory(project)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic(path / (task + '.json'), dict(task=task, settings=settings))


def state(project, task):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', task):
        raise ValueError('Invalid task')
    path = directory(project) / (task + '.json')
    record = read(path)
    validate(task, record['settings'])
    if record.get('task') != task:
        raise ValueError('Task identity changed')
    digest = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    job_path = path.with_name(task + '.launch.json')
    job = read(job_path) if job_path.exists() else None
    running = False
    if job and job.get('status') == 'running':
        try:
            os.kill(job['pid'], 0)
            running = True
        except ProcessLookupError:
            pass
    ownership = directory(project).parent / 'worktrees' / (task + '.json')
    finished = ownership.exists() and read(ownership).get('status') == 'finished'
    # CLI factories do not create a dashboard launch record. Match their
    # lifecycle record to this ticket and verify the PID's command line.
    if not running:
        for agent_path in (Path(project).resolve() / '.nightshift/agents').glob('factory-*.json'):
            try:
                agent = read(agent_path)
                if (agent.get('status') != 'running'
                        or agent.get('ticket', {}).get('source_id') != task):
                    continue
                pid = agent.get('pid')
                if type(pid) is not int or pid <= 0:
                    continue
                command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True)
                if 'nightshift-factory.sh' in command and record['settings']['ref'] in command:
                    running = True
                    break
            except (OSError, ValueError, subprocess.SubprocessError):
                continue
    repair = None
    if job and job.get('evidence'):
        evidence = Path(job['evidence'])
        if evidence.parent == directory(project) and (evidence / 'status.json').exists():
            repair = read(evidence / 'status.json')
    budget_path = path.with_name(task + '.repair-budget.json')
    budget = read(budget_path) if budget_path.exists() else {}
    attempts = budget.get('attempts', 0)
    credits = budget.get('proof_gate_bug_reconciliation', {}).get('credited_attempts', 0)
    remaining = max(0, 3 - (attempts - credits)) if type(attempts) is int and type(credits) is int else 0
    return dict(task=task, settings=record['settings'], sha256=digest, running=running, finished=finished, launch=job, repair=repair, updated_at=path.stat().st_mtime, repair_remaining=remaining)


def list_tickets(project):
    result = []
    for path in sorted(directory(project).glob('*.json'))[:200]:
        if path.name.endswith('.launch.json'):
            continue
        try:
            result.append(state(project, path.stem))
        except (OSError, ValueError, KeyError):
            continue
    return sorted(result, key=lambda item: (item['running'], item['updated_at']), reverse=True)


def resume_settings(project, task, settings):
    """Retained worktree identity pins resume even when a symbolic ref moves."""
    owner_path = directory(project).parent / 'worktrees' / (task + '.json')
    if not owner_path.exists():
        raise ValueError('Missing retained worktree ownership; cannot safely resume')
    owner = read(owner_path)
    base = owner.get('base_sha', '')
    if not isinstance(base, str) or not re.fullmatch(r'[0-9a-f]{40,64}', base):
        raise ValueError('Missing retained baseline commit; cannot safely resume')
    subprocess.run(['git', '-C', str(project), 'cat-file', '-e', base + '^{commit}'], check=True, capture_output=True)
    return dict(settings, base=base)


def repair_budget(path, task):
    """One-time reconciliation of the prelaunch proof-gate bug; never reset attempts."""
    budget_path = path / (task + '.repair-budget.json')
    budget = read(budget_path) if budget_path.exists() else dict(attempts=0, limit=3)
    used = budget.get('attempts')
    if type(used) is not int or used < 0:
        raise ValueError('Invalid repair budget')
    if 'proof_gate_bug_reconciliation' not in budget:
        evidence = []
        for folder in sorted(path.glob(task + '-repair-*')):
            try:
                receipt = read(folder / 'proposal.json')
                status = read(folder / 'status.json')
                if (status.get('phase') == 'blocked'
                        and receipt.get('status') == 'FAIL'
                        and receipt.get('reason') == 'required development proof is missing, stale or blocked'
                        and receipt.get('rules_fired') == ['dispatcher_failure']
                        and receipt.get('artifacts', {}).get('provider') == ''
                        and receipt.get('artifacts', {}).get('model') == ''
                        and not (folder / 'review.json').exists()
                        and not (folder / 'repair.diff').exists()):
                    evidence.append(dict(path=str(folder / 'proposal.json'), sha256=hashlib.sha256((folder / 'proposal.json').read_bytes()).hexdigest()))
            except (OSError, ValueError, KeyError):
                continue
        budget['proof_gate_bug_reconciliation'] = dict(
            reason='Pre-provider rejection caused by implementation-role diagnosis bug; fixed in fbb3300',
            credited_attempts=min(used, len(evidence), 3), evidence=evidence)
    credits = budget['proof_gate_bug_reconciliation'].get('credited_attempts', 0)
    if type(credits) is not int or not 0 <= credits <= min(used, 3):
        raise ValueError('Invalid repair budget reconciliation')
    if used - credits >= 3:
        raise ValueError('Repair budget exhausted (three charged attempts); inspect retained evidence')
    return budget_path, budget


def action(project, task, expected, operation, provider="auto"):
    if operation not in ('cleanup', 'resume', 'repair', 'stop'):
        raise ValueError('Invalid operation')
    if provider not in ('auto', 'claude', 'codex', 'local'):
        raise ValueError('Invalid repair provider')
    current = state(project, task)
    path = directory(project)
    fd = os.open(path / (task + '.lock'), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = state(project, task)
        if current['sha256'] != expected:
            raise ValueError('Run settings changed; refresh before continuing')
        if operation == 'stop':
            job = current.get('launch') or {}
            if not current['running'] or job.get('operation') != 'repair':
                raise ValueError('No active console repair to stop')
            actual = subprocess.check_output(['ps', '-p', str(job['pid']), '-o', 'lstart='], text=True).strip()
            if actual != job.get('started_identity'):
                raise ValueError('Process identity changed; refusing to stop')
            os.kill(job['pid'], signal.SIGTERM)
            return dict(status='stopping', message='Stopping repair and its owned worker; evidence retained.')
        if current['running']:
            return dict(status='running', message='This ticket already has a console-launched worker.')
        if current['finished']:
            raise ValueError('This ticket is finished; use the terminal for an intentional new run.')
        settings = resume_settings(project, task, current['settings'])
        if operation == 'repair' and settings['auth'] != 'subscription':
            raise ValueError('Browser repair requires subscription authentication')
        if operation == 'repair' and settings['policy'] == 'claude-only' and provider not in ('auto', 'claude'):
            raise ValueError('Selected provider conflicts with saved policy')
        if operation == 'resume' and settings['ref'].startswith('jira:'):
            if any(not os.environ.get(key) for key in ('JIRA_BASE_URL', 'JIRA_EMAIL', 'JIRA_TOKEN')):
                raise ValueError('Jira credentials are absent from this console process. Restart the console from your configured terminal.')
        cleaned = subprocess.run([sys.executable, str(HERE / 'nightshift-cleanup.py'), task,
                                  '--project', str(project)], capture_output=True, text=True, timeout=30)
        receipt = json.loads(cleaned.stdout)
        if cleaned.returncode:
            raise ValueError('Cleanup blocked: ' + receipt.get('reason', 'inspect retained worktree'))
        if operation == 'cleanup':
            return dict(status='ready', message='Artifacts preserved. The ticket is ready to resume.')
        argv = ['bash', str(FACTORY), settings['ref'], '--project', str(project),
                '--provider', settings['provider'], '--provider-policy', settings['policy'],
                '--auth', settings['auth'], '--branch', settings['branch']]
        for key in ('model', 'base'):
            if settings[key]: argv += ['--' + key, settings[key]]
        for key in ('push', 'pr'):
            if settings[key]: argv += ['--' + key]
        evidence = None
        if operation == 'repair':
            budget_path, budget = repair_budget(path, task)
            budget['attempts'] += 1
            atomic(budget_path, budget)
            evidence = tempfile.mkdtemp(prefix=task+'-repair-', dir=path)
            atomic(Path(evidence) / 'status.json', dict(phase='starting', provider=provider))
            argv = [sys.executable, str(REPAIR), '--project', str(project),
                    '--task', task, '--provider', provider, '--evidence', evidence]
        fd, log_path = tempfile.mkstemp(prefix=task+'-', suffix='.log', dir=path)
        with os.fdopen(fd, 'wb') as log:
            process = subprocess.Popen(argv, cwd=project, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        job_path = path / (task + '.launch.json')
        identity = subprocess.check_output(['ps', '-p', str(process.pid), '-o', 'lstart='], text=True).strip()
        atomic(job_path, dict(status='running', pid=process.pid, log=log_path, operation=operation, evidence=evidence, started_identity=identity))
        def reap():
            code = process.wait()
            with (path / (task + '.lock')).open('a') as finish_lock:
                fcntl.flock(finish_lock, fcntl.LOCK_EX)
                job = read(job_path)
                if job.get('pid') == process.pid:
                    job.update(status='exited', exit_code=code)
                    atomic(job_path, job)
        threading.Thread(target=reap, daemon=True).start()
        return dict(status='running', message=('Diagnosis started; repair requires independent review and verification before resume.' if operation == 'repair' else 'Resumed with the recorded provider and publication settings.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--settings', required=True)
    args = parser.parse_args()
    save(args.project, args.task, json.loads(args.settings))
