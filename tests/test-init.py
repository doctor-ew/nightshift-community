import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'new project'
        self.project.mkdir()
        (self.project / 'brief.md').write_text('# Brief\nBuild a small prompt.\n')
        (self.project / 'unrelated.txt').write_text('do not commit')
        self.env = dict(os.environ, HOME=str(self.base), NIGHTSHIFT_HOME=str(self.base / 'home'),
                        GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1',
                        GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
                        GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid')

    def run_init(self, *args, status=0):
        result = subprocess.run(['bash', str(ROOT / 'scripts/nightshift-factory.sh'), 'init',
                                 '--project', str(self.project), *args], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.project), *args], env=self.env, text=True).strip()

    def test_bootstrap_include_and_repeat(self):
        self.run_init('claude', '--include', 'brief.md')
        self.assertEqual(set(self.git('ls-files').splitlines()), {'.nightshift.toml', 'routing.json', 'brief.md'})
        self.assertEqual((self.project / '.nightshift.toml').stat().st_mode & 0o777, 0o600)
        config = tomllib.loads((self.project / '.nightshift.toml').read_text())
        self.assertEqual(config['runtime']['provider'], 'claude')
        before = self.git('rev-parse', 'HEAD')
        self.run_init('claude', '--include', 'brief.md')
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        receipt = subprocess.run(['bash', str(ROOT / 'scripts/nightshift-preflight-check.sh'),
                                 '--project', str(self.project), '--branch', 'auto', '--ref', 'brief.md'],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(receipt.returncode, 0, receipt.stdout + receipt.stderr)

    def test_alias_and_no_implicit_source_commit(self):
        self.run_init('codex/devstral')
        config = tomllib.loads((self.project / '.nightshift.toml').read_text())
        self.assertEqual(config['runtime']['provider'], 'local')
        self.assertEqual(config['runtime']['model'], 'devstral-small-2:24b')
        self.assertNotIn('brief.md', self.git('ls-files'))

    def test_no_runtime_override_inherits(self):
        self.run_init()
        config = tomllib.loads((self.project / '.nightshift.toml').read_text())
        self.assertNotIn('runtime', config)

    def test_preexisting_stage_is_preserved(self):
        self.run_init()
        subprocess.run(['git', '-C', str(self.project), 'add', 'unrelated.txt'], env=self.env, check=True)
        before = self.git('diff', '--cached')
        self.run_init(status=64)
        self.assertEqual(before, self.git('diff', '--cached'))

    def test_outside_include_rejected_without_git(self):
        (self.base / 'outside.md').write_text('outside')
        self.run_init('--include', '../outside.md', status=64)
        self.assertFalse((self.project / '.git').exists())

    def test_missing_identity_no_mutation(self):
        for key in list(self.env):
            if key.startswith(('GIT_AUTHOR_', 'GIT_COMMITTER_')):
                self.env.pop(key)
        self.run_init(status=64)
        self.assertFalse((self.project / '.git').exists())


if __name__ == '__main__':
    unittest.main()
