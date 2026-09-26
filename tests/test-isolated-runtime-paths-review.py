#!/usr/bin/env python3
"""Executable isolated-home regressions; providers are replaced with inert stubs."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('efficiency_paths', ROOT/'scripts/nightshift-efficiency.py')
efficiency = importlib.util.module_from_spec(spec)
spec.loader.exec_module(efficiency)


class RuntimePaths(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-isolated-paths-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base/'synthetic home'
        self.home.mkdir(mode=0o700)
        self.runtime = self.base/'runtime with spaces'
        self.bin = self.base/'fake bin'
        self.bin.mkdir()
        for name in ('gh','bd','ollama','claude','codex','mex'):
            target = self.bin/name
            target.write_text('#!/bin/sh\nexit 0\n')
            target.chmod(0o700)
        self.env = {key:value for key,value in os.environ.items() if not key.startswith('NIGHTSHIFT_') and key!='CODEX_HOME'}
        self.env.update(HOME=str(self.home), PATH=str(self.bin)+os.pathsep+os.environ['PATH'], PYTHONDONTWRITEBYTECODE='1')

    def capability(self, env, target):
        result = subprocess.run(['bash',str(ROOT/'scripts/nightshift-capability.sh'),'--refresh'],env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((target/'capabilities').is_file())

    def test_cache_uses_runtime_home_with_spaces(self):
        self.capability(dict(self.env,NIGHTSHIFT_HOME=str(self.runtime)),self.runtime)
        self.assertFalse((self.home/'.nightshift').exists())

    def test_cache_explicit_override_wins(self):
        explicit = self.base/'explicit cache'
        self.capability(dict(self.env,NIGHTSHIFT_HOME=str(self.runtime),NIGHTSHIFT_CACHE_DIR=str(explicit)),explicit)
        self.assertFalse(self.runtime.exists())

    def test_cache_default_remains_compatible(self):
        self.capability(self.env,self.home/'.nightshift')

    def receipt(self, env, expected):
        with patch.dict(os.environ,env,clear=True):
            receipt = efficiency.Receipt()
            try:
                self.assertEqual(receipt.path.parent,expected)
                receipt.save(dict(status='synthetic',reason='path_test'))
                self.assertTrue((receipt.path/'receipt.json').is_file())
            finally:
                receipt.close()

    def test_receipts_use_runtime_home_with_spaces(self):
        self.receipt(dict(self.env,NIGHTSHIFT_HOME=str(self.runtime)),self.runtime/'efficiency')
        self.assertFalse((self.home/'.nightshift').exists())

    def test_receipt_explicit_override_wins(self):
        explicit = self.base/'explicit receipts'
        self.receipt(dict(self.env,NIGHTSHIFT_HOME=str(self.runtime),NIGHTSHIFT_EFFICIENCY_DIR=str(explicit)),explicit)
        self.assertFalse(self.runtime.exists())

    def test_receipt_default_remains_compatible(self):
        self.receipt(self.env,self.home/'.nightshift/efficiency')

    def test_installer_generated_and_migrated_hooks_execute_in_selected_runtime(self):
        source = self.base/'source clone'
        subprocess.run(['git','clone','--quiet','--local','--no-hardlinks',str(ROOT),str(source)],check=True,capture_output=True)
        shutil.copyfile(ROOT/'install.sh',source/'install.sh')
        claude,codex,installed,launchers = [self.base/name for name in ('claude adapter','codex adapter','installed runtime','installed bin')]
        flags = ['--runtime','all','--target',str(claude),'--codex-target',str(codex),'--nightshift-target',str(installed),'--bin-target',str(launchers),'--with-hook']
        result = subprocess.run(['bash',str(source/'install.sh'),*flags],env=self.env,capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        settings = json.loads((claude/'settings.json').read_text())
        commands = [h['command'] for groups in settings['hooks'].values() for group in groups for h in group['hooks']]
        self.assertEqual(len(commands),3)
        for selected in (self.runtime,self.home/'.nightshift'):
            scripts = selected/'scripts';scripts.mkdir(parents=True,exist_ok=True)
            for name in ('nightshift-scope-freeze.sh','nightshift-spec-guardrail.sh','nightshift-stop-hook.sh'):
                (scripts/name).write_text('#!/bin/sh\nprintf selected-home\n')
            env = dict(self.env)
            if selected==self.runtime:env['NIGHTSHIFT_HOME']=str(selected)
            for command in commands:
                called = subprocess.run(['bash','-c',command],env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual((called.returncode,called.stdout),(0,'selected-home'),called.stderr)
        # Existing literal hooks are migrated; unrelated operator hooks are retained.
        custom = [
            'printf operator-hook',
            'echo ~/.nightshift/scripts/nightshift-stop-hook.sh',
            'bash "~/.nightshift/scripts/nightshift-stop-hook.sh"',
            'bash ~/.nightshift/scripts/nightshift-stop-hook.sh --custom',
            'bash ~/.nightshift/scripts/nightshift-custom.sh',
            'bash ~/.nightshift/scripts/nightshift-stop-hook.sh && printf retained',
            "printf '%s' 'bash ~/.claude/scripts/nightshift-stop-hook.sh'",
        ]
        settings['hooks']['Stop'] = [{'hooks':[{'type':'command','command':command} for command in ['bash ~/.claude/scripts/nightshift-stop-hook.sh',*custom]]}]
        (claude/'settings.json').write_text(json.dumps(settings))
        result = subprocess.run(['bash',str(source/'install.sh'),*flags],env=self.env,capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        migrated = json.loads((claude/'settings.json').read_text())['hooks']['Stop'][0]['hooks']
        self.assertEqual(migrated[0]['command'],'bash "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-stop-hook.sh"')
        self.assertEqual([hook['command'] for hook in migrated[1:]],custom)


if __name__=='__main__':
    unittest.main()
