import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dashboard_start', ROOT / 'scripts/nightshift-dashboard-start.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Startup(unittest.TestCase):
    def test_start_reuse_restart_and_project_isolation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'NIGHTSHIFT_HOME': directory}), patch.object(module.webbrowser, 'open') as browser:
            first_project = Path(directory) / 'first'
            second_project = Path(directory) / 'second'
            first_project.mkdir()
            second_project.mkdir()
            children = set()
            try:
                first = module.start(first_project, 'once', 0)
                children.add(first['pid'])
                self.assertEqual(first['status'], 'started')
                self.assertEqual(browser.call_count, 1)
                self.assertTrue(module.belongs(first['url'], first_project))
                self.assertFalse(module.belongs(first['url'], second_project))
                reused = module.start(first_project, 'once', 0)
                self.assertEqual(reused['url'], first['url'])
                self.assertEqual(reused['status'], 'reused')
                self.assertEqual(browser.call_count, 1)
                port = int(first['url'].rsplit(':', 1)[1])
                other = module.start(second_project, 'off', port)
                children.add(other['pid'])
                self.assertNotEqual(first['url'], other['url'])
                os.kill(first['pid'], signal.SIGTERM)
                module.CHILDREN.pop(first['pid']).wait(timeout=5)
                children.remove(first['pid'])
                restarted = module.start(first_project, 'off', 0)
                children.add(restarted['pid'])
                self.assertEqual(restarted['status'], 'started')
                self.assertEqual(browser.call_count, 1)
            finally:
                for pid in children:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        module.CHILDREN.pop(pid).wait(timeout=5)
                    except ProcessLookupError:
                        pass

    def test_untrusted_url_rejected(self):
        for url in ('https://example.invalid', 'http://localhost:8765', 'file:///tmp/x', 'http://127.0.0.1:8765/path'):
            self.assertFalse(module.belongs(url, Path('/tmp')))


if __name__ == '__main__':
    unittest.main()
