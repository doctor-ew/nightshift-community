#!/usr/bin/env python3
"""Independent synthetic security and accounting checks for package composition."""
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('hardening_fixtures', Path(__file__).with_name('test-package-controller.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m


class HardeningReview(unittest.TestCase):
    setUp = f.Controller.setUp
    prepare = f.Controller.prepare

    def interrupted_seed(self):
        grant = self.prepare()['id']
        original = m.subprocess.run

        def stop(argv, *args, **kwargs):
            if argv[:3] == ['git', 'init', '-q']:
                raise OSError('synthetic initialization interruption')
            return original(argv, *args, **kwargs)

        with patch.object(m.subprocess, 'run', side_effect=stop):
            result = self.c.run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(len(self.worker.calls), 2)
        return grant, Path(self.c.state['children']['left']['workspace'])

    def test_unexpected_retained_seed_is_preserved_and_not_authorized(self):
        grant, target = self.interrupted_seed()
        extra = target / 'operator-extra.py'
        extra.write_text('PRIVATE_OPERATOR_WORK = True\n')
        result = m.Packages(self.root, 'demo', self.worker).run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('unapproved_materialization_input', result['reason'])
        self.assertEqual(extra.read_text(), 'PRIVATE_OPERATOR_WORK = True\n')
        self.assertEqual(len(self.worker.calls), 2)

    def test_git_file_redirect_cannot_mutate_parent_repository(self):
        grant, target = self.interrupted_seed()
        (target / '.git').write_text('gitdir: ' + str(self.root / '.git') + '\n')
        head = subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD'])
        index = (self.root / '.git/index').read_bytes()
        config = (self.root / '.git/config').read_bytes()
        result = m.Packages(self.root, 'demo', self.worker).run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('unsafe_package_git', result['reason'])
        self.assertEqual(subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD']), head)
        self.assertEqual((self.root / '.git/index').read_bytes(), index)
        self.assertEqual((self.root / '.git/config').read_bytes(), config)
        self.assertEqual(len(self.worker.calls), 2)

    def test_git_worktree_configuration_redirect_is_rejected(self):
        grant, target = self.interrupted_seed()
        subprocess.run(['git', 'init', '-q', str(target)], check=True)
        subprocess.run(['git', '-C', str(target), 'config', 'core.worktree', str(self.root)], check=True)
        index = (self.root / '.git/index').read_bytes()
        result = m.Packages(self.root, 'demo', self.worker).run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('redirected_package_git', result['reason'])
        self.assertEqual((self.root / '.git/index').read_bytes(), index)
        self.assertEqual(len(self.worker.calls), 2)

    def test_mode_is_copied_and_parent_mode_change_invalidates_authority(self):
        path = self.root / 'left.py'
        path.chmod(0o755)
        grant = self.prepare()['id']
        definition = self.c.state['authorizations'][grant]['graph']['children'][0]
        with self.c.lease():
            child = self.c.materialize(definition, grant)
        self.assertEqual(stat.S_IMODE((child.project / 'left.py').stat().st_mode), 0o755)
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'package_authorized_inputs_changed'):
            self.c.run(grant)
        self.assertEqual(len(self.worker.calls), 2)

    def test_operator_seed_mode_change_is_never_overwritten(self):
        grant, target = self.interrupted_seed()
        path = target / 'rules.md'
        mode = stat.S_IMODE(path.stat().st_mode) ^ 0o100
        path.chmod(mode)
        result = m.Packages(self.root, 'demo', self.worker).run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('materialization_content_changed', result['reason'])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
        self.assertEqual(len(self.worker.calls), 2)

    def test_child_cases_must_cover_declared_parent_requirement(self):
        path = self.root / 'docs/integration/operations.json'
        plan = json.loads(path.read_text())
        plan['inputs']['scenarios'] = 'unrelated-cases.json'
        path.write_text(json.dumps(plan))
        (self.root / 'unrelated-cases.json').write_text(json.dumps(dict(version=1, cases=[
            dict(id='unrelated', requirement='Different requirement', manual=False)])))
        self.graph['children'][-1]['reads'].append('unrelated-cases.json')
        (self.root / 'graph.json').write_text(json.dumps(self.graph))
        with self.assertRaisesRegex(ValueError, 'package_requirement_cases_missing'):
            m.contracts.validate(self.root, self.graph, 'graph.json')
        self.assertEqual(self.worker.calls, [])

    def test_later_unknown_preparation_remains_charged_after_parent_authorization(self):
        grant = self.prepare()['id']
        preparation = self.c.preparation
        with preparation.lease():
            preparation.reserve('prepare', 'groom-spec', 'unknown-after-authorization', 17, seconds=1)
        result = m.Packages(self.root, 'demo', self.worker).run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['usage']['unknown_calls'], 1)
        self.assertEqual(result['usage']['calls'], 3)
        self.assertEqual(len(self.worker.calls), 2)
        self.assertFalse(self.c.state['children'])

    def test_later_finished_preparation_cannot_spend_reserved_child_allowance(self):
        grant = self.prepare()['id']
        preparation = self.c.preparation
        # Model completed independent preparation calls already retained in the
        # shared operations ledger; no real provider or extra worker is invoked.
        with preparation.lease():
            sample = next(iter(preparation.state['calls'].values()))
            for index in range(27):
                key = 'completed-preparation-' + str(index)
                preparation.state['calls'][key] = dict(sample, id=key, seconds=0)
            preparation.save()
        result = m.Packages(self.root, 'demo', self.worker).run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertLessEqual(result['usage']['calls'], result['grant']['graph']['aggregate']['calls'])
        self.assertEqual(len(self.worker.calls), 2)
        self.assertFalse(m.Packages(self.root, 'demo', self.worker).state['children'])

    def test_later_finished_preparation_cannot_spend_reserved_child_seconds(self):
        grant = self.prepare()['id']
        preparation = self.c.preparation
        with preparation.lease():
            sample = next(iter(preparation.state['calls'].values()))
            preparation.state['calls']['completed-seconds'] = dict(
                sample, id='completed-seconds', seconds=200, reserved_seconds=200)
            preparation.save()
        result = m.Packages(self.root, 'demo', self.worker).run(grant)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(len(self.worker.calls), 2)
        self.assertFalse(m.Packages(self.root, 'demo', self.worker).state['children'])

    def test_graph_holds_parent_operation_lease_during_child_dispatch(self):
        grant = self.prepare()['id']
        other = m.ops.Operations(self.root, 'demo', self.worker)
        attempted = []
        original = self.worker

        def worker(operation, *args):
            if not attempted:
                attempted.append(operation)
                with self.assertRaisesRegex(ValueError, 'operation_busy'):
                    other.execute('prepare', 'groom-spec', 'concurrent-preparation')
            return original(operation, *args)

        self.c.worker = worker
        result = self.c.run(grant)
        self.assertEqual(result['status'], 'pending_manual_acceptance', result)
        self.assertTrue(attempted)
        other.reload()
        self.assertEqual(len(other.state['calls']), 2)
        self.assertFalse(any(a['request'] == 'concurrent-preparation' for a in other.state['attempts']))
        with other.lease():
            self.assertEqual(len(other.state['calls']), 2)

    def test_retained_authorizations_are_bounded_before_ledger_overwrite(self):
        grant = self.prepare()['id']
        binding = self.c.state['authorizations'][grant]['binding']
        rejected = False
        for index in range(400):
            retained = self.c.path.read_bytes()
            try:
                self.c.authorize(binding, str(index) + ('x' * 3900), 'retained-' + str(index))
            except ValueError as error:
                self.assertIn('package_state_limit', str(error))
                self.assertEqual(self.c.path.read_bytes(), retained)
                rejected = True
                break
        self.assertTrue(rejected)
        self.assertLess(self.c.path.stat().st_size, 2000000)
        resumed = m.Packages(self.root, 'demo', self.worker)
        self.assertIn(grant, resumed.state['authorizations'])
        self.assertEqual(len(self.worker.calls), 2)


if __name__ == '__main__':
    unittest.main()
