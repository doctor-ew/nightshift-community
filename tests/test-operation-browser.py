#!/usr/bin/env python3
"""Launch actual dashboard/browser against disposable synthetic provider fixtures."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('interfaces', ROOT / 'tests/test-operation-interfaces.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

with tempfile.TemporaryDirectory(prefix='nightshift-browser-synthetic-') as directory:
    root = Path(directory)
    env = f.isolated(root)
    env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ("Library/Caches/ms-playwright" if __import__("sys").platform == "darwin" else ".cache/ms-playwright")))
    with tempfile.TemporaryFile(mode='w+') as errors:
        server = subprocess.Popen(['python3', str(ROOT / 'dashboard/server.py'), '--project', str(root), '--port', '0'], env=env, stdout=subprocess.PIPE, stderr=errors, text=True)
        try:
            url = server.stdout.readline().strip()
            if not url.startswith('http://127.0.0.1:'):
                raise RuntimeError('Synthetic dashboard did not start')
            env.update(NIGHTSHIFT_BROWSER_URL=url, NIGHTSHIFT_BROWSER_PROJECT=str(root))
            subprocess.run(['node', str(ROOT / 'dashboard/test-browser.mjs')], env=env, check=True, timeout=180)
        finally:
            server.terminate()
            server.communicate(timeout=10)
