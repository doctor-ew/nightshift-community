#!/usr/bin/env python3
"""Black-box acceptance tests for dp-g51; fixtures never call real beads/providers."""
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts/nightshift-harness-audit.sh"
CRON = ROOT / "scripts/nightshift-harness-audit-cron.sh"
CATEGORIES = {"tool_coverage", "context_efficiency", "quality_gates", "memory_persistence", "eval_coverage", "security_guardrails", "cost_efficiency"}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nightshift-audit-test-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.project = self.base / "project"
        self.project.mkdir()
        for name in ("scripts", "commands", "agents", "tests", "skills"):
            shutil.copytree(ROOT / name, self.project / name)
        for name in ("routing.json", "nightshift.toml", "README.md", "AGENTS.md"):
            shutil.copy2(ROOT / name, self.project / name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.db = self.base / "beads.json"
        self.db.write_text("[]")
        self.cache = self.base / "cache"
        self.cache.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home / ".codex"),
                        NIGHTSHIFT_CACHE_DIR=str(self.cache), NIGHTSHIFT_AUDIT_NOW="2026-09-01T09:00:00Z",
                        TEST_BD_DB=str(self.db), PATH=str(self.bin) + os.pathsep + os.environ["PATH"])
        self.env.pop("CLAUDE_PROJECT_DIR", None)
        bd = self.bin / "bd"
        bd.write_text("#!" + shutil.which("python3") + "\n" + r'''import json, os, sys
from pathlib import Path
p=Path(os.environ["TEST_BD_DB"])
a=sys.argv[1:]
if "--version" in a: print("bd test"); sys.exit(0)
if os.environ.get("TEST_BD_FAIL"): print("fixture failure", file=sys.stderr); sys.exit(1)
if a[0] == "list":
    if os.environ.get("TEST_BD_MALFORMED"): print("broken-json"); sys.exit(0)
    print(p.read_text()); sys.exit(0)
if a[0] == "create":
    rows=json.loads(p.read_text())
    ref=a[a.index("--external-ref")+1]
    row={"id":"test-"+str(len(rows)+1),"external_ref":ref,"status":"open"}
    rows.append(row); p.write_text(json.dumps(rows))
    if os.environ.get("TEST_BD_CREATE_NO_ID"): print("{}"); sys.exit(0)
    print(json.dumps(row) if "--json" in a else row["id"]); sys.exit(0)
raise SystemExit("unexpected bd invocation " + repr(a))
''')
        bd.chmod(0o755)
        # Prevent helper probes from contacting a real server/provider during --refresh.
        for tool in ("gh", "claude", "codex", "ollama"):
            f = self.bin / tool
            f.write_text("#!/bin/sh\nexit 1\n")
            f.chmod(0o755)
        self.cache.joinpath("capabilities").write_text(
            'NIGHTSHIFT_PROBE_TIME="' + str(int(datetime.datetime.now().timestamp())) + '"\n' +
            'NIGHTSHIFT_BD="' + str(bd) + '"\nNIGHTSHIFT_PYTHON3="python3"\nNIGHTSHIFT_JQ="jq"\n')

    def run_audit(self, *args, ok=True, env=None):
        self.assertTrue(AUDIT.is_file(), "AC1: audit entrypoint must exist")
        proc = subprocess.run(["bash", str(AUDIT), "--project", str(self.project), *args],
                              env=env or self.env, cwd=self.base, text=True, capture_output=True, timeout=30)
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        else:
            self.assertNotEqual(proc.returncode, 0, "expected a visible failure")
        if proc.stdout.strip():
            row = json.loads(proc.stdout)
            self.assertEqual(len(proc.stdout.splitlines()), 1)
            return row
        return None

    def history(self):
        legacy = self.project / ".claude/task-progress/harness-history.jsonl"
        return legacy if legacy.exists() else self.project / ".nightshift/harness-history.jsonl"

    def seed(self, scores=None, stamp="2026-08-01T09:00:00Z", status="not_requested"):
        row = self.run_audit()
        row["timestamp"] = stamp
        if scores is not None:
            row["scores"] = scores
        row["bead"] = {"status": status}
        self.history().write_text(json.dumps(row) + "\n")
        return row

    def test_stale_aliases_do_not_claim_unrelated_products(self):
        commands = self.home / '.claude/commands'
        commands.mkdir(parents=True)
        (commands / 'nightshift-eng.md').write_text('Canonical Nightshift command')
        (commands / 'unrelated-eng.md').write_text('Independent workflow')
        self.assertTrue(self.run_audit()['doctor']['stale_instructions']['ok'])
        (commands / 'retired-eng.md').write_text('Nightshift command with divergent instructions')
        self.assertFalse(self.run_audit()['doctor']['stale_instructions']['ok'])

    def test_static_schema_and_history(self):
        row = self.run_audit()
        self.assertEqual(set(row["scores"]), CATEGORIES)
        self.assertEqual(set(row["checks"]), CATEGORIES)
        self.assertEqual(row["task"], "harness-audit")
        self.assertEqual(row["mode"], "audit")
        self.assertFalse(row["cache_hit"])
        self.assertEqual(row["schema_version"], 1)
        for cat in CATEGORIES:
            self.assertEqual(len(row["checks"][cat]), 2)
            self.assertTrue(all(type(v) is bool for v in row["checks"][cat].values()))
            self.assertEqual(row["scores"][cat], sum(row["checks"][cat].values()) * 5)
            self.assertEqual(row["counts"][cat], {"BLOCK": 0, "WARN": 2 - sum(row["checks"][cat].values()), "NOTE": 0})
        self.assertEqual(json.loads(self.history().read_text()), row)
        changed = dict(self.env, NIGHTSHIFT_AUDIT_NOW="2026-09-02T09:00:00Z")
        again = self.run_audit("--refresh", env=changed)
        self.assertEqual(row["scores"], again["scores"])
        self.assertEqual(again["deltas"], dict.fromkeys(CATEGORIES, 0))
        self.assertEqual(len(self.history().read_text().splitlines()), 2)
        self.assertIn("ok", row["doctor"])

    def test_artifact_loss_and_external_symlink(self):
        row = self.run_audit()
        f = self.project / "scripts/nightshift-spec-digest.sh"
        f.write_text("")
        changed = self.run_audit()
        self.assertFalse(changed["checks"]["context_efficiency"]["digest"])
        self.assertEqual(changed["scores"]["context_efficiency"], row["scores"]["context_efficiency"] - 5)
        for cat in CATEGORIES - {"context_efficiency"}:
            self.assertEqual(changed["scores"][cat], row["scores"][cat])
        f.unlink()
        f.symlink_to(ROOT / "scripts/nightshift-spec-digest.sh")
        self.assertFalse(self.run_audit()["checks"]["context_efficiency"]["digest"])

    def test_each_static_artifact_and_routing_shape(self):
        baseline = self.run_audit()
        self.assertEqual(baseline["scores"], dict.fromkeys(CATEGORIES, 10))
        for name in ("scripts/nightshift-capability.sh", "scripts/nightshift-agent.sh",
                     "scripts/nightshift-context-check.sh", "scripts/nightshift-spec-digest.sh",
                     "commands/nightshift-review.md", "commands/nightshift-drift.md",
                     "scripts/nightshift-state-dir.sh", "tests/test-state-dir.sh",
                     "tests/test-agent-dispatch.sh", "scripts/nightshift-scope-freeze.sh",
                     "scripts/nightshift-spec-guardrail.sh", "routing.json"):
            f = self.project / name
            original = f.read_bytes()
            f.write_text("")
            changed = self.run_audit()
            self.assertLess(sum(changed["scores"].values()), 70, name)
            f.write_bytes(original)
        routing = self.project / "routing.json"
        for value in ([], {"roles": {}}, {"roles": {"bad": {"gears": []}}}):
            routing.write_text(json.dumps(value))
            row = self.run_audit()
            self.assertFalse(row["checks"]["cost_efficiency"]["routing_gears"])

    def test_history_shape_nonfinite_and_input_validation(self):
        row = self.run_audit()
        variants = []
        for field, value in (("schema_version", 2), ("mode", "unknown"), ("scores", {}),
                             ("checks", {}), ("counts", {}), ("timestamp", "2026-02-30T00:00:00Z")):
            bad = dict(row)
            bad[field] = value
            variants.append(bad)
        for score in (True, float("nan"), float("inf"), -1, 11):
            bad = dict(row, scores=dict(row["scores"], tool_coverage=score))
            variants.append(bad)
        for bad in variants:
            raw = json.dumps(bad) + "\n"
            self.history().write_text(raw)
            self.run_audit(ok=False)
            self.assertEqual(self.history().read_text(), raw)
        self.history().write_text("")
        for args in (("--unknown",), ("--project",), ("--project", str(self.base / "absent"))):
            proc = subprocess.run(["bash", str(AUDIT), *args], env=self.env,
                                  text=True, capture_output=True, timeout=15)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(self.history().read_text(), "")

    def test_legacy_history(self):
        legacy = self.project / ".claude/task-progress"
        legacy.mkdir(parents=True)
        self.run_audit()
        self.assertTrue((legacy / "harness-history.jsonl").is_file())
        self.assertFalse((self.project / ".nightshift/harness-history.jsonl").exists())

    def test_malformed_history_and_invalid_clock(self):
        self.run_audit()
        for bad in ("{truncated", '{"scores":{}}\n'):
            self.history().write_text(bad)
            self.run_audit(ok=False)
            self.assertEqual(self.history().read_text(), bad)
        self.history().write_text("")
        self.run_audit(ok=False, env=dict(self.env, NIGHTSHIFT_AUDIT_NOW="2026-02-30T09:00:00Z"))
        self.assertEqual(self.history().read_text(), "")

    def test_monthly_threshold_and_idempotence(self):
        digest = self.project / "scripts/nightshift-spec-digest.sh"
        original = digest.read_text()
        digest.write_text("")
        current = self.run_audit()["scores"]
        # Seed a genuine one-point decline: 6 -> 5 for context efficiency.
        prior = dict(current)
        prior["context_efficiency"] += 1
        self.seed(prior)
        row = self.run_audit("--monthly")
        self.assertEqual(row["bead"]["status"], "not_needed")
        self.assertEqual(json.loads(self.db.read_text()), [])
        self.assertEqual(row["deltas"]["context_efficiency"], -1)
        digest.write_text(original)
        self.seed()
        digest.write_text("")
        row = self.run_audit("--monthly")
        self.assertEqual(row["bead"]["status"], "created")
        self.assertEqual(row["deltas"]["context_efficiency"], -5)
        again = self.run_audit("--monthly")
        self.assertEqual(again["bead"]["status"], "existing")
        self.assertEqual(len(json.loads(self.db.read_text())), 1)

    def test_rollover_missing_month_and_future_samples(self):
        self.seed(stamp="2025-12-15T09:00:00Z")
        (self.project / "scripts/nightshift-spec-digest.sh").write_text("")
        row = self.run_audit("--monthly", env=dict(self.env, NIGHTSHIFT_AUDIT_NOW="2026-01-01T09:00:00Z"))
        self.assertEqual(row["deltas"]["context_efficiency"], -5)
        self.assertEqual(row["bead"]["status"], "created")
        self.seed(stamp="2026-07-31T09:00:00Z")
        self.assertTrue(all(v is None for v in self.run_audit("--monthly")["deltas"].values()))
        self.seed(stamp="2026-10-01T09:00:00Z")
        self.assertTrue(all(v is None for v in self.run_audit()["deltas"].values()))

    def test_pending_retry_and_interrupted_create(self):
        self.seed()
        (self.project / "scripts/nightshift-spec-digest.sh").write_text("")
        for failure in ("TEST_BD_FAIL", "TEST_BD_MALFORMED"):
            row = self.run_audit("--monthly", ok=False, env=dict(self.env, **{failure: "1"}))
            self.assertEqual(row["bead"]["status"], "pending")
            self.assertEqual(row["deltas"]["context_efficiency"], -5)
        row = self.run_audit("--monthly", ok=False, env=dict(self.env, TEST_BD_CREATE_NO_ID="1"))
        self.assertEqual(row["bead"]["status"], "pending")
        row = self.run_audit("--monthly")
        self.assertEqual(row["bead"]["status"], "existing")
        self.assertEqual(len(json.loads(self.db.read_text())), 1)

    def test_closed_bead_and_concurrent_idempotence(self):
        self.seed()
        (self.project / "scripts/nightshift-spec-digest.sh").write_text("")
        closed = {"id": "test-closed", "external_ref": "nightshift:harness-audit:2026-09", "status": "closed"}
        self.db.write_text(json.dumps([closed]))
        self.assertEqual(self.run_audit("--monthly")["bead"]["status"], "existing")
        self.seed()
        (self.project / "scripts/nightshift-context-check.sh").write_text("")
        self.db.write_text("[]")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            rows = list(executor.map(lambda _: self.run_audit("--monthly"), range(3)))
        self.assertEqual(len(json.loads(self.db.read_text())), 1)
        self.assertEqual(sum(r["bead"]["status"] == "created" for r in rows), 1)

    def test_project_commands_never_execute(self):
        marker = self.base / "injected"
        routing = json.loads((self.project / "routing.json").read_text())
        routing["providers"]["codex"]["cmd"] = "touch " + str(marker)
        (self.project / "routing.json").write_text(json.dumps(routing))
        (self.project / "scripts/nightshift-manifest-validate.sh").write_text("#!/bin/sh\ntouch " + str(marker) + "\n")
        self.run_audit()
        self.assertFalse(marker.exists())

    def test_cron_captured_path_with_both_quotes(self):
        # Crontab env grammar closes a quoted value at the first matching quote.
        # Cronie src/env.c VALUE/FINI states; this catches shell-vs-cron quoting.
        special = self.base / "path with ' single and \" double % dollar $ "
        special.mkdir()
        captured = self.base / "captured-path.json"
        wrapper = special / "python3"
        wrapper.write_text("#!" + shutil.which("python3") + "\n" +
                           "import os,sys,json\nfrom pathlib import Path\n" +
                           "Path(" + repr(str(captured)) + ").write_text(json.dumps(os.environ['PATH']))\n" +
                           "os.execv(" + repr(shutil.which("python3")) + ", [" +
                           repr(shutil.which("python3")) + "] + sys.argv[1:])\n")
        wrapper.chmod(0o755)
        exact_path = str(special) + os.pathsep + self.env["PATH"] + os.pathsep + str(special)
        env = dict(self.env, PATH=exact_path)
        proc = subprocess.run(["bash", str(CRON), "--project", str(self.project)],
                              env=env, text=True, capture_output=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        assignment, scheduled = proc.stdout.splitlines()
        self.assertTrue(assignment.startswith("PATH="))
        value = assignment.split("=", 1)[1].lstrip()
        if value and value[0] in "\"'":
            closing = value.find(value[0], 1)
            self.assertGreater(closing, 0)
            self.assertEqual(value[closing + 1:].strip(), "", "invalid crontab PATH assignment")
            bootstrap = value[1:closing]
        else:
            bootstrap = value.rstrip()
        # Ignore the generator interpreter: prove the scheduled process sees PATH.
        captured.unlink()
        # The printed assignment is the only PATH available to the scheduled shell.
        command = scheduled[len("0 9 1 * * "):].replace(r"\%", "%")
        result = subprocess.run(["/bin/sh", "-c", command], cwd=self.base,
                                env=dict(self.env, PATH=bootstrap), text=True,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(captured.read_text()), exact_path)
        self.assertEqual(json.loads(result.stdout)["mode"], "monthly")

    def test_cron_roundtrip_and_reject_newline(self):
        self.assertTrue(CRON.is_file(), "AC7: scheduler generator must exist")
        weird = self.base / "quote ' dollar $ and percent % project"
        self.project.rename(weird)
        self.project = weird
        proc = subprocess.run(["bash", str(CRON), "--project", str(weird)], env=self.env,
                              text=True, capture_output=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("PATH="))
        self.assertTrue(lines[1].startswith("0 9 1 * * "))
        command = lines[1][len("0 9 1 * * "):]
        self.assertNotRegex(command, r"(?<!\\)%")
        # cron unescapes protected percentages before invoking the shell.
        command = command.replace(r"\%", "%")
        run = subprocess.run(["sh", "-c", command], cwd=self.base, env=self.env,
                             text=True, capture_output=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(json.loads(run.stdout)["mode"], "monthly")
        bad = subprocess.run(["bash", str(CRON), "--project", "bad\npath"], env=self.env,
                             text=True, capture_output=True, timeout=15)
        self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
