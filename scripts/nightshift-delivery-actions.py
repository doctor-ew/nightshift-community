#!/usr/bin/env python3
"""Opt-in GitHub Actions integration evidence; default delivery stays SHA-strict.

REST schemas: docs.github.com/en/rest/actions/{workflow-runs,workflow-jobs,artifacts}
and docs.github.com/en/rest/checks/runs. Mutable run.pull_requests is never proof.
"""
import base64
import calendar
from datetime import datetime
from decimal import Decimal
import binascii
import hashlib
import io
import json
import re
import stat
import zipfile
import zlib
from urllib.parse import quote

MAX_ARCHIVE = 2_000_000
MAX_DIAGNOSTIC = 16_384
MAX_RECEIPT = 65_536
MAX_WORKFLOW = 65_536
CONTRACT_KEYS = {'workflow_path', 'workflow_sha256', 'job', 'producer_job', 'artifact_prefix'}
PROOF_KEYS = set('version repository repository_id head_repository_id run_id run_attempt event pull_request head base merge checkout parents workflow_path workflow_sha workflow_sha256 producer_job ref head_ref base_ref'.split())
OID = re.compile(r'[0-9a-f]{40}(?:[0-9a-f]{24})?')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def integer(value):
    return type(value) is int and value > 0


def validate_contract(value):
    require(isinstance(value, dict) and set(value) == CONTRACT_KEYS, 'invalid_actions_contract_fields')
    path = value['workflow_path']
    require(isinstance(path, str) and re.fullmatch(r'\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml', path), 'invalid_actions_workflow_path')
    require(isinstance(value['workflow_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', value['workflow_sha256']), 'invalid_actions_workflow_digest')
    for key in ('job', 'producer_job'):
        require(isinstance(value[key], str) and 0 < len(value[key].encode()) <= 256 and not any(ord(c) < 32 for c in value[key]), 'invalid_actions_job')
    require(isinstance(value['artifact_prefix'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value['artifact_prefix']), 'invalid_actions_artifact_prefix')
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_actions_receipt_key')
        result[key] = value
    return result


def receipt(blob, artifact):
    require(type(blob) is bytes and len(blob) <= MAX_ARCHIVE, 'actions_archive_size')
    require(type(artifact.get('size_in_bytes')) is int and artifact['size_in_bytes'] == len(blob), 'actions_archive_size_mismatch')
    require(artifact.get('digest') == 'sha256:' + hashlib.sha256(blob).hexdigest(), 'actions_archive_digest')
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            entries = archive.infolist()
            require(len(entries) == 1, 'actions_archive_entry_count')
            entry = entries[0]
            require(entry.filename == 'nightshift-integration.json' and not entry.is_dir(), 'actions_archive_entry_name')
            require(stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFREG), 'actions_archive_entry_type')
            require(not entry.flag_bits & 1, 'actions_archive_encrypted')
            require(entry.file_size <= MAX_RECEIPT and entry.compress_size <= MAX_ARCHIVE, 'actions_receipt_size')
            with archive.open(entry) as stream:
                raw = stream.read(MAX_RECEIPT + 1)
            require(len(raw) <= MAX_RECEIPT, 'actions_receipt_size')
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object)
    except (zipfile.BadZipFile, UnicodeError, RuntimeError, OSError, NotImplementedError, zlib.error) as exc:
        raise ValueError('invalid_actions_archive') from exc
    require(isinstance(result, dict) and set(result) == PROOF_KEYS, 'invalid_actions_receipt_fields')
    for key in ('version', 'repository_id', 'head_repository_id', 'run_id', 'run_attempt', 'pull_request'):
        require(integer(result[key]), 'invalid_actions_receipt_integer')
    require(result['version'] == 1, 'unsupported_actions_receipt_version')
    return result


def utc(value):
    require(isinstance(value, str), 'actions_diagnostic_timestamp')
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z', value)
    require(match is not None, 'actions_diagnostic_timestamp')
    try:
        whole = calendar.timegm(datetime.strptime(match.group(1), '%Y-%m-%dT%H:%M:%S').timetuple())
    except ValueError as exc:
        raise ValueError('actions_diagnostic_timestamp') from exc
    fraction = match.group(2) or ''
    return Decimal(whole) + Decimal('0.' + fraction if fraction else 0), Decimal(10) ** -len(fraction)


