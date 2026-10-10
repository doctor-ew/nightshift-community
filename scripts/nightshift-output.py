"""Display launcher output without changing provider status or investigation scope."""
import collections
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib


def options(argv, env):
    args = []
    explicit = None
    project = Path.cwd()
    i = 0
    while i < len(argv):
        value = argv[i]
        if value == '--output':
            i += 1
            if i == len(argv):
                raise ValueError('--output requires concise, verbose, or quiet')
            explicit = argv[i]
        else:
            args.append(value)
            if value == '--project' and i + 1 < len(argv):
                project = Path(argv[i + 1])
        i += 1
    mode = 'concise'
    home = Path(env.get('NIGHTSHIFT_HOME', str(Path.home() / '.nightshift')))
    for directory in (home, project):
        path = directory / '.nightshift.toml'
        if not path.exists():
            path = directory / 'nightshift.toml'
        if path.exists():
            data = tomllib.loads(path.read_text())
            output = data.get('output', {})
            if not isinstance(output, dict):
                raise ValueError('output must be a table')
            if 'mode' in output:
                mode = output['mode']
    mode = explicit or env.get('NIGHTSHIFT_OUTPUT') or mode
    if mode not in ('concise', 'verbose', 'quiet'):
        raise ValueError('output mode must be concise, verbose, or quiet')
    return args, mode, home


def run(launcher, argv):
    try:
        args, mode, home = options(argv, os.environ)
        # Private directories and files: transcripts may contain private tool data.
        logs = home / 'logs'
        logs.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = Path(tempfile.mkdtemp(prefix='run-', dir=logs))
        stdout_log = (directory / 'stdout.log').open('x')
        stderr_log = (directory / 'stderr.log').open('x')
        os.chmod(directory / 'stdout.log', 0o600)
        os.chmod(directory / 'stderr.log', 0o600)
    except (OSError, ValueError) as error:
        print(f'nightshift: cannot initialize output: {error}', file=sys.stderr)
        return 64
    env = dict(os.environ, NIGHTSHIFT_OUTPUT_CHILD='1', NIGHTSHIFT_OUTPUT_MODE=mode)
    events = queue.Queue(maxsize=1024)
    final = ''
    diagnostics = collections.deque(maxlen=20)
    warnings = 0
    semantic_error = False
    if mode == 'concise':
        print('nightshift: working…', file=sys.stderr, flush=True)
    try:
        child = subprocess.Popen(['bash', launcher, *args], env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, errors='replace', start_new_session=True)
    except OSError as error:
        print(f'nightshift: launch failed: {error}', file=sys.stderr)
        stdout_log.close()
        stderr_log.close()
        return 69

    def forward(signum, _frame):
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, forward)

    def read(stream, name):
        try:
            for line in stream:
                events.put((name, line))
        finally:
            stream.close()
            events.put((name, None))

    for name in ('stdout', 'stderr'):
        threading.Thread(target=read, args=(getattr(child, name), name), daemon=True).start()
    remaining = 2
    last_progress = time.monotonic()
    while remaining:
        if mode == 'concise' and time.monotonic() - last_progress >= 30:
            print('nightshift: still working…', file=sys.stderr, flush=True)
            last_progress = time.monotonic()
        try:
            name, line = events.get(timeout=30)
        except queue.Empty:
            continue
        if line is None:
            remaining -= 1
            continue
        log = stdout_log if name == 'stdout' else stderr_log
        log.write(line)
        log.flush()
        if mode == 'verbose':
            # Claude print mode needs stream-json to expose live tool activity.
            # Render its content blocks while retaining original events in logs.
            try:
                verbose_event = json.loads(line) if name == 'stdout' else {}
            except ValueError:
                verbose_event = {}
            if isinstance(verbose_event, dict) and verbose_event.get('type') in ('assistant', 'user'):
                message = verbose_event.get('message', {})
                blocks = message.get('content', []) if isinstance(message, dict) else []
                if not isinstance(blocks, list):
                    blocks = [{'type': 'text', 'text': str(blocks)}]
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    if block.get('type') == 'text':
                        print(block.get('text', ''), flush=True)
                    elif block.get('type') == 'tool_use':
                        print('[tool ' + str(block.get('name', 'unknown')) + '] ' + json.dumps(block.get('input', {})), flush=True)
                    elif block.get('type') == 'tool_result':
                        content = block.get('content', '')
                        print(content if isinstance(content, str) else json.dumps(content), flush=True)
            elif isinstance(verbose_event, dict) and verbose_event.get('type') == 'result':
                print(verbose_event.get('result') or json.dumps(verbose_event), flush=True)
            else:
                print(line, end='', file=sys.stdout if name == 'stdout' else sys.stderr, flush=True)
            continue
        if name == 'stderr':
            diagnostics.append(line.rstrip())
            if line.startswith('nightshift: awaiting spec approval;'):
                final = line.strip()
            if any(word in line.lower() for word in ('warning', ' error ', 'authrequired')):
                warnings += 1
            # Billing mode should remain explicit even with reduced output.
            if 'nightshift: authentication:' in line or 'nightshift: runtime:' in line:
                if mode == 'concise':
                    print(line, end='', file=sys.stderr, flush=True)
            continue
        try:
            event = json.loads(line)
        except ValueError:
            diagnostics.append(line.rstrip())
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get('type')
        item = event.get('item', {})
        if kind == 'item.completed' and isinstance(item, dict) and item.get('type') == 'agent_message':
            final = item.get('text', '')
        elif kind == 'workshop.progress' and mode == 'concise':
            print(f'nightshift: {event.get("stage")} (call {event.get("call")})', flush=True)
        elif kind == 'result':
            final = event.get('result', '') or final
            if event.get('is_error'):
                semantic_error = True
                print('nightshift: runtime reported failure: ' + str(event.get('errors') or final), file=sys.stderr, flush=True)
        elif kind == 'turn.failed':
            semantic_error = True
            print('nightshift: runtime turn failed: ' + str(event.get('error', 'unknown error')), file=sys.stderr, flush=True)
        elif kind == 'error':
            print('nightshift: runtime error: ' + str(event.get('message', event)), file=sys.stderr, flush=True)
    status = child.wait()
    status = 128 - status if status < 0 else status
    stdout_log.close()
    stderr_log.close()
    if mode != 'verbose':
        if final:
            print(final, flush=True)
        if status or semantic_error:
            print(f'nightshift: run failed (process exit {status}); recent diagnostics:', file=sys.stderr)
            print('\n'.join(diagnostics), file=sys.stderr)
        elif not final:
            print('nightshift: runtime returned no final answer; inspect the full log.', file=sys.stderr)
        if warnings and mode == 'concise':
            print(f'nightshift: {warnings} diagnostic warning/error lines retained in the log.', file=sys.stderr)
    print(f'nightshift: full logs: {directory}', file=sys.stderr)
    return status


if __name__ == '__main__':
    sys.exit(run(sys.argv[1], sys.argv[2:]))
