#!/usr/bin/env python3
"""Check certification mode and skip protocol; synthetic probes certify no run."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
KEY = 'NIGHTSHIFT_REQUIRE_INSTALLED_ACCEPTANCE'
LIVE_METHOD = 'InstalledAcceptance.test_actual_isolated_installed_six_stage_run_and_repeat'
RECORD = ROOT/'.nightshift/154-live-acceptance.json'


def main():
    results = ROOT/'.nightshift'/('154-certification-mode-results-'+uuid.uuid4().hex)
    results.mkdir(parents=True, exist_ok=False)
    print('Certification mode protocol evidence: '+str(results), flush=True)
    observations = []

    def probe(name, argv, setting):
        environment = dict(os.environ)
        environment.pop(KEY, None)
        if setting is not None:
            environment[KEY] = setting
        result = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True)
        for suffix, content in (('.stdout.log', result.stdout), ('.stderr.log', result.stderr)):
            with (results/(name+suffix)).open('xb') as stream:
                stream.write(content)
        output = (result.stdout+result.stderr).decode('utf-8', errors='replace')
        observations.append(dict(probe=name, mode=setting, exit_code=result.returncode))
        return result.returncode, output

    def require(condition, message):
        if not condition:
            raise AssertionError(message+'; raw evidence: '+str(results))

    if not RECORD.is_file() or RECORD.is_symlink():
        raise ValueError('A regular retained live record must exist before mode probes.')
    original_hash = hashlib.sha256(RECORD.read_bytes()).hexdigest()
    held = results/'retained-live-record.json'
    single = [sys.executable, str(ROOT/'tests/test-release-inputs.py'), LIVE_METHOD, '-v']
    # Renaming is temporary. Restore the exact original even when a probe fails.
    def interrupted(signum, frame):
        raise KeyboardInterrupt('mode probe interrupted')
    prior_handlers = {number: signal.signal(number, interrupted) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        try:
            RECORD.rename(held)
            for name, setting in (('ordinary-unset', None), ('ordinary-empty', ''), ('ordinary-zero', '0')):
                code, output = probe(name, single, setting)
                require(code == 0 and output.count('No live certification ran') == 1
                        and 'skipped=1' in output, name+' must explicitly skip exactly one live case')
            code, output = probe('required-absent', single, '1')
            require(code == 1 and 'AC-7: actual isolated installed acceptance has not run' in output
                    and 'skipped' not in output.lower(), 'Required missing evidence must fail without skipping')
        finally:
            if held.exists():
                if RECORD.exists() or RECORD.is_symlink():
                    raise RuntimeError('Retained record path changed during probes; original preserved at '+str(held))
                held.rename(RECORD)
        require(hashlib.sha256(RECORD.read_bytes()).hexdigest() == original_hash, 'Restored live record changed')
        code, output = probe('required-present', single, '1')
        require(code == 0 and 'skipped' not in output.lower() and 'Ran 1 test' in output,
                'Required retained live case must pass without skipping')
        driver = [sys.executable, str(ROOT/'docs/154/run-release-certification.py')]
        code, output = probe('driver-unset-present', driver, None)
        require(code == 1 and 'must be exactly 1' in output, 'Driver must reject absent certification mode')
        # Protocol-only injection: this deliberately skipped synthetic case never
        # substitutes for installed acceptance and cannot create certification.
        synthetic = '''import importlib.util, pathlib, unittest
from unittest.mock import patch
path=pathlib.Path('docs/154/run-release-certification.py')
spec=importlib.util.spec_from_file_location('certification_driver_protocol',path)
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
class SyntheticProtocolOnly(unittest.TestCase):
 def test_actual_isolated_installed_six_stage_run_and_repeat(self):
  self.skipTest('Synthetic protocol regression only; no live certification ran')
print('SYNTHETIC SKIP PROTOCOL REGRESSION; NOT LIVE CERTIFICATION',flush=True)
suite=unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticProtocolOnly)
with patch.object(driver,'load_suite',return_value=suite):
 raise SystemExit(driver.main())
'''
        code, output = probe('synthetic-skipped-live-method', [sys.executable, '-c', synthetic], '1')
        require(code == 1 and 'skipped=1' in output and 'Certification failed: installed acceptance was skipped' in output,
                'Driver must reject a synthetic skipped live method despite unittest success')
        with (results/'RESULT.json').open('x') as stream:
            json.dump(dict(kind='certification-mode-protocol-regression', status='pass',
                           original_live_record_sha256=original_hash, probes=observations), stream, indent=2)
        print('Certification mode protocol checks passed; synthetic injection certified no run.')
        return 0
    finally:
        for number, handler in prior_handlers.items():
            signal.signal(number, handler)


if __name__ == '__main__':
    raise SystemExit(main())
