#!/usr/bin/env python3
"""The per-process checkout cache must never answer for a different checkout at the same path."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
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
        self.assertIn(str(path),identity._CACHE)
        self.assertEqual(identity.checkout_identity(path),first)
    def test_a_different_checkout_at_the_same_path_is_not_served_from_cache(self):
        path=self.repo(self.tmp/'p');self.assertEqual(identity.checkout_identity(path)[1],path/'.git')
        shutil.rmtree(path);other=self.repo(self.tmp/'other')
        git('-C',str(other),'worktree','add','-q',str(path))
        self.assertEqual(identity.checkout_identity(path),(path,other/'.git'))
    def test_recreated_repository_at_the_same_path_is_looked_up_again(self):
        path=self.repo(self.tmp/'r');old=identity._CACHE.setdefault(str(path),None) or identity.checkout_identity(path)
        fingerprint=identity._CACHE[str(path)][2];shutil.rmtree(path);self.repo(path)
        identity.checkout_identity(path);self.assertNotEqual(identity._CACHE[str(path)][2],fingerprint)
    def test_non_checkouts_are_not_cached(self):
        plain=self.tmp/'plain';plain.mkdir()
        self.assertIsNone(identity.checkout_identity(plain));self.assertNotIn(str(plain),identity._CACHE)

if __name__=='__main__':unittest.main()
