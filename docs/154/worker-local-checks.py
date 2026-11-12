#!/usr/bin/env python3
"""Public QA probe: worker evidence writes and declared local HTTP/SQLite/browser checks."""
import argparse
import http.server
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--playwright-module', required=True)
parser.add_argument('--evidence', required=True)
args = parser.parse_args()
module = Path(args.playwright_module).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='nightshift-worker-local-') as temporary:
    directory = Path(temporary)
    connection = sqlite3.connect(directory / 'probe.sqlite3')
    connection.execute('CREATE TABLE probe (value TEXT NOT NULL)')
    connection.execute('INSERT INTO probe VALUES (?)', ('worker-local-check-ok',))
    connection.commit()
    value, = connection.execute('SELECT value FROM probe').fetchone()
    connection.close()
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            content = ('<html><body><main>' + value + '</main></body></html>').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, *_):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = 'http://127.0.0.1:' + str(server.server_port)
    try:
        assert value in urllib.request.urlopen(url).read().decode()
        javascript = """
import assert from 'node:assert/strict';
const {chromium} = await import(process.argv[1]);
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage();
  await page.goto(process.argv[2]);
  assert.equal(await page.locator('main').textContent(), 'worker-local-check-ok');
} finally { await browser.close(); }
"""
        subprocess.run(['node', '--input-type=module', '-e', javascript,
                        module.as_uri(), url], check=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    evidence = Path(args.evidence)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps({'version':1,'sqlite':'pass','http':'pass',
                                    'browser':'pass','worker_evidence_write':'pass'}, indent=2)+'\n')
    assert json.loads(evidence.read_text())['browser'] == 'pass'
print('Declared local SQLite, HTTP, browser and evidence-write checks passed.')
