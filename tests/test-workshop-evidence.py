"""Evidence attribution and complete cross-requirement coverage; no model calls."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('workshop',ROOT/'scripts/nightshift-workshop.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f=json.loads((ROOT/'tests/fixtures/workshop-false-pass.json').read_text())
        self.rows=[dict(case=o['case'],requirement=r['id'],verdict='pass',quote=o['response'][:100],reason='Fixture assessment') for o in self.f['observations'] for r in self.f['spec']['requirements']]
    def validate(self):
        return m.validate_assessments({'assessments':self.rows},self.f['spec'],self.f['cases'],self.f['observations'])
    def test_misattributed_case4_quote_cannot_support_case8(self):
        self.rows[-1]['quote']=self.f['misattributed_quote']
        with self.assertRaisesRegex(ValueError,'quote does not match'): self.validate()
    def test_nonassigned_source_failure_blocks_case7(self):
        row=next(r for r in self.rows if r['case']=='case-7' and r['requirement']=='sourced-competitor-claims');row['verdict']='fail'
        self.assertFalse(self.validate()[0]['passed'])
    def test_omitted_and_duplicate_pairs_rejected(self):
        saved=copy.deepcopy(self.rows);self.rows.pop()
        with self.assertRaisesRegex(ValueError,'every case/requirement'):self.validate()
        self.rows=saved;self.rows[-1]=self.rows[0]
        with self.assertRaisesRegex(ValueError,'duplicate'):self.validate()
    def test_unresolved_cannot_pass(self):
        self.rows[0]['verdict']='unresolved';self.assertFalse(self.validate()[0]['passed'])
    def test_assigned_requirement_cannot_be_skipped(self):
        self.rows[-1]['verdict']='not_applicable'
        with self.assertRaisesRegex(ValueError,'assigned criterion'):self.validate()
    def test_approval_boolean_cannot_override_failed_assessment(self):
        self.rows[0]['verdict']='fail'
        with tempfile.TemporaryDirectory() as d:
            reviewer=SimpleNamespace(reviewer='fixture',artifacts=Path(d),
                call=lambda *args: dict(approved=True,oracle_valid=True,issues=[],assessments=self.rows))
            self.assertFalse(m.Run.reviewed(reviewer,'code-review-0',self.f))

    def test_quotes_must_be_nonempty_and_verbatim(self):
        for quote in ('',' ','made up words not in response'):
            self.rows[0]['quote']=quote
            with self.assertRaisesRegex(ValueError,'quote does not match'):self.validate()

if __name__=='__main__':unittest.main()
