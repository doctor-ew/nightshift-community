#!/usr/bin/env python3
"""Independent active-preparation composition-window nonrenewal checks."""
import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('composition_window_fixture',Path(__file__).with_name('test-package-wall-review.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
m=f.m

class CompositionWindowReview(unittest.TestCase):
    setUp=f.WallReview.setUp
    grant=f.WallReview.grant
    prepare_with_validation_time=f.WallReview.prepare_with_validation_time

    def test_operator_identity_change_cannot_refresh_same_binding(self):
        _,ready=self.prepare_with_validation_time(2)
        first=self.c.authorize(ready['binding'],'first-operator','first-request')
        self.now+=30
        second=self.c.authorize(ready['binding'],'second-operator','second-request')
        self.assertEqual(second['binding'],first['binding'])
        self.assertNotEqual(second['id'],first['id'])
        self.assertEqual(second['deadline'],first['deadline'])
        self.assertEqual(len(self.worker.calls),2)

    def test_expired_original_window_blocks_new_operator_after_restart(self):
        _,ready=self.prepare_with_validation_time(2)
        first=self.c.authorize(ready['binding'],'first-operator','first-request')
        self.now=first['deadline']+1
        resumed=m.Packages(self.root,'demo',self.worker,self.clock)
        stopped=resumed.run(first['id'])
        self.assertEqual(stopped['status'],'blocked',stopped)
        self.assertEqual(stopped['reason'],'parent_deadline_exhausted')
        retained=resumed.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'parent_composition_wall_exhausted'):
            resumed.authorize(ready['binding'],'second-operator','new-request')
        self.assertEqual(resumed.path.read_bytes(),retained)
        self.assertEqual(set(resumed.state['authorizations']),{first['id']})
        self.assertFalse(resumed.state['children'])
        self.assertEqual(len(self.worker.calls),2)

    def test_idle_before_first_composition_still_excluded_from_active_preparation(self):
        prep,ready=self.prepare_with_validation_time(2)
        self.now+=10000
        resumed=m.Packages(self.root,'demo',self.worker,self.clock)
        replay=resumed.prepare(prep)
        self.assertEqual(replay['binding'],ready['binding'])
        first=resumed.authorize(replay['binding'],'synthetic','first-after-idle')
        self.assertEqual(first['deadline'],self.now+236)
        self.assertEqual(first['preparation_wall']['elapsed_seconds'],4)
        self.assertEqual(len(self.worker.calls),2)

    def revise_graph(self, wall, request):
        path=self.root/'graph.json';graph=json.loads(path.read_text())
        graph['aggregate']['wall_seconds']=wall;path.write_text(json.dumps(graph))
        prep=self.c.preparation;assessed=prep.assess('groom-spec')
        grant=prep.authorize(m.ops.RECIPES['groom'],assessed['binding'],'synthetic-'+request,request)['id']
        ready=self.c.prepare(grant)
        self.assertEqual(ready['status'],'ready',ready)
        return ready

    def test_changed_binding_narrows_then_expands_without_renewing_retained_window(self):
        _,ready=self.prepare_with_validation_time(2)
        first=self.c.authorize(ready['binding'],'first-operator','first')
        self.now+=6
        narrow=self.revise_graph(190,'prepare-narrow')
        second=self.c.authorize(narrow['binding'],'second-operator','second')
        self.assertNotEqual(second['binding'],first['binding'])
        self.assertLess(second['deadline'],first['deadline'])
        self.now+=10
        self.c=m.Packages(self.root,'demo',self.worker,self.clock)
        expanded=self.revise_graph(240,'prepare-expanded')
        third=self.c.authorize(expanded['binding'],'third-operator','third')
        self.assertNotEqual(third['binding'],second['binding'])
        self.assertEqual(third['deadline'],second['deadline'])
        self.assertFalse(self.c.state['children'])
        self.assertEqual(len(self.worker.calls),6)

if __name__=='__main__':unittest.main()
