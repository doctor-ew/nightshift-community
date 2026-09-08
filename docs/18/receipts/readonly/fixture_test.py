#!/usr/bin/env python3
import json, sys, unittest
args = sys.argv[1:]
print("NIGHTSHIFT_FIXTURE_ARGV=" + json.dumps(args), flush=True)
class ExactInvocation(unittest.TestCase):
    def test_arguments(self):
        self.assertEqual(args, ["--label", "two words", "--mode", "exact"])
unittest.main(argv=[sys.argv[0]], verbosity=2)
