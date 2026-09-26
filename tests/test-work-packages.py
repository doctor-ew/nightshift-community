#!/usr/bin/env python3
"""Public synthetic package contracts; no providers or caller state changes."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packages', ROOT/'scripts/nightshift-work-packages.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
fixture_spec=importlib.util.spec_from_file_location('fixture', ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(fixture_spec);fixture_spec.loader.exec_module(f)


def fixture(root):
    base=f.fixture(root)
    (root/'parent.md').write_text('Combine independent functions into a total.\n')
    children=[]
    for i, name in enumerate(('left','right','integration')):
        (root/'docs'/name).mkdir(parents=True)
        p=copy.deepcopy(base)
        p['inputs']['spec']='docs/'+name+'/SPEC.md'
        (root/p['inputs']['spec']).write_text('Package '+name+' implements R1.\n')
        p['scope']=[name+'.py']
        p['checks']=[dict(id='unit',argv=['python3',name+'_test.py'])]
        p['aggregate']=dict(calls=8,seconds=60,wall_seconds=60)
        (root/(name+'.py')).write_text('def value(): return 1\n')
        (root/(name+'_test.py')).write_text('import unittest\nfrom '+name+' import value\nclass T(unittest.TestCase):\n def test_value(self): self.assertEqual(value(), 1)\nunittest.main()\n')
        plan='docs/'+name+'/operations.json';(root/plan).write_text(json.dumps(p))
        reads=list(p['inputs'].values())+[name+'_test.py']
        if name=='integration':reads+=['left.py','right.py']
        children.append(dict(id=name,ref='spec:'+p['inputs']['spec'],depends_on=['left','right'] if i==2 else [],requirements=['R1'],integration=i==2,
            plan=plan,reads=reads,writes=p['scope'],interfaces=[dict(id='value',version='1',path=name+'.py',contract='Return one integer.')],allowance=p['aggregate']))
    graph=dict(version=1,parent='spec:parent.md',requirements=['R1'],children=children,aggregate=dict(calls=24,seconds=180,wall_seconds=180))
    (root/'graph.json').write_text(json.dumps(graph))
    return graph


class Packages(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='nightshift-packages-');self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.graph=fixture(self.root)
    def test_valid_contract_is_not_semantic_approval(self):
        result=m.validate(self.root,self.graph)
        self.assertEqual([c['id'] for c in result['children']],['left','right','integration'])
        self.assertFalse(result['semantic_approval'])
        self.assertEqual(m.template(self.graph),self.graph)
    def test_cycles_missing_dependencies_and_coverage(self):
        for mutate in (lambda g:g['children'][0]['depends_on'].append('integration'),lambda g:g['children'][0]['depends_on'].append('absent'),lambda g:g['requirements'].append('R2')):
            with self.subTest(mutation=mutate):
                g=copy.deepcopy(self.graph);mutate(g)
                with self.assertRaises(ValueError):m.validate(self.root,g)
    def test_conflicting_writes_rejected(self):
        g=self.graph;c=g['children'][1];c['writes']=['left.py'];c['interfaces'][0]['path']='left.py'
        p=json.loads((self.root/c['plan']).read_text());p['scope']=['left.py'];(self.root/c['plan']).write_text(json.dumps(p))
        with self.assertRaisesRegex(ValueError,'conflicting_package_writes'):m.validate(self.root,g)
    def test_undeclared_reads_and_missing_inputs_rejected(self):
        self.graph['children'][0]['reads'].append('right.py')
        with self.assertRaisesRegex(ValueError,'undeclared_package_dependency'):m.validate(self.root,self.graph)
        self.graph['children'][0]['reads'].pop();self.graph['children'][0]['reads'].append('absent.py')
        with self.assertRaisesRegex(ValueError,'package_input_missing'):m.validate(self.root,self.graph)
    def test_parent_budget_covers_all_children(self):
        for key in ('calls','seconds','wall_seconds'):
            g=copy.deepcopy(self.graph);g['aggregate'][key]-=1
            with self.assertRaisesRegex(ValueError,'parent_allowance_insufficient'):m.validate(self.root,g)
    def test_template_cannot_import_authority(self):
        self.graph['authorization']={'approved':True}
        with self.assertRaises(ValueError):m.template(self.graph)
    def test_symlink_input_rejected(self):
        target=self.root/'retained.md';target.write_text('retained');(self.root/'link.md').symlink_to(target)
        self.graph['children'][0]['reads'].append('link.md')
        with self.assertRaisesRegex(ValueError,'unsafe_artifact_path'):m.validate(self.root,self.graph)


if __name__=='__main__':unittest.main()
