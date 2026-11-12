import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

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
        environment = patch.dict(os.environ, {"NIGHTSHIFT_HOME": str(self.base / "runtime")})
        environment.start()
        self.addCleanup(environment.stop)
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

    def test_repair_failure_has_no_exhaustion_ceiling(self):
        home = self.base / "runtime"
        home.mkdir()
        self.assertTrue(updater.needs_repair())
        source = self.base / "helper"
        source.write_text("ok")
        link = self.base / "installed"
        link.symlink_to(source)
        (home / "install-links.json").write_text(json.dumps({str(link): str(source)}))
        self.assertFalse(updater.needs_repair())
        link.unlink()
        self.assertTrue(updater.needs_repair())
        with patch.object(updater.subprocess, "run", side_effect=subprocess.CalledProcessError(74, "installer")) as runner:
            with self.assertRaises(RuntimeError):
                updater.refresh_install(self.local, ["--repair"])
            self.assertEqual(runner.call_count, 1)
            for _ in range(4):
                with self.assertRaises(RuntimeError):
                    updater.refresh_install(self.local, ["--repair"])
            self.assertEqual(runner.call_count, 5)
        receipt = json.loads((home / "update-repair.json").read_text())
        self.assertEqual(receipt["attempts"], 5)
        self.assertEqual(receipt["status"], "failed")

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

    def test_optional_healing_failure_does_not_block_source_run(self):
        env = {"source": str(self.remote), "channel": "stable", "install_args": ["--repair"]}
        child = unittest.mock.Mock()
        child.wait.return_value = 0
        with patch.object(updater, "settings", return_value=env), \
                patch.object(updater, "update"), \
                patch.object(updater, "git", return_value=str(self.local / ".git")), \
                patch.object(updater, "needs_repair", return_value=True), \
                patch.object(updater, "refresh_install", side_effect=RuntimeError("retained conflict")), \
                patch.object(updater.subprocess, "Popen", return_value=child) as launch, \
                patch.object(updater.signal, "signal"), \
                patch.object(updater.sys, "argv", [str(SCRIPT), "--project", str(self.local), "--run", "gh:154"]):
            self.assertEqual(updater.main(), 0)
        self.assertEqual(launch.call_args.args[0][-1], "gh:154")



