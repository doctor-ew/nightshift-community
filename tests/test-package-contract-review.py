#!/usr/bin/env python3
"""Independent public-only adversarial package-contract fixtures."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('package_fixtures', Path(__file__).with_name('test-packages.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m


class ContractReview(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='nightshift-package-review-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.graph = f.fixture(self.root)
        preparation = self.root / 'docs/prepare/operations.json'
        if not preparation.exists():
            preparation.parent.mkdir(parents=True, exist_ok=True)
            plan = json.loads((self.root / 'docs/demo/operations.json').read_text())
            plan['inputs']['spec'] = 'parent.md'
            preparation.write_text(json.dumps(plan))

    def validate_graph(self, graph=None):
        graph = self.graph if graph is None else graph
        path = self.root / 'docs/prepare/operations.json'
        if path.exists():
            preparation = json.loads(path.read_text())
            (self.root / preparation['inputs']['spec']).write_text(json.dumps(graph))
        return m.validate(graph, self.root)

    def change_plan(self, task, update):
        path = self.root / 'docs' / task / 'operations.json'
        plan = json.loads(path.read_text())
        update(plan)
        path.write_text(json.dumps(plan))

    def test_missing_unproduced_input_rejected(self):
        self.graph['packages'][0]['reads'].append('missing-input.txt')
        with self.assertRaises(ValueError):
            self.validate_graph()

    def test_missing_check_script_rejected(self):
        self.change_plan('demo', lambda p: p['checks'][0].update(argv=['python3', 'missing-check.py']))
        self.graph['packages'][0]['reads'].append('missing-check.py')
        with self.assertRaises(ValueError):
            self.validate_graph()

    def test_aliased_control_overwrite_rejected(self):
        self.change_plan('demo', lambda p: p.update(scope=['./rules.md']))
        self.graph['packages'][0]['writes'] = ['./rules.md']
        with self.assertRaises(ValueError):
            self.validate_graph()

    def test_parent_source_is_protected(self):
        self.change_plan('demo', lambda p: p.update(scope=['parent.md']))
        self.graph['packages'][0]['writes'] = ['parent.md']
        with self.assertRaises(ValueError):
            self.validate_graph()

    def test_preparation_control_plan_is_protected(self):
        target = 'docs/prepare/operations.json'
        self.change_plan('demo', lambda p: p.update(scope=[target]))
        self.graph['packages'][0]['writes'] = [target]
        with self.assertRaises(ValueError):
            self.validate_graph()

    def test_preparation_plan_required(self):
        path = self.root / 'docs/prepare/operations.json'
        path.rename(path.with_suffix('.retained'))
        with self.assertRaises((ValueError, OSError)):
            self.validate_graph()

    def test_preparation_allocation_and_plan_are_bound(self):
        first = self.validate_graph()
        parent_calls = self.graph['aggregate']['calls']
        self.change_plan('prepare', lambda p: p['aggregate'].update(calls=parent_calls))
        with self.assertRaises(ValueError):
            self.validate_graph()
        self.change_plan('prepare', lambda p: p['aggregate'].update(calls=1))
        second = self.validate_graph()
        self.assertNotEqual(first['binding'], second['binding'])

    def test_implementation_scope_baseline_cannot_escape_binding(self):
        # Omit the existing write target everywhere; a validator must either
        # reject the undeclared read or bind that target separately.
        for package in self.graph['packages']:
            package['reads'] = [p for p in package['reads'] if p != 'app.py']
        try:
            first = self.validate_graph()
        except ValueError:
            return
        (self.root / 'app.py').write_text('def answer(): return 999\n')
        second = self.validate_graph()
        self.assertNotEqual(first['binding'], second['binding'])

    def test_preparation_spec_must_match_validated_manifest(self):
        preparation = json.loads((self.root / 'docs/prepare/operations.json').read_text())
        reviewed = copy.deepcopy(self.graph)
        reviewed['aggregate']['calls'] = 61
        (self.root / preparation['inputs']['spec']).write_text(json.dumps(reviewed))
        with self.assertRaises(ValueError):
            m.validate(self.graph, self.root)

    def test_output_file_and_nested_file_are_conflicting_writes(self):
        self.change_plan('demo', lambda p: p.update(scope=['new', 'new/file.py']))
        self.graph['packages'][0]['writes'] = ['new', 'new/file.py']
        self.graph['packages'][0]['reads'].extend(['new', 'new/file.py'])
        preparation = json.loads((self.root / 'docs/prepare/operations.json').read_text())
        (self.root / preparation['inputs']['spec']).write_text(json.dumps(self.graph))
        with self.assertRaises(ValueError):
            self.validate_graph()

    def test_declared_input_change_invalidates_binding(self):
        first = self.validate_graph()
        (self.root / 'rules.md').write_text('Different public coding rule.\n')
        second = self.validate_graph()
        self.assertNotEqual(first['binding'], second['binding'])

    def test_unsafe_and_symlink_paths_are_rejected(self):
        (self.root / 'rules-link.md').symlink_to(self.root / 'rules.md')
        for name in ('../outside', '/tmp/absolute', '.git/config', '.nightshift/state.json', 'rules-link.md'):
            graph = copy.deepcopy(self.graph)
            graph['packages'][0]['reads'].append(name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.validate_graph(graph)

    def test_undeclared_sibling_output_dependency_rejected(self):
        plan = json.loads((self.root / 'docs/demo/operations.json').read_text())
        plan['inputs']['spec'] = 'sibling.md'
        plan['scope'] = ['sibling.py']
        plan['aggregate']['calls'] = 1
        plan['aggregate']['seconds'] = 1
        (self.root / 'docs/sibling').mkdir()
        (self.root / 'docs/sibling/operations.json').write_text(json.dumps(plan))
        (self.root / 'sibling.md').write_text('Independent public package.\n')
        (self.root / 'sibling.py').write_text('VALUE = 1\n')
        self.graph['packages'].append(dict(id='sibling', task='sibling', template='implementation',
            reads=sorted(set(plan['inputs'].values()) | {'test_app.py', 'sibling.py'}),
            writes=['sibling.py'], requires=[], provides=[]))
        self.graph['decomposition']['children'].insert(1, dict(id='sibling', ref='spec:sibling.md',
            depends_on=[], requirements=['answer'], integration=False))
        self.graph['decomposition']['children'][-1]['depends_on'].append('sibling')
        self.graph['packages'][0]['reads'].append('sibling.py')
        with self.assertRaisesRegex(ValueError, 'undeclared_source_dependency'):
            self.validate_graph()


if __name__ == '__main__':
    unittest.main()
