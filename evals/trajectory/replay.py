#!/usr/bin/env python3
"""Compare offline observations to a reviewed baseline; never rewrite it."""
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('trajectory', ROOT / 'scripts/nightshift-trajectory.py')
trajectory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trajectory)


def main():
    parser = trajectory.SafeParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=Path(__file__).with_name('baseline.json'))
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                trajectory.require(key not in result)
                result[key] = value
            return result
        baseline = json.loads(args.baseline.read_text(), object_pairs_hook=unique)
        trajectory.require(type(baseline) is dict and set(baseline) == set(trajectory.SCENARIOS))
        for expected in baseline.values():
            trajectory.validate(expected)
    except Exception:
        print('replay: invalid baseline', file=sys.stderr)
        return 1
    failed = False
    for scenario in trajectory.SCENARIOS:
        try:
            actual = trajectory.record(scenario, args.root)
            matches = actual == baseline[scenario]
        except Exception:
            matches = False
        print(scenario + (': matching' if matches else ': mismatch'))
        failed |= not matches
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
