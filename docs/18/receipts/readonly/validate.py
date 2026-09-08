#!/usr/bin/env python3
"""Bind the predeclared execution oracle to observed Codex CLI completion events."""
import hashlib,json,pathlib,re,shlex,sys
base=pathlib.Path(__file__).parent
root=base/'codex-legacy'
raw=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else base/'raw.jsonl'
report=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else base/'report.json'
failures=[]
def check(ok, reason):
    if not ok: failures.append(reason)
baseline=json.loads((base/'baseline.json').read_text())
for name,digest in baseline.items():
    path=root/name
    check(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Fixture changed: '+name)
events=[json.loads(line) for line in raw.read_text().splitlines() if line.strip()]
commands=[e['item'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='command_execution']
expected="python3 ./fixture_test.py --label 'two words' --mode exact"
matched=[]
for item in commands:
    argv=shlex.split(item.get('command',''))
    if argv==['/bin/zsh','-lc',expected]: matched.append(item)
check(len(matched)==1,'Require exactly one actual completed execution of exact fixture command')
if len(matched)==1:
    item=matched[0]
    check(item.get('status')=='completed' and item.get('exit_code')==0,'Actual command did not complete successfully')
    output=item.get('aggregated_output','')
    records=[line.partition('=')[2] for line in output.splitlines() if line.startswith('NIGHTSHIFT_FIXTURE_ARGV=')]
    check(len(records)==1 and json.loads(records[0])==['--label','two words','--mode','exact'],'Actual execution argv output mismatch')
    check(bool(re.search(r'^Ran 1 test in [0-9.]+s$',output,re.M)) and bool(re.search(r'^OK$',output,re.M)),'Actual output missing one-test unittest success')
    check('test_arguments (__main__.ExactInvocation.test_arguments) ... ok' in output,'Actual argv assertion did not pass')
r=json.loads(report.read_text())
check(r.get('status')=='SUCCESS' and r.get('results')=={'passed':1,'failed':0},'Normalized result disagrees with actual execution')
check(r.get('artifacts',{}).get('provider')=='codex','Wrong provider provenance')
reason=r.get('reason','')
check(expected in reason and str(root/'CLAUDE.md')+':6' in reason,'Missing exact command or source-line provenance')
check('Legacy fallback' in reason and 'no neutral instructions or configured test command' in reason,'Missing legacy fallback rationale')
hashes={str(path.relative_to(base)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [raw,report,base/'baseline.json',root/'fixture_test.py',root/'CLAUDE.md']}
print(json.dumps({'status':'FAIL' if failures else 'PASS','failures':failures,'evidence_sha256':hashes},indent=2))
sys.exit(bool(failures))
