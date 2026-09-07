"""Read-only loopback transport for the existing bounded Nightshift collector."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/assets/app.js': ('assets/app.js', 'text/javascript; charset=utf-8'),
          '/assets/app.css': ('assets/app.css', 'text/css; charset=utf-8')}
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, project, port):
        self.project = project
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
        if self.path == '/api/state':
            try:
                self.reply(200, self.server.collect(), 'application/json')
            except (subprocess.SubprocessError, ValueError, OSError):
                self.reply(503, b'{"error":"State collection unavailable; retry shortly"}', 'application/json')
            return
        asset = ASSETS.get(self.path)
        if asset is None:
            self.reply(404, b'Not found')
            return
        try:
            self.reply(200, (ROOT / 'dashboard' / 'dist' / asset[0]).read_bytes(), asset[1])
        except OSError:
            self.reply(503, b'Dashboard bundle missing; run npm ci && npm run build in dashboard/')

    def reject_method(self):
        self.reply(405, b'Read-only dashboard; GET required')

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = reject_method


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
