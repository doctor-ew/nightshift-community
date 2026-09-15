#!/usr/bin/env python3
"""Preserve interrupted ticket artifacts and authorize their unchanged reuse."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def git(project, *args):
    return subprocess.check_output(['git', '-C', str(project), *args], stderr=subprocess.DEVNULL)


def common_dir(project):
    return (project / git(project, 'rev-parse', '--git-common-dir').decode().strip()).resolve()


def inventory(project, task):
    if git(project, 'diff', '--cached', '--name-only').strip():
        raise ValueError('staged_changes_require_review')
    paths = set(git(project, 'ls-files', '-m', '-o', '--exclude-standard', '-z').decode().split('\0')) - {''}
    result = {}
    for name in sorted(paths):
        if not (name.startswith('docs/' + task + '/') or name.startswith('.nightshift/')):
            raise ValueError('source_changes_require_review')
        path = project / name
        if path.resolve() != path.absolute() or not path.is_file():
            raise ValueError('unsafe_or_missing_artifact')
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('artifact_too_large')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    # Deletions are never silently adopted as interrupted artifacts.
    if git(project, 'ls-files', '-d').strip():
        raise ValueError('deleted_files_require_review')
    return result


def live_workers(projects, task):
    for project in projects:
        directory = project / '.nightshift/agents'
        if not directory.exists():
            continue
        if directory.resolve() != directory.absolute():
            raise ValueError('unsafe_agent_directory')
        for path in directory.glob('*.json'):
            if path.is_symlink():
                raise ValueError('unsafe_agent_record')
            record = json.loads(path.read_text())
            if record.get('status') != 'running':
                continue
            identity = record.get('ticket')
            if isinstance(identity, dict) and identity.get('source_id') != task:
                continue
            pid = record.get('pid')
            if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
                raise ValueError('invalid_worker_pid')
            if str(pid) == os.environ.get('NIGHTSHIFT_FACTORY_PID'):
                continue
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            except PermissionError:
                pass
            raise ValueError('worker_still_alive')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task')
    parser.add_argument('--project', default='.')
    parser.add_argument('--check', action='store_true', help='Read-only fingerprint validation')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.task):
        raise ValueError('invalid_task')
    project = Path(args.project).resolve()
    common = common_dir(project)
    recovery = common / 'nightshift/recovery' / args.task
    manifest = recovery / 'resume.json'
    if args.check:
        if manifest.resolve() != manifest.absolute():
            raise ValueError('unsafe_recovery_record')
        record = json.loads(manifest.read_text())
        live_workers({project, common.parent}, args.task)
        current = inventory(project, args.task)
        if (record.get('worktree') != str(project) or record.get('head') != git(project, 'rev-parse', 'HEAD').decode().strip()
                or record.get('files') != current):
            raise ValueError('artifacts_changed_since_cleanup')
        print(json.dumps({'status': 'resumable', 'task': args.task}))
        return
    check = subprocess.run(['bash', str(HERE / 'nightshift-worktree.sh'), 'check', args.task,
                            '--project', str(project)], capture_output=True, text=True)
    record = json.loads(check.stdout)
    if not record.get('registered') or set(record.get('checks', {})) != {'base_match', 'prerequisite_ancestry', 'root_match', 'dirty'}:
        raise ValueError('worktree_not_owned')
    if any(value == 'fail' for key, value in record['checks'].items() if key != 'dirty'):
        raise ValueError('worktree_identity_mismatch')
    target = Path(record['worktree'])
    files = inventory(target, args.task)
    live_workers({project, target}, args.task)
    if not files:
        print(json.dumps({'status': 'clean', 'task': args.task}))
        return
    if recovery.resolve() != recovery.absolute():
        raise ValueError('unsafe_recovery_directory')
    recovery.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (recovery / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        live_workers({project, target}, args.task)
        snapshot = Path(tempfile.mkdtemp(prefix='snapshot-', dir=recovery))
        for name, digest in files.items():
            payload = (target / name).read_bytes()
            if hashlib.sha256(payload).hexdigest() != digest:
                raise ValueError('artifact_changed_during_cleanup')
            destination = snapshot / name
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.write_bytes(payload)
            destination.chmod(0o600)
        if inventory(target, args.task) != files:
            raise ValueError('artifacts_changed_during_cleanup')
        result = {'status': 'resumable', 'task': args.task, 'worktree': str(target),
                  'head': git(target, 'rev-parse', 'HEAD').decode().strip(),
                  'files': files, 'snapshot': str(snapshot)}
        fd, temporary = tempfile.mkstemp(prefix='.resume-', dir=recovery)
        with os.fdopen(fd, 'w') as stream:
            json.dump(result, stream)
        os.replace(temporary, manifest)
        print(json.dumps({'status': 'resumable', 'task': args.task, 'preserved_files': len(files), 'snapshot': str(snapshot)}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'blocked', 'reason': str(error)}))
        raise SystemExit(67)
