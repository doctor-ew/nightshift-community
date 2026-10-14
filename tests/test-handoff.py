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

 def test_product_rewind_defers_exact_adversarial_receipt_even_after_stage_label_changes(self):
  import copy
  with tempfile.TemporaryDirectory() as tmp,patch.object(m,'graph',return_value={'status':'unavailable','records':[]}):
   project=Path(tmp); receipt=str(project/'docs/sample/adversarial-2.json')
   retained={'id':'adv-2','target':receipt,'problem':'Retained adversarial failure'}
   own={'id':'product-4','target':'docs/sample/SPEC.md','problem':'Missing current Product acceptance criterion'}
   state={'finding_stage':'product','findings':[retained,own],'attempts':[{'stage':'adversarial','status':'fail','receipt':receipt}]}
   before=copy.deepcopy(state)
   value=m.build(project,'sample','product',state,'repair')
   self.assertEqual(value['findings'],[own]);self.assertEqual(value['deferred_findings'],[retained]);self.assertEqual(state,before)

 def test_scope_finding_for_implementation_is_context_when_product_runs(self):
  import copy
  with tempfile.TemporaryDirectory() as tmp,patch.object(m,'graph',return_value={'status':'unavailable','records':[]}):
   finding={'id':'scope','target':'app.py','problem':'Resolve implementation scope'}
   state={'finding_stage':'implement','findings':[finding],'history':[{'reason':'scope_blocked'}],'attempts':[]}
   before=copy.deepcopy(state)
   product=m.build(tmp,'sample','product',state,'scope')
   implementation=m.build(tmp,'sample','implement',state,'scope')
   self.assertEqual(product['findings'],[]);self.assertEqual(product['deferred_findings'],[finding])
   self.assertEqual(implementation['findings'],[finding]);self.assertEqual(implementation['deferred_findings'],[])
   self.assertEqual(state,before)

 def test_controller_assigned_artifact_repairs_remain_mandatory(self):
  import copy
  for origin,stage,target in [('adversarial','product','docs/sample/SPEC.md'),('review','implement','app.py')]:
   with self.subTest(origin=origin),tempfile.TemporaryDirectory() as tmp,patch.object(m,'graph',return_value={'status':'unavailable','records':[]}):
    receipt=str(Path(tmp)/'docs/sample'/f'{origin}-2.json')
    finding={'id':'semantic','target':target,'problem':'Repair concrete reviewed defect'}
    diagnostic={'id':'receipt','target':receipt,'problem':'Retained other-stage receipt failure'}
    state={'status':'repairing','next_action':stage,'finding_stage':origin,'findings':[finding,diagnostic],'attempts':[{'stage':origin,'status':'fail','category':'substantive','reason':'stage_failed','receipt':receipt}]}
    before=copy.deepcopy(state);value=m.build(tmp,'sample',stage,state,'repair')
    self.assertEqual(value['findings'],[finding]);self.assertEqual(value['deferred_findings'],[diagnostic]);self.assertEqual(state,before)

 def test_transport_and_stale_receipts_do_not_assign_artifact_repairs(self):
  for category in ('transport','schema'):
   with self.subTest(category=category),tempfile.TemporaryDirectory() as tmp,patch.object(m,'graph',return_value={'status':'unavailable','records':[]}):
    finding={'id':'diagnostic','target':'docs/sample/SPEC.md','problem':'Unaccepted worker diagnostic'}
    state={'status':'repairing','next_action':'product','finding_stage':'adversarial','findings':[finding],'attempts':[{'stage':'adversarial','status':'fail','category':category,'receipt':str(Path(tmp)/'adversarial.json')}]}
    value=m.build(tmp,'sample','product',state,'repair')
    self.assertEqual(value['findings'],[]);self.assertEqual(value['deferred_findings'],[finding])

 def test_unvalidated_or_successful_origin_does_not_assign_artifact_repairs(self):
  for attempt in (None,{'stage':'adversarial','status':'pass','category':'success','reason':'stage_failed'}, {'stage':'adversarial','status':'fail','reason':'worker_exit_1'}):
   with self.subTest(attempt=attempt),tempfile.TemporaryDirectory() as tmp,patch.object(m,'graph',return_value={'status':'unavailable','records':[]}):
    finding={'id':'unvalidated','target':'docs/sample/SPEC.md','problem':'Historical diagnostic'}
    state={'status':'repairing','next_action':'product','finding_stage':'adversarial','findings':[finding],'attempts':[attempt] if attempt else []}
    value=m.build(tmp,'sample','product',state,'repair')
    self.assertEqual(value['findings'],[]);self.assertEqual(value['deferred_findings'],[finding])

if __name__=='__main__':unittest.main()
