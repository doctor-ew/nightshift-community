#!/usr/bin/env python3
"""Execute public prompt helper expressions against configured/default sentinels."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / (folder + '/nightshift-' + name + '.md') for folder, names in (
    ('commands', 'product adversarial implement review drift qa batch deploy eng preflight'),
    ('agents', 'architect code-fact-extractor engineer spec-writer')) for name in names.split()]
PATTERN = re.compile(r'"\$\{NIGHTSHIFT_HOME:-\$HOME/\.nightshift\}/scripts/([A-Za-z0-9_.-]+)"')


class RuntimeHome(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-runtime-home-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / 'operator home with spaces'; self.home.mkdir()
        self.configured = self.base / 'isolated community ; $(not-executed)'
        self.default = self.home / '.nightshift'
        self.log = self.base / 'sentinel.jsonl'
        self.env = dict(os.environ, HOME=str(self.home), NIGHTSHIFT_HOME=str(self.configured), NIGHTSHIFT_FORBID_DEFAULT='1', NIGHTSHIFT_SENTINEL_LOG=str(self.log), PROJECT=str(self.base / 'project with spaces'), TASK='gh-1', TASK_KEY='gh-1', REF='gh:1')
        self.expressions = sorted({match.group(0) for path in FILES for match in PATTERN.finditer(path.read_text())})
        for directory, label in ((self.configured, 'configured'), (self.default, 'default')):
            scripts = directory / 'scripts'; scripts.mkdir(parents=True)
            for expression in self.expressions:
                name = PATTERN.fullmatch(expression).group(1)
                self.assertTrue((ROOT / 'scripts' / name).is_file(), name)
                target = scripts / name
                body = 'import json,os,sys\nwith open(os.environ["NIGHTSHIFT_SENTINEL_LOG"],"a") as f:f.write(json.dumps(dict(origin='+repr(label)+',helper='+repr(name)+',args=sys.argv[1:]))+"\\n")\nprint("{}")\n'
                body += 'if '+repr(label)+' == "default" and os.environ.get("NIGHTSHIFT_FORBID_DEFAULT") == "1": raise SystemExit(97)\n'
                if name.endswith('.py'):
                    target.write_text(body)
                else:
                    target.write_text('#!/usr/bin/env bash\nexec python3 - "$@" <<\'PY\'\n'+body+'PY\n')
                target.chmod(0o755)

    def rows(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_every_helper_expression_uses_configured_path_with_spaces(self):
        self.assertTrue(self.expressions)
        for expression in self.expressions:
            name = PATTERN.fullmatch(expression).group(1)
            interpreter = 'python3 ' if name.endswith('.py') else 'bash '
            subprocess.run(['bash', '-c', interpreter + expression + ' "argument with spaces"'], env=self.env, check=True, capture_output=True, timeout=10)
        rows = self.rows(); self.assertEqual(len(rows), len(self.expressions))
        self.assertTrue(all(row['origin'] == 'configured' and row['args'] == ['argument with spaces'] for row in rows))

    def test_unset_and_empty_runtime_home_preserve_default_with_spaces(self):
        expression = next(value for value in self.expressions if value.endswith('/nightshift-ticket-source.sh"'))
        for empty in (False, True):
            env = dict(self.env); env.pop('NIGHTSHIFT_FORBID_DEFAULT')
            if empty: env['NIGHTSHIFT_HOME'] = ''
            else: env.pop('NIGHTSHIFT_HOME')
            subprocess.run(['bash', '-c', expression + ' "$REF"'], env=env, check=True, capture_output=True, timeout=10)
        self.assertEqual([row['origin'] for row in self.rows()], ['default', 'default'])
        self.assertEqual([row['args'] for row in self.rows()], [['gh:1'], ['gh:1']])

    def test_actual_product_and_review_shell_snippets_use_only_configured_helpers(self):
        product = (ROOT / 'commands/nightshift-product.md').read_text().splitlines()
        review = (ROOT / 'commands/nightshift-review.md').read_text().splitlines()
        lines = [next(line for line in product if line.startswith('TICKET_JSON=$(')), next(line for line in product if line.startswith('TASK_DIR=$(')), next(line for line in review if line.startswith('INTEGRITY=$('))]
        subprocess.run(['bash', '-e', '-c', '\n'.join(lines)], env=self.env, check=True, capture_output=True, timeout=10)
        rows = self.rows(); self.assertEqual(len(rows), 3)
        self.assertTrue(all(row['origin'] == 'configured' for row in rows))
        self.assertEqual(rows[0]['args'], ['gh:1'])
        self.assertEqual(rows[1]['args'], ['--project', self.env['PROJECT'], '--task', 'gh-1', '--create'])
        self.assertEqual(rows[2]['args'], ['gh-1'])

    def test_claim_cache_assignment_keeps_configured_path(self):
        lines = (ROOT / 'commands/nightshift-adversarial.md').read_text().splitlines()
        assignment = next(line for line in lines if line.startswith('SCRIPT='))
        subprocess.run(['bash', '-e', '-c', assignment+'\nbash "$SCRIPT" "$TASK"'], env=self.env, check=True, capture_output=True, timeout=10)
        self.assertEqual(self.rows(), [dict(origin='configured', helper='nightshift-claim-cache.sh', args=['gh-1'])])

    def test_no_public_prompt_bypasses_runtime_home(self):
        for folder in ('commands', 'agents'):
            for path in (ROOT / folder).glob('nightshift-*.md'):
                for line in path.read_text().splitlines():
                    self.assertNotIn('~/.nightshift', line, str(path.relative_to(ROOT)))
                    stripped = line.replace('${NIGHTSHIFT_HOME:-$HOME/.nightshift}', '')
                    self.assertNotIn('$HOME/.nightshift', stripped, str(path.relative_to(ROOT)))


if __name__ == '__main__': unittest.main()
