#!/usr/bin/env python3
"""Independent model-free intake authority and preservation regressions."""
import copy
import importlib.util
import http.client
import threading
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

f = load('intake_review_fixture', 'tests/test-operations.py')
m = load('intake_review_controller', 'scripts/nightshift-intake.py')


class IntakeReview(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-intake-review-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        f.fixture(self.root)
        self.task = 'intake-review'
        self.source = dict(source='spec', source_id=self.task, external_ref='spec:request.md',
            title='Synthetic request', body='Return two.\n', labels=[], url='', state='open',
            source_path='request.md', source_revision=m.ops.sha(self.root/'request.md'))
        self.choices = dict(scope=['app.py'], checks=[dict(id='unit', argv=['python3', 'test_app.py'])],
            requirements=[dict(id='two', requirement='Return two.', manual=False)],
            rules='rules.md', architecture='architecture.md', allowance=dict(calls=8, seconds=60, wall_seconds=60))
        self.c = m.Intake(self.root, self.task)
        for name, replacement in (
            ('resolve', lambda *_: (copy.deepcopy(self.source), self.task)),
            ('runtime', lambda: dict(serving_revision='synthetic-revision', provider_calls=0)),
            ('readiness', lambda *_: dict(admission=dict(status='ok'), provider_calls=0))):
            context = patch.object(m, name, replacement)
            context.start(); self.addCleanup(context.stop)

    def preview(self, choices=None):
        return self.c.preview('spec:request.md', copy.deepcopy(self.source), self.choices if choices is None else choices)

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*')
                if p.is_file() and '.git' not in p.parts}

    def test_preview_and_cancel_preserve_project_without_operation_grant(self):
        before = self.files()
        row = self.preview()
        self.assertEqual(row['status'], 'preview')
        self.assertEqual(self.files(), before)
        result = self.c.apply(row['binding'], 'synthetic', 'cancel-preview', cancel=True)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(self.files(), before)
        self.assertFalse(m.ops.Operations(self.root, self.task).state['authorizations'])
        with self.assertRaisesRegex(ValueError, 'intake_cancelled'):
            self.c.apply(row['binding'], 'synthetic', 'apply-cancelled')

    def test_changed_source_and_changed_input_block_before_file_creation(self):
        row = self.preview()
        before = self.files()
        self.source['body'] += 'Changed after preview.\n'
        with self.assertRaisesRegex(ValueError, 'intake_preview_stale'):
            self.c.apply(row['binding'], 'synthetic', 'changed-source')
        self.assertEqual(self.files(), before)
        self.source['body'] = 'Return two.\n'
        (self.root/'test_app.py').write_text('# retained operator change\n')
        changed = self.files()
        with self.assertRaisesRegex(ValueError, 'intake_input_changed'):
            self.c.apply(row['binding'], 'synthetic', 'changed-test')
        self.assertEqual(self.files(), changed)
        self.assertFalse((self.root/'docs'/self.task).exists())

    def test_missing_choices_persist_nonexecuting_decision(self):
        before = self.files()
        row = self.preview({})
        self.assertEqual(row['status'], 'needs_decision')
        self.assertTrue(row['missing'])
        self.assertIsNone(row['plan'])
        self.assertEqual(row['files'], {})
        decision = row['decision']
        self.assertEqual(decision['continuation_operation'], 'none')
        with self.assertRaisesRegex(ValueError, 'intake_decisions_required'):
            self.c.apply(row['binding'], 'synthetic', 'unresolved')
        self.assertEqual(self.files(), before)
        self.assertFalse(m.ops.Operations(self.root, self.task).state['authorizations'])

    def test_existing_conflicting_artifact_is_preserved(self):
        path = self.root/'docs'/self.task/'SPEC.md'
        path.parent.mkdir(parents=True)
        path.write_text('Operator draft must survive.\n')
        row = self.preview()
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'intake_preserves_existing_file'):
            self.c.apply(row['binding'], 'synthetic', 'conflicting-file')
        self.assertEqual(self.files(), before)

    def test_same_request_replays_receipt_without_grant_or_worker(self):
        row = self.preview()
        first = self.c.apply(row['binding'], 'synthetic', 'submit-once')
        before = self.files()
        resumed = m.Intake(self.root, self.task)
        second = resumed.apply(row['binding'], 'synthetic', 'submit-once')
        self.assertEqual(first, second)
        self.assertEqual(self.files(), before)
        self.assertFalse(m.ops.Operations(self.root, self.task).state['authorizations'])
        self.assertEqual(first['provider_calls'], 0)

    def test_distinct_duplicate_request_reuses_prepared_receipt(self):
        row = self.preview()
        first = self.c.apply(row['binding'], 'synthetic', 'first-submit')
        self.assertEqual(first, self.c.apply(row['binding'], 'synthetic', 'duplicate-submit'))
        with self.assertRaisesRegex(ValueError, 'intake_already_prepared'):
            self.c.apply(row['binding'], 'synthetic', 'cancel-after-prepare', cancel=True)
        (self.root/next(iter(row['files']))).write_text('Operator edit must survive.\n')
        with self.assertRaisesRegex(ValueError, 'prepared_intake_changed'):
            self.c.apply(row['binding'], 'synthetic', 'first-submit')

    def test_answer_prepares_only_and_replays_without_worker(self):
        row = self.preview({})
        before = self.files()
        body = dict(action='intake-answer', task=self.task, binding=row['binding'], choices=self.choices)
        result = m.api(self.root, body)
        self.assertEqual(result['status'], 'preview')
        self.assertEqual(result, m.api(self.root, body))
        self.assertEqual(self.files(), before)
        self.assertFalse(m.ops.Operations(self.root, self.task).state['authorizations'])

    def test_bootstrap_without_existing_plan_retains_csrf_boundary(self):
        server_module = load('intake_review_server', 'dashboard/server.py')
        server = server_module.DashboardServer(str(self.root), 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def request(method, path, token=None, origin=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            headers = {'Content-Type': 'application/json'}
            if origin is not None: headers['Origin'] = origin
            if token is not None: headers['X-Nightshift-Token'] = token
            body = json.dumps(dict(action='intake-bootstrap')) if method == 'POST' else None
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            status, raw = response.status, response.read()
            connection.close()
            return status, raw
        self.assertFalse((self.root/'docs'/self.task/'operations.json').exists())
        status, raw = request('GET', '/api/intake')
        self.assertEqual(status, 200)
        bootstrap = json.loads(raw)
        self.assertEqual(bootstrap['view']['provider_calls'], 0)
        origin = 'http://127.0.0.1:' + str(server.server_port)
        self.assertEqual(request('POST', '/api/operations', origin=origin)[0], 403)
        self.assertEqual(request('POST', '/api/operations', token=bootstrap['token'], origin='https://example.invalid')[0], 403)
        self.assertEqual(request('GET', '/api/intake', origin='https://example.invalid')[0], 403)
        self.assertEqual(request('POST', '/api/operations', token=bootstrap['token'], origin=origin)[0], 200)
        self.assertFalse((self.root/'docs'/self.task).exists())

    def test_child_role_and_symlink_state_cannot_write_intake(self):
        with patch.dict(os.environ, NIGHTSHIFT_ROLE_CHILD='1'):
            with self.assertRaisesRegex(ValueError, 'worker_cannot_prepare_intake'):
                self.preview()
        self.assertFalse(self.c.directory.exists())
        target = self.root/'untouched-state'
        target.mkdir()
        self.c.directory.parent.mkdir(parents=True, exist_ok=True)
        self.c.directory.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'unsafe_intake_state'):
            self.preview()
        self.assertEqual(list(target.iterdir()), [])

    def test_scope_cannot_own_generated_or_existing_control_artifacts(self):
        for name in ('docs/'+self.task+'/SPEC.md', 'rules.md', 'architecture.md'):
            with self.subTest(path=name):
                choices = copy.deepcopy(self.choices)
                choices['scope'] = [name]
                with self.assertRaises(ValueError):
                    self.preview(choices)
        self.assertFalse((self.root/'docs'/self.task).exists())

    def test_interrupted_complete_file_creation_resumes_same_request(self):
        row = self.preview()
        fsync = m.os.fsync
        def interrupted(fd):
            fsync(fd)
            stat = os.fstat(fd)
            created = [self.root/name for name in row['files']]
            if any(path.exists() and path.stat().st_ino == stat.st_ino for path in created):
                raise KeyboardInterrupt('synthetic crash after first complete created file')
        with patch.object(m.os, 'fsync', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.c.apply(row['binding'], 'synthetic', 'recover-files')
        self.assertTrue(any((self.root/name).exists() for name in row['files']))
        resumed = m.Intake(self.root, self.task)
        result = resumed.apply(row['binding'], 'synthetic', 'recover-files')
        self.assertEqual(result['status'], 'prepared')
        for name, text in row['files'].items():
            self.assertEqual((self.root/name).read_bytes(), text.encode())
        self.assertFalse(m.ops.Operations(self.root, self.task).state['authorizations'])


if __name__ == '__main__':
    unittest.main()
