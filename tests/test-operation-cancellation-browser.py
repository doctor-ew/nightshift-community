#!/usr/bin/env python3
"""Actual browser cancellation against one disposable synthetic provider."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cancel_browser_fixture',ROOT/'tests/test-operation-interfaces.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
with tempfile.TemporaryDirectory(prefix='nightshift-cancel-browser-') as directory:
    root=Path(directory).resolve();env=f.isolated(root)
    env.update(SYNTHETIC_PAUSE='15',NIGHTSHIFT_BROWSER_PROJECT=str(root),NIGHTSHIFT_BROWSER_ARTIFACTS=str(ROOT/'test-output/cancellation-browser'))
    env['PLAYWRIGHT_BROWSERS_PATH']=os.environ.get('PLAYWRIGHT_BROWSERS_PATH',str(Path.home()/('Library/Caches/ms-playwright' if __import__('sys').platform=='darwin' else '.cache/ms-playwright')))
    with tempfile.TemporaryFile(mode='w+') as errors:
        server=subprocess.Popen(['python3',str(ROOT/'dashboard/server.py'),'--project',str(root),'--port','0'],env=env,stdout=subprocess.PIPE,stderr=errors,text=True)
        try:
            env['NIGHTSHIFT_BROWSER_URL']=server.stdout.readline().strip()
            subprocess.run(['node',str(ROOT/'dashboard/test-cancellation-browser.mjs')],env=env,check=True,timeout=90)
        finally:server.terminate();server.communicate(timeout=10)
