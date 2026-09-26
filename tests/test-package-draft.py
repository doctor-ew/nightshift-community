#!/usr/bin/env python3
"""Synthetic autonomous child artifact drafting and rejection boundaries."""
import copy
import difflib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('draft_fixture',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m


def fixture(root):
    plan=f.fixture(root)
    plan['inputs'].update(request='request.md',spec='graph.json')
    plan['scope']=['left.py','right.py','integration.py']
    plan['aggregate']=dict(calls=32,seconds=300,wall_seconds=300)
    policy=dict(version=1,limits=plan['limits'],aggregate=dict(calls=8,seconds=60,wall_seconds=60),reviewer_policy=plan['reviewer_policy'],environment={})
    (root/'package-template.json').write_text(json.dumps(policy))
    plan['package_draft']=dict(version=1,slots=['left','right','integration'],template='package-template.json',aggregate=dict(calls=32,seconds=300,wall_seconds=300),max_bytes=65536)
    files={};children=[]
    cases=json.dumps(dict(version=1,cases=[dict(id='two',requirement='Return two',manual=False)]))
    for key in plan['package_draft']['slots']:
        (root/(key+'.py')).write_text('def value(): return 2\n')
        child=copy.deepcopy(plan);child.pop('package_draft');child['scope']=[key+'.py'];child['aggregate']=policy['aggregate']
        child['inputs'].update(spec=f'docs/{key}/SPEC.md',scenarios=f'docs/{key}/scenarios.json')
        child['checks']=[dict(id='unit',argv=['python3',f'docs/{key}/checks.py'])]
        files[f'docs/{key}/operations.json']=json.dumps(child)+'\n'
        files[child['inputs']['spec']]='Return two for package '+key+'.\n'
        files[child['inputs']['scenarios']]=cases+'\n'
        files[f'docs/{key}/checks.py']='import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parents[2]))\nimport unittest\nfrom '+key+' import value\nclass T(unittest.TestCase):\n def test_two(self): self.assertEqual(value(),2)\nunittest.main()\n'
        reads=list(child['inputs'].values())+[f'docs/{key}/checks.py']
        if key=='integration':reads+=['left.py','right.py']
        children.append(dict(id=key,ref='spec:'+child['inputs']['spec'],depends_on=['left','right'] if key=='integration' else [],requirements=['two'],integration=key=='integration',plan=f'docs/{key}/operations.json',reads=reads,writes=child['scope'],interfaces=[dict(id='value',version='1',path=key+'.py',contract='Return two.')],allowance=child['aggregate']))
    graph=dict(version=1,parent='spec:request.md',requirements=['two'],children=children,aggregate=plan['package_draft']['aggregate'])
    (root/'graph.json').write_text(json.dumps(dict(graph,children=[]))+'\n')
    files['graph.json']=json.dumps(graph)+'\n';files['scenarios.json']=cases+'\n'
    (root/'docs/demo/operations.json').write_text(json.dumps(plan))
    return plan,files


def patch(root,files):
    result=''
    for name,text in files.items():
        exists=(root/name).exists();before=(root/name).read_text() if exists else ''
        result+=''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='a/'+name if exists else '/dev/null',tofile='b/'+name))
    return result


class Draft(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-package-draft-test-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.plan,self.files=fixture(self.root);self.worker=f.Worker()
        base=self.worker
        def worker(operation,*args):
            base.patch=patch(self.root,self.files) if operation=='groom-spec' and 'graph.json' in args[0]['artifacts'] else ''
            return base(operation,*args)
        self.c=m.Operations(self.root,'demo',worker);self.invoke=worker
    def grant(self):
        assessment=self.c.assess('groom-spec');self.assertEqual(assessment['status'],'ready',assessment)
        return self.c.authorize(m.RECIPES['groom'],assessment['binding'],'synthetic','draft')['id']
    def test_no_child_artifacts_to_prepared_composition_and_replay(self):
        self.assertFalse((self.root/'docs/left').exists())
        grant=self.grant();result=self.c.chain(grant)
        self.assertTrue(all(r['status'] in ('passed','reused') for r in result['results']),[(r['status'],r.get('reason')) for r in result['results']])
        self.assertEqual(len(self.worker.calls),2)
        self.assertIn('docs/left/checks.py',self.worker.packets[-1]['artifacts'])
        prior=list(self.worker.calls);self.c.chain(grant);self.assertEqual(prior,self.worker.calls)
        packages=m.load('package-controller').Packages(self.root,'demo',self.invoke)
        assessment=packages.assess();self.assertEqual(assessment['status'],'ready',assessment)
        packages.authorize(assessment['binding'],'synthetic','compose')
        result=packages.run('compose');self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(result['usage']['calls'],14)
    def test_invalid_candidate_never_writes_parent(self):
        child=json.loads(self.files['docs/left/operations.json']);child['scope']=['app.py'];self.files['docs/left/operations.json']=json.dumps(child)+'\n'
        before={name:(self.root/name).read_bytes() for name in self.c.corpus()}
        result=self.c.execute(self.grant(),'groom-spec','invalid')
        self.assertEqual(result['status'],'failed',result)
        self.assertFalse((self.root/'docs/left').exists())
        self.assertEqual(before,{name:(self.root/name).read_bytes() for name in before})
        self.assertEqual(len(self.worker.calls),1)
    def test_expanded_budget_and_weakened_policy_reject(self):
        for mutation in ('budget','policy'):
            with self.subTest(mutation=mutation):
                files=copy.deepcopy(self.files)
                if mutation=='budget':
                    graph=json.loads(files['graph.json']);graph['aggregate']['calls']=33;files['graph.json']=json.dumps(graph)
                else:
                    child=json.loads(files['docs/left/operations.json']);child['reviewer_policy']['require_different_provider']=False;files['docs/left/operations.json']=json.dumps(child)
                changes={name:dict(before=None,text=text,after=m.hashlib.sha256(text.encode()).hexdigest()) for name,text in files.items()}
                with self.assertRaises(ValueError):m.load('package-draft').validate_candidate(self.c,self.plan,changes)
                self.assertFalse((self.root/'docs/left').exists())


if __name__=='__main__':unittest.main()
