#!/usr/bin/env python3
"""Start or reuse a per-project read-only loopback dashboard."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
CHILDREN = {}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def belongs(url, project):
    project = Path(project).resolve()
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username:
        return False
    try:
        if not parsed.port or not 1 <= parsed.port <= 65535:
            return False
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(url.rstrip('/') + '/api/identity', timeout=1) as response:
                identity = json.loads(response.read(16384))
        except urllib.error.HTTPError as error:
            if error.code != 404:
                return False
            # Compatibility with already-running dashboards from older installs.
            with opener.open(url.rstrip('/') + '/api/state', timeout=2) as response:
                state = json.loads(response.read(1048576))
            return (state.get('root') == str(project)
                    and isinstance(state.get('rows'), list)
                    and isinstance(state.get('checkouts'), list)
                    and 'generated_at' in state)
        return identity.get('service') == 'nightshift-dashboard' and identity.get('root') == str(project)
    except (OSError, ValueError, urllib.error.URLError):
        return False


def start(project, browser='once', port=8765):
    project = Path(project).resolve(strict=True)
    home = Path(os.environ.get('NIGHTSHIFT_HOME', str(Path.home() / '.nightshift')))
    directory = home / 'dashboards'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(str(project).encode()).hexdigest()[:20]
    state = directory / (key + '.json')
    with (directory / (key + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        candidates = ['http://127.0.0.1:' + str(port)] if port else []
        try:
            candidates.insert(0, json.loads(state.read_text())['url'])
        except (OSError, ValueError, KeyError):
            pass
        for url in candidates:
            if isinstance(url, str) and belongs(url, project):
                return {'status': 'reused', 'url': url}
        # Try preferred port; if occupied by another service/project, use an
        # OS-selected port. Never kill or reuse a different project's listener.
        for candidate in dict.fromkeys((port, 0)):
            with tempfile.NamedTemporaryFile(prefix=key + '-', suffix='.log', dir=directory, delete=False) as log:
                child = subprocess.Popen([sys.executable, str(ROOT / 'dashboard/server.py'), '--project', str(project), '--port', str(candidate)], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                log_path = Path(log.name)
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and child.poll() is None:
                first = log_path.read_text().splitlines()
                url = first[0] if first else ''
                if url.startswith('http://127.0.0.1:') and belongs(url, project):
                    result = {'status': 'started', 'url': url, 'pid': child.pid}
                    CHILDREN[child.pid] = child
                    with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as out:
                        json.dump(result, out)
                    os.replace(out.name, state)
                    if browser == 'once':
                        try:
                            webbrowser.open(url, new=2)
                        except webbrowser.Error:
                            pass
                    return result
                time.sleep(0.1)
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
        raise RuntimeError('Dashboard did not become ready; inspect private dashboard logs')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--browser', choices=('once', 'off'), default='once')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be 0..65535')
    try:
        result = start(args.project, args.browser, args.port)
        print('nightshift: dashboard (' + result['status'] + '): ' + result['url'], file=sys.stderr)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('nightshift: dashboard unavailable (' + type(error).__name__ + '); factory may continue', file=sys.stderr)
        sys.exit(1)
