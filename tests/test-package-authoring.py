#!/usr/bin/env python3
"""Autonomous decomposition authoring inside one bounded Groom artifact."""
import copy
import difflib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
f=load('authoring_fixture','tests/test-package-controller.py')
m=load('authoring_controller','scripts/nightshift-package-controller.py')

class Authoring(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-package-authoring-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);base=f.f.f.fixture(self.root)
        with tempfile.TemporaryDirectory(prefix='nightshift-authored-fixture-') as directory:
            seed=Path(directory);graph=f.fixture(seed)
            for name in ('parent.md','scenarios.json'):(self.root/name).write_bytes((seed/name).read_bytes())
            artifacts={}
            for child in graph['children']:
                for name in child['reads']+child['writes']+[child['plan']]:
                    if not (self.root/name).exists():artifacts[name]=(seed/name).read_text()
        graph.update(version=3,templates=[dict(id='standard',version=1,operations=m.ops.RECIPES['factory'])],artifacts=artifacts)
        for child in graph['children']:child['template']='standard'
        self.graph=graph
        base['inputs'].update(request='parent.md',spec='graph.json')
        (self.root/'docs/demo/operations.json').write_text(json.dumps(base))
        self.draft=dict(version=3,parent='spec:parent.md',requirements=['R1'],children=[],templates=graph['templates'],artifacts={},aggregate=graph['aggregate'])
        (self.root/'graph.json').write_text(json.dumps(self.draft)+'\n')
        self.worker=f.f.f.Worker()
        def author(operation,packet,route,output,seconds):
            self.worker.patch=''
            if operation=='groom-spec' and 'graph.json' in packet['artifacts']:
                before=packet['artifacts']['graph.json'];after=json.dumps(self.graph)
                self.worker.patch=''.join(difflib.unified_diff(before.splitlines(keepends=True),(after+'\n').splitlines(keepends=True),fromfile='a/graph.json',tofile='b/graph.json'))
            return self.worker(operation,packet,route,output,seconds)
        self.c=m.Packages(self.root,'demo',author)
    def test_author_creates_child_contracts_without_caller_files(self):
        before={path.relative_to(self.root).as_posix():path.read_bytes() for path in self.root.rglob('*') if path.is_file() and '.git' not in path.parts}
        prep=self.c.preparation;a=prep.assess('groom-spec')
        g=prep.authorize(m.ops.RECIPES['groom'],a['binding'],'synthetic','author')
        result=self.c.prepare(g['id']);self.assertEqual(result['status'],'ready',result)
        self.assertEqual(len(self.worker.calls),2)
        self.assertFalse((self.root/'docs/left').exists())
        for name,data in before.items():
            if name!='graph.json':self.assertEqual((self.root/name).read_bytes(),data,name)
        grant=self.c.authorize(result['binding'],'synthetic','compose')
        result=self.c.run(grant['id']);self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(len(self.worker.calls),14)
        self.assertFalse((self.root/'docs/left').exists())

if __name__=='__main__':unittest.main()
