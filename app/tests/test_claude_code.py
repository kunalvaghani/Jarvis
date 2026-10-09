import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from jarvis.claude_code_guard import decide
from jarvis.claude_code import environment, event_progress
from jarvis.coder import Coder
from jarvis.claude_code_permissions import approve


class ClaudeCode(unittest.TestCase):
    def test_coding_with_email_or_github_in_spec_reaches_coder(self):
        from jarvis.brain import Brain
        from jarvis.coder import explicit_coding_intent
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            brain=Brain.__new__(Brain)
            brain.visual_fallback=SimpleNamespace(last_saved=None)
            brain.options={'enabled':True}
            brain.actions=SimpleNamespace(_task_folder=Mock(return_value=root))
            brain.client=SimpleNamespace(options={'coding_backend':'claude-code'})
            for goal in ('create a website with an email contact form', 'build a React app using the GitHub API', 'modify main.py to add a calendar UI'):
                with patch('jarvis.coder.Coder.run',return_value='done') as run:
                    self.assertEqual(brain._run(goal,lambda:False),'done')
                    run.assert_called_once()
                    self.assertEqual(run.call_args.args[1],goal)
            for goal in ('write an email introducing me', 'create GitHub repository', 'read notes.txt and draft tests for it', 'write a pull request description for my React app', 'create a calendar event for the Java app release'):
                self.assertFalse(explicit_coding_intent(goal))

    def test_folder_priority_and_absolute_file_scope(self):
        from jarvis.coder import coding_folder, named_folder_request
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);prior=root/'old';prior.mkdir();current=root/'new';current.mkdir()
            actions=SimpleNamespace(_task_folder=Mock(return_value=current))
            self.assertEqual(coding_folder(actions,'create a React app',lambda:False,{'project':str(prior)}),current)
            actions._task_folder.assert_called_with('this folder',unittest.mock.ANY)
            goal='edit "'+str(prior/'main.cpp')+'" to add UI'
            self.assertEqual(named_folder_request(goal),str(prior))
            self.assertEqual(named_folder_request('add UI to "'+str(prior/'main.cpp')+'"'),str(prior))
            coding_folder(actions,goal,lambda:False,{'project':str(current)})
            actions._task_folder.assert_called_with(str(prior),unittest.mock.ANY)
            actions._task_folder.side_effect=ValueError('No open folder')
            self.assertEqual(coding_folder(actions,'add UI to main.cpp',lambda:False,{'project':str(prior)}),str(prior))
            with self.assertRaises(ValueError):coding_folder(actions,'add UI',lambda:True,{'project':str(prior)})
            self.assertEqual(named_folder_request('create app in this folder'),'this folder')

    def test_python_shortcut_uses_cli_without_legacy_template(self):
        from jarvis.coder import create_python_from_goal
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            actions=SimpleNamespace(_task_folder=Mock(return_value=root))
            client=SimpleNamespace(options={'coding_backend':'claude-code'})
            with patch('jarvis.claude_code.run',return_value='done') as run:
                self.assertEqual(create_python_from_goal(actions,client,'create Python calculator', 'calculator.py',lambda:False),'done')
                self.assertIn('calculator.py',run.call_args.args[2])
                self.assertFalse((root/'calculator.py').exists())

    def test_stop_and_failed_bridge_close_owned_tree_without_replay(self):
        import io
        from jarvis.claude_code import run
        for mode in ('stop','bridge','proxy','timeout'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'project';root.mkdir()
                events=[];stop=[False]
                def report(kind,value):
                    events.append((kind,value))
                coder=SimpleNamespace(actions=SimpleNamespace(base=Path(folder),report=report),client=SimpleNamespace(options={}))
                response=Mock();response.json.return_value={'capabilities':['tools']}
                http=Mock();http.post.return_value=response
                process=Mock(stdin=io.StringIO(),stdout=io.StringIO(json.dumps({'type':'system','subtype':'init','mcp_servers':[{'name':'jarvis_guard','status':'failed'}]})+'\n'))
                process.poll.return_value=None
                if mode=='stop':process.stdin=Mock(write=Mock(side_effect=lambda value:stop.__setitem__(0,True)))
                job=Mock()
                proxy=Mock();proxy.poll.return_value=None
                if mode=='proxy':proxy.poll.return_value=1
                def launch(argv,**kw):
                    if 'jarvis.claude_code_proxy' in argv:
                        if mode!='proxy':(Path(argv[-1])/'proxy-ready.json').write_text('{"port":12345}')
                        return proxy
                    return process
                from contextlib import nullcontext
                clock=patch('jarvis.claude_code.time.monotonic',side_effect=[0,0,1801]) if mode=='timeout' else nullcontext()
                with clock,patch('jarvis.claude_code.executable',return_value='claude.exe'),patch('jarvis.knowledge_worker.session') as session,patch('jarvis.claude_code.OwnedJob',return_value=job),patch('jarvis.claude_code.hidden_spawn',return_value=launch) as spawn:
                    session.return_value.__enter__.return_value=http
                    with self.assertRaisesRegex(ValueError,{'stop':'stopped','bridge':'bridge','proxy':'adapter','timeout':'limit'}[mode]):
                        run(coder,root,'create main.py',lambda:stop[0])
                    self.assertEqual(spawn.call_count,1 if mode=='proxy' else 2)
                    job.close.assert_called_once()
                    if mode=='proxy':process.terminate.assert_not_called();proxy.terminate.assert_not_called()
                    else:process.terminate.assert_called_once();proxy.terminate.assert_called_once()
                failures=list((Path(folder)/'.jarvis-runtime/claude-code').glob('*/failure.json'))
                self.assertEqual(len(failures),1)
                self.assertFalse(json.loads(failures[0].read_text())['automatically_replayed'])
                self.assertFalse(events[-1][1]['active'])
                self.assertEqual(list(root.iterdir()),[])

    def test_local_adapter_disables_thinking_and_never_forwards_cloud_routes(self):
        from jarvis.claude_code_proxy import prepare
        payload={'model':'qwen3.5:9b','max_tokens':32000,'thinking':{'type':'adaptive'},'output_config':{'effort':'low'}}
        route,body=prepare('/v1/messages?beta=true',payload)
        self.assertEqual(route,'/v1/messages');self.assertEqual(body['thinking'],{'type':'disabled'})
        self.assertNotIn('effort',body['output_config']);self.assertEqual(payload['thinking'],{'type':'adaptive'})
        self.assertEqual(body['max_tokens'],6000)
        for path,request in [('/v1/web_search',payload),('/v1/messages',{'model':'claude-sonnet-5'})]:
            with self.assertRaises(ValueError):prepare(path,request)

    def test_scope_and_original_edit_checks(self):
        from jarvis.claude_code_guard import gui_script_target
        self.assertTrue(gui_script_target('add UI to main.py',Path('main.py')))
        self.assertFalse(gui_script_target('add UI to domain.py',Path('main.py')))
        self.assertFalse(gui_script_target('split GUI across main.py and view.py',Path('main.py')))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'main.py';target.write_text('x=1\n')
            path,source=decide(root,'Edit',{'file_path':'main.py','old_string':'x=1','new_string':'x=2'})
            self.assertEqual(source,'x=2\n');self.assertEqual(target.read_text(),'x=1\n')
            for tool,args in [('Bash',{'command':'del main.py'}),('Write',{'file_path':'../other.py','content':'x=1'}),
                ('Write',{'file_path':'.env','content':'key=123'}),('Write',{'file_path':'main.py','content':'x = '}),
                ('Edit',{'file_path':'main.py','old_string':'missing','new_string':'x=2'}),('Glob',{'pattern':'../*'})]:
                with self.subTest(tool=tool,args=args),self.assertRaises(ValueError):decide(root,tool,args)

    def test_credentials_and_paid_providers_do_not_leak_into_child(self):
        with patch.dict('os.environ',{'ANTHROPIC_API_KEY':'private','ANTHROPIC_BASE_URL':'https://api.anthropic.com',
            'CLAUDE_CODE_USE_BEDROCK':'1','AZURE_SECRET':'private','API_TIMEOUT_MS':'1000','CLAUDE_STREAM_IDLE_TIMEOUT_MS':'1000','API_FORCE_IDLE_TIMEOUT':'1'}):
            env=environment(Path('project'),Path('run'),'qwen3.5:9b')
        self.assertEqual(env['ANTHROPIC_BASE_URL'],'http://127.0.0.1:11434')
        self.assertEqual(env['ANTHROPIC_API_KEY'],'')
        self.assertEqual(env['ANTHROPIC_AUTH_TOKEN'],'ollama')
        self.assertNotIn('CLAUDE_CODE_USE_BEDROCK',env)
        self.assertNotIn('AZURE_SECRET',env)
        self.assertEqual(env['API_TIMEOUT_MS'],'1800000')
        self.assertEqual(env['CLAUDE_STREAM_IDLE_TIMEOUT_MS'],'1800000')
        self.assertEqual(env['CLAUDE_BYTE_STREAM_IDLE_TIMEOUT_MS'],'1800000')
        self.assertEqual(env['API_FORCE_IDLE_TIMEOUT'],'0')

    def test_permission_bridge_preserves_backups_and_blocks_concurrent_rewrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();run=Path(folder)/'run';run.mkdir()
            path=root/'main.py';path.write_text('x=1\n')
            backup=run/'originals/main.py';backup.parent.mkdir();backup.write_bytes(path.read_bytes())
            with patch.dict('os.environ',{'JARVIS_CLAUDE_PROJECT':str(root),'JARVIS_CLAUDE_RUN':str(run)}):
                result=approve('Edit',{'file_path':'main.py','old_string':'x=1','new_string':'x=2'})
                self.assertEqual(result['behavior'],'allow')
                self.assertEqual(backup.read_text(),'x=1\n')
                path.write_text('x=3\n')
                self.assertEqual(approve('Write',{'file_path':'main.py','content':'x=2\n'})['behavior'],'deny')
                self.assertEqual(approve('Write',{'file_path':'../outside.py','content':'x=1'})['behavior'],'deny')
                self.assertEqual(approve('Bash',{'command':'echo hi'})['behavior'],'deny')
                path.write_text('x=1\n')
                edit={'file_path':'main.py','old_string':'1','new_string':'12'}
                self.assertEqual(approve('Edit',edit)['behavior'],'allow')
                path.write_text('x=12\n')
                self.assertEqual(approve('Edit',edit)['behavior'],'deny')
                (run/'request.json').write_text(json.dumps({'goal':'add UI to main.py'}))
                self.assertEqual(approve('Write',{'file_path':'main.py','content':'print(5)\n'})['behavior'],'deny')
                self.assertEqual(approve('Write',{'file_path':'helper.py','content':'x=1\n'})['behavior'],'allow')
                path.write_text('def add(a,b): return a+b\n')
                self.assertEqual(approve('Edit',{'file_path':'main.py','old_string':'def add(a,b): return a+b','new_string':'x=1'})['behavior'],'deny')

    def test_only_visible_text_and_tool_activity_reach_island(self):
        rows=[];report=lambda *a:rows.append(a);pending={}
        event_progress({'type':'stream_event','event':{'delta':{'type':'thinking_delta','thinking':'hidden'}}},report,Path('project'),pending)
        self.assertEqual(rows,[])
        event_progress({'type':'assistant','message':{'content':[{'type':'tool_use','id':'1','name':'Write','input':{'file_path':'main.py','content':'x=1'}}]}},report,Path('project'),pending)
        event_progress({'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'1','is_error':False}]}},report,Path('project'),pending)
        self.assertEqual(rows[0][1]['file'],'main.py')
        self.assertIn('completed',rows[-1][1]['phase'])
        event_progress({'type':'stream_event','event':{'delta':{'type':'text_delta','text':'ok\udc8d'}}},report,Path('project'),pending)
        rows[-1][1]['preview'].encode('utf-8')
        self.assertIn('ok',rows[-1][1]['preview'])

    def test_completion_requires_approved_source_and_matching_disk_bytes(self):
        import io,hashlib
        from jarvis.claude_code import run
        for mode in ('approved','unapproved','diverged'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'project';root.mkdir();path=root/'main.py';path.write_text('x=1\n')
                coder=SimpleNamespace(actions=SimpleNamespace(base=Path(folder),report=Mock()),client=SimpleNamespace(options={}))
                response=Mock();response.json.return_value={'capabilities':['tools']}
                http=Mock();http.post.return_value=response
                records=[{'type':'system','subtype':'init','mcp_servers':[{'name':'jarvis_guard','status':'connected'}]},
                         {'type':'result','is_error':False,'result':'Edited main.py'}]
                process=Mock(stdin=io.StringIO(),stdout=io.StringIO(''.join(json.dumps(r)+'\n' for r in records)),returncode=0)
                process.poll.return_value=0
                proxy=Mock();proxy.poll.return_value=0
                directory=[None]
                def launch(argv,**kw):
                    if 'jarvis.claude_code_proxy' in argv:
                        directory[0]=Path(argv[-1]);(directory[0]/'proxy-ready.json').write_text('{"port":12345}')
                        return proxy
                    path.write_text('x=3\n' if mode=='diverged' else 'x=2\n')
                    if mode!='unapproved':
                        (directory[0]/'file-events.jsonl').write_text(json.dumps({'tool':'Edit','path':str(path),'approved':True,
                            'observed_sha256':hashlib.sha256(b'x=1\n').hexdigest(),'proposed_sha256':hashlib.sha256(b'x=2\n').hexdigest()})+'\n')
                    return process
                with patch('jarvis.claude_code.executable',return_value='claude.exe'),patch('jarvis.knowledge_worker.session') as session,patch('jarvis.claude_code.OwnedJob'),patch('jarvis.claude_code.hidden_spawn',return_value=launch):
                    session.return_value.__enter__.return_value=http
                    if mode=='approved':self.assertIn('updated project: main.py',run(coder,root,'edit main.py',lambda:False))
                    else:
                        with self.assertRaisesRegex(ValueError,'without changing' if mode=='unapproved' else 'differs from'):
                            run(coder,root,'edit main.py',lambda:False)

    def test_coder_dispatch_retains_folder_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'demo';root.mkdir()
            coder=Coder(SimpleNamespace(),SimpleNamespace(options={'coding_backend':'claude-code'}))
            with patch('jarvis.claude_code.run',return_value='done') as run:
                self.assertEqual(coder.run(root,'create a C# app',selected=True),'done')
                run.assert_called_once()
                with self.assertRaises(ValueError):coder.run(root,'create a C# app in other folder with UI',selected=True)
                self.assertEqual(coder.run(root,'create C# app in "'+str(root)+'"',selected=True),'done')
                folder_coder=Coder(Mock(),SimpleNamespace(options={'coding_backend':'claude-code'}))
                self.assertIn('Tools',folder_coder.run(root,'create a folder named Tools',selected=True))
                self.assertTrue((root/'Tools').is_dir())
                self.assertEqual(run.call_count,2)
                goal='Create a React website. '+('Preserve this explicit requirement. '*60)
                self.assertEqual(coder.run(root,goal,selected=True),'done')
                self.assertEqual(run.call_args.args[2],goal)
                with self.assertRaises(ValueError):coder.run(root,'Create app '+('x'*6000),selected=True)


if __name__=='__main__':unittest.main()
