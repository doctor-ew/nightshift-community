#!/usr/bin/env python3
"""Synthetic existing-ticket exhaustion, external implementation and recovery."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import shutil
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
RUNTIME_TMP=tempfile.TemporaryDirectory(prefix='nightshift-recovery-runtime-')
RUNTIME=Path(RUNTIME_TMP.name).resolve()
for name in ('scripts','commands','agents','contracts'):
    shutil.copytree(ROOT/name,RUNTIME/name,ignore=shutil.ignore_patterns('__pycache__'))
for name in ('routing.json','nightshift.toml','efficiency.json'):shutil.copy(ROOT/name,RUNTIME/name)
spec=importlib.util.spec_from_file_location('recovery',RUNTIME/'scripts/nightshift-controller-recovery.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name).resolve()/'primary';self.project.mkdir()
        self.env=patch.dict(os.environ,dict(NIGHTSHIFT_ROUTING_FILE=str(ROOT/'routing.json'),PYTHONDONTWRITEBYTECODE='1'));self.env.start();self.addCleanup(self.env.stop)
        self.git('init','-q','--initial-branch=main');self.git('config','user.name','External fixture author');self.git('config','user.email','author@fixture')
        (self.project/'source.txt').write_text('broken\n');self.git('add','.');self.git('commit','-qm','baseline')
        (self.project/'.nightshift.toml').write_text((ROOT/'nightshift.toml').read_text())
        self.base=self.git('rev-parse','HEAD');self.target=self.project.parent/'retained worktree'
        self.git('worktree','add','-qb','ticket',str(self.target))
        self.docs=self.target/'docs/T-1';self.docs.mkdir(parents=True)
        self.docs.joinpath('SPEC.md').write_text('# Contract\nAC-1: source is fixed.\n')
        self.document=dict(version=1,task='T-1',ac_ids=['AC-1'],author=dict(provider='claude',author_id='old-spec-author'),applicability=dict(kind='deterministic'),cases=[dict(id='CASE-one',applicability=dict(kind='deterministic'),ac_ids=['AC-1'])])
        self.docs.joinpath('behavior-scenarios.json').write_text(json.dumps(self.document))
        self.directory=m.p.root(self.project,'T-1');self.directory.mkdir(parents=True)
        common=self.directory.parent.parent
        (common/'worktrees').mkdir();(common/'worktrees/T-1.json').write_text(json.dumps(dict(worktree=str(self.target),base_sha=self.base,status='prepared')))
        settings=dict(ref='jira:T-1',provider='codex',model='fixture-author',policy='standard',auth='subscription',branch='auto',base=self.base,push=False,pr=False)
        m.load('console-actions').save(self.project,'T-1',settings)
        self.state=dict(version=1,task='T-1',worktree=str(self.target),plan=m.p.routes(self.target,settings),request='jira:T-1',decisions=[],architecture=[],completed={},attempts=[],findings=[],history=[],status='blocked',next_action='adversarial')
        # Retained draft, then the old manifest failure and repeated classification repairs.
        product=self.directory/'product-import.json'
        m.p.recovery.atomic(product,dict(version=1,task='T-1',stage='product',status='pass',findings=[],checks=[dict(command='draft schema validation',exit_code=0)],evidence=[dict(path='docs/T-1/SPEC.md',sha256=m.p.sha(self.docs/'SPEC.md'))]))
        self.state['completed']['product']=dict(receipt=str(product),sha256=m.p.sha(product),input_sha256='old')
        self.state['history'].append(dict(stage='product',reason='existing_draft_validated_without_dispatch'))
        for n,reason in [(1,'worker_exit_68'),(2,'worker_exit_143')]:
            log=self.directory/f'adversarial-{n}.log';log.write_text(reason+'\n')
            self.state['attempts'].append(dict(stage='adversarial',status='fail',reason=reason,receipt=str(log.with_suffix('.json'))))
        for n in range(4):
            self.document['repair']=n;self.docs.joinpath('behavior-scenarios.json').write_text(json.dumps(self.document))
            receipt=self.docs/f'classification-review-{n+2}.out.json'
            receipt.write_text(json.dumps(dict(status='SUCCESS',results=dict(decision='repair',findings=[dict(code='COVERAGE',scenario_id='CASE-one',reason='Verify source assertion '+str(n))]))))
        self.state['findings']=[dict(id='interrupted',target='adversarial-2.log',problem='ticket_budget_exhausted')]
        m.p.recovery.atomic(self.directory/'state.json',self.state)
        ledger=m.load('ticket-budget');ledger.update(self.project,'T-1','reserve','parent',max_seconds=600,now=1)
        ledger.update(self.project,'T-1','reserve','child',now=451);ledger.update(self.project,'T-1','finish','child',now=601);ledger.update(self.project,'T-1','finish','parent',now=452)
        self.ledger=ledger.ledger_path(self.project,'T-1');self.budget_before=self.ledger.read_bytes()
        self.assertTrue(ledger.snapshot(self.project,'T-1')['exhausted'])
        # External implementation after exhaustion; the controller has not approved it.
        self.target.joinpath('source.txt').write_text('fixed\n')
        tests=self.target/'evals/unit';tests.mkdir(parents=True)
        (tests/'test-source.sh').write_text('#!/bin/sh\nset -eu\ntest "$(cat source.txt)" = fixed\necho PASS\n')
        report=self.docs/'direct-verification';report.mkdir();(report/'results.json').write_text(json.dumps([dict(test='test-source.sh',exit_code=0)]))
        subprocess.run(['git','-C',str(self.target),'add','.'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(self.target),'commit','-qm','external fix'],check=True,capture_output=True)
        self.before={str(path):path.read_bytes() for path in self.docs.rglob('*') if path.is_file()}
        self.calls=[]

    def git(self,*args):return m.git(self.project,*args)

    def review(self,value,stage,checks,reviewer_id,output,timeout):
        self.calls.append(stage)
        return dict(status='SUCCESS',reason='Synthetic independent evidence review',attempts=1,
                    artifacts=dict(branch='',diff='',**value['reviewer_route']),rules_fired=[],
                    results=dict(binding=m.digest(value),stage=stage,reviewer_id=reviewer_id,decision='approve',findings=[],
                      dispositions=[dict(id=f['id'],resolution='resolved',reason='Current assertion and source resolve the retained finding') for f in value['findings']],
                      cases=[dict(id=c['id'],status='verified',reason='Exact passing assertion covers this case',checks=[dict(id=x['id'],sha256=x['output_sha256']) for x in checks['checks']]) for c in value['cases']],ac_ids=value['ac_ids']))

    def assess(self):return m.assessment(self.project,'T-1')
    def run_recovery(self,operation='authorize',expected=None,runner=None):
        return m.operate(self.project,'T-1',operation,expected or self.assess()['sha256'],'fixture-operator',runner or self.review)

    def test_sequence_readonly_assessment_adoption_remaining_and_manual(self):
        before=self.directory.joinpath('state.json').read_bytes()
        a=self.assess();self.assertEqual(before,self.directory.joinpath('state.json').read_bytes())
        self.assertEqual(a['evidence']['author']['email'],'author@fixture');self.assertEqual(a['evidence']['retained_spec_author']['provider'],'claude')
        self.assertEqual(len(a['evidence']['findings']),5)
        result=self.run_recovery(expected=a['sha256'])
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(self.calls,['adoption','review','drift','qa'])
        state=m.p.snapshot(self.project,'T-1')
        self.assertEqual(set(state['completed']),set(m.p.STAGES));self.assertEqual(state['attempts'],self.state['attempts'])
        self.assertEqual(state['findings'],self.state['findings']);self.assertEqual(self.ledger.read_bytes(),self.budget_before)
        self.assertEqual({str(path):path.read_bytes() for path in self.docs.rglob('*') if path.is_file()},self.before)
        self.assertEqual(self.assess()['sha256'],a['sha256'])
        self.assertEqual(m.p.view(self.project,'T-1')['status'],'pending_manual_acceptance')
        repeated=self.run_recovery(expected=a['sha256']);self.assertEqual(repeated['allowance'],result['allowance']);self.assertEqual(len(self.calls),4)

    def test_changed_inputs_reject_before_any_grant(self):
        a=self.assess();self.target.joinpath('source.txt').write_text('changed\n')
        with self.assertRaisesRegex(ValueError,'committed_source|inputs_changed'):self.run_recovery(expected=a['sha256'])
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'));self.assertEqual(self.ledger.read_bytes(),self.budget_before)

    def test_stale_incomplete_unresolved_identity_and_coverage_fail_closed(self):
        for mode in ('stale','unresolved','incomplete','identity','test_hash'):
            with self.subTest(mode=mode):
                a=self.assess()
                def bad(*args):
                    value=self.review(*args)
                    if mode=='stale':value['results']['binding']='0'*64
                    if mode=='unresolved':value['results']['findings']=['Not addressed']
                    if mode=='incomplete':value['results']['dispositions']=[]
                    if mode=='identity':value['results']['reviewer_id']='original-author'
                    if mode=='test_hash':value['results']['cases'][0]['checks'][0]['sha256']='0'*64
                    return value
                result=self.run_recovery(expected=a['sha256'],runner=bad)
                self.assertEqual(result['status'],'blocked');self.assertNotIn('implement',m.p.snapshot(self.project,'T-1')['completed'])
                self.assertEqual(self.ledger.read_bytes(),self.budget_before)
                # Restore only synthetic state between independent malformed provider cases.
                m.p.recovery.atomic(self.directory/'state.json',self.state)

    def test_restart_reuses_verified_checks_and_adoption_without_new_grant(self):
        a=self.assess();original=m.adopt
        def interrupted(state,session,stage,directory):
            original(state,session,stage,directory)
            if stage=='adoption':raise KeyboardInterrupt('synthetic process interruption after verified receipt')
        with patch.object(m,'adopt',interrupted),self.assertRaises(KeyboardInterrupt):self.run_recovery(expected=a['sha256'])
        prior=m.p.snapshot(self.project,'T-1')['recovery_sessions'][a['sha256']]['allowance'].copy()
        result=self.run_recovery('resume',a['sha256'])
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        self.assertEqual(self.calls,['adoption','review','drift','qa']);self.assertEqual(result['allowance']['deadline_at'],prior['deadline_at'])
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)

    def test_unfinished_reservation_never_relaunches(self):
        a=self.assess()
        def crash(*args):raise KeyboardInterrupt('synthetic process lost')
        with self.assertRaises(KeyboardInterrupt):self.run_recovery(expected=a['sha256'],runner=crash)
        result=self.run_recovery('resume',a['sha256'])
        self.assertEqual(result['status'],'blocked');self.assertEqual(self.calls,[])
        self.assertEqual(result['allowance']['calls_used'],1)

    def test_process_success_or_existing_report_does_not_pass(self):
        a=self.assess()
        def empty(*args):return dict(status='SUCCESS',artifacts=a['evidence']['reviewer_route'],results={})
        result=self.run_recovery(expected=a['sha256'],runner=empty)
        self.assertEqual(result['status'],'blocked');self.assertNotIn('implement',m.p.snapshot(self.project,'T-1')['completed'])

    def test_test_failure_stops_before_provider(self):
        self.target.joinpath('source.txt').write_text('bad\n');subprocess.run(['git','-C',str(self.target),'commit','-qam','broken external fix'],check=True,capture_output=True)
        result=self.run_recovery();self.assertEqual(result['status'],'blocked');self.assertEqual(self.calls,[])

    def test_missing_compact_plan_blocks_before_grant_or_provider(self):
        assessment=self.assess()
        with self.assertRaisesRegex(ValueError,'recovery_decision_preflight'):
            m.operate(self.project,'T-1','authorize',assessment['sha256'],'fixture-operator')
        self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)

    def test_changed_hash_after_adoption_marks_view_stale(self):
        a=self.assess();self.run_recovery(expected=a['sha256'])
        self.target.joinpath('source.txt').write_text('changed later')
        self.assertEqual(m.p.view(self.project,'T-1')['status'],'stale')
        with self.assertRaisesRegex(ValueError,'committed_source|inputs_changed'):self.run_recovery(expected=a['sha256'])

    def test_expired_resume_cannot_add_time(self):
        a=self.assess()
        def crash(*args):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.run_recovery(expected=a['sha256'],runner=crash)
        state=m.p.snapshot(self.project,'T-1');session=state['recovery_sessions'][a['sha256']]
        deadline=session['allowance']['deadline_at']
        with patch.object(m.time,'time',return_value=deadline+1):
            result=self.run_recovery('resume',a['sha256'])
        self.assertEqual(result['status'],'blocked');self.assertEqual(result['allowance']['deadline_at'],deadline)
        self.assertEqual(self.ledger.read_bytes(),self.budget_before)

    def test_duplicate_concurrent_requests_cannot_launch_twice(self):
        import concurrent.futures, threading
        a=self.assess();entered=threading.Event();release=threading.Event()
        def waiting(*args):
            if args[1]=='adoption':entered.set();release.wait(10)
            return self.review(*args)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            first=pool.submit(self.run_recovery,'authorize',a['sha256'],waiting)
            self.assertTrue(entered.wait(10))
            with self.assertRaises(BlockingIOError):self.run_recovery(expected=a['sha256'])
            release.set();self.assertEqual(first.result()['status'],'pending_manual_acceptance')
        self.assertEqual(self.calls,['adoption','review','drift','qa'])

    def test_normal_pipeline_cannot_repeat_implementation_after_recovery(self):
        self.run_recovery()
        before=self.directory.joinpath('state.json').read_bytes()
        controller=m.p.Pipeline(self.target,'T-1',{},runner=lambda *args:self.fail('ordinary stage relaunched'))
        with self.assertRaisesRegex(ValueError,'explicit recovery'):controller.run()
        self.assertEqual(before,self.directory.joinpath('state.json').read_bytes())

    def test_supervisor_bounds_execution_and_parent_loss(self):
        output=self.project.parent/'supervisor.log'
        for parent in (os.getpid(),0):
            with output.open('wb') as log:
                process=subprocess.run([__import__('sys').executable,str(RUNTIME/'scripts/nightshift-recovery-exec.py'),str(parent),'.2',str(output),__import__('sys').executable,'-c','import time;time.sleep(20)'],stdout=log,stderr=log,timeout=5)
            self.assertEqual(process.returncode,124)

    def test_http_assessment_same_controller_and_authorization_requires_token(self):
        import threading, http.client
        module_spec=importlib.util.spec_from_file_location('recovery_http',ROOT/'dashboard/server.py')
        server_module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(server_module)
        server=server_module.DashboardServer(str(self.project),0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            a=self.assess();console=m.load('console-actions');current=console.state(self.project,'T-1')
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
            body=json.dumps(dict(task='T-1',sha256=current['sha256']))
            headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(server.server_port),'X-Nightshift-Token':server.approval_token}
            conn.request('POST','/api/tickets/recovery-assess',body,headers);response=conn.getresponse()
            self.assertEqual(response.status,200);self.assertEqual(json.loads(response.read())['sha256'],a['sha256'])
            headers.pop('X-Nightshift-Token')
            conn.request('POST','/api/tickets/recovery-authorize',json.dumps(dict(task='T-1',sha256=current['sha256'],assessment_sha256=a['sha256'],operator='fixture')),headers)
            response=conn.getresponse();self.assertEqual(response.status,403);response.read();conn.close()
            self.assertNotIn('recovery_sessions',m.p.snapshot(self.project,'T-1'))
        finally:server.shutdown();server.server_close();thread.join()

    def test_cli_and_browser_assessment_same_controller(self):
        a=self.assess();console=m.load('console-actions');settings=console.state(self.project,'T-1')
        actual=console.recovery_action(self.project,'T-1',settings['sha256'],'recovery-assess')
        self.assertEqual(actual,a)
        result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'recover','assess','jira:T-1','--project',str(self.project)],capture_output=True,text=True,env=os.environ,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(json.loads(result.stdout)['sha256'],a['sha256'])

if __name__=='__main__':unittest.main()
