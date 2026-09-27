#!/usr/bin/env python3
"""Cross-session answer reuse and the timing-normalized observation view. Synthetic only."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
e=load('reuse_engine',ROOT/'scripts/nightshift-decision-engine.py')
adapter=load('reuse_adapter',ROOT/'scripts/nightshift-recovery-decisions.py')
fixture=load('reuse_fixture',Path(__file__).with_name('test-reviewer-grounding.py'))
A,B,C='a'*64,'b'*64,'c'*64


class Reuse(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.packet=fixture.realistic_packet();self.calls=[]
        self.settings=dict(semantic_mode='independent',provider='claude',model='fixture',timeout_seconds=120,max_bytes=e.MAX_BYTES)
    def engine(self,authority,verdict='yes',prior=(),settings=None):
        def review(packet,reviewer_id,missing=None):
            self.calls.append((authority,reviewer_id))
            return e.review_from_grounding(fixture.grounded(packet,reviewer_id,decision=verdict),packet)
        return e.IndependentEngine(self.root/('recovery-'+authority)/'decisions',authority,settings or self.settings,
                                   lambda kind,rid,size:rid,lambda token,outcome:None,review,prior=prior)
    def test_identical_packet_reuses_earlier_yes_without_a_call(self):
        first=self.engine(A).decide(self.packet);self.assertEqual(len(self.calls),1)
        second=self.engine(B,prior=[A]).decide(self.packet)
        self.assertEqual((second['status'],second['decision'],second['reason'],second['calls']),('complete','yes','decision_reused',[]))
        self.assertEqual(second['reused_from'],dict(authority=A,key=first['key'],receipt_sha256=first['receipt_sha256']))
        self.assertEqual(len(self.calls),1)
        cached=self.engine(B,prior=[A]).decide(self.packet);self.assertTrue(cached['cache_hit']);self.assertEqual(len(self.calls),1)
        e.validate_independent_receipt(second,self.packet,self.settings,B,self.root/('recovery-'+B)/'decisions')
    def test_earlier_no_is_reused_so_identical_evidence_cannot_be_re_asked(self):
        self.engine(A,verdict='no').decide(self.packet)
        second=self.engine(B,verdict='yes',prior=[A]).decide(self.packet)
        self.assertEqual((second['decision'],second['status']),('no','complete'));self.assertEqual(len(self.calls),1)
    def test_abstention_is_never_reused(self):
        self.engine(A,verdict='abstain').decide(self.packet)
        second=self.engine(B,prior=[A]).decide(self.packet)
        self.assertEqual(second['decision'],'yes');self.assertNotIn('reused_from',second);self.assertEqual(len(self.calls),2)
    def test_changed_packet_or_settings_do_not_reuse(self):
        self.engine(A).decide(self.packet)
        changed=json.loads(json.dumps(self.packet));changed['question']+=' (edited)'
        self.assertNotIn('reused_from',self.engine(B,prior=[A]).decide(changed))
        other=dict(self.settings,model='other-model')
        self.assertNotIn('reused_from',self.engine(C,prior=[A],settings=other).decide(self.packet))
        self.assertEqual(len(self.calls),3)
    def test_session_not_listed_as_prior_is_not_reused(self):
        self.engine(A).decide(self.packet)
        self.assertNotIn('reused_from',self.engine(B,prior=[]).decide(self.packet));self.assertEqual(len(self.calls),2)
    def test_tampered_or_missing_origin_invalidates_the_reused_receipt(self):
        first=self.engine(A).decide(self.packet);second=self.engine(B,prior=[A]).decide(self.packet)
        origin=self.root/('recovery-'+A)/'decisions'/(first['key']+'.review.json')
        saved=origin.read_text();origin.write_text('{}')
        with self.assertRaises(ValueError):self.engine(B,prior=[A]).decide(self.packet)
        origin.write_text(saved)
        (self.root/('recovery-'+A)/'decisions'/(first['key']+'.json')).unlink()
        with self.assertRaisesRegex(ValueError,'origin_missing'):self.engine(B,prior=[A]).decide(self.packet)
    def test_reuse_is_not_chained(self):
        self.engine(A).decide(self.packet);self.engine(B,prior=[A]).decide(self.packet)
        third=self.engine(C,prior=[B]).decide(self.packet)
        self.assertNotIn('reused_from',third);self.assertEqual(len(self.calls),2)
    def test_forged_reuse_record_is_rejected(self):
        first=self.engine(A).decide(self.packet);second=self.engine(B,prior=[A]).decide(self.packet)
        path=self.root/('recovery-'+B)/'decisions'/(second['key']+'.json')
        for field,value in (('decision','no'),('calls',[{'kind':'independent','status':'complete'}]),('reused_from',dict(second['reused_from'],authority=B))):
            with self.subTest(field=field):
                bad=dict(second,**{field:value});bad['receipt_sha256']=e.digest({k:v for k,v in bad.items() if k not in ('receipt_sha256','cache_hit')})
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):self.engine(B,prior=[A]).decide(self.packet)
        path.write_text(json.dumps(second))


class ObservationView(unittest.TestCase):
    def test_only_timing_tokens_change_and_lines_are_preserved(self):
        raw='\n'.join(['✔ exact prompt (0.390209ms)','✔ build check (28.76975ms)','ℹ duration_ms 267.472875','  duration_ms: 0.73',
                       'Ran 11 tests in 28.298s','=== 5 passed in 0.12s ===','{"status":"passed","elapsed_ms":1066,"bytes":1234}',
                       'plain (important)','count (3 items)','sum 42ms total','✖ failing test (1.5ms)'])
        view=adapter.observation_view(raw)
        self.assertEqual(len(view.split('\n')),len(raw.split('\n')))
        self.assertEqual(view.split('\n'),['✔ exact prompt (<duration>)','✔ build check (<duration>)','ℹ duration_ms <duration>','  duration_ms: <duration>',
                         'Ran 11 tests in <duration>','=== 5 passed in <duration> ===','{"status":"passed","elapsed_ms":"<duration>","bytes":1234}',
                         'plain (important)','count (3 items)','sum 42ms total','✖ failing test (<duration>)'])
        self.assertEqual(adapter.observation_view(view),view)
    def test_asserted_values_in_titles_and_thresholds_are_kept(self):
        kept=['ok 1 - response completes under threshold (200ms)','completes under threshold (200ms)','{"duration":30,"timeout_ms_limit":5}',
              '✔ waits at least 5 seconds (5s)']
        view=adapter.observation_view('\n'.join(kept)).split('\n')
        self.assertEqual(view[1:3],kept[1:3])
        # On runner result lines only the final, appended measurement is replaced.
        self.assertEqual(adapter.observation_view('✔ waits at least 5 seconds (5s) (5003.2ms)'),'✔ waits at least 5 seconds (5s) (<duration>)')
        self.assertEqual(adapter.observation_view(kept[0]),kept[0])  # TAP lines are never edited
    def test_runs_differing_only_in_timing_produce_one_view(self):
        a='✔ t (0.73ms)\nℹ duration_ms 267.4\n{"elapsed_ms":1066}';b='✔ t (0.51ms)\nℹ duration_ms 238.9\n{"elapsed_ms":968}'
        self.assertEqual(adapter.observation_view(a),adapter.observation_view(b))
        self.assertNotEqual(adapter.observation_view(a),adapter.observation_view(a.replace('✔','✖')))


class Controller(unittest.TestCase):
    def test_only_sessions_with_identical_reviewer_framing_are_reusable(self):
        c=load('reuse_controller',ROOT/'scripts/nightshift-controller-recovery.py')
        assets={n:'h-'+n for n in c.REVIEWER_ASSETS}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            state=dict(recovery_sessions={A:dict(evidence=dict(assets=dict(assets))),B:dict(evidence=dict(assets=dict(assets,**{c.REVIEWER_ASSETS[0]:'changed'}))),
                                          C:dict(evidence=dict(assets=dict(assets)))})
            (root/'state.json').write_text(json.dumps(state))
            self.assertEqual(c.reusable_sessions(dict(assets=assets),dict(binding=C),root),[A])
        self.assertEqual(c.MAX_RECOVERY_SESSIONS,4)

if __name__=='__main__':unittest.main()