def failed_segments(raw, steps):
    """Select complete timestamp-owned records, retaining continuation lines.

    API completion times are rounded to their supplied precision. Include that
    final quantum; the diagnostic window is not evidence of test/merge authority.
    Log content, including apparent timestamp prefixes, remains untrusted text.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MAX_ARCHIVE, 'actions_diagnostic_log_size')
    require(isinstance(steps, list), 'actions_diagnostic_steps_missing')
    failures = [step for step in steps if step.get('conclusion') == 'failure']
    require(bool(failures), 'actions_diagnostic_steps_missing')
    intervals = []
    for step in failures:
        require(step.get('status') == 'completed', 'actions_diagnostic_step_incomplete')
        start, _ = utc(step.get('started_at'))
        end, quantum = utc(step.get('completed_at'))
        require(end >= start, 'actions_diagnostic_step_order')
        intervals.append((start, end + quantum))
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('actions_diagnostic_encoding') from exc
    records = []
    previous = None
    for line in text.splitlines(keepends=True):
        match = re.match(r'^(\d{4}-\d{2}-\d{2}T[^ ]+) ', line)
        if match:
            stamp, _ = utc(match.group(1))
            require(previous is None or stamp >= previous, 'actions_diagnostic_log_order')
            previous = stamp
            records.append([stamp, [line]])
        else:
            require(not re.match(r'^\d{4}-', line) and bool(records), 'actions_diagnostic_timestamp')
            records[-1][1].append(line)
    selected = ''.join(''.join(lines) for stamp, lines in records if any(start <= stamp < end for start, end in intervals))
    size = len(selected.encode('utf-8'))
    require(0 < size <= MAX_DIAGNOSTIC, 'actions_diagnostic_segment_size')
    return selected, dict(raw_sha256=hashlib.sha256(raw).hexdigest(), raw_bytes=len(raw), selected_bytes=size, failed_steps=len(failures), window='UTC step intervals including supplied completion-time precision; complete timestamp records with continuation lines; untrusted diagnostic text')


class Resolver:
    def __init__(self, host, profile, pr):
        self.host, self.p, self.pr = host, profile, pr
        self.repo = profile['repository']
        self.prefix = 'repos/' + self.repo + '/'
        self.cache = {}

    def get(self, path, binary=False):
        key = (path, binary)
        if key not in self.cache:
            kwargs = dict(observation=True)
            kwargs['bytes_output' if binary else 'json_output'] = True
            argv = ['gh', 'api', self.prefix + path]
            if binary and path.endswith('/logs'):
                argv.append('--allow-escape-sequences')
            self.cache[key] = self.host.call(argv, **kwargs)
        return self.cache[key]

    def listing(self, path, key):
        data = self.get(path)
        require(isinstance(data, dict) and isinstance(data.get(key), list), 'invalid_actions_list')
        require(type(data.get('total_count')) is int and data['total_count'] == len(data[key]) and len(data[key]) <= 100, 'actions_pagination_incomplete')
        return data[key]

    def identity(self):
        pr = self.pr
        require(integer(pr.get('number')), 'invalid_actions_pr')
        for side in ('head', 'base'):
            value = pr[side]
            require(isinstance(value.get('sha'), str) and OID.fullmatch(value['sha']), 'invalid_actions_pr_revision')
            require(integer(value['repo']['id']) and value['repo']['full_name'] == self.repo, 'actions_pr_repository')
            require(isinstance(value.get('ref'), str) and value['ref'], 'invalid_actions_pr_ref')
        require(pr['base']['ref'] == self.p['base'] and pr['head']['ref'] == self.p['branch'], 'actions_pr_ref_mismatch')
        merge = pr.get('merge_commit_sha')
        require(isinstance(merge, str) and OID.fullmatch(merge), 'actions_merge_missing')
        commit = self.get('git/commits/' + merge)
        require(commit.get('sha') == merge and [row['sha'] for row in commit['parents']] == [pr['base']['sha'], pr['head']['sha']], 'actions_merge_parents')

    def resolve(self, configured):
        self.reported_head = None
        contract = validate_contract(configured['actions'])
        self.identity()
        pr, repo = self.pr, self.repo
        head, merge = pr['head']['sha'], pr['merge_commit_sha']
        runs = self.listing('actions/runs?event=pull_request&head_sha=' + head + '&per_page=100', 'workflow_runs')
        # Only this workflow's PR runs qualify. Never fall back past a newer run.
        matching = [run for run in runs if run.get('event') == 'pull_request' and run.get('head_sha') == head and run.get('path') == contract['workflow_path']]
        require(bool(matching), 'actions_run_missing')
        require(all(all(integer(run.get(key)) for key in ('id', 'run_attempt', 'run_number', 'workflow_id')) for run in matching), 'invalid_actions_run_identity')
        require(len({run['id'] for run in matching}) == len(matching), 'ambiguous_actions_runs')
        require(len({run['workflow_id'] for run in matching}) == 1, 'actions_workflow_identity_ambiguous')
        require(len({run['run_number'] for run in matching}) == len(matching), 'actions_run_order_ambiguous')
        run = max(matching, key=lambda value: value['run_number'])
        run_id, attempt = run['id'], run['run_attempt']
        require(integer(run['repository'].get('id')) and run['repository']['id'] == pr['base']['repo']['id'] and run['repository']['full_name'] == repo, 'actions_run_repository')
        require(integer(run['head_repository'].get('id')) and run['head_repository']['id'] == pr['head']['repo']['id'] and run['head_repository']['full_name'] == repo, 'actions_run_head_repository')
        require(run.get('head_branch') == pr['head']['ref'], 'actions_run_branch')
        require(integer(run.get('check_suite_id')), 'invalid_actions_suite')
        jobs = self.listing('actions/runs/' + str(run_id) + '/attempts/' + str(attempt) + '/jobs?per_page=100', 'jobs')
        def job(name):
            matches = [row for row in jobs if row.get('name') == name]
            require(len(matches) == 1, 'actions_job_missing_or_ambiguous')
            row = matches[0]
            require(integer(row.get('id')) and type(row.get('run_id')) is int and type(row.get('run_attempt')) is int and row['run_id'] == run_id and row['run_attempt'] == attempt and row.get('head_sha') == head, 'actions_job_identity')
            return row
        tested = job(contract['job'])
        check_prefix = 'https://api.github.com/repos/' + repo + '/check-runs/'
        check_url = tested.get('check_run_url')
        match = re.fullmatch(re.escape(check_prefix) + r'([1-9][0-9]*)', check_url) if isinstance(check_url, str) else None
        require(match is not None, 'actions_job_check_identity')
        check_id = int(match.group(1))
        checks = self.listing('commits/' + head + '/check-runs?filter=all&per_page=100', 'check_runs')
        selected = [check for check in checks if type(check.get('id')) is int and check['id'] == check_id and check.get('name') == configured['name'] and integer(check.get('app', {}).get('id')) and check.get('app', {}).get('id') == configured['app_id'] and integer(check.get('check_suite', {}).get('id')) and check.get('check_suite', {}).get('id') == run['check_suite_id']]
        require(len(selected) == 1, 'actions_check_missing_or_ambiguous')
        check = selected[0]
        self.reported_head = check.get('head_sha')
        require(integer(check.get('id')) and check.get('head_sha') == head, 'actions_check_head')
        require(tested.get('status') == check.get('status') and tested.get('conclusion') == check.get('conclusion'), 'actions_job_check_state')
        require(check.get('status') == 'completed' and check.get('conclusion') in ('success', 'failure'), 'actions_check_pending_or_inconclusive')
        producer = job(contract['producer_job'])
        require(producer.get('status') == 'completed' and producer.get('conclusion') == 'success', 'actions_producer_incomplete')
        workflow = self.get('contents/' + quote(contract['workflow_path'], safe='/') + '?ref=' + merge)
        require(workflow.get('encoding') == 'base64' and workflow.get('path') == contract['workflow_path'] and workflow.get('type') == 'file', 'actions_workflow_content')
        content = workflow.get('content')
        require(isinstance(content, str) and len(content) <= 2 * MAX_WORKFLOW, 'actions_workflow_size')
        try:
            raw = base64.b64decode(''.join(content.split()), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('actions_workflow_encoding') from exc
        require(len(raw) <= MAX_WORKFLOW and type(workflow.get('size')) is int and workflow['size'] == len(raw), 'actions_workflow_size')
        require(hashlib.sha256(raw).hexdigest() == contract['workflow_sha256'], 'actions_workflow_digest')
        artifacts = self.listing('actions/runs/' + str(run_id) + '/artifacts?per_page=100', 'artifacts')
        name = contract['artifact_prefix'] + '-' + str(run_id) + '-' + str(attempt)
        matches = [row for row in artifacts if row.get('name') == name]
        require(len(matches) == 1, 'actions_artifact_missing_or_ambiguous')
        artifact = matches[0]
        require(integer(artifact.get('id')) and artifact.get('expired') is False, 'actions_artifact_expired')
        require(type(artifact.get('size_in_bytes')) is int and 0 < artifact['size_in_bytes'] <= MAX_ARCHIVE, 'actions_archive_size')
        attached = artifact.get('workflow_run', {})
        expected = dict(id=run_id, repository_id=pr['base']['repo']['id'], head_repository_id=pr['head']['repo']['id'], head_sha=head, head_branch=pr['head']['ref'])
        require(all(type(attached.get(key)) is type(value) and attached.get(key) == value for key, value in expected.items()), 'actions_artifact_run_identity')
        proof = receipt(self.get('actions/artifacts/' + str(artifact['id']) + '/zip', binary=True), artifact)
        expected_proof = dict(version=1, repository=repo, repository_id=pr['base']['repo']['id'], head_repository_id=pr['head']['repo']['id'], run_id=run_id, run_attempt=attempt, event='pull_request', pull_request=pr['number'], head=head, base=pr['base']['sha'], merge=merge, checkout=merge, parents=[pr['base']['sha'], head], workflow_path=contract['workflow_path'], workflow_sha=merge, workflow_sha256=contract['workflow_sha256'], producer_job=contract['producer_job'], ref='refs/pull/' + str(pr['number']) + '/merge', head_ref=pr['head']['ref'], base_ref=pr['base']['ref'])
        require(proof == expected_proof, 'actions_receipt_candidate_mismatch')
        require(isinstance(check.get('output', {}), dict), 'invalid_actions_check_output')
        result = dict(name=check['name'], app_id=configured['app_id'], id=check['id'], reported_head=check['head_sha'], head=merge, status=check['status'], conclusion=check['conclusion'], output=check.get('output', {}), actions=dict(run_id=run_id, run_attempt=attempt, run_number=run['run_number'], workflow_id=run['workflow_id'], check_suite_id=run['check_suite_id'], job_id=tested['id'], producer_job_id=producer['id'], artifact_id=artifact['id'], artifact_digest=artifact['digest'], workflow_sha256=contract['workflow_sha256']))
        if check['conclusion'] == 'failure' and not any(isinstance(result['output'].get(key), str) and result['output'][key].strip() for key in ('summary', 'text')):
            try:
                raw = self.get('actions/jobs/' + str(tested['id']) + '/logs', binary=True)
                if type(raw) is bytes:
                    result['actions']['diagnostic_log'] = dict(raw_sha256=hashlib.sha256(raw).hexdigest(), raw_bytes=len(raw))
                text, provenance = failed_segments(raw, tested.get('steps'))
                result['output'] = dict(result['output'], text=text)
                result['actions']['diagnostics'] = provenance
            except (ValueError, KeyError, TypeError, IndexError, OverflowError, AttributeError) as exc:
                reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'[a-z_]+', str(exc)) else 'actions_diagnostics_unavailable'
                result['actions']['diagnostic_reason'] = reason
        return result


def resolve(host, p, pr):
    """Return only configured Actions identities; unverifiable evidence stays unknown."""
    adapter = Resolver(host, p, pr)
    rows = []
    for configured in p['checks']:
        if 'actions' not in configured:
            continue
        try:
            rows.append(adapter.resolve(configured))
        except (ValueError, KeyError, TypeError, IndexError, OverflowError, AttributeError) as exc:
            # Stable reasons omit untrusted API/transport output and personal paths.
            reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'[a-z_]+', str(exc)) else 'actions_evidence_unavailable'
            rows.append(dict(name=configured['name'], app_id=configured['app_id'], id=None, reported_head=getattr(adapter, 'reported_head', None), head=None, status='unknown', conclusion=None, output={}, reason=reason))
    return rows
