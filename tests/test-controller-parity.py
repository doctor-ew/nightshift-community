#!/usr/bin/env python3
"""Synthetic controller regressions for portable downstream fixes."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
m = load('parity_pipeline', 'scripts/nightshift-pipeline.py')
f = load('parity_fixture', 'tests/nightshift-behavior-fixture.py')

class ControllerParity(unittest.TestCase):
    def stage_run(self, development):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve() / 'project'; f.prepare(ROOT, project, task='sample', final=True)
            settings = dict(ref='gh:sample', provider='claude', model='fixture', policy='claude-only', auth='subscription', branch='none', base='', push=False, pr=False)
            calls = []
            def worker(stage, handoff, receipt):
                calls.append(stage); log = project / 'docs/sample' / (stage + '-check.log'); log.write_text('synthetic worker check\n')
                receipt.write_text(json.dumps(dict(version=1, task='sample', stage=stage, status='pass', findings=[], checks=[dict(command='synthetic-check', exit_code=0)], evidence=[dict(path=str(log.relative_to(project)), sha256=m.sha(log))])))
                return 0
            handoff = m.load('handoff'); original_load = m.load
            with patch.object(handoff, 'graph', return_value=dict(status='unavailable', reason='synthetic-no-graph', records=[])), patch.object(m, 'load', side_effect=lambda name: handoff if name == 'handoff' else original_load(name)), patch.dict('os.environ', NIGHTSHIFT_ROUTING_FILE=str(ROOT/'routing.json')), patch.object(m, 'proof', side_effect=lambda project, task, gate: development if gate == 'development' else dict(outcome='unknown', reason='proof_state_unavailable')):
                controller = m.Pipeline(project, 'sample', settings, worker); controller.run()
            return calls, controller.state

    def test_unsealed_proof_allows_adversarial_and_implementation_entry(self):
        calls, state = self.stage_run(dict(outcome='unknown', reason='proof_state_unavailable'))
        self.assertEqual(calls[:2], ['adversarial', 'implement'])
        self.assertNotIn('development-proof', [row['id'] for row in state.get('findings', [])])

    def test_failed_sealed_proof_still_blocks_implementation(self):
        calls, state = self.stage_run(dict(outcome='fail', reason='red_not_observed'))
        self.assertNotIn('implement', calls)
        self.assertEqual(state['findings'][0]['id'], 'development-proof')

    def test_later_route_change_does_not_invalidate_product(self):
        route = dict(provider='codex', model='synthetic')
        plan = dict(policy='standard', routing_path='/synthetic', routing_sha256='a', stages={stage:dict(route) for stage in m.STAGES})
        changed = copy.deepcopy(plan); changed['stages']['review']['model']='different-synthetic'
        self.assertEqual(m.stage_policy(plan,'product'), m.stage_policy(changed,'product'))
        self.assertNotEqual(m.stage_policy(plan,'review'), m.stage_policy(changed,'review'))

    def test_runtime_identity_includes_dispatcher_and_contract(self):
        before=m.runtime_digest(); original=m.sha
        for name in ('scripts/nightshift-agent.sh','scripts/nightshift-contract.jq','scripts/nightshift-retry-budget.py','scripts/nightshift-ticket-budget.py','agents/nightshift-engineer.md'):
            with patch.object(m, 'sha', side_effect=lambda path:'0'*64 if Path(path)==ROOT/name else original(path)):
                self.assertNotEqual(m.runtime_digest(), before, name)


    def test_classification_review_is_bound_to_independent_current_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()/'project'; f.prepare(ROOT,project,task='sample',final=True)
            path=project/'docs/sample/behavior-scenarios.json'; doc=json.loads(path.read_text())
            doc['author']['provider']='codex'
            for app in [doc['applicability']]+[case['applicability'] for case in doc['cases']]: app['review']=None
            path.write_text(json.dumps(doc)); original=path.read_bytes()
            receipt=project/'docs/sample/adversarial-current.json'
            classification=path.with_name('classification-review-adversarial-1.json')
            classification.write_text(json.dumps(dict(version=1,task='sample',decision='approve',reviewed_input_sha256=m.load('behavior-proof').semantics(doc),case_ids=[case['id'] for case in doc['cases']])))
            report=dict(version=1,task='sample',stage='adversarial',status='pass',findings=[],checks=[dict(command='synthetic-classification-review',exit_code=0)],evidence=[dict(path=str(classification.relative_to(project)),sha256=m.sha(classification))])
            transport=path.with_name('classification-review-transport.out.json')
            transport.write_text(json.dumps(dict(status='SUCCESS',results=dict(decision='approve'))))
            report['evidence'].append(dict(path=str(transport.relative_to(project)),sha256=m.sha(transport)))
            receipt.write_text(json.dumps(report))
            self.assertFalse(m.record_classification_review(project,'sample',dict(provider='codex',model='synthetic'),receipt)); self.assertEqual(path.read_bytes(),original)
            self.assertTrue(m.record_classification_review(project,'sample',dict(provider='claude',model='synthetic'),receipt))
            retained=json.loads(path.read_text()); self.assertEqual(retained['applicability']['review']['evidence_sha256'],m.sha(receipt))
            self.assertEqual(retained['applicability']['review']['reviewed_input_sha256'],m.load('behavior-proof').semantics(retained))
            self.assertEqual(m.validate_receipt(receipt,'sample','adversarial',project)['status'],'pass')
            self.assertFalse(m.record_classification_review(project,'sample',dict(provider='claude',model='synthetic'),receipt))

    def test_missing_or_stale_classification_receipt_cannot_approve(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()/'project'; f.prepare(ROOT,project,task='sample',final=True)
            path=project/'docs/sample/behavior-scenarios.json'; doc=json.loads(path.read_text());doc['author']['provider']='codex'
            for app in [doc['applicability']]+[case['applicability'] for case in doc['cases']]:app['review']=None
            path.write_text(json.dumps(doc)); original=path.read_bytes(); receipt=project/'docs/sample/adversarial-stale.json'
            self.assertFalse(m.record_classification_review(project,'sample',dict(provider='claude',model='synthetic'),receipt))
            receipt.write_text(json.dumps(dict(version=1,task='sample',stage='adversarial',status='pass',findings=[],checks=[dict(command='synthetic-check',exit_code=0)],evidence=[dict(path=str(path.relative_to(project)),sha256='0'*64)])))
            self.assertFalse(m.record_classification_review(project,'sample',dict(provider='claude',model='synthetic'),receipt));self.assertEqual(path.read_bytes(),original)


    def test_policy_change_invalidates_independence_contract(self):
        plan=dict(policy='standard',stages={stage:dict(provider='claude',model='synthetic') for stage in m.STAGES})
        changed=copy.deepcopy(plan);changed['policy']='claude-only'
        for stage in m.STAGES:self.assertNotEqual(m.stage_policy(plan,stage),m.stage_policy(changed,stage))


    def test_current_independent_review_replaces_stale_attestation_without_rewriting_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()/'project';f.prepare(ROOT,project,task='sample',final=True)
            path=project/'docs/sample/behavior-scenarios.json';doc=json.loads(path.read_text());doc['author']['provider']='claude'
            for app in [doc['applicability']]+[case['applicability'] for case in doc['cases']]:
                app['review']=dict(reviewer_provider='claude',reviewer_author_id='prior-independent-session',decision='approve',reviewed_input_sha256='0'*64,evidence_sha256='1'*64)
            path.write_text(json.dumps(doc));classification=path.with_name('classification-review-adversarial-2.json')
            classification.write_text(json.dumps(dict(version=1,task='sample',decision='approve',reviewed_input_sha256=m.load('behavior-proof').semantics(doc),case_ids=[case['id'] for case in doc['cases']])))
            receipt=path.with_name('adversarial-2.json');receipt.write_text(json.dumps(dict(version=1,task='sample',stage='adversarial',status='pass',findings=[],checks=[dict(command='synthetic-classification-review',exit_code=0)],evidence=[dict(path=str(classification.relative_to(project)),sha256=m.sha(classification))])))
            original=receipt.read_bytes()
            self.assertFalse(m.record_classification_review(project,'sample',dict(provider='claude',model='synthetic'),receipt))
            self.assertTrue(m.record_classification_review(project,'sample',dict(provider='claude',model='synthetic'),receipt,policy='claude-only'))
            m.load('behavior-proof').reviewed(json.loads(path.read_text()));self.assertEqual(receipt.read_bytes(),original)
            self.assertEqual(m.validate_receipt(receipt,'sample','adversarial',project)['status'],'pass')

    def test_nested_product_route_is_bound_without_unrelated_engineering_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp).resolve()/'routing.json';routing=json.loads((ROOT/'routing.json').read_text());path.write_text(json.dumps(routing))
            plan=dict(routing_path=str(path))
            before=m.nested_routing(plan,'product')
            routing['roles']['nightshift-engineer']['gears']['1']['model']='unrelated-synthetic';path.write_text(json.dumps(routing))
            self.assertEqual(m.nested_routing(plan,'product'),before)
            routing['roles']['nightshift-spec-writer']['gears']['1']['model']='changed-synthetic';path.write_text(json.dumps(routing))
            self.assertNotEqual(m.nested_routing(plan,'product'),before)


    def test_current_self_approval_is_replaced_by_fresh_independent_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()/'project';f.prepare(ROOT,project,task='sample',final=True)
            path=project/'docs/sample/behavior-scenarios.json';doc=json.loads(path.read_text());doc['author']['provider']='codex'
            helper=m.load('behavior-proof');digest=helper.semantics(doc)
            for app in [doc['applicability']]+[case['applicability'] for case in doc['cases']]:
                app['review']=dict(reviewer_provider=doc['author']['provider'],reviewer_author_id=doc['author']['author_id'],decision='approve',reviewed_input_sha256=digest,evidence_sha256='1'*64)
            path.write_text(json.dumps(doc));classification=path.with_name('classification-review-adversarial-1.json')
            classification.write_text(json.dumps(dict(version=1,task='sample',decision='approve',reviewed_input_sha256=digest,case_ids=[case['id'] for case in doc['cases']])))
            receipt=path.with_name('adversarial-1.json');receipt.write_text(json.dumps(dict(version=1,task='sample',stage='adversarial',status='pass',findings=[],checks=[dict(command='synthetic-review',exit_code=0)],evidence=[dict(path=str(classification.relative_to(project)),sha256=m.sha(classification))])))
            original=receipt.read_bytes()
            self.assertTrue(m.record_classification_review(project,'sample',dict(provider='claude',model='synthetic'),receipt))
            helper.reviewed(json.loads(path.read_text()));self.assertEqual(receipt.read_bytes(),original)

    def test_fresh_product_scenario_receipt_survives_controller_attestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()/'project';f.prepare(ROOT,project,task='sample',final=True)
            path=project/'docs/sample/behavior-scenarios.json';doc=json.loads(path.read_text());doc['author']['provider']='codex'
            for app in [doc['applicability']]+[case['applicability'] for case in doc['cases']]:app['review']=None
            path.write_text(json.dumps(doc))
            settings=dict(ref='gh:sample',provider='codex',model='synthetic',policy='standard',auth='subscription',branch='none',base='',push=False,pr=False)
            calls=[];original_product=[]
            def worker(stage,handoff,receipt):
                calls.append(stage)
                if stage=='review' or (stage=='product' and calls.count('product')>1):return 1
                log=project/'docs/sample'/(stage+'-check.log');log.write_text('synthetic check')
                evidence=[dict(path=str(log.relative_to(project)),sha256=m.sha(log))]
                if stage=='product':evidence.append(dict(path=str(path.relative_to(project)),sha256=m.sha(path)))
                if stage=='adversarial':
                    current=json.loads(path.read_text());classification=path.with_name('classification-review-'+receipt.stem+'.json')
                    classification.write_text(json.dumps(dict(version=1,task='sample',decision='approve',reviewed_input_sha256=m.load('behavior-proof').semantics(current),case_ids=[case['id'] for case in current['cases']])))
                    evidence.append(dict(path=str(classification.relative_to(project)),sha256=m.sha(classification)))
                receipt.write_text(json.dumps(dict(version=1,task='sample',stage=stage,status='pass',findings=[],checks=[dict(command='synthetic-check',exit_code=0)],evidence=evidence)))
                if stage=='product':original_product.append((receipt,receipt.read_bytes()))
                return 0
            handoff=m.load('handoff');original_load=m.load
            with patch.object(handoff,'graph',return_value=dict(status='unavailable',records=[])),patch.object(m,'load',side_effect=lambda name:handoff if name=='handoff' else original_load(name)),patch.dict('os.environ',NIGHTSHIFT_ROUTING_FILE=str(ROOT/'routing.json')),patch.object(m,'proof',return_value=dict(outcome='unknown',reason='proof_state_unavailable')):
                controller=m.Pipeline(project,'sample',settings,worker)
                # Existing stage history proves this is fresh worker authoring,
                # rather than the separate existing-draft import shortcut.
                controller.state['history'].append(dict(reason='fresh-worker-fixture'))
                controller.save();controller.run()
                self.assertEqual(calls.count('product'),1,calls)
                self.assertEqual(calls[:3],['product','adversarial','implement'])
                row=controller.state['completed']['product']
                report=m.validate_receipt(row['receipt'],'sample','product',project)
                self.assertEqual(original_product[0][0].read_bytes(),original_product[0][1])
                self.assertTrue(any(h.get('reason')=='classification_attestations_revalidated' for h in controller.state['history']))
                # Every unaffected evidence file remains authoritative.
                (project/'docs/sample/product-check.log').write_text('tampered')
                with self.assertRaises(ValueError):m.validate_receipt(row['receipt'],'sample','product',project)


    def test_invalid_literal_scope_is_never_imported_or_mutated(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()/'project';f.prepare(ROOT,project,task='sample',final=True)
            spec=project/'docs/sample/SPEC.md'
            spec.write_text(spec.read_text().replace('| tests/test_fixture_sample.py |', '| `tests/test_fixture_sample.py` — net-new planned file |'))
            settings=dict(ref='gh:sample',provider='codex',model='synthetic',policy='standard',auth='subscription',branch='none',base='',push=False,pr=False)
            controller=m.Pipeline(project,'sample',settings,lambda *args:1)
            controller.state.update(plan=m.routes(project,settings),decisions=[])
            before={str(p.relative_to(project)):p.read_bytes() for p in project.rglob('*') if p.is_file()}
            controller.import_draft()
            self.assertNotIn('product',controller.state['completed'])
            self.assertIn('scope',controller.state['findings'][0]['id'])
            after={str(p.relative_to(project)):p.read_bytes() for p in project.rglob('*') if p.is_file()}
            self.assertEqual(after,before)
            self.assertFalse(list((project/'.git').rglob('product-import-*.json')))

    def test_worker_product_scope_is_checked_before_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()/'project';f.prepare(ROOT,project,task='sample',final=True)
            spec=project/'docs/sample/SPEC.md';calls=[]
            settings=dict(ref='gh:sample',provider='codex',model='synthetic',policy='standard',auth='subscription',branch='none',base='',push=False,pr=False)
            def worker(stage,handoff,receipt):
                calls.append(stage)
                if stage!='product':return 1
                spec.write_text(spec.read_text().replace('| tests/test_fixture_sample.py |','| `tests/test_fixture_sample.py` — net-new planned file |'))
                receipt.write_text(json.dumps(dict(version=1,task='sample',stage=stage,status='pass',findings=[],checks=[dict(command='synthetic-check',exit_code=0)],evidence=[dict(path=str(spec.relative_to(project)),sha256=m.sha(spec))])))
                return 0
            handoff=m.load('handoff');original_load=m.load
            with patch.object(handoff,'graph',return_value=dict(status='unavailable',records=[])),patch.object(m,'load',side_effect=lambda name:handoff if name=='handoff' else original_load(name)),patch.dict('os.environ',NIGHTSHIFT_ROUTING_FILE=str(ROOT/'routing.json')):
                controller=m.Pipeline(project,'sample',settings,worker)
                controller.state['history'].append(dict(reason='fresh-worker-fixture'));controller.save()
                result=controller.run()
            self.assertEqual(result,1);self.assertEqual(calls,['product'])
            self.assertNotIn('product',controller.state['completed'])
            self.assertIn('product_scope_invalid',controller.state['attempts'][0]['reason'])

if __name__ == '__main__': unittest.main()
