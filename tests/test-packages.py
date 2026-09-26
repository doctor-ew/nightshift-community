#!/usr/bin/env python3
"""Public package-contract fixtures; no providers or controller writes."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixtures',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
spec=importlib.util.spec_from_file_location('packages',ROOT/'scripts/nightshift-packages.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def fixture(root):
    plan=f.fixture(root)
    (root/'parent.md').write_text('Return two across the public interface.\n')
    (root/'final.md').write_text('Verify the combined answer interface.\n')
    (root/'docs/final').mkdir()
    (root/'docs/prepare').mkdir()
    preparation=copy.deepcopy(plan);preparation['inputs']['spec']='graph.json'
    (root/'docs/prepare/operations.json').write_text(json.dumps(preparation))
    final=copy.deepcopy(plan);final['inputs']['spec']='final.md'
    (root/'docs/final/operations.json').write_text(json.dumps(final))
    def package(key,task,p,integration=False):
        return dict(id=key,task=task,template='integration' if integration else 'implementation',
                    reads=sorted(set(p['inputs'].values())|{'test_app.py','app.py'}),
                    writes=[] if integration else ['app.py'],requires=['answer-v1'] if integration else [],provides=[] if integration else ['answer-v1'])
    graph=dict(version=1,preparation_task='prepare',aggregate=dict(calls=60,seconds=600,wall_seconds=180),
        decomposition=dict(version=1,parent='spec:parent.md',requirements=['answer'],children=[
            dict(id='writer',ref='spec:spec.md',depends_on=[],requirements=['answer'],integration=False),
            dict(id='integrate',ref='spec:final.md',depends_on=['writer'],requirements=['answer'],integration=True)]),
        templates=[dict(id='implementation',version=1,operations=f.m.RECIPES['factory']),dict(id='integration',version=1,operations=m.INTEGRATION)],
        packages=[package('writer','demo',plan),package('integrate','final',final,True)])
    (root/'graph.json').write_text(json.dumps(graph))
    return graph


class Packages(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nightshift-packages-')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.graph=fixture(self.root)
    def test_versioned_plan_reuses_decomposition_and_stays_read_only(self):
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=m.validate(self.graph,self.root)
        self.assertEqual(result['status'],'valid');self.assertFalse(result['semantic_approval']);self.assertFalse(result['authorized'])
        self.assertEqual([p['package']['id'] for p in result['packages']],['writer','integrate'])
        self.assertEqual(result['allocations'],dict(calls=60,seconds=540))
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_rejects_cycles_missing_coverage_and_unknown_dependencies(self):
        for field,value in [('cycle',None),('coverage',None),('dependency',None)]:
            graph=copy.deepcopy(self.graph)
            if field=='cycle':graph['decomposition']['children'][0]['depends_on']=['integrate']
            elif field=='coverage':graph['decomposition']['requirements'].append('uncovered')
            else:graph['decomposition']['children'][0]['depends_on']=['missing']
            with self.subTest(field=field),self.assertRaises(ValueError):m.validate(graph,self.root)
    def test_rejects_overlapping_writes_and_missing_interface(self):
        self.graph['packages'][1]['writes']=['app.py']
        with self.assertRaisesRegex(ValueError,'conflicting_package_writes'):m.validate(self.graph,self.root)
        self.graph['packages'][1]['writes']=[];self.graph['packages'][1]['requires']=['absent']
        with self.assertRaisesRegex(ValueError,'missing_interface_dependency'):m.validate(self.graph,self.root)
    def test_parent_allocations_are_static_and_bounded(self):
        self.graph['aggregate']['calls']=39
        with self.assertRaisesRegex(ValueError,'child_allocations_exceed_parent'):m.validate(self.graph,self.root)
        self.graph['aggregate']['calls']=60;self.graph['aggregate']['wall_seconds']=10
        with self.assertRaisesRegex(ValueError,'deadline_exceeds_parent'):m.validate(self.graph,self.root)
    def test_templates_cannot_add_publication_or_recursive_recipe(self):
        for recipe in [f.m.RECIPES['factory']+['publish'],['factory'],['adopt','verify']]:
            self.graph['templates'][0]['operations']=recipe
            with self.assertRaisesRegex(ValueError,'unsupported_package_recipe'):m.validate(self.graph,self.root)
    def test_input_and_plan_hashes_change_with_real_dependencies(self):
        first=m.validate(self.graph,self.root)
        (self.root/'rules.md').write_text('changed coding rule\n')
        second=m.validate(self.graph,self.root)
        self.assertNotEqual(first['packages'][0]['input_sha256'],second['packages'][0]['input_sha256'])
        self.assertNotEqual(first['binding'],second['binding'])
        self.graph['packages'][0]['reads'].remove('rules.md')
        with self.assertRaisesRegex(ValueError,'package_inputs_not_declared'):m.validate(self.graph,self.root)
    def test_schema_is_exact_and_template_version_supported(self):
        self.graph['surprise']=True
        with self.assertRaisesRegex(ValueError,'invalid_shape'):m.validate(self.graph,self.root)
        self.graph.pop('surprise');self.graph['templates'][0]['version']=2
        with self.assertRaisesRegex(ValueError,'invalid_package_template'):m.validate(self.graph,self.root)

if __name__=='__main__':unittest.main()
