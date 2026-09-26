#!/usr/bin/env python3
"""Independent snapshot-threading and fresh-boundary regressions."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('context_fixture',ROOT/'tests/test-operations.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class ContextReview(unittest.TestCase):
    setUp=f.Operations.setUp
    tearDown=f.Operations.tearDown
    grant=f.Operations.grant
    full=f.Operations.full
    modify_plan=f.Operations.modify_plan
    def ask(self):
        assessed=self.c.assess('groom-spec')
        with self.c.lease():return self.c.question('groom-spec',assessed['binding'],dict(question='Which synthetic behavior?',reason='Context regression',options=[]))
    def typed(self):
        self.plan['checks'][0]['adapter']='unittest-v1';self.modify_plan()
        path=self.root/'test_app.py';path.write_text(path.read_text().replace('unittest.main()',"if __name__=='__main__':unittest.main()"))
    def test_provided_context_preserves_basis_without_rebuilding(self):
        self.ask();p,context=self.c.context();deps=self.c.dependencies('groom-spec',p,context)
        expected=self.c.question_basis(deps,'groom-spec');rows=self.c.decision_rows('groom-spec',deps)
        with patch.object(self.c,'context',side_effect=AssertionError('nested context rebuild')):
            self.assertEqual(self.c.question_basis(deps,'groom-spec',context),expected)
            self.assertEqual(self.c.decision_rows('groom-spec',deps,context),rows)
            self.assertEqual(self.c.dependencies('groom-spec',p,context),deps)
    def test_exact_assessment_binding_matches_prior_reconstruction(self):
        self.ask();threaded=self.c.assess('groom-spec');original=self.c.question_basis
        with patch.object(self.c,'question_basis',side_effect=lambda deps,operation,context=None:original(deps,operation)):
            reconstructed=self.c.assess('groom-spec')
        self.assertEqual(threaded,reconstructed)
    def test_outer_assessments_observe_source_and_effective_environment_drift(self):
        self.typed();self.ask();before=self.c.assess('groom-spec')
        (self.root/'spec.md').write_text('Changed specification\n')
        after=self.c.assess('groom-spec');self.assertNotEqual(before['binding'],after['binding']);self.assertFalse(after['questions'][0]['current'])
        binding=self.c.assess('verify')['binding']
        with patch.dict(os.environ,{'LANG':'synthetic-context-changed'}):self.assertNotEqual(self.c.assess('verify')['binding'],binding)
    def test_completed_typed_view_uses_one_context_per_operation(self):
        self.typed();question=self.ask();self.c.answer('groom-spec',self.c.assess('groom-spec')['binding'],question['sha256'],'','Return two.')
        self.full();original=subprocess.run;probes=[]
        def observed(argv,*args,**kwargs):
            selected=isinstance(argv,list) and '-I' in argv and '-c' in argv and any('root.glob' in str(x) for x in argv)
            started=time.perf_counter();result=original(argv,*args,**kwargs)
            if selected:probes.append(time.perf_counter()-started)
            return result
        started=time.perf_counter()
        with patch.object(self.c,'context',wraps=self.c.context) as context,patch.object(subprocess,'run',observed):
            view=self.c.view()
        elapsed=time.perf_counter()-started
        self.assertEqual(view['status'],'pending_manual_acceptance');self.assertEqual(context.call_count,len(m.OPS));self.assertEqual(len(probes),len(m.OPS))
        report=dict(synthetic=True,view_seconds=elapsed,identity_subprocesses=len(probes),identity_seconds=sum(probes),context_calls=context.call_count)
        print(json.dumps(report),flush=True)
        evidence=ROOT/'test-output/operation-context-review.json'
        evidence.parent.mkdir(parents=True,exist_ok=True)
        evidence.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':unittest.main()
