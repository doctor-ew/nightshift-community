#!/usr/bin/env python3
"""Task-bound behavioral evidence, deterministic oracles and bounded execution."""
import sys
sys.dont_write_bytecode = True

import argparse
from collections import deque
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import tomllib
import uuid

MAX_JSON = 1024 * 1024
MAX_LOG = 4 * MAX_JSON
TASK_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z')
SHA_RE = re.compile(r'[0-9a-f]{64}\Z')
PROFILE = 'claude-subscription-text-v1'
MULTITURN_PROFILE = 'claude-subscription-multiturn-text-v1'
RISKS = {'deterministic_logic', 'prompt_behavior', 'agent_behavior', 'runtime_interaction', 'safety_sensitive'}
MODEL_RISKS = {'prompt_behavior', 'agent_behavior', 'runtime_interaction'}
KINDS = {'prototype', 'deterministic', 'not_applicable'}
DEFAULTS = dict(version=1, development_calls=8, final_calls=2, repairs=2,
                infrastructure_failures=2, timeout_seconds=120,
                output_bytes=1048576, force_prompt=False)
ENGINE = Path(__file__).resolve(strict=True)
HERE = ENGINE.parent


class Invalid(Exception):
    pass


class Blocked(Exception):
    pass


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


context = None
retry = None


def dependencies():
    global context, retry
    if context is None:
        context = module('nightshift_context', 'nightshift-project-context.py')
    if retry is None:
        retry = module('nightshift_retry', 'nightshift-retry-budget.py')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def semantics(doc):
    value = copy.deepcopy(doc)
    value['applicability']['review'] = None
    for case in value['cases']:
        case['applicability']['review'] = None
    return digest(value)


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise Invalid('schema_keys')


def text(value, nonempty=True):
    if not isinstance(value, str) or (nonempty and not value.strip()) or '\0' in value:
        raise Invalid('schema_string')
    return value


