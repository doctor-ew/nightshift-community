#!/usr/bin/env python3
"""Bounded, model-free regression evidence. This does not approve any gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

MAX_BYTES = 2_000_000
MAX_FINDINGS = 256


def digest(data):
    return hashlib.sha256(data).hexdigest()


def confined(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute() or '..' in Path(value).parts:
        raise ValueError('paths must be nonempty project-relative paths without traversal')
    path = root / value
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('path escapes project')
    # Refuse symlink aliases, including output paths, rather than guessing ownership.
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError('symlink paths are not allowed')
    return path


def read_json(path):
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('JSON input exceeds bounded size')
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('duplicate JSON key')
            obj[key] = value
        return obj
    def nonfinite(value):
        raise ValueError('non-finite JSON number')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite), digest(raw)


def pointer_value(document, pointer):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')) or re.search(r'~(?![01])', pointer):
        raise ValueError('invalid JSON pointer')
    value = document
    for raw in pointer.split('/')[1:] if pointer else []:
        key = raw.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict):
            if key not in value:
                return False, None
            value = value[key]
        elif isinstance(value, list) and re.fullmatch(r'0|[1-9][0-9]*', key):
            index = int(key)
            if index >= len(value):
                return False, None
            value = value[index]
        else:
            return False, None
    return True, value


def equal(actual, expected):
    # Python considers True == 1; JSON assertions must preserve their types.
    return json.dumps(actual, sort_keys=True, separators=(',', ':')) == json.dumps(expected, sort_keys=True, separators=(',', ':'))


def check(root, manifest, output):
    root = Path(root).resolve(strict=True)
    manifest_path = confined(root, manifest)
    out = confined(root, output)
    if out.name != 'repair-check.receipt.json' or out.parent != manifest_path.parent:
        raise ValueError('receipt must be repair-check.receipt.json beside the manifest')
    data, manifest_hash = read_json(manifest_path)
    if not isinstance(data, dict) or set(data) != {'schema_version', 'findings'} or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('invalid repair manifest schema')
    findings = data['findings']
    if not isinstance(findings, list) or not 1 <= len(findings) <= MAX_FINDINGS:
        raise ValueError('manifest requires 1..256 findings')
    loaded = {}
    ids = set()
    rows = []
    for finding in findings:
        fields = {'id', 'artifact', 'pointer', 'expected', 'prior_artifact', 'prior_sha256'}
        if not isinstance(finding, dict) or set(finding) != fields:
            raise ValueError('invalid finding fields')
        identity = finding['id']
        if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', identity) or identity in ids:
            raise ValueError('finding IDs must be stable, bounded and unique')
        ids.add(identity)
        if not isinstance(finding['prior_sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', finding['prior_sha256']):
            raise ValueError('prior_sha256 must pin the pre-repair snapshot')
        paths = [confined(root, finding[key]) for key in ('artifact', 'prior_artifact')]
        if paths[0] == paths[1] or out in paths or manifest_path in paths:
            raise ValueError('snapshot, artifact, manifest and receipt must be distinct')
        for path in paths:
            if path not in loaded:
                loaded[path] = read_json(path)
        current, current_hash = loaded[paths[0]]
        prior, prior_hash = loaded[paths[1]]
        if prior_hash != finding['prior_sha256']:
            raise ValueError('pre-repair snapshot hash mismatch')
        present_before, before = pointer_value(prior, finding['pointer'])
        present_after, after = pointer_value(current, finding['pointer'])
        original_failed = not present_before or not equal(before, finding['expected'])
        current_passed = present_after and equal(after, finding['expected'])
        rows.append({'id': identity, 'artifact': finding['artifact'], 'pointer': finding['pointer'],
                     'prior_artifact': finding['prior_artifact'], 'prior_sha256': prior_hash,
                     'artifact_content_sha256': digest(json.dumps(current, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()),
                     'artifact_sha256': current_hash, 'original_failed': original_failed,
                     'current_passed': current_passed, 'passed': original_failed and current_passed})
    # Fail if any input changed while collecting this receipt.
    for path, (_, expected_hash) in loaded.items():
        if read_json(path)[1] != expected_hash:
            raise ValueError('artifact changed during check')
    if read_json(manifest_path)[1] != manifest_hash:
        raise ValueError('manifest changed during check')
    receipt = {'schema_version': 1, 'status': 'passed' if all(row['passed'] for row in rows) else 'failed',
               'manifest': manifest, 'manifest_sha256': manifest_hash, 'findings': rows,
               'gate_approval': False}
    out.parent.mkdir(parents=True, exist_ok=True)
    # Atomic publication, no partial success receipt.
    fd, temporary = tempfile.mkstemp(prefix='.repair-check-', dir=out.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2)
            stream.write('\n')
        os.replace(temporary, out)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return receipt



def apply(root, manifest, output):
    """Explicitly apply pinned JSON corrections; never author prose or approve gates."""
    root = Path(root).resolve(strict=True)
    # Validate every entry/path/hash before modifying any artifact.
    initial = check(root, manifest, output)
    if initial['status'] == 'passed':
        return initial
    data, manifest_hash = read_json(confined(root, manifest))
    if manifest_hash != initial['manifest_sha256']:
        raise ValueError('manifest changed before apply')
    findings = data['findings']
    if len({f['artifact'] for f in findings}) != 1:
        raise ValueError('apply requires exactly one artifact for atomic repair')
    if not all(row['original_failed'] for row in initial['findings']):
        raise ValueError('apply requires every original assertion to fail')
    path = confined(root, findings[0]['artifact'])
    document, current_hash = read_json(path)
    if any(current_hash != f['prior_sha256'] for f in findings):
        raise ValueError('artifact changed since pinned snapshot; refusing overwrite')
    pointers = []
    for finding in findings:
        pointer = finding['pointer']
        if not pointer_value(document, pointer)[0]:
            raise ValueError('apply requires existing JSON pointers')
        tokens = [t.replace('~1', '/').replace('~0', '~') for t in pointer.split('/')[1:]] if pointer else []
        for previous in pointers:
            if tokens[:len(previous)] == previous or previous[:len(tokens)] == tokens:
                raise ValueError('apply refuses overlapping JSON pointers')
        pointers.append(tokens)
    for finding, tokens in zip(findings, pointers):
        if not tokens:
            document = finding['expected']
            continue
        parent = document
        for token in tokens[:-1]:
            parent = parent[int(token)] if isinstance(parent, list) else parent[token]
        if isinstance(parent, list):
            parent[int(tokens[-1])] = finding['expected']
        else:
            parent[tokens[-1]] = finding['expected']
    encoded = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode()
    if len(encoded) > MAX_BYTES:
        raise ValueError('repaired JSON exceeds bounded size')
    fd, temporary = tempfile.mkstemp(prefix='.repair-apply-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777)
        # Guard against intervening normal edits before atomic publication.
        if read_json(path)[1] != current_hash or read_json(confined(root, manifest))[1] != manifest_hash:
            raise ValueError('inputs changed during apply')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return check(root, manifest, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'apply'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        result = (apply if args.command == 'apply' else check)(args.project, args.manifest, args.out)
    except (ValueError, OSError, RecursionError) as error:
        print(json.dumps({'status': 'error', 'error': str(error), 'gate_approval': False}))
        return 2
    print(json.dumps({'status': result['status'], 'receipt': args.out, 'gate_approval': False}))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
