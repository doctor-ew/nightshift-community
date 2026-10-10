"""Retained workers inherit configuration, never workspace or ticket identity."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/('nightshift-'+name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RetainedManifest(unittest.TestCase):
    def test_primary_only_configuration_reaches_real_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp).resolve();primary=base/'primary checkout';primary.mkdir()
            subprocess.run(['git','init','-q',str(primary)],check=True)
            subprocess.run(['git','-C',str(primary),'-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','baseline'],check=True)
            target=base/'retained worktree'
            subprocess.run(['git','-C',str(primary),'worktree','add','-qb','ticket',str(target)],check=True)
            config=primary/'configuration';config.mkdir()
            routing=config/'routes.json';shutil.copy2(ROOT/'routing.json',routing)
            manifest=primary/'.nightshift.toml'
            manifest.write_text((ROOT/'nightshift.toml').read_text().replace('routing_file = "routing.json"','routing_file = "configuration/routes.json"')+'\n[runtime]\nprovider="codex"\nmodel="fixture-model"\n[tests]\ncommand="python3 local_test.py"\n')
            context=load('project-context');routes=load('routing-path')
            with patch.dict(os.environ,{},clear=True):
                self.assertEqual(context.manifest_path(target),manifest)
                self.assertEqual(routes.resolve(ROOT,target),routing)
                self.assertEqual(context.discover(target)['project'],str(target))
                self.assertEqual(context.discover(target)['test_command'],'python3 local_test.py')
                self.assertEqual(load('behavior-proof').config(target),load('behavior-proof').config(primary))
            binary=base/'bin';binary.mkdir();capture=base/'provider.json'
            (binary/'codex').write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys
if sys.argv[1:3]==['login','status']:
 print('Logged in using ChatGPT');sys.exit(0)
pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps(dict(argv=sys.argv[1:],cwd=os.getcwd(),routing=os.environ['NIGHTSHIFT_ROUTING_FILE'])))
print(json.dumps(dict(type='item.completed',item=dict(type='agent_message',text='fixture'))))
''');(binary/'codex').chmod(0o755)
            home=base/'home';home.mkdir();handoff=base/'handoff.json';handoff.write_text('{}')
            env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],HOME=str(home),NIGHTSHIFT_HOME=str(home),NIGHTSHIFT_UPDATE_GUARD='1',NIGHTSHIFT_OUTPUT_CHILD='1',NIGHTSHIFT_PIPELINE_STAGE='adversarial',NIGHTSHIFT_PIPELINE_TASK='TEST-1',NIGHTSHIFT_STAGE_HANDOFF=str(handoff),NIGHTSHIFT_STAGE_RECEIPT=str(base/'receipt.json'),NIGHTSHIFT_BUDGET_TASK='TEST-1',NIGHTSHIFT_BUDGET_PROJECT=str(target),CAPTURE=str(capture),PYTHONDONTWRITEBYTECODE='1')
            env.pop('NIGHTSHIFT_ROUTING_FILE',None)
            result=subprocess.run(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'jira:TEST-1','--project',str(target),'--branch','none','--dashboard','off'],env=env,cwd=target,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            actual=json.loads(capture.read_text())
            self.assertEqual(actual['cwd'],str(target))
            self.assertEqual(actual['routing'],str(routing))
            self.assertIn('fixture-model',actual['argv'])
            self.assertFalse((target/'.nightshift.toml').exists())
            # Local legacy configuration overrides inherited canonical configuration.
            local=target/'nightshift.toml';local.write_text(manifest.read_text().replace('configuration/routes.json',str(routing)))
            self.assertEqual(context.manifest_path(target),local)
            self.assertEqual(routes.resolve(ROOT,target),routing)
            check=subprocess.run(['bash',str(ROOT/'scripts/nightshift-manifest-validate.sh'),'--project',str(target)],capture_output=True,text=True)
            self.assertEqual(check.returncode,0,check.stdout+check.stderr)
            (target/'.nightshift.toml').symlink_to(target/'missing.toml')
            self.assertEqual(context.manifest_path(target),target/'.nightshift.toml')
            with self.assertRaises(OSError):routes.resolve(ROOT,target)


if __name__ == '__main__':
    unittest.main()
