#!/usr/bin/env python3
"""Versioned verification adapter identities and strict observation validation."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ADAPTER='unittest-v1'
STATUSES={'running','passed','failed','skipped','expected_failure','unexpected_success'}


def identity(environment):
    interpreter=shutil.which('python3',path=environment.get('PATH'))
    if not interpreter:raise ValueError('verification_interpreter_missing')
    code="import hashlib,json,pathlib,sys,unittest; root=pathlib.Path(unittest.__file__).parent; print(json.dumps(dict(executable=sys.executable,version=sys.version,unittest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))})))"
    result=subprocess.run([interpreter,'-I','-c',code],env=environment,capture_output=True,text=True,timeout=5,check=True)
    value=json.loads(result.stdout)
    value['executable_sha256']=hashlib.sha256(Path(interpreter).read_bytes()).hexdigest()
    return value


def observation(path,exit_code):
    raw=path.read_bytes() if path.exists() and not path.is_symlink() and path.stat().st_size<=1000000 else b''
    result=dict(adapter=ADAPTER,receipt_sha256=hashlib.sha256(raw).hexdigest(),receipt=None,status='failed',reason='typed_receipt_missing',counts={key:0 for key in STATUSES})
    try:
        if len(raw)>1000000:raise ValueError('typed_receipt_too_large')
        def unique(items):
            value={}
            for key,item in items:
                if key in value:raise ValueError('typed_duplicate_field')
                value[key]=item
            return value
        value=json.loads(raw,object_pairs_hook=unique)
        if not isinstance(value,dict) or set(value)!={'version','complete','tests','error'} or type(value['version']) is not int or value['version']!=1 or type(value['complete']) is not bool or not isinstance(value['tests'],list) or len(value['tests'])>10000:raise ValueError('typed_receipt_malformed')
        result['receipt']=value;seen=set()
        for row in value['tests']:
            if not isinstance(row,dict) or set(row)!={'id','status'} or not isinstance(row['id'],str) or not row['id'] or len(row['id'])>4000 or row['id'] in seen or row['status'] not in STATUSES:raise ValueError('typed_test_identity_or_status_invalid')
            seen.add(row['id']);result['counts'][row['status']]+=1
        if value['error'] is not None or not value['complete'] or result['counts']['running']:raise ValueError('typed_execution_incomplete')
        if exit_code!=0 or result['counts']['failed'] or result['counts']['unexpected_success']:raise ValueError('typed_execution_failed')
        if not result['counts']['passed']:raise ValueError('typed_no_useful_tests')
        result.update(status='passed',reason=None)
    except (OSError,ValueError,KeyError,TypeError) as error:result['reason']=str(error) or 'typed_receipt_malformed'
    return result
