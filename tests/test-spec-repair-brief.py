#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('brief',ROOT/'scripts/nightshift-spec-repair-brief.py')
brief=importlib.util.module_from_spec(spec);spec.loader.exec_module(brief)

class RepairBrief(unittest.TestCase):
    def test_current_concrete_findings_required_for_existing_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.assertEqual(brief.brief(root),'')
            draft=root/'SPEC.md';draft.write_text('# Existing draft\n')
            with self.assertRaisesRegex(ValueError,'reuse it'):brief.brief(root)
            data={'spec_sha256':hashlib.sha256(draft.read_bytes()).hexdigest(),'findings':[{'id':'AC-1','target':'Acceptance Criteria','problem':'Retain user-owned manual verification'}]}
            path=root/'spec-repair.json';path.write_text(json.dumps(data))
            self.assertIn('Preserve unaffected',brief.brief(root))
            draft.write_text('# Changed draft\n')
            with self.assertRaisesRegex(ValueError,'current draft'):brief.brief(root)

    def test_missing_brief_stops_before_provider_authentication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); binary=root/'bin';binary.mkdir();calls=root/'calls'
            stub=binary/'claude';stub.write_text('#!/bin/sh\necho called >> "'+str(calls)+'"\nexit 1\n');stub.chmod(0o755)
            (root/'SPEC.md').write_text('# Existing draft\n')
            request=root/'request.md';request.write_text('Rewrite the whole spec.')
            env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],NIGHTSHIFT_ROUTING_FILE=str(ROOT/'routing.json'),NIGHTSHIFT_PROVIDER_POLICY='claude-only')
            run=subprocess.run(['bash',str(ROOT/'scripts/nightshift-agent.sh'),'nightshift-spec-writer','--gear','1','--in',str(request),'--out',str(root/'writer.json')],env=env,capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertFalse(calls.exists())
            self.assertIn('focused repair brief',json.loads((root/'writer.json').read_text())['reason'])

if __name__=='__main__':unittest.main()
