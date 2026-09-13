"""Opt-in live reviewer regression; receipts retained in a printed temporary directory."""
import importlib.util,json,os,time,tempfile,types
from pathlib import Path
import sys
if '--live' not in sys.argv:
 print('Skipped: pass --live to spend up to $0.50 estimated subscription usage on two reviewer regression calls.');sys.exit(0)
root=Path(__file__).resolve().parents[1]
def module(name,file):
 s=importlib.util.spec_from_file_location(name,root/'scripts'/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('workshop','nightshift-workshop.py');rt=module('runtime','nightshift-runtime.py')
class Probe(m.Run):
 def save(self):
  self.state['elapsed_seconds']=time.monotonic()-self.started
  m.write(self.artifacts/'CHECK.json',self.state)
r=Probe.__new__(Probe);r.args=types.SimpleNamespace(auth='subscription');r.limits=dict(m.DEFAULTS,calls=2,cost_usd=.5);r.started=time.monotonic();r.prior_elapsed=0;r.reviewer='sonnet';r.executable=rt.executable('claude');out=Path(tempfile.mkdtemp(prefix='nightshift-quoted-evidence-'));print(out,flush=True)
r.state=dict(cache={},calls=[],elapsed_seconds=0,cost_usd=0,input_tokens=0,output_tokens=0)
r.env={k:v for k,v in os.environ.items() if k not in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','OPENAI_API_KEY','CODEX_API_KEY')};r.env['CLAUDE_CODE_MAX_OUTPUT_TOKENS']='4096'
bad=json.loads((root/'tests/fixtures/workshop-false-pass.json').read_text())
good={'spec':{'requirements':[{'id':'sources','criterion':'Do not treat supplied URLs as proof, and keep synthetic examples labeled synthetic.'},{'id':'tone','criterion':'Use a respectful coaching tone.'}]},'prompt':'Be a respectful coach. Keep synthetic examples labeled synthetic; URLs are not verified claims.', 'cases':[{'id':'control','criteria':['sources','tone'],'kind':'positive','input':'Synthetic exercise: compare hypothetical Tool A, placeholder https://tool-a.test.','expected':'Keep the synthetic label and explain uncertainty respectfully.'}], 'observations':[{'case':'control','response':'We can explore this synthetic example together. Tool A and https://tool-a.test remain hypothetical, not verified real-world evidence. What would you like to test?'}]}
for label,payload,want in [('bad',bad,False),('good',good,True)]:
 r.artifacts=out/label;r.artifacts.mkdir();payload={k:payload[k] for k in ['spec','prompt','cases','observations']}
 try: actual=r.reviewed('code-review-'+label,payload)
 except ValueError as e: actual=False;print(label,str(e),flush=True)
 review_path=r.artifacts/('code-review-'+label+'.json')
 assert review_path.exists(), 'No reviewer verdict; probe failed. Inspect retained CHECK.json; this is not a rejection pass.'
 review=json.loads(review_path.read_text())
 assert actual==want,(label,review)
 if label=='bad':
  target=next(a for a in review['assessments'] if a['case']=='case-7' and a['requirement']=='sourced-competitor-claims')
  assert target['verdict']=='fail',target
 print(label,'PASS',flush=True)
