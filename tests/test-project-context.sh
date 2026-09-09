#!/usr/bin/env bash
# Behavioral contract fixtures for neutral project discovery and tool lookup.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
import json, os, pathlib, subprocess, sys, tempfile, unittest

ROOT = pathlib.Path(sys.argv.pop(1))
RESOLVER = ROOT / 'scripts/nightshift-project-context.py'

class ContextContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nightshift-context-contract-')
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name).resolve()
        self.project = self.base / 'project'; self.project.mkdir()
        self.other = self.base / 'other'; self.other.mkdir()
        self.env = dict(os.environ)
        for key in ('NIGHTSHIFT_PROJECT_DIR', 'CLAUDE_PROJECT_DIR', 'GIT_DIR', 'GIT_WORK_TREE'):
            self.env.pop(key, None)
        self.env['NIGHTSHIFT_CACHE_DIR'] = str(self.base / 'must-not-create-cache')
        binary = self.base / 'bin'; binary.mkdir()
        self.calls = self.base / 'unexpected-tool-call'
        self.env['UNEXPECTED_CALL'] = str(self.calls)
        for name in ('gh', 'claude', 'codex', 'curl', 'ollama', 'bd', 'mex'):
            stub = binary / name
            stub.write_text('#!/bin/sh\nprintf called >> "$UNEXPECTED_CALL"\nexit 99\n')
            stub.chmod(0o755)
        self.env['PATH'] = str(binary) + os.pathsep + self.env['PATH']

    def run_command(self, argv, env=None, cwd=None):
        return subprocess.run([str(a) for a in argv], cwd=cwd or self.project,
                              env=env or self.env, capture_output=True, text=True)

    def resolve(self, *args, env=None, cwd=None):
        if not RESOLVER.is_file():
            self.skipTest('UNIMPLEMENTED: resolver absent; not a behavioral RED assertion')
        return self.run_command(['python3', RESOLVER, *args], env, cwd)

    def root(self, *args, env=None, cwd=None):
        result = self.resolve(*args, '--root-only', env=env, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def payload(self, *args, env=None):
        result = self.resolve(*args, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_root_precedence_and_conflict(self):
        env = dict(self.env, NIGHTSHIFT_PROJECT_DIR=str(self.project), CLAUDE_PROJECT_DIR=str(self.other))
        self.assertNotEqual(self.resolve('--root-only', env=env).returncode, 0)
        self.assertEqual(self.root('--project', self.other, env=env), str(self.other))
        env.pop('CLAUDE_PROJECT_DIR')
        self.assertEqual(self.root(env=env, cwd=self.other), str(self.project))
        env.pop('NIGHTSHIFT_PROJECT_DIR'); env['CLAUDE_PROJECT_DIR'] = str(self.other)
        self.assertEqual(self.root(env=env), str(self.other))

    def test_symlink_equivalence(self):
        alias = self.base / 'alias'; alias.symlink_to(self.project, target_is_directory=True)
        env = dict(self.env, NIGHTSHIFT_PROJECT_DIR=str(alias), CLAUDE_PROJECT_DIR=str(self.project))
        self.assertEqual(self.root(env=env), str(self.project))

    def test_git_root_and_cwd_default(self):
        self.run_command(['git', 'init', '-q', self.project])
        child = self.project / 'child'; child.mkdir()
        self.assertEqual(self.root(cwd=child), str(self.project))
        self.assertEqual(self.root('--cwd-default', cwd=child), str(child))

    def test_scoped_conventions_and_exact_configured_command(self):
        child = self.project / 'child'; child.mkdir()
        nested = child / 'nested'; nested.mkdir()
        sibling = self.project / 'sibling'; sibling.mkdir()
        expected = []
        for directory in (self.project, child, nested):
            for name in ('AGENTS.md', 'CLAUDE.md'):
                path = directory / name; path.write_text('Fixture instructions')
                expected.append(str(path))
        (sibling / 'AGENTS.md').write_text('Not applicable')
        command = '  bun run test -- --runInBand --reporter="x y"  '
        manifest = self.project / '.nightshift.toml'
        manifest.write_text('[tests]\ncommand = ' + json.dumps(command) + '\n')
        before = {str(p): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        result = self.payload('--project', self.project, '--scope', nested)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['project'], str(self.project))
        self.assertEqual(result['conventions'], expected)
        self.assertEqual(result['test_command'], command)
        self.assertEqual(result['test_command_source'], str(manifest))
        self.assertEqual(result['convention_policy'], 'runtime_review_required')
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.project.rglob('*') if p.is_file()})

    def test_missing_manifest_is_discoverable(self):
        result = self.payload('--project', self.project)
        self.assertEqual(result['status'], 'ok')
        self.assertIsNone(result['manifest'])
        self.assertIsNone(result['test_command'])
        self.assertIsNone(result['test_command_source'])

    def test_state_implicit_disagreement_blocks(self):
        env = dict(self.env, NIGHTSHIFT_PROJECT_DIR=str(self.other), CLAUDE_PROJECT_DIR=str(self.project))
        result = self.run_command(['bash', ROOT / 'scripts/nightshift-state-dir.sh'], env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')

    def test_scope_escape_rejected(self):
        self.assertNotEqual(self.resolve('--project', self.project, '--scope', self.other).returncode, 0)
        escape = self.project / 'escape'; escape.symlink_to(self.other, target_is_directory=True)
        self.assertNotEqual(self.resolve('--project', self.project, '--scope', escape).returncode, 0)

    def test_root_and_shell_ignore_bad_manifest(self):
        (self.project / '.nightshift.toml').write_text('broken = [')
        self.assertEqual(self.root('--project', self.project), str(self.project))
        result = self.resolve('--project', self.project, '--shell')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(self.resolve('--project', self.project).returncode, 0)

    def test_shell_quoting_and_legacy_clear(self):
        strange = self.base / "quote ' $(touch INJECTED) `touch SECOND` ; space"
        strange.mkdir()
        env = dict(self.env, CLAUDE_PROJECT_DIR=str(self.other))
        result = self.resolve('--project', strange, '--shell', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        env['CONTEXT_SHELL'] = result.stdout
        checked = self.run_command(['bash', '-c', 'eval "$CONTEXT_SHELL"; printf "%s\\n%s\\n" "$NIGHTSHIFT_PROJECT_DIR" "${CLAUDE_PROJECT_DIR-unset}"'], env)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(checked.stdout.splitlines(), [str(strange), 'unset'])
        self.assertFalse((self.project / 'INJECTED').exists())
        self.assertFalse((self.project / 'SECOND').exists())

    def test_canonical_invalid_never_falls_back(self):
        (self.project / 'nightshift.toml').write_text('[tests]\ncommand = "legacy"\n')
        canonical = self.project / '.nightshift.toml'
        for content in ('broken = [', 'tests = 17', '[tests]\ncommand = 17', '[tests]\ncommand = "   "', '[tests]\ncommand = "a\\nb"'):
            with self.subTest(content=content):
                canonical.write_text(content)
                self.assertNotEqual(self.resolve('--project', self.project).returncode, 0)

    def test_unreadable_canonical_never_falls_back(self):
        canonical = self.project / '.nightshift.toml'; canonical.write_text('[tests]\ncommand = "a"')
        (self.project / 'nightshift.toml').write_text('[tests]\ncommand = "b"')
        canonical.chmod(0)
        try:
            if os.access(canonical, os.R_OK):
                self.skipTest('Host identity can read mode-000 file')
            self.assertNotEqual(self.resolve('--project', self.project).returncode, 0)
        finally:
            canonical.chmod(0o600)

    def test_state_explicit_override_and_legacy_preservation(self):
        env = dict(self.env, NIGHTSHIFT_PROJECT_DIR=str(self.other), CLAUDE_PROJECT_DIR=str(self.project))
        legacy = self.project / '.claude/task-progress'; legacy.mkdir(parents=True)
        (legacy / 'fixture.md').write_text('retained')
        result = self.run_command(['bash', ROOT / 'scripts/nightshift-state-dir.sh', '--project', self.project, '--task', 'fixture'], env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(pathlib.Path(result.stdout.strip()), legacy)
        self.assertFalse((self.project / '.nightshift').exists())

    def capability(self, mapping=None, available=None):
        args = ['bash', ROOT / 'scripts/nightshift-capability.sh', '--resolve', 'document-read']
        if mapping is not None:
            path = self.base / 'mapping.json'; path.write_text(mapping)
            args += ['--mapping', path]
        if available is not None:
            path = self.base / 'available.json'; path.write_text(available)
            args += ['--available-tools', path]
        result = self.run_command(args)
        self.assertFalse((self.base / 'must-not-create-cache').exists())
        self.assertFalse(self.calls.exists(), 'Semantic lookup invoked an external capability probe')
        return result

    def test_capability_absent_is_unavailable(self):
        result = self.capability()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'unavailable')

    def test_capability_exact_available_mapping(self):
        result = self.capability('{"document-read":"fixture_read"}', '["fixture_read"]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['tool'], 'fixture_read')
        result = self.capability('{"document-read":"fixture_read"}', '["fixture_reader"]')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'unavailable')

    def test_capability_invalid_data(self):
        for mapping, available in [('{', '[]'), ('[]', '[]'), ('{"document-read":17}', '[]'), ('{"document-read":"bad;tool"}', '[]'), ('{"document-read":"fixture_read"}', '{}'), ('{"document-read":"fixture_read"}', '[17]')]:
            with self.subTest(mapping=mapping, available=available):
                self.assertEqual(self.capability(mapping, available).returncode, 64)

unittest.main(verbosity=2)
PY
