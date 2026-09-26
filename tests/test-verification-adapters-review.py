#!/usr/bin/env python3
"""Independent synthetic runner tests; no providers or installed runtime changes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('verification_review_adapter',ROOT/'scripts/nightshift-verification-adapters.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class AdaptersReview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='nightshift-adapter-review-')
        self.root=Path(self.temp.name);self.events=self.root/'events.json';self.raw=self.root/'raw.log'
        self.binding='synthetic-binding-72'
    def tearDown(self):self.temp.cleanup()
    def execute(self,source,runtime='python3',timeout=10):
        name={'python3':'case.py','node':'case.mjs','bash':'case.sh'}[runtime]
        (self.root/name).write_text(source)
        self.check={'id':'synthetic','argv':[runtime,name]}
        argv,env=m.command(self.check,self.root,self.events,self.binding,os.environ)
        termination=None
        with self.raw.open('wb') as output:
            try:code=subprocess.run(argv,cwd=self.root,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=timeout).returncode
            except subprocess.TimeoutExpired:code=124;termination='timeout'
        return m.observe(self.check,self.events,self.binding,code,self.raw,termination)
    def python(self,body,decorator=''):
        return 'import unittest\nclass Case(unittest.TestCase):\n'+('    '+decorator+'\n' if decorator else '')+'    def test_case(self):\n'+''.join('        '+line+'\n' for line in body.splitlines())+'unittest.main()\n'
    def test_python_forged_prose_and_zero(self):
        for source in ['print("Ran 99 tests\\nOK\\n99 passed")','import unittest\nunittest.main()']:
            with self.subTest(source=source):self.assertEqual(self.execute(source)['status'],'blocked')
    def test_python_pass_fail_skipped_expected_and_unexpected(self):
        cases=[('self.assertTrue(True)','', 'passed'),('self.fail("no")','', 'blocked'),('self.fail("not run")','@unittest.skip("skip")','blocked'),('self.fail("expected")','@unittest.expectedFailure','blocked'),('pass','@unittest.expectedFailure','blocked')]
        for body,deco,status in cases:
            with self.subTest(body=body,deco=deco):self.assertEqual(self.execute(self.python(body,deco))['status'],status)
    def test_python_import_error(self):
        self.assertEqual(self.execute('import definitely_missing_synthetic_module')['status'],'blocked')
    def test_python_completed_pass_then_abrupt_exit(self):
        source=self.python('pass').replace('unittest.main()','unittest.main(exit=False)\nimport os\nos._exit(0)')
        row=self.execute(source);self.assertEqual(row['status'],'blocked');self.assertFalse(row['complete'])
    def test_python_completed_pass_then_timeout(self):
        source=self.python('pass').replace('unittest.main()','unittest.main(exit=False)\nimport time\ntime.sleep(10)')
        row=self.execute(source,timeout=.4);self.assertEqual(row['status'],'blocked');self.assertEqual(row['reason'],'timeout')
    def test_python_failing_subtests_cannot_become_success(self):
        body='for i in range(2):\n    with self.subTest(i=i): self.fail("failure")'
        self.assertEqual(self.execute(self.python(body))['status'],'blocked')
    def test_node_prose_and_empty_file_are_not_tests(self):
        for source in ['', 'console.log("Ran 99 tests\\n99 passed");']:
            with self.subTest(source=source):self.assertEqual(self.execute(source,'node')['status'],'blocked')
    def test_node_pass_fail_skip_and_todo(self):
        for expression,status in [('test("pass",()=>{})','passed'),('test("fail",()=>{throw Error("failed")})','blocked'),('test.skip("skip",()=>{})','blocked'),('test.todo("todo")','blocked')]:
            with self.subTest(expression=expression):self.assertEqual(self.execute('import test from "node:test";'+expression,'node')['status'],status)
    def test_node_partial_completion(self):
        row=self.execute('import test from "node:test";test("partial",()=>{process.exit(0)});','node')
        self.assertEqual(row['status'],'blocked')
    def test_node_timeout(self):
        row=self.execute('import test from "node:test";test("partial",async()=>{await new Promise(resolve=>setTimeout(resolve,10000))});','node',timeout=.5)
        self.assertEqual(row['status'],'blocked');self.assertEqual(row['reason'],'timeout')
    def test_legacy_wrapper_retains_output_without_certification(self):
        row=self.execute('printf "Ran 100 tests\\n100 passed\\n"\n','bash')
        self.assertEqual(row['status'],'blocked');self.assertEqual(row['tests'],0);self.assertIn('100 passed',row['output']);self.assertIn('legacy_wrapper',row['reason'])
    def good_report(self):
        self.assertEqual(self.execute(self.python('pass'))['status'],'passed')
        return json.loads(self.events.read_text())
    def test_report_binding_and_count_shapes(self):
        original=self.good_report()
        mutations=[lambda x:x.update(binding='other'),lambda x:x.update(adapter='node-test-v1'),lambda x:x.update(complete='true'),lambda x:x.update(runs={}),lambda x:x['runs'][0].update(complete=False),lambda x:x['runs'][0]['counts'].update(passed=True),lambda x:x['runs'][0]['counts'].update(passed=-1),lambda x:x['runs'][0]['counts'].update(total=50),lambda x:x['runs'][0]['counts'].update(extra=0)]
        for mutate in mutations:
            value=json.loads(json.dumps(original));mutate(value);self.events.write_text(json.dumps(value))
            with self.subTest(value=value):self.assertEqual(m.observe(self.check,self.events,self.binding,0,self.raw)['status'],'blocked')
    def test_malformed_missing_and_symlink_report(self):
        self.good_report();self.events.write_text('{')
        self.assertEqual(m.observe(self.check,self.events,self.binding,0,self.raw)['status'],'blocked')
        self.events.rename(self.root/'saved.json')
        self.assertEqual(m.observe(self.check,self.events,self.binding,0,self.raw)['status'],'blocked')
        self.events.symlink_to(self.root/'saved.json')
        self.assertEqual(m.observe(self.check,self.events,self.binding,0,self.raw)['status'],'blocked')
    def test_complete_receipt_does_not_override_nonzero_exit(self):
        self.good_report();self.assertEqual(m.observe(self.check,self.events,self.binding,1,self.raw)['status'],'blocked')
    def test_mixed_skipped_subtest_preserves_useful_pass(self):
        body='for i in range(2):\n    with self.subTest(i=i):\n        if i==0: self.skipTest("optional")\n        self.assertEqual(i,1)'
        self.assertEqual(self.execute(self.python(body))['status'],'passed')
    def test_all_skipped_subtests_are_vacuous(self):
        body='for i in range(2):\n    with self.subTest(i=i): self.skipTest("optional")'
        self.assertEqual(self.execute(self.python(body))['status'],'blocked')
    def test_duplicate_test_id_cannot_certify(self):
        source=self.python('pass').replace('unittest.main()', 'def load_tests(loader, tests, pattern):\n    return unittest.TestSuite([Case("test_case"),Case("test_case")])\nunittest.main()')
        self.assertEqual(self.execute(source)['status'],'blocked')
    def test_boolean_version_and_duplicate_json_field_rejected(self):
        value=self.good_report();value['version']=True;self.events.write_text(json.dumps(value))
        self.assertEqual(m.observe(self.check,self.events,self.binding,0,self.raw)['status'],'blocked')
        value['version']=1;raw=json.dumps(value);self.events.write_text(raw[:-1]+',"complete":true}')
        self.assertEqual(m.observe(self.check,self.events,self.binding,0,self.raw)['status'],'blocked')
    def test_adapter_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'incompatible'):m.profile({'argv':['python3','case.py'],'adapter':'node-test-v1'})

if __name__=='__main__':unittest.main()
