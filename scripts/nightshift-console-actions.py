#!/usr/bin/env python3
"""Local ticket recovery actions using recorded invocation policy."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
FACTORY = HERE / 'nightshift-factory.sh'


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


def input_spec(project, settings):
    ref = settings['ref']
    name = ref[5:] if ref.startswith('spec:') else ref
    source = Path(name)
    if not source.is_absolute():
        source = Path(project) / source
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 1048576:
        raise ValueError('Spec review requires a regular local file of at most 1 MiB')
    if not source.resolve().is_relative_to(Path(project).resolve()):
        raise ValueError('Spec must be inside the selected project for console approval')
    return source, source.read_bytes()


def save(project, task, settings, review_spec=False):
    validate(task, settings)
    path = directory(project)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = path / (task + '.json')
    previous = read(target) if target.exists() else {}
    required = review_spec or previous.get('review_spec', False)
    if required:
        input_spec(project, settings)
    atomic(target, dict(task=task, settings=settings, review_spec=required))


def state(project, task):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', task):
        raise ValueError('Invalid task')
    path = directory(project) / (task + '.json')
    record = read(path)
    validate(task, record['settings'])
    if record.get('task') != task:
        raise ValueError('Task identity changed')
    review = None
    if record.get('review_spec'):
        source, content = input_spec(project, record['settings'])
        review = dict(path=str(source), spec=content.decode('utf-8'), sha256=hashlib.sha256(content).hexdigest())
    digest = hashlib.sha256(json.dumps(dict(record=record, review=review), sort_keys=True).encode()).hexdigest()
    if review is not None:
        receipt = path.with_name(task + '.approval.json')
        review['approved'] = receipt.exists() and read(receipt).get('sha256') == digest
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
    return dict(task=task, settings=record['settings'], sha256=digest, running=running, finished=finished, launch=job, review=review, owned=ownership.exists())


def list_tickets(project):
    result = []
    for path in sorted(directory(project).glob('*.json'))[:200]:
        if path.name.endswith(('.launch.json', '.approval.json')):
            continue
        try:
            result.append(state(project, path.stem))
        except (OSError, ValueError, KeyError):
            continue
    return result


def action(project, task, expected, operation):
    if operation not in ('cleanup', 'resume', 'approve'):
        raise ValueError('Invalid operation')
    current = state(project, task)
    path = directory(project)
    fd = os.open(path / (task + '.lock'), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = state(project, task)
        if current['sha256'] != expected:
            raise ValueError('Run settings changed; refresh before continuing')
        if current['running']:
            return dict(status='running', message='This ticket already has a console-launched worker.')
        if current['finished']:
            raise ValueError('This ticket is finished; use the terminal for an intentional new run.')
        settings = current['settings']
        if operation in ('resume', 'approve') and settings['ref'].startswith('jira:'):
            if any(not os.environ.get(key) for key in ('JIRA_BASE_URL', 'JIRA_EMAIL', 'JIRA_TOKEN')):
                raise ValueError('Jira credentials are absent from this console process. Restart the console from your configured terminal.')
        if operation == 'approve':
            if current['review'] is None:
                raise ValueError('No spec is awaiting approval')
        elif operation == 'resume' and current['review'] and not current['review']['approved']:
            raise ValueError('Read the current spec and approve it before continuing')
        if current['owned']:
            cleaned = subprocess.run([sys.executable, str(HERE / 'nightshift-cleanup.py'), task,
                                      '--project', str(project)], capture_output=True, text=True, timeout=30)
            receipt = json.loads(cleaned.stdout)
            if cleaned.returncode:
                raise ValueError('Cleanup blocked: ' + receipt.get('reason', 'inspect retained worktree'))
        if operation == 'cleanup':
            return dict(status='ready', message='Artifacts preserved.' if current['owned'] else 'No worktree has been created; there is nothing to clean up.')
        if operation == 'approve':
            # Bind approval to the displayed bytes AND publication/provider settings.
            if state(project, task)['sha256'] != expected:
                raise ValueError('Spec or settings changed; reload before approving')
            atomic(path / (task + '.approval.json'), dict(task=task, sha256=expected, method='web', approved_at=datetime.now(timezone.utc).isoformat()))
        argv = ['bash', str(FACTORY), settings['ref'], '--project', str(project),
                '--provider', settings['provider'], '--provider-policy', settings['policy'],
                '--auth', settings['auth'], '--branch', settings['branch']]
        for key in ('model', 'base'):
            if settings[key]: argv += ['--' + key, settings[key]]
        for key in ('push', 'pr'):
            if settings[key]: argv += ['--' + key]
        fd, log_path = tempfile.mkstemp(prefix=task+'-', suffix='.log', dir=path)
        with os.fdopen(fd, 'wb') as log:
            process = subprocess.Popen(argv, cwd=project, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        job_path = path / (task + '.launch.json')
        atomic(job_path, dict(status='running', pid=process.pid, log=log_path))
        def reap():
            code = process.wait()
            with (path / (task + '.lock')).open('a') as finish_lock:
                fcntl.flock(finish_lock, fcntl.LOCK_EX)
                job = read(job_path)
                if job.get('pid') == process.pid:
                    job.update(status='exited', exit_code=code)
                    atomic(job_path, job)
        threading.Thread(target=reap, daemon=True).start()
        return dict(status='running', message='Resumed with the recorded provider and publication settings.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--settings')
    parser.add_argument('--review-spec', action='store_true')
    parser.add_argument('--check-approval', action='store_true')
    args = parser.parse_args()
    if args.check_approval:
        review = state(args.project, args.task)['review']
        print('not_required' if review is None else 'approved' if review['approved'] else 'pending')
    else:
        if not args.settings:
            parser.error('--settings is required when saving')
        save(args.project, args.task, json.loads(args.settings), args.review_spec)
