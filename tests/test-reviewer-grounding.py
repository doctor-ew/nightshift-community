#!/usr/bin/env python3
"""Role-grouped reviewer grounding, the single re-ask and the configured framing limit.

Synthetic reviewers only. The 11-reference packet mirrors the layout of a real
selective-citation failure (two requirement, three source, four assertion, two
observation references) with invented text.
"""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
e=load('grounding_engine',ROOT/'scripts/nightshift-decision-engine.py')
render=load('grounding_render',ROOT/'scripts/nightshift-decision-render.py')

LAYOUT=[('requirement','SPEC.md'),('requirement','scenarios.json'),('source','build.py'),
        ('assertion','test-unit.js'),('assertion','test-unit.js'),('assertion','run-unit.sh'),('assertion','run-browser.sh'),
        ('observation','observations/unit'),('observation','observations/browser'),('source','app.js'),('source','test-helpers.js')]

def realistic_packet():
    refs=[]
    for index,(role,path) in enumerate(LAYOUT,1):
        text=f'{role} line {index} for {path}'
        refs.append(dict(id=f'ref-{index}',role=role,path=path,file_sha256=e.text_hash(text),sha256=e.text_hash(text),start_line=1,end_line=1,text=text))
    observed=[r for r in refs if r['role']=='observation']
    return dict(version=1,id='requirement_supported-2',kind='requirement_supported',question='Is the requirement supported by source, assertions and observations?',
                requirements=[dict(id='AC-2',evidence=[r['id'] for r in refs])],findings=[],evidence=refs,
                checks=[dict(id='check-'+r['path'].split('/')[-1],exit_code=0,output_sha256=r['file_sha256'],evidence=[r['id']]) for r in observed],high_risk=False)

def ids(packet,*roles):
    return [r['id'] for r in packet['evidence'] if r['role'] in roles]

def grounded(packet,reviewer_id,decision='yes',skip=(),annotate=False):
    """A reviewer answer in the new grouped shape, as the dispatcher would parse it."""
    groups={}
    for role in ('requirement','source','assertion','observation'):
        chosen=[] if role in skip else ids(packet,role)[:2]
        groups[role]=[c+': because' if annotate else c for c in chosen]
    return dict(decision=decision,packet_sha256=e.digest(packet),reviewer_id=reviewer_id,grounding=groups)


class Adapter(unittest.TestCase):
    def setUp(self):self.packet=realistic_packet();self.reviewer='decision-review-'+'a'*32
    def test_selective_role_complete_yes_is_accepted(self):
        review=e.review_from_grounding(grounded(self.packet,self.reviewer),self.packet)
        self.assertEqual(e.validate_independent_result(review,self.packet,self.reviewer)['decision'],'yes')
        self.assertLess(len(review['evidence']),len(self.packet['evidence']))
    def test_annotated_ids_normalize_without_a_model_call(self):
        review=e.review_from_grounding(grounded(self.packet,self.reviewer,annotate=True),self.packet)
        self.assertTrue(all(ref in ids(self.packet,'requirement','source','assertion','observation') for ref in review['evidence']))
        e.validate_independent_result(review,self.packet,self.reviewer)
    def test_misfiled_id_uses_packet_role(self):
        answer=grounded(self.packet,self.reviewer);moved=answer['grounding']['source'].pop(0);answer['grounding']['assertion'].append(moved)
        e.validate_independent_result(e.review_from_grounding(answer,self.packet),self.packet,self.reviewer)
    def test_role_incomplete_yes_still_blocks_and_names_roles(self):
        review=e.review_from_grounding(grounded(self.packet,self.reviewer,skip=('assertion',)),self.packet)
        with self.assertRaisesRegex(ValueError,'evidence_incomplete'):e.validate_independent_result(review,self.packet,self.reviewer)
        self.assertEqual(e.incomplete_roles(review,self.packet,self.reviewer),['assertion'])
    def test_duplicates_unknown_ids_and_rebinding_still_rejected(self):
        dup=grounded(self.packet,self.reviewer);dup['grounding']['source'].append(dup['grounding']['requirement'][0])
        unknown=grounded(self.packet,self.reviewer);unknown['grounding']['source']=['ref-99']
        rebound=grounded(self.packet,self.reviewer);rebound['packet_sha256']='0'*64
        for answer in (dup,unknown,rebound):
            with self.subTest(answer=answer),self.assertRaises(ValueError):
                review=e.review_from_grounding(answer,self.packet)
                e.validate_independent_result(review,self.packet,self.reviewer)
                self.assertIsNone(e.incomplete_roles(review,self.packet,self.reviewer))
    def test_no_and_abstain_never_trigger_reask(self):
        for verdict in ('no','abstain'):
            review=e.review_from_grounding(grounded(self.packet,self.reviewer,decision=verdict,skip=('assertion',)),self.packet)
            self.assertIsNone(e.incomplete_roles(review,self.packet,self.reviewer))


