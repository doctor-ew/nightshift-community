#!/usr/bin/env python3
"""Independent exact-evidence acceptance regressions; synthetic providers only."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('acceptance_review_fixture',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class ManualFixture(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-acceptance-review-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.plan=f.fixture(self.root)
        self.cases=[dict(id='visual',requirement='Observe the return value in the interface.',manual=True),
            dict(id='keyboard',requirement='Complete the flow using the keyboard.',manual=True),
            dict(id='unit',requirement='Return two in unit checks.',manual=False)]
        self.write_cases();self.binding='a'*64
    def write_cases(self):(self.root/'scenarios.json').write_text(json.dumps(dict(version=1,cases=self.cases)))
    def attest(self,binding=None):
        return dict(binding=binding or self.binding,cases=[dict(id=c['id'],case_sha256=m.digest(c),passed=True,
            observation='Observed the required behavior.',evidence='Synthetic manual observation on the inspected revision.') for c in self.cases if c['manual']])
    def validate(self,att):return m.manual_acceptance(self.root,self.plan,self.binding,att)

class ManualContract(ManualFixture):
    def test_exact_case_coverage_and_literal_pass_required(self):
        good=self.attest();bad=[]
        bad.extend([dict(binding=self.binding,accepted=True),dict(good,cases=good['cases'][:1]),dict(good,cases=good['cases']+[good['cases'][0]])])
        for mutate in (lambda a:a['cases'][1].update(id='visual'),lambda a:a['cases'][0].update(id='unit'),
                       lambda a:a['cases'][0].update(case_sha256='b'*64),lambda a:a['cases'][0].update(passed=1),
                       lambda a:a['cases'][0].update(passed=False),lambda a:a['cases'][0].update(extra='ignored')):
            value=copy.deepcopy(good);mutate(value);bad.append(value)
        for index,value in enumerate(bad):
            with self.subTest(index=index),self.assertRaises(ValueError):self.validate(value)
    def test_text_bounds_and_nul_are_rejected(self):
        for field in ('observation','evidence'):
            for value in ('','  ',None,[], 'x\0y','é'*1025):
                with self.subTest(field=field,value=repr(value)[:30]):
                    att=self.attest();att['cases'][0][field]=value
                    with self.assertRaises(ValueError):self.validate(att)
    def test_same_case_id_changed_requirement_rejects_old_hash(self):
        att=self.attest();self.cases[0]['requirement']='A new manual obligation';self.write_cases()
        with self.assertRaises(ValueError):self.validate(att)
    def test_aggregate_byte_ceiling_is_enforced(self):
        self.cases=[dict(id='m'+str(i),requirement='Inspect '+str(i),manual=True) for i in range(4)];self.write_cases()
        att=self.attest()
        for row in att['cases']:row.update(observation='é'*1000,evidence='é'*1000)
        with self.assertRaisesRegex(ValueError,'too_large'):self.validate(att)
    def test_automated_only_boolean_compatibility(self):
        self.cases=[dict(id='unit',requirement='Return two.',manual=False)];self.write_cases()
        self.assertEqual(self.validate(dict(binding=self.binding,accepted=True)),dict(binding=self.binding,accepted=True,cases=[]))
        with self.assertRaises(ValueError):self.validate(dict(binding=self.binding,accepted=1))
    def test_normalization_orders_cases_without_changing_testimony(self):
        a=self.attest();b=copy.deepcopy(a);b['cases'].reverse()
        self.assertEqual(self.validate(a),self.validate(b))
        self.assertEqual({r['observation'] for r in self.validate(a)['cases']},{'Observed the required behavior.'})

class ManualExecution(ManualFixture):
    def prepared(self):
        self.worker=f.Worker();self.c=m.Operations(self.root,'demo',self.worker)
        assessment=self.c.assess('groom-spec')
        grant=self.c.authorize(m.RECIPES['factory'],assessment['binding'],'synthetic','prepare')
        result=self.c.chain(grant['id'])
        self.assertTrue(all(r['status']=='passed' for r in result['results']),result)
        self.binding=self.c.assess('accept')['binding'];return self.attest()
    def grant(self,att,request='accept'):
        return self.c.authorize(['accept'],self.binding,'synthetic-operator',request,att)
    def test_invalid_attestation_creates_no_grant_or_call(self):
        self.prepared();before=copy.deepcopy(self.c.state['authorizations']);calls=list(self.worker.calls)
        with self.assertRaises(ValueError):self.grant(dict(binding=self.binding,accepted=True))
        self.assertEqual(self.c.state['authorizations'],before);self.assertEqual(self.worker.calls,calls)
    def test_exact_receipt_duplicate_replay_and_changed_payload_conflict(self):
        att=self.prepared();grant=self.grant(att);calls=list(self.worker.calls)
        self.assertEqual(self.grant(att,'different-request')['id'],grant['id'])
        reordered=copy.deepcopy(att);reordered['cases'].reverse()
        self.assertEqual(self.grant(reordered,'reordered-request')['id'],grant['id'])
        result=self.c.execute(grant['id'],'accept','accept-run');self.assertEqual(result['status'],'passed')
        accepted=self.c.state['results']['accept']
        self.assertEqual(accepted['attestation'],m.manual_acceptance(self.root,self.plan,self.binding,att))
        self.assertEqual(accepted['operator'],'synthetic-operator')
        self.assertEqual(self.c.execute(grant['id'],'accept','accept-run')['result'],result['result'])
        changed=copy.deepcopy(att);changed['cases'][0]['observation']='Different testimony'
        with self.assertRaisesRegex(ValueError,'request_id_conflict'):self.grant(changed)
        self.assertEqual(self.worker.calls,calls)
    def test_changed_source_after_grant_cannot_accept(self):
        att=self.prepared();grant=self.grant(att);calls=list(self.worker.calls)
        (self.root/'app.py').write_text('def answer(): return 3\n')
        with self.assertRaises(ValueError):self.c.execute(grant['id'],'accept','stale-accept')
        self.assertNotIn('accept',self.c.state['results']);self.assertEqual(self.worker.calls,calls)
    def test_execute_revalidates_retained_attestation(self):
        att=self.prepared();grant=self.grant(att)
        with self.c.lease():
            self.c.state['authorizations'][grant['id']]['attestation']['cases'][0]['passed']=False;self.c.save()
        with self.assertRaises(ValueError):self.c.execute(grant['id'],'accept','tampered-accept')
        self.assertNotIn('accept',self.c.state['results'])
    def test_checkpoint_replay_preserves_exact_attestation_without_calls(self):
        att=self.prepared();grant=self.grant(att);calls=list(self.worker.calls)
        with patch.object(self.c,'finalize',side_effect=KeyboardInterrupt('synthetic crash')):
            with self.assertRaises(KeyboardInterrupt):self.c.execute(grant['id'],'accept','checkpoint-accept')
        resumed=m.Operations(self.root,'demo',self.worker)
        self.assertEqual(resumed.execute(grant['id'],'accept','checkpoint-accept')['status'],'passed')
        self.assertEqual(resumed.state['results']['accept']['attestation'],m.manual_acceptance(self.root,self.plan,self.binding,att))
        self.assertEqual(self.worker.calls,calls)

if __name__=='__main__':unittest.main()
