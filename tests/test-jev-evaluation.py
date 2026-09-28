import importlib.util,json,os,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('jev',ROOT/'scripts/nightshift-jev-evaluation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Evaluation(unittest.TestCase):
 def test_no_key_reports_no_measurement_or_savings(self):
  corpus=json.loads((ROOT/'evals/jev/public-evidence.json').read_text())
  with patch.dict(os.environ,{},clear=True):result=m.evaluate(corpus,{'key_env':'FIXTURE_KEY','model':'fixture'})
  self.assertEqual(result['service_requests'],0);self.assertEqual(result['status'],'incomplete');self.assertEqual(result['claude_calls_avoided'],0)
 def test_labels_are_compared_to_real_response_shape(self):
  corpus=json.loads((ROOT/'evals/jev/public-evidence.json').read_text())
  labels={c['evidence']:c['defective'] for c in corpus['cases']}
  def request(settings,key,body):
   bad=labels[json.loads(body)['state']]
   return json.dumps({'answers':{k:{'noul':0 if bad else 1} for k in m.e.QUESTIONS}})
  with patch.dict(os.environ,{'FIXTURE_KEY':'fixture'}):result=m.evaluate(corpus,{'key_env':'FIXTURE_KEY','model':'fixture'},request)
  self.assertEqual(result['service_requests'],6);self.assertEqual(result['defects_caught'],3);self.assertEqual(result['false_positives'],0)
if __name__=='__main__':unittest.main()
