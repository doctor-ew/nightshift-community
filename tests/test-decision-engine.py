#!/usr/bin/env python3
"""Synthetic-only decision authority, bounded transport and restart regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('engine',Path(__file__).resolve().parents[1]/'scripts/nightshift-decision-engine.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


def packet():
    refs=[]
    for role in sorted(e.ROLES):
        text={'requirement':'The function returns the argument.','source':'def identity(value): return value','assertion':'assert identity(3) == 3','observation':'PASS identity assertion'}[role]
        refs.append(dict(id=role,role=role,path=role+'.txt',file_sha256=e.text_hash(text),sha256=e.text_hash(text),start_line=1,end_line=1,text=text))
    return dict(version=1,id='identity',kind='requirement_supported',question='Does the supplied implementation and executed assertion support this requirement?',requirements=[dict(id='requirement-one',evidence=[r['id'] for r in refs])],findings=[],evidence=refs,checks=[dict(id='identity-test',exit_code=0,output_sha256=next(r['file_sha256'] for r in refs if r['role']=='observation'),evidence=['observation'])],high_risk=False)


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.calls=[];self.finished=[];self.transport_calls=[]
        self.settings=dict(endpoint='https://example.invalid/evaluate',model='fixture-v1',key_env='SYNTHETIC_UNUSED',timeout_seconds=1,max_bytes=24576,allow_loopback=False,enabled=True)
    def engine(self,score=1,shadow=0,review=None,transport=None,authority='authorized-session',policy=None):
        def request(settings,key,body):
            self.transport_calls.append(body)
            return e.encoded(dict(model=settings['model'],answers={'supported':dict(type='noul',noul=score)}))
        def reserve(kind,request_id,size):
            token=len(self.calls);self.calls.append((kind,request_id,size));return token
        return e.Engine(self.tmp.name,authority,self.settings,reserve,lambda token,outcome:self.finished.append((token,outcome)),transport or request,review,policy or dict(e.POLICY,shadow_percent=shadow))
    def review(self,result='yes'):
        return lambda p,primary,mode:dict(decision=result,packet_sha256=e.digest(p),reviewer_id='independent-fixture',evidence=[r['id'] for r in p['evidence']])
    def test_yes_cached_no_repeat(self):
        engine=self.engine();first=engine.decide(packet());second=engine.decide(packet())
        self.assertEqual(first['decision'],'yes');self.assertTrue(second['cache_hit']);self.assertEqual(len(self.calls),1)
        self.assertLessEqual(len(self.transport_calls[0]),e.MAX_BYTES)
    def test_no_preserved(self):
        engine=self.engine(score=0);self.assertEqual(engine.decide(packet())['decision'],'no')
        self.assertTrue(engine.decide(packet())['cache_hit']);self.assertEqual(len(self.calls),1)
    def test_abstain_selective_escalation(self):
        result=self.engine(score=.5,review=self.review()).decide(packet())
        self.assertEqual(result['decision'],'yes');self.assertEqual([x[0] for x in self.calls],['jev','exception'])
    def test_abstain_without_review_blocks(self):
        result=self.engine(score=.5).decide(packet());self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['reason'],'decision_escalation_required')
    def test_shadow_contradiction_blocks_confident_yes_and_no(self):
        for primary,shadow in ((1,'no'),(0,'yes')):
            engine=self.engine(score=primary,shadow=100,review=self.review(shadow),authority=str(primary))
            result=engine.decide(packet());self.assertEqual(result['reason'],'decision_reviewer_contradiction');self.assertEqual(result['decision'],'abstain')
    def test_high_risk_requires_review(self):
        p=packet();p['high_risk']=True
        self.assertEqual(self.engine().decide(p)['reason'],'decision_escalation_required')
    def test_changed_inputs_and_policy_and_authority_invalidate(self):
        engine=self.engine();engine.decide(packet())
        p=packet();p['question']+=' Check the value.';engine.decide(p)
        self.engine(authority='other-authority').decide(packet())
        self.engine(policy=dict(e.POLICY,shadow_percent=0,yes=.99)).decide(packet())
        self.assertEqual(len(self.calls),4)
    def test_unfinished_reservation_never_relaunches(self):
        def crash(*args):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.engine(transport=crash).decide(packet())
        result=self.engine().decide(packet())
        self.assertEqual(result['reason'],'decision_unfinished_reservation');self.assertEqual(len(self.calls),1)
    def test_missing_or_weak_mapping_prevents_dispatch(self):
        changes=[lambda p:p['requirements'][0]['evidence'].remove('assertion'),lambda p:p['checks'].clear(),lambda p:p['checks'][0].update(exit_code=1),lambda p:p['evidence'][0].update(sha256='0'*64),lambda p:p['evidence'][0].update(end_line=8),lambda p:p['evidence'][0].update(path='../escape')]
        for mutate in changes:
            p=packet();mutate(p)
            with self.assertRaises(ValueError):self.engine().decide(p)
        self.assertEqual(self.calls,[])
    def test_packet_and_encoded_request_limits_before_reservation(self):
        p=packet();p['question']='x'*e.MAX_BYTES
        with self.assertRaisesRegex(ValueError,'packet_too_large'):self.engine().decide(p)
        p=packet();p['question']='x'*(e.MAX_BYTES-len(e.encoded(p))-20)
        self.assertLess(len(e.encoded(p)),e.MAX_BYTES)
        with self.assertRaisesRegex(ValueError,'request_too_large'):self.engine().decide(p)
        self.assertEqual(self.calls,[])
    def test_model_schema_nonfinite_and_transport_error_fail_closed(self):
        responses=[b'{',e.encoded(dict(model='other',answers={})),b'{"model":"fixture-v1","answers":{"supported":{"type":"noul","noul":NaN}}}',e.encoded(dict(model='fixture-v1',answers={'supported':dict(type='noul',noul=True)}))]
        for i,response in enumerate(responses):
            result=self.engine(transport=lambda *args,r=response:r,authority=str(i)).decide(packet())
            self.assertEqual(result['status'],'blocked');self.assertEqual(result['decision'],'abstain')
        def failed(*args):raise OSError('synthetic transport failure')
        self.assertEqual(self.engine(transport=failed,authority='failed').decide(packet())['status'],'blocked')
    def test_stale_or_incomplete_escalation_rejected(self):
        for i,review in enumerate((lambda *a:{},lambda *a:dict(decision='yes',packet_sha256='0'*64,reviewer_id='fixture',evidence=['source']))):
            self.assertEqual(self.engine(score=.5,review=review,authority=str(i)).decide(packet())['reason'],'decision_escalation_invalid')
    def test_escalation_yes_requires_all_evidence_roles(self):
        def incomplete(p,primary,mode):
            return dict(decision='yes',packet_sha256=e.digest(p),reviewer_id='independent-fixture',evidence=['source'])
        result=self.engine(score=.5,review=incomplete).decide(packet())
        self.assertEqual(result['reason'],'decision_escalation_evidence_incomplete')
        self.assertEqual(result['decision'],'abstain')
    def test_shadow_sample_is_stable_across_authorities(self):
        results=[]
        for authority in ('first','second'):
            results.append(self.engine(shadow=50,review=self.review(),authority=authority).decide(packet()))
        self.assertEqual([c['kind'] for c in results[0]['calls']],[c['kind'] for c in results[1]['calls']])
    def test_cache_revalidates_raw_artifact_integrity(self):
        for suffix in ('packet','jev','review'):
            engine=self.engine(shadow=100,review=self.review(),authority=suffix)
            result=engine.decide(packet());calls=len(self.calls)
            path=Path(self.tmp.name)/(result['key']+'.'+suffix+'.json')
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'artifact_changed'):engine.decide(packet())
            self.assertEqual(len(self.calls),calls)
    def test_cache_receipt_tampering_cannot_turn_negative_into_yes(self):
        engine=self.engine(score=0);result=engine.decide(packet())
        path=Path(self.tmp.name)/(result['key']+'.json')
        data=json.loads(path.read_text());data['decision']='yes';path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'cache_integrity'):engine.decide(packet())
        self.assertEqual(len(self.calls),1)
    def test_cache_rederives_verdict_even_if_local_checksum_recomputed(self):
        engine=self.engine(score=0);result=engine.decide(packet())
        path=Path(self.tmp.name)/(result['key']+'.json')
        data=json.loads(path.read_text());data['decision']='yes'
        data['receipt_sha256']=e.digest({k:v for k,v in data.items() if k not in ('receipt_sha256','cache_hit')})
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'verdict_changed'):engine.decide(packet())
    def test_shadow_sampling_ignores_packet_and_reference_labels(self):
        original=packet();renamed=copy.deepcopy(original);renamed['id']='unrelated-new-label'
        mapping={r['id']:'renamed-'+r['id'] for r in renamed['evidence']}
        for r in renamed['evidence']:r['id']=mapping[r['id']]
        renamed['evidence'].reverse()
        for group in ('requirements','findings','checks'):
            for row in renamed[group]:row['evidence']=[mapping[r] for r in reversed(row['evidence'])]
        self.assertEqual(e.sampled(original,dict(e.POLICY,shadow_percent=43)),e.sampled(renamed,dict(e.POLICY,shadow_percent=43)))
    def test_mutable_model_alias_rejected(self):
        self.settings['model']='jev-latest'
        with self.assertRaisesRegex(ValueError,'concrete_model_required'):self.engine()
        self.assertEqual(self.calls,[])
    def test_unknown_kind_cannot_authorize_operator_or_manual(self):
        p=packet();p['kind']='operator_approved'
        with self.assertRaisesRegex(ValueError,'kind_invalid'):self.engine().decide(p)
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
