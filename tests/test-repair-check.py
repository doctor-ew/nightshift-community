#!/usr/bin/env python3
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/nightshift-repair-check.py'
spec = importlib.util.spec_from_file_location('repair_check', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RepairCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.folder = self.root / 'docs/task'
        self.folder.mkdir(parents=True)
        self.before = {'cases': {'c06': {'turn2': 'accept that sentence', 'turn3': 'accept that sentence'}}}
        self.write('before.json', self.before)
        self.write('current.json', self.before)
        self.manifest = {'schema_version': 1, 'findings': [self.finding('turn2'), self.finding('turn3')]}

    def write(self, name, value):
        (self.folder / name).write_text(json.dumps(value))

    def finding(self, turn):
        return {'id': 'c06-' + turn, 'artifact': 'docs/task/current.json',
                'prior_artifact': 'docs/task/before.json',
                'prior_sha256': hashlib.sha256((self.folder / 'before.json').read_bytes()).hexdigest(),
                'pointer': '/cases/c06/' + turn, 'expected': 'accept the proposed text'}

    def run_check(self):
        self.write('repair-checks.json', self.manifest)
        return module.check(self.root, 'docs/task/repair-checks.json', 'docs/task/repair-check.receipt.json')

    def fix(self):
        self.write('current.json', {'cases': {'c06': {'turn2': 'accept the proposed text', 'turn3': 'accept the proposed text'}}})

    def test_adjacent_turn_remains_wrong(self):
        self.write('current.json', {'cases': {'c06': {'turn2': 'accept the proposed text', 'turn3': 'accept that sentence'}}})
        receipt = self.run_check()
        self.assertEqual(receipt['status'], 'failed')
        self.assertTrue(receipt['findings'][0]['passed'])
        self.assertFalse(receipt['findings'][1]['passed'])

    def test_all_fixed_hash_bound_not_approval(self):
        self.fix()
        receipt = self.run_check()
        self.assertEqual(receipt['status'], 'passed')
        self.assertFalse(receipt['gate_approval'])
        self.assertEqual(receipt['findings'][0]['artifact_sha256'], hashlib.sha256((self.folder / 'current.json').read_bytes()).hexdigest())
        self.assertEqual(json.loads((self.folder / 'repair-check.receipt.json').read_text()), receipt)

    def test_original_must_fail(self):
        self.fix()
        self.write('before.json', json.loads((self.folder / 'current.json').read_text()))
        self.manifest['findings'] = [self.finding('turn2')]
        self.assertEqual(self.run_check()['status'], 'failed')

    def test_snapshot_tampering(self):
        self.write('before.json', {})
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.run_check()

    def test_missing_current_pointer(self):
        self.write('current.json', {})
        self.assertEqual(self.run_check()['status'], 'failed')

    def test_json_types_do_not_coerce(self):
        self.assertFalse(module.equal(True, 1))
        self.assertFalse(module.equal(1, 1.0))

    def test_paths_are_bounded(self):
        for path in ('../secret', '/tmp/secret'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                module.confined(self.root, path)
        (self.folder / 'link').symlink_to('/tmp')
        with self.assertRaises(ValueError):
            module.confined(self.root, 'docs/task/link/file.json')

    def test_receipt_cannot_overwrite_inputs(self):
        self.write('repair-checks.json', self.manifest)
        with self.assertRaises(ValueError):
            module.check(self.root, 'docs/task/repair-checks.json', 'docs/task/current.json')

    def test_duplicate_ids_and_extra_fields(self):
        self.manifest['findings'].append(self.finding('turn2'))
        with self.assertRaises(ValueError):
            self.run_check()
        self.manifest['findings'] = [self.finding('turn2')]
        self.manifest['findings'][0]['command'] = 'echo nope'
        with self.assertRaises(ValueError):
            self.run_check()

    def test_pointer_escape_and_array(self):
        self.assertEqual(module.pointer_value({'a/b': [{'~x': 3}]}, '/a~1b/0/~0x'), (True, 3))
        with self.assertRaises(ValueError):
            module.pointer_value({}, '/x~3')

    def apply(self):
        self.write('repair-checks.json', self.manifest)
        return module.apply(self.root, 'docs/task/repair-checks.json', 'docs/task/repair-check.receipt.json')

    def test_apply_multiple_fields_and_idempotent(self):
        receipt = self.apply()
        self.assertEqual(receipt['status'], 'passed')
        self.assertFalse(receipt['gate_approval'])
        after = (self.folder / 'current.json').read_bytes()
        self.assertEqual(self.apply()['status'], 'passed')
        self.assertEqual(after, (self.folder / 'current.json').read_bytes())
        self.assertEqual(json.loads((self.folder / 'before.json').read_text()), self.before)

    def test_apply_preserves_key_order(self):
        doc = {'z': 1, 'cases': self.before['cases'], 'a': 2}
        self.write('before.json', doc)
        self.write('current.json', doc)
        self.manifest['findings'] = [self.finding('turn2'), self.finding('turn3')]
        self.apply()
        self.assertEqual(list(json.loads((self.folder / 'current.json').read_text())), ['z', 'cases', 'a'])

    def test_apply_refuses_later_edit(self):
        self.write('current.json', {'cases': {'c06': {'turn2': 'later work', 'turn3': 'accept that sentence'}}})
        before = (self.folder / 'current.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'refusing overwrite'):
            self.apply()
        self.assertEqual(before, (self.folder / 'current.json').read_bytes())

    def test_apply_requires_existing_pointer_without_partial_write(self):
        self.manifest['findings'][1]['pointer'] = '/missing'
        before = (self.folder / 'current.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'existing JSON pointers'):
            self.apply()
        self.assertEqual(before, (self.folder / 'current.json').read_bytes())

    def test_apply_validates_all_before_mutation(self):
        self.manifest['findings'][1]['prior_sha256'] = '0' * 64
        before = (self.folder / 'current.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.apply()
        self.assertEqual(before, (self.folder / 'current.json').read_bytes())

    def test_apply_rejects_multiple_artifacts(self):
        self.write('second.json', self.before)
        self.manifest['findings'][1]['artifact'] = 'docs/task/second.json'
        before = (self.folder / 'current.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'exactly one artifact'):
            self.apply()
        self.assertEqual(before, (self.folder / 'current.json').read_bytes())

    def test_apply_rejects_overlapping_pointers(self):
        self.manifest['findings'][1]['pointer'] = '/cases/c06'
        self.manifest['findings'][1]['expected'] = {}
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            self.apply()

    def test_apply_cli_success(self):
        self.write('repair-checks.json', self.manifest)
        result = subprocess.run([sys.executable, str(SCRIPT), 'apply', '--project', str(self.root), '--manifest', 'docs/task/repair-checks.json', '--out', 'docs/task/repair-check.receipt.json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'passed')

    def test_cli_failure_exit(self):
        self.write('repair-checks.json', self.manifest)
        result = subprocess.run([sys.executable, str(SCRIPT), 'check', '--project', str(self.root), '--manifest', 'docs/task/repair-checks.json', '--out', 'docs/task/repair-check.receipt.json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
