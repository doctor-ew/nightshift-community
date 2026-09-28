#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('chat', ROOT / 'scripts/nightshift-console-chat.py')
chat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat)

class ChatTests(unittest.TestCase):
    def test_route_no_fallback_and_policy(self):
        routing = {'roles': {'nightshift-engineer': {'gears': {'1': {'provider':'codex','model':'sol'}, '2':{'provider':'claude','model':'sonnet'}}}}, 'local':{'model':'qwen'}}
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            chat.route(routing,'auto','standard')
        self.assertEqual(chat.route(routing,'auto','claude-only')['provider'],'claude')
        self.assertEqual(chat.route(routing,'local','standard')['model'],'qwen')
        with self.assertRaisesRegex(ValueError,'policy'):
            chat.route(routing,'local','claude-only')

    def test_citations_fail_closed(self):
        sources = [dict(source_id='S1',path='SPEC.md')]
        self.assertEqual(chat.validate_answer({'answer':'Draft exists [S1]','sources':['S1']},sources)['citations'],sources)
        for refs in ([],['S99'],[{}]):
            with self.assertRaises(ValueError):
                chat.validate_answer({'answer':'answer','sources':refs},sources)

    def test_evidence_omits_private_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d).resolve(); docs=target/'docs/ticket'; docs.mkdir(parents=True)
            (docs/'SPEC.md').write_text('public draft')
            (docs/'heldout.json').write_text('PRIVATE')
            (docs/'BLOCKED.md').symlink_to(docs/'heldout.json')
            text,sources=chat.bundle(target,'ticket')
            self.assertIn('1: public draft',text)
            self.assertNotIn('PRIVATE',text)
            self.assertEqual(len(sources),1)

    def test_worker_persists_answer_and_failure(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d).resolve(); (target/'routing.json').write_text('{}'); path=target/'chat.json'
            initial=dict(messages=[dict(role='user',content='why?')],running=True,phase='answering',provider='claude',model='sonnet',_target=d)
            with patch.object(chat.actions,'state',return_value={}),patch.object(chat,'module') as module_mock,patch.object(chat,'location',return_value=path),patch.object(chat,'bundle',return_value=('public', [dict(source_id='S1',path='SPEC.md')])):
                module_mock.return_value.progress.return_value = {}
                path.write_text(json.dumps(initial))
                with patch.object(chat,'claude_call',return_value={'answer':'draft [S1]','sources':['S1']}):
                    chat.worker(d,'ticket')
                result=json.loads(path.read_text());self.assertFalse(result['running']);self.assertEqual(result['phase'],'complete');self.assertNotIn('_target',result)
                path.write_text(json.dumps(initial))
                with patch.object(chat,'claude_call',side_effect=ValueError('provider failed')):
                    chat.worker(d,'ticket')
                self.assertEqual(json.loads(path.read_text())['phase'],'failed')

    def test_external_routing_without_consumer_routing_file(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve(); target=root/'consumer'; target.mkdir()
            metadata=root/'console'; metadata.mkdir(); (root/'worktrees').mkdir()
            (root/'worktrees/ticket.json').write_text(json.dumps({'worktree':str(target)}))
            routing=root/'profile.json'
            routing.write_text(json.dumps({'roles':{'nightshift-engineer':{'gears':{'1':{'provider':'claude','model':'opus'}}}}}))
            saved={'sha256':'version','settings':{'auth':'subscription','policy':'standard'}}
            child=SimpleNamespace(pid=42,wait=lambda:0)
            with patch.dict(os.environ, NIGHTSHIFT_ROUTING_FILE=str(routing)), patch.object(chat.actions,'state',return_value=saved), patch.object(chat.actions,'directory',return_value=metadata), patch.object(chat.subprocess,'Popen',return_value=child), patch.object(chat.subprocess,'check_output',return_value='identity'):
                result=chat.start(root,'ticket','version','auto','What is happening?')
            self.assertEqual(result['model'],'opus')
            self.assertFalse((target/'routing.json').exists())
            self.assertNotIn('_routing',result)
            # Child uses the admitted configuration even if its environment differs.
            with patch.dict(os.environ, NIGHTSHIFT_ROUTING_FILE=str(root/'missing.json')), patch.object(chat.actions,'state',return_value=saved), patch.object(chat.actions,'directory',return_value=metadata), patch.object(chat,'module') as modules, patch.object(chat,'bundle',return_value=('public',[{'source_id':'S1'}])), patch.object(chat,'claude_call',return_value={'answer':'Evidence [S1]','sources':['S1']}):
                modules.return_value.progress.return_value={}
                chat.worker(root,'ticket')
            persisted=json.loads((metadata/'ticket.chat.json').read_text())
            self.assertEqual(persisted['phase'],'complete')
            self.assertNotIn('_routing',persisted)

    def test_claude_tools_disabled(self):
        class Process:
            returncode=0
            def communicate(self,*args,**kwargs): return ('{"structured_output":{"answer":"x","sources":["S1"]}}','')
        from types import SimpleNamespace
        login=SimpleNamespace(returncode=0,stdout=json.dumps(dict(loggedIn=True,authMethod='claude.ai',apiProvider='firstParty')))
        with patch.object(chat.subprocess,'run',return_value=login),patch.object(chat.subprocess,'Popen',return_value=Process()) as launch:
            chat.claude_call('sonnet','question')
        argv=launch.call_args.args[0]
        self.assertEqual(argv[argv.index('--tools')+1],'')
        self.assertIn('--safe-mode',argv);self.assertIn('--strict-mcp-config',argv)
        self.assertEqual(argv[argv.index('--mcp-config')+1],'{"mcpServers":{}}')
        self.assertNotIn('ANTHROPIC_API_KEY',launch.call_args.kwargs['env'])

    def test_local_nonloopback_rejected(self):
        for url in ('https://example.com/v1','http://user@localhost/v1','http://localhost/v1?key=foo'):
            with self.assertRaises(ValueError): chat.local_call({'backend':'omlx','base_url':url},'qwen','question')

    def test_old_live_worker_keeps_slot(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d).resolve()/'chat.json'
            path.write_text(json.dumps(dict(messages=[],running=True,phase='answering',pid=42,pid_started='identity',started_at=0)))
            with patch.object(chat,'location',return_value=path),patch.object(chat.subprocess,'check_output',side_effect=['python nightshift-console-chat.py ticket','identity']):
                self.assertTrue(chat.state(d,'ticket')['running'])

    def test_safe_text_rejects_symlink_ancestors_and_nonfiles(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve(); (root/'real').mkdir(); (root/'real/a').write_text('public')
            (root/'link').symlink_to(root/'real',target_is_directory=True)
            self.assertEqual(chat.safe_text(root/'real/a',3),'pub')
            with self.assertRaises(OSError): chat.safe_text(root/'link/a')
            with self.assertRaises((OSError,ValueError)): chat.safe_text(root/'real')

    def test_local_backend_endpoint_is_explicit(self):
        class Opener:
            def open(self,request,timeout):
                self.url=request.full_url
                self.body=json.loads(request.data)
                raise RuntimeError('captured')
        for backend,port in [('omlx',8000),('ollama',11434),('lmstudio',1234)]:
            opener=Opener()
            with patch.object(chat.urllib.request,'build_opener',return_value=opener):
                with self.assertRaisesRegex(RuntimeError,'captured'):
                    chat.local_call({'backend':backend},'model','question')
            self.assertEqual(opener.url,f'http://127.0.0.1:{port}/v1/chat/completions')
            self.assertEqual(opener.body['response_format']['json_schema']['schema'],chat.SCHEMA)
            self.assertNotIn('tools',opener.body)
        for config in ({},{'backend':'unknown'},{'backend':'openai-compatible'}):
            with self.assertRaises(ValueError): chat.local_call(config,'model','question')

if __name__=='__main__': unittest.main()
