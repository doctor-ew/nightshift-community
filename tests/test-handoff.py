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

 def test_source_and_spec_are_bound_inline_without_private_log_reads(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(m,'graph',return_value={'status':'unavailable','records':[]}):
   project=Path(tmp);request=project/'brief.md';request.write_text('# Public request\nFix one function.\n')
   docs=project/'docs/sample';docs.mkdir(parents=True);(docs/'SPEC.md').write_text('# Current specification\nAC-1.\n')
   private=docs/'old-provider.log';private.write_text('OLD_LOG_MUST_NOT_ENTER_HANDOFF')
   state={'request':str(request),'decisions':[],'findings':[{'id':'transport','target':str(private),'problem':'worker_exit_1'}],'attempts':[{'stage':'product','status':'fail','category':'transport','reason':'worker_exit_1','receipt':str(private)}]}
   value=m.build(project,'sample','product',state,'repair')
   files={item['path']:item for item in value['artifacts']}
   self.assertEqual(files['brief.md']['content'],request.read_text());self.assertEqual(files['docs/sample/SPEC.md']['content'],(docs/'SPEC.md').read_text())
   self.assertNotIn('OLD_LOG_MUST_NOT_ENTER_HANDOFF',json.dumps(value));self.assertEqual(value['diagnostics'][0]['category'],'transport')
   self.assertLessEqual(len(json.dumps(value,sort_keys=True).encode()),m.LIMIT)

 def test_large_file_is_referenced_whole_instead_of_truncated(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(m,'graph',return_value={'status':'unavailable','records':[]}):
   project=Path(tmp);request=project/'brief.md';request.write_text('x'*30000)
   value=m.build(project,'sample','product',{'request':str(request)},'scope')
   artifact=next(row for row in value['artifacts'] if row['path']=='brief.md')
   self.assertNotIn('content',artifact);self.assertEqual(artifact['content_status'],'reference_only')
   self.assertEqual(artifact['sha256'],__import__('hashlib').sha256(request.read_bytes()).hexdigest())

 def test_missing_project_graph_does_not_start_graph_process(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(m.subprocess,'run') as run:
   result=m.graph(tmp,'scope');self.assertEqual(result['status'],'unavailable');run.assert_not_called()

if __name__=='__main__':unittest.main()
