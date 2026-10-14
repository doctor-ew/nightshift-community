#!/usr/bin/env python3
"""Execute managed-stage admission without a provider or paid work."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class StageAdmission(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.project=Path(self.temp.name).resolve();subprocess.run(['git','init','-q',str(self.project)],check=True)
  self.directory=self.project/'.git/nightshift/pipeline/sample';self.directory.mkdir(parents=True)
  self.handoff=self.directory/'product-1.handoff.json';self.handoff.write_text(json.dumps(dict(version=1,task='sample',stage='product')))
  self.receipt=self.project/'docs/sample/.nightshift-product-1.json';self.receipt.parent.mkdir(parents=True)
  source=(ROOT/'scripts/nightshift-factory.sh').read_text();self.guard=source.split("<<'PYSTAGEADMISSION' || exit 65\n",1)[1].split('\nPYSTAGEADMISSION',1)[0]
 def run_guard(self,handoff=None,receipt=None):
  return subprocess.run([sys.executable,'-',str(self.project),'sample','product',str(handoff or self.handoff),str(receipt or self.receipt)],input=self.guard,capture_output=True,text=True)
 def test_valid_managed_handoff_is_admitted(self):self.assertEqual(self.run_guard().returncode,0)
 def test_mismatched_identity_stops_before_sandbox_selection(self):
  for key,value in [('task','different'),('stage','review'),('version','1')]:
   data=dict(version=1,task='sample',stage='product');data[key]=value;self.handoff.write_text(json.dumps(data));self.assertEqual(self.run_guard().returncode,65)
 def test_external_or_symlinked_handoff_is_rejected(self):
  external=self.project/'elsewhere.json';external.write_bytes(self.handoff.read_bytes());self.assertEqual(self.run_guard(external).returncode,65)
  self.handoff.unlink();self.handoff.symlink_to(external);self.assertEqual(self.run_guard().returncode,65)
 def test_receipt_cannot_escape_or_overwrite(self):
  self.assertEqual(self.run_guard(receipt=self.project/'outside.json').returncode,65)
  self.receipt.write_text('previous evidence');self.assertEqual(self.run_guard().returncode,65)
if __name__=='__main__':unittest.main()
