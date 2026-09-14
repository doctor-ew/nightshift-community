"""Offline installer contracts; no WSL install, package install, or model request."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PWSH = os.environ.get('PWSH') or shutil.which('pwsh')


@unittest.skipUnless(PWSH, 'PowerShell required (set PWSH or run Windows CI)')
class PowerShellContracts(unittest.TestCase):
    def run_ps(self, script, env=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.ps1'
            path.write_text(script)
            return subprocess.run([PWSH, '-NoProfile', '-File', str(path)], text=True,
                                  capture_output=True, env=env, timeout=30)

    def test_parse_and_plan(self):
        for file in [ROOT / 'install.ps1', ROOT / 'scripts/nightshift-windows.ps1']:
            result = self.run_ps("$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('" + str(file).replace("'", "''") + "',[ref]$t,[ref]$e);if($e.Count){$e;exit 1}")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        env = dict(os.environ, USERPROFILE=str(ROOT))
        result = subprocess.run([PWSH, '-NoProfile', '-File', str(ROOT / 'install.ps1'), '-Plan'],
                                text=True, capture_output=True, env=env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual((plan['mode'], plan['runtime'], plan['auth']), ('wsl', 'claude', 'subscription'))

    def test_launcher_preserves_arguments_and_exit_status(self):
        with tempfile.TemporaryDirectory(prefix='nightshift windows ') as directory:
            path = Path(directory)
            wrapper = path / 'nightshift-windows.ps1'
            shutil.copy(ROOT / 'scripts/nightshift-windows.ps1', wrapper)
            (path / 'nightshift-windows.json').write_text(json.dumps({'distribution':'Ubuntu-24.04','launcher':'/home/student name/.local/bin/nightshift'}))
            capture = path / 'captured.json'
            values = ['claude', 'docs/brief with spaces.md', '--output', 'concise', 'literal "quote" $HOME; $(echo nope)', '']
            literal = ','.join("'" + v.replace("'", "''") + "'" for v in values)
            script = """function global:wsl.exe {
                ConvertTo-Json -InputObject @($args) -Compress | Set-Content -LiteralPath $env:NS_CAPTURE
                $global:LASTEXITCODE=23
            }
            """ + "$forward=@(" + literal + "); & '" + str(wrapper).replace("'", "''") + "' @forward; exit $LASTEXITCODE"
            result = self.run_ps(script, dict(os.environ, NS_CAPTURE=str(capture)))
            self.assertEqual(result.returncode, 23, result.stderr)
            argv = json.loads(capture.read_text(encoding='utf-8-sig'))
            self.assertEqual(json.loads(base64.b64decode(argv[-1])), values)
            self.assertEqual(argv[-2], '/home/student name/.local/bin/nightshift')
            self.assertIn('--cd', argv)


@unittest.skipIf(os.name == 'nt', 'Bash contract covered on macOS/Linux')
class BootstrapContracts(unittest.TestCase):
    def test_invalid_selection_stops_before_mutation(self):
        result = subprocess.run(['bash', str(ROOT / 'scripts/nightshift-windows-bootstrap.sh'),
                                 '/nonexistent', 'invalid-runtime', 'api', 'install'], capture_output=True)
        self.assertEqual(result.returncode, 64)

    def test_repeat_install_retains_source_and_passes_preferences(self):
        with tempfile.TemporaryDirectory(prefix='nightshift bootstrap ') as directory:
            root = Path(directory)
            home = root / 'home'; home.mkdir()
            bin_dir = root / 'bin'; bin_dir.mkdir()
            source = root / 'source checkout'; source.mkdir()
            capture = root / 'install-args'
            git = bin_dir / 'git'
            git.write_text('''#!/usr/bin/env python3
import os,sys,pathlib
args=sys.argv[1:]
if 'status' in args: print(' M dirty' if os.environ.get('NS_DIRTY') else '')
elif 'rev-parse' in args: print('abc123')
elif 'clone' in args:
 p=pathlib.Path(args[-1]);p.mkdir();(p/'.git').mkdir()
 (p/'install.sh').write_text('#!/bin/bash\\nprintf "%s\\\\n" "$@" > "$NS_CAPTURE"\\nmkdir -p "$HOME/.local/bin"\\nprintf "#!/bin/bash\\\\nexit 0\\\\n" > "$HOME/.local/bin/nightshift"\\n')
elif 'remote' in args: print(os.environ['NS_SOURCE'])
''')
            for name, text in [('id', '#!/bin/sh\necho 1000\n'), ('claude', '#!/bin/sh\necho Claude-fixture\n')]:
                (bin_dir / name).write_text(text)
            for file in bin_dir.iterdir(): file.chmod(0o755)
            env = dict(os.environ, HOME=str(home), PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],
                       NS_CAPTURE=str(capture), NS_SOURCE=str(source))
            command = ['bash', str(ROOT / 'scripts/nightshift-windows-bootstrap.sh'), str(source), 'claude', 'api', 'check']
            for _ in range(2):
                result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(capture.read_text().splitlines(), ['--runtime','claude','--auth','api','--symlink'])
            result = subprocess.run(command, env=dict(env, NS_DIRTY='1'), text=True, capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((home / '.nightshift/windows-source/.git').is_dir())

if __name__ == '__main__': unittest.main()
