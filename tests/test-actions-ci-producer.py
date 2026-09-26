#!/usr/bin/env python3
"""Run the exact inline evidence producer against synthetic events and disposable Git."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = '.github/workflows/shellcheck.yml'
TEXT = (ROOT / WORKFLOW).read_text()
CODE = '\n'.join(line[10:] for line in TEXT.split('          # NIGHTSHIFT_INTEGRATION_PRODUCER_BEGIN\n', 1)[1].split('          # NIGHTSHIFT_INTEGRATION_PRODUCER_END', 1)[0].splitlines())
FIELDS = set('version repository repository_id head_repository_id run_id run_attempt event pull_request head base merge checkout parents workflow_path workflow_sha workflow_sha256 producer_job ref head_ref base_ref'.split())


class Producer(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-ci-receipt-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / 'repo'; self.root.mkdir()
        self.home = self.base / 'home'; self.home.mkdir()
        self.temp = self.base / 'runner'; self.temp.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), GIT_CONFIG_NOSYSTEM='1', PYTHONDONTWRITEBYTECODE='1')
        self.git('init', '-q'); self.git('config', 'user.name', 'Synthetic'); self.git('config', 'user.email', 'synthetic@example.invalid')
        workflow = self.root / WORKFLOW; workflow.parent.mkdir(parents=True); workflow.write_text(TEXT)
        self.git('add', '.'); self.git('commit', '-qm', 'Synthetic common base'); common = self.git('rev-parse', 'HEAD')
        (self.root / 'head.txt').write_text('synthetic head\n'); self.git('add', '.'); self.git('commit', '-qm', 'Synthetic head'); self.head = self.git('rev-parse', 'HEAD')
        self.git('checkout', '--detach', common)
        (self.root / 'base.txt').write_text('synthetic base\n'); self.git('add', '.'); self.git('commit', '-qm', 'Synthetic base'); self.base_sha = self.git('rev-parse', 'HEAD')
        self.git('merge', '--no-ff', self.head, '-m', 'Synthetic integration merge'); self.merge = self.git('rev-parse', 'HEAD')
        repository = dict(id=10, full_name='synthetic/repository')
        self.event = dict(number=7, repository=repository, pull_request=dict(number=7, merge_commit_sha=self.merge, base=dict(sha=self.base_sha, ref='main', repo=repository), head=dict(sha=self.head, ref='topic', repo=dict(id=20, full_name='synthetic/fork'))))
        self.event_path = self.base / 'event.json'
        self.env.update(GITHUB_EVENT_NAME='pull_request', GITHUB_EVENT_PATH=str(self.event_path), GITHUB_REPOSITORY='synthetic/repository', GITHUB_REPOSITORY_ID='10', GITHUB_SHA=self.merge, GITHUB_REF='refs/pull/7/merge', GITHUB_HEAD_REF='topic', GITHUB_BASE_REF='main', GITHUB_WORKFLOW_SHA=self.merge, GITHUB_WORKFLOW_REF='synthetic/repository/'+WORKFLOW+'@refs/pull/7/merge', GITHUB_JOB='nightshift-integration-evidence', GITHUB_WORKSPACE=str(self.root), GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2', RUNNER_TEMP=str(self.temp))

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, env=self.env, stderr=subprocess.PIPE, text=True).strip()

    def produce(self, raw=None):
        self.event_path.write_text(json.dumps(self.event) if raw is None else raw)
        return subprocess.run(['python3', '-I', '-'], input=CODE, text=True, cwd=self.root, env=self.env, capture_output=True, timeout=20)

    def rejected(self, raw=None):
        result = self.produce(raw)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.temp / 'nightshift-integration/nightshift-integration.json').exists())

    def test_exact_receipt_binds_fork_merge_workflow_and_attempt(self):
        result = self.produce(); self.assertEqual(result.returncode, 0, result.stderr)
        output = self.temp / 'nightshift-integration/nightshift-integration.json'
        receipt = json.loads(output.read_text()); self.assertEqual(set(receipt), FIELDS)
        self.assertEqual(receipt['parents'], [self.base_sha, self.head]); self.assertEqual(receipt['checkout'], self.merge)
        self.assertEqual(receipt['head_repository_id'], 20); self.assertEqual(receipt['run_attempt'], 2)
        self.assertEqual(receipt['workflow_sha256'], hashlib.sha256((self.root / WORKFLOW).read_bytes()).hexdigest())
        self.assertLess(output.stat().st_size, 8192)

    def test_null_event_merge_uses_exact_execution_checkout_and_parents(self):
        self.event['pull_request']['merge_commit_sha'] = None
        result = self.produce()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.temp / 'nightshift-integration/nightshift-integration.json').read_text())
        self.assertEqual(receipt['merge'], self.merge)
        self.assertEqual(receipt['parents'], [self.base_sha, self.head])

    def test_nonnull_invalid_or_mismatched_event_merge_is_rejected(self):
        for value in (self.head, '', False, 7, []):
            with self.subTest(value=value):
                self.event['pull_request']['merge_commit_sha'] = value
                self.rejected()

    def test_absent_event_merge_field_is_rejected(self):
        del self.event['pull_request']['merge_commit_sha']
        self.rejected()

    def test_event_and_environment_identity_mismatches_produce_no_receipt(self):
        changes = dict(GITHUB_EVENT_NAME='pull_request_target', GITHUB_REPOSITORY_ID='11', GITHUB_REPOSITORY='wrong/repository', GITHUB_SHA=self.head, GITHUB_REF='refs/heads/topic', GITHUB_HEAD_REF='other', GITHUB_BASE_REF='other', GITHUB_WORKFLOW_SHA=self.head, GITHUB_WORKFLOW_REF='synthetic/repository/'+WORKFLOW+'@refs/heads/main', GITHUB_JOB='shellcheck', GITHUB_RUN_ID='0', GITHUB_RUN_ATTEMPT='01')
        for key, value in changes.items():
            with self.subTest(key=key):
                old = self.env[key]; self.env[key] = value
                self.rejected(); self.env[key] = old

    def test_actual_checkout_must_match_event(self):
        self.git('checkout', '--detach', self.head); self.rejected()

    def test_actual_ordered_parents_must_match_event(self):
        self.event['pull_request']['head']['sha'] = self.base_sha
        self.event['pull_request']['base']['sha'] = self.head
        self.rejected()

    def test_modified_workflow_is_not_attested(self):
        with (self.root / WORKFLOW).open('a') as stream: stream.write('\n# uncommitted change\n')
        self.rejected()

    def test_symlink_workflow_is_not_attested(self):
        external = self.base / 'external-workflow'; external.write_text(TEXT)
        workflow = self.root / WORKFLOW; workflow.rename(self.base / 'retained-original-workflow'); workflow.symlink_to(external)
        self.rejected()

    def test_boolean_numeric_identity_rejected(self):
        self.event['pull_request']['head']['repo']['id'] = True; self.rejected()

    def test_duplicate_event_key_rejected(self):
        raw = json.dumps(self.event); self.rejected('{"number":7,'+raw[1:])

    def test_oversized_event_rejected(self):
        self.rejected(' ' * 2_000_001)

    def test_existing_receipt_is_never_overwritten(self):
        self.assertEqual(self.produce().returncode, 0)
        output = self.temp / 'nightshift-integration/nightshift-integration.json'; before = output.read_bytes()
        self.env['GITHUB_RUN_ATTEMPT'] = '3'; self.assertNotEqual(self.produce().returncode, 0)
        self.assertEqual(output.read_bytes(), before)

    def test_repository_python_startup_code_is_never_executed(self):
        marker = self.base / 'unexpected-execution'
        (self.root / 'sitecustomize.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("unsafe")\n')
        self.env['PYTHONPATH'] = str(self.root)
        result = self.produce(); self.assertEqual(result.returncode, 0, result.stderr); self.assertFalse(marker.exists())

    def test_producer_job_contains_only_pinned_actions_and_inline_python(self):
        job = TEXT.split('\n  nightshift-integration-evidence:\n', 1)[1]
        self.assertEqual(job.count('uses:'), 2); self.assertEqual(job.count('run: |'), 1)
        self.assertIn('actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', job)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02', job)
        for expected in ("github.event_name == 'pull_request'", 'persist-credentials: false', 'submodules: false', 'python3 -I -', 'overwrite: false', 'retention-days: 30', 'nightshift-integration-${{ github.run_id }}-${{ github.run_attempt }}'):
            self.assertIn(expected, job)
        self.assertNotIn('scripts/', job); self.assertNotIn('tests/', job)
        tested = TEXT.split('\n  nightshift-integration-evidence:\n', 1)[0]
        self.assertIn('actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', tested)
        self.assertIn('ref: ${{ github.sha }}', tested)
        self.assertIn('persist-credentials: false', tested)


if __name__ == '__main__': unittest.main()
