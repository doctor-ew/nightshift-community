"""Loopback evidence transport with version-bound workshop spec approval."""
import argparse
import importlib.util
import secrets
import json
import os
import stat
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/assets/app.js': ('assets/app.js', 'text/javascript; charset=utf-8'),
          '/assets/app.css': ('assets/app.css', 'text/css; charset=utf-8')}
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, project, port):
        self.project = project
        self.approval_token = secrets.token_urlsafe(32)
        self.snapshot = None
        self.collected_at = 0
        self.collect_lock = threading.Lock()
        super().__init__(('127.0.0.1', port), Handler)

    def collect(self):
        with self.collect_lock:
            if self.snapshot is None or time.monotonic() - self.collected_at >= 2:
                result = subprocess.run(['bash', str(ROOT / 'scripts/nightshift-dashboard.sh'),
                    '--project', self.project, '--json'], capture_output=True, timeout=15, check=True)
                snapshot = json.loads(result.stdout)
                self.snapshot = json.dumps(snapshot, ensure_ascii=True).encode()
                self.collected_at = time.monotonic()
            return self.snapshot

    def evidence(self, uri):
        snapshot = json.loads(self.collect())
        allowed = {link['href'] for row in snapshot.get('rows', [])
                   for link in row.get('links', []) if link and link.get('href')}
        for ticket in action_module().list_tickets(self.project):
            job = ticket.get('launch') or {}
            if job.get('log'): allowed.add(Path(job['log']).as_uri())
            if job.get('evidence'):
                for name in ('status.json', 'repair.diff', 'proposal.json', 'review.json', 'verification.json'):
                    allowed.add((Path(job['evidence']) / name).as_uri())
        parsed = urlsplit(uri)
        if uri not in allowed or parsed.scheme != 'file' or parsed.netloc:
            raise ValueError('Unknown evidence')
        path = Path(unquote(parsed.path))
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe evidence path')
        # Open every component without following links, including parent directories.
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in path.parts[1:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(file_fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 1_048_576:
                    raise ValueError('Evidence is not a bounded regular file')
                content = stream.read(1_048_577)
                if len(content) > 1_048_576:
                    raise ValueError('Evidence is too large')
                return content
        finally:
            os.close(fd)



def operation_module():
    spec = importlib.util.spec_from_file_location('operations', ROOT / 'scripts/nightshift-operations.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def action_module():
    spec = importlib.util.spec_from_file_location('console_actions', ROOT / 'scripts/nightshift-console-actions.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def chat_module():
    spec = importlib.util.spec_from_file_location('console_chat', ROOT / 'scripts/nightshift-console-chat.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def decision_module():
    spec = importlib.util.spec_from_file_location('console_decisions', ROOT / 'scripts/nightshift-console-decisions.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def review_module():
    spec = importlib.util.spec_from_file_location('workshop_review', ROOT / 'scripts/nightshift-workshop-review.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, code, body=b'', content_type='text/plain; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_GET(self):
        expected = '127.0.0.1:%d' % self.server.server_port
        if (self.headers.get('Host') != expected
                or self.headers.get('Origin', 'http://' + expected) != 'http://' + expected
                or self.headers.get('Sec-Fetch-Site') == 'cross-site'):
            self.reply(403, b'Local same-origin access only')
            return
        if self.path == '/api/identity':
            self.reply(200, json.dumps({'service': 'nightshift-dashboard', 'root': self.server.project, 'workshop_review_api': 2, 'ticket_actions_api': 2, 'recovery_decisions_api': 1, 'operations_api': 1, 'evidence_api': 1, 'ticket_chat_api': 1, 'ticket_decisions_api': 1}).encode(), 'application/json')
            return
        if self.path == '/api/workshop/reviews':
            try:
                self.reply(200, json.dumps(dict(reviews=review_module().list_reviews(self.server.project), token=self.server.approval_token)).encode(), 'application/json')
            except (ValueError, OSError, subprocess.SubprocessError):
                self.reply(503, b'Review collection unavailable')
            return
        if urlsplit(self.path).path == '/api/tickets/chat':
            try:
                query = parse_qs(urlsplit(self.path).query, strict_parsing=True)
                if set(query) != {'task'} or len(query['task']) != 1:
                    raise ValueError('Invalid chat query')
                action_module().state(self.server.project, query['task'][0])
                value = chat_module().state(self.server.project, query['task'][0])
                self.reply(200, json.dumps(value).encode(), 'application/json')
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                self.reply(409, json.dumps({'error': str(error)}).encode(), 'application/json')
            return
        if self.path == '/api/intake':
            try:
                value=operation_module().api(self.server.project,dict(action='intake-bootstrap'))
                self.reply(200,json.dumps(dict(view=value,token=self.server.approval_token)).encode(),'application/json')
            except (OSError,ValueError,subprocess.SubprocessError) as error:self.reply(409,json.dumps(dict(error=str(error))).encode(),'application/json')
            return
        if urlsplit(self.path).path == '/api/operations':
            try:
                query = parse_qs(urlsplit(self.path).query, strict_parsing=True)
                if set(query) != {'task'} or len(query['task']) != 1: raise ValueError('Invalid operation query')
                view = operation_module().api(self.server.project, dict(task=query['task'][0], action='view'))
                self.reply(200, json.dumps(dict(view=view, token=self.server.approval_token)).encode(), 'application/json')
            except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
                self.reply(409, json.dumps({'error':str(error)}).encode(), 'application/json')
            return
        if self.path == '/api/tickets':
            try:
                self.reply(200, json.dumps(dict(tickets=action_module().list_tickets(self.server.project), token=self.server.approval_token)).encode(), 'application/json')
            except (ValueError, OSError, subprocess.SubprocessError):
                self.reply(503, b'Ticket actions unavailable')
            return
        if self.path == '/api/state':
            try:
                self.reply(200, self.server.collect(), 'application/json')
            except (subprocess.SubprocessError, ValueError, OSError):
                self.reply(503, b'{"error":"State collection unavailable; retry shortly"}', 'application/json')
            return
        if urlsplit(self.path).path == '/api/evidence':
            try:
                query = parse_qs(urlsplit(self.path).query, strict_parsing=True)
                if set(query) != {'uri'} or len(query['uri']) != 1:
                    raise ValueError('Invalid evidence request')
                self.reply(200, self.server.evidence(query['uri'][0]))
            except (ValueError, OSError, subprocess.SubprocessError):
                self.reply(404, b'Evidence unavailable or outside collected artifacts')
            return
        asset = ASSETS.get('/') if urlsplit(self.path).path == '/evidence' else ASSETS.get(self.path)
        if asset is None:
            self.reply(404, b'Not found')
            return
        try:
            self.reply(200, (ROOT / 'dashboard' / 'dist' / asset[0]).read_bytes(), asset[1])
        except OSError:
            self.reply(503, b'Dashboard bundle missing; run npm ci && npm run build in dashboard/')

    def reject_method(self):
        self.reply(405, b'Read-only dashboard; GET required')

    def do_POST(self):
        if self.path not in ('/api/operations', '/api/tickets/recovery-assess', '/api/tickets/recovery-authorize', '/api/tickets/recovery-resume', '/api/workshop/approve', '/api/tickets/resume', '/api/tickets/continue', '/api/tickets/cleanup', '/api/tickets/repair', '/api/tickets/stop', '/api/tickets/chat', '/api/tickets/decision'):
            self.reject_method(); return
        expected = '127.0.0.1:%d' % self.server.server_port
        if (self.headers.get('Host') != expected or self.headers.get('Origin') != 'http://' + expected
                or self.headers.get('Sec-Fetch-Site') == 'cross-site'
                or not secrets.compare_digest(self.headers.get('X-Nightshift-Token', ''), self.server.approval_token)):
            self.reply(403, b'Local same-origin approval required'); return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= (16384 if self.path in ('/api/operations', '/api/tickets/chat', '/api/tickets/decision') else 4096) or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type') != 'application/json':
                raise ValueError('Invalid request')
            self.connection.settimeout(5)
            body = json.loads(self.rfile.read(length))
            if self.path == '/api/operations':
                result = operation_module().api(self.server.project, body)
                self.reply(200, json.dumps(result).encode(), 'application/json')
                return
            allowed = {'task', 'sha256', 'assessment_sha256', 'operator'} if self.path in ('/api/tickets/recovery-authorize','/api/tickets/recovery-resume') else {'task', 'sha256', 'budget_revision'} if self.path == '/api/tickets/continue' else {'task', 'sha256', 'decision_sha256', 'choice', 'answer'} if self.path == '/api/tickets/decision' else {'task', 'sha256', 'provider', 'message'} if self.path == '/api/tickets/chat' else {'task', 'sha256', 'provider'} if self.path == '/api/tickets/repair' else {'task', 'sha256'}
            if not isinstance(body, dict) or set(body) != allowed or not all(isinstance(v, str) for v in body.values()):
                raise ValueError('Invalid approval')
            if self.path.startswith('/api/tickets/recovery-'):
                result = action_module().recovery_action(self.server.project,body['task'],body['sha256'],self.path.rsplit('/',1)[1],body.get('assessment_sha256',''),body.get('operator',''))
            elif self.path == '/api/workshop/approve':
                result = review_module().approve_and_continue(self.server.project, body['task'], body['sha256'])
            elif self.path == '/api/tickets/decision':
                result = decision_module().submit(self.server.project, body['task'], body['sha256'], body['decision_sha256'], body['choice'], body['answer'])
            elif self.path == '/api/tickets/chat':
                result = chat_module().start(self.server.project, body['task'], body['sha256'], body['provider'], body['message'])
            else:
                result = action_module().action(self.server.project, body['task'], body['sha256'], self.path.rsplit('/', 1)[1], provider=body.get('provider', 'auto'), **({'budget_revision': body['budget_revision']} if self.path == '/api/tickets/continue' else {}))
            self.reply(200, json.dumps(result).encode(), 'application/json')
        except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
            self.reply(409, json.dumps({'error': str(error)}).encode(), 'application/json')

    do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = reject_method


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = DashboardServer(args.project, args.port)
    print('http://127.0.0.1:%d' % server.server_port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
