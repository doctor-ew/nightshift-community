#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
python3 - "$ROOT" <<'PYTEST'
import copy,json,os,subprocess,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1])
recorder=root/'scripts/nightshift-trajectory.py'
replay=root/'evals/trajectory/replay.py'
assert recorder.is_file(), 'trajectory recording capability must exist'
assert replay.is_file(), 'offline replay capability must exist'
def run(*args,env=None):
    return subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True,env=env)
def passed(result):
    assert result.returncode==0, result.stdout+result.stderr
result=run(replay); passed(result)
baseline_path=root/'evals/trajectory/baseline.json'
original=baseline_path.read_bytes(); baseline=json.loads(original)
required={'success','repaired-success','exhausted-failure','missing-isolation','needs-decision','deny-removal','deny-production','adversarial-route'}
assert set(baseline)==required, 'baseline must cover all eight core scenarios'
assert {v.get('status') for v in baseline.values()} >= {'complete','failed','blocked','needs-decision'}
assert baseline['adversarial-route']['route']['provider']!='claude', 'adversarial route must cross provider'
secret='trajectory-test-secret-should-never-escape'
env=dict(os.environ,ANTHROPIC_API_KEY=secret,OPENAI_API_KEY=secret,NIGHTSHIFT_PRODUCTION_CONFIRMATION_TOKEN=secret)
for name in sorted(required):
    r=run(recorder,'--scenario',name,env=env); passed(r)
    record=json.loads(r.stdout)
    assert record==baseline[name], name+' deterministic output'
    assert secret not in r.stdout and str(root) not in r.stdout
    def clean(node):
        if isinstance(node,dict):
            assert not ({'command','commands','output','worktree','ticket','changed_files','next_action','timestamp','generated_at'} & set(node)), 'raw receipt fields leaked'
            for v in node.values(): clean(v)
        elif isinstance(node,list):
            for v in node: clean(v)
    clean(record)
with tempfile.TemporaryDirectory(prefix='nightshift-trajectory-test-') as temporary:
    target=Path(temporary)/'mutated.json'
    def rejects(data,label):
        target.write_text(json.dumps(data)); r=run(replay,'--baseline',target)
        assert r.returncode!=0, label+' regression was silently accepted'
    mutated=copy.deepcopy(baseline); mutated['success']['tool_order'].pop(); rejects(mutated,'removed tool')
    mutated=copy.deepcopy(baseline); order=mutated['repaired-success']['tool_order']
    pair=next((i,j) for i in range(len(order)) for j in range(i+1,len(order)) if order[i]!=order[j])
    i,j=pair; order[i],order[j]=order[j],order[i]; rejects(mutated,'reordered tools')
    mutated=copy.deepcopy(baseline); mutated['deny-removal']['policy_decisions'][0]['decision']='allow'; rejects(mutated,'guardrail decision')
    mutated=copy.deepcopy(baseline); del mutated['success']['repair_budget']; rejects(mutated,'missing receipt evidence')
    mutated=copy.deepcopy(baseline); del mutated['adversarial-route']['route']['provider']; rejects(mutated,'routing evidence')
    mutated=copy.deepcopy(baseline); del mutated['success']; rejects(mutated,'missing scenario')
    target.write_text('{invalid'); assert run(replay,'--baseline',target).returncode!=0
assert baseline_path.read_bytes()==original, 'replay rewrote committed baseline'
workflow=(root/'.github/workflows/shellcheck.yml').read_text()
assert workflow.count("'nightshift/**'")>=2, 'stacked pushes and PRs must trigger offline CI'
print('PASS: trajectory replay, sanitization, order, policy, evidence and baseline mutations')
PYTEST
