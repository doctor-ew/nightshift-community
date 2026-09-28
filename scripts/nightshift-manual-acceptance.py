#!/usr/bin/env python3
"""Shared explicit manual-case attestation policy for operations and recovery."""
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def exact(value, keys):
    if not isinstance(value,dict) or set(value)!=set(keys.split()):
        raise ValueError('invalid_shape:' + keys)


def validate(required, binding, attestation):
    if not isinstance(attestation,dict) or attestation.get('binding')!=binding:
        raise ValueError('bound_human_attestation_required')
    if not required:
        exact(attestation,'binding accepted')
        if attestation['accepted'] is not True:raise ValueError('manual_acceptance_pending')
        return dict(binding=binding,accepted=True,cases=[])
    exact(attestation,'binding cases')
    if len(json.dumps(attestation,ensure_ascii=False).encode())>12000:raise ValueError('manual_acceptance_too_large')
    rows=attestation['cases']
    if not isinstance(rows,list) or len(rows)!=len(required):raise ValueError('manual_cases_incomplete')
    expected={case['id']:digest(case) for case in required};seen=set();normalized=[]
    for row in rows:
        exact(row,'id case_sha256 passed observation evidence')
        if not isinstance(row['id'],str) or row['id'] not in expected or row['id'] in seen or row['case_sha256']!=expected[row['id']]:raise ValueError('manual_case_identity_changed')
        if row['passed'] is not True:raise ValueError('manual_acceptance_pending')
        for key in ('observation','evidence'):
            if not isinstance(row[key],str) or not row[key].strip() or '\0' in row[key] or len(row[key].encode())>2048:raise ValueError('manual_case_observation_required')
        seen.add(row['id']);normalized.append(dict(row))
    return dict(binding=binding,accepted=True,cases=sorted(normalized,key=lambda row:row['id']))

