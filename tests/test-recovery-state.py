#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recovery', ROOT/'scripts/nightshift-recovery-state.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class Checkpoints(unittest.TestCase):
    def test_restart_change_tamper_and_exhaustion_never_reset_history(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp).resolve()
            subprocess.run(['git','init','-q',str(p)],check=True)
            subprocess.run(['git','-C',str(p),'-c','user.name=test','-c','user.email=test@local','commit','--allow-empty','-qm','fixture'],check=True)
            (p/'source').write_text('original')
            evidence=p/'.git/evidence';evidence.mkdir()
            r=m.Recovery(p,'42',p,{'policy':'claude-only'},evidence)
            out=evidence/'proposal.json';out.write_text(json.dumps({'status':'SUCCESS'}))
            r.reserve('proposal',out);r.finish('proposal',out,True)
            deadline=r.state['deadline_at']
            resumed=m.Recovery(p,'42',p,{'policy':'claude-only'},evidence)
            self.assertEqual(resumed.result('proposal'),{'status':'SUCCESS'})
            out.write_text('{}')
            with self.assertRaisesRegex(ValueError,'evidence changed'):resumed.result('proposal')
            (p/'source').write_text('relevant input changed')
            changed=m.Recovery(p,'42',p,{'policy':'claude-only'},evidence)
            self.assertIsNone(changed.result('proposal'))
            self.assertEqual(changed.state['deadline_at'],deadline)
            self.assertEqual(len(changed.state['history']),1)
            self.assertEqual(len(changed.state['attempts']),1)
            for _ in range(2):
                changed.reserve('proposal',out);changed.finish('proposal',out,False,'failed check')
            with self.assertRaisesRegex(ValueError,'budget exhausted'):changed.reserve('proposal',out)
            changed.state['deadline_at']=time.time()-1;changed.save()
            expired=m.Recovery(p,'42',p,{'policy':'claude-only'},evidence)
            with self.assertRaisesRegex(ValueError,'deadline exhausted'):expired.reserve('review',out)
            self.assertEqual(len(expired.state['attempts']),3)

if __name__ == '__main__':unittest.main()
