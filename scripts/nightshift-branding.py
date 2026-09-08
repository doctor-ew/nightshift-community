#!/usr/bin/env python3
"""Read-only, explicitly scoped source and installed artifact audit."""
import sys

sys.dont_write_bytecode = True

import argparse
from collections import deque
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

ARTIFACT_LIMIT = 4 * 1024 * 1024
RECORD_LIMIT = 1024 * 1024
ROOT_FILES = (
    'README.md', 'CLAUDE' + '.md', 'AGENTS.md', 'SECURITY.md', 'CONTRIBUTING.md',
    'CODE_OF_CONDUCT.md', 'LICENSE', 'VERSION', '.gitignore', 'install.sh',
    'routing.json', 'nightshift.toml',
)
ROOT_DIRS = ('scripts', 'commands', 'agents', 'skills', 'tests', 'docs',
             'contracts', 'evals', 'dashboard', '.github')
RULES = {'retired-brand', 'provider-mcp', 'provider-executor', 'role-model',
         'legacy-project-context', 'legacy-convention'}
RETIRED = re.compile('|'.join((
    'cx' + 'eng', 'con' + 'nexure', 'drew' + r'[-_ ]pipeline', 'drew' + '-',
    r'(?<![\w/])/' + r'cx(?:-[a-z0-9]+)*(?![\w-])', 'CX' + ' ADR-002',
)), re.I)
MCP = re.compile(r'\bmcp__\w+__\w+\b|\bmcp_[a-z0-9_]*(?:claude|codex|openai|anthropic)[a-z0-9_]*\b', re.I)
EXECUTOR = re.compile(
    r'\bclaude\s+(?:-p\b|--print\b)|\bcodex\s+exec\b|'
    r'\b(?:run|invoke|execute|use)\s+(?:the\s+)?(?:claude(?:\s+code)?|codex)\b|'
    r'\b(?:run|executed|performed)\s+(?:inline\s+)?by\s+(?:claude(?:\s+code)?|codex)\b', re.I)
NEGATIVE = re.compile(r'\b(?:do\s+not|don.t|never|must\s+not|no|not)\s+(?:\w+\s+){0,3}(?:invoke|run|execute|executed|performed|use|call)\b', re.I)


class AuditError(Exception):
    """Only fixed reason codes cross the output boundary."""


def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def lexical(path):
    return Path(os.path.abspath(os.path.normpath(str(path))))