class InstalledAcceptance(unittest.TestCase):
    def test_selected_runtime_inventory_is_distinct_from_path_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / 'consumer'; project.mkdir()
            home = base / 'saved-state'; home.mkdir()
            older = base / 'older-bin'; older.mkdir()
            executable = older / 'nightshift'
            executable.write_text('#!/bin/sh\nexit 99\n'); executable.chmod(0o755)
            (home / 'updates.json').write_text(json.dumps({'source': updater.COMMUNITY, 'channel': 'branch:fixture'}))
            (project / 'routing.json').write_bytes((ROOT / 'routing.json').read_bytes())
            (project / '.nightshift.toml').write_text('[providers]\nrouting_file = "routing.json"\n[runtime]\nprovider = "codex"\nmodel = "fixture-author"\n')
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith('NIGHTSHIFT_') and key != 'CLAUDE_PROJECT_DIR'}
            environment.update(NIGHTSHIFT_HOME=str(home), NIGHTSHIFT_SYNC_CHECK='off',
                               NIGHTSHIFT_UPDATE_GUARD='1', NIGHTSHIFT_DASHBOARD='off',
                               NIGHTSHIFT_OUTPUT='verbose', PATH=str(older)+os.pathsep+os.environ['PATH'])
            result = subprocess.run(['bash', str(ROOT / 'scripts/nightshift-factory.sh'), 'inventory',
                                     '--project', str(project)], env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, 'AC-1: read-only inventory is missing: '+result.stderr[-1200:])
            report = json.loads(result.stdout)
            self.assertEqual(Path(report['invoked_executable']).resolve(), ROOT / 'scripts/nightshift-factory.sh')
            self.assertEqual(Path(report['path_executable']).resolve(), executable)
            self.assertNotEqual(report['invoked_executable'], report['path_executable'])
            self.assertEqual(Path(report['resolved_source_checkout']).resolve(), ROOT)
            self.assertEqual(report['revision'], subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip())
            self.assertEqual(report['install_channel'], 'branch:fixture')
            self.assertEqual(report['effective_stage_runtime']['product']['provider'], 'codex')
            self.assertEqual(report['effective_stage_runtime']['product']['model'], 'fixture-author')
            self.assertNotEqual(report['effective_stage_runtime']['adversarial']['provider'], 'codex')
            self.assertEqual(report['certification'], 'not-established')

    def test_draft_and_forged_completion_expose_recovery_without_false_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'consumer'; project.mkdir()
            subprocess.run(['git','-C',str(project),'init','-q'],check=True)
            (project/'routing.json').write_bytes((ROOT/'routing.json').read_bytes())
            (project/'.nightshift.toml').write_text('[providers]\nrouting_file = "routing.json"\n[runtime]\nprovider = "codex"\nmodel = "fixture-author"\n')
            directory=project/'.git/nightshift/pipeline/154'; directory.mkdir(parents=True)
            state={'version':1,'task':'154','worktree':str(project),'status':'blocked','next_action':'product',
                   'request':'gh:doctor-ew/nightshift-community#154','completed':{},'findings':[],'attempts':[],'history':[]}
            environment={k:v for k,v in os.environ.items() if not k.startswith('NIGHTSHIFT_') and k!='CLAUDE_PROJECT_DIR'}
            home=project/'saved-state';home.mkdir()
            environment.update(NIGHTSHIFT_HOME=str(home),NIGHTSHIFT_UPDATE_GUARD='1',NIGHTSHIFT_SYNC_CHECK='off',NIGHTSHIFT_OUTPUT='verbose')
            for status in ('blocked','complete'):
                with self.subTest(recorded_status=status):
                    state['status']=status
                    (directory/'state.json').write_text(json.dumps(state))
                    result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'inventory','--project',str(project),'--task','154'],env=environment,capture_output=True,text=True)
                    self.assertEqual(result.returncode,0,'AC-9: inspection must not dispatch or require a source run: '+result.stderr[-500:])
                    recovery=json.loads(result.stdout)['recovery']
                    self.assertNotEqual(recovery['status'],'complete','AC-9: empty completion claim cannot pass')
                    self.assertTrue(recovery['next_action'])
                    self.assertIn(state['request'],recovery['resume_command'])
                    self.assertIn(str(project),recovery['resume_command'])
                    self.assertIn(str(ROOT/'scripts/nightshift-factory.sh'),recovery['resume_command'])

    def test_public_claims_distinguish_certification_boundaries(self):
        for name in ('README.md', 'slides/saturday.md', 'slides/tuesday.md'):
            with self.subTest(path=name):
                content = (ROOT / name).read_text()
                lower = content.lower()
                for category in ('source', 'temporary', 'activat', 'certif'):
                    self.assertIn(category, lower, 'AC-8: missing provenance category in '+name)
                self.assertNotIn(str(Path.home()), content, 'AC-8: personal checkout path in public content')
                self.assertNotIn('NIGHTSHIFT_PRIVATE_CONSUMER_SENTINEL_154', content)

    def test_actual_isolated_installed_six_stage_run_and_repeat(self):
        record = ROOT / '.nightshift/154-live-acceptance.json'
        self.assertTrue(record.is_file(), 'AC-7: actual isolated installed acceptance has not run')
        evidence = json.loads(record.read_text())
        self.assertEqual(evidence['version'], 1)
        candidate = Path(evidence['source_checkout']).resolve(strict=True)
        revision = subprocess.check_output(['git','-C',str(candidate),'rev-parse','HEAD'],text=True).strip()
        self.assertEqual(revision, evidence['candidate_revision'])
        self.assertEqual(Path(evidence['installed_executable']).resolve(), candidate / 'scripts/nightshift-factory.sh')
        for relative in ('scripts/nightshift-factory.sh','scripts/nightshift-update.py','scripts/nightshift-pipeline.py'):
            self.assertEqual((candidate / relative).read_bytes(), (ROOT / relative).read_bytes())
        module_spec = importlib.util.spec_from_file_location('installed_acceptance_pipeline', candidate / 'scripts/nightshift-pipeline.py')
        pipeline = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(pipeline)
        project = Path(evidence['consumer_project']).resolve(strict=True)
        state = pipeline.snapshot(project, evidence['task'])
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(set(state['completed']), set(pipeline.STAGES))
        target = Path(state['worktree'])
        for stage, item in state['completed'].items():
            self.assertEqual(pipeline.sha(item['receipt']), item['sha256'])
            self.assertEqual(item['input_sha256'], pipeline.inputs(target,evidence['task'],stage,state))
            self.assertEqual(pipeline.validate_receipt(item['receipt'],evidence['task'],stage,target)['status'],'pass')
        for gate in ('development','final'):
            self.assertEqual(pipeline.proof(target,evidence['task'],gate)['outcome'],'pass')
        environment={k:v for k,v in os.environ.items() if not k.startswith('NIGHTSHIFT_') and k!='CLAUDE_PROJECT_DIR'}
        environment.update(NIGHTSHIFT_HOME=evidence['runtime_home'],NIGHTSHIFT_SYNC_CHECK='off',NIGHTSHIFT_UPDATE_GUARD='1')
        inspected=subprocess.run([evidence['installed_executable'],'inventory','--project',str(project),'--task',evidence['task']],env=environment,capture_output=True,text=True)
        self.assertEqual(inspected.returncode,0,inspected.stderr[-1000:])
        self.assertEqual(json.loads(inspected.stdout)['recovery']['status'],'complete')
        self.assertEqual(evidence['repeat']['exit_code'],0)
        self.assertEqual(evidence['repeat']['before_receipts'],evidence['repeat']['after_receipts'])
        self.assertEqual(evidence['repeat']['before_reservations'],evidence['repeat']['after_reservations'])
        self.assertTrue(evidence['repeat']['before_reservations'])
        self.assertEqual({item['provider'] for item in evidence['providers']}, {'codex','claude'})
        import hashlib
        for item in evidence['providers']:
            self.assertEqual(hashlib.sha256(Path(item['executable']).resolve(strict=True).read_bytes()).hexdigest(),item['sha256'])

if __name__ == "__main__":
    unittest.main()
