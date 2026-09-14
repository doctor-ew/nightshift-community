"""Version-bound local workshop review copies and approval receipts."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import sys
import threading
from datetime import datetime, timezone

TASK = re.compile(r'workshop-[a-f0-9]{16}\Z')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def common(project):
    value = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--git-common-dir'], text=True).strip()
    return (Path(project) / value).resolve()


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
        raise ValueError('Missing or unsafe review file')
    return path.read_bytes()


def atomic(path, data):
    fd, name = tempfile.mkstemp(prefix='.nightshift-review-', dir=path.parent)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())
    os.replace(name, path)


def copy_path(project, task):
    if not TASK.fullmatch(task):
        raise ValueError('Invalid workshop task')
    return Path(project) / ('NIGHTSHIFT-SPEC-' + task + '.md')


def publish(project, task, data):
    target = copy_path(project, task)
    # Existing student edits or unrelated files must never be overwritten.
    try:
        with target.open('xb') as handle:
            handle.write(data)
    except FileExistsError:
        if read(target) != data:
            raise ValueError('Review copy differs from the canonical spec; preserve your edits and revise the brief before starting a new exercise: ' + str(target))
    return target


def review(project, task):
    if not TASK.fullmatch(task):
        raise ValueError('Invalid workshop task')
    directory = common(project) / 'nightshift-workshop'
    state = json.loads(read(directory / (task + '.json')))
    if state.get('task') != task or state.get('status') != 'awaiting_spec_approval':
        raise ValueError('This workshop is no longer awaiting spec approval')
    worktree = Path(state['worktree'])
    registered = subprocess.check_output(['git', '-C', str(project), 'worktree', 'list', '--porcelain'], text=True)
    if 'worktree ' + str(worktree) + '\n' not in registered:
        raise ValueError('Worktree is not registered')
    canonical = worktree / 'docs' / task / 'SPEC.md'
    if canonical.resolve() != canonical or common(worktree) != common(project):
        raise ValueError('Invalid canonical spec location')
    data = read(canonical)
    local = copy_path(project, task)
    if read(local) != data:
        raise ValueError('The project review copy changed; approval refused')
    digest = sha(data)
    approved = False
    receipt = directory / (task + '.approval.json')
    if receipt.exists():
        approved = json.loads(read(receipt)).get('sha256') == digest
    job_path = directory / (task + '.launch.json')
    job = json.loads(read(job_path)) if job_path.exists() else None
    return dict(task=task, sha256=digest, spec=data.decode(), copy_path=str(local), approved=approved, launch=job)


def list_reviews(project):
    directory = common(project) / 'nightshift-workshop'
    result = []
    for path in sorted(directory.glob('workshop-*.json'))[:200]:
        if not TASK.fullmatch(path.stem):
            continue
        try:
            state = json.loads(read(path))
            if state.get('status') == 'awaiting_spec_approval':
                try:
                    result.append(review(project, path.stem))
                except (ValueError, OSError) as error:
                    result.append(dict(task=path.stem, error=str(error)))
        except (ValueError, OSError):
            continue
    return result


def approve(project, task, expected):
    if not TASK.fullmatch(task):
        raise ValueError('Invalid workshop task')
    directory = common(project) / 'nightshift-workshop'
    with (directory / (task + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = review(project, task)
        if expected != current['sha256']:
            raise ValueError('Spec changed; reload it before approving')
        atomic(directory / (task + '.approval.json'), json.dumps(dict(
            task=task, sha256=expected, method='web', approved_at=datetime.now(timezone.utc).isoformat()
        )).encode())
    return dict(status='approved', task=task, message='Approval saved. Rerun your original Nightshift command to continue; no hash is needed.')


def approved_hash(project, task):
    path = common(project) / 'nightshift-workshop' / (task + '.approval.json')
    if not path.exists():
        return None
    value = json.loads(read(path))
    if value.get('task') != task:
        raise ValueError('Approval receipt identity mismatch')
    return value.get('sha256')


def active_launch(path, expected):
    if not path.exists():
        return None
    job = json.loads(read(path))
    if job.get('sha256') != expected or job.get('status') != 'running':
        return None
    try:
        os.kill(job['pid'], 0)
    except ProcessLookupError:
        return None
    return dict(status='running', pid=job['pid'], message='Build is running. Follow its progress below.')


def approve_and_continue(project, task, expected):
    if not TASK.fullmatch(task):
        raise ValueError('Invalid workshop task')
    directory = common(project) / 'nightshift-workshop'
    launch_path = directory / (task + '.launch.json')
    with (directory / (task + '.lock')).open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            running = active_launch(launch_path, expected)
            if running: return running
            raise ValueError('Workshop is busy; no duplicate build was started') from None
        running = active_launch(launch_path, expected)
        if running: return running
        current = review(project, task)
        if current['sha256'] != expected:
            raise ValueError('Spec changed; reload before approving')
        state = json.loads(read(directory / (task + '.json')))
        identity = state.get('identity', {})
        auth = identity.get('auth')
        if auth not in ('api', 'subscription'):
            raise ValueError('Saved authentication mode is missing')
        if auth == 'api' and not os.environ.get('ANTHROPIC_API_KEY'):
            raise ValueError('This dashboard has no API credential. Restart it from the terminal with the same API key configured; no subscription fallback was used.')
        saved = state.get('resume', {})
        ref = saved.get('ref')
        if not ref:
            # Compatibility for already-waiting runs created before resume metadata.
            names = subprocess.check_output(['git', '-C', str(project), 'ls-files', '-z'], text=True).split('\0')
            matches = [name for name in names if 'workshop-' + sha(name.encode())[:16] == task]
            if len(matches) != 1: raise ValueError('Cannot resolve saved brief')
            ref = matches[0]
        source = (Path(project) / ref).resolve()
        if not source.is_relative_to(Path(project).resolve()) or sha(read(source)) != state['brief_sha256']:
            raise ValueError('Source brief changed; build was not started')
        argv = [sys.executable, str(Path(__file__).with_name('nightshift-workshop.py')),
                '--project', str(project), '--ref', ref, '--provider', 'claude',
                '--auth', auth, '--model', identity['writer'], '--wait-for-review-lock']
        for flag in ('push', 'pr'):
            if saved.get(flag) is True: argv.append('--' + flag)
        atomic(directory / (task + '.approval.json'), json.dumps(dict(
            task=task, sha256=expected, method='web', approved_at=datetime.now(timezone.utc).isoformat()
        )).encode())
        fd, log_path = tempfile.mkstemp(prefix=task+'-web-', suffix='.log', dir=directory)
        with os.fdopen(fd, 'wb') as log:
            process = subprocess.Popen(argv, cwd=project, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        atomic(launch_path, json.dumps(dict(status='running', pid=process.pid, sha256=expected, log=log_path)).encode())
        def reap():
            code = process.wait()
            # Only update this exact launch, preserving a subsequent retry record.
            with (directory / (task + '.lock')).open('a') as finish_lock:
                fcntl.flock(finish_lock, fcntl.LOCK_EX)
                job = json.loads(read(launch_path))
                if job.get('pid') == process.pid:
                    job.update(status='exited', exit_code=code)
                    atomic(launch_path, json.dumps(job).encode())
        threading.Thread(target=reap, daemon=True).start()
    return dict(status='running', pid=process.pid, message='Build started. Follow its progress below.')