def safe_source(path, root):
    """Resolve one component at a time, rejecting escapes before target stat/read."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if not inside(candidate, root):
        raise AuditError('external')
    pending = deque(candidate.relative_to(root).parts)
    current = root
    links = set()
    followed = False
    while pending:
        part = pending.popleft()
        if part == '..':
            current = current.parent
            if not inside(current, root):
                raise AuditError('external')
            continue
        if part == '.':
            continue
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            raise AuditError('dangling' if followed else 'missing') from None
        except OSError:
            raise AuditError('unreadable') from None
        if stat.S_ISLNK(info.st_mode):
            if current in links or len(links) >= 40:
                raise AuditError('cycle')
            links.add(current)
            followed = True
            try:
                target = Path(os.readlink(current))
            except OSError:
                raise AuditError('unreadable') from None
            if target.is_absolute():
                if not inside(target, root):
                    raise AuditError('external')
                pending.extendleft(reversed(target.relative_to(root).parts))
                current = root
            else:
                pending.extendleft(reversed(target.parts))
                current = current.parent
        elif pending and not stat.S_ISDIR(info.st_mode):
            raise AuditError('unsupported')
    return current


def mapped_link_source(path, expected, project):
    """Validate the actual payload before accepting its declared-source spelling."""
    try:
        payload = Path(os.readlink(path))
    except OSError:
        raise AuditError('unreadable') from None
    if payload.is_absolute():
        target = payload
    else:
        # This parent was already validated physically by installed traversal.
        # Leading parent steps need no lookup; later steps retain OS ordering.
        parent = path.parent
        parts = deque(payload.parts)
        while parts and parts[0] in ('.', '..'):
            if parts.popleft() == '..':
                parent = parent.parent
        target = parent.joinpath(*parts)
    if lexical(target) != expected:
        raise AuditError('external')
    try:
        actual = safe_source(target, project)
        declared = safe_source(expected, project)
    except AuditError as error:
        if str(error) == 'missing':
            raise AuditError('dangling') from None
        raise
    if actual != declared:
        raise AuditError('external')
    return actual


def read_text(path, limit=ARTIFACT_LIMIT):
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise AuditError('unsupported')
        if info.st_mode & 0o444 == 0:
            raise AuditError('unreadable')
        if info.st_size > limit:
            raise AuditError('oversized')
        with path.open('rb') as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise AuditError('oversized')
        return data.decode('utf-8')
    except UnicodeError:
        raise AuditError('invalid_encoding') from None
    except OSError:
        raise AuditError('unreadable') from None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuditError('duplicate_keys')
        result[key] = value
    return result


def parse_json(text):
    try:
        return json.loads(text, object_pairs_hook=unique_object)
    except (ValueError, RecursionError):
        raise AuditError('invalid_json') from None


def excluded(relative):
    parts = Path(relative).parts
    return ('__pycache__' in parts or Path(relative).suffix in ('.pyc', '.pyo')
            or parts[:2] == ('dashboard', 'node_modules'))


def affirmative(pattern, line):
    for match in pattern.finditer(line):
        # A prohibition suppresses only its own clause, not a later affirmative call.
        prefix = line[:match.start()]
        boundary = max(prefix.rfind(';'), prefix.rfind('. '), prefix.rfind('! '), prefix.rfind('? '))
        clause = line[boundary + 1:match.end()]
        if not NEGATIVE.search(clause):
            return True
    return False


def matches(relative, content):
    if RETIRED.search(relative):
        yield 'retired-brand', 0, relative
    core = ((relative.startswith(('commands/', 'agents/')) and relative.endswith('.md'))
            or (relative.startswith('scripts/') and relative.endswith(('.sh', '.py'))))
    lines = content.splitlines()
    frontmatter = relative.startswith('agents/') and bool(lines) and lines[0].lstrip('\ufeff').strip() == '---'
    for number, line in enumerate(lines, 1):
        if RETIRED.search(line):
            yield 'retired-brand', number, line
        if not core:
            continue
        if number > 1 and frontmatter and line.strip() == '---':
            frontmatter = False
        comment = line.lstrip().startswith(('#', '<!--', '//'))
        if frontmatter and not comment and re.match(r'''^\s*(?:model|'model'|"model")\s*:''', line):
            yield 'role-model', number, line
        if comment:
            continue
        if affirmative(MCP, line):
            yield 'provider-mcp', number, line
        if affirmative(EXECUTOR, line):
            yield 'provider-executor', number, line
        if 'CLAUDE' + '_PROJECT_DIR' in line:
            yield 'legacy-project-context', number, line
        if 'CLAUDE' + '.md' in line:
            yield 'legacy-convention', number, line


class Audit:
    def __init__(self, project, requested):
        self.project = project
        self.requested = requested
        self.findings = []
        self.coverage = []
        self.inventories = {}
        self.exceptions = {}
        self.used = set()
        self.source_files = {}

    def counts(self, inventory):
        if inventory not in self.inventories:
            self.inventories[inventory] = dict(status='complete', discovered=0, scanned=0,
                                             missing=0, unreadable=0, unknown=0, excluded=0)
        return self.inventories[inventory]

    def diagnostic(self, inventory, path, reason):
        self.coverage.append(dict(inventory=inventory, path=path, reason=reason))
        counts = self.counts(inventory)
        if reason in ('excluded', 'not_installed', 'missing_ownership'):
            if reason == 'excluded':
                counts['excluded'] += 1
            return
        counts['status'] = 'incomplete'
        bucket = 'missing' if reason in ('missing', 'dangling') else (
            'unknown' if reason in ('unknown_ownership', 'invalid_ownership', 'missing_ownership') else 'unreadable')
        counts[bucket] += 1

    def load_policy(self):
        path = safe_source(self.project / 'scripts/nightshift-branding-policy.json', self.project)
        policy = parse_json(read_text(path, RECORD_LIMIT))
        if (not isinstance(policy, dict) or set(policy) != {'version', 'exceptions'}
                or type(policy['version']) is not int or policy['version'] != 1
                or not isinstance(policy['exceptions'], list)):
            raise AuditError('invalid_policy')
        for entry in policy['exceptions']:
            if not isinstance(entry, dict) or set(entry) != {'rule', 'path', 'context', 'reason'}:
                raise AuditError('invalid_policy')
            if any(not isinstance(entry[key], str) or not entry[key].strip() for key in entry):
                raise AuditError('invalid_policy')
            relative = entry['path']
            if (entry['rule'] not in RULES or relative.startswith('/')
                    or any(part in ('', '.', '..') for part in relative.split('/'))
                    or '\\' in relative or '\n' in entry['context'] or '\r' in entry['context']):
                raise AuditError('invalid_policy')
            key = (entry['rule'], relative, entry['context'])
            if key in self.exceptions:
                raise AuditError('invalid_policy')
            self.exceptions[key] = entry['reason']

    def scan(self, inventory, logical, relative, path):
        self.counts(inventory)['discovered'] += 1
        try:
            content = read_text(path)
        except AuditError as error:
            self.diagnostic(inventory, logical, str(error))
            return
        self.counts(inventory)['scanned'] += 1
        if inventory == 'source':
            self.source_files[relative] = content
        for rule, line, context in matches(relative, content):
            key = (rule, relative, context)
            if key in self.exceptions:
                if inventory == 'source':
                    self.used.add(key)
                continue
            self.findings.append(dict(inventory=inventory, rule=rule, path=logical, line=line))
        # Installed logical names also carry branding requirements, independently of source classification.
        if inventory == 'installed' and RETIRED.search(logical) and not RETIRED.search(relative):
            self.findings.append(dict(inventory=inventory, rule='retired-brand', path=logical, line=0))

    def source_walk(self, relative, ancestors=()):
        if excluded(relative):
            self.diagnostic('source', relative, 'excluded')
            return
        try:
            path = safe_source(self.project / relative, self.project)
            info = path.stat()
            if stat.S_ISDIR(info.st_mode):
                identity = (info.st_dev, info.st_ino)
                if identity in ancestors:
                    raise AuditError('cycle')
                if info.st_mode & 0o444 == 0 or info.st_mode & 0o111 == 0:
                    raise AuditError('unreadable')
                # Resolve before directory enumeration; never ask walk() to follow links.
                children = sorted(path.iterdir(), key=lambda item: item.name)
                if RETIRED.search(relative):
                    key = ('retired-brand', relative, relative)
                    if key in self.exceptions:
                        self.used.add(key)
                    else:
                        self.findings.append(dict(inventory='source', rule='retired-brand', path=relative, line=0))
                for child in children:
                    self.source_walk(relative + '/' + child.name, ancestors + (identity,))
            else:
                self.scan('source', relative, relative, path)
        except AuditError as error:
            self.diagnostic('source', relative, str(error))
        except OSError:
            self.diagnostic('source', relative, 'unreadable')

    def source(self):
        self.counts('source')
        for relative in ROOT_FILES + ROOT_DIRS:
            self.source_walk(relative)
        try:
            safe_source(self.project / 'dashboard/dist', self.project)
        except AuditError as error:
            if str(error) == 'missing':
                self.diagnostic('source', 'dashboard/dist', 'not_installed')

    def validate_exceptions(self):
        if len(self.used) != len(self.exceptions):
            raise AuditError('invalid_policy')

    def installed_path(self, path, root, expected, leaf_link=True):
        """Only the mapped leaf may link, and only to its exact declared source."""
        relative = path.relative_to(root)
        current = root
        for index, part in enumerate(relative.parts):
            current /= part
            try:
                info = current.lstat()
            except FileNotFoundError:
                raise AuditError('missing') from None
            except OSError:
                raise AuditError('unreadable') from None
            if stat.S_ISLNK(info.st_mode):
                if index != len(relative.parts) - 1 or not leaf_link:
                    raise AuditError('external')
                return mapped_link_source(current, expected, self.project), True
            if index < len(relative.parts) - 1 and not stat.S_ISDIR(info.st_mode):
                raise AuditError('unsupported')
        return current, False

    def installed_tree(self, actual, expected, logical, relative, ancestors=()):
        if excluded(relative):
            self.diagnostic('installed', logical, 'excluded')
            return
        try:
            # Descendant links must correspond to this exact source descendant.
            if actual.is_symlink():
                actual = mapped_link_source(actual, expected, self.project)
            safe_source(expected, self.project)
            info = actual.stat()
            if not stat.S_ISDIR(info.st_mode):
                self.scan('installed', logical, relative, actual)
                return
            identity = (info.st_dev, info.st_ino)
            if identity in ancestors:
                raise AuditError('cycle')
            if info.st_mode & 0o444 == 0 or info.st_mode & 0o111 == 0:
                raise AuditError('unreadable')
            source_directory = safe_source(expected, self.project)
            source_info = source_directory.stat()
            if not stat.S_ISDIR(source_info.st_mode):
                raise AuditError('unsupported')
            if source_info.st_mode & 0o444 == 0 or source_info.st_mode & 0o111 == 0:
                raise AuditError('unreadable')
            source_names = {item.name for item in source_directory.iterdir()}
            names = {item.name for item in actual.iterdir()}
            for name in sorted(source_names | names):
                child_logical = logical + '/' + name
                child_relative = relative + '/' + name
                if name not in names:
                    self.diagnostic('installed', child_logical, 'missing')
                elif name not in source_names:
                    self.diagnostic('installed', child_logical, 'unknown_ownership')
                else:
                    self.installed_tree(actual / name, expected / name, child_logical,
                                        child_relative, ancestors + (identity,))
        except AuditError as error:
            self.diagnostic('installed', logical, str(error))
        except FileNotFoundError:
            self.diagnostic('installed', logical, 'dangling')
        except OSError:
            self.diagnostic('installed', logical, 'unreadable')

    def installed(self, runtime, targets):
        self.counts('installed')
        try:
            for relative in ('scripts', 'commands', 'contracts', 'agents', 'skills',
                             'skills/nightshift', 'dashboard'):
                safe_source(self.project / relative, self.project)
            try:
                safe_source(self.project / 'dashboard/dist', self.project)
            except AuditError as error:
                if str(error) != 'missing':
                    raise
            module_path = Path(__file__).absolute().parent / 'nightshift-install-inventory.py'
            spec = importlib.util.spec_from_file_location('nightshift_install_inventory', module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            inventory = module.make_inventory(self.project, runtime, targets)
            entries = inventory['entries']
        except (AuditError, OSError, ValueError, KeyError, ImportError, RuntimeError):
            self.diagnostic('installed', 'inventory', 'invalid_inventory')
            return
        by_destination = {entry['destination']: entry['source'] for entry in entries}
        records = {}
        try:
            record_path, _ = self.installed_path(targets['nightshift'] / 'install-links.json',
                                                 targets['nightshift'], self.project, False)
            records = parse_json(read_text(record_path, RECORD_LIMIT))
            if not isinstance(records, dict):
                raise AuditError('invalid_ownership')
            if any(not isinstance(key, str) or not isinstance(value, str)
                   or key not in by_destination or by_destination[key] != value
                   for key, value in records.items()):
                raise AuditError('invalid_ownership')
        except AuditError as error:
            reason = str(error)
            if reason == 'missing':
                reason = 'missing_ownership'
            elif reason not in ('oversized', 'unreadable', 'invalid_encoding', 'external'):
                reason = 'invalid_ownership'
            self.diagnostic('installed', 'nightshift/install-links.json', reason)
            records = {}
        existing = 0
        for entry in entries:
            logical = entry['logical_path']
            relative = entry['source_relative']
            destination = Path(entry['destination'])
            expected = Path(entry['source'])
            label = logical.split('/', 1)[0]
            try:
                actual, linked = self.installed_path(destination, targets[label], expected)
                existing += 1
                if entry['destination'] not in records:
                    self.diagnostic('installed', logical, 'missing_ownership' if linked else 'unknown_ownership')
                    if not linked:
                        continue
                if entry['kind'] == 'tree':
                    self.installed_tree(actual, expected, logical, relative)
                else:
                    self.scan('installed', logical, relative, actual)
            except AuditError as error:
                self.diagnostic('installed', logical, str(error))
        if not existing:
            self.counts('installed')['status'] = 'unavailable'

    def result(self, status=None):
        self.findings.sort(key=lambda row: (row['inventory'], row['path'], row['line'], row['rule']))
        self.coverage.sort(key=lambda row: (row['inventory'], row['path'], row['reason']))
        failed = bool(self.findings) or any(value['status'] != 'complete' for value in self.inventories.values())
        return dict(status=status or ('fail' if failed else 'pass'), inventories=self.inventories,
                    findings=self.findings, coverage=self.coverage)


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise AuditError('invalid_arguments')


def main():
    audit = None
    try:
        parser = Arguments(add_help=False)
        parser.add_argument('--project', required=True)
        parser.add_argument('--inventory', choices=('source', 'installed', 'all'), default='source')
        parser.add_argument('--runtime', choices=('claude', 'codex', 'local', 'all'), default='all')
        for flag in ('--target', '--codex-target', '--nightshift-target', '--bin-target'):
            parser.add_argument(flag)
        args = parser.parse_args()
        if args.inventory != 'source' and not all((args.target, args.codex_target,
                                                   args.nightshift_target, args.bin_target)):
            raise AuditError('invalid_arguments')
        try:
            project = Path(args.project).resolve(strict=True)
            if not project.is_dir():
                raise AuditError('invalid_arguments')
        except (OSError, RuntimeError):
            raise AuditError('invalid_arguments') from None
        audit = Audit(project, args.inventory)
        audit.load_policy()
        # The declared source inventory also validates exception usage for installed-only requests.
        audit.source()
        audit.validate_exceptions()
        if args.inventory == 'installed':
            audit.findings = [row for row in audit.findings if row['inventory'] != 'source']
            audit.coverage = [row for row in audit.coverage if row['inventory'] != 'source']
            audit.inventories.pop('source', None)
        if args.inventory != 'source':
            targets = {label: Path(value).resolve() for label, value in (
                ('claude', args.target), ('codex', args.codex_target),
                ('nightshift', args.nightshift_target), ('bin', args.bin_target))}
            audit.installed(args.runtime, targets)
        result = audit.result()
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if result['status'] == 'pass' else 1
    except (AuditError, OSError, ValueError, RuntimeError, RecursionError):
        # Never render an exception: it may contain source content or a user path.
        result = dict(status='invalid', inventories={}, findings=[],
                      coverage=[dict(inventory='policy', path='policy', reason='invalid_arguments_or_policy')])
        print(json.dumps(result, sort_keys=True))
        return 64


if __name__ == '__main__':
    sys.exit(main())
