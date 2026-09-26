#!/usr/bin/env python3
"""Fresh source intake through an actual browser, synthetic launchers and local HTTP."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('intake_browser_fixture',ROOT/'tests/test-operation-interfaces.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
for reference in ('spec:request.md','gh:synthetic/project#123'):
    with tempfile.TemporaryDirectory(prefix='nightshift-intake-browser-') as directory:
        root=Path(directory);env=f.isolated(root)
        data=dict(number=123,title='Synthetic request',body='Return two.',state='OPEN',labels=[],url='https://github.com/synthetic/project/issues/123')
        gh=root/'.nightshift-fixture-bin/gh';gh.write_text('#!/usr/bin/env python3\nprint('+repr(json.dumps(data))+')\n');gh.chmod(0o755)
        env.update(PLAYWRIGHT_BROWSERS_PATH=os.environ.get('PLAYWRIGHT_BROWSERS_PATH',str(Path.home()/('Library/Caches/ms-playwright' if __import__('sys').platform=='darwin' else '.cache/ms-playwright'))),NIGHTSHIFT_INTAKE_REFERENCE=reference)
        with tempfile.TemporaryFile(mode='w+') as errors:
            server=subprocess.Popen(['python3',str(ROOT/'dashboard/server.py'),'--project',str(root),'--port','0'],env=env,stdout=subprocess.PIPE,stderr=errors,text=True)
            try:
                url=server.stdout.readline().strip()
                if not url.startswith('http://127.0.0.1:'):raise RuntimeError('Disposable intake server failed to start')
                env.update(NIGHTSHIFT_BROWSER_URL=url,NIGHTSHIFT_BROWSER_PROJECT=str(root))
                subprocess.run(['node',str(ROOT/'dashboard/test-intake-browser.mjs')],env=env,check=True,timeout=180)
            finally:server.terminate();server.communicate(timeout=10)
