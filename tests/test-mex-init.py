import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mex',ROOT/'scripts/nightshift-mex.py')
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class MexInit(unittest.TestCase):
    def test_fresh_reused_stale_refreshed_missing_built(self):
        with tempfile.TemporaryDirectory() as tmp:
            for before, action in [('fresh','reuse'),('stale','refresh'),('missing','rebuild')]:
                replies = [json.dumps(dict(status=before))]
                if before != 'fresh':replies += ['{}',json.dumps(dict(status='fresh'))]
                with patch.object(m,'binary',return_value='/fixture/mex'),patch.object(m,'run',side_effect=replies) as run:
                    result = m.prepare(Path(tmp))
                self.assertEqual(result['status'],'ready');self.assertEqual(result['action'],action)
                self.assertEqual(run.call_count,1 if before=='fresh' else 3)
                if before!='fresh':self.assertEqual(run.call_args_list[1].args[0][2],action)

    def test_missing_cli_pinned_private_install(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,NIGHTSHIFT_HOME=tmp):
            with patch.object(m,'binary',side_effect=[None,'/fixture/mex']),patch.object(m.shutil,'which',return_value='/fixture/npm'),patch.object(m,'run',side_effect=['',json.dumps(dict(status='fresh'))]) as run:
                result = m.prepare(Path(tmp))
            self.assertEqual(result['status'],'ready')
            argv = run.call_args_list[0].args[0]
            self.assertIn('mex-agent@0.8.2',argv);self.assertIn('--prefix',argv);self.assertNotIn('-g',argv)

    def test_timeout_and_unsafe_graph_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp);(p/'.mex').mkdir();db=p/'.mex/graph.db';db.write_text('retained')
            for value in ['corrupt','degraded','missing']:
                with patch.object(m,'binary',return_value='/fixture/mex'),patch.object(m,'run',return_value=json.dumps(dict(status=value))) as run:
                    result=m.prepare(p)
                self.assertEqual(result['status'],'unavailable');self.assertEqual(run.call_count,1);self.assertEqual(db.read_text(),'retained')
            with patch.object(m,'binary',return_value='/fixture/mex'),patch.object(m,'run',side_effect=TimeoutError('bounded')):
                self.assertEqual(m.prepare(p)['status'],'unavailable')

    def test_init_default_calls_mex_and_repeat_reuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);p=base/'repo';p.mkdir();binary=base/'bin';binary.mkdir();log=base/'calls'
            stub=binary/'mex';stub.write_text('''#!/usr/bin/env python3
import json,os,sys
with open(os.environ['MEX_TEST_LOG'],'a') as f:f.write(' '.join(sys.argv[1:])+'\\n')
print(json.dumps({'status':'fresh'}))
''');stub.chmod(0o755)
            env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],HOME=str(base),NIGHTSHIFT_HOME=str(base/'home'),MEX_TEST_LOG=str(log),GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_NOSYSTEM='1',GIT_AUTHOR_NAME='fixture',GIT_AUTHOR_EMAIL='fixture@local',GIT_COMMITTER_NAME='fixture',GIT_COMMITTER_EMAIL='fixture@local')
            for _ in range(2):
                proc=subprocess.run(['python3',str(ROOT/'scripts/nightshift-init.py'),'--project',str(p)],env=env,capture_output=True,text=True)
                self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
                rows=[json.loads(line) for line in proc.stdout.splitlines() if line.startswith('{')]
                receipt=next(row for row in rows if 'baseline' in row)
                self.assertEqual(receipt['mex']['action'],'reuse');self.assertFalse(receipt['model_started'])
            self.assertEqual(len(log.read_text().splitlines()),2)

if __name__=='__main__':unittest.main()
