"""Explicit continuation preserves history and starts only after operator invocation."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('budget', ROOT/'scripts/nightshift-ticket-budget.py')
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


class Continuation(unittest.TestCase):
    def test_launcher_continuation_help_is_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            env=dict(os.environ, HOME=temp, NIGHTSHIFT_HOME=temp,
                     NIGHTSHIFT_UPDATE_GUARD='1', PYTHONDONTWRITEBYTECODE='1')
            result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'continue','--help'],
                                  env=env,cwd=temp,capture_output=True,text=True,check=True)
            self.assertIn('nightshift continue jira:TICKET',result.stdout)
            self.assertNotIn('no final answer',result.stderr)

    def test_explicit_resume_and_rejected_grant(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            project = root/'project with spaces'
            project.mkdir()
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            subprocess.run(['git','-C',str(project),'-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','baseline'],check=True)
            (project/'.git/info/exclude').write_text('.nightshift.toml\nconfig/\n')
            (project/'config').mkdir()
            shutil.copy2(ROOT/'routing.json',project/'config/team.json')
            (project/'.nightshift.toml').write_text((ROOT/'nightshift.toml').read_text().replace('routing_file = "routing.json"','routing_file = "config/team.json"'))
            target=json.loads(subprocess.check_output(['bash',str(ROOT/'scripts/nightshift-worktree.sh'),'prepare','TEST-1','--project',str(project),'--base','HEAD','--root',str(root/'worktrees')],text=True))['worktree']
            target=Path(target)
            self.assertFalse((target/'.nightshift.toml').exists())
            pipeline=project/'.git/nightshift/pipeline/TEST-1/state.json'
            pipeline.parent.mkdir(parents=True)
            pipeline.write_text(json.dumps(dict(worktree=str(target),completed={'product':{'retained':True}},attempts=[{'reason':'worker_exit_68'}],history=[{'retained':True}])))
            retained=pipeline.read_bytes()
            scripts = root/'scripts'
            shutil.copytree(ROOT/'scripts', scripts)
            # The boundary captures argv; it never invokes a real provider.
            (scripts/'nightshift-factory.sh').write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$CONTINUE_CAPTURE"\n')
            capture = root/'launched'
            env = dict(os.environ, CONTINUE_CAPTURE=str(capture), NIGHTSHIFT_HOME=str(root/'isolated-home'))
            budget.update(project, 'TEST-1', 'reserve', 'old', now=1)
            budget.update(project, 'TEST-1', 'finish', 'old', now=2, outcome='failed')
            path = budget.ledger_path(project, 'TEST-1')
            budget.update(project,'TEST-1','continue',now=3,continuation_seconds=60)
            before = json.loads(path.read_text())
            argv = ['bash', str(scripts/'nightshift-continue.sh'), '--run']
            subprocess.run(argv+['--help'], env=env, check=True, capture_output=True)
            self.assertEqual(json.loads(path.read_text()), before)
            self.assertFalse(capture.exists())
            manifest=project/'.nightshift.toml'
            manifest.rename(project/'.nightshift.toml.saved')
            missing=subprocess.run(argv+['jira:TEST-1','--project',str(project)],env=env,capture_output=True,text=True)
            self.assertEqual(missing.returncode,68,missing.stderr)
            self.assertIn('MANIFEST_MISSING',missing.stderr)
            self.assertEqual(json.loads(path.read_text()),before)
            self.assertFalse(capture.exists())
            (project/'.nightshift.toml.saved').rename(manifest)
            # A valid primary configuration cannot mask a broken worktree override.
            (target/'.nightshift.toml').write_text('[providers]\nrouting_file="missing.json"\n')
            blocked=subprocess.run(argv+['jira:TEST-1','--project',str(project)],env=env,capture_output=True,text=True)
            self.assertEqual(blocked.returncode,68,blocked.stderr)
            self.assertIn('MANIFEST_INVALID',blocked.stderr)
            self.assertEqual(json.loads(path.read_text()),before)
            self.assertFalse(capture.exists())
            (target/'.nightshift.toml').rename(root/'invalid-worktree-config')
            routing=project/'config/team.json'
            valid_routing=routing.read_text()
            for changed in ('{invalid json', json.dumps(dict(json.loads(valid_routing),allowed_providers=['local']))):
                routing.write_text(changed)
                rejected=subprocess.run(argv+['jira:TEST-1','--project',str(project)],env=env,capture_output=True,text=True)
                self.assertNotEqual(rejected.returncode,0,rejected.stdout)
                self.assertEqual(json.loads(path.read_text()),before)
                self.assertFalse(capture.exists())
            routing.write_text(valid_routing)
            subprocess.run(argv+['jira:TEST-1', '--project', str(project)], env=env, check=True, capture_output=True)
            after = json.loads(path.read_text())
            self.assertEqual(after['reservations'], before['reservations'])
            self.assertEqual(after['max_calls'], before['max_calls'])
            self.assertEqual(after['continuations'][:-1],before['continuations'])
            self.assertEqual(after['continuations'][-1]['previous_deadline_at'], before['deadline_at'])
            self.assertEqual(pipeline.read_bytes(),retained)
            self.assertFalse((target/'.nightshift.toml').exists())
            self.assertEqual(capture.read_text().splitlines(), ['jira:TEST-1', '--project', str(project)])
            capture.write_text('not launched')
            budget.update(project, 'TEST-1', 'reserve', 'unfinished')
            result = subprocess.run(argv+['jira:TEST-1', '--project', str(project)], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(capture.read_text(), 'not launched')


if __name__ == '__main__':
    unittest.main()
