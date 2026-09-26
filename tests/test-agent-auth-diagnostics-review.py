#!/usr/bin/env python3
"""Execute the dispatcher authentication section with synthetic CLIs only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AuthenticationDiagnostics(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='nightshift-auth-review-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.bin = self.root/'bin';self.bin.mkdir()
        (self.bin/'python3').symlink_to(sys.executable)
        self.stub = '#!'+sys.executable+'\nimport os,sys,time\nassert sys.argv[1:] in (["login","status"],["auth","status","--json"])\nassert not any(os.environ.get(k) for k in ("OPENAI_API_KEY","CODEX_API_KEY","ANTHROPIC_API_KEY","ANTHROPIC_AUTH_TOKEN"))\ntime.sleep(float(os.environ.get("PROBE_SLEEP","0")))\nsys.stdout.write(os.environ.get("PROBE_STDOUT",""))\nsys.stderr.write(os.environ.get("PROBE_STDERR",""))\nsys.exit(int(os.environ.get("PROBE_EXIT","0")))\n'
        for provider in ('codex','claude'):
            p=self.bin/provider;p.write_text(self.stub);p.chmod(0o700)
        source=(ROOT/'scripts/nightshift-agent.sh').read_text()
        start=source.index('if [ "$AUTH" = subscription ]; then')
        end=source.index('# Carry controller mode',start)
        self.script=self.root/'auth-section.sh'
        self.script.write_text('set -euo pipefail\nfail() { printf "%s\\n" "$1" >&2; exit 1; }\n'+source[start:end]+'printf dispatch-permitted\n')
        self.env={k:v for k,v in os.environ.items() if not k.startswith(('NIGHTSHIFT_','PROBE_'))}
        self.env.update(PATH=str(self.bin),HOME=str(self.root),AUTH='subscription',PROVIDER='codex',OUTPUT=str(self.root/'result.json'),OPENAI_API_KEY='synthetic-secret',ANTHROPIC_API_KEY='synthetic-secret')

    def run_probe(self,category,provider='codex',text='',stderr='',code=0,**extra):
        before=set(self.root.glob('*.auth-*.json'))
        result=subprocess.run(['/bin/bash',str(self.script)],env=dict(self.env,PROVIDER=provider,PROBE_STDOUT=text,PROBE_STDERR=stderr,PROBE_EXIT=str(code),**extra),capture_output=True,text=True,timeout=8)
        paths=set(self.root.glob('*.auth-*.json'))-before
        self.assertEqual(len(paths),1,result.stderr)
        path=paths.pop();receipt=json.loads(path.read_text())
        self.assertEqual(receipt['category'],category,result.stderr)
        self.assertEqual(result.returncode,0 if category=='subscription_confirmed' else 1,result.stderr)
        self.assertFalse(receipt['raw_output_retained'])
        self.assertFalse(receipt['provider_dispatched'])
        self.assertEqual(path.stat().st_mode&0o777,0o600)
        if category!='subscription_confirmed':self.assertNotIn('dispatch-permitted',result.stdout)
        self.assertNotIn('synthetic-secret',path.read_text()+result.stdout+result.stderr)
        return receipt,result

    def test_codex_confirmed_stdout_or_stderr(self):
        for stream in ('text','stderr'):
            receipt,_=self.run_probe('subscription_confirmed',**{stream:'Logged in using ChatGPT\n'})
            self.assertIs(receipt['authenticated'],True)

    def test_claude_confirmed_subscription(self):
        self.run_probe('subscription_confirmed','claude',json.dumps(dict(loggedIn=True,authMethod='claude.ai',apiProvider='firstParty')))

    def test_explicit_codex_logged_out_is_not_unknown(self):
        receipt,result=self.run_probe('subscription_login_required',text='Not logged in\n',code=1)
        self.assertIs(receipt['authenticated'],False)
        self.assertIn('explicit logged-out status',result.stderr)

    def test_explicit_claude_logged_out(self):
        self.run_probe('subscription_login_required','claude','{"loggedIn":false}',code=1)

    def test_wrong_authentication_method_is_separate(self):
        self.run_probe('subscription_method_mismatch',text='Logged in using an API key: synthetic-secret')
        self.run_probe('subscription_method_mismatch','claude','{"loggedIn":true,"authMethod":"api_key","apiProvider":"anthropic"}')

    def test_probe_denial_does_not_claim_logged_out(self):
        for provider in ('codex','claude'):
            receipt,result=self.run_probe('auth_probe_denied',provider,stderr='Permission denied: synthetic-secret /private/config',code=1)
            self.assertIsNone(receipt['authenticated'])
            self.assertNotIn('login required',result.stderr)
            self.assertNotIn('/private/config',result.stderr)

    def test_nonzero_network_failure_is_unknown(self):
        for provider in ('codex','claude'):
            self.run_probe('auth_probe_failed',provider,stderr='Network unavailable synthetic-secret',code=7)

    def test_success_text_on_nonzero_is_not_confirmation(self):
        self.run_probe('auth_probe_failed',text='Logged in using ChatGPT',code=1)
        self.run_probe('auth_probe_failed','claude','{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"firstParty"}',code=1)

    def test_invalid_and_duplicate_claude_output_is_unknown(self):
        for output in ('not json','{}','{"loggedIn":"true"}','{"loggedIn":true,"loggedIn":false}','{"loggedIn":true}'):
            self.run_probe('auth_probe_invalid_output','claude',output)

    def test_invalid_codex_output_is_unknown(self):
        self.run_probe('auth_probe_invalid_output',text='status unavailable; synthetic-secret')
        self.run_probe('auth_probe_invalid_output',text='Logged in using ChatGPT\nNot logged in')

    def test_missing_cli_is_distinct(self):
        (self.bin/'codex').unlink()
        self.run_probe('auth_cli_missing')

    def test_oversized_output_is_unknown_and_bounded(self):
        receipt,_=self.run_probe('auth_probe_output_limit',text='x'*40000)
        self.assertFalse(receipt['output_complete'])
        self.assertLess(receipt['stdout_bytes'],45000)

    def test_timeout_is_unknown_and_bounded(self):
        receipt,_=self.run_probe('auth_probe_timeout',PROBE_SLEEP='6')
        self.assertLess(receipt['elapsed_seconds'],6)
        self.assertFalse(receipt['output_complete'])

    def test_retries_retain_distinct_sanitized_receipts(self):
        self.run_probe('auth_probe_failed',stderr='one',code=1)
        self.run_probe('auth_probe_failed',stderr='two',code=2)
        self.assertEqual(len(list(self.root.glob('*.auth-*.json'))),2)


if __name__=='__main__':unittest.main()
