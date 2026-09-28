#!/usr/bin/env python3
"""Launch actual dashboard/browser against disposable synthetic provider fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('interfaces', ROOT / 'tests/test-operation-interfaces.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

with tempfile.TemporaryDirectory(prefix='nightshift-browser-synthetic-') as directory:
    root = Path(directory)
    packages = os.environ.get('NIGHTSHIFT_PACKAGE_BROWSER') == '1'
    if packages:
        package_spec = importlib.util.spec_from_file_location('package_browser_fixture', ROOT/'tests/test-package-controller.py')
        fixture = importlib.util.module_from_spec(package_spec);package_spec.loader.exec_module(fixture)
        fixture.fixture(root)
    env = f.isolated(root, initialize=not packages)
    env['SYNTHETIC_FAILURE_CONTROL']=str(root/'.synthetic-review-failure')
    env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ("Library/Caches/ms-playwright" if __import__("sys").platform == "darwin" else ".cache/ms-playwright")))
    with tempfile.TemporaryFile(mode='w+') as errors:
        server = subprocess.Popen(['python3', str(ROOT / 'dashboard/server.py'), '--project', str(root), '--port', '0'], env=env, stdout=subprocess.PIPE, stderr=errors, text=True)
        try:
            url = server.stdout.readline().strip()
            if not url.startswith('http://127.0.0.1:'):
                raise RuntimeError('Synthetic dashboard did not start')
            env.update(NIGHTSHIFT_BROWSER_URL=url, NIGHTSHIFT_BROWSER_PROJECT=str(root))
            # The complete default journey includes typed verification, repair exhaustion,
            # and external adoption. Per-action waits and controller allowances stay bounded.
            journey_timeout = 360
            started = time.monotonic()
            completed = False
            try:
                subprocess.run(['node', str(ROOT / ('dashboard/test-packages-browser.mjs' if packages else 'dashboard/test-browser.mjs'))], env=env, check=True, timeout=journey_timeout)
                completed = True
            finally:
                artifacts = Path(env.get('NIGHTSHIFT_BROWSER_ARTIFACTS', ROOT / ('test-output/packages-browser' if packages else 'test-output/browser')))
                artifacts.mkdir(parents=True, exist_ok=True)
                (artifacts / 'journey.json').write_text(json.dumps(dict(completed=completed, packages=packages, elapsed_seconds=time.monotonic()-started, watchdog_seconds=journey_timeout), indent=2)+'\n')
        finally:
            server.terminate()
            server.communicate(timeout=10)
