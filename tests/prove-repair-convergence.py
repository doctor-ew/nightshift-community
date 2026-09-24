#!/usr/bin/env python3
"""Run a synthetic consumer through real fault, deterministic repair and behavior.

No model executable is invoked. This is not full factory/provider certification.
Keep all evidence in a fresh output directory; never reuse prior success.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def prove(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + 30
    def run(label, args, expected):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('30-second demonstration limit exhausted')
        result = subprocess.run(args, cwd=output, capture_output=True, text=True, timeout=remaining)
        (output/(label + '.json')).write_text(json.dumps(dict(command=args, exit_code=result.returncode,
            stdout=result.stdout, stderr=result.stderr), indent=2) + '\n')
        if result.returncode != expected:
            raise AssertionError(f'{label}: expected exit {expected}, got {result.returncode}')
        return result
    before = b'{"multiplier":3}\n'
    (output/'prior.json').write_bytes(before)
    (output/'current.json').write_bytes(before)
    (output/'consumer.py').write_text('''import json
from pathlib import Path
def transform(value):
    return value * json.loads(Path("current.json").read_text())["multiplier"]
''')
    (output/'verify.py').write_text('''from consumer import transform
for value in (-3, 0, 2):
    actual = transform(value)
    assert actual == value * 2, (value, actual)
print("PASS: three consumer behavior assertions")
''')
    (output/'repair-checks.json').write_text(json.dumps({'schema_version':1, 'findings':[{
        'id':'double-input', 'artifact':'current.json', 'pointer':'/multiplier', 'expected':2,
        'prior_artifact':'prior.json', 'prior_sha256':hashlib.sha256(before).hexdigest()}]}, indent=2))
    run('fault', [sys.executable, 'verify.py'], 1)
    checker = [sys.executable, str(ROOT/'scripts/nightshift-repair-check.py')]
    options = ['--project', str(output), '--manifest', 'repair-checks.json', '--out', 'repair-check.receipt.json']
    run('original-check', checker + ['check'] + options, 1)
    run('repair', checker + ['apply'] + options, 0)
    result = run('behavior', [sys.executable, 'verify.py'], 0)
    assert result.stdout.strip() == 'PASS: three consumer behavior assertions'
    receipt = json.loads((output/'repair-check.receipt.json').read_text())
    assert receipt['status'] == 'passed' and receipt['gate_approval'] is False
    assert (output/'prior.json').read_bytes() == before
    summary = dict(ticket='convergence-proof', gate='synthetic-consumer-behavior', status='complete',
        reason='Original behavior failed; deterministic apply repaired the pinned value; three actual consumer assertions passed.',
        scope='synthetic deterministic consumer; not full factory or live model proof',
        elapsed_seconds=round(time.monotonic()-started, 3), time_limit_seconds=30,
        provider_launch_limit=0, provider_launches=0, repair_attempts=1, behavior_retries=1,
        known_provider_tokens=0, assistant_session_tokens=None,
        unknown_accounting=['assistant session token usage', 'historical subscription usage'], gate_approval=False)
    (output/'completion.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    prove(parser.parse_args().out)
