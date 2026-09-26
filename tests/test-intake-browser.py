#!/usr/bin/env python3
"""Fresh local and GitHub intake through actual browser, synthetic providers only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('intake_browser_fixture',ROOT/'tests/test-operation-interfaces.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
with tempfile.TemporaryDirectory(prefix='nightshift-intake-browser-') as directory:
    root=Path(directory).resolve();env=f.isolated(root)
    gh=root/'.nightshift-fixture-bin/gh'
    gh.write_text('#!/usr/bin/env python3\nimport json,sys\nassert sys.argv[1:3]==["issue","view"]\nprint(json.dumps(dict(title="Synthetic fresh request",body="Return two.",labels=[],url="https://github.com/synthetic/disposable/issues/777",state="OPEN")))\n');gh.chmod(0o755)
    env['PLAYWRIGHT_BROWSERS_PATH']=os.environ.get('PLAYWRIGHT_BROWSERS_PATH',str(Path.home()/('Library/Caches/ms-playwright' if __import__('sys').platform=='darwin' else '.cache/ms-playwright')))
    env.update(NIGHTSHIFT_BROWSER_PROJECT=str(root),NIGHTSHIFT_BROWSER_ARTIFACTS=str(ROOT/'test-output/intake-browser'))
    with tempfile.TemporaryFile(mode='w+') as errors:
        server=subprocess.Popen(['python3',str(ROOT/'dashboard/server.py'),'--project',str(root),'--port','0'],env=env,stdout=subprocess.PIPE,stderr=errors,text=True)
        try:
            url=server.stdout.readline().strip();assert url.startswith('http://127.0.0.1:');env['NIGHTSHIFT_BROWSER_URL']=url
            subprocess.run(['node',str(ROOT/'dashboard/test-intake-browser.mjs')],env=env,check=True,timeout=240)
        finally:server.terminate();server.communicate(timeout=10)
