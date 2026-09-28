#!/usr/bin/env python3
"""Cross-entrypoint ownership of a ticket while a console repair mutates it."""
import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time


def directory(project):
    common = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--git-common-dir'], text=True).strip()
    return (Path(project) / common).resolve() / 'nightshift/console'


def identity(pid):
    if type(pid) is not int or pid <= 0:
        return None
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart='], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def canonical_active(record):
    """Verify legacy lifecycle PID ownership without trusting PID existence alone.

    Canonical records predate started_identity. Their UTC telemetry timestamp is
    recorded after shell startup, so a later process birth proves PID reuse.
    Command identity additionally rejects an unrelated process born in the same
    timestamp second. Modern exact identities remain authoritative.
    """
    pid = record.get('pid')
    started = identity(pid)
    if not started:
        return False
    if record.get('started_identity'):
        return started == record['started_identity']
    try:
        recorded = datetime.fromisoformat(record['started_at'].replace('Z', '+00:00'))
        if recorded.tzinfo is None:
            return False
        # ps lstart uses local time; timestamp() interprets the naive value in
        # the same system timezone. Canonical telemetry has second precision.
        born = datetime.strptime(started, '%a %b %d %H:%M:%S %Y').timestamp()
        if born > recorded.timestamp():
            return False
        result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
        command = shlex.split(result.stdout.strip())
        expected = 'nightshift-factory.sh' if record.get('role') == 'nightshift-factory' else 'nightshift-agent.sh'
        return result.returncode == 0 and any(Path(arg).name == expected for arg in command[:3])
    except (KeyError, TypeError, ValueError):
        return False


def read(path):
    if not path.exists():
        return {}
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError('Unsafe lease record')
    return json.loads(path.read_text())


def validate(task):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', task):
        raise ValueError('Invalid lease task')


def active(project, task):
    validate(task)
    record = read(directory(project) / (task + '.repair-lease.json'))
    if (record.get('task') == task and record.get('status') == 'running'
            and record.get('started_identity') and identity(record.get('pid')) == record['started_identity']):
        return record
    return None


def atomic(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.lease-', dir=path.parent)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)
    os.replace(temporary, path)


class Lease:
    def __init__(self, project, task, owner_parent, worktree):
        validate(task)
        self.project, self.task = Path(project).resolve(), task
        self.owner_parent, self.worktree = owner_parent, Path(worktree).resolve()
        self.lock = None
        self.record = None

    def acquire(self):
        path = directory(self.project)
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = os.fdopen(os.open(path / (self.task + '.lock'), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'w')
        try:
            # The launching parent briefly owns this lock until its PID receipt is
            # written. Wait only for that startup handshake, never for another run.
            deadline = time.monotonic() + 5
            while True:
                try:
                    fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if active(self.project, self.task) or time.monotonic() >= deadline:
                        raise ValueError('Target task is busy')
                    time.sleep(.05)
            if active(self.project, self.task):
                raise ValueError('Target already has an active repair')
            launch = read(path / (self.task + '.launch.json'))
            if (launch.get('status') == 'running' and launch.get('pid') != os.getpid()
                    and identity(launch.get('pid'))
                    and (not launch.get('started_identity') or identity(launch['pid']) == launch['started_identity'])):
                raise ValueError('Target already has an active console worker')
            owner = read(path.parent / 'worktrees' / (self.task + '.json'))
            roots = {self.project, self.worktree, path.parent.parent.parent}
            if owner.get('project'):
                roots.add(Path(owner['project']))
            for root in roots:
                for record_path in (root / '.nightshift/agents').glob('*.json'):
                    record = read(record_path)
                    ticket = record.get('ticket') or {}
                    if record.get('status') != 'running' or ticket.get('source_id') not in (None, self.task):
                        continue
                    pid = record.get('pid')
                    if pid != os.getpid() and canonical_active(record):
                        raise ValueError('Target already has an active canonical worker')
            self.record = dict(task=self.task, status='running', pid=os.getpid(),
                started_identity=identity(os.getpid()), owner_parent=self.owner_parent, worktree=str(self.worktree))
            atomic(path / (self.task + '.repair-lease.json'), self.record)
            return self
        except BaseException:
            self.release()
            raise

    def release(self):
        if self.lock:
            try:
                if self.record:
                    self.record.update(status='finished', finished_at=time.time())
                    atomic(directory(self.project) / (self.task + '.repair-lease.json'), self.record)
            finally:
                self.lock.close()
                self.lock = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()


def guarded(project, task, command):
    """Hold the same lock throughout worktree preparation, closing the check/use race."""
    validate(task)
    path = directory(project)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path / (task + '.lock'), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'w') as lock:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if active(project, task) or time.monotonic() >= deadline:
                    raise ValueError('Target task is busy with a console action or repair')
                time.sleep(.05)
        if active(project, task):
            raise ValueError('Target task has an active repair lease')
        return subprocess.call(command, env=dict(os.environ, NIGHTSHIFT_WORKTREE_LEASE_GUARDED='1'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        raise SystemExit(guarded(args.project, args.task, args.command[1:] if args.command[:1] == ['--'] else args.command))
    except ValueError as error:
        parser.exit(1, str(error) + '\n')
