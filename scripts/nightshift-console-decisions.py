#!/usr/bin/env python3
"""Durable, version-bound operator decisions. Answers never manufacture gate results."""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def location(project, task):
    if not isinstance(task, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,150}', task):
        raise ValueError('Invalid task')
    common = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--git-common-dir'], text=True).strip()
    root = (Path(project) / common).resolve() / 'nightshift/console'
    if root.resolve() != root.absolute():
        raise ValueError('Unsafe console directory')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root / (task + '.decisions.json')


def read(path):
    if not path.exists():
        return {'version': 1, 'requests': []}
    if path.resolve() != path.absolute() or not path.is_file() or path.stat().st_size > 1_000_000:
        raise ValueError('Unsafe decision record')
    result = json.loads(path.read_text())
    if result.get('version') != 1 or not isinstance(result.get('requests'), list):
        raise ValueError('Invalid decision record')
    return result


def write(path, data):
    if path.is_symlink():
        raise ValueError('Unsafe decision record')
    fd, tmp = tempfile.mkstemp(prefix='.decision-', dir=path.parent)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream)
    os.replace(tmp, path)


def locked(path):
    fd = os.open(str(path) + '.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    stream = os.fdopen(fd, 'w')
    fcntl.flock(stream, fcntl.LOCK_EX)
    return stream


def text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\0' in value:
        raise ValueError('Missing or oversized decision text')
    return value.strip()


def snapshot(project, task):
    data = read(location(project, task))
    for item in data['requests']:
        continuation = item.get('continuation', {})
        if (continuation.get('status') in ('queued', 'waiting', 'launching')
                and continuation.get('pid') and time.time() - continuation.get('queued_at', 0) > 5
                and not watcher_alive(continuation)):
            continuation.update(status='blocked', message='Continuation watcher stopped; retry the saved answer')
    return {'pending': [r for r in data['requests'] if r.get('response') is None],
            'answered': [r for r in data['requests'] if r.get('response') is not None][-10:]}


def request(project, task, value):
    if not isinstance(value, dict) or not {'question', 'reason', 'options'} <= set(value) or set(value) - {'question', 'reason', 'options', 'continuation', 'provider', 'decision_key', 'supersedes', 'reopen_reason'}:
        raise ValueError('Request requires question, reason and options')
    extra = {k: value[k] for k in ('decision_key', 'supersedes', 'reopen_reason') if k in value}
    if 'decision_key' in extra and (not isinstance(extra['decision_key'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,150}', extra['decision_key'])):
        raise ValueError('Invalid stable decision key')
    if ('supersedes' in extra) != ('reopen_reason' in extra):
        raise ValueError('Reopening requires the prior decision hash and new evidence')
    if 'supersedes' in extra:
        if not isinstance(extra['supersedes'], str) or not re.fullmatch(r'[a-f0-9]{64}', extra['supersedes']):
            raise ValueError('Invalid superseded decision hash')
        extra['reopen_reason'] = text(extra['reopen_reason'], 4000)
    operation = value.get('continuation', 'resume')
    if operation not in ('resume', 'repair'):
        raise ValueError('Continuation must be resume or repair')
    provider = value.get('provider', 'auto')
    if provider not in ('auto', 'claude', 'codex', 'local'):
        raise ValueError('Invalid continuation provider')
    value = dict(question=text(value['question'], 2000), reason=text(value['reason'], 4000), options=value['options'], continuation_operation=operation, continuation_provider=provider)
    value.update(extra)
    options = value['options']
    if not isinstance(options, list) or len(options) > 3:
        raise ValueError('Use up to three options; free text is always available')
    ids = set()
    for option in options:
        if not isinstance(option, dict) or set(option) != {'id', 'label', 'description'}:
            raise ValueError('Options require id, label and description')
        if not isinstance(option['id'], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,151}', option['id']) or option['id'] in ids:
            raise ValueError('Invalid or duplicate option id')
        ids.add(option['id']); text(option['label'], 160); text(option['description'], 800)
    path = location(project, task)
    with locked(path):
        data = read(path)
        # A changed rationale or wording must not discard a settled decision.
        # Legacy callers match normalized question text; new callers use a stable key.
        previous = next((item for item in reversed(data['requests'])
            if ('decision_key' in value and item.get('decision_key') == value['decision_key'])
            or ' '.join(item['question'].casefold().split()) == ' '.join(value['question'].casefold().split())), None)
        if previous is not None:
            if all(previous.get(k) == v for k, v in value.items()) or 'supersedes' not in value:
                return previous
            if previous.get('response') is None or value['supersedes'] != previous['sha256']:
                raise ValueError('Reopening requires the latest answered decision')
        elif 'supersedes' in value:
            raise ValueError('No matching decision to reopen')
        for item in data['requests']:
            if item.get('response') is None:
                if all(item.get(k) == v for k, v in value.items()):
                    return item
                raise ValueError('Resolve the pending decision before requesting another')
        if len(data['requests']) >= 100:
            raise ValueError('Decision history limit reached; preserve history and split the ticket')
        occurrence = len(data['requests']) + 1
        key = digest(dict(task=task, occurrence=occurrence, request=value))
        item = dict(value, sha256=key, task=task, occurrence=occurrence,
                    created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), response=None)
        data['requests'].append(item); write(path, data)
        return item


def respond(project, task, expected, choice, answer):
    if not isinstance(answer, str) or len(answer) > 4000 or '\0' in answer:
        raise ValueError('Answer must be at most 4000 characters')
    path = location(project, task)
    with locked(path):
        data = read(path)
        item = next((r for r in data['requests'] if r['sha256'] == expected), None)
        if item is None:
            raise ValueError('Decision changed; refresh before answering')
        if data['requests'][-1] is not item:
            raise ValueError('A newer decision exists; refresh before answering')
        selected = next((o for o in item['options'] if o['id'] == choice), None)
        if choice and selected is None:
            raise ValueError('Unknown decision option')
        if not selected and not answer.strip():
            raise ValueError('Select an option or write your answer')
        value = dict(choice=choice, answer=answer.strip(), selected=selected)
        if item['response'] is not None:
            old = item['response']
            if any(old.get(k) != v for k, v in value.items()):
                raise ValueError('Decision already answered; publish a new question for a changed decision')
            return item
        item['response'] = dict(value, source='authenticated-local-portal', answered_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write(path, data)
        return item


def actions_module():
    spec = importlib.util.spec_from_file_location('actions', HERE / 'nightshift-console-actions.py')
    actions = importlib.util.module_from_spec(spec); spec.loader.exec_module(actions)
    return actions


def process_identity(pid):
    try:
        return subprocess.check_output(['ps', '-p', str(pid), '-o', 'lstart='], text=True).strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def watcher_alive(continuation):
    pid = continuation.get('pid')
    return (type(pid) is int and pid > 0 and bool(continuation.get('identity'))
            and process_identity(pid) == continuation['identity'])


def decision_in_state(current, sha):
    decisions = current.get('decisions', {})
    pending = decisions.get('pending', [])
    if pending and not any(r.get('sha256') == sha for r in pending):
        raise ValueError('A newer or different decision is pending; refresh before continuing')
    item = next((r for r in pending + decisions.get('answered', []) if r.get('sha256') == sha), None)
    if item is None:
        raise ValueError('Decision is no longer visible for this ticket; refresh')
    return item


def spawn_watcher(argv, log_path):
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as log:
        return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=log, start_new_session=True, close_fds=True)


def submit(project, task, settings_sha, decision_sha, choice, answer):
    current = actions_module().state(project, task)
    if current['sha256'] != settings_sha:
        raise ValueError('Run settings changed; refresh before answering')
    if current['finished']:
        raise ValueError('Ticket finished; start an intentional follow-up ticket')
    selected = decision_in_state(current, decision_sha)
    target = selected['task']
    item = respond(project, target, decision_sha, choice, answer)
    path = location(project, target)
    with locked(path):
        data = read(path)
        item = next(r for r in data['requests'] if r['sha256'] == decision_sha)
        if data['requests'][-1] is not item:
            raise ValueError('A newer decision exists; answer retained but continuation rejected')
        previous = item.get('continuation', {})
        if previous.get('status') == 'resumed':
            return dict(status='resumed', message='Answer recorded; continuation was already launched.', decision=item)
        if previous.get('status') in ('queued', 'waiting', 'launching') and watcher_alive(previous):
            return dict(status='queued', message='Answer saved; continuation is already queued.', decision=item)
        token = uuid.uuid4().hex
        item['continuation'] = dict(status='queued', parent_task=task, settings_sha256=settings_sha,
            token=token, queued_at=time.time(), deadline=time.time() + 1800,
            log=str(path.parent / (target + '.continue-' + token + '.log')))
        write(path, data)
        try:
            process = spawn_watcher([sys.executable, str(Path(__file__).resolve()), 'continue',
                '--project', str(Path(project).resolve()), '--task', target,
                '--decision-sha', decision_sha, '--token', token], item['continuation']['log'])
            identity = process_identity(process.pid)
            if not identity:
                raise OSError('Continuation watcher exited before registration')
            item['continuation'].update(pid=process.pid, identity=identity)
            write(path, data)
        except OSError as error:
            item['continuation'].update(status='blocked', message=str(error))
            write(path, data)
            return dict(status='answer_saved', message='Answer saved; automatic continuation could not start. Retry this answer.', decision=item)
    return dict(status='queued', message='Answer saved. Continuation will start after the active worker exits.', decision=item)


def continue_answer(project, task, sha, token, *, sleep=time.sleep, now=time.time, actions=None):
    """Bounded detached watcher; settings and decision freshness checked each poll."""
    actions = actions or actions_module()
    path = location(project, task)
    while True:
        launch = None
        with locked(path):
            data = read(path)
            item = next((r for r in data['requests'] if r['sha256'] == sha), None)
            if item is None or item.get('continuation', {}).get('token') != token:
                return 1
            cont = item['continuation']
            if cont['status'] not in ('queued', 'waiting', 'launching'):
                return 0 if cont['status'] == 'resumed' else 1
            try:
                if data['requests'][-1] is not item:
                    raise ValueError('A newer decision exists; continuation cancelled')
                if now() >= cont['deadline']:
                    raise ValueError('Continuation timed out after 30 minutes; retry the saved answer')
                current = actions.state(project, cont['parent_task'])
                if current['sha256'] != cont['settings_sha256']:
                    raise ValueError('Run settings changed; continuation cancelled')
                if current['finished']:
                    raise ValueError('Ticket already finished; continuation cancelled')
                decision_in_state(current, sha)
                if current['running']:
                    cont.update(status='waiting', message='Waiting for the active worker to exit')
                else:
                    cont.update(status='launching', message='Launching continuation')
                    launch = (cont['parent_task'], cont['settings_sha256'], item.get('continuation_operation', 'resume'), item.get('continuation_provider', 'auto'))
                write(path, data)
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                cont.update(status='blocked', message=str(error), completed_at=now())
                write(path, data)
                return 1
        if launch:
            # action holds its own per-ticket launch lock and rechecks pending
            # questions. Do not hold the decision lock: repair may publish a new
            # question itself when its set of eligible children has changed.
            try:
                result = actions.action(project, *launch)
                launched = result.get('launched', False)
                if launched:
                    outcome = dict(status='resumed', message=result['message'], completed_at=now())
                elif result.get('status') == 'running':
                    outcome = dict(status='waiting', message='Another worker started; waiting for it to exit')
                else:
                    outcome = dict(status='blocked', message=result.get('message', 'Continuation did not launch'), completed_at=now())
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                outcome = dict(status='blocked', message=str(error), completed_at=now())
            with locked(path):
                data = read(path)
                item = next((r for r in data['requests'] if r['sha256'] == sha), None)
                if item is None or item.get('continuation', {}).get('token') != token:
                    return 1
                item['continuation'].update(outcome)
                write(path, data)
            if outcome['status'] != 'waiting':
                return 0 if outcome['status'] == 'resumed' else 1
        sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['request', 'context', 'continue'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--input')
    parser.add_argument('--decision-sha')
    parser.add_argument('--token')
    args = parser.parse_args()
    if args.operation == 'continue':
        if not args.decision_sha or not args.token: parser.error('continue requires decision-sha and token')
        try:
            code = continue_answer(args.project, args.task, args.decision_sha, args.token)
        except Exception as error:
            path = location(args.project, args.task)
            with locked(path):
                data = read(path)
                item = next((r for r in data['requests'] if r['sha256'] == args.decision_sha), None)
                if item and item.get('continuation', {}).get('token') == args.token:
                    item['continuation'].update(status='blocked', message='Continuation worker failed: ' + str(error)[:800])
                    write(path, data)
            raise
        print(json.dumps(dict(operation='continue', task=args.task, exit_code=code)))
        raise SystemExit(code)
    if args.operation == 'request':
        if not args.input: parser.error('--input is required for request')
        result = request(args.project, args.task, json.loads(Path(args.input).read_text()))
    else:
        result = snapshot(args.project, args.task)
    print(json.dumps(result))
