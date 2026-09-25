#!/usr/bin/env python3
"""Synthetic providers only. No installed runtime, real ticket or model calls."""
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('operations',ROOT/'scripts/nightshift-operations.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def fixture(root):
    subprocess.run(['git','init','-q',str(root)],check=True)
    subprocess.run(['git','-C',str(root),'config','user.email','synthetic@example.invalid'],check=True)
    subprocess.run(['git','-C',str(root),'config','user.name','Synthetic'],check=True)
    (root/'docs/demo').mkdir(parents=True)
    for name,text in {'request.md':'Return two.\n','spec.md':'Return two.\n','scenarios.json':'{"version":1,"cases":[{"id":"two","requirement":"Return two","manual":false}]}\n','rules.md':'Keep functions simple.\n','architecture.md':'No accepted decisions apply.\n','app.py':'def answer():\n    return 2\n','test_app.py':'import unittest\nfrom app import answer\nclass Test(unittest.TestCase):\n    def test_answer(self): self.assertEqual(answer(),2)\nunittest.main()\n','.gitignore':'__pycache__/\n'}.items():
        (root/name).write_text(text)
    p=dict(version=1,inputs=dict(request='request.md',spec='spec.md',scenarios='scenarios.json',rules='rules.md',architecture='architecture.md'),scope=['app.py'],checks=[dict(id='unit',argv=['python3','test_app.py'])],environment={},reviewer_policy=dict(version=1,require_different_provider=True,semantic_plan=None),limits={op:dict(calls=4,seconds=30,wall_seconds=30) for op in m.OPS},aggregate=dict(calls=20,seconds=180,wall_seconds=180),publication=None)
    (root/'docs/demo/operations.json').write_text(json.dumps(p))
    subprocess.run(['git','-C',str(root),'add','.'],check=True)
    subprocess.run(['git','-C',str(root),'commit','-qm','Synthetic baseline'],check=True)
    return p


class Worker:
    def __init__(self):self.calls=[];self.fail=False;self.patch='';self.sleep=0
    def __call__(self,operation,packet,route,output,seconds):
        self.calls.append((operation,len(json.dumps(packet,sort_keys=True).encode())))
        time.sleep(self.sleep)
        return dict(status='FAIL' if self.fail else 'SUCCESS',reason='concrete classification finding' if self.fail else '',attempts=1,
            artifacts=dict(branch='',diff=self.patch,provider=route['provider'],model=route['model']),rules_fired=[],
            results=dict(binding=packet['binding'],decision='repair' if self.fail else 'approve',findings=['classification unclear'] if self.fail else [],resolved=packet['findings'],coverage=['scope','rules','architecture','scenarios','correctness','test_oracles',*[c['id'] for c in packet.get('cases',[])]]))


class Operations(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='nightshift-operations-fixture-')
        self.root=Path(self.temp.name);self.plan=fixture(self.root);self.worker=Worker();self.c=m.Operations(self.root,'demo',self.worker)
        self.n=0
    def tearDown(self):self.temp.cleanup()
    def grant(self,ops,attestation=None):
        self.n+=1;key='r'+str(self.n);a=self.c.assess(ops[0]);g=self.c.authorize(ops,a['binding'],'synthetic-operator',key,attestation);return g['id']
    def run_op(self,op,attestation=None):
        key=self.grant([op],attestation);return self.c.execute(key,op,key+'.'+op)
    def groom(self):
        grant=self.grant(m.RECIPES['groom']);r=self.c.chain(grant);self.assertTrue(all(x['status']=='passed' for x in r['results']),r);return grant
    def full(self):
        g=self.grant(m.RECIPES['factory']);r=self.c.chain(g);self.assertEqual(r['view']['status'],'pending_manual_acceptance',r);return g
    def modify_plan(self):
        (self.root/'docs/demo/operations.json').write_text(json.dumps(self.plan))
    def test_checkpoint_rejects_changed_dependencies(self):
        def stop(a):raise KeyboardInterrupt()
        self.c.finalize=stop;g=self.grant(['groom-spec'])
        with self.assertRaises(KeyboardInterrupt):self.c.execute(g,'groom-spec','checkpoint-stale')
        (self.root/'rules.md').write_text('changed rules')
        c=m.Operations(self.root,'demo',self.worker)
        with self.assertRaisesRegex(ValueError,'checkpoint_inputs_changed'):c.execute(g,'groom-spec','checkpoint-stale')
        self.assertEqual(len(self.worker.calls),1)
    def test_provider_overrun_charged_but_never_passes(self):
        self.plan['limits']['groom-spec']['seconds']=.001;self.modify_plan();self.worker.sleep=.01
        r=self.run_op('groom-spec');self.assertEqual(r['reason'],'provider_execution_exceeded_allowance')
        self.assertGreater(self.c.usage(r['grant'])['seconds'],.001)
    def test_findings_enable_targeted_repair(self):
        self.full();(self.root/'app.py').write_text('def answer(): return 2 # changed\n')
        a=self.c.assess('adopt');self.run_op('adopt',dict(binding=a['binding'],identity='external',provider='human'));self.run_op('verify')
        self.worker.fail=True;self.assertEqual(self.run_op('review')['status'],'failed');self.worker.fail=False
        self.assertEqual(self.c.assess('implement')['status'],'ready')
        import difflib
        before=(self.root/'app.py').read_text();after='def answer():\n    return 2 # repaired\n'
        self.worker.patch=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='a/app.py',tofile='b/app.py'))
        self.assertEqual(self.run_op('implement')['status'],'passed')
        self.worker.patch=''
        self.assertEqual(self.c.assess('implement')['status'],'current')
        self.assertEqual(self.run_op('verify')['status'],'passed')
        self.assertEqual(self.run_op('review')['status'],'passed')
    def test_each_dependency_invalidates_precisely(self):
        self.full()
        self.plan['reviewer_policy']['version']=1;self.plan['reviewer_policy']['require_different_provider']=False;self.modify_plan()
        self.assertEqual(self.c.assess('verify')['status'],'current');self.assertEqual(self.c.assess('groom')['status'],'current');self.assertNotEqual(self.c.assess('review')['status'],'current')
        for key in ('spec','scenarios','rules','architecture'):
            path=self.root/self.plan['inputs'][key];old=path.read_bytes();path.write_bytes(old+b'\n')
            self.assertNotEqual(self.c.assess('groom')['status'],'current',key)
            self.assertNotEqual(self.c.assess('verify')['status'],'current',key);path.write_bytes(old)
    def test_concurrent_requests_and_worker_recursion(self):
        g=self.grant(['groom-spec']);self.worker.sleep=.15
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            future=pool.submit(self.c.execute,g,'groom-spec','concurrent')
            time.sleep(.04)
            other=m.Operations(self.root,'demo',self.worker)
            with self.assertRaisesRegex(ValueError,'operation_busy'):other.execute(g,'groom-spec','other')
            self.assertEqual(future.result()['status'],'passed')
        from unittest.mock import patch
        with patch.dict(os.environ,{'NIGHTSHIFT_ROLE_CHILD':'1'}):
            with self.assertRaisesRegex(ValueError,'worker_cannot'):self.run_op('groom-rules')
    def test_missing_tests_do_not_block_groom_and_oversized_context_no_grant(self):
        (self.root/'test_app.py').unlink()
        self.assertEqual(self.c.assess('groom-spec')['status'],'ready')
        (self.root/'request.md').write_text('x'*70000)
        self.assertEqual(self.c.assess('groom-spec')['status'],'blocked')
        with self.assertRaisesRegex(ValueError,'too_large'):self.grant(['groom-spec'])
        self.assertFalse(self.c.state['authorizations'])
    def test_actual_patch_implementation_then_verification(self):
        (self.root/'app.py').write_text('def answer():\n    return 1\n')
        self.groom()
        self.worker.patch='diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n def answer():\n-    return 1\n+    return 2\n'
        self.assertEqual(self.run_op('implement')['status'],'passed')
        self.worker.patch=''
        self.assertIn('return 2',(self.root/'app.py').read_text());self.assertEqual(self.run_op('verify')['status'],'passed');self.assertEqual(self.run_op('review')['status'],'passed')
        self.assertEqual(sum(op=='implement' for op,b in self.worker.calls),1)
    def test_parallel_calls_charge_sum_not_idle_or_wall(self):
        g=self.grant(['groom-spec'])
        with self.c.lease():
            def run(index,duration):
                key='parallel-'+str(index);self.c.reserve(g,'groom-spec',key,10,seconds=.2)
                started=time.monotonic();time.sleep(duration);elapsed=time.monotonic()-started;self.c.finish(key,elapsed)
                return elapsed
            started=time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                one=pool.submit(run,1,.04);two=pool.submit(run,2,.06);total=one.result()+two.result()
            wall=time.monotonic()-started
            self.assertAlmostEqual(self.c.usage(g)['seconds'],total);self.assertEqual(self.c.usage(g)['calls'],2);self.assertGreater(total,wall)
    def test_publish_explicit_local_remote_and_replay(self):
        with tempfile.TemporaryDirectory() as remote:
            subprocess.run(['git','init','--bare','-q',remote],check=True)
            subprocess.run(['git','-C',str(self.root),'remote','add','synthetic',remote],check=True)
            subprocess.run(['git','-C',str(self.root),'checkout','-qb','synthetic-publication'],check=True)
            self.plan['publication']=dict(remote='synthetic',branch='synthetic-publication');self.modify_plan()
            subprocess.run(['git','-C',str(self.root),'add','.'],check=True);subprocess.run(['git','-C',str(self.root),'commit','-qm','Publication fixture'],check=True)
            self.full();a=self.c.assess('accept');self.run_op('accept',dict(binding=a['binding'],accepted=True))
            a=self.c.assess('publish');self.assertEqual(a['status'],'ready',a)
            with self.assertRaisesRegex(ValueError,'attestation'):self.run_op('publish')
            g=self.grant(['publish'],dict(binding=a['binding'],publication=self.plan['publication']))
            r=self.c.execute(g,'publish','publish');self.assertEqual(r['status'],'passed',r)
            head=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],text=True).strip()
            self.assertEqual(subprocess.check_output(['git','--git-dir',remote,'rev-parse','refs/heads/synthetic-publication'],text=True).strip(),head)
            self.assertEqual(self.c.execute(g,'publish','publish')['status'],'passed')
    def test_classification_exhaustion_can_adopt_external_without_implementation(self):
        self.run_op('groom-rules')
        for i in range(3):
            (self.root/'spec.md').write_text('Return two. Clarification '+str(i)+'\n')
            self.worker.fail=False;self.run_op('groom-spec');self.worker.fail=True
            self.assertEqual(self.run_op('groom-adversarial')['status'],'failed')
        draft=(self.root/'spec.md').read_bytes();self.worker.fail=False
        (self.root/'app.py').write_text('def answer(): return 2 # externally implemented\n')
        a=self.c.assess('adopt');g=self.grant(m.RECIPES['external'],dict(binding=a['binding'],identity='external-human',provider='human'))
        result=self.c.chain(g);self.assertEqual(result['view']['status'],'pending_manual_acceptance',result)
        self.assertEqual((self.root/'spec.md').read_bytes(),draft)
        self.assertEqual(sum(op=='implement' for op,b in self.worker.calls),0)
        self.assertIn('repair_limit_exhausted',self.c.assess('groom-adversarial')['blockers'])
    def test_accepted_architecture_is_checked_by_verifier(self):
        m.load('architecture').accept(self.root,dict(id='no-forbidden',decision='Do not use forbidden marker',operator='synthetic',upstream='https://example.invalid/issues/1',scope=['app.py'],reference='app.py',constraints=[dict(kind='forbidden_literal',value='FORBIDDEN')]))
        self.groom();self.run_op('implement')
        (self.root/'app.py').write_text('def answer(): return 2 # FORBIDDEN\n')
        result=self.run_op('verify');self.assertEqual(result['reason'],'architecture_constraints_failed')
    def test_preflight_is_read_only_and_no_implicit_upstream(self):
        before=list(self.root.rglob('*'));a=self.c.assess('implement');self.assertEqual(a['status'],'blocked');self.assertEqual(before,list(self.root.rglob('*')));self.assertFalse(self.worker.calls)
        with self.assertRaisesRegex(ValueError,'missing_current_results'):self.grant(['implement'])
    def test_independent_and_chain_equivalence(self):
        for op in m.RECIPES['factory']:self.assertEqual(self.run_op(op)['status'],'passed')
        outcome=[(r['operation'],r['status']) for r in self.c.view()['operations']]
        calls=list(self.worker.calls)
        with tempfile.TemporaryDirectory() as other:
            project=Path(other);fixture(project);w=Worker();c=m.Operations(project,'demo',w)
            c.authorize(m.RECIPES['factory'],c.assess('groom-spec')['binding'],'synthetic-operator','recipe');r=c.chain('recipe')
            self.assertEqual(outcome,[(x['operation'],x['status']) for x in r['view']['operations']])
            self.assertEqual([o for o,b in calls],[o for o,b in w.calls])
            for op in m.RECIPES['factory']:
                def normalized(value,controller):
                    aliases={r['digest']:name for name,r in controller.state['results'].items()}
                    if isinstance(value,dict):return {k:normalized(v,controller) for k,v in value.items() if k not in ('worktree','repository')}
                    if isinstance(value,list):return [normalized(v,controller) for v in value]
                    return aliases.get(value,value) if isinstance(value,str) else value
                self.assertEqual(normalized(self.c.state['results'][op]['dependencies'],self.c),normalized(c.state['results'][op]['dependencies'],c),op)
    def test_duplicates_cache_and_no_repeat_implementation(self):
        grant=self.full();count=len(self.worker.calls);r=self.c.chain(grant);self.assertEqual(len(self.worker.calls),count)
        self.assertTrue(all(x['status']=='passed' for x in r['results']))
        self.assertEqual(self.run_op('implement')['status'],'reused');self.assertEqual(len(self.worker.calls),count)
        self.assertEqual(len(self.c.state['calls']),4)
    def test_source_environment_policy_selective_invalidation(self):
        self.full();(self.root/'app.py').write_text('def answer():\n    return 2 # changed\n')
        self.assertEqual(self.c.assess('implement')['status'],'current');self.assertEqual(self.c.assess('groom')['status'],'current');self.assertNotEqual(self.c.assess('verify')['status'],'current')
        self.assertIn('current_author_provenance_required:adopt',self.c.assess('review')['blockers'])
        a=self.c.assess('adopt');self.assertEqual(self.run_op('adopt',dict(binding=a['binding'],identity='external-engineer',provider='human'))['status'],'passed')
        self.assertEqual(self.run_op('verify')['status'],'passed');self.assertEqual(self.run_op('review')['status'],'passed')
        self.plan['environment']={'LANG':'C'};self.modify_plan();self.assertNotEqual(self.c.assess('verify')['status'],'current');self.assertEqual(self.c.assess('implement')['status'],'current')
    def test_exhaustion_external_adoption_preserves_draft_and_ledger(self):
        self.groom();draft=(self.root/'spec.md').read_bytes();self.worker.fail=True
        for i in range(3):
            (self.root/'app.py').write_text('def answer():\n    return 2 # repair '+str(i)+'\n')
            r=self.run_op('implement');self.assertEqual(r['status'],'failed')
            with self.assertRaisesRegex(ValueError,'unchanged_failure|exhausted'):self.c.execute(r['grant'],'implement','duplicate-'+str(i))
        failures=json.dumps(self.c.state['attempts'])
        self.worker.fail=False;a=self.c.assess('adopt')
        g=self.grant(m.RECIPES['external'],dict(binding=a['binding'],identity='external-engineer',provider='human'))
        r=self.c.chain(g);self.assertEqual(r['view']['status'],'pending_manual_acceptance',r)
        self.assertEqual((self.root/'spec.md').read_bytes(),draft)
        self.assertEqual(sum(o=='implement' for o,b in self.worker.calls),3)
        self.assertEqual(json.loads(failures),self.c.state['attempts'][:len(json.loads(failures))])
    def test_failed_vacuous_and_missing_evidence(self):
        self.groom();self.run_op('implement');(self.root/'test_app.py').write_text('print("nothing executed")\n')
        self.assertEqual(self.run_op('verify')['reason'],'failed_or_vacuous_tests')
        self.assertNotEqual(self.c.assess('review')['status'],'ready')
    def test_budget_and_rejected_preflight_no_charge(self):
        self.plan['aggregate']['calls']=1;self.modify_plan();g=self.grant(m.RECIPES['factory']);r=self.c.chain(g)
        self.assertEqual(len(self.worker.calls),1);self.assertEqual(self.c.usage(g)['calls'],1)
        self.assertEqual(r['results'][-1]['reason'],'provider_call_limit_exhausted')
    def test_pending_unknown_never_reinvoked(self):
        class Crash(BaseException):pass
        def die(*args):raise Crash()
        self.c.worker=die;g=self.grant(['groom-spec'])
        with self.assertRaises(Crash):self.c.execute(g,'groom-spec','pending')
        c=m.Operations(self.root,'demo',self.worker)
        self.assertEqual(c.execute(g,'groom-spec','pending')['status'],'pending')
        with self.assertRaisesRegex(ValueError,'unfinished_operation'):c.execute(g,'groom-spec','different')
        self.assertFalse(self.worker.calls)
    def test_checkpoint_restart_and_tamper(self):
        original=self.c.finalize
        def stop(a):raise KeyboardInterrupt()
        self.c.finalize=stop;g=self.grant(['groom-spec'])
        with self.assertRaises(KeyboardInterrupt):self.c.execute(g,'groom-spec','checkpoint')
        self.c=m.Operations(self.root,'demo',self.worker)
        self.assertEqual(self.c.execute(g,'groom-spec','checkpoint')['status'],'passed');self.assertEqual(len(self.worker.calls),1)
        row=self.c.state['results']['groom-spec'];(self.c.directory/next(iter(row['evidence']))).write_text('{}')
        self.assertNotEqual(self.c.assess('groom-spec')['status'],'current')
    def test_exact_once_parallel_accounting_and_unknown_reservation(self):
        g=self.grant(['groom-spec'])
        with self.c.lease():
            # Each reservation holds its maximum capacity. Finish releases unused capacity.
            r=self.c.reserve(g,'groom-spec','one',20);self.c.finish('one',.01);self.c.finish('one',.01)
            with self.assertRaisesRegex(ValueError,'accounting_conflict'):self.c.finish('one',.02)
            self.c.reserve(g,'groom-spec','unknown',30)
            with self.assertRaisesRegex(ValueError,'time_limit'):self.c.reserve(g,'groom-spec','three',40)
        c=m.Operations(self.root,'demo');u=c.usage(g);self.assertEqual(u['calls'],2);self.assertEqual(u['unknown'],1);self.assertAlmostEqual(u['seconds'],30)
    def test_migration_never_mutates_legacy(self):
        legacy=self.c.directory.parent.parent/'pipeline/demo/state.json';legacy.parent.mkdir(parents=True);legacy.write_bytes(b'{"version":1,"exhausted":true,"usage":600}\n')
        budget=m.load('ticket-budget').ledger_path(self.root,'demo');budget.parent.mkdir(parents=True,exist_ok=True);budget.write_bytes(b'{"exhausted":true,"active_used":600,"provider_calls":64}\n')
        before=legacy.read_bytes();budget_before=budget.read_bytes();self.c.migrate('synthetic','migration');self.assertEqual(legacy.read_bytes(),before);self.assertEqual(budget.read_bytes(),budget_before)
        self.assertEqual(self.c.assess('groom-spec')['status'],'current');self.assertNotEqual(self.c.assess('groom')['status'],'current')
    def test_accept_requires_explicit_current_attestation(self):
        self.full();a=self.c.assess('accept')
        with self.assertRaisesRegex(ValueError,'attestation'):self.run_op('accept')
        self.assertEqual(self.run_op('accept',dict(binding=a['binding'],accepted=True))['status'],'passed')
        (self.root/'app.py').write_text('def answer(): return 3\n');self.assertNotEqual(self.c.assess('accept')['status'],'current')
    def test_stale_authorization_and_duplicate_grant(self):
        a=self.c.assess('groom-spec');g=self.grant(['groom-spec'])
        old=self.c.state['authorizations'][g]
        self.assertEqual(old,self.c.authorize(['groom-spec'],a['binding'],'synthetic-operator',g))
        (self.root/'request.md').write_text('changed\n')
        with self.assertRaisesRegex(ValueError,'authorized_inputs_changed'):self.c.execute(g,'groom-spec','changed')
        self.assertFalse(self.worker.calls)


if __name__=='__main__':unittest.main()
