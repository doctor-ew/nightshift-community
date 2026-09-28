#!/usr/bin/env python3
"""Measure optional shadow review on explicit labelled public evidence."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('efficiency',HERE/'nightshift-efficiency.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


def evaluate(corpus, settings, request=None):
    request=request or e.bounded_request
    if not isinstance(corpus,dict) or set(corpus)!={'version','cases'} or corpus['version']!=1 or not 2<=len(corpus['cases'])<=12:raise ValueError('invalid_evaluation_corpus')
    rows=[];key=os.environ.get(settings['key_env']);started=time.monotonic()
    for case in corpus['cases']:
        if set(case)!={'id','evidence','defective'} or type(case['defective']) is not bool or not isinstance(case['evidence'],str) or len(case['evidence'])>8000:raise ValueError('invalid_evaluation_case')
        row=dict(id=case['id'],expected_defective=case['defective'],request_attempted=False,status='unavailable',reason='NO_KEY',caught=None,usage=None)
        if key:
            body=e.encoded(dict(state=case['evidence'],model=settings['model'],questions=e.QUESTIONS))
            row['request_attempted']=True
            try:
                response=json.loads(request(settings,key,body));answers=response['answers']
                values=[answers[k]['noul'] for k in e.QUESTIONS]
                if any(type(v) not in (int,float) or not 0<=v<=1 for v in values):raise ValueError('invalid_judgment')
                row.update(status='evaluated',reason='SHADOW_ONLY',caught=values[0]<0.5,usage=response.get('usage'),judgments=dict(zip(e.QUESTIONS,values)))
            except (OSError,ValueError,KeyError,e.Invalid):row['reason']='EVALUATION_FAILED'
        rows.append(row)
    evaluated=[r for r in rows if r['status']=='evaluated']
    tp=sum(r['caught'] and r['expected_defective'] for r in evaluated)
    fp=sum(r['caught'] and not r['expected_defective'] for r in evaluated)
    return dict(version=1,status='measured' if len(evaluated)==len(rows) else 'incomplete',cases=rows,
                service_requests=sum(r['request_attempted'] for r in rows),defects_caught=tp,false_positives=fp,
                evaluated_cases=len(evaluated),elapsed_seconds=time.monotonic()-started,
                claude_calls_avoided=0,actual_billed_usd=None,
                recommendation='keep_optional_shadow_only',limitations=['Small labelled public corpus, not consumer certification.','No required reviewer is replaced; avoided Claude calls are zero.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--corpus',required=True);parser.add_argument('--out',required=True);parser.add_argument('--project',default='.')
    args=parser.parse_args()
    settings=e.config(argparse.Namespace(action='evaluate',project=args.project))['jev']
    output=Path(args.out)
    with output.open('x') as stream:json.dump(evaluate(json.loads(Path(args.corpus).read_text()),settings),stream,indent=2)
