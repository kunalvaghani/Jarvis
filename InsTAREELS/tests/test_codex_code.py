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
from jarvis.codex_proxy import prepare, validate, restore, TOOLS, worker_scope


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
        self.assertEqual(value['temperature'],0)
        self.assertEqual(value['max_output_tokens'],6000);self.assertNotIn('reasoning',value)
        for payload in ({'model':'cloud','tools':tools},{'model':MODEL,'tools':[]},{'model':MODEL,'tools':tools,'previous_response_id':'old'}):
            with self.assertRaises(ValueError): prepare('/v1/responses',payload)
        with self.assertRaises(ValueError): prepare('/v1/chat/completions',{'model':MODEL,'tools':tools})
        with self.assertRaises(ValueError): validate({'type':'response.output_item.done','item':{'type':'function_call','name':'exec_command'}})
        with self.assertRaises(ValueError): validate({'type':'response.completed','response':{'output':[{'type':'custom_tool_call','name':'apply_patch'}]}})
        validate({'type':'response.output_item.done','item':{'type':'function_call','name':next(iter(TOOLS))}})
        event=restore({'type':'response.output_item.done','item':{'type':'function_call','name':'mcp__jarvis_files__Read','arguments':'{}','call_id':'call1'}})
        self.assertEqual(event['item']['name'],'Read');self.assertEqual(event['item']['namespace'],'mcp__jarvis_files')
        for name in ('Read','Write','Edit','Glob','Grep','Plan'):
            short=restore({'type':'response.output_item.done','item':{'type':'function_call','name':name,'arguments':'{}','call_id':'call-short'}})
            self.assertEqual(short['item']['name'],name);self.assertEqual(short['item']['namespace'],'mcp__jarvis_files')
        for name in ('Shell','ReadFile','read','exec_command'):
            with self.assertRaisesRegex(ValueError,'unoffered'):
                restore({'type':'response.output_item.done','item':{'type':'function_call','name':name}})
        with self.assertRaisesRegex(ValueError,'unoffered'):
            restore({'type':'response.output_item.done','item':{'type':'function_call','name':'Read','namespace':'another_server'}})
        value=prepare('/v1/responses',{'model':MODEL,'tools':tools,'input':[event['item']]})
        self.assertEqual(value['input'][0]['name'],'mcp__jarvis_files__Read');self.assertNotIn('namespace',value['input'][0])

    def test_worker_schema_moves_from_missing_test_to_assigned_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();run=Path(folder)/'run';run.mkdir()
            (run/'request.json').write_text(json.dumps({'project':str(root),'allowed_paths':['a.py','test_a.py']}))
            (run/'validation-contract.json').write_text(json.dumps({'files':[{'path':'a.py','role':'logic'},{'path':'test_a.py','role':'test'}]}))
            payload={'instructions':'Preserve original instructions','tools':[{'name':'mcp__jarvis_files__Write','parameters':{'type':'object','properties':{'file_path':{'type':'string'},'content':{'type':'string'}},'required':['file_path','content']}}]}
            value=worker_scope(payload,run)
            self.assertEqual(value['tools'][0]['parameters']['properties']['file_path']['enum'],['test_a.py'])
            self.assertIn('Preserve original instructions',value['instructions'])
            self.assertNotIn('enum',payload['tools'][0]['parameters']['properties']['file_path'])
            (root/'test_a.py').write_text('import unittest\n')
            self.assertEqual(worker_scope(payload,run)['tools'][0]['parameters']['properties']['file_path']['enum'],['a.py','test_a.py'])
            (run/'request.json').write_text(json.dumps({'project':str(root),'allowed_paths':['styles.css','test_styles.py']}))
            instruction=worker_scope(payload,run)['instructions']
            self.assertIn('do not parse CSS as HTML',instruction);self.assertNotIn('HTMLParser',instruction)
            (run/'request.json').write_text(json.dumps({'project':str(root),'allowed_paths':['app.js'],'platform_component':True}))
            instruction=worker_scope(payload,run)['instructions']
            self.assertIn('Jarvis supplies actual Chrome tests',instruction);self.assertNotIn('node:test',instruction)
            settings=configuration(root,run,MODEL,12345)
            self.assertIn('enabled_tools = ["Read", "Write", "Edit"]',settings)
            self.assertIn('Do not author test files',(run/'instructions.txt').read_text())
            (root/'index.html').write_text('<span id=count>0</span>')
            (run/'validation-contract.json').write_text(json.dumps({'files':[{'path':'app.js','role':'logic'}],
                                                                    'checks':[{'kind':'browser_component','entry':'index.html','steps':[{'action':'text','selector':'#count','value':'0'}]}]}))
            scoped=worker_scope(payload,run);instruction=scoped['instructions']
            self.assertIn('<span id=count>0</span>',instruction);self.assertIn('textContent',instruction)
            self.assertIn('never an input for a text assertion',instruction)
            self.assertIn('"selector": "#count"',instruction);self.assertEqual(scoped['max_output_tokens'],3000)
            self.assertIn('INITIAL STATE AFTER JAVASCRIPT INITIALIZATION',instruction)
            self.assertFalse((root/'app.js').exists())

    def test_compact_component_context_preserves_guidance_repair_and_paired_source_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();run=Path(folder)/'run';run.mkdir()
            request={'project':str(root),'goal':'Wire the agreed controls','allowed_paths':['app.js'],'platform_component':True,
                     'project_guidance':{'instructions':'Preserve keyboard accessibility'},'repair_diagnostics':{'error':'Click did not update text'}}
            (run/'request.json').write_text(json.dumps(request))
            (run/'validation-contract.json').write_text(json.dumps({'files':[{'path':'app.js','role':'logic'}],'checks':[]}))
            call={'type':'function_call','call_id':'read1','name':'mcp__jarvis_files__Read','arguments':'{"file_path":"app.js"}'}
            output={'type':'function_call_output','call_id':'read1','output':'Observed current source'}
            payload={'instructions':'Unrelated generic environment descriptions','tools':[{'name':'mcp__jarvis_files__'+name} for name in ('Read','Write','Edit')],
                     'input':[{'role':'developer','content':'Unrelated skills'},call,output,{'role':'assistant','content':'Repeated speculation'}]}
            result=worker_scope(payload,run)
            self.assertEqual(result['input'][1:-1],[call,output])
            self.assertIn('Click did not update text',result['input'][-1]['content'][0]['text'])
            task=json.loads(result['input'][0]['content'][0]['text'])
            self.assertEqual(task['project_guidance'],request['project_guidance'])
            self.assertEqual(task['repair_diagnostics'],request['repair_diagnostics'])
            self.assertEqual(task['assigned_task'],request['goal']);self.assertEqual(task['registered_plan']['files'][0]['path'],'app.js')
            self.assertEqual([tool['name'] for tool in result['tools']],['mcp__jarvis_files__Read','mcp__jarvis_files__Write'])
            self.assertNotIn('Unrelated',result['instructions'])
            request['platform_component']=False;(run/'request.json').write_text(json.dumps(request))
            self.assertEqual(worker_scope(payload,run)['input'],payload['input'])

    def test_python_worker_context_preserves_contract_guidance_tool_pairs_and_save_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();run=Path(folder)/'run';run.mkdir()
            plan={'files':[{'path':'main.py','role':'entrypoint'},{'path':'test_main.py','role':'test'}],
                  'checks':[{'kind':'python_tests','path':'test_main.py'}]}
            request={'project':str(root),'goal':'Create a Python script drawing a circle on screen',
                     'allowed_paths':['main.py','test_main.py'],'validation_contract':plan,
                     'project_guidance':{'repository_instructions':['Keep the chosen destination']},
                     'repair_diagnostics':{'errors':['Unconnected mock; call_args is None']}}
            (run/'validation-contract.json').write_text(json.dumps(plan))
            call={'type':'function_call','call_id':'r1','name':'mcp__jarvis_files__Read','arguments':'{}'}
            output={'type':'function_call_output','call_id':'r1','output':'Actual source'}
            payload={'instructions':'Unrelated generic website setup','tools':[{'name':'mcp__jarvis_files__Write','parameters':{'properties':{'file_path':{'type':'string'}}}}],
                     'input':[{'role':'developer','content':'Unrelated CLI prose'},call,output,{'role':'assistant','content':'Speculation'}]}
            for allowed in (request['allowed_paths'],None):
                request['allowed_paths']=allowed;(run/'request.json').write_text(json.dumps(request))
                value=worker_scope(payload,run)
                task=json.loads(value['input'][0]['content'][0]['text'])
                self.assertEqual(task['original_task'],request['goal']);self.assertEqual(task['registered_plan'],plan)
                self.assertEqual(task['project_guidance'],request['project_guidance']);self.assertEqual(task['repair_diagnostics'],request['repair_diagnostics'])
                self.assertEqual(value['input'][1:-1],[call,output]);self.assertNotIn('Unrelated',value['instructions'])
                self.assertIn('unconnected mock',value['instructions']);self.assertIn('four positional bounds',value['instructions'])
                self.assertIn('constructor call_args.kwargs',value['instructions']);self.assertIn('outline thickness',value['instructions'])
                if allowed:self.assertEqual(value['tools'][0]['parameters']['properties']['file_path']['enum'],['test_main.py'])
                else:self.assertEqual(value['tools'],payload['tools'])
            request['goal']='Create a Python backend and frontend';request['allowed_paths']=['main.py','test_main.py']
            (run/'request.json').write_text(json.dumps(request))
            self.assertEqual(worker_scope(payload,run)['input'],payload['input'])

    def test_full_project_repair_preserves_authorized_context_and_tool_pairs(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder)
            request={'project':str(run),'goal':'Repair the homepage', 'allowed_paths':None,
                     'project_guidance':{'repository_instructions':['Keep existing keyboard controls']},
                     'repair_diagnostics':{'errors':['Homepage lacks #count']}}
            plan={'files':[{'path':'server.py','role':'backend'}],'checks':[{'kind':'browser','path':'index.html'}]}
            (run/'request.json').write_text(json.dumps(request))
            (run/'validation-contract.json').write_text(json.dumps(plan))
            (run/'instructions.txt').write_text('Original source safety rules; never delete files.')
            call={'type':'function_call','call_id':'r1','name':'mcp__jarvis_files__Read','arguments':'{}'}
            output={'type':'function_call_output','call_id':'r1','output':'Current faulty source'}
            payload={'instructions':'Original source safety rules','tools':[{'name':'mcp__jarvis_files__Edit'}],
                     'input':[{'role':'developer','content':'CLI descriptions'},call,output,
                              {'role':'assistant','content':'Repeated unsupported permission guesses'}], 'max_output_tokens':6000}
            result=worker_scope(payload,run)
            task=json.loads(result['input'][0]['content'][0]['text'])
            self.assertEqual(task['original_task'],request['goal'])
            self.assertEqual(task['project_guidance'],request['project_guidance'])
            self.assertEqual(task['repair_diagnostics'],request['repair_diagnostics'])
            self.assertEqual(task['registered_plan'],plan)
            self.assertEqual(result['input'][1:-1],[call,output])
            self.assertIn('Original source safety rules',result['instructions'])
            self.assertIn('never delete files',result['instructions'])
            self.assertEqual(result['tools'],payload['tools'])
            self.assertEqual(result['max_output_tokens'],3000)
            self.assertNotIn('unsupported permission guesses',json.dumps(result['input']))
            request['repair_diagnostics']=None
            (run/'request.json').write_text(json.dumps(request))
            self.assertEqual(worker_scope(payload,run),payload)

    def test_completed_peer_css_requires_confirmed_validation_hash(self):
        from jarvis.codex_proxy import tested_peer_styles
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)/'codex-workloads'/('a'*32)
            root=directory/'workers/logic';root.mkdir(parents=True)
            peer=directory/'workers/styles';peer.mkdir()
            source=peer/'styles.css';source.write_text('.dark{background:purple}')
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            row={'key':'styles','status':'tested_and_combined','changed':['styles.css'],'validation':{'passed':True,'hashes':{'styles.css':digest}}}
            receipt=directory/'receipt.json';receipt.write_text(json.dumps({'workers':[row]}))
            self.assertEqual(tested_peer_styles(root)[0]['source'],source.read_text())
            row['status']='running';receipt.write_text(json.dumps({'workers':[row]}));self.assertEqual(tested_peer_styles(root),[])
            row['status']='tested_and_combined';receipt.write_text(json.dumps({'workers':[row]}))
            source.write_text('.dark{background:red}');self.assertEqual(tested_peer_styles(root),[])
            self.assertFalse((root/'styles.css').exists())

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
                with self.assertRaisesRegex(ValueError,'Rejected source near the error'): execute('Write',{'file_path':'bad.js','content':'function broken( {'})
                # Returning the same original content externally cannot replay an attempted edit.
                source.write_bytes(original);execute('Read',{'file_path':'main.py'})
                with self.assertRaisesRegex(ValueError,'already attempted'): execute('Edit',args)
            rows=[json.loads(line) for line in (run/'file-events.jsonl').read_text().splitlines()]
            self.assertEqual([r['stage'] for r in rows if r['stage']!='rejected'],['attempted','applied','attempted','applied'])
            rejected=[r for r in rows if r['stage']=='rejected']
            self.assertEqual(len(rejected),1);self.assertEqual(rejected[0]['path'],'bad.js')
            self.assertEqual(rejected[0]['proposed_source'],'function broken( {')
            self.assertIn('Rejected source near the error',rejected[0]['error'])
            self.assertFalse((root/'bad.js').exists())
            from jarvis.codex_validation import retain_rejected_javascript
            old_run=Path(folder)/'old-run';old_run.mkdir()
            (old_run/'request.json').write_text(json.dumps({'allowed_paths':['bad.js']}))
            item={'type':'mcp_tool_call','tool':'Write','status':'failed','arguments':{'file_path':'bad.js','content':rejected[0]['proposed_source']},
                  'result':{'content':[{'type':'text','text':rejected[0]['error']}]}}
            (old_run/'events.jsonl').write_text(json.dumps({'type':'item.completed','item':item})+'\n')
            self.assertEqual(retain_rejected_javascript(root,old_run),1)
            self.assertEqual(retain_rejected_javascript(root,old_run),0)
            self.assertFalse((root/'bad.js').exists())

    def test_noop_save_is_rejected_before_backup_or_mutation_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();run=Path(folder)/'run';run.mkdir()
            source=root/'index.html';text='<html><h1>Counter</h1></html>';source.write_text(text)
            before=source.stat().st_mtime_ns
            plan={'files':[{'path':'index.html','role':'frontend','purpose':'Visible counter'}],
                  'checks':[{'kind':'browser','path':'index.html','steps':[{'action':'text','selector':'h1','value':'Counter'}]}]}
            (run/'request.json').write_text(json.dumps({'project':str(root),'goal':'Repair index.html','require_validation':True}))
            (run/'validation-contract.json').write_text(json.dumps(plan))
            with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(root),'JARVIS_CODEX_RUN':str(run)}):
                execute('Read',{'file_path':'index.html'})
                with self.assertRaisesRegex(ValueError,'unchanged'):
                    execute('Write',{'file_path':'index.html','content':text})
            self.assertEqual(source.read_text(),text)
            self.assertEqual(source.stat().st_mtime_ns,before)
            self.assertFalse((run/'file-events.jsonl').exists())
            self.assertFalse((run/'originals').exists())

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

    def test_cold_service_preflight_failure_or_stop_prevents_coding_effects(self):
        from jarvis.codex_code import _turn
        for stopped in (False,True):
            with self.subTest(stopped=stopped),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source=root/'existing.py';source.write_text('value=1\n')
                cancelled=[False]
                coder=SimpleNamespace(actions=SimpleNamespace(base=root,report=Mock()),client=SimpleNamespace(options={}))
                def preflight(client):
                    if stopped:cancelled[0]=True
                    else:raise ValueError('Local service unavailable')
                with patch('jarvis.codex_code.executable',return_value='codex.exe'),\
                     patch('jarvis.knowledge_worker.session'),\
                     patch('jarvis.knowledge_worker.ensure_server',side_effect=preflight) as service,\
                     patch('jarvis.ollama_models.coding_model') as model,\
                     patch('jarvis.codex_code.hidden_spawn') as spawn:
                    with self.assertRaisesRegex(ValueError,'cancelled|unavailable'):
                        _turn(coder,root,'Repair existing.py',lambda:cancelled[0])
                    service.assert_called_once();model.assert_not_called();spawn.assert_not_called()
                self.assertEqual(source.read_text(),'value=1\n')
                self.assertFalse((root/'.jarvis-runtime').exists())

    def test_stop_bridge_failure_and_deadline_close_owned_children(self):
        from jarvis.codex_code import _turn as run
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

    def test_rejected_saves_handoff_only_after_confirmed_mutation_state(self):
        from jarvis.codex_code import _turn
        for uncertain in (False,True):
            with self.subTest(uncertain=uncertain),tempfile.TemporaryDirectory() as folder:
                project=Path(folder)/'project';project.mkdir()
                coder=SimpleNamespace(actions=SimpleNamespace(base=Path(folder),report=Mock()),client=SimpleNamespace(options={}))
                events=[{'type':'item.completed','item':{'type':'mcp_tool_call','tool':'Write','status':'failed',
                         'arguments':{'file_path':'main.py'},'result':{'content':[{'type':'text','text':'Syntax rejected'}]}}}]*3
                process=Mock(stdin=io.StringIO(),stdout=io.StringIO(''.join(json.dumps(event)+'\n' for event in events)))
                process.returncode=1;process.poll.return_value=1
                proxy=Mock();proxy.poll.return_value=None;job=Mock()
                def launch(argv,**kwargs):
                    if 'jarvis.codex_proxy' in argv:
                        directory=Path(argv[-1]);(directory/'proxy-ready.json').write_text('{"port":12345}')
                        if uncertain:
                            (directory/'file-events.jsonl').write_text(json.dumps({'stage':'attempted','signature':'unconfirmed'})+'\n')
                        return proxy
                    return process
                response=Mock();response.json.return_value={'capabilities':['tools']}
                with patch('jarvis.codex_code.executable',return_value='codex.exe'),patch('jarvis.knowledge_worker.session') as session,patch('jarvis.codex_code.OwnedJob',return_value=job),patch('jarvis.codex_code.hidden_spawn',return_value=launch):
                    session.return_value.__enter__.return_value.post.return_value=response
                    if uncertain:
                        with self.assertRaisesRegex(ValueError,'without confirmed readback'):_turn(coder,project,'create a script',lambda:False)
                    else:
                        turn=_turn(coder,project,'create a script',lambda:False)
                        self.assertEqual(turn['changed'],[]);self.assertIn('three confirmed',turn['report'])
                self.assertEqual(job.close.call_count,2)


    def test_registered_partition_hands_off_to_checks_without_waiting_for_final_report(self):
        from jarvis.codex_code import _turn
        for uncertain,component in ((False,False),(True,False),(False,True),(True,True)):
            with self.subTest(uncertain=uncertain,component=component),tempfile.TemporaryDirectory() as folder:
                project=Path(folder)/'project';project.mkdir()
                (project/'main.py').write_text('def value():\n    return 1\n')
                (project/'test_main.py').write_text('import unittest\nfrom main import value\nclass Checks(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(value(),1)\n')
                plan={'files':[{'path':'main.py','role':'logic','purpose':'Return the requested value'},
                               {'path':'test_main.py','role':'test','purpose':'Assert the requested value'}],
                      'checks':[{'kind':'python_tests','path':'test_main.py'}]}
                if component:
                    (project/'index.html').write_text('<span id="count">0</span>')
                    plan={'files':[{'path':'index.html','role':'frontend','purpose':'Render visible counter'}],
                          'checks':[{'kind':'browser_component','component':'markup','entry':'index.html','path':'index.html','steps':[{'action':'text','selector':'#count','value':'0'}]}]}
                names=[f['path'] for f in plan['files']]
                event={'type':'item.completed','item':{'type':'mcp_tool_call','tool':'Write','status':'completed',
                                                     'arguments':{'file_path':names[-1]},'result':{}}}
                process=Mock(stdin=io.StringIO(),stdout=io.StringIO(json.dumps(event)+'\n'));process.returncode=1;process.poll.return_value=1
                proxy=Mock();proxy.poll.return_value=None;job=Mock()
                coder=SimpleNamespace(actions=SimpleNamespace(base=Path(folder),report=Mock()),client=SimpleNamespace(options={}))
                def launch(argv,**kwargs):
                    if 'jarvis.codex_proxy' in argv:
                        directory=Path(argv[-1]);(directory/'proxy-ready.json').write_text('{"port":12345}')
                        rows=[]
                        for name in names:
                            row={'path':str(project/name),'signature':name,'observed_sha256':None,
                                 'proposed_sha256':hashlib.sha256((project/name).read_bytes()).hexdigest()}
                            rows.extend([{**row,'stage':'attempted'},{**row,'stage':'applied'}])
                        if uncertain:rows.append({'signature':'uncertain','stage':'attempted'})
                        (directory/'file-events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
                        return proxy
                    return process
                response=Mock();response.json.return_value={'capabilities':['tools']}
                with patch('jarvis.codex_code.executable',return_value='codex.exe'),patch('jarvis.knowledge_worker.session') as session,patch('jarvis.codex_code.OwnedJob',return_value=job),patch('jarvis.codex_code.hidden_spawn',return_value=launch):
                    session.return_value.__enter__.return_value.post.return_value=response
                    if uncertain:
                        with self.assertRaisesRegex(ValueError,'without confirmed readback'):_turn(coder,project,'Implement a value',lambda:False,feedback={'error':'Observed assertion failure'} if component else None,plan=plan,allowed_paths=names)
                    else:
                        result=_turn(coder,project,'Implement a value',lambda:False,feedback={'error':'Observed assertion failure'} if component else None,plan=plan,allowed_paths=names)
                        self.assertEqual(set(result['changed']),set(names))
                        self.assertIn('independent checks',result['report'])
                        self.assertFalse(json.loads((result['directory']/'result.json').read_text())['functional_behavior_verified'])
                self.assertEqual(job.close.call_count,2)


if __name__=='__main__': unittest.main()
