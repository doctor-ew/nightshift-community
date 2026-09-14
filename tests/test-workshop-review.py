import importlib.util
import fcntl
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('review', ROOT/'scripts/nightshift-workshop-review.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Reviews(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name).resolve(); self.task='workshop-'+'a'*16
        subprocess.run(['git','init',str(self.project)],check=True,capture_output=True)
        subprocess.run(['git','-C',str(self.project),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','--allow-empty','-m','baseline'],check=True,capture_output=True)
        self.directory=m.common(self.project)/'nightshift-workshop';self.directory.mkdir()
        (self.directory/(self.task+'.json')).write_text(json.dumps(dict(task=self.task,status='awaiting_spec_approval',worktree=str(self.project))))
        p=self.project/'docs'/self.task;p.mkdir(parents=True)
        (p/'SPEC.md').write_text('# Reviewed spec\n')
        self.content=(p/'SPEC.md').read_bytes()
        m.publish(self.project,self.task,self.content)

    def test_copy_and_exact_approval(self):
        info=m.review(self.project,self.task)
        self.assertEqual(info['spec'],self.content.decode())
        m.approve(self.project,self.task,info['sha256'])
        self.assertEqual(m.approved_hash(self.project,self.task),m.sha(self.content))
        self.assertTrue(m.list_reviews(self.project)[0]['approved'])

    def test_edits_and_stale_hash_refused(self):
        with self.assertRaises(ValueError):m.approve(self.project,self.task,'stale')
        m.copy_path(self.project,self.task).write_text('Student edits')
        with self.assertRaises(ValueError):m.approve(self.project,self.task,m.sha(self.content))
        with self.assertRaises(ValueError):m.publish(self.project,self.task,self.content)
        self.assertEqual(m.copy_path(self.project,self.task).read_text(),'Student edits')

    def test_running_lock_prevents_approval(self):
        with (self.directory/(self.task+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):m.approve(self.project,self.task,m.sha(self.content))
        self.assertIsNone(m.approved_hash(self.project,self.task))

    def test_traversal_and_active_run_refused(self):
        with self.assertRaises(ValueError):m.approve(self.project,'../other','x')
        state=self.directory/(self.task+'.json');v=json.loads(state.read_text());v['status']='implementation-0';state.write_text(json.dumps(v))
        with self.assertRaises(ValueError):m.approve(self.project,self.task,m.sha(self.content))

if __name__=='__main__':unittest.main()
