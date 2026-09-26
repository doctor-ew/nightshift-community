#!/usr/bin/env python3
"""Independent startup cancellation tests; only disposable owned processes."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
RUNNER=Path(os.environ.get('NIGHTSHIFT_TEST_RUNNER_SOURCE',ROOT/'scripts/nightshift-recovery-exec.py')).resolve()

class StartupOwnership(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='nightshift-owned-startup-review-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.children=[];self.owned=[]
        self.env=dict(HOME=str(self.root),NIGHTSHIFT_HOME=str(self.root/'home'),XDG_CONFIG_HOME=str(self.root/'config'),PATH=os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null')
        self.addCleanup(self.cleanup_owned)
    def cleanup_owned(self):
        for child in self.children:
            if child.poll() is None:child.kill()
            child.wait(timeout=5)
        for pid in self.owned:
            command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
            if str(self.root) in command:
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
    def launch(self,mode='normal',seconds=8,parent=None,command=None):
        self.marker=self.root/'spawned';self.output=self.root/'output.log';self.output.touch()
        script=self.root/'wrapper.py'
        script.write_text('''import importlib.util,os,signal,subprocess,sys,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('owned_runner',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
marker=Path(sys.argv[2]);mode=sys.argv[3];original=m.subprocess.Popen
original_signal=m.signal.signal
def installed(sig,handler):
 result=original_signal(sig,handler)
 if mode=='before_spawn' and sig==signal.SIGINT:os.kill(os.getpid(),signal.SIGTERM)
 return result
m.signal.signal=installed
def tracked(*args,**kwargs):
 child=original(*args,**kwargs);marker.write_text(str(child.pid))
 if mode=='during_spawn':time.sleep(1)
 return child
m.subprocess.Popen=tracked
raise SystemExit(m.run(int(sys.argv[4]),float(sys.argv[5]),sys.argv[6],sys.argv[7:]))
''')
        if command is None:command=[sys.executable,'-c','import time;time.sleep(20)']
        command=[*command,str(self.root)]
        self.log=self.output.open('ab');self.addCleanup(self.log.close)
        child=subprocess.Popen([sys.executable,'-B',str(script),str(RUNNER),str(self.marker),mode,str(os.getpid() if parent is None else parent),str(seconds),str(self.output),*command],env=self.env,stdin=subprocess.DEVNULL,stdout=self.log,stderr=self.log)
        self.children.append(child);return child
    def wait_spawn(self):
        deadline=time.monotonic()+5
        while not self.marker.exists() and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(self.marker.exists(),'owned command never spawned')
        pid=int(self.marker.read_text());self.owned.append(pid);return pid
    def assert_stopped(self,pid):
        result=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True,check=False)
        status=result.stdout.strip();self.assertTrue(not status or status.startswith('Z'),'owned command survived supervisor: '+status)
    def during_spawn(self,sig):
        unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'],env=self.env);self.children.append(unrelated)
        child=self.launch('during_spawn');pid=self.wait_spawn();child.send_signal(sig);code=child.wait(timeout=5)
        self.assertIsNone(unrelated.poll(),'unrelated owned sentinel was stopped')
        self.assert_stopped(pid);self.assertEqual(code,124)
    def test_sigterm_during_popen_stops_owned_command(self):self.during_spawn(signal.SIGTERM)
    def test_sigint_during_popen_stops_owned_command(self):self.during_spawn(signal.SIGINT)
    def test_cancel_before_spawn_creates_no_command(self):
        child=self.launch('before_spawn');self.assertEqual(child.wait(timeout=5),124)
        if self.marker.exists():self.owned.append(int(self.marker.read_text()))
        self.assertFalse(self.marker.exists(),'command spawned after observed cancellation')
    def test_missing_command_keeps_original_launch_failure(self):
        child=self.launch(command=[str(self.root/'missing-command')]);self.assertNotEqual(child.wait(timeout=5),0)
        self.assertFalse(self.marker.exists());text=self.output.read_text();self.assertIn('FileNotFoundError',text);self.assertNotIn('UnboundLocalError',text)
    def test_dead_parent_before_spawn_creates_no_command(self):
        child=self.launch(parent=0);self.assertEqual(child.wait(timeout=5),124)
        if self.marker.exists():self.owned.append(int(self.marker.read_text()))
        self.assertFalse(self.marker.exists(),'command spawned after parent was already absent')
    def test_expired_deadline_before_spawn_creates_no_command(self):
        child=self.launch(seconds=0);self.assertEqual(child.wait(timeout=5),124)
        if self.marker.exists():self.owned.append(int(self.marker.read_text()))
        self.assertFalse(self.marker.exists(),'command spawned after deadline')
    def test_active_deadline_stops_command(self):
        child=self.launch(seconds=.2);pid=self.wait_spawn();self.assertEqual(child.wait(timeout=5),124);self.assert_stopped(pid)
    def test_parent_death_after_spawn_stops_owned_command(self):
        marker=self.root/'command.pid';supervisor_marker=self.root/'supervisor.pid';output=self.root/'parent-loss.log'
        command='import os,time;from pathlib import Path;Path('+repr(str(marker))+').write_text(str(os.getpid()));time.sleep(20)'
        launcher=self.root/'controller.py'
        launcher.write_text('import os,subprocess,sys,time\nfrom pathlib import Path\nlog=open(sys.argv[3],"wb")\nchild=subprocess.Popen([sys.executable,sys.argv[1],str(os.getpid()),"10",sys.argv[3],sys.executable,"-c",sys.argv[4]],stdout=log,stderr=log)\nPath(sys.argv[2]).write_text(str(child.pid))\ntime.sleep(20)\n')
        controller=subprocess.Popen([sys.executable,str(launcher),str(RUNNER),str(supervisor_marker),str(output),command],env=self.env);self.children.append(controller)
        deadline=time.monotonic()+5
        while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(marker.exists());pid=int(marker.read_text());self.owned.append(pid);self.owned.append(int(supervisor_marker.read_text()))
        controller.terminate();controller.wait(timeout=5)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            result=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True).stdout.strip()
            if not result or result.startswith('Z'):break
            time.sleep(.05)
        self.assert_stopped(pid)
    def test_normal_completion_preserves_exit_status(self):
        child=self.launch(command=[sys.executable,'-c','raise SystemExit(7)']);pid=self.wait_spawn();self.assertEqual(child.wait(timeout=5),7);self.assert_stopped(pid)

if __name__=='__main__':unittest.main()
