#!/usr/bin/env python3
"""Real Git snapshot, dispatcher, repair and gate-finalization reuse regression."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retry_reuse', ROOT/'scripts/nightshift-retry-budget.py')
retry = importlib.util.module_from_spec(spec); spec.loader.exec_module(retry)

class ReviewReuse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        self.old = Path.cwd(); os.chdir(self.project); self.addCleanup(os.chdir, self.old)
        subprocess.run(['git','init','-q'],check=True)
        subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','base'],check=True)
        self.directory=self.project/'docs/task'; self.directory.mkdir(parents=True)
        self.source=self.project/'service.py'; self.source.write_text('answer = 0\n')
        self.input=self.directory/'request.md'; self.input.write_text('Verify that service.py defines answer = 42.')
        self.route=self.project/'routing.json'; self.route.write_text('{}')
        self.args=['nightshift-code-fact-extractor','--in',str(self.input),'--out',str(self.directory/'review.json'),'--adversarial']
        self.calls=0
        self.real_run=subprocess.run
        self.env=patch.dict(os.environ,NIGHTSHIFT_ROUTING_FILE=str(self.route),NIGHTSHIFT_PROVIDER_POLICY='claude-only');self.env.start();self.addCleanup(self.env.stop)

    def provider(self, command, **kwargs):
        if command[0]!='bash': return self.real_run(command,**kwargs)
        self.calls+=1
        valid=self.source.read_text()=='answer = 42\n'
        report=dict(status='SUCCESS',results=dict(claims=[dict(claim='answer equals 42',status='VERIFIED' if valid else 'CONFLICT',file='service.py',line=1,inspected_files=['service.py'])]))
        Path(command[command.index('--out')+1]).write_text(json.dumps(report))
        return subprocess.CompletedProcess(command,0)

    def dispatch(self, category):
        with patch.object(retry.subprocess,'run',self.provider): self.assertEqual(retry.run_dispatch(self.args),0)
        sidecar=json.loads(Path(self.args[4]+'.retry.json').read_text())
        return retry.account(sidecar['state_path'],sidecar['attempt_id'],category)

    def test_fault_repair_pass_and_free_reuse(self):
        started=time.monotonic()
        first=self.dispatch('substantive')
        with patch.object(retry.subprocess,'run',self.provider), self.assertRaisesRegex(ValueError,'Unchanged evidence'):
            retry.run_dispatch(self.args)
        self.assertEqual(self.calls,1)
        self.source.write_text('answer = 42\n')
        passed=self.dispatch('success')
        self.assertEqual(self.calls,2)
        reused=self.dispatch('success')
        self.assertEqual(self.calls,2)
        self.assertEqual(reused,passed)
        self.assertEqual(first['total'],1)
        self.assertTrue(json.loads(Path(self.args[4]+'.retry.json').read_text())['reused'])
        print(json.dumps(dict(synthetic=True,elapsed_seconds=round(time.monotonic()-started,3),provider_stub_launches=self.calls,external_model_launches=0,repair_attempts=1)))

    def test_concurrent_source_change_does_not_bind_stale_report(self):
        self.source.write_text('answer = 42\n')
        original=self.provider
        def concurrent(command, **kwargs):
            result=original(command, **kwargs)
            if command[0]=='bash': self.source.write_text('answer = 0\n')
            return result
        with patch.object(retry.subprocess,'run',concurrent):
            self.assertEqual(retry.run_dispatch(self.args),0)
        side=json.loads(Path(self.args[4]+'.retry.json').read_text())
        state=retry.account(side['state_path'],side['attempt_id'],'success')
        self.assertNotIn('report_sha256',state['review_requests'][side['attempt_id']])
        self.source.write_text('answer = 42\n')
        self.dispatch('success');self.assertEqual(self.calls,2)

    def test_same_finding_after_changed_evidence_escalates_strategy(self):
        self.dispatch('substantive')
        self.source.write_text('answer = 1\n')
        state=self.dispatch('substantive')
        self.assertEqual(state['next_action'],'change_repair_strategy')
        self.assertEqual(len(state['recurring_source_findings']),1)
        receipt=json.loads((self.directory/'review-convergence.json').read_text())
        self.assertFalse(receipt['gate_approval'])
        self.assertEqual(len(receipt['findings'][0]['attempts']),2)
        portal=self.real_run(['bash',str(ROOT/'scripts/nightshift-dashboard.sh'),'--project',str(self.project),'--json'],capture_output=True,text=True,check=True)
        self.assertIn('review-convergence',portal.stdout)
        self.assertIn('same source conflict',portal.stdout)
        self.source.write_text('answer = 42\n')
        resolved=self.dispatch('success')
        self.assertEqual(resolved['recurring_source_findings'],[])
        self.assertEqual(len(resolved['resolved_source_findings']),1)
        self.assertEqual(json.loads((self.directory/'review-convergence.json').read_text())['status'],'skipped')

    def test_dirty_dependency_invalidates_without_commit(self):
        self.source.write_text('answer = 42\n'); self.dispatch('success')
        self.source.write_text('answer = 0\n'); self.dispatch('substantive')
        self.assertEqual(self.calls,2)

    def test_policy_and_retained_report_changes_prevent_reuse(self):
        self.source.write_text('answer = 42\n'); self.dispatch('success')
        side=json.loads(Path(self.args[4]+'.retry.json').read_text())
        Path(side['result_path']).write_text('{}')
        self.dispatch('success'); self.assertEqual(self.calls,2)
        self.route.write_text('{"changed":true}')
        self.dispatch('success'); self.assertEqual(self.calls,3)

if __name__=='__main__': unittest.main()
