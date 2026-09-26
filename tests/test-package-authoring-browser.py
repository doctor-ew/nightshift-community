#!/usr/bin/env python3
"""Real browser and launcher author inline packages with synthetic executables."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
f=load('authoring_browser_fixture','tests/test-package-authoring.py')
i=load('authoring_browser_interface','tests/test-operation-interfaces.py')
case=f.Authoring('test_author_creates_child_contracts_without_caller_files');case.setUp()
try:
    root=case.root;env=i.isolated(root,initialize=False)
    bundle=root/'.nightshift-fixture-bin/authored-bundle.json';bundle.write_text(json.dumps(case.graph)+'\n')
    env['SYNTHETIC_PACKAGE_BUNDLE']=str(bundle)
    env['PLAYWRIGHT_BROWSERS_PATH']=os.environ.get('PLAYWRIGHT_BROWSERS_PATH',str(Path.home()/('Library/Caches/ms-playwright' if __import__('sys').platform=='darwin' else '.cache/ms-playwright')))
    env['NIGHTSHIFT_BROWSER_ARTIFACTS']=str(ROOT/'test-output/authoring-browser')
    with tempfile.TemporaryFile(mode='w+') as errors:
        server=subprocess.Popen(['python3',str(ROOT/'dashboard/server.py'),'--project',str(root),'--port','0'],env=env,stdout=subprocess.PIPE,stderr=errors,text=True)
        try:
            url=server.stdout.readline().strip()
            if not url.startswith('http://127.0.0.1:'):raise RuntimeError('Synthetic dashboard did not start')
            env.update(NIGHTSHIFT_BROWSER_URL=url,NIGHTSHIFT_BROWSER_PROJECT=str(root))
            subprocess.run(['node',str(ROOT/'dashboard/test-packages-browser.mjs')],env=env,check=True,timeout=180)
            assert not (root/'docs/left').exists()
        finally:
            server.terminate();server.communicate(timeout=10)
finally:case.doCleanups()
