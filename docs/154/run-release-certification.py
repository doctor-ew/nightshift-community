#!/usr/bin/env python3
"""Run the complete release suite with mandatory installed acceptance."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
LIVE_METHOD = 'test_actual_isolated_installed_six_stage_run_and_repeat'
MODE_KEY = 'NIGHTSHIFT_REQUIRE_INSTALLED_ACCEPTANCE'


def load_suite():
    specification = importlib.util.spec_from_file_location('release_certification_tests', ROOT/'tests/test-release-inputs.py')
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return unittest.defaultTestLoader.loadTestsFromModule(module)


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def run_suite(suite):
    """Reject a missing or skipped live case independently of unittest success."""
    live_cases = [case for case in cases(suite) if getattr(case, '_testMethodName', None) == LIVE_METHOD]
    if len(live_cases) != 1:
        print('Certification failed: exactly one installed acceptance test is required.', file=sys.stderr)
        return 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    live_skipped = [(case, reason) for case, reason in result.skipped
                    if getattr(case, '_testMethodName', None) == LIVE_METHOD]
    if live_skipped:
        print('Certification failed: installed acceptance was skipped; no live certification ran.', file=sys.stderr)
    return 0 if result.wasSuccessful() and not live_skipped else 1


def main():
    if os.environ.get(MODE_KEY) != '1':
        print(MODE_KEY+' must be exactly 1; no live certification ran.', file=sys.stderr)
        return 1
    return run_suite(load_suite())


if __name__ == '__main__':
    raise SystemExit(main())
