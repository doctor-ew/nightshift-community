import os
import json
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

    def test_workshop_migrates_route_and_keeps_existing_roles(self):
        self.run_init('claude', '--include', 'brief.md')
        route = self.project / 'routing.json'
        data = json.loads(route.read_text())
        data.pop('profiles')
        route.write_text(json.dumps(data))
        subprocess.run(['git', '-C', str(self.project), 'add', 'routing.json'], env=self.env, check=True)
        subprocess.run(['git', '-C', str(self.project), 'commit', '-m', 'fixture legacy routing'], env=self.env, check=True, capture_output=True)
        self.run_init('--profile', 'workshop')
        config = tomllib.loads((self.project / '.nightshift.toml').read_text())
        self.assertEqual(config['workflow']['profile'], 'workshop')
        self.assertEqual(config['ledger']['mode'], 'files')
        upgraded = json.loads(route.read_text())
        self.assertEqual(upgraded['roles'], data['roles'])
        self.assertFalse(upgraded['profiles']['workshop']['cross_provider'])
        before = self.git('rev-parse', 'HEAD')
        self.run_init('--profile', 'workshop')
        self.assertEqual(before, self.git('rev-parse', 'HEAD'))

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
        head = self.git('rev-parse', 'HEAD')
        self.run_init()
        self.assertEqual(head, self.git('rev-parse', 'HEAD'))
        self.assertEqual(before, self.git('diff', '--cached'))

    def test_initialization_preserves_partial_stage(self):
        self.git('init', '-b', 'main')
        self.git('add', 'unrelated.txt')
        self.git('commit', '-m', 'baseline')
        (self.project / 'unrelated.txt').write_text('staged version')
        self.git('add', 'unrelated.txt')
        (self.project / 'unrelated.txt').write_text('unstaged version')
        staged = self.git('diff', '--cached')
        unstaged = self.git('diff')
        self.run_init('claude')
        self.assertEqual(staged, self.git('diff', '--cached'))
        self.assertEqual(unstaged, self.git('diff'))
        self.assertEqual(set(self.git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines()),
                         {'.nightshift.toml', 'routing.json'})

    def test_unborn_repository_preserves_staged_file(self):
        self.git('init', '-b', 'main')
        self.git('add', 'unrelated.txt')
        staged = self.git('diff', '--cached')
        self.run_init('claude', '--include', 'brief.md')
        self.assertEqual(staged, self.git('diff', '--cached'))
        self.assertEqual(set(self.git('ls-tree', '--name-only', 'HEAD').splitlines()),
                         {'.nightshift.toml', 'routing.json', 'brief.md'})

    def test_staged_initialization_file_rejected_without_mutation(self):
        self.run_init()
        config = self.project / '.nightshift.toml'
        config.write_text(config.read_text() + '\n# user edit\n')
        self.git('add', '.nightshift.toml')
        staged = self.git('diff', '--cached')
        head = self.git('rev-parse', 'HEAD')
        self.run_init('claude', status=64)
        self.assertEqual(staged, self.git('diff', '--cached'))
        self.assertEqual(head, self.git('rev-parse', 'HEAD'))

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
