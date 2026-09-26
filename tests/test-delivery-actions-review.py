#!/usr/bin/env python3
"""Synthetic immutable Actions receipts; never invoke a provider or remote host."""
import base64
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('delivery_actions', ROOT / 'scripts/nightshift-delivery-actions.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
HEAD, BASE, MERGE = 'a' * 40, 'b' * 40, 'c' * 40
REPO = 'synthetic/repository'
WORKFLOW = b'name: synthetic trusted integration\n'
DIGEST = hashlib.sha256(WORKFLOW).hexdigest()


class Host:
    def __init__(self):
        self.calls = []
        self.routes = {}

    def call(self, argv, json_output=False, allowed=(0,), observation=False, bytes_output=False):
        assert argv[:2] == ['gh', 'api'] and observation
        assert json_output != bytes_output
        self.calls.append(argv[2])
        result = self.routes[argv[2].removeprefix('repos/' + REPO + '/')]
        if isinstance(result, Exception):
            raise result
        return copy.deepcopy(result)


class ActionsEvidence(unittest.TestCase):
    def setUp(self):
        self.contract = dict(workflow_path='.github/workflows/ci.yml', workflow_sha256=DIGEST, job='test', producer_job='producer', artifact_prefix='nightshift-integration')
        self.p = dict(repository=REPO, branch='topic', base='main', checks=[dict(name='test', app_id=15368, actions=self.contract)])
        repository = dict(id=101, full_name=REPO)
        self.pr = dict(number=7, head=dict(sha=HEAD, ref='topic', repo=copy.deepcopy(repository)), base=dict(sha=BASE, ref='main', repo=copy.deepcopy(repository)), merge_commit_sha=MERGE)
        self.run = dict(id=202, run_number=9, run_attempt=2, workflow_id=303, event='pull_request', head_sha=HEAD, head_branch='topic', path=self.contract['workflow_path'], check_suite_id=404, repository=copy.deepcopy(repository), head_repository=copy.deepcopy(repository), pull_requests=[dict(base=dict(sha='mutable-ignored'), head=dict(sha='mutable-ignored'))])
        self.check = dict(id=505, name='test', app=dict(id=15368), check_suite=dict(id=404), head_sha=HEAD, status='completed', conclusion='success', output={'summary': 'synthetic check output'})
        self.job = dict(id=606, run_id=202, run_attempt=2, head_sha=HEAD, name='test', check_run_url='https://api.github.com/repos/' + REPO + '/check-runs/505', status='completed', conclusion='success')
        self.producer = dict(id=607, run_id=202, run_attempt=2, head_sha=HEAD, name='producer', check_run_url='https://api.github.com/repos/' + REPO + '/check-runs/506', status='completed', conclusion='success')
        self.artifact = dict(id=808, name='nightshift-integration-202-2', expired=False, workflow_run=dict(id=202, repository_id=101, head_repository_id=101, head_sha=HEAD, head_branch='topic'))
        self.proof = dict(version=1, repository=REPO, repository_id=101, head_repository_id=101, run_id=202, run_attempt=2, event='pull_request', pull_request=7, head=HEAD, base=BASE, merge=MERGE, checkout=MERGE, parents=[BASE, HEAD], workflow_path=self.contract['workflow_path'], workflow_sha=MERGE, workflow_sha256=DIGEST, producer_job='producer', ref='refs/pull/7/merge', head_ref='topic', base_ref='main')
        self.host = Host()
        self.host.routes = {
            'git/commits/' + MERGE: dict(sha=MERGE, parents=[dict(sha=BASE), dict(sha=HEAD)]),
            'actions/runs?event=pull_request&head_sha=' + HEAD + '&per_page=100': dict(total_count=1, workflow_runs=[self.run]),
            'commits/' + HEAD + '/check-runs?filter=all&per_page=100': dict(total_count=1, check_runs=[self.check]),
            'actions/runs/202/attempts/2/jobs?per_page=100': dict(total_count=2, jobs=[self.job, self.producer]),
            'contents/.github/workflows/ci.yml?ref=' + MERGE: dict(path=self.contract['workflow_path'], type='file', encoding='base64', size=len(WORKFLOW), content=base64.b64encode(WORKFLOW).decode()),
            'actions/runs/202/artifacts?per_page=100': dict(total_count=1, artifacts=[self.artifact])}
        self.archive()

    def archive(self, raw=None, names=None, symlink=False):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as output:
            for name in names or ['nightshift-integration.json']:
                entry = zipfile.ZipInfo(name)
                if symlink:
                    entry.create_system = 3
                    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                output.writestr(entry, raw if raw is not None else json.dumps(self.proof).encode())
        value = stream.getvalue()
        self.artifact.update(size_in_bytes=len(value), digest='sha256:' + hashlib.sha256(value).hexdigest())
        self.host.routes['actions/artifacts/808/zip'] = value

    def result(self):
        rows = a.resolve(self.host, self.p, self.pr)
        self.assertEqual(len(rows), 1)
        return rows[0]

    def unknown(self, reason=None):
        result = self.result()
        self.assertIsNone(result['head'])
        self.assertIsNone(result['conclusion'])
        self.assertEqual(result['status'], 'unknown')
        if reason:
            self.assertEqual(result['reason'], reason)
        return result

    def test_valid_receipt_preserves_reported_head_and_verifies_merge(self):
        result = self.result()
        self.assertEqual((result['reported_head'], result['head'], result['conclusion']), (HEAD, MERGE, 'success'))
        self.assertEqual(result['actions']['run_attempt'], 2)
        self.assertEqual(result['actions']['run_number'], 9)

    def test_push_and_pull_request_same_named_check_selects_only_pr(self):
        run = copy.deepcopy(self.run)
        run.update(id=999, event='push', check_suite_id=999, run_number=99)
        checks = self.host.routes['commits/' + HEAD + '/check-runs?filter=all&per_page=100']
        other = copy.deepcopy(self.check)
        other.update(id=999, check_suite={'id': 999}, conclusion='failure')
        checks.update(total_count=2, check_runs=[other, self.check])
        runs = self.host.routes['actions/runs?event=pull_request&head_sha=' + HEAD + '&per_page=100']
        runs.update(total_count=2, workflow_runs=[run, self.run])
        self.assertEqual(self.result()['id'], 505)

    def test_base_change_cannot_relabel_old_receipt_using_mutable_run_pr(self):
        changed = 'd' * 40
        self.pr['base']['sha'] = changed
        self.host.routes['git/commits/' + MERGE]['parents'][0]['sha'] = changed
        self.run['pull_requests'] = [dict(base={'sha': changed}, head={'sha': HEAD})]
        self.unknown('actions_receipt_candidate_mismatch')

    def test_stale_head_run_cannot_supply_receipt(self):
        self.run['head_sha'] = 'd' * 40
        self.unknown('actions_run_missing')

    def test_latest_workflow_run_number_wins_not_larger_run_id(self):
        old = copy.deepcopy(self.run)
        old.update(id=999, run_number=8)
        runs = self.host.routes['actions/runs?event=pull_request&head_sha=' + HEAD + '&per_page=100']
        runs.update(total_count=2, workflow_runs=[old, self.run])
        self.assertEqual(self.result()['actions']['run_id'], 202)

    def test_newer_missing_check_never_falls_back_to_older_pass(self):
        latest = copy.deepcopy(self.run)
        latest.update(id=201, run_number=10, check_suite_id=444)
        runs = self.host.routes['actions/runs?event=pull_request&head_sha=' + HEAD + '&per_page=100']
        runs.update(total_count=2, workflow_runs=[self.run, latest])
        self.unknown('actions_evidence_unavailable')

    def test_ambiguous_run_order_blocks(self):
        other = copy.deepcopy(self.run)
        other['id'] = 203
        runs = self.host.routes['actions/runs?event=pull_request&head_sha=' + HEAD + '&per_page=100']
        runs.update(total_count=2, workflow_runs=[self.run, other])
        self.unknown('actions_run_order_ambiguous')

    def test_retained_old_attempt_check_does_not_hide_latest_attempt(self):
        old = copy.deepcopy(self.check)
        old.update(id=504, conclusion='failure')
        checks = self.host.routes['commits/' + HEAD + '/check-runs?filter=all&per_page=100']
        checks.update(total_count=2, check_runs=[old, self.check])
        self.assertEqual(self.result()['id'], 505)

    def test_duplicate_current_attempt_check_blocks(self):
        checks = self.host.routes['commits/' + HEAD + '/check-runs?filter=all&per_page=100']
        checks.update(total_count=2, check_runs=[copy.deepcopy(self.check), self.check])
        self.unknown('actions_check_missing_or_ambiguous')

    def test_malformed_host_data_stays_unknown(self):
        for owner, key in [(self.check, 'app'), (self.check, 'check_suite'), (self.run, 'repository'), (self.run, 'head_repository')]:
            original = owner[key]
            for value in [None, [], 'malformed']:
                with self.subTest(key=key, value=value):
                    owner[key] = value
                    self.unknown()
            owner[key] = original
        runs = self.host.routes['actions/runs?event=pull_request&head_sha=' + HEAD + '&per_page=100']
        runs['workflow_runs'] = [None]
        self.unknown()

    def test_attempt_swap_in_job_blocks(self):
        self.job['run_attempt'] = 1
        self.unknown('actions_job_identity')

    def test_attempt_swap_in_proof_blocks(self):
        self.proof['run_attempt'] = 1
        self.archive()
        self.unknown('actions_receipt_candidate_mismatch')

    def test_old_attempt_artifact_name_blocks(self):
        self.artifact['name'] = 'nightshift-integration-202-1'
        self.unknown('actions_artifact_missing_or_ambiguous')

    def test_workflow_hash_mismatch_blocks(self):
        self.contract['workflow_sha256'] = '0' * 64
        self.unknown('actions_workflow_digest')

    def test_spoofed_app_blocks(self):
        self.check['app']['id'] = 999
        self.unknown('actions_check_missing_or_ambiguous')

    def test_spoofed_job_check_url_blocks(self):
        self.job['check_run_url'] = 'https://api.github.com/repos/foreign/repo/check-runs/505'
        self.unknown('actions_job_check_identity')

    def test_spoofed_job_head_blocks(self):
        self.job['head_sha'] = MERGE
        self.unknown('actions_job_identity')

    def test_spoofed_run_repository_blocks(self):
        self.run['repository']['id'] = 999
        self.unknown('actions_run_repository')

    def test_spoofed_artifact_repository_blocks(self):
        self.artifact['workflow_run']['head_repository_id'] = 999
        self.unknown('actions_artifact_run_identity')

    def test_spoofed_receipt_fields_each_block(self):
        for key, value in [('event', 'push'), ('repository', 'foreign/repo'), ('checkout', HEAD), ('workflow_sha', HEAD), ('producer_job', 'other'), ('ref', 'refs/heads/topic'), ('head_ref', 'other'), ('base_ref', 'other'), ('run_id', 999), ('pull_request', 8), ('parents', [HEAD, BASE])]:
            with self.subTest(field=key):
                original = self.proof[key]
                self.proof[key] = value
                self.archive()
                self.unknown('actions_receipt_candidate_mismatch')
                self.proof[key] = original

    def test_bool_integer_receipt_is_rejected(self):
        self.proof['version'] = True
        self.archive()
        self.unknown('invalid_actions_receipt_integer')

    def test_duplicate_json_key_rejected(self):
        raw = json.dumps(self.proof).replace('"version": 1', '"version": 1, "version": 1').encode()
        self.archive(raw)
        self.unknown('duplicate_actions_receipt_key')

    def test_unknown_receipt_fields_rejected(self):
        self.proof['extra'] = 'not admitted'
        self.archive()
        self.unknown('invalid_actions_receipt_fields')

    def test_zip_digest_mismatch_blocks(self):
        self.artifact['digest'] = 'sha256:' + '0' * 64
        self.unknown('actions_archive_digest')

    def test_zip_and_receipt_size_bounds(self):
        self.artifact['size_in_bytes'] = a.MAX_ARCHIVE + 1
        self.unknown('actions_archive_size')
        self.assertFalse(any(x.endswith('/zip') for x in self.host.calls))
        self.archive(b' ' * (a.MAX_RECEIPT + 1))
        self.unknown('actions_receipt_size')

    def test_transport_oversize_fails_closed(self):
        self.host.routes['actions/artifacts/808/zip'] = ValueError('delivery_host_output_too_large:private-log')
        self.unknown('actions_evidence_unavailable')

    def test_duplicate_or_expired_artifacts_block(self):
        artifacts = self.host.routes['actions/runs/202/artifacts?per_page=100']
        artifacts.update(total_count=2, artifacts=[self.artifact, copy.deepcopy(self.artifact)])
        self.unknown('actions_artifact_missing_or_ambiguous')
        artifacts.update(total_count=1, artifacts=[self.artifact])
        self.artifact['expired'] = True
        self.unknown('actions_artifact_expired')

    def test_zip_entry_names_duplicates_and_symlinks_block(self):
        for names in [['../nightshift-integration.json'], ['nightshift-integration.json', 'other.json'], ['nightshift-integration.json', 'nightshift-integration.json']]:
            with self.subTest(names=names):
                self.archive(names=names)
                self.unknown()
        self.archive(symlink=True)
        self.unknown('actions_archive_entry_type')

    def test_pending_cancelled_skipped_or_timed_out_check_is_unknown(self):
        for status, conclusion in [('queued', None), ('in_progress', None), ('completed', 'cancelled'), ('completed', 'skipped'), ('completed', 'timed_out'), ('completed', 'action_required')]:
            with self.subTest(status=status, conclusion=conclusion):
                self.check.update(status=status, conclusion=conclusion)
                self.job.update(status=status, conclusion=conclusion)
                self.unknown('actions_check_pending_or_inconclusive')

    def test_substantive_failure_preserves_diagnostics_after_binding(self):
        self.check['conclusion'] = self.job['conclusion'] = 'failure'
        result = self.result()
        self.assertEqual((result['head'], result['conclusion'], result['output']), (MERGE, 'failure', self.check['output']))

    def test_missing_diagnostics_does_not_invent_them(self):
        self.check['conclusion'] = self.job['conclusion'] = 'failure'
        self.check['output'] = {}
        self.assertEqual(self.result()['output'], {})

    def failed_logs(self, raw):
        self.check['conclusion'] = self.job['conclusion'] = 'failure'
        self.check['output'] = {}
        self.job['steps'] = [dict(status='completed', conclusion='failure', started_at='2026-09-26T12:00:01Z', completed_at='2026-09-26T12:00:02Z')]
        self.host.routes['actions/jobs/606/logs'] = raw

    def test_failed_step_diagnostics_use_complete_bounded_records(self):
        self.failed_logs(b'\xef\xbb\xbf2026-09-26T12:00:00.0000000Z outside\n2026-09-26T12:00:01.1234567Z assertion failed\ncontinued diagnostic\n2026-09-26T12:00:02.9000000Z failure end\n2026-09-26T12:00:03.0000000Z outside\n')
        result = self.result()
        self.assertEqual(result['conclusion'], 'failure')
        self.assertNotIn('outside', result['output']['text'])
        self.assertIn('continued diagnostic', result['output']['text'])
        self.assertIn('failure end', result['output']['text'])
        proof = result['actions']['diagnostics']
        self.assertEqual(proof['selected_bytes'], len(result['output']['text'].encode()))
        self.assertEqual(proof['raw_bytes'], len(self.host.routes['actions/jobs/606/logs']))

    def test_multiple_failed_steps_keep_all_selected_segments(self):
        self.failed_logs(b'2026-09-26T12:00:01Z first\n2026-09-26T12:00:03Z outside\n2026-09-26T12:00:04Z second\n')
        self.job['steps'].append(dict(status='completed', conclusion='failure', started_at='2026-09-26T12:00:04Z', completed_at='2026-09-26T12:00:05Z'))
        result = self.result()
        self.assertIn('first', result['output']['text'])
        self.assertIn('second', result['output']['text'])
        self.assertNotIn('outside', result['output']['text'])
        self.assertEqual(result['actions']['diagnostics']['failed_steps'], 2)

    def test_missing_or_malformed_diagnostics_cannot_erase_ci_failure(self):
        for raw in [b'not timestamped\n', b'2026-99-26T12:00:01Z bad date\n', b'2026-09-26T12:00:02Z later\n2026-09-26T12:00:01Z earlier\n', b'2026-09-26T12:00:01Z ' + b'x' * (a.MAX_DIAGNOSTIC + 1), b'x' * (a.MAX_ARCHIVE + 1), ValueError('delivery_host_output_too_large:private-log')]:
            with self.subTest(kind=type(raw).__name__):
                self.failed_logs(raw)
                result = self.result()
                self.assertEqual((result['head'], result['conclusion'], result['output']), (MERGE, 'failure', {}))
                self.assertIn('diagnostic_reason', result['actions'])

    def test_absent_or_invalid_failed_step_times_block_only_diagnostics(self):
        self.failed_logs(b'2026-09-26T12:00:01Z failure\n')
        for steps in [None, [], [dict(status='completed', conclusion='failure')], [dict(status='completed', conclusion='failure', started_at='2026-09-26T12:00:02Z', completed_at='2026-09-26T12:00:01Z')]]:
            self.job['steps'] = steps
            result = self.result()
            self.assertEqual((result['head'], result['conclusion'], result['output']), (MERGE, 'failure', {}))
            self.assertIn('diagnostic_reason', result['actions'])

    def test_success_does_not_fetch_logs(self):
        self.check['output'] = {}
        self.assertEqual(self.result()['conclusion'], 'success')
        self.assertFalse(any('/logs' in path for path in self.host.calls))

    def test_failed_or_queued_producer_blocks(self):
        for status, conclusion in [('queued', None), ('completed', 'failure')]:
            self.producer.update(status=status, conclusion=conclusion)
            self.unknown('actions_producer_incomplete')

    def test_incomplete_pagination_blocks(self):
        for path, value in list(self.host.routes.items()):
            if isinstance(value, dict) and 'total_count' in value:
                with self.subTest(path=path):
                    value['total_count'] += 1
                    self.unknown('actions_pagination_incomplete')
                    value['total_count'] -= 1

    def test_actual_merge_parents_must_have_order_and_cardinality(self):
        for parents in [[HEAD, BASE], [BASE, HEAD, 'd' * 40], [HEAD, HEAD]]:
            self.host.routes['git/commits/' + MERGE]['parents'] = [dict(sha=x) for x in parents]
            self.unknown('actions_merge_parents')

    def test_reported_head_is_not_rewritten_on_failure(self):
        self.check['head_sha'] = 'd' * 40
        self.assertEqual(self.unknown()['reported_head'], 'd' * 40)

    def test_strict_checks_are_not_resolved(self):
        del self.p['checks'][0]['actions']
        self.assertEqual(a.resolve(self.host, self.p, self.pr), [])
        self.assertEqual(self.host.calls, [])

    def test_contract_rejects_extra_keys_traversal_hash_and_control_bytes(self):
        for key, value in [('workflow_path', '../ci.yml'), ('workflow_sha256', 'x' * 64), ('job', 'bad\njob'), ('producer_job', ''), ('artifact_prefix', '../receipt'), ('unexpected', True)]:
            contract = dict(self.contract)
            contract[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                a.validate_contract(contract)


if __name__ == '__main__':
    unittest.main()
