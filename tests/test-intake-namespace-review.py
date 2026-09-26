#!/usr/bin/env python3
"""Independent intake namespace derivation and bounded adapter regressions."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
m=load('namespace_intake','scripts/nightshift-intake.py')
f=load('namespace_fixture','tests/test-operations.py')

class NamespaceReview(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-namespace-review-')
        self.addCleanup(temporary.cleanup);self.root=Path(temporary.name).resolve();f.fixture(self.root)
        subprocess.run(['git','-C',str(self.root),'remote','remove','origin'],capture_output=True)
    def origin(self,url):
        subprocess.run(['git','-C',str(self.root),'remote','add','origin',url],check=True,capture_output=True)
    def source(self,repository='expected/repository'):
        return dict(source='gh',repository=repository,source_id='7',external_ref='gh-7',body='Synthetic request',url='https://github.com/'+repository+'/issues/7')
    def resolve(self,reference,source):
        original=m.source_json
        def adapter(project,argv):
            if '--derive-id' in argv:return original(project,argv)
            return source
        with patch.object(m,'source_json',adapter):return m.resolve(self.root,reference)
    def test_bare_reference_rejects_returned_repository_different_from_origin(self):
        self.origin('https://github.com/expected/repository.git')
        with self.assertRaisesRegex(ValueError,'source_identity_mismatch'):
            self.resolve('gh:7',self.source('wrong/repository'))
    def test_valid_bare_ssh_origin(self):
        self.origin('git@github.com:expected/repository.git')
        source,task=self.resolve('gh:7',self.source());self.assertEqual(source,self.source());self.assertTrue(task.startswith('gh-'))
    def test_qualified_reference_overrides_different_origin(self):
        self.origin('https://github.com/other/repository.git')
        source,_=self.resolve('gh:expected/repository#7',self.source());self.assertEqual(source,self.source())
    def test_bare_without_origin_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'source_identity_mismatch'):
            self.resolve('gh:7',self.source())
    def test_qualified_without_origin_succeeds(self):
        source,_=self.resolve('gh:expected/repository#7',self.source());self.assertEqual(source,self.source())
    def test_each_returned_identity_field_is_checked(self):
        for key,value in [('source','spec'),('source_id','8'),('external_ref','gh-8'),('url','https://github.com/wrong/repository/issues/7')]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'source_identity_mismatch'):
                self.resolve('gh:expected/repository#7',{**self.source(),key:value})
    def test_local_bare_and_explicit_compatibility(self):
        explicit=m.resolve(self.root,'spec:request.md');bare=m.resolve(self.root,'request.md');self.assertEqual(explicit,bare)
    def test_source_output_limit_and_failed_adapter_are_not_parsed(self):
        for payload,code,reason in [('x'*(m.ops.MAX_REQUEST//2+1),0,'source_too_large'),('{bad',1,'source_unavailable')]:
            def bounded(argv,project,env,seconds,output):
                self.assertEqual(seconds,30);self.assertEqual(env['GH_PROMPT_DISABLED'],'1');self.assertEqual(env['GIT_TERMINAL_PROMPT'],'0')
                output.write_text(payload);return code
            with self.subTest(reason=reason),patch.object(m.ops,'load',return_value=SimpleNamespace(bounded=bounded)),self.assertRaisesRegex(ValueError,reason):
                m.source_json(self.root,['synthetic-adapter'])
    def test_invalid_and_private_paths_do_not_invoke_adapter(self):
        for reference in ['--bad','spec:../outside.md','spec:.env','spec:.git/config','x'*1025]:
            with self.subTest(reference=reference[:30]),patch.object(m,'source_json') as adapter,self.assertRaises(ValueError):
                m.resolve(self.root,reference)
            adapter.assert_not_called()

if __name__=='__main__':unittest.main()
