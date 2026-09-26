#!/usr/bin/env python3
"""Typed verification observations; legacy output remains non-authoritative."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
PROFILES={'python-unittest-v1':'python3','node-test-v1':'node','legacy-wrapper-v1':'bash'}
COUNTS=('total','passed','failed','errors','skipped','expected_failures','unexpected_successes')


def profile(check):
    selected=check.get('adapter',{'python3':'python-unittest-v1','node':'node-test-v1','bash':'legacy-wrapper-v1'}.get(check['argv'][0]))
    selected={'unittest-v1':'python-unittest-v1','legacy-log-v1':'legacy-wrapper-v1'}.get(selected,selected)
    if selected not in PROFILES or PROFILES[selected]!=check['argv'][0]:raise ValueError('verification_adapter_missing_or_incompatible')
    return selected


def assets(check):
    selected=profile(check)
    names=['nightshift-verification-adapters.py']+(['nightshift-verification-python.py'] if selected=='python-unittest-v1' else ['nightshift-verification-node.mjs'] if selected=='node-test-v1' else [])
    return {name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in names}


def command(check,target,events,binding,environment):
    selected=profile(check);env=dict(environment)
    if not shutil.which(PROFILES[selected]):raise ValueError('verification_runtime_missing:'+PROFILES[selected])
    if selected=='python-unittest-v1':argv=['python3','-I',str(HERE/'nightshift-verification-python.py'),str(target/check['argv'][1]),str(events),binding]
    elif selected=='node-test-v1':
        argv=['node','--test','--test-reporter='+str(HERE/'nightshift-verification-node.mjs'),str(target/check['argv'][1])]
        env.update(NIGHTSHIFT_TEST_EVENTS=str(events),NIGHTSHIFT_TEST_BINDING=binding)
    else:argv=check['argv']
    return argv,env


def observe(check,events,binding,code,raw,termination=None):
    selected=profile(check);counts={key:0 for key in COUNTS};complete=False;reason=termination
    value=None
    if selected=='legacy-wrapper-v1':reason=reason or 'legacy_wrapper_requires_typed_check:no_summary_admission'
    else:
        try:
            if events.is_symlink() or events.stat().st_size>1000000:raise ValueError('unsafe_typed_report')
            def unique(items):
                result={}
                for key,item in items:
                    if key in result:raise ValueError('typed_duplicate_field')
                    result[key]=item
                return result
            value=json.loads(events.read_text(),object_pairs_hook=unique)
            if not isinstance(value,dict) or type(value.get('version')) is not int or value.get('version')!=1 or value.get('adapter')!=selected or value.get('binding')!=binding or type(value.get('complete')) is not bool or not isinstance(value.get('runs'),list):raise ValueError('invalid_typed_report')
            seen=set()
            for run in value['runs']:
                if not isinstance(run,dict) or run.get('complete') is not True or not isinstance(run.get('counts'),dict) or set(run['counts'])!=set(COUNTS):raise ValueError('partial_typed_execution')
                if any(type(n) is not int or n<0 for n in run['counts'].values()):raise ValueError('invalid_typed_counts')
                c=run['counts']
                if c['total']!=sum(c[k] for k in COUNTS if k!='total'):raise ValueError('inconsistent_typed_counts')
                if selected=='python-unittest-v1':
                    tests=run.get('tests')
                    if not isinstance(tests,list):raise ValueError('missing_test_lifecycles')
                    actual={key:0 for key in COUNTS}
                    for test in tests:
                        if not isinstance(test,dict) or set(test)!={'id','status'} or not isinstance(test['id'],str) or not test['id'] or test['id'] in seen or test['status'] not in COUNTS[1:]:raise ValueError('invalid_test_lifecycle')
                        seen.add(test['id']);actual['total']+=1;actual[test['status']]+=1
                    if actual!=c:raise ValueError('test_lifecycle_count_mismatch')
                for key in COUNTS:counts[key]+=c[key]
            complete=value['complete']
            if value.get('error'):reason=reason or 'typed_execution_error'
            if not complete:reason=reason or 'partial_typed_execution'
            if selected=='node-test-v1' and value.get('success') is not True:reason=reason or 'node_runner_failed'
        except (OSError,ValueError,TypeError,KeyError) as error:reason=reason or 'typed_report_unavailable:'+str(error)
    executed=counts['passed']+counts['failed']+counts['errors']+counts['unexpected_successes']
    passed=complete and code==0 and executed>0 and counts['failed']==counts['errors']==counts['unexpected_successes']==0 and not reason
    raw_hash=hashlib.sha256(b'').hexdigest()
    if raw.exists():
        with raw.open('rb') as stream:raw_hash=hashlib.file_digest(stream,'sha256').hexdigest()
    text=raw.read_text(errors='replace') if raw.exists() and raw.stat().st_size<=500000 else ''
    if raw.exists() and raw.stat().st_size>500000:reason='verification_evidence_too_large';passed=False
    return dict(version=1,id=check['id'],argv=check['argv'],adapter=selected,adapter_assets=assets(check),binding=binding,complete=complete,status='passed' if passed else 'blocked',reason=reason or ('' if passed else 'failed_or_vacuous_tests'),exit_code=code,counts=counts,tests=executed if passed else 0,output=text,output_sha256=raw_hash,events_sha256=hashlib.sha256(events.read_bytes()).hexdigest() if events.is_file() and not events.is_symlink() and events.stat().st_size<=1000000 else None,runtime=value.get('runtime') if isinstance(value,dict) else None)


# Runtime identity follows the integrated #96 unittest adapter.
def identity(environment):
    interpreter=shutil.which('python3',path=environment.get('PATH'))
    if not interpreter:raise ValueError('verification_interpreter_missing')
    code="import hashlib,json,pathlib,sys,unittest; root=pathlib.Path(unittest.__file__).parent; print(json.dumps(dict(executable=sys.executable,version=sys.version,unittest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))})))"
    result=subprocess.run([interpreter,'-I','-c',code],env=environment,capture_output=True,text=True,timeout=5,check=True)
    value=json.loads(result.stdout)
    value['executable_sha256']=hashlib.sha256(Path(interpreter).read_bytes()).hexdigest()
    return value

