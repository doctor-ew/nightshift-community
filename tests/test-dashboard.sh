#!/usr/bin/env bash
# Behavioral fixtures for the read-only dashboard. No network or provider calls.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$root" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse

SCRIPT = Path(sys.argv.pop()) / 'scripts/nightshift-dashboard.sh'

class Document(HTMLParser):
    def __init__(self, body):
        super().__init__(); self.text = []; self.links = []; self.tags = []
        self.feed(body)
    def handle_data(self, text):
        self.text.append(text)
    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for key, value in attrs:
            if key == 'href': self.links.append(value)
            if key.lower().startswith('on'): raise AssertionError('event handler attribute')
    @property
    def visible(self): return ' '.join(self.text)

class Dashboard(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'dashboard entrypoint must exist for durable-state reporting')
        self.tmp = tempfile.TemporaryDirectory(prefix='nightshift dashboard ')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.repo = self.home / 'selected repo'
        self.repo.mkdir()
        self.git(self.repo, 'init', '-q')
        self.git(self.repo, '-c', 'user.name=fixture', '-c', 'user.email=fixture@local',
                 'commit', '--allow-empty', '-qm', 'fixture')
    def git(self, repo, *args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL, text=True).strip()
    def write(self, rel, data, root=None):
        p = (root or self.repo) / rel; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data)); return p
    def render(self, *args):
        r = subprocess.run(['bash', str(SCRIPT), '--project', str(self.repo), *args], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('<html', r.stdout.lower()); self.assertIn('</html>', r.stdout.lower())
        return r.stdout, Document(r.stdout)
    def receipt(self, task, status='failed', **extra):
        r = dict(ticket=task, status=status, gate='review', provider='claude', worktree=str(self.repo),
                 repair_budget=3, attempts=[{'attempt':1,'exit_code':1}, {'repair_after_attempt':1,'exit_code':0},
                                           {'attempt':2,'exit_code':1}], next_action='inspect smallest cause')
        r.update(extra); return r
    def snapshot(self):
        result = {}
        for base in [self.repo / '.nightshift', self.repo / '.drew', self.repo / '.claude', self.repo / 'docs']:
            if base.exists():
                for p in base.rglob('*'):
                    if p.is_file() and not p.is_symlink():
                        result[str(p)] = (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
        return result
    def test_empty_and_usage(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK), 'installed entrypoint must be executable')
        _, doc = self.render(); self.assertRegex(doc.visible.lower(), 'no |empty|unknown')
        for args, expected in [(['--help'],0), (['--invalid'],1), (['--project'],1),
                               (['--project',str(self.home)],1)]:
            r = subprocess.run(['bash',str(SCRIPT),*args],capture_output=True,text=True)
            self.assertEqual(r.returncode == 0, expected == 0, r.stdout+r.stderr)
    def test_durable_status_fields_and_read_only(self):
        statuses = {task:{'status':status,'gate':'qa','provider':'codex','reason':'needs audit'} for task,status in
                    [('active-task','in_progress'),('done-task','complete'),('bad-task','failed'),
                     ('blocked-task','blocked'),('decision-task','needs-decision')]}
        batch = self.write('.nightshift/batch-20300101-0101.json', {'batch_id':'20300101-0101','statuses':statuses})
        rec = self.write('.nightshift/receipts/gate.json',self.receipt('receipt-task'))
        before = self.snapshot(); _, doc = self.render(); self.assertEqual(before,self.snapshot())
        for word in [*statuses, 'receipt-task','in_progress','complete','blocked','needs-decision','review','claude','codex','inspect smallest cause']:
            self.assertIn(word,doc.visible)
        self.assertIn(batch.as_uri(),doc.links); self.assertIn(rec.as_uri(),doc.links)
        self.assertRegex(doc.visible.lower(),'remaining')
    def test_registered_worktrees_and_legacy_homes_only(self):
        wt=self.home/'registered worktree'; self.git(self.repo,'worktree','add','-qb','ticket',str(wt))
        self.write('.drew/receipt.json',self.receipt('legacy-task'),root=wt)
        self.write('.claude/task-progress/receipt.json',self.receipt('claude-state-task'))
        outside=self.home/'unrelated'; outside.mkdir()
        self.write('.nightshift/receipt.json',self.receipt('UNRELATED_SECRET_MARKER'),root=outside)
        _,doc=self.render()
        self.assertIn('legacy-task',doc.visible);self.assertIn('claude-state-task',doc.visible)
        self.assertNotIn('UNRELATED_SECRET_MARKER',doc.visible)
    def test_artifacts_escape_and_unsafe_links(self):
        task='danger-task'; evil='<script>alert("payload")</script>'
        marker=self.home/'executed-marker'
        self.write('.nightshift/receipt.json',self.receipt(task,reason=evil,commands={'attempt':'touch '+str(marker)}))
        artifact=self.repo/'docs'/task/'spec with # &.md'; artifact.parent.mkdir(parents=True); artifact.write_text('safe artifact')
        outside=self.home/'private.json';outside.write_text(json.dumps(self.receipt('EXTERNAL_SECRET_MARKER')))
        (self.repo/'.nightshift'/'escape.json').symlink_to(outside)
        (artifact.parent/'escape.md').symlink_to(outside)
        (self.repo/'.nightshift'/'escaped-dir').symlink_to(self.home,target_is_directory=True)
        for index,target in enumerate(['javascript:alert(1)','https://example.invalid/','../../private.json',str(outside)]):
            self.write('.nightshift/unsafe-'+str(index)+'.json',self.receipt('unsafe-'+str(index),receipt=target))
        body,doc=self.render()
        self.assertIn(evil,doc.visible);self.assertNotIn('<script>',body);self.assertNotIn('script',doc.tags)
        self.assertIn(artifact.as_uri(),doc.links);self.assertNotIn('EXTERNAL_SECRET_MARKER',doc.visible)
        self.assertFalse(marker.exists())
        for link in doc.links:
            self.assertEqual(urlparse(link).scheme,'file',link)
            target=Path(unquote(urlparse(link).path)).resolve()
            self.assertNotEqual(target,outside.resolve())
            self.assertTrue(target.is_file())
    def test_bad_shapes_and_corruption_keep_healthy_rows(self):
        self.write('.nightshift/good.json',self.receipt('healthy-task'))
        p=self.repo/'.nightshift/broken.json';p.write_text('{')
        self.write('.nightshift/wrong.json',{'ticket':'wrong-type','status':{'complete':True},'attempts':'oops','repair_budget':False})
        self.write('.nightshift/bad-batch.json',{'batch_id':'invalid','statuses':['complete']})
        self.write('.nightshift/list.json',['not','a','record'])
        _,doc=self.render();self.assertIn('healthy-task',doc.visible)
        self.assertRegex(doc.visible.lower(),'error|unknown');self.assertIn('broken.json',doc.visible)
    def test_ownership_is_metadata_not_run_success(self):
        common=Path(self.git(self.repo,'rev-parse','--git-common-dir'))
        if not common.is_absolute(): common=self.repo/common
        self.write('nightshift/worktrees/owned-task.json',dict(version=1,task='owned-task',repository=str(common.resolve()),
                   branch='nightshift/owned-task',worktree=str(self.repo),base_ref='HEAD',base_sha=self.git(self.repo,'rev-parse','HEAD'),
                   dependency='',status='finished'),root=common)
        self.write('.nightshift/receipt.json',self.receipt('owned-task',status='blocked'))
        _,doc=self.render();self.assertIn('owned-task',doc.visible);self.assertIn('blocked',doc.visible)
        self.assertRegex(doc.visible.lower(),'ownership|worktree')
    def test_oversized_json_is_reported(self):
        self.write('.nightshift/good.json',self.receipt('survives-large-record'))
        huge=self.repo/'.nightshift/large.json';huge.write_text(' '*(2*1024*1024)+'{}')
        _,doc=self.render();self.assertIn('survives-large-record',doc.visible)
        self.assertRegex(doc.visible.lower(),'error|oversiz|limit|large')
    def test_invalid_unicode_preserves_healthy_rows(self):
        self.write('.nightshift/healthy.json', self.receipt('healthy-unicode-task'))
        self.write('.nightshift/surrogate.json', self.receipt('invalid-\ud800-task', reason='broken-\udfff-reason'))
        _, doc = self.render()
        self.assertIn('healthy-unicode-task', doc.visible)
        self.assertRegex(doc.visible.lower(), 'invalid|unknown|error|replacement')
    def test_overlapping_records_preserve_provenance(self):
        self.write('.nightshift/batch-20300101-0101.json',{'batch_id':'20300101-0101','statuses':{'same-task':{'status':'in_progress'}}})
        self.write('.nightshift/gate.json',self.receipt('same-task',status='complete'))
        _,doc=self.render();self.assertIn('in_progress',doc.visible);self.assertIn('complete',doc.visible)
        self.assertIn('batch-20300101-0101.json',doc.visible);self.assertIn('gate.json',doc.visible)

unittest.main(verbosity=2)
PY