class ReAsk(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.directory=Path(self.tmp.name)
        self.packet=realistic_packet();self.calls=[];self.finished=[];self.inputs=[]
        self.settings=dict(semantic_mode='independent',provider='claude',model='fixture',timeout_seconds=120,max_bytes=e.MAX_BYTES)
    def reserve(self,kind,request_id,size):
        if len(self.calls)>=getattr(self,'allowance',99):raise ValueError('recovery_allowance_exhausted')
        self.calls.append((kind,request_id,size));return request_id
    def engine(self,answers):
        answers=list(answers)
        def review(packet,reviewer_id,missing=None):
            self.inputs.append((reviewer_id,missing))
            return e.review_from_grounding(answers.pop(0)(packet,reviewer_id),packet)
        return e.IndependentEngine(self.directory,'explicit-authority',self.settings,self.reserve,lambda t,o:self.finished.append(o),review)
    def test_single_reask_recovers_role_incomplete_yes(self):
        result=self.engine([lambda p,r:grounded(p,r,skip=('assertion',)),lambda p,r:grounded(p,r)]).decide(self.packet)
        self.assertEqual((result['status'],result['decision']),('complete','yes'))
        self.assertEqual([c[0] for c in self.calls],['independent','reask']);self.assertEqual(self.finished,['complete','complete'])
        first,second=self.inputs;self.assertIsNone(first[1]);self.assertEqual(second[1],['assertion']);self.assertNotEqual(first[0],second[0])
        request=json.loads((self.directory/(result['key']+'.reask_request.json')).read_text())
        self.assertEqual(set(request),{'packet','packet_sha256','reviewer_id','mode','missing_roles'})
        self.assertTrue((self.directory/(result['key']+'.review.json')).is_file())
        cached=self.engine([]).decide(self.packet);self.assertTrue(cached['cache_hit']);self.assertEqual(len(self.calls),2)
    def test_reask_is_bounded_to_one(self):
        partial=lambda p,r:grounded(p,r,skip=('assertion',))
        result=self.engine([partial,partial,partial]).decide(self.packet)
        self.assertEqual((result['status'],result['reason']),('blocked','decision_independent_evidence_incomplete'))
        self.assertEqual(len(self.calls),2)
    def test_complete_first_answer_spends_one_call(self):
        result=self.engine([lambda p,r:grounded(p,r)]).decide(self.packet)
        self.assertEqual(result['decision'],'yes');self.assertEqual(len(self.calls),1);self.assertNotIn('reask',result)
    def test_reask_respects_allowance(self):
        self.allowance=1
        result=self.engine([lambda p,r:grounded(p,r,skip=('observation',))]).decide(self.packet)
        self.assertEqual((result['status'],result['reason']),('blocked','recovery_allowance_exhausted'))
        self.assertTrue((self.directory/(result['key']+'.review.json')).is_file())
    def test_tampered_reask_receipt_rejected(self):
        result=self.engine([lambda p,r:grounded(p,r,skip=('assertion',)),lambda p,r:grounded(p,r)]).decide(self.packet)
        path=self.directory/(result['key']+'.json');record=json.loads(path.read_text())
        for field,value in (('missing_roles',['observation']),('first_reviewer_id','decision-review-'+'f'*32)):
            with self.subTest(field=field):
                bad=copy.deepcopy(record);bad['reask'][field]=value
                bad['receipt_sha256']=e.digest({k:v for k,v in bad.items() if k not in ('receipt_sha256','cache_hit')})
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):self.engine([]).decide(self.packet)
        path.write_text(json.dumps(record))


class Framing(unittest.TestCase):
    def setUp(self):self.packet=realistic_packet();self.raw=e.encoded(e.independent_envelope(self.packet,'decision-review-'+'c'*32))
    def test_role_is_sent_once(self):
        framed=render.render(ROOT,self.raw,'claude','haiku')
        self.assertNotIn(framed['role'],framed['prompt']);self.assertTrue(framed['prompt'].startswith('Task input:\n'))
    def test_grounding_schema_admits_only_each_roles_ids(self):
        schema=json.loads(render.render(ROOT,self.raw,'claude','haiku')['schema'])['properties']['results']['properties']
        self.assertNotIn('evidence',schema)
        for role in ('requirement','source','assertion','observation'):
            self.assertEqual(schema['grounding']['properties'][role]['items']['enum'],ids(self.packet,role))
        self.assertEqual(schema['grounding']['required'],['requirement','source','assertion','observation'])
    def test_limit_comes_from_routing_with_documented_default_and_ceiling(self):
        self.assertEqual(render.input_limit(None,'claude'),24576)
        self.assertEqual(render.input_limit({'providers':{'claude':{'limits':{'max_input_bytes':65536}}}},'claude'),65536)
        for bad in (1024,131073,'65536',True,None):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'limit_invalid'):
                render.input_limit({'providers':{'claude':{'limits':{'max_input_bytes':bad}}}},'claude')
    def test_configured_limit_is_enforced(self):
        size=render.render(ROOT,self.raw,'claude','haiku')['argument_content_bytes']
        self.assertEqual(render.render(ROOT,self.raw,'claude','haiku',limit=size)['maximum_bytes'],size)
        with self.assertRaisesRegex(ValueError,'framing_too_large'):render.render(ROOT,self.raw,'claude','haiku',limit=size-1)
    def test_reask_envelope_is_bounded_and_validated(self):
        with self.assertRaisesRegex(ValueError,'reask_roles_invalid'):e.independent_envelope(self.packet,'decision-review-'+'c'*32,['assertion','assertion'])
        with self.assertRaisesRegex(ValueError,'reask_roles_invalid'):e.independent_envelope(self.packet,'decision-review-'+'c'*32,['unknown'])
        raw=e.encoded(e.independent_envelope(self.packet,'decision-review-'+'c'*32,['assertion','observation']))
        self.assertIn('missing_roles',render.render(ROOT,raw,'claude','haiku')['prompt'])

if __name__=='__main__':unittest.main()
