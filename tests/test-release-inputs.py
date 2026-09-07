import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/nightshift-update.py"
spec = importlib.util.spec_from_file_location("updater", SCRIPT)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class ReleaseInputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base / "remote"
        self.local = self.base / "local"
        self.run_git(self.base, "init", "-q", "-b", "main", str(self.remote))
        self.run_git(self.remote, "config", "user.name", "Test")
        self.run_git(self.remote, "config", "user.email", "test@example.invalid")
        (self.remote / "VERSION").write_text("0.1.0\n")
        self.commit()
        self.run_git(self.base, "clone", "-q", str(self.remote), str(self.local))
        self.data = {"source": str(self.remote), "channel": "stable"}

    def run_git(self, cwd, *args):
        return subprocess.check_output(["git", "-C", str(cwd), *args], text=True, stderr=subprocess.PIPE).strip()

    def commit(self):
        self.run_git(self.remote, "add", ".")
        self.run_git(self.remote, "commit", "-qm", "fixture")

    def release(self, version="0.2.0"):
        (self.remote / "VERSION").write_text(version + "\n")
        self.commit()
        self.run_git(self.remote, "tag", "v" + version)

    def test_stable_update_and_dirty_guard(self):
        self.release()
        (self.local / "unfinished").write_text("preserve")
        self.assertEqual(updater.update(self.local, self.data, True)["status"], "deferred-dirty-or-development-checkout")
        (self.local / "unfinished").unlink()
        self.assertEqual(updater.update(self.local, self.data, True)["status"], "updated")
        self.assertEqual((self.local / "VERSION").read_text(), "0.2.0\n")

    def test_check_never_applies_and_version_order(self):
        self.release("0.9.0")
        self.release("0.10.0")
        result = updater.update(self.local, self.data, False)
        self.assertEqual(result["ref"], "refs/tags/v0.10.0")
        self.assertEqual((self.local / "VERSION").read_text(), "0.1.0\n")

    def test_no_release_or_mismatched_tag(self):
        with self.assertRaises(ValueError):
            updater.select(self.local, self.data)
        self.run_git(self.remote, "tag", "v9.0.0")
        with self.assertRaises(ValueError):
            updater.select(self.local, self.data)

    def test_branch_explicit_and_feature_preserved(self):
        self.release()
        self.run_git(self.local, "switch", "-c", "feature")
        self.assertEqual(updater.update(self.local, self.data, True)["status"], "deferred-dirty-or-development-checkout")
        result = updater.select(self.local, {**self.data, "channel": "branch:main"})
        self.assertEqual(result[1], "refs/heads/main")

    def test_active_run_defers_apply(self):
        self.release()
        with (self.local / ".git/nightshift-update.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            result = subprocess.run(["python3", str(SCRIPT), "--project", str(self.local),
                                     "--source", str(self.remote), "--apply"],
                                    env={**os.environ, "NIGHTSHIFT_HOME": str(self.base / "home")},
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 75)
            self.assertIn("active run", result.stderr)
        self.assertEqual((self.local / "VERSION").read_text(), "0.1.0\n")

    def test_adapter_failure_keeps_retry_receipt(self):
        (self.remote / "install.sh").write_text("#!/bin/sh\nexit 1\n")
        self.release()
        data = {**self.data, "install_args": ["--runtime", "all"]}
        with self.assertRaises(RuntimeError):
            updater.update(self.local, data, True)
        self.assertTrue((self.local / ".git/nightshift-install-pending.json").exists())

    def test_configurable_source_and_channel(self):
        env = {**os.environ, "NIGHTSHIFT_HOME": str(self.base / "home")}
        subprocess.run(["python3", str(SCRIPT), "--project", str(self.local),
                        "--configure", "--source", str(self.remote),
                        "--channel", "branch:main"], env=env, check=True, capture_output=True)
        data = json.loads((self.base / "home/updates.json").read_text())
        self.assertEqual(data, {"source": str(self.remote), "channel": "branch:main"})

    def test_spec_no_external_cli_and_stable_identity(self):
        path = self.local / "agent idea.md"
        path.write_text("# Coach\nBuild a coach.\n")
        def resolve(ref, cwd=self.local):
            return json.loads(subprocess.check_output(["bash", str(ROOT / "scripts/nightshift-ticket-source.sh"), ref], cwd=cwd, text=True))
        first = resolve("agent idea.md")
        self.assertEqual(first, resolve("spec:agent idea.md"))
        path.write_text("# Coach\nChanged requirements.\n")
        changed = resolve(str(path))
        self.assertEqual(first["source_id"], changed["source_id"])
        self.assertNotEqual(first["source_revision"], changed["source_revision"])
        worktree = self.base / "isolated"
        self.run_git(self.local, "worktree", "add", "--detach", str(worktree))
        self.assertEqual(resolve(str(path), worktree), changed)
        outside = self.base / "outside.md"
        outside.write_text("# Outside")
        with self.assertRaises(subprocess.CalledProcessError):
            resolve("spec:" + str(outside))


if __name__ == "__main__":
    unittest.main()
