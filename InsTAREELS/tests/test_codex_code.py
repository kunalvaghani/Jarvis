import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.codex_code import MODEL, configuration, environment, event_progress, changed_sources
from jarvis.codex_files import execute, READS
from jarvis.codex_proxy import prepare, validate, restore, TOOLS


class CodexCode(unittest.TestCase):
    def test_isolated_settings_and_credential_scrub(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);run=root/'run';run.mkdir()
            with patch.dict(os.environ,{'OPENAI_API_KEY':'private','ANTHROPIC_AUTH_TOKEN':'private','CODEX_HOME':'old','OLLAMA_HOST':'https://example.com'}):
                env=environment(root,run)
            self.assertEqual(env['CODEX_HOME'],str(run/'home'))
            self.assertFalse(any(k in env for k in ('OPENAI_API_KEY','ANTHROPIC_AUTH_TOKEN','OLLAMA_HOST')))
            text=configuration(root,run,MODEL,12345)
            for expected in ('wire_api = "responses"','requires_openai_auth = false','sandbox_mode = "read-only"','shell_tool = false','plugins = false','request_max_retries = 0','stream_max_retries = 0','required = true'):
                self.assertIn(expected,text)
            self.assertNotIn('dangerously',text)

    def test_namespace_flattening_only_local_file_tools(self):
        tools=[{'type':'namespace','name':'mcp__jarvis_files','tools':[{'type':'function','name':'Read'},{'type':'function','name':'Write'},{'type':'function','name':'Shell'}]}, {'type':'custom','name':'apply_patch'}]
        value=prepare('/v1/responses',{'model':MODEL,'tools':tools,'reasoning':{'effort':'high'},'max_output_tokens':9000})
        self.assertEqual({t['name'] for t in value['tools']},{'mcp__jarvis_files__Read','mcp__jarvis_files__Write'})
        self.assertFalse(value['think']);self.assertFalse(value['parallel_tool_calls'])
        self.assertEqual(value['max_output_tokens'],6000);self.assertNotIn('reasoning',value)
        for payload in ({'model':'cloud','tools':tools},{'model':MODEL,'tools':[]},{'model':MODEL,'tools':tools,'previous_response_id':'old'}):
            with self.assertRaises(ValueError): prepare('/v1/responses',payload)
        with self.assertRaises(ValueError): prepare('/v1/chat/completions',{'model':MODEL,'tools':tools})
        with self.assertRaises(ValueError): validate({'type':'response.output_item.done','item':{'type':'function_call','name':'exec_command'}})
        with self.assertRaises(ValueError): validate({'type':'response.completed','response':{'output':[{'type':'custom_tool_call','name':'apply_patch'}]}})
        validate({'type':'response.output_item.done','item':{'type':'function_call','name':next(iter(TOOLS))}})
        event=restore({'type':'response.output_item.done','item':{'type':'function_call','name':'mcp__jarvis_files__Read','arguments':'{}','call_id':'call1'}})
        self.assertEqual(event['item']['name'],'Read');self.assertEqual(event['item']['namespace'],'mcp__jarvis_files')
        value=prepare('/v1/responses',{'model':MODEL,'tools':tools,'input':[event['item']]})
        self.assertEqual(value['input'][0]['name'],'mcp__jarvis_files__Read');self.assertNotIn('namespace',value['input'][0])

    def test_current_read_backups_exact_edits_and_uncertain_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();run=Path(folder)/'run';run.mkdir()
            (run/'request.json').write_text('{"goal":"modify main.py"}')
            source=root/'main.py';source.write_text('def add(a,b):\n    return a+b\n')
            READS.clear()
            with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(root),'JARVIS_CODEX_RUN':str(run)}):
                with self.assertRaisesRegex(ValueError,'Read'): execute('Write',{'file_path':'main.py','content':'def add(a,b):\n    return a+b\n'})
                execute('Read',{'file_path':'main.py'})
                source.write_text('def add(a,b):\n    return a+b # changed\n')
                with self.assertRaisesRegex(ValueError,'Read'): execute('Edit',{'file_path':'main.py','old_string':'a+b','new_string':'a-b'})
                original=source.read_bytes();execute('Read',{'file_path':'main.py'})
                self.assertEqual(execute('Glob',{'pattern':'**/*.py'})['files'],['main.py'])
                args={'file_path':'main.py','old_string':'return a+b # changed','new_string':'return a-b'}
                self.assertTrue(execute('Edit',args)['saved'])
                self.assertEqual((run/'originals/main.py').read_bytes(),original)
                self.assertIn('return a-b',source.read_text())
                # The checked save is fresh observed state for another exact edit.
                execute('Edit',{'file_path':'main.py','old_string':'return a-b','new_string':'return a-b # checked'})
                execute('Read',{'file_path':'main.py'})
                with self.assertRaises(ValueError): execute('Write',{'file_path':'../outside.py','content':'print(1)'})
                with self.assertRaises(ValueError): execute('Write',{'file_path':'.env','content':'secret'})
                with self.assertRaises(ValueError): execute('Write',{'file_path':'bad.js','content':'function broken( {'})
                # Returning the same original content externally cannot replay an attempted edit.
                source.write_bytes(original);execute('Read',{'file_path':'main.py'})
                with self.assertRaisesRegex(ValueError,'already attempted'): execute('Edit',args)
            rows=[json.loads(line) for line in (run/'file-events.jsonl').read_text().splitlines()]
            self.assertEqual([r['stage'] for r in rows],['attempted','applied','attempted','applied'])

    def test_only_applied_source_readback_credited(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'main.py';source.write_text('print(1)\n')
            run=root/'run';run.mkdir()
            self.assertEqual(changed_sources(root,run,'modify script'),[])
            row={'stage':'applied','path':str(source),'observed_sha256':None,'proposed_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
            (run/'file-events.jsonl').write_text(json.dumps(row)+'\n')
            self.assertEqual(changed_sources(root,run,'modify script'),['main.py'])
            source.write_text('print(2)\n')
            with self.assertRaisesRegex(ValueError,'changed'): changed_sources(root,run,'modify script')

    def test_visible_stream_progress_not_reasoning(self):
        report=Mock();pending={};project=Path('project')
        event_progress({'type':'response.reasoning_summary_text.delta','delta':'hidden'},report,project,pending)
        report.assert_not_called()
        event_progress({'type':'response.output_text.delta','delta':'Preparing controls'},report,project,pending)
        self.assertEqual(report.call_args.args[1]['preview'],'Preparing controls')
        event_progress({'type':'response.function_call_arguments.delta','item_id':'f','delta':'{"file_path":"main.cpp","content":"int main(){'},report,project,pending)
        self.assertIn('int main()',report.call_args.args[1]['preview'])

    def test_coder_routes_codex_with_exact_long_goal(self):
        from jarvis.coder import Coder, create_python_from_goal
        from jarvis.model_selection import required_models
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);actions=SimpleNamespace(_task_folder=Mock(return_value=root))
            client=SimpleNamespace(options={'coding_backend':'codex'})
            with patch('jarvis.codex_code.run',return_value='done') as run:
                goal='create a website with an email form '+('requested controls '*110)
                self.assertEqual(Coder(actions,client).run(root,goal,selected=True),'done')
                self.assertEqual(run.call_args.args[2],goal)
                self.assertEqual(create_python_from_goal(actions,client,'create Python calculator','calculator.py',lambda:False),'done')
            self.assertIn(MODEL,required_models({'brain':{'coding_backend':'codex'}}))

    def test_stop_bridge_failure_and_deadline_close_owned_children(self):
        from jarvis.codex_code import run
        from contextlib import nullcontext
        for mode in ('stop','proxy','turn','timeout'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'project';root.mkdir();stop=[False];reports=[]
                coder=SimpleNamespace(actions=SimpleNamespace(base=Path(folder),report=lambda k,v:reports.append((k,v))),client=SimpleNamespace(options={}))
                response=Mock();response.json.return_value={'capabilities':['tools']}
                process=Mock(stdin=io.StringIO(),stdout=io.StringIO(json.dumps({'type':'turn.failed','error':{'message':'MCP failed'}})+'\n'))
                process.poll.return_value=None
                if mode=='stop':process.stdin=Mock(write=Mock(side_effect=lambda v:stop.__setitem__(0,True)))
                proxy=Mock();proxy.poll.return_value=1 if mode=='proxy' else None;job=Mock()
                def launch(argv,**kwargs):
                    if 'jarvis.codex_proxy' in argv:
                        if mode!='proxy':(Path(argv[-1])/'proxy-ready.json').write_text('{"port":12345}')
                        return proxy
                    return process
                clock=patch('jarvis.codex_code.time.monotonic',side_effect=[0,0,1801]) if mode=='timeout' else nullcontext()
                with clock,patch('jarvis.codex_code.executable',return_value='codex.exe'),patch('jarvis.knowledge_worker.session') as session,patch('jarvis.codex_code.OwnedJob',return_value=job),patch('jarvis.codex_code.hidden_spawn',return_value=launch) as spawn:
                    session.return_value.__enter__.return_value.post.return_value=response
                    with self.assertRaisesRegex(ValueError,{'stop':'stopped','proxy':'adapter','turn':'failed','timeout':'limit'}[mode]): run(coder,root,'create main.py',lambda:stop[0])
                    job.close.assert_called_once();self.assertEqual(spawn.call_count,1 if mode=='proxy' else 2)
                failure=list((Path(folder)/'.jarvis-runtime/codex-code').glob('*/failure.json'))
                self.assertFalse(json.loads(failure[0].read_text())['automatically_replayed'])
                self.assertFalse(reports[-1][1]['active']);self.assertEqual(list(root.iterdir()),[])


if __name__=='__main__': unittest.main()
