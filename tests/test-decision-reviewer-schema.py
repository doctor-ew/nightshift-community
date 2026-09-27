#!/usr/bin/env python3
"""Packet-bound schema and real dispatcher checks with synthetic CLI only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
render=load('renderer',ROOT/'scripts/nightshift-decision-render.py')
f=load('independent_fixture',Path(__file__).with_name('test-recovery-independent-review.py'))
m=f.m
e=load('engine_fixture',Path(__file__).with_name('test-decision-engine.py'))

class Rendering(unittest.TestCase):
    def test_citation_normalization_preserves_identity_verdict_and_input(self):
        packet=e.packet();reviewer='decision-review-'+'b'*32
        for verdict in ('yes','no','abstain'):
            review=dict(decision=verdict,packet_sha256=e.e.digest(packet),reviewer_id=reviewer,
                        evidence=['  '+r['id']+': explanation  ' for r in packet['evidence']])
            original=copy.deepcopy(review)
            result=e.e.normalize_review_citations(review,packet)
            self.assertEqual(e.e.validate_independent_result(result,packet,reviewer),result)
            self.assertEqual(result['decision'],verdict);self.assertEqual(review,original)
            self.assertEqual(e.e.normalize_review_citations(result,packet),result)
    def test_normalization_cannot_invent_ids_deduplicate_or_rebind(self):
        packet=e.packet();reviewer='decision-review-'+'b'*32
        valid=dict(decision='yes',packet_sha256=e.e.digest(packet),reviewer_id=reviewer,evidence=[r['id'] for r in packet['evidence']])
        variants=[]
        for bad in ('unknown: explanation','source-extra: explanation','SOURCE: explanation',{'id':'source'}):
            value=copy.deepcopy(valid);value['evidence'][0]=bad;variants.append(value)
        value=copy.deepcopy(valid);value['evidence'].append(value['evidence'][0]+': duplicate');variants.append(value)
        value=copy.deepcopy(valid);value['packet_sha256']='0'*64;variants.append(value)
        for value in variants:
            with self.subTest(value=value),self.assertRaises(ValueError):
                e.e.validate_independent_result(e.e.normalize_review_citations(value,packet),packet,reviewer)
        ambiguous=dict(evidence=[dict(id='ref'),dict(id='ref:part')])
        value=dict(evidence=['ref:part: explanation'])
        self.assertEqual(e.e.normalize_review_citations(value,ambiguous),value)

    def envelope(self):
        packet=e.packet()
        return dict(packet=packet,packet_sha256=e.e.digest(packet),reviewer_id='decision-review-'+'a'*32,mode='independent')
    def test_exact_enums_and_actual_argument_byte_count(self):
        envelope=self.envelope();raw=e.e.encoded(envelope)
        result=render.render(ROOT,raw,'claude','configured-synthetic-model')
        schema=json.loads(result['schema']);props=schema['properties']['results']['properties']
        refs=envelope['packet']['evidence'];roles=[x for x in ('requirement','source','assertion','observation') if any(r['role']==x for r in refs)]
        self.assertNotIn('evidence',props);self.assertEqual(props['grounding']['required'],roles)
        for role in roles:
            self.assertEqual(props['grounding']['properties'][role]['items']['enum'],[r['id'] for r in refs if r['role']==role])
            self.assertNotIn('uniqueItems',props['grounding']['properties'][role]);self.assertNotIn('maxItems',props['grounding']['properties'][role])
        self.assertNotIn('minimum',schema['properties']['attempts'])
        canonical=json.loads((ROOT/'contracts/nightshift-decision-reviewer.schema.json').read_text())
        self.assertEqual(canonical['properties']['attempts']['minimum'],1)
        self.assertEqual(props['packet_sha256']['enum'],[envelope['packet_sha256']])
        self.assertEqual(props['reviewer_id']['enum'],[envelope['reviewer_id']])
        self.assertNotIn('allOf',schema);self.assertNotIn('$schema',schema)
        self.assertEqual(result['argument_content_bytes'],sum(len(result[k].encode()) for k in ('prompt','role','schema')))
        self.assertEqual(result['input_envelope_bytes'],len(raw))
        first=props['grounding']['properties'][roles[0]]['items']['enum'];self.assertNotIn(first[0]+': explanation',first)
    def test_malformed_references_and_stale_packet_are_rejected(self):
        original=self.envelope()
        for kind in ('duplicate','empty','stale','wrongtype'):
            value=copy.deepcopy(original)
            if kind=='duplicate':value['packet']['evidence'].append(value['packet']['evidence'][0])
            if kind=='empty':value['packet']['evidence'][0]['id']=''
            if kind=='stale':value['packet_sha256']='0'*64
            if kind=='wrongtype':value['packet']['evidence']={}
            with self.subTest(kind=kind),self.assertRaises(ValueError):render.render(ROOT,e.e.encoded(value),'claude','model')
    def test_envelope_below_limit_can_fail_full_framing_without_truncation(self):
        value=self.envelope();value['packet']['question']='Synthetic bound '+('x'*21000)
        value['packet_sha256']=e.e.digest(value['packet']);raw=e.e.encoded(value)
        self.assertLess(len(raw),render.MAX_BYTES)
        with self.assertRaisesRegex(ValueError,'framing_too_large'):render.render(ROOT,raw,'claude','model')

class Dispatcher(f.IndependentRecovery):
    def run_synthetic(self,mode):
        self.setup_independent();binary=self.project.parent/'bin';binary.mkdir();calls=self.project.parent/'calls.jsonl'
        route=self.assess()['evidence']['reviewer_route'];stub=binary/'claude'
        stub.write_text('#!/usr/bin/env python3\nimport sys,json,os\n'+
          'if sys.argv[1:3]==["auth","status"]:\n print(json.dumps(dict(loggedIn=True,authMethod="claude.ai",apiProvider="firstParty")));sys.exit(0)\n'+
          'assert sys.argv[sys.argv.index("--tools")+1]==""\n'+
          'schema=json.loads(sys.argv[sys.argv.index("--json-schema")+1]);data=json.JSONDecoder().raw_decode(sys.argv[-1].split("Task input:\\n",1)[1])[0]\n'+
          'props=schema["properties"]["results"]["properties"];refs=data["packet"]["evidence"];ids=[r["id"] for r in refs]\n'+
          'roles=[x for x in ("requirement","source","assertion","observation") if any(r["role"]==x for r in refs)]\n'+
          'assert "evidence" not in props and props["grounding"]["required"]==roles\n'+
          'assert all(props["grounding"]["properties"][x]["items"]["enum"]==[r["id"] for r in refs if r["role"]==x] for x in roles)\n'+
          'assert props["packet_sha256"]["enum"]==[data["packet_sha256"]]\nassert props["reviewer_id"]["enum"]==[data["reviewer_id"]]\n'+
          'assert sys.argv[sys.argv.index("--system-prompt")+1] not in sys.argv[-1]\n'+
          'size=sum(len(s.encode()) for s in (sys.argv[-1],sys.argv[sys.argv.index("--system-prompt")+1],sys.argv[sys.argv.index("--json-schema")+1]));assert size<=24576\n'+
          'mode=os.environ["SYNTHETIC_REVIEW_MODE"]\n'+
          'if mode=="reask_recovers":mode="yes" if "missing_roles" in data else "missing_roles"\n'+
          'group={x:[r["id"] for r in refs if r["role"]==x] for x in roles}\n'+
          'if mode=="annotated":group={x:[i+": explanation" for i in v] for x,v in group.items()}\n'+
          'if mode=="selective":group={x:v[:1] for x,v in group.items()}\n'+
          'if mode=="missing_roles":group={x:(v[:1] if x==roles[0] else []) for x,v in group.items()}\n'+
          'if mode=="duplicate":group[roles[1]]=group[roles[1]]+group[roles[0]][:1]\n'+
          'result=dict(decision=mode if mode in ("no","abstain") else "yes",packet_sha256=data["packet_sha256"],reviewer_id=data["reviewer_id"],grounding=group)\n'+
          'with open('+repr(str(calls))+',"a") as out:out.write(json.dumps(dict(size=size,input=data))+"\\n")\n'+
          'print(json.dumps(dict(structured_output=dict(status="SUCCESS",reason="Synthetic explanation belongs here",attempts=1,artifacts=dict(branch="",diff="",**'+repr(route)+'),rules_fired=[],results=result))))\n')
        stub.chmod(0o755)
        with patch.dict(os.environ,{'PATH':str(binary)+os.pathsep+os.environ['PATH'],'SYNTHETIC_REVIEW_MODE':mode}):
            result=self.recover(review=m.compact_review)
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)
        return result,[json.loads(line) for line in calls.read_text().splitlines()]
    def test_exact_ids_pass_actual_packet_bound_dispatch(self):
        result,calls=self.run_synthetic('yes');self.assertEqual(result['status'],'pending_manual_acceptance',result);self.assertEqual(len(calls),4)
        for call in calls:
            value=self.assess()['evidence'];expected=render.render(ROOT,e.e.encoded(call['input']),value['reviewer_route']['provider'],value['reviewer_route']['model'])
            self.assertEqual(call['size'],expected['argument_content_bytes'])
    def test_annotated_ids_pass_without_extra_calls_and_preserve_raw_response(self):
        result,calls=self.run_synthetic('annotated');self.assertEqual(result['status'],'pending_manual_acceptance',result);self.assertEqual(len(calls),4)
        session=next(iter(m.p.snapshot(self.project,'T-1')['recovery_sessions'].values()))
        folder=self.directory/('recovery-'+session['binding'])
        raw=list(folder.glob('decision-*.review.json'))
        self.assertTrue(raw)
        for path in raw:
            self.assertTrue(all(': explanation' in r for v in json.loads(path.read_text())['results']['grounding'].values() for r in v))
    def test_duplicate_ids_remain_locally_rejected(self):
        result,calls=self.run_synthetic('duplicate');self.assertEqual(result['status'],'blocked');self.assertIn('evidence_invalid',result['reason']);self.assertEqual(len(calls),1)
    def test_no_remains_blocked(self):
        result,calls=self.run_synthetic('no');self.assertEqual(result['status'],'blocked');self.assertEqual(len(calls),1)
    def test_abstain_remains_blocked(self):
        result,calls=self.run_synthetic('abstain');self.assertEqual(result['status'],'blocked');self.assertEqual(len(calls),1)
    def test_missing_roles_remain_blocked_after_one_reask(self):
        result,calls=self.run_synthetic('missing_roles');self.assertEqual(result['status'],'blocked');self.assertIn('evidence_incomplete',result['reason']);self.assertEqual(len(calls),2)
        self.assertNotIn('missing_roles',calls[0]['input']);self.assertEqual(calls[1]['input']['missing_roles'],sorted(set(r['role'] for r in calls[1]['input']['packet']['evidence'])-{'requirement'}))
    def test_selective_role_complete_answer_passes(self):
        result,calls=self.run_synthetic('selective');self.assertEqual(result['status'],'pending_manual_acceptance',result);self.assertEqual(len(calls),4)
    def test_reask_recovers_and_retains_first_report(self):
        result,calls=self.run_synthetic('reask_recovers');self.assertEqual(result['status'],'pending_manual_acceptance',result);self.assertEqual(len(calls),8)
        session=next(iter(m.p.snapshot(self.project,'T-1')['recovery_sessions'].values()))
        folder=self.directory/('recovery-'+session['binding'])
        self.assertEqual(len(list(folder.glob('decision-*.reask.review.json'))),4)
        self.assertEqual(len([x for x in folder.glob('decision-*.review.json') if '.reask.' not in x.name]),4)

class AssistedDispatcher(f.f.Decisions):
    def test_actual_assisted_input_bytes_match_reserved_envelope(self):
        super().test_real_dispatcher_with_synthetic_tool_free_reviewer()
        session=next(iter(m.p.snapshot(self.project,'T-1')['recovery_sessions'].values()))
        folder=self.directory/('recovery-'+session['binding'])
        inputs={json.loads(p.read_text())['packet_sha256']:p.read_bytes() for p in folder.glob('*.input.json')}
        reviewed=0
        for key,call in session['decision_calls'].items():
            if call['kind'] not in ('exception','shadow'):continue
            receipt=json.loads((folder/'decisions'/(key.rsplit(':',1)[0]+'.json')).read_text())
            self.assertEqual(call['request_bytes'],len(inputs[receipt['packet_sha256']]))
            reviewed+=1
        self.assertGreater(reviewed,0)

for name in dir(f.f.Decisions):
    if name.startswith('test_') and name not in AssistedDispatcher.__dict__:setattr(AssistedDispatcher,name,None)

for name in dir(f.IndependentRecovery):
    if name.startswith('test_') and name not in Dispatcher.__dict__:setattr(Dispatcher,name,None)
if __name__=='__main__':unittest.main()
