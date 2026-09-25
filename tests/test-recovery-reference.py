#!/usr/bin/env python3
"""Recovery resolves saved ticket identity without source access or state changes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recovery', ROOT/'scripts/nightshift-controller-recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RetainedReferenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.console = recovery.load('console-actions')
        self.directory = self.console.directory(self.project)
        self.directory.mkdir(parents=True)
        self.budget = self.directory.parent/'retained-budget.json'
        self.budget.write_text('{"exhausted":true,"used":600}')

    def save(self, task, ref):
        self.console.save(self.project, task, dict(ref=ref, provider='codex', model='fixture',
                          policy='standard', auth='subscription', branch='auto',
                          base='', push=False, pr=False))

    def snapshot(self):
        return {str(p.relative_to(self.project)): p.read_bytes()
                for p in self.project.rglob('*') if p.is_file()}

    def test_source_agnostic_exact_refs_and_bare_keys_are_readonly(self):
        refs = {'42':'gh:fixture/repo#42', 'local-42':'gh:42', 'T-1':'jira:T-1',
                'board-7':'monday:7', 'draft':'spec:docs/draft.md'}
        for task, ref in refs.items():
            self.save(task, ref)
        before = self.snapshot()
        real_run = subprocess.run
        def local_git_only(argv, *args, **kwargs):
            self.assertEqual(argv[0], 'git', 'reference resolution queried an external provider')
            return real_run(argv, *args, **kwargs)
        with patch.object(subprocess, 'run', local_git_only), patch.object(recovery, 'load', return_value=self.console), patch.object(self.console, 'state', side_effect=AssertionError('state enrichment called')):
            for task, ref in refs.items():
                self.assertEqual(recovery.resolve_retained_ref(self.project, ref), task)
                self.assertEqual(recovery.resolve_retained_ref(self.project, task), task)
        self.assertEqual(before, self.snapshot())

    def test_different_repository_is_not_guessed_from_numeric_suffix(self):
        self.save('42', 'gh:fixture/repo#42')
        before = self.snapshot()
        for ref in ('gh:other/repo#42', 'gh:42', 'missing'):
            with self.assertRaisesRegex(ValueError, 'reference_not_found'):
                recovery.resolve_retained_ref(self.project, ref)
        self.assertEqual(before, self.snapshot())

    def test_duplicate_ref_and_bare_key_collision_fail_closed(self):
        self.save('42', 'gh:fixture/repo#42')
        self.save('another', 'gh:fixture/repo#42')
        self.save('shadow', '42')
        before = self.snapshot()
        for ref in ('gh:fixture/repo#42', '42'):
            with self.assertRaisesRegex(ValueError, 'reference_ambiguous'):
                recovery.resolve_retained_ref(self.project, ref)
        self.assertEqual(before, self.snapshot())

    def test_changed_record_identity_and_invalid_arguments_are_rejected(self):
        self.save('42', 'gh:fixture/repo#42')
        path = self.directory/'42.json'
        record = json.loads(path.read_text()); record['task'] = 'another'
        path.write_text(json.dumps(record))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'identity_changed'):
            recovery.resolve_retained_ref(self.project, 'gh:fixture/repo#42')
        for ref in ('', '42\n', None):
            with self.assertRaisesRegex(ValueError, 'invalid_reference'):
                recovery.resolve_retained_ref(self.project, ref)
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
