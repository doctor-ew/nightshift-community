#!/usr/bin/env python3
"""Synthetic malformed worker receipts remain invalid and explainable."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
m=load('diagnostic_pipeline','scripts/nightshift-pipeline.py')
f=load('diagnostic_fixture','tests/nightshift-behavior-fixture.py')

class Diagnostics(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory(prefix='nightshift-stage-diagnostics-');self.addCleanup(tmp.cleanup)
  self.root=Path(tmp.name).resolve();self.path=self.root/'receipt.json'
  self.value=dict(version=1,task='123',stage='product',status='fail',findings=[dict(id='synthetic-root-cause',target='synthetic-config',problem='Synthetic route unavailable; this is an unvalidated observation.')],checks=[],evidence=[])
 def check_error(self,value,expected):
  self.path.write_text(json.dumps(value))
  with self.assertRaises(ValueError) as raised:m.validate_receipt(self.path,'123','product',self.root)
  self.assertEqual(str(raised.exception),expected)
 def test_root_numeric_task_boolean_version_and_container_types_are_precise(self):
  self.check_error([], 'stage_receipt.root:expected_object')
  for field,value,error in [('version',True,'expected_integer'),('version',2,'unsupported_version'),('task',123,'expected_string'),('task','other','identity_mismatch'),('stage',None,'expected_string'),('status',[],'expected_string'),('findings',{},'expected_array'),('checks',None,'expected_array'),('evidence','text','expected_array')]:
   with self.subTest(field=field,value=value):
    candidate=dict(self.value);candidate[field]=value;self.check_error(candidate,'stage_receipt.'+field+':'+error)
 def test_rows_are_validated_on_failed_receipts_too(self):
  for field in ('findings','checks','evidence'):
   for item in (None,17,'bad',[]):
    with self.subTest(field=field,item=item):
     candidate=dict(self.value);candidate[field]=[item];self.check_error(candidate,'stage_receipt.'+field+'[0]:expected_object')
  candidate=dict(self.value,checks=[dict(command='synthetic check',exit_code=True)])
  self.check_error(candidate,'stage_receipt.checks[0].exit_code:expected_integer')
 def test_duplicate_json_rejected_without_silent_last_value(self):
  self.path.write_text('{"task":"other",'+json.dumps(self.value)[1:])
  with self.assertRaisesRegex(ValueError,'stage_receipt.json:duplicate_key'):m.validate_receipt(self.path,'123','product',self.root)
 def test_typed_template_keeps_numeric_task_as_string(self):
  shell=(ROOT/'scripts/nightshift-factory.sh').read_text()
  line=next(line.strip() for line in shell.splitlines() if line.strip().startswith('STAGE_RECEIPT_TEMPLATE='))
  env=dict(os.environ,NIGHTSHIFT_PIPELINE_TASK='123',MODE='product')
  raw=subprocess.check_output(['bash','-c',line+'\nprintf "%s" "$STAGE_RECEIPT_TEMPLATE"'],env=env,text=True)
  value=json.loads(raw);self.assertEqual(value['task'],'123');self.assertIs(type(value['version']),int);self.assertEqual(value['status'],'fail')
  self.assertIn('${STAGE_RECEIPT_TEMPLATE}',shell)
 def test_diagnostic_is_bounded_hash_bound_immutable_and_not_authority(self):
  candidate=dict(self.value,task=123);candidate['findings'][0]['problem']='x'*20000
  raw=json.dumps(candidate).encode();self.path.write_bytes(raw)
  result=m.retain_diagnostic(self.path,'123','product',self.root,'stage_receipt.task:expected_string')
  artifact=Path(result['path']);retained=artifact.read_bytes();value=json.loads(retained)
  self.assertEqual(artifact.stat().st_mode & 0o777,0o600)
  self.assertEqual(value['label'],'UNVALIDATED_WORKER_DIAGNOSTIC');self.assertEqual(value['source_sha256'],m.sha(self.path));self.assertEqual(value['source_bytes'],len(raw))
  self.assertEqual(value['validation_error'],'stage_receipt.task:expected_string');self.assertTrue(value['preview_truncated']);self.assertLessEqual(len(value['preview'].encode()),8192)
  self.assertEqual(len(result['reported_findings'][0]['problem']),1024)
  self.path.write_text('changed operator artifact')
  self.assertEqual(m.retain_diagnostic(self.path,'123','product',self.root,'changed'),result);self.assertEqual(artifact.read_bytes(),retained)
 def test_oversized_and_symlink_sources_are_not_read_or_hashed(self):
  self.path.write_bytes(b'x'*2000001)
  result=m.retain_diagnostic(self.path,'123','product',self.root,'oversized');value=json.loads(Path(result['path']).read_text())
  self.assertIsNone(value['source_sha256']);self.assertEqual(value['preview'],'');self.assertTrue(value['preview_truncated'])
  other=self.root/'link.json';other.symlink_to(self.path)
  result=m.retain_diagnostic(other,'123','product',self.root,'unsafe');value=json.loads(Path(result['path']).read_text())
  self.assertIsNone(value['source_sha256']);self.assertEqual(value['validation_error'],'stage_receipt.file:missing_or_unsafe')
 def pipeline_case(self,code,raw_worker=False):
  project=self.root/'project';f.prepare(ROOT,project,task='123',manual=True,final=True)
  settings=dict(ref='gh:123',provider='claude',model='fixture',policy='claude-only',auth='subscription',branch='none',base='',push=False,pr=False)
  ledger=m.load('ticket-budget');ledger.update(project,'123','reserve','retained',max_calls=10);ledger.update(project,'123','finish','retained',outcome='failed');before=ledger.ledger_path(project,'123').read_bytes()
  def runner(stage,handoff,receipt):
   receipt.write_text(json.dumps(dict(self.value,task=123,stage=stage)));return code
  with patch.dict(os.environ,{'NIGHTSHIFT_ROUTING_FILE':str(ROOT/'routing.json')}):
   controller=m.Pipeline(project,'123',settings,runner)
   if raw_worker:
    controller.runner=controller.dispatch
    class Process:
     def wait(inner,timeout):
      (project/'docs/123/.nightshift-adversarial-1.json').write_text('['*100000+']'*100000 if raw_worker=='deep' else '[]');return code
    real_popen=m.subprocess.Popen
    def popen(argv,*args,**kwargs):
     if len(argv)>1 and str(argv[1]).endswith('nightshift-factory.sh'):return Process()
     return real_popen(argv,*args,**kwargs)
    with patch.object(m.subprocess,'Popen',side_effect=popen):result=controller.run()
   else:result=controller.run()
  self.assertEqual(result,1);attempt=controller.state['attempts'][-1]
  self.assertEqual(attempt['category'],'transport' if code else 'schema')
  self.assertEqual(attempt['reason'],'worker_exit_'+str(code) if code else 'stage_receipt.json:invalid_json' if raw_worker=='deep' else 'stage_receipt.root:expected_object' if raw_worker else 'stage_receipt.task:expected_string')
  self.assertEqual(attempt['diagnostic']['validation_error'],'stage_receipt.json:invalid_json' if raw_worker=='deep' else 'stage_receipt.root:expected_object' if raw_worker else 'stage_receipt.task:expected_string')
  self.assertEqual(controller.state['retry_budgets']['adversarial']['infrastructure_failures'],1)
  self.assertEqual(controller.state['retry_budgets']['adversarial']['substantive_failures'],0)
  self.assertEqual(ledger.ledger_path(project,'123').read_bytes(),before)
  self.assertNotIn('Synthetic route unavailable',json.dumps(controller.state['findings']))
  handoff=m.load('handoff').build(project,'123','adversarial',controller.state,'synthetic')
  self.assertNotIn('Synthetic route unavailable',json.dumps(handoff))
  self.assertIn('retry_budgets',m.view(project,'123'))
 def test_invalid_task_retains_reason_without_authorizing_worker_findings(self):self.pipeline_case(0)
 def test_nonzero_exit_keeps_transport_accounting_and_schema_detail(self):self.pipeline_case(23)
 def test_actual_dispatch_nonzero_invalid_root_does_not_become_schema_category(self):self.pipeline_case(23,True)
 def test_reaped_child_schema_error_is_not_replaced_by_cleanup_error(self):self.pipeline_case(0,True)
 def test_deep_json_retains_schema_failure_instead_of_pending_attempt(self):self.pipeline_case(0,'deep')
 def test_malformed_existing_diagnostic_is_not_trusted(self):
  self.path.with_suffix('.diagnostic.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'invalid_diagnostic_record'):m.retain_diagnostic(self.path,'123','product',self.root,'synthetic')

if __name__=='__main__':unittest.main()
