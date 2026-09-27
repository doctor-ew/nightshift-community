#!/usr/bin/env python3
"""Independent sequential package acceptance using disposable synthetic providers."""
import difflib
import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('package_acceptance_fixture',Path(__file__).with_name('test-package-controller.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class PackageAcceptanceReview(unittest.TestCase):
    setUp=f.Controller.setUp
    prepare=f.Controller.prepare

    def test_exhausted_child_external_adoption_reuses_unrelated_and_never_reimplements_child(self):
        self.graph['children'][1]['allowance']['calls']=12
        plan=self.root/'docs/right/operations.json';value=json.loads(plan.read_text());value['aggregate']['calls']=12;plan.write_text(json.dumps(value))
        (self.root/'graph.json').write_text(json.dumps(self.graph))
        grant=self.prepare()['id'];base=self.worker;repair=[0];reject=[True]
        def worker(operation,packet,*args):
            right='docs/right/SPEC.md' in packet['artifacts']
            base.fail=right and operation=='review' and reject[0]
            base.patch=''
            if right and operation=='implement':
                before=packet['artifacts']['right.py'];repair[0]+=1
                after=before+'# bounded repair '+str(repair[0])+'\n'
                base.patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/right.py',tofile='b/right.py'))
            return base(operation,packet,*args)
        self.c.worker=worker
        failed=self.c.run(grant)
        self.assertEqual(failed['status'],'blocked',failed)
        right=self.c.child('right');left=self.c.child('left')
        failures=[a for a in right.state['attempts'] if a['operation']=='review' and a['status']=='failed']
        self.assertEqual(len(failures),3)
        self.assertTrue(any(s.get('reason')=='repair_limit_exhausted' for s in right.state['supervisors'].values()))
        self.assertEqual(sum(a['operation']=='implement' for a in right.state['attempts']),3)
        retained_left=left.path.read_bytes();retained_calls=len(base.calls)
        stopped=m.Packages(self.root,'demo',worker).run(grant)
        self.assertEqual(stopped['status'],'blocked')
        self.assertEqual(len(base.calls),retained_calls)
        reject[0]=False
        source=right.project/'right.py';source.write_text(source.read_text()+'# external reviewed implementation\n')
        assessed=right.assess('adopt')
        external=right.authorize(['adopt'],assessed['binding'],'synthetic','external-after-exhaustion',dict(binding=assessed['binding'],provider='human',identity='synthetic-external-author'))
        self.assertEqual(right.execute(external['id'],'adopt','external-adoption')['status'],'passed')
        resumed=m.Packages(self.root,'demo',worker);result=resumed.run(grant)
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        recovered=resumed.child('right')
        self.assertEqual(sum(a['operation']=='implement' for a in recovered.state['attempts']),3)
        self.assertEqual(len([a for a in recovered.state['attempts'] if a['operation']=='review' and a['status']=='failed']),3)
        self.assertTrue(recovered.state['results']['implement']['external'])
        self.assertEqual(recovered.state['results']['implement']['provenance']['identity'],'synthetic-external-author')
        self.assertEqual(left.path.read_bytes(),retained_left)
        self.assertEqual(sum(op=='implement' for op,_ in base.calls[retained_calls:]),1)
        self.assertEqual(result['usage']['calls'],len(base.calls))
        self.assertEqual(result['usage']['unknown_calls'],0)
        self.assertIn('external reviewed implementation',(resumed.child('integration').project/'right.py').read_text())
        calls=list(base.calls);usage=result['usage'];again=m.Packages(self.root,'demo',worker).run(grant)
        self.assertEqual(again['status'],'pending_manual_acceptance',again)
        self.assertEqual(base.calls,calls);self.assertEqual(again['usage'],usage)

    def test_standalone_package_then_composition_reuses_exact_bindings_and_authority(self):
        grant=self.prepare()['id']
        with self.c.lease():
            child=self.c.materialize(self.c.state['authorizations'][grant]['graph']['children'][0],grant)
        assessed=child.assess('groom-spec')
        standalone=child.authorize(m.ops.RECIPES['factory'],assessed['binding'],'synthetic','standalone-package',{'bounded_repair':True})
        result=m.ops.load('operation-supervisor').run(child,standalone['id'])
        self.assertEqual(result['status'],'passed',result)
        bindings={op:child.assess(op)['binding'] for op in m.ops.RECIPES['factory']}
        retained=child.path.read_bytes();calls=len(self.worker.calls)
        result=self.c.run(grant)
        self.assertEqual(result['status'],'pending_manual_acceptance',result)
        child=self.c.child('left')
        self.assertEqual(child.path.read_bytes(),retained)
        self.assertEqual({op:child.assess(op)['binding'] for op in m.ops.RECIPES['factory']},bindings)
        self.assertEqual(set(child.state['authorizations']),{'standalone-package'})
        self.assertEqual(sum(op=='implement' for op,_ in self.worker.calls[calls:]),2)
        self.assertEqual(result['usage']['calls'],len(self.worker.calls))
        self.assertEqual(result['usage']['orchestration_provider_calls'],0)

if __name__=='__main__':unittest.main()
