#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$ROOT" <<'PY'
import copy,hashlib,json,os,pathlib,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(sys.argv[1]);SCRIPT=ROOT/'scripts/nightshift-failure-memory.sh'
NEXT='inspect the final gate output and repair the smallest in-scope cause'
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def event(ticket,day,status='failed',provider='codex',gate='review'):
    return dict(ticket=ticket,generated_at='2026-09-%02dT00:00:00Z'%day,gate=gate,provider=provider,status=status,
        attempts=[dict(attempt=1,exit_code=0 if status=='complete' else 1,output='PRIVATE-SENTINEL',command='touch /tmp/never')],
        next_action='continue to the next gate' if status=='complete' else NEXT,
        output='PRIVATE-SENTINEL',worktree='/private/PRIVATE-SENTINEL',commands={'attempt':'PRIVATE-SENTINEL'})
def identity(row):return digest({k:row[k] for k in ('ticket','generated_at','gate','provider')})
def signature(row):return digest(dict(gate=row['gate'],provider=row['provider'],status=row['status'],exit_code=1,next_action_category='inspect-and-repair'))
class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.box=tempfile.TemporaryDirectory(prefix='nightshift-learning-');self.addCleanup(self.box.cleanup)
        self.p=pathlib.Path(self.box.name);self.receipts=self.p/'receipts.jsonl';self.registry=self.p/'learnings.json';self.marker=self.p/'EXECUTED'
        self.rows=[event('PRIVATE-SENTINEL-a',1),event('PRIVATE-SENTINEL-b',2),event('PRIVATE-SENTINEL-c',3,'complete'),event('d',5,'complete'),event('e',6,'complete'),event('f',7)]
        self.write_rows(self.rows);self.write_registry([])
    def write_rows(self,rows):self.receipts.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    def write_registry(self,entries):self.registry.write_text(json.dumps(dict(schema_version=1,learnings=entries)))
    def run_report(self,good=True,args=None):
        self.assertTrue(SCRIPT.is_file(),'failure-memory entrypoint must exist')
        result=subprocess.run(['bash',str(SCRIPT),*(args if args is not None else ['--project',str(self.p),'--receipts','receipts.jsonl','--learnings','learnings.json'])],text=True,capture_output=True,timeout=20,cwd='/tmp')
        self.assertNotIn('PRIVATE-SENTINEL',result.stdout+result.stderr)
        if good:
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(len(result.stdout.splitlines()),1)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,'');return result
    def adopt(self):
        mechanism=self.p/'guardrail.py';mechanism.write_text('raise SystemExit("never execute inspected evidence")\n')
        ids=[identity(r) for r in self.rows[:2]]
        entry=dict(id='learning-1',signature=signature(self.rows[0]),adopted_at='2026-09-04T00:00:00Z',kind='guardrail',mechanism='guardrail.py',evidence=ids,validation='validation.json')
        validation=dict(schema_version=1,status='passed',mechanism='guardrail.py',sha256=hashlib.sha256(mechanism.read_bytes()).hexdigest(),evidence=ids,validated_at='2026-09-03T00:00:00Z')
        (self.p/'validation.json').write_text(json.dumps(validation));self.write_registry([entry]);return entry,validation
    def test_clustering_deduplication_and_order(self):
        a=self.run_report();self.assertEqual(a['receipt_count'],6);self.assertEqual(len(a['clusters']),1)
        cluster=a['clusters'][0];self.assertEqual(cluster['signature'],signature(self.rows[0]));self.assertEqual(cluster['count'],3);self.assertTrue(cluster['repeated'])
        duplicate=copy.deepcopy(self.rows[0]);duplicate['output']='different private output'
        self.write_rows(list(reversed(self.rows))+[duplicate]);self.assertEqual(a,self.run_report())
        self.write_rows([self.rows[0]]);self.assertFalse(self.run_report()['clusters'][0]['repeated'])
    def test_supported_learning_and_observational_improvement(self):
        self.adopt();before={x.name:x.read_bytes() for x in self.p.iterdir()}
        report=self.run_report();learning=report['learnings'][0];self.assertEqual(learning['status'],'supported');self.assertEqual(learning['reasons'],[])
        outcome=learning['outcomes'];self.assertEqual(outcome['status'],'improved')
        self.assertEqual(outcome['before']['total_runs'],3);self.assertEqual(outcome['after']['total_runs'],3)
        self.assertAlmostEqual(outcome['before']['completion_rate'],1/3);self.assertAlmostEqual(outcome['after']['completion_rate'],2/3)
        self.assertEqual(outcome['before']['recurrences'],2);self.assertEqual(outcome['after']['recurrences'],1)
        self.assertEqual(before,{x.name:x.read_bytes() for x in self.p.iterdir()})
    def test_unsupported_missing_stale_failed_and_mismatched_evidence(self):
        entry,valid=self.adopt()
        variants=[dict(entry,kind='prompt'),dict(entry,mechanism='../outside'),dict(entry,mechanism='missing'),dict(entry,evidence=[]),dict(entry,evidence=[entry['evidence'][0]]),dict(entry,evidence=['0'*64,entry['evidence'][0]]),dict(entry,signature='0'*64),dict(entry,validation='absent')]
        for field in ('mechanism','validation','evidence'):
            v=dict(entry);del v[field];variants.append(v)
        for v in variants:
            self.write_registry([v]);r=self.run_report()['learnings'][0];self.assertEqual(r['status'],'unsupported');self.assertTrue(r['reasons']);self.assertEqual(r['outcomes']['status'],'unknown')
        self.write_registry([entry])
        for change in ({'status':'failed'},{'sha256':'0'*64},{'evidence':[]},{'mechanism':'other'},{'validated_at':'2026-09-05T00:00:00Z'},{'validated_at':'2026-09-01T00:00:00Z'}):
            (self.p/'validation.json').write_text(json.dumps(dict(valid,**change)));self.assertEqual(self.run_report()['learnings'][0]['status'],'unsupported')
        (self.p/'validation.json').write_text(json.dumps(valid));(self.p/'guardrail.py').write_text('changed content')
        self.assertEqual(self.run_report()['learnings'][0]['status'],'unsupported')
    def test_time_cohorts_provider_gate_and_outcome_classes(self):
        self.adopt();base=self.rows[:3]
        for after,expected in (([], 'insufficient_evidence'),([event('later',5)],'regressed'),([event('later',5,'complete')],'improved'),([event('later',5),event('later2',6),event('later3',7,'complete')],'unchanged')):
            rows=base+after+[event('same-time',4,'complete'),event('other-provider',6,'complete','claude'),event('other-gate',6,'complete',gate='qa')]
            self.write_rows(rows);r=self.run_report()['learnings'][0]['outcomes'];self.assertEqual(r['status'],expected);self.assertEqual(r['before']['total_runs'],3);self.assertEqual(r['after']['total_runs'],len(after))
        entry,_=self.adopt();entry['adopted_at']='2026-09-02T00:00:00Z';self.write_registry([entry]);self.assertEqual(self.run_report()['learnings'][0]['status'],'unsupported')
    def test_conflicting_identity_and_invalid_data_fail_sanitized(self):
        contradiction=dict(self.rows[0],status='complete',attempts=[dict(attempt=1,exit_code=0)])
        self.write_rows(self.rows+[contradiction]);self.run_report(False)
        for field,value in [('status','PRIVATE-SENTINEL'),('generated_at','2026-02-30T00:00:00Z'),('provider','PRIVATE-SENTINEL'),('attempts',[dict(attempt=1,exit_code=True)]),('attempts',[dict(attempt=1,repair_after_attempt=1,exit_code=1)]),('attempts',[])]:
            bad=dict(self.rows[0],**{field:value});self.write_rows([bad]);self.run_report(False)
        for raw in ('{PRIVATE-SENTINEL','{"ticket":"PRIVATE-SENTINEL","ticket":"duplicate"}\n','NaN\n',''):
            self.receipts.write_text(raw);self.run_report(False);self.assertEqual(self.receipts.read_text(),raw)
        self.write_rows(self.rows);entry,_=self.adopt();self.write_registry([entry,entry]);self.run_report(False)
    def test_confined_paths_and_no_execution(self):
        self.adopt();other=pathlib.Path(tempfile.mkdtemp(prefix='nightshift-learning-outside-'))
        self.addCleanup(lambda: __import__('shutil').rmtree(other))
        external=other/'outside';external.write_text('PRIVATE-SENTINEL');(self.p/'escape').symlink_to(external)
        for path in ('../outside',str(self.receipts),'escape','missing'):
            self.run_report(False,['--project',str(self.p),'--receipts',path,'--learnings','learnings.json'])
        entry,_=self.adopt();entry['mechanism']='escape';self.write_registry([entry]);self.assertEqual(self.run_report()['learnings'][0]['status'],'unsupported')
        for row in self.rows:row['next_action']='touch '+str(self.marker);row['output']='$(touch '+str(self.marker)+') PRIVATE-SENTINEL'
        self.write_rows(self.rows);self.write_registry([]);self.run_report();self.assertFalse(self.marker.exists())
        self.run_report(False,['--project',str(self.p),'--unknown','PRIVATE-SENTINEL'])
    def test_last_ordinary_attempt_and_blocked_without_attempts(self):
        row=self.rows[0];row['attempts']=[dict(attempt=1,exit_code=1),dict(repair_after_attempt=1,exit_code=0)]
        self.write_rows([row]);self.assertEqual(self.run_report()['clusters'][0]['exit_code'],1)
        row=dict(row,status='blocked',attempts=[],next_action='Configure NIGHTSHIFT_WORKER_IMAGE; host execution is disabled.')
        self.write_rows([row]);c=self.run_report()['clusters'][0];self.assertIsNone(c['exit_code']);self.assertEqual(c['next_action_category'],'configure-isolation')
unittest.main(argv=[sys.argv[0]],verbosity=2)
PY
