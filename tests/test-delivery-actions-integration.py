#!/usr/bin/env python3
"""Actions proof admission through the shared delivery controller; synthetic only."""
import copy
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

f = load('actions_delivery_fixture', ROOT / 'tests/test-delivery-review.py')
a = load('actions_api_fixture', ROOT / 'tests/test-delivery-actions-review.py')
d = f.d


class HostFlow(unittest.TestCase):
    def setUp(self):
        self.fixture = a.ActionsEvidence('test_valid_receipt_preserves_reported_head_and_verifies_merge')
        self.fixture.setUp()
        self.fixture.pr.update(state='open', merged=False)
        self.fixture.host.routes['pulls/7'] = self.fixture.pr
        tmp = tempfile.TemporaryDirectory(prefix='nightshift-actions-admission-')
        self.addCleanup(tmp.cleanup)
        self.controller = SimpleNamespace(directory=Path(tmp.name))
        self.delivery = d.Delivery(self.controller)
        self.host = self.delivery.host
        self.host.call = self.fixture.host.call
        self.refs = dict(head=a.HEAD, base=a.BASE)
        self.host.refs = lambda _: dict(self.refs)

    def observe(self):
        return self.delivery.observe_ci(self.fixture.p, dict(number=7), a.HEAD, self.refs)

    def strict(self, check_head):
        self.fixture.p['checks'][0].pop('actions')
        row = copy.deepcopy(self.fixture.check)
        row['head_sha'] = check_head
        self.fixture.host.routes['commits/' + a.MERGE + '/check-runs'] = dict(total_count=1, check_runs=[row])

    def test_verified_actions_receipt_reaches_ci_passed(self):
        result, observed = self.observe()
        self.assertEqual(result['status'], 'ci_passed')
        self.assertEqual(observed['checks'][0]['reported_head'], a.HEAD)
        self.assertEqual(observed['checks'][0]['head'], a.MERGE)
        self.assertTrue(result['evidence'])

    def test_default_never_promotes_head_attached_check(self):
        self.strict(a.HEAD)
        self.assertEqual(self.observe()[0]['status'], 'ci_unknown')
        self.assertFalse(any('/actions/' in path for path in self.fixture.host.calls))

    def test_default_merge_attached_check_still_passes(self):
        self.strict(a.MERGE)
        self.assertEqual(self.observe()[0]['status'], 'ci_passed')

    def test_mixed_required_gate_cannot_be_dropped(self):
        self.fixture.p['checks'].append(dict(name='extra', app_id=17))
        route = 'commits/' + a.MERGE + '/check-runs'
        self.fixture.host.routes[route] = dict(total_count=0, check_runs=[])
        self.assertEqual(self.observe()[0]['status'], 'ci_unknown')
        row = copy.deepcopy(self.fixture.check)
        row.update(name='extra', head_sha=a.MERGE, app=dict(id=17),
                   status='queued', conclusion=None)
        self.fixture.host.routes[route] = dict(total_count=1, check_runs=[row])
        self.assertEqual(self.observe()[0]['status'], 'ci_unknown')
        row.update(status='completed', conclusion='success')
        self.assertEqual(self.observe()[0]['status'], 'ci_passed')

    def test_missing_receipt_remains_unknown(self):
        self.fixture.host.routes['actions/runs/202/artifacts?per_page=100'] = dict(total_count=0, artifacts=[])
        result, observed = self.observe()
        self.assertEqual(result['status'], 'ci_unknown')
        self.assertEqual(observed['checks'][0]['reason'], 'actions_artifact_missing_or_ambiguous')

    def test_verified_failed_check_remains_failure(self):
        self.fixture.check['conclusion'] = 'failure'
        self.fixture.job['conclusion'] = 'failure'
        self.assertEqual(self.observe()[0]['status'], 'ci_failed')

    def test_pr_candidate_changed_during_collection_blocks(self):
        original = self.host.call
        def moved(argv, *args, **kwargs):
            result = original(argv, *args, **kwargs)
            if argv[-1].endswith('/zip'):
                self.fixture.pr['merge_commit_sha'] = 'd' * 40
            return result
        self.host.call = moved
        with self.assertRaisesRegex(ValueError, 'ci_pull_request_changed'):
            self.observe()

    def test_remote_base_changed_after_collection_blocks(self):
        self.host.refs = lambda _: dict(head=a.HEAD, base='d' * 40)
        with self.assertRaisesRegex(ValueError, 'ci_revision_changed'):
            self.observe()

    def test_duplicate_merge_parents_cannot_certify_default(self):
        self.strict(a.MERGE)
        self.fixture.host.routes['git/commits/' + a.MERGE]['parents'].append(dict(sha=a.HEAD))
        self.assertEqual(self.observe()[0]['status'], 'ci_unknown')


class AuthorityBinding(unittest.TestCase):
    setUp = f.DeliveryReview.setUp
    git = f.DeliveryReview.git
    write_profile = f.DeliveryReview.write_profile
    authority = f.DeliveryReview.authority

    def contract(self):
        return dict(workflow_path='.github/workflows/ci.yml', workflow_sha256=a.DIGEST,
                    job='test', producer_job='producer', artifact_prefix='nightshift-integration')

    def test_optional_contract_is_explicit_profile_data(self):
        self.profile['checks'][0]['actions'] = self.contract()
        self.write_profile()
        self.assertEqual(d.profile(self.c)['checks'][0]['actions'], self.contract())

    def test_duplicate_identity_with_different_contract_is_rejected(self):
        extra = copy.deepcopy(self.profile['checks'][0])
        extra['actions'] = self.contract()
        self.profile['checks'].append(extra)
        self.write_profile()
        with self.assertRaisesRegex(ValueError, 'duplicate_required_checks'):
            d.profile(self.c)

    def test_adapter_change_blocks_retained_repair_before_dispatch(self):
        grant, request = self.authority('commit')
        state = self.delivery.state()
        state['attempts'][request] = dict(grant=grant, repair=dict(grant='factory', trigger='synthetic'))
        self.c.save()
        original = d.m.sha
        def changed(path):
            return '0' * 64 if Path(path).name == 'nightshift-delivery-actions.py' else original(path)
        count = len(self.worker.calls)
        with patch.object(d.m, 'sha', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'delivery_policy_changed'):
                self.delivery.resume_repair(grant, request)
        self.assertEqual(len(self.worker.calls), count)


if __name__ == '__main__':
    unittest.main()
