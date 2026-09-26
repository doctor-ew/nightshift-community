#!/usr/bin/env python3
"""Independent drafting authority, byte preservation and restart regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import stat
import unittest

spec=importlib.util.spec_from_file_location('draft_review_fixture',Path(__file__).with_name('test-package-draft.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class DraftReview(unittest.TestCase):
    setUp=f.Draft.setUp
    grant=f.Draft.grant

    def candidate(self,files):
        changes={name:dict(before=m.sha(self.root/name) if (self.root/name).exists() else None,text=text,after=m.hashlib.sha256(text.encode()).hexdigest()) for name,text in files.items()}
        return m.load('package-draft').validate_candidate(self.c,self.plan,changes)

    def test_package_prepare_accepts_no_child_artifacts_and_duplicate_reuses(self):
        grant=self.grant()
        packages=m.load('package-controller').Packages(self.root,'demo',self.invoke)
        result=packages.prepare(grant)
        self.assertEqual(result['status'],'ready',result)
        self.assertEqual(len(self.worker.calls),2)
        self.assertIn('docs/left/checks.py',self.worker.packets[-1]['artifacts'])
        replay=packages.prepare(grant)
        self.assertEqual(replay['binding'],result['binding'])
        self.assertEqual(len(self.worker.calls),2)
        self.assertFalse(packages.state['authorizations'])
        self.assertFalse(packages.state['children'])

    def test_partial_integration_resumes_without_redrafting(self):
        grant=self.grant();integrate=self.c.integrate
        def interrupted(changes):
            name=next(iter(changes));integrate({name:changes[name]})
            raise KeyboardInterrupt('synthetic partial draft checkpoint')
        self.c.integrate=interrupted
        with self.assertRaises(KeyboardInterrupt):self.c.execute(grant,'groom-spec','partial')
        self.assertEqual(len(self.worker.calls),1)
        resumed=m.Operations(self.root,'demo',self.invoke)
        result=resumed.execute(grant,'groom-spec','partial')
        self.assertEqual(result['status'],'passed',result)
        self.assertEqual(len(self.worker.calls),1)
        for name,text in self.files.items():self.assertEqual((self.root/name).read_bytes(),text.encode())

    def test_operator_change_after_partial_integration_preserved(self):
        grant=self.grant();integrate=self.c.integrate;written=[]
        def interrupted(changes):
            name=next(iter(changes));written.append(name);integrate({name:changes[name]})
            raise KeyboardInterrupt()
        self.c.integrate=interrupted
        with self.assertRaises(KeyboardInterrupt):self.c.execute(grant,'groom-spec','partial')
        path=self.root/written[0];path.write_text('operator content\n')
        resumed=m.Operations(self.root,'demo',self.invoke)
        with self.assertRaisesRegex(ValueError,'checkpoint_inputs_changed'):
            resumed.execute(grant,'groom-spec','partial')
        self.assertEqual(path.read_text(),'operator content\n')
        self.assertEqual(len(self.worker.calls),1)

    def test_crlf_draft_and_existing_mode_preserved(self):
        name='docs/left/SPEC.md';path=self.root/name;path.parent.mkdir(parents=True)
        path.write_bytes(b'Old draft\n');path.chmod(0o640)
        self.files[name]='Return two with retained CRLF.\r\n'
        result=self.c.execute(self.grant(),'groom-spec','crlf')
        self.assertEqual(result['status'],'passed',result)
        self.assertEqual(path.read_bytes(),self.files[name].encode())
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o640)

    def test_template_change_after_authorization_blocks_without_call(self):
        grant=self.grant();path=self.root/'package-template.json';value=json.loads(path.read_text())
        value['aggregate']['calls']=7;path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):self.c.execute(grant,'groom-spec','changed-template')
        self.assertEqual(self.worker.calls,[])

    def test_source_scope_escape_rejected_with_consistent_child_graph(self):
        files=copy.deepcopy(self.files)
        child=json.loads(files['docs/left/operations.json']);child['scope']=['app.py'];files['docs/left/operations.json']=json.dumps(child)
        graph=json.loads(files['graph.json']);graph['children'][0]['writes']=['app.py'];graph['children'][0]['interfaces'][0]['path']='app.py'
        graph['children'][-1]['reads'].remove('left.py');graph['children'][-1]['reads'].append('app.py');files['graph.json']=json.dumps(graph)
        with self.assertRaisesRegex(ValueError,'package_draft_source_scope_expanded'):self.candidate(files)
        self.assertFalse((self.root/'docs/left').exists())

    def test_external_artifact_or_noncanonical_inventory_rejected(self):
        for name in ('routing.json','docs/left/../right/SPEC.md','operator.py'):
            with self.subTest(name=name):
                files=copy.deepcopy(self.files);files[name]='unapproved\n'
                with self.assertRaisesRegex(ValueError,'package_draft_outside_inventory'):self.candidate(files)

    def test_noop_or_missing_artifact_cannot_pass(self):
        for missing in (None,'docs/right/checks.py'):
            with self.subTest(missing=missing):
                files=copy.deepcopy(self.files) if missing else {}
                if missing:files.pop(missing)
                with self.assertRaisesRegex(ValueError,'package_draft_output_missing'):self.candidate(files)

    def worker_recovery(self, invalid):
        if invalid:
            graph=json.loads(self.files['graph.json']);graph['aggregate']['calls']=33
            self.files['graph.json']=json.dumps(graph)+'\n'
        grant=self.grant()
        def interrupted(*args):raise KeyboardInterrupt('worker completed before candidate validation')
        self.c.patch=interrupted
        with self.assertRaises(KeyboardInterrupt):self.c.execute(grant,'groom-spec','worker-recovery')
        self.assertFalse((self.root/'docs/left').exists())
        self.assertEqual(len(self.worker.calls),1)
        resumed=m.Operations(self.root,'demo',self.invoke)
        result=resumed.execute(grant,'groom-spec','worker-recovery')
        self.assertEqual(result['status'],'failed' if invalid else 'passed',result)
        self.assertEqual(len(self.worker.calls),1)
        if invalid:
            self.assertIn('package_draft_allowance_expanded',result['reason'])
            self.assertFalse((self.root/'docs/left').exists())

    def test_completed_worker_recovery_validates_before_integration(self):
        self.worker_recovery(True)

    def test_completed_worker_recovery_reuses_call(self):
        self.worker_recovery(False)

    def test_invalid_generated_check_has_no_parent_writes(self):
        self.files['docs/left/checks.py']='def invalid(:\n'
        result=self.c.execute(self.grant(),'groom-spec','syntax')
        self.assertEqual(result['status'],'failed',result)
        self.assertIn('syntax',result['reason'])
        self.assertFalse((self.root/'docs/left').exists())
        self.assertEqual(len(self.worker.calls),1)

    def test_output_byte_limit_and_declared_hash_enforced(self):
        files=copy.deepcopy(self.files);files['docs/left/SPEC.md']='x'*65536
        with self.assertRaisesRegex(ValueError,'package_draft_outputs_too_large'):self.candidate(files)
        with self.assertRaisesRegex(ValueError,'package_draft_content_hash_mismatch'):
            m.load('package-draft').validate_candidate(self.c,self.plan,{'graph.json':dict(text='{}',after='wrong',before=None)})

if __name__=='__main__':unittest.main()