def integer(value, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise Invalid('schema_integer')
    return value


def strings(value, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise Invalid('schema_array')
    for item in value:
        text(item)
    if len(value) != len(set(value)):
        raise Invalid('schema_duplicate')
    return value


def hash_string(value):
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise Invalid('schema_digest')
    return value


def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise Invalid('nonfinite_json')
    if isinstance(value, dict):
        for item in value.values():
            finite(item)
    if isinstance(value, list):
        for item in value:
            finite(item)


def parse_json(data):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise Invalid('duplicate_json_key')
            value[key] = item
        return value
    try:
        value = json.loads(data, object_pairs_hook=pairs)
        finite(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise Invalid('invalid_json') from None


def relative(value):
    text(value)
    parts = value.split('/')
    if (value.startswith(('/', '-', '~')) or any(p in ('', '.', '..') for p in parts)
            or any(c in value for c in '\\*?[]`\n\r\t')):
        raise Invalid('invalid_relative_path')
    return value


def confined(project, value, missing=False):
    """Regular project artifacts cannot use a symlink at any component."""
    relative(value)
    current = project
    for index, part in enumerate(Path(value).parts):
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if missing:
                return None
            raise Blocked('artifact_missing') from None
        if stat.S_ISLNK(info.st_mode):
            raise Blocked('artifact_symlink')
        if index < len(Path(value).parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise Blocked('artifact_unsupported')
    return current


def public_relative(project, value):
    """Canonicalize only the project ancestor, retaining every descendant link."""
    supplied = Path(value)
    if not supplied.is_absolute():
        return relative(str(supplied))
    # Search from the filesystem root inward, stopping at the project boundary.
    # Resolving the supplied leaf would erase evidence of an illicit leaf link.
    for ancestor in reversed(supplied.parents):
        try:
            physical = ancestor.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if physical == project:
            return relative(str(supplied.relative_to(ancestor)))
    raise Invalid('public_scenarios_outside_project')


def regular(path):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o444:
        raise Blocked('artifact_unreadable')
    return info


def bounded(path, limit=MAX_JSON):
    path = Path(path)
    info = regular(path)
    if info.st_size > limit:
        raise Invalid('artifact_oversized')
    with path.open('rb') as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise Invalid('artifact_oversized')
    return value


def read_json(path):
    return parse_json(bounded(path))


def file_hash(path):
    regular(path)
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(65536):
            result.update(chunk)
    return result.hexdigest()


def private_file(path):
    path = Path(path)
    if not path.is_absolute():
        raise Invalid('absolute_private_path_required')
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if stat.S_ISLNK(current.lstat().st_mode):
            raise Blocked('private_path_symlink')
    regular(path)
    return path


def identity(value):
    exact(value, ('provider', 'author_id'))
    text(value['provider']); text(value['author_id'])
    return value


def applicability(value):
    exact(value, ('kind', 'rationale', 'risks', 'review'))
    text(value['kind']); text(value['rationale'])
    if value['kind'] not in KINDS:
        raise Invalid('invalid_applicability')
    risks = set(strings(value['risks']))
    if not risks <= RISKS or (risks & MODEL_RISKS and value['kind'] != 'prototype'):
        raise Invalid('risk_downgrade')
    if value['kind'] == 'not_applicable' and (risks or not re.search(r'doc|documentation', value['rationale'], re.I)):
        raise Invalid('not_applicable_requires_documentation')
    review = value['review']
    if review is not None:
        exact(review, ('reviewer_provider', 'reviewer_author_id', 'decision', 'reviewed_input_sha256', 'evidence_sha256'))
        text(review['reviewer_provider']); text(review['reviewer_author_id'])
        if review['decision'] not in ('approve', 'repair'):
            raise Invalid('invalid_review')
        hash_string(review['reviewed_input_sha256']); hash_string(review['evidence_sha256'])


def assertion(value):
    if not isinstance(value, dict) or value.get('op') not in ('text_equals', 'text_contains', 'json_equals', 'json_field_equals',
                                                                             'json_field_length_at_most', 'json_field_nonempty'):
        raise Invalid('invalid_oracle')
    exact(value, ('op', 'value', 'field') if value['op'].startswith('json_field_') else ('op', 'value'))
    if value['op'].startswith('text_'):
        text(value['value'], False)
    if value['op'].startswith('json_field_'):
        if not isinstance(value['field'], list) or not value['field']:
            raise Invalid('invalid_oracle_field')
        for key in value['field']:
            text(key, False)
    if value['op'] == 'json_field_length_at_most':
        integer(value['value'], 1, 16)
    if value['op'] == 'json_field_nonempty' and value['value'] is not True:
        raise Invalid('invalid_oracle_value')
    finite(value['value'])


def validate_doc(doc, project=None, task=None, private=False):
    exact(doc, ('version', 'task', 'ac_ids', 'author', 'applicability', 'runtime', 'prototype_files', 'cases', 'heldout'))
    if type(doc['version']) is not int or doc['version'] != 1:
        raise Invalid('scenario_version')
    if not isinstance(doc['task'], str) or not TASK_RE.fullmatch(doc['task']) or (task is not None and task != doc['task']):
        raise Invalid('scenario_task')
    acs = set(strings(doc['ac_ids'], True))
    identity(doc['author'])
    applicability(doc['applicability'])
    for path in strings(doc['prototype_files']):
        relative(path)
        if project is not None:
            regular(confined(project, path))
    if not isinstance(doc['cases'], list) or not doc['cases']:
        raise Invalid('cases_missing')
    ids = set(); covered = set(); prototype_acs = set(); optional_acs = set()
    kinds = set(); risks = set(); any_prototype = False
    case_keys = ('id', 'ac_ids', 'required', 'applicability', 'given', 'when', 'then', 'forbidden',
                 'input', 'expected', 'prohibited', 'counterexamples', 'visibility')
    for case in doc['cases']:
        exact(case, case_keys)
        text(case['id'])
        if case['id'] in ids:
            raise Invalid('case_duplicate')
        ids.add(case['id'])
        selected = set(strings(case['ac_ids'], True))
        if not selected <= acs:
            raise Invalid('case_ac_unknown')
        if type(case['required']) is not bool or case['visibility'] != ('held_out' if private else 'public'):
            raise Invalid('case_visibility_or_required')
        for key in ('given', 'when', 'then', 'forbidden'):
            text(case[key], key != 'forbidden')
        strings(case['counterexamples'])
        applicability(case['applicability'])
        kind = case['applicability']['kind']
        risks.update(case['applicability']['risks'])
        if private and kind != 'prototype':
            raise Invalid('private_case_kind')
        if case['required']:
            covered.update(selected); kinds.add(kind)
        for key in ('expected', 'prohibited'):
            if not isinstance(case[key], list):
                raise Invalid('oracle_array')
            for item in case[key]:
                assertion(item)
        if kind == 'prototype':
            any_prototype = True
            if isinstance(doc['runtime'], dict) and doc['runtime'].get('profile') == MULTITURN_PROFILE:
                turns = case['input']
                if not isinstance(turns, list) or not 1 <= len(turns) <= 16:
                    raise Invalid('invalid_turn_count')
                for turn in turns:
                    exact(turn, ('input', 'expected', 'prohibited'))
                    text(turn['input'])
                    for key in ('expected', 'prohibited'):
                        if not isinstance(turn[key], list):
                            raise Invalid('oracle_array')
                        for item in turn[key]:
                            assertion(item)
                    if not turn['expected']:
                        raise Invalid('prototype_oracle_missing')
            else:
                text(case['input'])
            if not case['expected'] or (not case['prohibited'] and not case['forbidden'].strip()):
                raise Invalid('prototype_oracle_missing')
            (prototype_acs if case['required'] else optional_acs).update(selected)
        elif case['input'] is not None:
            text(case['input'])
    if covered != acs or not optional_acs <= prototype_acs:
        raise Invalid('required_ac_coverage')
    derived = 'prototype' if 'prototype' in kinds else ('deterministic' if 'deterministic' in kinds else 'not_applicable')
    if doc['applicability']['kind'] != derived or set(doc['applicability']['risks']) != risks:
        raise Invalid('applicability_summary')
    runtime = doc['runtime']
    if any_prototype:
        runtime_keys = ('profile', 'model', 'cli_version', 'system_prompt_file')
        exact(runtime, runtime_keys + (('response_normalization',) if isinstance(runtime, dict)
                                       and 'response_normalization' in runtime else ()))
        if runtime.get('response_normalization', 'none') not in ('none', 'json-or-single-fence-v1'):
            raise Invalid('unsupported_response_normalization')
        for value in runtime.values():
            text(value)
        relative(runtime['system_prompt_file'])
        if runtime['system_prompt_file'] not in doc['prototype_files']:
            raise Invalid('prompt_outside_prototype')
        if project is not None:
            try:
                text(bounded(confined(project, runtime['system_prompt_file'])).decode('utf-8'))
            except UnicodeError:
                raise Invalid('prompt_encoding') from None
        if runtime['profile'] not in (PROFILE, MULTITURN_PROFILE):
            raise Blocked('unsupported_runtime_profile')
        if private:
            if doc['heldout'] is not None:
                raise Invalid('private_self_commitment')
        else:
            exact(doc['heldout'], ('manifest_sha256', 'case_ids', 'author', 'prepared_at'))
            hash_string(doc['heldout']['manifest_sha256'])
            strings(doc['heldout']['case_ids'], True)
            identity(doc['heldout']['author']); text(doc['heldout']['prepared_at'])
            if ids & set(doc['heldout']['case_ids']):
                raise Invalid('public_private_id_overlap')
    elif runtime is not None or doc['prototype_files'] or doc['heldout'] is not None:
        raise Invalid('unused_prototype_metadata')
    return doc


def reviewed(doc):
    expected = semantics(doc)
    for app in [doc['applicability']] + [case['applicability'] for case in doc['cases']]:
        review = app['review']
        if (review is None or review['decision'] != 'approve' or review['reviewed_input_sha256'] != expected
                or (review['reviewer_provider'], review['reviewer_author_id']) ==
                (doc['author']['provider'], doc['author']['author_id'])):
            raise Blocked('classification_unreviewed')


def config(project):
    # Preserve the context resolver's canonical precedence, including dangling canonical paths.
    candidates = (project / '.nightshift.toml', project / 'nightshift.toml')
    selected = next((path for path in candidates if path.exists() or path.is_symlink()), None)
    values = dict(DEFAULTS)
    if selected is not None:
        try:
            data = tomllib.loads(bounded(selected).decode('utf-8'))
        except (ValueError, UnicodeError):
            raise Invalid('config_invalid') from None
        section = data.get('behavior_proof', {})
        if not isinstance(section, dict) or set(section) - set(DEFAULTS):
            raise Invalid('config_keys')
        values.update(section)
    integer(values['version'], 1, 1)
    for key, low, high in (('development_calls', 1, 64), ('final_calls', 1, 64), ('repairs', 0, 64),
                           ('infrastructure_failures', 0, 2), ('timeout_seconds', 1, 120), ('output_bytes', 1, MAX_JSON)):
        integer(values[key], low, high)
    if type(values['force_prompt']) is not bool:
        raise Invalid('config_force_prompt')
    return values


def forced(doc, policy):
    if policy['force_prompt']:
        covered = {ac for case in doc['cases'] if case['required'] and case['applicability']['kind'] == 'prototype' for ac in case['ac_ids']}
        if covered != set(doc['ac_ids']):
            raise Blocked('force_prompt_coverage_required')


def equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    return left == right


def completion_json(completion, normalization='none'):
    if normalization == 'json-or-single-fence-v1':
        match = re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```', completion.strip(), re.DOTALL)
        if match is not None:
            return parse_json(match.group(1))
    return parse_json(completion)


def evaluate(completion, case, normalization='none'):
    assertions = case['expected'] + case['prohibited']
    parsed = None
    if any(item['op'].startswith('json_') for item in assertions):
        try:
            parsed = completion_json(completion, normalization)
        except Invalid:
            return False
    def holds(item):
        op = item['op']
        if op == 'text_equals':
            return completion == item['value']
        if op == 'text_contains':
            return item['value'] in completion
        value = parsed
        if op.startswith('json_field_'):
            for key in item['field']:
                if not isinstance(value, dict) or key not in value:
                    return False
                value = value[key]
        if op == 'json_field_length_at_most':
            return isinstance(value, list) and len(value) <= item['value']
        if op == 'json_field_nonempty':
            return (isinstance(value, str) and bool(value.strip())) or (isinstance(value, list) and bool(value))
        return equal(value, item['value'])
    return all(holds(item) for item in case['expected']) and not any(holds(item) for item in case['prohibited'])


def assertion_outcomes(completion, case, normalization='none'):
    return {kind: [evaluate(completion, {'expected': [item] if kind == 'expected' else [],
                                        'prohibited': [item] if kind == 'prohibited' else []}, normalization)
                   for item in case[kind]] for kind in ('expected', 'prohibited')}


def git(project, *arguments):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    result = subprocess.run(['git', '-C', str(project), *arguments], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env, timeout=30)
    if result.returncode:
        raise Blocked('git_evidence_unavailable')
    return result.stdout


def git_hash(project, commit, path):
    result = subprocess.Popen(['git', '-C', str(project), 'show', commit + ':' + path],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    value = hashlib.sha256()
    try:
        while chunk := result.stdout.read(65536):
            value.update(chunk)
        if result.wait(timeout=30):
            raise Blocked('locked_artifact_missing')
    finally:
        result.stdout.close()
        if result.poll() is None:
            result.kill(); result.wait()
    return value.hexdigest()


def scope_table(project, task):
    path = confined(project, 'docs/' + task + '/SPEC.md')
    try:
        lines = bounded(path, MAX_LOG).decode('utf-8').splitlines()
    except UnicodeError:
        raise Invalid('spec_encoding') from None
    active = False; found = False; scope = {}; tests = set()
    for line in lines:
        if line.startswith('## '):
            if active:
                break
            if re.fullmatch(r'## Files[ -]to[ -]Change\s*', line):
                active = True; found = True
            continue
        if not active or not line.startswith('|'):
            continue
        fields = [part.strip().strip('`') for part in line.split('|')[1:-1]]
        if len(fields) < 2:
            raise Invalid('scope_table_invalid')
        if fields[0] in ('File', 'Path') or re.fullmatch(r':?-+:?', fields[0]):
            continue
        path = relative(fields[0])
        if path in scope:
            raise Invalid('scope_duplicate')
        scope[path] = fields[1]
        if ('TEST' in fields[1].upper() or path.startswith('tests/')
                or re.search(r'(?:\.test\.|\.spec\.|_test\.)', path)):
            tests.add(path)
    if not found or not scope:
        raise Invalid('scope_missing')
    return scope, tests


def state_directory(project, task=None):
    command = ['bash', str(HERE / 'nightshift-state-dir.sh'), '--project', str(project)]
    if task is not None:
        command += ['--task', task]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    if result.returncode:
        raise Blocked('task_state_unavailable')
    path = Path(result.stdout.decode('utf-8').strip())
    if not path.is_relative_to(project):
        raise Blocked('task_state_external')
    # Directory may be absent for read-only discovery; no creation is attempted.
    current = project
    for part in path.relative_to(project).parts:
        current /= part
        if current.is_symlink():
            raise Blocked('task_state_symlink')
    return path


def lock_identity(project, task, key):
    directory = state_directory(project, task)
    sidecar = directory / (task + '.locks')
    values = []
    for line in bounded(sidecar).decode('utf-8').splitlines():
        if line.startswith(key + '='):
            values.append(line.split('=', 1)[1])
    if len(values) != 1 or not re.fullmatch(r'[0-9a-f]{7,64}', values[0]):
        raise Blocked('lock_identity_missing')
    commit = git(project, 'rev-parse', '--verify', values[0] + '^{commit}').decode().strip()
    git(project, 'merge-base', '--is-ancestor', commit, 'HEAD')
    return commit


def scope_owner(project, task, scope):
    directory = state_directory(project)
    active = directory / ('.active-scope-' + task)
    owner = directory / '.checkout-lease' / 'owner'
    for path in (active, owner):
        confined(project, str(path.relative_to(project)))
    if bounded(owner).decode().strip() != task:
        raise Blocked('scope_owner_mismatch')
    lines = bounded(active).decode().splitlines()
    if not lines or lines[0] != task or not set(scope) <= set(lines[1:]):
        raise Blocked('scope_not_activated')


def snapshot(project, task, scope, final=False):
    if final:
        paths = set(scope)
        paths = {path for path in paths if not path.startswith('docs/' + task + '/')}
    else:
        names = git(project, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')
        paths = {os.fsdecode(name) for name in names.split(b'\0') if name}
        paths = {path for path in paths if not (path == '.nightshift.toml' or path == '.git'
                  or path.startswith(('.git/', '.nightshift/', 'docs/' + task + '/')))}
        paths.update(scope)
    result = {}
    for name in sorted(paths):
        path = confined(project, name, missing=not final)
        result[name] = file_hash(path) if path is not None else None
    return result


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def failure_observations(state):
    """Retained turn failures are authoritative even before case aggregation."""
    return [obs for obs in state['observations'] + state.get('turn_observations', [])
            if obs['outcome'] == 'fail']


def failure_bound(observation, seal):
    return observation['seal_sha256'] in [seal['sha256']] + seal.get('failure_seals', [])


def seal_digest(seal):
    mutable = {'sha256', 'current_prompt', 'revisions', 'red', 'final',
               'development_accepted', 'runtime_observed'}
    return digest({key: value for key, value in seal.items() if key not in mutable})


class Proof:
    def __init__(self, project, task, policy):
        dependencies()
        self.project = project
        self.task = task
        self.policy = policy
        common = Path(git(project, 'rev-parse', '--git-common-dir').decode().strip())
        self.common = (project / common).resolve(strict=True)
        self.path = self.common / 'nightshift' / 'behavior-proof' / task / 'state.json'

    def initial(self):
        return {'version': 1, 'task': self.task, 'seals': [], 'challenges': {},
                'observations': [], 'exposures': [], 'seal': None, 'latest': None}

    @contextmanager
    def transaction(self, readonly=False, allow_policy_change=False):
        with retry.transaction(self.path, self.initial, secure_root=self.common, readonly=readonly) as (state, save):
            if (not isinstance(state, dict) or set(state) - set(self.initial()) - {'budget', 'turn_observations', 'policy_amendments'}
                    or set(self.initial()) - set(state) or type(state['version']) is not int
                    or state['version'] != 1 or state['task'] != self.task):
                raise Blocked('proof_state_invalid')
            if not isinstance(state.get('policy_amendments', []), list):
                raise Blocked('proof_state_invalid')
            if not isinstance(state.get('turn_observations', []), list):
                raise Blocked('proof_state_invalid')
            retry.proof_validate(state)
            for key in ('seals', 'observations', 'exposures'):
                if not isinstance(state[key], list):
                    raise Blocked('proof_state_invalid')
            if not isinstance(state['challenges'], dict):
                raise Blocked('proof_state_invalid')
            if (not allow_policy_change and state.get('budget') and state['budget']['pinned']
                    and state['budget']['policy'] != self.policy):
                raise Blocked('policy_changed')
            yield state, save

    def amend_policy(self, path):
        value = read_json(confined(self.project, public_relative(self.project, path)))
        exact(value, ('version', 'task', 'previous_policy_sha256', 'policy', 'rationale', 'authorization', 'review'))
        if type(value['version']) is not int or value['version'] != 1 or value['task'] != self.task:
            raise Invalid('policy_amendment_identity')
        hash_string(value['previous_policy_sha256']); text(value['rationale'])
        if not equal(value['policy'], self.policy):
            raise Blocked('policy_amendment_target_mismatch')
        authorization = value['authorization']
        exact(authorization, ('path', 'sha256'))
        hash_string(authorization['sha256'])
        authorization_path = relative(authorization['path'])
        if not authorization_path.startswith('docs/' + self.task + '/'):
            raise Invalid('policy_authorization_path')
        source = confined(self.project, authorization_path)
        if file_hash(source) != authorization['sha256'] or not bounded(source).strip():
            raise Blocked('policy_authorization_mismatch')
        review = value['review']
        exact(review, ('provider', 'author_id', 'decision', 'reviewed_input_sha256'))
        identity({'provider': review['provider'], 'author_id': review['author_id']})
        unsigned = dict(value, review=None)
        if review['decision'] != 'approve' or review['reviewed_input_sha256'] != digest(unsigned):
            raise Blocked('policy_amendment_unreviewed')
        author = self.doc()['author']
        if (review['provider'], review['author_id']) == (author['provider'], author['author_id']):
            raise Blocked('policy_amendment_independence')
        with self.transaction(allow_policy_change=True) as (state, save):
            budget = state.get('budget')
            if budget is None or not budget['pinned']:
                raise Blocked('policy_amendment_requires_pinned_budget')
            if any(item['outcome'] == 'pending' for item in budget['attempts'].values()):
                raise Blocked('policy_amendment_pending_attempt')
            previous = budget['policy']
            if digest(previous) != value['previous_policy_sha256']:
                raise Blocked('policy_amendment_stale')
            changed = {key for key in previous if previous[key] != self.policy[key]}
            if (not changed or changed - {'repairs', 'development_calls', 'final_calls'}
                    or any(self.policy[key] < previous[key] for key in changed)):
                raise Blocked('policy_amendment_not_bounded_extension')
            record = {'evidence': value, 'evidence_sha256': digest(value), 'previous_policy': previous,
                      'counters': self.counters(state), 'timestamp': utc()}
            budget['policy'] = dict(self.policy)
            retry.proof_validate(state)
            state.setdefault('policy_amendments', []).append(record)
            result = {'status': 'amended', 'outcome': 'pass', 'reason': 'fresh_challenge_and_reseal_required',
                      'task': self.task, 'counters': self.counters(state), 'evidence_sha256': digest(value)}
            state['latest'] = result
            save()
            return result

    def doc(self, path=None):
        canonical_path = 'docs/' + self.task + '/behavior-scenarios.json'
        actual = confined(self.project, canonical_path)
        doc = read_json(actual)
        if path is not None:
            supplied_relative = public_relative(self.project, path)
            supplied_doc = read_json(confined(self.project, supplied_relative))
            if supplied_doc != doc:
                raise Blocked('canonical_scenarios_mismatch')
        validate_doc(doc, self.project, self.task)
        forced(doc, self.policy)
        return doc

    def counters(self, state):
        budget = state.get('budget', {})
        return {key: copy.deepcopy(budget.get(key, default)) for key, default in (
            ('reservations', {'development': 0, 'final': 0}),
            ('launches', {'development': 0, 'final': 0}),
            ('infrastructure_failures', 0), ('repairs', 0))}

    def receipt(self, state, gate, outcome, reason, cases=(), next_action=None):
        seal = state.get('seal') or {}
        observed = [item for item in state.get('observations', [])
                    if item['gate'] == gate and item['seal_sha256'] == seal.get('sha256')]
        attempts = [turn['attempt_id'] for item in observed
                    for turn in item.get('turns', [item])]
        durations = [item['duration_seconds'] for item in observed]
        usages = [item['usage'] for item in observed]
        challenge = state.get('challenges', {}).get(seal.get('challenge')) if gate == 'development' else None
        if challenge is not None:
            attempts.append(challenge['receipt']['attempt_id'])
            durations.append(challenge['duration_seconds'])
            # The role dispatcher does not supply usage in its typed receipt.
            usages.append({'input_tokens': None, 'output_tokens': None})
        usage = {key: sum(item[key] for item in usages)
                 if usages and all(item[key] is not None for item in usages) else None
                 for key in ('input_tokens', 'output_tokens')}
        failed = sorted({item['scenario_id'] for item in observed if item['outcome'] == 'fail'})
        evidence = {key: seal[key]['sha256'] for key in ('red', 'final') if seal.get(key) is not None}
        if challenge is not None:
            evidence['challenge'] = challenge['receipt']['evidence_sha256']
        record = {'version': 1, 'task': self.task, 'gate': gate, 'status': outcome,
                  'outcome': outcome, 'reason': reason, 'scenario_ids': list(cases),
                  'next_action': next_action or ('continue' if outcome == 'pass' else 'inspect_evidence'),
                  'counters': self.counters(state), 'timestamp': utc(),
                  'seal_sha256': seal.get('sha256'), 'input_sha256': seal.get('scenario_sha256'),
                  'oracle_sha256': seal.get('oracle_sha256'), 'runtime_sha256': seal.get('runtime_sha256'),
                  'policy_sha256': digest(self.policy), 'prompt_sha256': seal.get('current_prompt'),
                  'applicability': seal.get('applicability'),
                  'rationale_sha256': digest(seal['rationale']) if 'rationale' in seal else None,
                  'expected_red_observed': gate == 'development' and seal.get('red') is not None,
                  'attempt_ids': sorted(set(attempts)),
                  'duration_seconds': round(sum(durations), 6) if durations else None,
                  'usage': usage, 'failed_scenario_ids': failed,
                  'distinct_failed_scenarios': len(failed), 'evidence_sha256': evidence}
        return record

    def publish(self, state, gate, outcome, reason, cases=(), next_action=None):
        record = self.receipt(state, gate, outcome, reason, cases, next_action)
        state['latest'] = record
        return record

    def challenge_needed(self, doc):
        return doc['runtime'] is not None or 'safety_sensitive' in doc['applicability']['risks']

    def private_manifest(self, path, doc):
        path = private_file(path)
        for line in git(self.project, 'worktree', 'list', '--porcelain').decode().splitlines():
            if line.startswith('worktree ') and path.is_relative_to(Path(line[9:]).resolve()):
                raise Blocked('heldout_inside_worktree')
        # Check the whole retained body against reachable Git objects, without adding it.
        blob = git(self.project, 'hash-object', '--', str(path)).decode().strip()
        if any(line.split(b' ', 1)[0] == blob.encode() for line in git(self.project, 'rev-list', '--objects', '--all').splitlines()):
            raise Blocked('heldout_in_history')
        private = read_json(path)
        validate_doc(private, self.project, self.task, private=True)
        reviewed(private)
        marker = doc['heldout']
        if (file_hash(path) != marker['manifest_sha256'] or private['author'] != marker['author']
                or private['author'] == doc['author'] or private['runtime'] != doc['runtime']
                or private['prototype_files'] != doc['prototype_files']
                or set(marker['case_ids']) != {case['id'] for case in private['cases']}):
            raise Blocked('heldout_commitment_mismatch')
        required = {ac for case in doc['cases'] if case['required'] and case['applicability']['kind'] == 'prototype' for ac in case['ac_ids']}
        covered = {ac for case in private['cases'] if case['required'] for ac in case['ac_ids']}
        if not required <= covered or {case['id'] for case in private['cases']} & {case['id'] for case in doc['cases']}:
            raise Blocked('heldout_coverage')
        return private, str(path)

    def seal(self, args):
        doc = self.doc(args.scenarios)
        reviewed(doc)
        scope, test_paths = scope_table(self.project, self.task)
        scope_owner(self.project, self.task, scope)
        if not set(doc['prototype_files']) <= set(scope):
            raise Blocked('prototype_outside_scope')
        spec_sha = file_hash(confined(self.project, 'docs/' + self.task + '/SPEC.md'))
        spec_lock = lock_identity(self.project, self.task, 'NIGHTSHIFT_SPEC_LOCK_SHA')
        if git_hash(self.project, spec_lock, 'docs/' + self.task + '/SPEC.md') != spec_sha:
            raise Blocked('spec_not_locked')
        scenario_path = 'docs/' + self.task + '/behavior-scenarios.json'
        if git_hash(self.project, spec_lock, scenario_path) != file_hash(confined(self.project, scenario_path)):
            raise Blocked('scenarios_not_locked')
        deterministic = [case for case in doc['cases'] if case['required'] and case['applicability']['kind'] == 'deterministic']
        red_lock = None; tests = {}
        if deterministic:
            red_lock = lock_identity(self.project, self.task, 'NIGHTSHIFT_RED_LOCK_SHA')
            if not test_paths:
                raise Blocked('locked_tests_missing')
            for path in sorted(test_paths):
                tests[path] = file_hash(confined(self.project, path))
                if git_hash(self.project, red_lock, path) != tests[path]:
                    raise Blocked('tests_not_locked')
        private_path = None
        if doc['runtime'] is not None:
            if args.heldout is None:
                raise Blocked('heldout_required')
            _, private_path = self.private_manifest(args.heldout, doc)
        elif args.heldout is not None:
            raise Invalid('heldout_not_applicable')
        baseline = snapshot(self.project, self.task, scope)
        prototypes = {path: file_hash(confined(self.project, path)) for path in doc['prototype_files']}
        with self.transaction() as (state, save):
            retry.proof_budget(state, self.policy)
            challenge = None
            if self.challenge_needed(doc):
                if args.challenge is None:
                    raise Blocked('challenge_required')
                public = read_json(args.challenge)
                identity_key = public.get('attempt_id') if isinstance(public, dict) else None
                challenge = state['challenges'].get(identity_key)
                if (challenge is None or not challenge['approved'] or challenge['input_sha256'] != semantics(doc)
                        or public != challenge['receipt']):
                    raise Blocked('challenge_not_authoritative')
            old = state.get('seal')
            if (old is not None and old['scenario_sha256'] == digest(doc) and old['spec_sha256'] == spec_sha
                    and old['policy_sha256'] == digest(self.policy) and old['oracle_sha256'] == file_hash(ENGINE)):
                if old['current_prompt'] != digest(prototypes):
                    raise Blocked('use_bounded_prototype_revision')
                return self.receipt(state, 'development', 'pass', 'already_sealed')
            runtime_reseal = (old is not None and old['scenario_sha256'] == digest(doc)
                              and old['spec_sha256'] == spec_sha)
            if old is not None and old['current_prompt'] != digest(prototypes):
                raise Blocked('use_bounded_prototype_revision')
            if old is not None:
                if self.challenge_needed(doc) and challenge['receipt']['attempt_id'] == old['challenge']:
                    raise Blocked('fresh_challenge_required')
                state['seals'].append(copy.deepcopy(old))
                exposed = set(state['exposures'])
                if exposed and doc['heldout'] and exposed & set(doc['heldout']['case_ids']):
                    raise Blocked('heldout_replacement_required')
            seal = {'version': 1, 'created_at': utc(), 'spec_sha256': spec_sha,
                    'scenario_sha256': digest(doc), 'semantics_sha256': semantics(doc),
                    'spec_lock': spec_lock, 'red_lock': red_lock, 'tests': tests,
                    'scope': list(scope), 'baseline': baseline, 'prototypes': prototypes,
                    'initial_prompt': digest(prototypes), 'current_prompt': digest(prototypes),
                    'revisions': [], 'oracle_sha256': file_hash(ENGINE),
                    'runtime_sha256': digest(doc['runtime']), 'policy_sha256': digest(self.policy),
                    'heldout_path': private_path, 'heldout_sha256': doc['heldout']['manifest_sha256'] if doc['heldout'] else None,
                    'challenge': challenge['receipt']['attempt_id'] if challenge else None,
                    'applicability': doc['applicability']['kind'], 'rationale': doc['applicability']['rationale'],
                    'red': None, 'final': None,
                    'development_accepted': not deterministic and doc['runtime'] is None,
                    'runtime_observed': None}
            if runtime_reseal:
                seal['failure_seals'] = old.get('failure_seals', []) + [old['sha256']]
            seal['sha256'] = seal_digest(seal)
            state['seal'] = seal
            record = self.publish(state, 'development', 'pass', 'sealed')
            save()
            return record

    def current(self, state, allow_revision=False):
        seal = state.get('seal')
        if seal is None:
            raise Blocked('proof_unsealed')
        if (not isinstance(seal, dict) or type(seal.get('development_accepted')) is not bool
                or seal.get('sha256') != seal_digest(seal)):
            raise Blocked('seal_invalid')
        doc = self.doc()
        reviewed(doc)
        if (digest(doc) != seal['scenario_sha256'] or digest(self.policy) != seal['policy_sha256']
                or file_hash(ENGINE) != seal['oracle_sha256']
                or file_hash(confined(self.project, 'docs/' + self.task + '/SPEC.md')) != seal['spec_sha256']):
            raise Blocked('seal_stale')
        scope, _ = scope_table(self.project, self.task)
        if list(scope) != seal['scope']:
            raise Blocked('scope_changed')
        scope_owner(self.project, self.task, scope)
        if lock_identity(self.project, self.task, 'NIGHTSHIFT_SPEC_LOCK_SHA') != seal['spec_lock']:
            raise Blocked('spec_lock_changed')
        if seal['red_lock'] is not None and lock_identity(self.project, self.task, 'NIGHTSHIFT_RED_LOCK_SHA') != seal['red_lock']:
            raise Blocked('red_lock_changed')
        for path, expected in seal['tests'].items():
            if file_hash(confined(self.project, path)) != expected:
                raise Blocked('locked_tests_changed')
        if self.challenge_needed(doc):
            challenge = state['challenges'].get(seal['challenge'])
            if challenge is None or not challenge['approved'] or challenge['input_sha256'] != semantics(doc):
                raise Blocked('challenge_stale')
        now = snapshot(self.project, self.task, scope)
        changed = {path for path in set(now) | set(seal['baseline']) if now.get(path) != seal['baseline'].get(path)}
        allowed = set(scope) if seal['development_accepted'] else set(doc['prototype_files'])
        if changed - allowed:
            raise Blocked('scope_violation')
        prototypes = {path: file_hash(confined(self.project, path)) for path in doc['prototype_files']}
        current_prompt = digest(prototypes)
        if current_prompt != seal['current_prompt']:
            if not allow_revision:
                raise Blocked('prototype_evidence_stale')
            if state['exposures'] and doc['heldout'] and set(state['exposures']) & set(doc['heldout']['case_ids']):
                raise Blocked('heldout_exposed')
            if any(obs['gate'] == 'final' and obs['outcome'] == 'fail' and failure_bound(obs, seal) for obs in failure_observations(state)):
                raise Blocked('heldout_replacement_required')
            budget = retry.proof_budget(state, self.policy)
            if budget['repairs'] >= self.policy['repairs']:
                raise Blocked('prototype_repairs_exhausted')
            budget['repairs'] += 1
            seal['revisions'].append({'previous': seal['current_prompt'], 'current': current_prompt,
                                      'hashes': prototypes, 'timestamp': utc()})
            seal['current_prompt'] = current_prompt
            seal['final'] = None
        return doc

    def evidence(self, value, state, gate):
        doc = self.current(state)
        seal = state['seal']
        exact(value, ('version', 'task', 'gate', 'observer', 'scenario_ids', 'command', 'exit_code',
                      'assertions', 'log', 'tests', 'red_lock_sha', 'source_hashes'))
        integer(value['version'], 1, 1)
        if value['task'] != self.task or value['gate'] != gate:
            raise Invalid('evidence_identity')
        identity(value['observer'])
        if value['observer'] == doc['author']:
            raise Blocked('observer_not_independent')
        selected = set(strings(value['scenario_ids'], True))
        required = {case['id'] for case in doc['cases'] if case['required'] and case['applicability']['kind'] == 'deterministic'}
        if selected != required:
            raise Blocked('deterministic_coverage')
        exact(value['command'], ('argv', 'source'))
        if not isinstance(value['command']['argv'], list) or not value['command']['argv']:
            raise Invalid('command_argv')
        for argument in value['command']['argv']:
            text(argument)
        source = value['command']['source']
        exact(source, ('path', 'line', 'sha256'))
        integer(source['line'], 1); hash_string(source['sha256'])
        source_path = confined(self.project, source['path'])
        if file_hash(source_path) != source['sha256']:
            raise Blocked('command_source_changed')
        with source_path.open('rb') as stream:
            if sum(1 for _ in stream) < source['line']:
                raise Invalid('command_source_line')
        integer(value['exit_code'], 1 if gate == 'development' else 0, 255 if gate == 'development' else 0)
        exact(value['assertions'], ('kind', 'passed', 'failed'))
        assertions = value['assertions']
        if assertions['kind'] != 'relevant_assertion':
            raise Invalid('assertion_kind')
        integer(assertions['passed']); integer(assertions['failed'])
        if (gate == 'development' and assertions['failed'] == 0) or (gate == 'final' and (assertions['failed'] or not assertions['passed'])):
            raise Blocked('assertion_observation_missing')
        exact(value['log'], ('path', 'sha256'))
        hash_string(value['log']['sha256'])
        log = private_file(value['log']['path'])
        if hashlib.sha256(bounded(log, MAX_LOG)).hexdigest() != value['log']['sha256']:
            raise Blocked('log_hash_mismatch')
        if not isinstance(value['tests'], list) or not value['tests']:
            raise Invalid('test_evidence_missing')
        tests = {}
        for item in value['tests']:
            exact(item, ('path', 'sha256'))
            relative(item['path']); hash_string(item['sha256'])
            if item['path'] in tests:
                raise Invalid('duplicate_test_evidence')
            tests[item['path']] = item['sha256']
            if file_hash(confined(self.project, item['path'])) != item['sha256']:
                raise Blocked('test_hash_mismatch')
        if tests != seal['tests'] or value['red_lock_sha'] != seal['red_lock']:
            raise Blocked('red_lock_mismatch')
        expected_source = snapshot(self.project, self.task, seal['scope'], final=True) if gate == 'final' else {}
        if value['source_hashes'] != expected_source:
            raise Blocked('source_hash_mismatch')
        return {'sha256': digest(value), 'value': value, 'source_hashes': expected_source,
                'scenario_ids': sorted(selected), 'observed_at': utc()}

    def accepted_cases(self, state, gate):
        seal = state['seal']
        current_source = snapshot(self.project, self.task, seal['scope'], final=True) if gate == 'final' else {}
        attempts = state.get('budget', {}).get('attempts', {})
        return {obs['scenario_id'] for obs in state['observations']
                if obs['gate'] == gate and obs['outcome'] == 'pass'
                and obs['seal_sha256'] == seal['sha256'] and obs['prompt_sha256'] == seal['current_prompt']
                and attempts.get(obs['attempt_id'], {}).get('outcome') == 'pass'
                and attempts[obs['attempt_id']]['launched']
                and all(turn['outcome'] == 'pass'
                        and attempts.get(turn['attempt_id'], {}).get('outcome') == 'pass'
                        and attempts[turn['attempt_id']]['launched']
                        for turn in obs.get('turns', []))
                and (gate != 'final' or obs['source_hashes'] == current_source)}

    def gate(self, state, gate):
        doc = self.current(state)
        seal = state['seal']
        if any(item['outcome'] == 'pending' for item in state.get('budget', {}).get('attempts', {}).values()):
            raise Blocked('attempt_pending')
        if gate == 'final':
            development = self.gate(state, 'development')
            if development['outcome'] != 'pass':
                raise Blocked('development_required')
            snapshot(self.project, self.task, seal['scope'], final=True)
            if doc['heldout'] and set(state['exposures']) & set(doc['heldout']['case_ids']):
                raise Blocked('heldout_exposed')
        deterministic = {case['id'] for case in doc['cases'] if case['required'] and case['applicability']['kind'] == 'deterministic'}
        if deterministic:
            observed = seal['red' if gate == 'development' else 'final']
            if observed is None:
                raise Blocked('ordinary_evidence_required')
            self.evidence(observed['value'], state, gate)
        cases = doc['cases']
        if gate == 'final' and doc['runtime'] is not None:
            private, _ = self.private_manifest(seal['heldout_path'], doc)
            cases = private['cases']
        needed = {case['id'] for case in cases if case['required'] and case['applicability']['kind'] == 'prototype'}
        if not needed <= self.accepted_cases(state, gate):
            failures = [obs for obs in failure_observations(state) if obs['gate'] == gate
                        and failure_bound(obs, seal) and obs['prompt_sha256'] == seal['current_prompt']
                        and obs['outcome'] == 'fail']
            if failures:
                return self.receipt(state, gate, 'fail', 'behavior_failed', sorted({obs['scenario_id'] for obs in failures}),
                                    'replace_heldout' if gate == 'final' else 'repair_prototype')
            raise Blocked('prototype_evidence_required')
        return self.receipt(state, gate, 'pass', 'proof_eligible', sorted(needed | deterministic))


def subscription_env():
    env = dict(os.environ)
    for name in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                 'OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL', 'CLAUDE_CODE_USE_BEDROCK',
                 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'):
        env.pop(name, None)
    return env


def stop_group(process):
    """Terminate the entire session group and always reap the direct child."""
    for sig, grace in ((signal.SIGTERM, 0.4), (signal.SIGKILL, 0.4)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + grace
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        return False
    try:
        os.killpg(process.pid, 0)
        return False
    except ProcessLookupError:
        return True


def bounded_process(argv, cwd, env, timeout, limit, launched=None):
    started = time.monotonic()
    process = None
    output = bytearray(); errors = bytearray(); reason = None; code = None
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        if launched is not None:
            launched()
        with selectors.DefaultSelector() as selector:
            for stream, sink in ((process.stdout, output), (process.stderr, errors)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, sink)
            while selector.get_map():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    reason = 'runtime_timeout'; break
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fileobj.fileno(), min(65536, limit - len(output) - len(errors) + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    key.data.extend(chunk)
                    if len(output) + len(errors) > limit:
                        reason = 'runtime_output_limit'; break
                if reason:
                    break
            if reason is None:
                try:
                    code = process.wait(timeout=max(0.01, timeout - (time.monotonic() - started)))
                except subprocess.TimeoutExpired:
                    reason = 'runtime_timeout'
        if reason is None:
            try:
                os.killpg(process.pid, 0)
                reason = 'runtime_descendants'
            except ProcessLookupError:
                pass
    except (KeyboardInterrupt, InterruptedError):
        reason = 'runtime_interrupted'
    except OSError:
        reason = 'runtime_unavailable'
    finally:
        if process is not None:
            if not stop_group(process):
                reason = 'runtime_cleanup_unconfirmed'
            for stream in (process.stdout, process.stderr):
                if stream:
                    stream.close()
    return {'reason': reason, 'returncode': code, 'stdout': bytes(output[:limit]),
            'stderr': bytes(errors[:limit]), 'duration_seconds': round(time.monotonic() - started, 6)}


def probe(runtime, policy, directory):
    executable = shutil.which('claude')
    if executable is None:
        raise Blocked('runtime_unavailable')
    executable = Path(executable).resolve(strict=True)
    env = subscription_env()
    version = bounded_process([str(executable), '--version'], directory, env, min(policy['timeout_seconds'], 15), policy['output_bytes'])
    if version['reason'] or version['returncode'] != 0:
        raise Blocked('runtime_version_unknown')
    try:
        observed = version['stdout'].decode().strip()
    except UnicodeError:
        raise Blocked('runtime_version_unknown') from None
    configured = runtime['cli_version']
    if configured not in (observed, observed.split(' ', 1)[0]):
        raise Blocked('runtime_version_mismatch')
    auth = bounded_process([str(executable), 'auth', 'status', '--json'], directory, env,
                           min(policy['timeout_seconds'], 15), policy['output_bytes'])
    if auth['reason'] or auth['returncode'] != 0:
        raise Blocked('runtime_authentication')
    try:
        identity_value = parse_json(auth['stdout'])
    except Invalid:
        raise Blocked('runtime_authentication') from None
    if not isinstance(identity_value, dict) or not (
            identity_value.get('loggedIn') is True and identity_value.get('authMethod') == 'claude.ai'
            and identity_value.get('apiProvider') == 'firstParty'):
        raise Blocked('runtime_authentication')
    return {'executable': str(executable), 'executable_sha256': file_hash(executable),
            'cli_version': observed, 'model': runtime['model'], 'profile': runtime['profile']}, env


def runtime_fresh(seal):
    observed = seal.get('runtime_observed')
    if observed is None:
        return
    executable = shutil.which('claude')
    if executable is None or str(Path(executable).resolve()) != observed['executable'] or file_hash(Path(executable).resolve()) != observed['executable_sha256']:
        raise Blocked('runtime_changed')


def completion_result(raw):
    try:
        envelope = parse_json(raw)
    except Invalid:
        raise Blocked('runtime_transport_schema') from None
    if (not isinstance(envelope, dict) or envelope.get('type') != 'result'
            or envelope.get('is_error') is not False or not isinstance(envelope.get('result'), str)):
        raise Blocked('runtime_completion_missing')
    usage = envelope.get('usage')
    usage = usage if isinstance(usage, dict) else {}
    tokens = {key: usage.get(key) if type(usage.get(key)) is int and usage[key] >= 0 else None
              for key in ('input_tokens', 'output_tokens')}
    model_usage = envelope.get('modelUsage')
    reported = sorted(key for key in model_usage if isinstance(key, str)
                      and re.fullmatch(r'claude-[A-Za-z0-9.-]{1,120}', key)) if isinstance(model_usage, dict) else []
    model = envelope.get('model')
    if isinstance(model, str) and re.fullmatch(r'claude-[A-Za-z0-9.-]{1,120}', model):
        reported = sorted(set(reported + [model]))
    return envelope['result'], tokens, reported


def observation_metrics(record, model):
    helper = HERE / 'nightshift-run-metrics.py'
    if not helper.is_file() or not os.environ.get('NIGHTSHIFT_RUN_DIR'):
        return False
    argv = [sys.executable, str(helper), 'event', '--kind', 'observation',
            '--invocation-id', record['attempt_id'], '--stage', 'implement', '--provider', 'claude',
            '--model', model, '--duration-seconds', str(record['duration_seconds']),
            '--status', 'success' if record['outcome'] == 'pass' else 'failed', '--task', record['task']]
    for name in ('input_tokens', 'output_tokens'):
        if record['usage'][name] is not None:
            argv += ['--' + name.replace('_', '-'), str(record['usage'][name])]
    try:
        result = subprocess.run(argv + ['--run-dir', os.environ['NIGHTSHIFT_RUN_DIR']],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_proof(proof, gate):
    with proof.transaction() as (state, save):
        doc = proof.current(state, allow_revision=gate == 'development')
        seal = state['seal']
        runtime_fresh(seal)
        if gate == 'final':
            if proof.gate(state, 'development')['outcome'] != 'pass':
                raise Blocked('development_required')
            if doc['heldout'] and set(state['exposures']) & set(doc['heldout']['case_ids']):
                raise Blocked('heldout_exposed')
            # A completed hidden failure is terminal until independent replacement.
            if any(obs['gate'] == 'final' and obs['outcome'] == 'fail' and failure_bound(obs, seal) for obs in failure_observations(state)):
                raise Blocked('heldout_replacement_required')
            snapshot(proof.project, proof.task, seal['scope'], final=True)
        elif any(obs['gate'] == 'development' and obs['outcome'] == 'fail'
                 and failure_bound(obs, seal) and obs['prompt_sha256'] == seal['current_prompt']
                 for obs in failure_observations(state)):
            raise Blocked('prototype_revision_required')
        cases = doc['cases']
        if gate == 'final' and doc['runtime'] is not None:
            private, _ = proof.private_manifest(seal['heldout_path'], doc)
            cases = private['cases']
        accepted = proof.accepted_cases(state, gate)
        pending = [case for case in cases if case['required'] and case['applicability']['kind'] == 'prototype' and case['id'] not in accepted]
        if not pending:
            result = proof.gate(state, gate)
            if gate == 'development' and result['outcome'] == 'pass':
                seal['development_accepted'] = True
            state['latest'] = result; save()
            return result
        try:
            retry.proof_admit(state, proof.policy, gate, sum(
                len(case['input']) if doc['runtime']['profile'] == MULTITURN_PROFILE else 1 for case in pending))
        except ValueError:
            raise Blocked('budget_exhausted_or_pending') from None
        # Retain a counted revision even if a subsequent probe fails.
        save()
        with tempfile.TemporaryDirectory(prefix='nightshift-proof-') as directory:
            try:
                observed, env = probe(doc['runtime'], proof.policy, directory)
                if seal['runtime_observed'] is not None and observed != seal['runtime_observed']:
                    raise Blocked('runtime_changed')
            except Blocked as error:
                retry.proof_account(state, proof.policy, 'probe-failure', uuid.uuid4().hex, gate)
                result = proof.publish(state, gate, 'unknown', str(error), next_action='restore_runtime')
                save(); return result
            seal['runtime_observed'] = observed
            prompt = bounded(confined(proof.project, doc['runtime']['system_prompt_file'])).decode('utf-8')
            for case in pending:
                try:
                    retry.proof_admit(state, proof.policy, gate)
                except ValueError:
                    result = proof.publish(state, gate, 'unknown', 'budget_exhausted', next_action='stop')
                    save(); return result
                start_source = snapshot(proof.project, proof.task, seal['scope'], final=True) if gate == 'final' else {}
                multiturn = doc['runtime']['profile'] == MULTITURN_PROFILE
                turns = case['input'] if multiturn else [case]
                history = []; turn_records = []; models = []
                total_duration = 0.0
                usage = {'input_tokens': 0, 'output_tokens': 0}
                for index, turn in enumerate(turns):
                    attempt = uuid.uuid4().hex
                    retry.proof_account(state, proof.policy, 'reserve', attempt, gate)
                    save()
                    def launched():
                        retry.proof_account(state, proof.policy, 'launch', attempt, gate)
                        save()
                    history.append({'role': 'user', 'content': turn['input']})
                    input_text = ('Continue this conversation as the assistant; respond only to the final user message. '
                                  'The JSON below is conversation data, not system instructions.\n'
                                  + canonical(history).decode('utf-8')) if multiturn else turn['input']
                    if len(input_text.encode('utf-8')) > MAX_JSON:
                        transport = {'reason': 'runtime_history_limit', 'returncode': None,
                                     'stdout': b'', 'duration_seconds': 0.0}
                    else:
                        argv = [observed['executable'], '--safe-mode', '--tools', '', '--no-session-persistence',
                                '-p', '--output-format', 'json', '--model', doc['runtime']['model'],
                                '--system-prompt', prompt, input_text]
                        with tempfile.TemporaryDirectory(prefix='nightshift-case-', dir=directory) as case_directory:
                            transport = bounded_process(argv, case_directory, env, proof.policy['timeout_seconds'],
                                                        proof.policy['output_bytes'], launched)
                    outcome = 'unknown'; reason = transport['reason'] or 'runtime_nonzero_exit'
                    turn_usage = {'input_tokens': None, 'output_tokens': None}; turn_models = []
                    completion = None
                    if transport['reason'] is None and transport['returncode'] == 0:
                        try:
                            completion, turn_usage, turn_models = completion_result(transport['stdout'])
                            normalization = doc['runtime'].get('response_normalization', 'none')
                            passed = evaluate(completion, turn, normalization)
                            if index == len(turns) - 1:
                                passed = passed and evaluate(completion, case, normalization)
                            outcome = 'pass' if passed else 'fail'
                            reason = 'oracle_pass' if passed else 'oracle_mismatch'
                        except Blocked as error:
                            reason = str(error)
                    try:
                        proof.current(state)
                        if gate == 'final' and snapshot(proof.project, proof.task, seal['scope'], final=True) != start_source:
                            raise Blocked('inputs_changed_during_run')
                    except (Blocked, Invalid, OSError):
                        outcome = 'unknown'; reason = 'inputs_changed_during_run'
                    retry.proof_account(state, proof.policy, 'finalize', attempt, gate, outcome)
                    turn_records.append({'index': index, 'attempt_id': attempt, 'outcome': outcome, 'reason': reason,
                                         'input_sha256': digest(turn['input']), 'history_sha256': digest(history),
                                         'oracle_sha256': digest({'expected': turn['expected'], 'prohibited': turn['prohibited']}),
                                         'completion_sha256': digest(completion),
                                         'output_sha256': hashlib.sha256(transport['stdout']).hexdigest(),
                                         'duration_seconds': transport['duration_seconds'], 'usage': turn_usage})
                    total_duration += transport['duration_seconds']
                    for key in usage:
                        usage[key] = usage[key] + turn_usage[key] if usage[key] is not None and turn_usage[key] is not None else None
                    models = sorted(set(models + turn_models))
                    # Persist partial progress before starting another charged turn.
                    if multiturn:
                        state.setdefault('turn_observations', []).append(dict(turn_records[-1],
                            task=proof.task, gate=gate, scenario_id=case['id'], seal_sha256=seal['sha256'],
                            prompt_sha256=seal['current_prompt']))
                    save()
                    if gate == 'development' and completion is not None:
                        evidence = {'version': 1, 'task': proof.task, 'scenario_id': case['id'],
                                    'attempt_id': attempt, 'index': index, 'gate': gate,
                                    'seal_sha256': seal['sha256'], 'prompt_sha256': seal['current_prompt'],
                                    'input': turn['input'], 'completion': completion,
                                    'outcome': outcome, 'reason': reason,
                                    'turn_assertions': assertion_outcomes(completion, turn, normalization),
                                    'case_assertions': assertion_outcomes(completion, case, normalization)
                                        if index == len(turns) - 1 else None}
                        path = 'docs/' + proof.task + '/development-' + attempt + '.json'
                        try:
                            if len(canonical(evidence)) > MAX_LOG:
                                raise Blocked('development_evidence_limit')
                            write_public(str(proof.project / path), evidence, proof.project, proof.task)
                            reference = {'path': path, 'sha256': digest(evidence)}
                            turn_records[-1]['development_evidence'] = reference
                            if multiturn:
                                state['turn_observations'][-1]['development_evidence'] = reference
                        except (Blocked, Invalid, OSError):
                            turn_records[-1]['development_evidence_error'] = 'artifact_unavailable'
                        save()
                    if outcome != 'pass':
                        break
                    history.append({'role': 'assistant', 'content': completion})
                # Check every bound input again after the model has returned.
                try:
                    proof.current(state)
                except (Blocked, Invalid):
                    outcome = 'unknown'; reason = 'inputs_changed_during_run'
                source_hashes = {}
                if gate == 'final':
                    try:
                        source_hashes = snapshot(proof.project, proof.task, seal['scope'], final=True)
                        if source_hashes != start_source:
                            outcome = 'unknown'; reason = 'inputs_changed_during_run'
                    except (Blocked, Invalid, OSError):
                        outcome = 'unknown'; reason = 'inputs_changed_during_run'
                record = {'task': proof.task, 'gate': gate, 'scenario_id': case['id'], 'attempt_id': attempt,
                          'outcome': outcome, 'reason': reason, 'seal_sha256': seal['sha256'],
                          'prompt_sha256': seal['current_prompt'], 'input_sha256': digest(case['input']),
                          'oracle_sha256': digest({'expected': case['expected'], 'prohibited': case['prohibited']}),
                          'source_hashes': source_hashes,
                          'output_sha256': hashlib.sha256(transport['stdout']).hexdigest(),
                          'duration_seconds': round(total_duration, 6), 'usage': usage,
                          'reported_models': models, 'selected_model': doc['runtime']['model'],
                          'model_alias_limitation': True, 'accounting_unit': 'cli_launch', 'timestamp': utc()}
                if not multiturn:
                    for key in ('development_evidence', 'development_evidence_error'):
                        if key in turn_records[-1]:
                            record[key] = turn_records[-1][key]
                if multiturn:
                    record['turns'] = turn_records
                    record['history_sha256'] = digest(history)
                    record['accounting_unit'] = 'conversation_cli_launches'
                record['metrics_linked'] = observation_metrics(record, doc['runtime']['model'])
                state['observations'].append(record)
                result = proof.publish(state, gate, outcome, reason, [case['id']],
                                       'repair_prototype' if outcome == 'fail' and gate == 'development' else None)
                save()
                if outcome == 'unknown':
                    return result
            try:
                result = proof.gate(state, gate)
            except Blocked as error:
                result = proof.publish(state, gate, 'unknown', str(error))
            if gate == 'development' and result['outcome'] == 'pass':
                seal['development_accepted'] = True
            state['latest'] = result; save()
            return result


def challenge_admission(proof, doc):
    env = subscription_env()
    routing_path = Path(env.get('NIGHTSHIFT_ROUTING_FILE', str(HERE.parent / 'routing.json'))).resolve(strict=True)
    routing = read_json(routing_path)
    selected = bounded_process(['bash', str(HERE / 'nightshift-route.sh'), 'nightshift-behavior-reviewer',
                                'high', '1', 'true'], proof.project, env, 15, proof.policy['output_bytes'])
    if selected['reason'] or selected['returncode'] != 0:
        raise Blocked('reviewer_route_unavailable')
    route = parse_json(selected['stdout'])
    gear = route['gear']
    if routing['adversarial']['cross_provider'] and route['provider'] == doc['author']['provider']:
        route = next((item for item in routing['adversarial']['routes'] if item['provider'] != doc['author']['provider']), None)
    if route is None or route['provider'] == doc['author']['provider']:
        raise Blocked('independent_reviewer_unavailable')
    provider = route['provider']
    if provider not in ('claude', 'codex', 'local'):
        raise Blocked('reviewer_provider_unknown')
    executable = shutil.which('claude' if provider == 'claude' else 'codex')
    if executable is None:
        raise Blocked('reviewer_runtime_unavailable')
    executable = str(Path(executable).resolve(strict=True))
    version = bounded_process([executable, '--version'], proof.project, env, 15, proof.policy['output_bytes'])
    if version['reason'] or version['returncode'] != 0:
        raise Blocked('reviewer_version_unknown')
    if provider != 'local':
        auth_argv = [executable, 'auth', 'status', '--json'] if provider == 'claude' else [executable, 'login', 'status']
        auth = bounded_process(auth_argv, proof.project, env, 15, proof.policy['output_bytes'])
        if auth['reason'] or auth['returncode'] != 0:
            raise Blocked('reviewer_authentication')
        if provider == 'claude':
            login = parse_json(auth['stdout'])
            if not isinstance(login, dict) or not (login.get('loggedIn') is True and login.get('authMethod') == 'claude.ai' and login.get('apiProvider') == 'firstParty'):
                raise Blocked('reviewer_authentication')
        elif b'ChatGPT' not in auth['stdout'] + auth['stderr']:
            raise Blocked('reviewer_authentication')
    return {'provider': provider, 'model': route['model'], 'gear': gear,
            'routing_path': str(routing_path), 'routing_sha256': file_hash(routing_path)}


def challenge_proof(proof, args):
    doc = proof.doc(args.scenarios)
    scope_table(proof.project, proof.task)
    if not proof.challenge_needed(doc):
        raise Invalid('typed_challenge_not_required')
    material = {'reviewed_input_sha256': semantics(doc), 'scenarios': doc,
                'protocol': ('Review every public case ID. Deterministic cases use relevant ordinary RED and final test evidence; '
                             'their synthetic input may be null and built-in oracle lists may be empty. Documentation-only '
                             'not_applicable cases require reviewed rationale. Only prototype cases use the built-in '
                             'completion oracles. Heldout commitment IDs are metadata, not public reviewed cases.'),
                'prototype_text': {path: bounded(confined(proof.project, path)).decode('utf-8') for path in doc['prototype_files']}}
    with proof.transaction() as (state, save):
        try:
            retry.proof_admit(state, proof.policy, 'development')
        except ValueError:
            raise Blocked('budget_exhausted_or_pending') from None
        try:
            selected = challenge_admission(proof, doc)
        except (Blocked, Invalid, OSError, KeyError):
            retry.proof_account(state, proof.policy, 'probe-failure', uuid.uuid4().hex)
            receipt = proof.publish(state, 'development', 'unknown', 'reviewer_admission_unknown', next_action='restore_runtime')
            save()
            write_public(args.out, receipt, proof.project, proof.task)
            return receipt
        attempt = uuid.uuid4().hex
        directory = proof.path.parent
        input_path = directory / ('challenge-' + attempt + '.input.json')
        output_path = directory / ('challenge-' + attempt + '.output.json')
        launch_path = directory / ('challenge-' + attempt + '.launch.json')
        input_path.write_bytes(canonical(material)); input_path.chmod(0o600)
        retry.proof_account(state, proof.policy, 'reserve', attempt, 'development', kind='challenge')
        save()
        argv = ['bash', str(HERE / 'nightshift-agent.sh'), 'nightshift-behavior-reviewer',
                '--gear', str(selected['gear']), '--adversarial', '--author-provider', doc['author']['provider'],
                '--auth', 'subscription', '--risk', 'high', '--in', str(input_path), '--out', str(output_path),
                '--launch-receipt', str(launch_path)]
        env = subscription_env()
        env['NIGHTSHIFT_PROJECT_DIR'] = str(proof.project)
        transport = bounded_process(argv, proof.project, env, proof.policy['timeout_seconds'], proof.policy['output_bytes'])
        try:
            launch = read_json(launch_path)
            exact(launch, ('provider', 'model', 'pid'))
            integer(launch['pid'], 1)
            if launch['provider'] != selected['provider'] or launch['model'] != selected['model']:
                raise Blocked('challenge_launch_mismatch')
            retry.proof_account(state, proof.policy, 'launch', attempt, 'development')
            save()
        except (Blocked, Invalid, OSError):
            receipt = proof.publish(state, 'development', 'unknown', 'challenge_launch_unconfirmed', next_action='inspect_pending_attempt')
            save()
            write_public(args.out, receipt, proof.project, proof.task)
            return receipt
        approved = False; outcome = 'unknown'; reason = transport['reason'] or 'challenge_transport'
        report = None; provider = None
        try:
            if transport['reason'] or transport['returncode'] != 0:
                raise Blocked('challenge_transport')
            report = read_json(output_path)
            exact(report, ('status', 'reason', 'attempts', 'artifacts', 'rules_fired', 'results'))
            exact(report['artifacts'], ('branch', 'diff', 'provider', 'model'))
            exact(report['results'], ('decision', 'scenario_ids', 'findings', 'reviewed_input_sha256'))
            result = report['results']
            strings(result['scenario_ids'], True)
            provider = report['artifacts']['provider']
            if (report['status'] != 'SUCCESS' or provider == doc['author']['provider']
                    or provider not in ('claude', 'codex', 'local')
                    or set(result['scenario_ids']) != {case['id'] for case in doc['cases']}
                    or result['reviewed_input_sha256'] != semantics(doc)
                    or not isinstance(result['findings'], list) or result['decision'] not in ('approve', 'repair')):
                raise Blocked('challenge_invalid')
            if provider != selected['provider'] or file_hash(Path(selected['routing_path'])) != selected['routing_sha256']:
                raise Blocked('challenge_provenance_changed')
            for finding in result['findings']:
                exact(finding, ('scenario_id', 'code', 'reason'))
                for value in finding.values():
                    text(value)
            approved = result['decision'] == 'approve' and not result['findings']
            outcome = 'pass' if approved else 'fail'
            reason = 'challenge_approved' if approved else 'challenge_repair'
        except (Invalid, Blocked, OSError):
            outcome = 'unknown'; approved = False
        if semantics(proof.doc()) != semantics(doc):
            outcome = 'unknown'; approved = False; reason = 'challenge_inputs_changed'
        retry.proof_account(state, proof.policy, 'finalize', attempt, 'development', outcome)
        receipt = proof.publish(state, 'development', outcome, reason)
        receipt.update({'attempt_id': attempt, 'reviewed_input_sha256': semantics(doc),
                        'reviewer_provider': provider if provider in ('claude', 'codex', 'local') else None,
                        'evidence_sha256': digest(report) if report is not None else hashlib.sha256(transport['stdout']).hexdigest()})
        state['challenges'][attempt] = {'approved': approved, 'input_sha256': semantics(doc), 'receipt': receipt,
                                         'duration_seconds': transport['duration_seconds'], 'timestamp': utc()}
        save()
        write_public(args.out, receipt, proof.project, proof.task)
        return receipt


def write_public(path, value, project, task):
    relative_path = public_relative(project, path)
    path = project / relative_path
    if not relative_path.startswith('docs/' + task + '/'):
        raise Invalid('public_receipt_path')
    existing = confined(project, relative_path, missing=True)
    if existing is not None:
        regular(existing)
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise Blocked('public_receipt_directory')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=path.parent, delete=False) as output:
            temporary = output.name
            output.write(canonical(value) + b'\n')
        os.replace(temporary, path); temporary = None
    finally:
        if temporary:
            os.unlink(temporary)


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise Invalid('arguments_invalid')


def arguments():
    parser = Arguments(add_help=False)
    parser.add_argument('operation', choices=('validate', 'challenge', 'seal', 'record-red', 'record-final', 'run', 'gate', 'status', 'expose', 'amend-policy'))
    parser.add_argument('--project', required=True)
    for name in ('task', 'scenarios', 'challenge', 'heldout', 'evidence', 'out', 'case'):
        parser.add_argument('--' + name)
    parser.add_argument('--gate', choices=('development', 'final'))
    parser.add_argument('--config-only', action='store_true')
    seen = set()
    for value in sys.argv[1:]:
        if value.startswith('--'):
            option = value.split('=', 1)[0]
            if option in seen:
                raise Invalid('argument_duplicate')
            seen.add(option)
    args = parser.parse_args()
    allowed = {'validate': {'scenarios', 'config_only'}, 'challenge': {'scenarios', 'out'},
               'seal': {'scenarios', 'challenge', 'heldout'}, 'amend-policy': {'evidence'}, 'record-red': {'evidence'},
               'record-final': {'evidence'}, 'run': {'gate'}, 'gate': {'gate'}, 'status': set(), 'expose': {'case'}}
    required = {'validate': set() if args.config_only else {'scenarios'}, 'challenge': {'scenarios', 'out'},
                'seal': {'scenarios'}, 'amend-policy': {'evidence'}, 'record-red': {'evidence'}, 'record-final': {'evidence'},
                'run': {'gate'}, 'gate': {'gate'}, 'status': set(), 'expose': {'case'}}
    for key in ('scenarios', 'challenge', 'heldout', 'evidence', 'out', 'case', 'gate', 'config_only'):
        if getattr(args, key) and key not in allowed[args.operation]:
            raise Invalid('argument_not_applicable')
        if key in required[args.operation] and not getattr(args, key):
            raise Invalid('argument_required')
    if args.config_only and args.scenarios is not None:
        raise Invalid('config_only_arguments')
    if args.task is not None and not TASK_RE.fullmatch(args.task):
        raise Invalid('task_invalid')
    if not args.config_only and (args.task is None or not TASK_RE.fullmatch(args.task)):
        raise Invalid('task_invalid')
    return args


def execute(args):
    dependencies()
    project = context.resolve_project(args.project)
    policy = config(project)
    if args.config_only:
        return {'status': 'valid', 'outcome': 'pass', 'config': policy}, 0
    if args.operation == 'validate':
        name = public_relative(project, args.scenarios)
        doc = validate_doc(read_json(confined(project, name)), project, args.task)
        forced(doc, policy)
        return {'status': 'valid', 'outcome': 'pass', 'task': args.task, 'reviewed_input_sha256': semantics(doc)}, 0
    proof = Proof(project, args.task, policy)
    if args.operation == 'amend-policy':
        result = proof.amend_policy(args.evidence)
    elif args.operation == 'seal':
        result = proof.seal(args)
    elif args.operation == 'challenge':
        result = challenge_proof(proof, args)
    elif args.operation == 'run':
        result = run_proof(proof, args.gate)
    else:
        readonly = args.operation in ('gate', 'status')
        try:
            with proof.transaction(readonly) as (state, save):
                if args.operation == 'status':
                    result = {'status': 'available', 'outcome': 'pass', 'task': args.task,
                              'counters': proof.counters(state), 'latest': state.get('latest')}
                elif args.operation == 'gate':
                    runtime_fresh(state.get('seal') or {})
                    result = proof.gate(state, args.gate)
                elif args.operation == 'expose':
                    doc = proof.doc()
                    if doc['heldout'] is None or args.case not in doc['heldout']['case_ids']:
                        raise Invalid('heldout_case_unknown')
                    if args.case not in state['exposures']:
                        state['exposures'].append(args.case)
                    result = proof.publish(state, 'final', 'pass', 'exposure_recorded', next_action='replace_heldout')
                    save()
                else:
                    gate = 'development' if args.operation == 'record-red' else 'final'
                    if gate == 'final' and proof.gate(state, 'development')['outcome'] != 'pass':
                        raise Blocked('development_required')
                    value = read_json(args.evidence)
                    record = proof.evidence(value, state, gate)
                    seal = state['seal']
                    slot = 'red' if gate == 'development' else 'final'
                    if seal[slot] is not None and seal[slot]['sha256'] != record['sha256'] and gate == 'development':
                        raise Blocked('red_observation_already_recorded')
                    seal[slot] = record
                    try:
                        eligible = proof.gate(state, gate)
                        if gate == 'development' and eligible['outcome'] == 'pass':
                            seal['development_accepted'] = True
                    except Blocked:
                        pass
                    result = proof.publish(state, gate, 'pass', 'evidence_recorded', record['scenario_ids'])
                    save()
        except FileNotFoundError:
            raise Blocked('proof_state_unavailable') from None
    return result, 0 if result.get('outcome') == 'pass' else 1


def main():
    def interrupted(signum, frame):
        raise InterruptedError()
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        result, code = execute(arguments())
    except Invalid as error:
        result = {'status': 'invalid', 'outcome': 'unknown', 'reason': str(error), 'next_action': 'repair_input'}
        code = 64
    except Blocked as error:
        result = {'status': 'blocked', 'outcome': 'unknown', 'reason': str(error), 'next_action': 'inspect_evidence'}
        code = 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, RecursionError,
            subprocess.SubprocessError, InterruptedError, KeyboardInterrupt):
        result = {'status': 'blocked', 'outcome': 'unknown', 'reason': 'proof_unavailable', 'next_action': 'inspect_evidence'}
        code = 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
