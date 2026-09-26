#!/usr/bin/env python3
"""Independent cancellation/reconciliation regression tests in disposable repositories."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reconciliation_review_fixture',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m
r=m.load('operation-reconciliation')

class Reconciliation(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-reconciliation-review-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();f.fixture(self.root);self.worker=f.Worker();self.c=m.Operations(self.root,'demo',self.worker)
        a=self.c.assess('groom-spec');self.g=self.c.authorize(['groom-spec'],a['binding'],'synthetic','grant')
    def cancel(self):
        other=m.Operations(self.root,'demo',self.worker)
        return r.cancel(other,self.g['id'],r.identity(other,self.g),'synthetic','cancel')
    def reconcile(self,resolution='finalize'):
        self.c.reload();attempt=self.c.state['attempts'][0]
        return r.reconcile(self.c,attempt['request'],r.assessment(self.c,attempt)['binding'],'synthetic',resolution)
    def pending(self,cancel=True):
        def interrupted(*args):
            self.worker(*args)
            if cancel:self.cancel()
            raise KeyboardInterrupt('synthetic interrupted worker')
        self.c.worker=interrupted
        with self.assertRaises(KeyboardInterrupt):self.c.execute(self.g['id'],'groom-spec','run')
        self.c.reload()
    def checkpoint(self):
        with patch.object(self.c,'finalize',side_effect=KeyboardInterrupt('synthetic checkpoint crash')):
            with self.assertRaises(KeyboardInterrupt):self.c.execute(self.g['id'],'groom-spec','run')
        self.c.reload();self.assertEqual(self.c.state['attempts'][0]['status'],'checkpoint')
    def test_cancel_before_dispatch_is_durable_and_duplicate_safe(self):
        first=self.cancel();self.assertEqual(first,self.cancel())
        self.c=m.Operations(self.root,'demo',self.worker)
        with self.assertRaisesRegex(ValueError,'cancel'):self.c.execute(self.g['id'],'groom-spec','run')
        self.assertFalse(self.worker.calls);self.assertFalse(self.c.state['calls'])
    def test_wrong_operator_and_stale_authority_do_not_write_intent(self):
        for operator,binding in [('other',r.identity(self.c,self.g)),('synthetic','0'*64)]:
            with self.subTest(operator=operator),self.assertRaises(ValueError):r.cancel(self.c,self.g['id'],binding,operator,'bad-cancel')
        self.assertIsNone(r.intent(self.c,self.g['id']))
    def test_cancelled_unknown_preserves_full_reservation_and_blocks_finalization(self):
        self.pending();before=copy.deepcopy(self.c.state['calls'])
        self.assertEqual(self.c.usage(self.g['id'])['reserved_unknown_seconds'],next(iter(before.values()))['reserved_seconds'])
        with self.assertRaisesRegex(ValueError,'no_controller_completion_receipt'):self.reconcile()
        result=self.reconcile('preserve');self.assertTrue(result['result']['unknown_usage_preserved'])
        self.assertEqual(self.c.state['calls'],before);self.assertEqual(len(self.worker.calls),1)
        self.assertNotIn('groom-spec',self.c.state['results'])
    def test_controller_interruption_without_cancel_retains_unknown_usage(self):
        self.pending(cancel=False)
        self.assertGreater(self.c.usage(self.g['id'])['reserved_unknown_seconds'],0)
        self.cancel();self.reconcile('preserve')
        self.assertGreater(self.c.usage(self.g['id'])['reserved_unknown_seconds'],0)
    def test_explicit_checkpoint_finalize_ignores_cancel_only_for_that_receipt(self):
        self.checkpoint();self.cancel();calls=list(self.worker.calls)
        attempt=copy.deepcopy(self.c.state['attempts'][0]);binding=r.assessment(self.c,attempt)['binding']
        result=r.reconcile(self.c,'run',binding,'synthetic','finalize')
        self.assertEqual(result['result']['status'],'passed');self.assertEqual(result['provider_calls'],0)
        self.assertEqual(result,r.reconcile(self.c,'run',binding,'synthetic','finalize'))
        self.assertEqual(self.worker.calls,calls)
        with self.assertRaisesRegex(ValueError,'cancel'):self.c.execute(self.g['id'],'groom-spec','another-run')
    def test_changed_source_rejects_checkpoint_without_overwrite(self):
        self.checkpoint();self.cancel();path=self.root/'app.py';path.write_text('Operator edit\n')
        with self.assertRaisesRegex(ValueError,'checkpoint_inputs_changed'):self.reconcile()
        self.assertEqual(path.read_text(),'Operator edit\n');self.assertEqual(len(self.worker.calls),1)
    def test_changed_checkpoint_hash_rejects_stale_reconciliation_binding(self):
        self.checkpoint();self.cancel();attempt=self.c.state['attempts'][0];binding=r.assessment(self.c,attempt)['binding']
        path=self.c.directory/attempt['checkpoint'];path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'stale_reconciliation'):r.reconcile(self.c,'run',binding,'synthetic','finalize')
        self.assertNotIn('groom-spec',self.c.state['results'])
    def test_completion_receipt_recovery_never_redispatches(self):
        with patch.object(self.c,'finish',side_effect=KeyboardInterrupt('synthetic completion crash')):
            with self.assertRaises(KeyboardInterrupt):self.c.execute(self.g['id'],'groom-spec','run')
        self.cancel();result=self.reconcile()
        self.assertEqual(result['result']['status'],'passed');self.assertEqual(result['provider_calls'],0)
        self.assertEqual(len(self.worker.calls),1)

class SemanticReconciliation(unittest.TestCase):
    def test_missing_semantic_checkpoint_never_dispatches_evaluator(self):
        spec=importlib.util.spec_from_file_location('reconciliation_semantic_fixture',ROOT/'tests/test-operation-decisions.py')
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
        case=fixture.Decisions();case.setUp();self.addCleanup(case.tearDown)
        c=case.c;a=c.assess('review');g=c.authorize(['review'],a['binding'],'synthetic','semantic-review')
        with patch.object(c,'finish',side_effect=KeyboardInterrupt('synthetic crash before semantic evaluation')):
            with self.assertRaises(KeyboardInterrupt):c.execute(g['id'],'review','semantic-review-run')
        calls=list(case.w.calls)
        r.cancel(c,g['id'],r.identity(c,g),'synthetic','cancel-semantic')
        attempt=c.state['attempts'][-1]
        with self.assertRaisesRegex(ValueError,'semantic_reconciliation_requires_retained_complete_checkpoint'):
            r.reconcile(c,attempt['request'],r.assessment(c,attempt)['binding'],'synthetic','finalize')
        self.assertEqual(case.w.calls,calls);self.assertFalse(case.calls)
        self.assertNotIn('review',c.state['results'])

class RunnerOwnership(unittest.TestCase):
    def test_ownership_receipt_write_failure_reaps_started_supervisor(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-runner-receipt-review-');self.addCleanup(temporary.cleanup)
        root=Path(temporary.name).resolve();runner=m.load('controller-recovery');children=[];popen=subprocess.Popen
        def track(*args,**kwargs):
            child=popen(*args,**kwargs);children.append(child);return child
        def cleanup():
            for child in children:
                if child.poll() is None:child.terminate();child.wait(timeout=5)
        self.addCleanup(cleanup)
        with patch.object(runner.subprocess,'Popen',side_effect=track),patch.object(runner.p.recovery,'atomic',side_effect=OSError('synthetic receipt write failure')):
            with self.assertRaisesRegex(OSError,'receipt write failure'):
                runner.bounded([sys.executable,'-c','import time;time.sleep(30)'],root,dict(os.environ),5,root/'output.log',ownership=root/'ownership.json')
        self.assertEqual(len(children),1)
        self.assertIsNotNone(children[0].poll(),'owned supervisor survived failed receipt write')
    def test_term_resistant_owned_child_stops_and_unrelated_process_survives(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-runner-cancel-review-');self.addCleanup(temporary.cleanup)
        root=Path(temporary.name).resolve();sentinel=root/'cancel.json';pidfile=root/'owned.pid';output=root/'output.log';owner=root/'owner.json'
        unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        def cleanup():
            unrelated.terminate();unrelated.wait(timeout=5)
            if pidfile.exists():
                pid=int(pidfile.read_text())
                command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
                if str(pidfile) in command:
                    try:os.kill(pid,signal.SIGKILL)
                    except ProcessLookupError:pass
        self.addCleanup(cleanup)
        code='import os,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path('+repr(str(pidfile))+').write_text(str(os.getpid()));time.sleep(30)'
        result=[]
        def run():
            try:m.load('controller-recovery').bounded([sys.executable,'-c',code],root,dict(os.environ),10,output,cancellation=sentinel,ownership=owner)
            except BaseException as error:result.append(error)
        thread=threading.Thread(target=run);thread.start()
        deadline=time.monotonic()+5
        while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.02)
        self.assertTrue(pidfile.exists());sentinel.write_text('{}');thread.join(7)
        self.assertFalse(thread.is_alive());self.assertTrue(result);self.assertIsNone(unrelated.poll())
        self.assertIsInstance(result[0],ValueError);self.assertIn('operation_cancelled',str(result[0]))
        pid=int(pidfile.read_text());probe=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True)
        self.assertFalse(probe.stdout.strip() and not probe.stdout.strip().startswith('Z'),'owned TERM-resistant child survived cancellation')
        self.assertEqual(json.loads(owner.read_text())['status'],'stopped')

if __name__=='__main__':unittest.main()
