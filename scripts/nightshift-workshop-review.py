"""Version-bound local workshop review copies and approval receipts."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
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
    return dict(task=task, sha256=digest, spec=data.decode(), copy_path=str(local), approved=approved)


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
