import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('runtime',ROOT/'scripts/nightshift-runtime.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

class RuntimeTest(unittest.TestCase):
    def test_mise_shim_resolves_through_mise_without_changing_argv0(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);shims=root/'mise/shims';shims.mkdir(parents=True)
            actual=root/'actual';actual.write_text('#!/bin/sh\necho version\n');actual.chmod(0o755)
            mise=root/'mise-bin';mise.write_text('#!/bin/sh\nprintf "%s\\n" "'+str(actual)+'"\n');mise.chmod(0o755)
            shim=shims/'codex';shim.symlink_to(mise)
            with patch.object(runtime.shutil,'which',side_effect=lambda n:str(shim if n=='codex' else mise)):
                self.assertEqual(runtime.executable('codex'),str(actual))
    def test_ordinary_symlink_keeps_dispatch_name(self):
        with patch.object(runtime.shutil,'which',return_value='/tmp/bin/codex'):
            self.assertEqual(runtime.executable('codex'),'/tmp/bin/codex')
    def test_missing_runtime(self):
        with patch.object(runtime.shutil,'which',return_value=None):
            with self.assertRaises(ValueError):runtime.executable('missing')
if __name__=='__main__':unittest.main()
