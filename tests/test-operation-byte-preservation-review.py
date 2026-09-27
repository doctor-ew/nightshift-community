#!/usr/bin/env python3
"""Independent exact-byte and mode regression for accepted UTF-8 patches."""
import difflib
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('byte_review_fixtures', Path(__file__).with_name('test-operations.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m


class BytePreservationReview(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nightshift-byte-review-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        f.fixture(self.root)
        self.path = self.root/'spec.md'
        self.path.chmod(0o640)
        self.expected = 'Return two with retained UTF-8: café.\r\nSecond line.\r\n'.encode('utf-8')
        self.worker = f.Worker()
        self.worker.patch = ''.join(difflib.unified_diff(self.path.read_text().splitlines(True),
            self.expected.decode('utf-8').splitlines(True), fromfile='a/spec.md', tofile='b/spec.md'))
        self.c = m.Operations(self.root, 'demo', self.worker)
        assessed = self.c.assess('groom-spec')
        self.grant = self.c.authorize(['groom-spec'], assessed['binding'], 'synthetic', 'byte-preservation')['id']

    def assert_preserved(self, controller):
        self.assertEqual(self.path.read_bytes(), self.expected)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o640)
        self.assertEqual(controller.state['results']['groom-spec']['outputs']['spec.md'], m.sha(self.path))
        self.assertEqual(len(self.worker.calls), 1)

    def test_crlf_utf8_bytes_and_existing_mode_survive_patch_and_replay(self):
        result = self.c.execute(self.grant, 'groom-spec', 'draft-bytes')
        self.assertEqual(result['status'], 'passed', result)
        self.assert_preserved(self.c)
        resumed = m.Operations(self.root, 'demo', self.worker)
        self.assertIn(resumed.execute(self.grant, 'groom-spec', 'draft-bytes')['status'], ('passed', 'reused'))
        self.assert_preserved(resumed)

    def test_checkpoint_restart_integrates_identical_crlf_bytes_once(self):
        def interrupted(*args):
            raise KeyboardInterrupt('synthetic interruption before patch integration')
        self.c.finalize = interrupted
        with self.assertRaises(KeyboardInterrupt):
            self.c.execute(self.grant, 'groom-spec', 'checkpoint-bytes')
        self.assertEqual(len(self.worker.calls), 1)
        self.assertNotEqual(self.path.read_bytes(), self.expected)
        resumed = m.Operations(self.root, 'demo', self.worker)
        self.assertEqual(resumed.execute(self.grant, 'groom-spec', 'checkpoint-bytes')['status'], 'passed')
        self.assert_preserved(resumed)


if __name__ == '__main__':
    unittest.main()
