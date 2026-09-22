#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('decisions', ROOT/'scripts/nightshift-console-decisions.py')
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)


class Decisions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        subprocess.run(['git','init','-q',str(self.project)],check=True)
        self.question = dict(question='Which export format?',reason='The brief leaves the export format open.',options=[dict(id='markdown',label='Markdown',description='Portable plain text'),dict(id='pdf',label='PDF',description='Fixed layout')])

    def test_choice_free_text_and_idempotent_answer(self):
        q=d.request(self.project,'task',self.question)
        self.assertEqual(d.request(self.project,'task',self.question),q)
        with self.assertRaises(ValueError): d.respond(self.project,'task','stale','markdown','')
        with self.assertRaises(ValueError): d.respond(self.project,'task',q['sha256'],'shell','')
        with self.assertRaises(ValueError): d.respond(self.project,'task',q['sha256'],'','')
        result=d.respond(self.project,'task',q['sha256'],'markdown','Keep citations separate.')
        self.assertEqual(d.respond(self.project,'task',q['sha256'],'markdown','Keep citations separate.'),result)
        with self.assertRaises(ValueError): d.respond(self.project,'task',q['sha256'],'pdf','')
        self.assertFalse(d.snapshot(self.project,'task')['pending'])
        self.assertEqual(len(d.snapshot(self.project,'task')['answered']),1)
        q2=d.request(self.project,'task',dict(self.question,question='Which audience?'))
        answer=d.respond(self.project,'task',q2['sha256'],'','Job seekers at the event.')
        self.assertEqual(answer['response']['answer'],'Job seekers at the event.')
        self.assertEqual(len(d.snapshot(self.project,'task')['answered']),2)

    def test_pending_question_and_path_protection(self):
        d.request(self.project,'task',self.question)
        with self.assertRaises(ValueError): d.request(self.project,'task',dict(self.question,question='Different question'))
        with self.assertRaises(ValueError): d.snapshot(self.project,'../escape')
        external=self.project/'outside';external.write_text('untouched')
        p=d.location(self.project,'symlink');p.symlink_to(external)
        with self.assertRaises(ValueError): d.request(self.project,'symlink',self.question)
        self.assertEqual(external.read_text(),'untouched')

    def test_invalid_options_and_bounds(self):
        for options in [[dict(id='x',label='X',description='x')]*2, [dict(id=str(n),label='X',description='x') for n in range(4)]]:
            with self.assertRaises(ValueError):d.request(self.project,'task',dict(self.question,options=options))
        q=d.request(self.project,'task',self.question)
        with self.assertRaises(ValueError):d.respond(self.project,'task',q['sha256'],'','x'*4001)
        self.assertEqual(len(d.snapshot(self.project,'task')['pending']),1)

    def test_old_answer_rejected_and_repeat_question_gets_new_occurrence(self):
        first=d.request(self.project,'task',self.question)
        d.respond(self.project,'task',first['sha256'],'markdown','')
        second=d.request(self.project,'task',self.question)
        self.assertNotEqual(first['sha256'],second['sha256'])
        self.assertEqual(d.request(self.project,'task',self.question),second)
        with self.assertRaises(ValueError):d.respond(self.project,'task',first['sha256'],'markdown','')
        child=d.request(self.project,'child',self.question)
        self.assertNotEqual(first['sha256'],child['sha256'])

    def queued(self, target='task', operation='resume', provider='auto'):
        question=d.request(self.project,target,dict(self.question,continuation=operation,provider=provider))
        current=dict(sha256='settings',finished=False,running=True,decisions=dict(pending=[question],answered=[]))
        actions=SimpleNamespace(state=lambda *args:current)
        with patch.object(d,'actions_module',return_value=actions), patch.object(d,'spawn_watcher',return_value=SimpleNamespace(pid=123)), patch.object(d,'process_identity',return_value='identity'):
            result=d.submit(self.project,'parent','settings',question['sha256'],'markdown','')
        return question,result

    def test_child_answer_routes_to_child_and_queues_parent_continuation(self):
        question,result=self.queued('child')
        self.assertEqual(result['status'],'queued')
        item=d.read(d.location(self.project,'child'))['requests'][0]
        self.assertEqual(item['response']['choice'],'markdown')
        self.assertEqual(item['continuation']['parent_task'],'parent')
        self.assertFalse(d.snapshot(self.project,'parent')['answered'])
        current=dict(sha256='settings',finished=False,running=True,decisions=dict(pending=[],answered=[item]))
        with patch.object(d,'actions_module',return_value=SimpleNamespace(state=lambda *args:current)),patch.object(d,'process_identity',return_value='identity'),patch.object(d,'spawn_watcher') as spawn:
            self.assertEqual(d.submit(self.project,'parent','settings',question['sha256'],'markdown','')['status'],'queued')
            spawn.assert_not_called()

    def test_watcher_waits_for_exit_and_handles_launch_race(self):
        question,result=self.queued(operation='repair',provider='claude')
        item=result['decision'];calls=[];polls=[True,False,False]
        def state(*args):
            return dict(sha256='settings',finished=False,running=polls.pop(0),decisions=dict(pending=[],answered=[item]))
        def action(*args):
            calls.append(args)
            return dict(launched=len(calls)>1,status='running',message='launched' if len(calls)>1 else 'already active')
        sleeps=[]
        code=d.continue_answer(self.project,'task',question['sha256'],item['continuation']['token'],sleep=lambda n:sleeps.append(n),actions=SimpleNamespace(state=state,action=action))
        self.assertEqual(code,0);self.assertEqual(len(sleeps),2)
        self.assertEqual(calls[-1][1:],('parent','settings','repair','claude'))
        self.assertEqual(d.read(d.location(self.project,'task'))['requests'][0]['continuation']['status'],'resumed')

    def test_watcher_rejects_stale_settings_new_pending_and_timeout(self):
        for reason in ('settings','pending','timeout'):
            with self.subTest(reason=reason):
                task='task-'+reason;question,result=self.queued(task)
                item=result['decision']
                state=dict(sha256='different' if reason=='settings' else 'settings',finished=False,running=False,decisions=dict(pending=[dict(sha256='new')] if reason=='pending' else [],answered=[item]))
                actions=SimpleNamespace(state=lambda *args:state,action=lambda *args:self.fail('must not launch'))
                now=(lambda:item['continuation']['deadline']+1) if reason=='timeout' else d.time.time
                self.assertEqual(d.continue_answer(self.project,task,question['sha256'],item['continuation']['token'],now=now,actions=actions,sleep=lambda n:self.fail('must not wait')),1)
                self.assertEqual(d.read(d.location(self.project,task))['requests'][0]['continuation']['status'],'blocked')

    def test_failed_spawn_retains_answer_for_identical_retry(self):
        question=d.request(self.project,'task',self.question)
        def state(*args):
            return dict(sha256='settings',finished=False,running=False,decisions=d.snapshot(self.project,'task'))
        with patch.object(d,'actions_module',return_value=SimpleNamespace(state=state)),patch.object(d,'spawn_watcher',side_effect=OSError('fixture failure')):
            self.assertEqual(d.submit(self.project,'task','settings',question['sha256'],'markdown','')['status'],'answer_saved')
        with patch.object(d,'actions_module',return_value=SimpleNamespace(state=state)),patch.object(d,'spawn_watcher',return_value=SimpleNamespace(pid=123)),patch.object(d,'process_identity',return_value='identity'):
            self.assertEqual(d.submit(self.project,'task','settings',question['sha256'],'markdown','')['status'],'queued')

    def test_dead_watcher_is_presented_as_retryable_without_rewriting_history(self):
        question,result=self.queued()
        path=d.location(self.project,'task');data=d.read(path)
        data['requests'][0]['continuation']['queued_at']=0;d.write(path,data)
        with patch.object(d,'watcher_alive',return_value=False):
            shown=d.snapshot(self.project,'task')['answered'][0]
        self.assertEqual(shown['continuation']['status'],'blocked')
        self.assertEqual(d.read(path)['requests'][0]['continuation']['status'],'queued')

    def test_action_requiring_new_decision_does_not_deadlock_or_claim_launch(self):
        question,result=self.queued();item=result['decision']
        state=dict(sha256='settings',finished=False,running=False,decisions=dict(pending=[],answered=[item]))
        def action(*args):
            d.request(self.project,'task',dict(self.question,question='A new question'))
            return dict(status='needs-decision',launched=False,message='New decision needed')
        actions=SimpleNamespace(state=lambda *args:state,action=action)
        self.assertEqual(d.continue_answer(self.project,'task',question['sha256'],item['continuation']['token'],actions=actions),1)
        record=d.read(d.location(self.project,'task'))
        self.assertEqual(record['requests'][0]['continuation']['status'],'blocked')
        self.assertIsNone(record['requests'][1]['response'])


if __name__ == '__main__': unittest.main()
