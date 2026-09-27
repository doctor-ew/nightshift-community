#!/usr/bin/env python3
"""The per-process checkout cache must never answer for a different checkout at the same path."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('identity',ROOT/'scripts/nightshift-checkout-identity.py')
identity=importlib.util.module_from_spec(spec);spec.loader.exec_module(identity)
git=lambda *a:subprocess.run(['git',*a],check=True,capture_output=True)


class CheckoutIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp=Path(tempfile.mkdtemp()).resolve();self.addCleanup(shutil.rmtree,self.tmp,True)
        identity._CACHE.clear()
    def repo(self,path):
        path.mkdir(parents=True,exist_ok=True);git('init','-q',str(path))
        git('-C',str(path),'-c','user.name=t','-c','user.email=t@t','commit','-q','--allow-empty','-m','init')
        return path
    def test_answers_are_cached_and_reused(self):
        path=self.repo(self.tmp/'a');first=identity.checkout_identity(path)
        self.assertEqual(first,(path,path/'.git'))
        self.assertTrue(any(k[0]==str(path) for k in identity._CACHE))
        self.assertEqual(identity.checkout_identity(path),first)
    def test_a_different_checkout_at_the_same_path_is_not_served_from_cache(self):
        path=self.repo(self.tmp/'p');self.assertEqual(identity.checkout_identity(path)[1],path/'.git')
        shutil.rmtree(path);other=self.repo(self.tmp/'other')
        git('-C',str(other),'worktree','add','-q',str(path))
        self.assertEqual(identity.checkout_identity(path),(path,other/'.git'))
    def test_recreated_repository_at_the_same_path_answers_correctly(self):
        path=self.repo(self.tmp/'r');self.assertEqual(identity.checkout_identity(path),(path,path/'.git'))
        shutil.rmtree(path);self.repo(path)
        self.assertEqual(identity.checkout_identity(path),(path,path/'.git'))
    def test_nested_repository_created_later_owns_the_path(self):
        outer=self.repo(self.tmp/'outer');inner=outer/'sub'/'inner';inner.mkdir(parents=True)
        self.assertEqual(identity.checkout_identity(inner),(outer,outer/'.git'))
        self.repo(outer/'sub')
        self.assertEqual(identity.checkout_identity(inner),(outer/'sub',outer/'sub'/'.git'))
    def test_repointed_symlink_is_a_different_checkout(self):
        a=self.repo(self.tmp/'a');b=self.repo(self.tmp/'b');link=self.tmp/'link';link.symlink_to(a)
        self.assertEqual(identity.checkout_identity(link),(a,a/'.git'))
        link.unlink();link.symlink_to(b)
        self.assertEqual(identity.checkout_identity(link),(b,b/'.git'))
    def test_git_discovery_environment_is_part_of_the_key(self):
        a=self.repo(self.tmp/'a');b=self.repo(self.tmp/'b')
        self.assertEqual(identity.checkout_identity(a),(a,a/'.git'))
        with unittest.mock.patch.dict(identity.os.environ,GIT_DIR=str(b/'.git'),GIT_WORK_TREE=str(b)):
            self.assertEqual(identity.checkout_identity(a),(b,b/'.git'))
        self.assertEqual(identity.checkout_identity(a),(a,a/'.git'))
    def test_differently_cased_query_is_cached_on_case_insensitive_filesystems(self):
        path=self.repo(self.tmp/'MyRepo');query=self.tmp/'myrepo'
        if not query.exists():self.skipTest('case-sensitive filesystem')
        self.assertEqual(identity.checkout_identity(query),(path,path/'.git'))
        self.assertTrue(any(k[0]==str(query) for k in identity._CACHE))
    def test_non_checkouts_are_not_cached(self):
        plain=self.tmp/'plain';plain.mkdir()
        self.assertIsNone(identity.checkout_identity(plain));self.assertFalse(any(k[0]==str(plain) for k in identity._CACHE))

if __name__=='__main__':unittest.main()
