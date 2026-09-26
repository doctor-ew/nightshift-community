#!/usr/bin/env python3
"""Independent compact recovery acceptance regressions; synthetic reviewers only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('independent_fixture',Path(__file__).with_name('test-recovery-independent-review.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class Acceptance(f.IndependentRecovery):
    def ready(self,manual=True):
        if manual:self.add_manual_case()
        self.setup_independent()
        self.result=self.recover()
        self.assertEqual(self.result['status'],'pending_manual_acceptance',self.result)
        self.binding=self.result['sha256']
        self.folder=m.p.root(self.project,'T-1')/('recovery-'+self.binding)
        self.attestation=dict(binding=self.binding,accepted=True)
        if manual:
            case=next(c for c in self.document['cases'] if c['id']=='CASE-manual')
            self.attestation=dict(binding=self.binding,cases=[dict(id=case['id'],case_sha256=m.digest(case),passed=True,observation='Independent fictional interaction checked.',evidence='Synthetic browser receipt reviewed.')])
        self.calls_before=len(self.review_calls)
        self.allowance_before=copy.deepcopy(self.result['allowance'])

    def accept(self,attestation=None,operator='reviewing-operator'):
        return m.operate(self.project,'T-1','accept',self.binding,operator,attestation=self.attestation if attestation is None else attestation)

    def assert_unchanged_spend(self):
        self.assertEqual(len(self.review_calls),self.calls_before)
        session=m.p.snapshot(self.project,'T-1')['recovery_sessions'][self.binding]
        self.assertEqual(session['allowance'],self.allowance_before)
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)
        self.assertEqual(m.p.snapshot(self.project,'T-1')['attempts'],self.state['attempts'])

    def test_manual_accept_view_and_exact_replay(self):
        self.ready();result=self.accept()
        self.assertEqual(result['status'],'complete')
        self.assertEqual(m.p.view(self.project,'T-1')['status'],'complete')
        before=(self.folder/'acceptance.json').read_bytes()
        self.assertEqual(self.accept(),result)
        self.assertEqual((self.folder/'acceptance.json').read_bytes(),before)
        self.assert_unchanged_spend()

    def test_no_manual_accept_view_and_exact_replay(self):
        self.ready(False);result=self.accept()
        self.assertEqual(result['status'],'complete')
        self.assertEqual(m.p.view(self.project,'T-1')['status'],'complete')
        self.assertEqual(self.accept(),result);self.assert_unchanged_spend()

    def test_invalid_attestations_do_not_publish(self):
        self.ready();row=self.attestation['cases'][0]
        values=[dict(binding=self.binding,accepted=True),dict(binding=self.binding,cases=[]),dict(binding=self.binding,cases=[row,row]),dict(binding=self.binding,cases=[dict(row,passed=False)]),dict(binding=self.binding,cases=[dict(row,case_sha256='0'*64)]),dict(binding=self.binding,cases=[dict(row,observation=' ')]),dict(self.attestation,binding='0'*64)]
        for value in values:
            with self.subTest(value=value),self.assertRaises(ValueError):self.accept(value)
        self.assertFalse((self.folder/'acceptance.json').exists());self.assert_unchanged_spend()

    def test_changed_operator_or_observation_conflicts(self):
        self.ready();self.accept()
        with self.assertRaisesRegex(ValueError,'conflict'):self.accept(operator='different-operator')
        changed=copy.deepcopy(self.attestation);changed['cases'][0]['observation']='Changed attestation'
        with self.assertRaisesRegex(ValueError,'conflict'):self.accept(changed)
        self.assert_unchanged_spend()

    def test_stale_source_prevents_accept(self):
        self.ready();(self.target/'source.txt').write_text('Changed fictional source\n')
        with self.assertRaises(ValueError):self.accept()
        self.assertFalse((self.folder/'acceptance.json').exists());self.assert_unchanged_spend()

    def test_gate_receipt_tamper_prevents_accept(self):
        self.ready();(self.folder/'qa.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'receipt_changed'):self.accept()
        self.assertFalse((self.folder/'acceptance.json').exists());self.assert_unchanged_spend()

    def test_legacy_fixture_mode_cannot_accept(self):
        self.ready();state=m.p.snapshot(self.project,'T-1')
        state['recovery_sessions'][self.binding]['decision_mode']='legacy_fixture'
        m.p.recovery.atomic(m.p.root(self.project,'T-1')/'state.json',state)
        with self.assertRaisesRegex(ValueError,'operation_mode_changed'):self.accept()
        self.assertFalse((self.folder/'acceptance.json').exists())

    def test_acceptance_tamper_turns_view_stale(self):
        self.ready();self.accept();(self.folder/'acceptance.json').write_text('{}')
        self.assertEqual(m.p.view(self.project,'T-1')['status'],'stale')
        with self.assertRaises(ValueError):self.accept()
        self.assert_unchanged_spend()

    def test_crash_before_publish_leaves_no_partial_receipt(self):
        self.ready()
        with patch('os.link',side_effect=KeyboardInterrupt()),self.assertRaises(KeyboardInterrupt):self.accept()
        self.assertFalse((self.folder/'acceptance.json').exists())
        self.assertEqual(self.accept()['status'],'complete');self.assert_unchanged_spend()

    def test_crash_after_publish_reuses_identical_receipt(self):
        self.ready();original=m.p.recovery.atomic
        def crash(path,value):
            if Path(path).name=='state.json' and value.get('status')=='complete':raise KeyboardInterrupt()
            return original(path,value)
        with patch.object(m.p.recovery,'atomic',crash),self.assertRaises(KeyboardInterrupt):self.accept()
        retained=(self.folder/'acceptance.json').read_bytes()
        self.assertEqual(m.p.snapshot(self.project,'T-1')['status'],'pending_manual_acceptance')
        self.assertEqual(self.accept()['status'],'complete')
        self.assertEqual((self.folder/'acceptance.json').read_bytes(),retained);self.assert_unchanged_spend()

    def test_receipt_mutation_during_revalidation_cannot_complete(self):
        self.ready();helper=m.load('recovery-acceptance');original=helper.verified;count=0
        def changed(*args,**kwargs):
            nonlocal count
            result=original(*args,**kwargs);count+=1
            if count==2:(self.folder/'acceptance.json').write_text('{}')
            return result
        with patch.object(helper,'verified',changed),self.assertRaisesRegex(ValueError,'acceptance_receipt_changed'):
            helper.accept(m,self.project,'T-1',self.binding,'reviewing-operator',self.attestation)
        self.assertEqual(m.p.snapshot(self.project,'T-1')['status'],'pending_manual_acceptance')
        self.assert_unchanged_spend()

    def test_oversized_receipt_rejected(self):
        self.ready();(self.folder/'acceptance.json').write_bytes(b'x'*2_000_001)
        with self.assertRaisesRegex(ValueError,'evidence_invalid'):self.accept()
        self.assert_unchanged_spend()

    def test_console_forwarding_and_stale_settings(self):
        self.ready();console=m.load('console-actions')
        current=console.state(self.project,'T-1')
        with self.assertRaisesRegex(ValueError,'settings changed'):
            console.recovery_action(self.project,'T-1','0'*64,'recovery-accept',self.binding,'reviewing-operator',self.attestation)
        self.assertFalse((self.folder/'acceptance.json').exists())
        result=console.recovery_action(self.project,'T-1',current['sha256'],'recovery-accept',self.binding,'reviewing-operator',self.attestation)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['acceptance']['attestation']['cases'],self.attestation['cases'])
        self.assert_unchanged_spend()

    def test_actual_http_compact_accept_and_replay(self):
        import http.client
        import threading
        self.ready();console=m.load('console-actions')
        current=console.state(self.project,'T-1')
        spec=importlib.util.spec_from_file_location('acceptance_server',Path(__file__).resolve().parents[1]/'dashboard/server.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        server=module.DashboardServer(str(self.project),0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        body=dict(task='T-1',sha256=current['sha256'],assessment_sha256=self.binding,operator='reviewing-operator',attestation=self.attestation)
        headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(server.server_port),'X-Nightshift-Token':server.approval_token}
        try:
            with patch.object(module,'action_module',return_value=console):
                for _ in range(2):
                    conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=30)
                    conn.request('POST','/api/tickets/recovery-accept',json.dumps(body),headers)
                    response=conn.getresponse();data=response.read();conn.close()
                    self.assertEqual(response.status,200,data)
                    self.assertEqual(json.loads(data)['status'],'complete')
            self.assertEqual(m.p.view(self.project,'T-1')['status'],'complete')
            self.assert_unchanged_spend()
        finally:
            server.shutdown();server.server_close();thread.join(5)

    def test_actual_cli_accept_and_replay(self):
        self.ready();attestation=self.project.parent/'acceptance-input.json'
        attestation.write_text(json.dumps(self.attestation))
        argv=[sys.executable,str(Path(m.__file__)),'accept','T-1','--project',str(self.project),'--expected',self.binding,'--operator','reviewing-operator','--attestation',str(attestation)]
        for _ in range(2):
            result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'complete')
        self.assertEqual(m.p.view(self.project,'T-1')['status'],'complete');self.assert_unchanged_spend()

for name in dir(f.IndependentRecovery):
    if name.startswith('test_') and name not in Acceptance.__dict__:setattr(Acceptance,name,None)
if __name__=='__main__':unittest.main()
