import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('handoff',ROOT/'scripts/nightshift-handoff.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Handoff(unittest.TestCase):
 def test_missing_graph_and_large_decisions_do_not_drop_findings(self):
  with tempfile.TemporaryDirectory() as p,patch.object(m.shutil,'which',return_value=None):
   value=m.build(p,'42','review',{'decisions':[{'answer':'saved'}],'findings':[{'id':'x','problem':'retained'}]},'scope')
   self.assertEqual(value['graph']['status'],'unavailable');self.assertEqual(value['findings'][0]['id'],'x')
   with self.assertRaises(ValueError):m.build(p,'42','review',{'decisions':['x'*25000]},'scope')
 def test_stale_graph_is_not_trusted(self):
  result=type('Result',(),dict(returncode=0,stdout=json.dumps(dict(type='health',staleFiles=['x']))+'\n'+json.dumps(dict(type='summary',status='ok'))))()
  with patch.object(m.shutil,'which',return_value='/mex'),patch.object(m.subprocess,'run',return_value=result):
   self.assertEqual(m.graph('.','task')['records'],[])
if __name__=='__main__':unittest.main()
