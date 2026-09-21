import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('decomposition', Path(__file__).resolve().parents[1] / 'scripts/nightshift-decomposition.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class Plans(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        for name in ('parent','first','final'):
            (self.root / (name + '.md')).write_text(name)
        self.plan = dict(version=1,parent='spec:parent.md',requirements=['AC1','AC2'],children=[
            dict(id='final',ref='spec:final.md',depends_on=['first'],requirements=['AC1','AC2'],integration=True),
            dict(id='first',ref='spec:first.md',depends_on=[],requirements=['AC1'],integration=False)])

    def tearDown(self):
        self.tmp.cleanup()

    def test_order_and_source_hash(self):
        result=m.validate(self.plan,self.root)
        self.assertEqual([c['id'] for c in result['children']],['first','final'])
        self.assertEqual(len(result['parent_sha256']),64)
        (self.root/'first.md').write_text('changed')
        self.assertNotEqual(result['children'][0]['source_sha256'],m.validate(self.plan,self.root)['children'][0]['source_sha256'])

    def test_invalid_graph_and_coverage(self):
        mutations=[lambda p:p['children'][1].update(depends_on=['final']),
                   lambda p:p['children'][0].update(depends_on=['missing']),
                   lambda p:p['requirements'].append('AC3'),
                   lambda p:p['children'][0].update(depends_on=[]),
                   lambda p:p['children'][1].update(integration=True),
                   lambda p:p['children'][1].update(ref='spec:../escape.md')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                plan=copy.deepcopy(self.plan);mutate(plan)
                with self.assertRaises(ValueError):m.validate(plan,self.root)

    def test_symlink_source_rejected(self):
        (self.root/'link.md').symlink_to(self.root/'first.md')
        self.plan['children'][1]['ref']='spec:link.md'
        with self.assertRaises(ValueError):m.validate(self.plan,self.root)


if __name__=='__main__':unittest.main()
