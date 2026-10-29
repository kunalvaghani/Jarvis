"""Fault injection only; these tests do not establish autonomous application success."""
import json
from pathlib import Path
import tempfile
import unittest
import time
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.structured_output import decode, ModelOutputError


class StructuredOutput(unittest.TestCase):
    def test_generation_schema_keeps_semantic_regex_local_and_preserves_named_fields(self):
        from jarvis.structured_output import generation_schema,validate_contract
        semantic={'type':'object','required':['pattern'],'additionalProperties':False,
            'properties':{'pattern':{'type':'string','pattern':r'.*\.py$','maxLength':60}}}
        before=json.dumps(semantic,sort_keys=True)
        generated=generation_schema(semantic)
        self.assertIn('pattern',generated['properties'])
        self.assertNotIn('pattern',generated['properties']['pattern'])
        self.assertEqual(generated['properties']['pattern']['maxLength'],60)
        self.assertEqual(json.dumps(semantic,sort_keys=True),before)
        validate_contract(generated,{'pattern':'wrong.txt'})
        with self.assertRaises(ValueError):validate_contract(semantic,{'pattern':'wrong.txt'})
        validate_contract(semantic,{'pattern':'main.py'})

    def test_native_wire_grammar_omits_regex_but_local_contract_still_rejects_oversized_plan(self):
        from jarvis.native_coding import infer
        class Client:
            post=lambda *a,**k:None
            def __enter__(self):return self
            def __exit__(self,*args):return False
        def answer(client,options,*args,**kwargs):
            fields=options['format_schema']['anyOf'][0]['properties']['arguments']['properties']['observed_cause']
            self.assertNotIn('pattern',fields)
            options['on_complete']({'done':True,'done_reason':'stop'})
            return json.dumps({'tool':'update_plan','arguments':{'observed_cause':'x'*241,
                'permitted_strategy':'Preserve the contract.','verification':'Run unchanged checks.'}})
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),\
                    patch('jarvis.knowledge_worker.chat',side_effect=answer):
                with self.assertRaises(ModelOutputError):
                    infer([{'role':'user','content':'Read-only fixture'}],
                        {'coder':'qwen3.5:9b','native_required_tool':'update_plan','native_diagnostic_plan':True},
                        lambda:False,time.monotonic()+10,lambda *args:None,root)
            self.assertFalse((root/'file-events.jsonl').exists())
            self.assertTrue(list(root.glob('model-responses/*/metadata.json')))

    def test_idle_limit_allows_one_ready_guarded_replacement_then_stops_if_unchanged(self):
        from jarvis.native_coding import run,StalledCoding
        from jarvis.coder import Coder
        from tests.test_native_coding import plan,TEST
        for corrected in (True,False):
            with self.subTest(corrected=corrected),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);root=base/'project';root.mkdir()
                source='# bounded source view context\n'*47+'def add(a,b):\n return a-b\n'+'# bounded source view context\n'*80
                (root/'main.py').write_text(source);(root/'test_main.py').write_text(TEST)
                calls=[]
                def inference(messages,options,*args):
                    calls.append(options.get('native_required_tool'));index=len(calls)
                    if index<=3:return {'tool':'read_batch','arguments':{'paths':['main.py','test_main.py']}}
                    if index==4:return {'tool':'run_checks','arguments':{}}
                    if index in (5,10,15):return {'tool':'Read','arguments':{'file_path':'main.py'}}
                    slices={6:(48,10),7:(1,24),8:(25,24),11:(48,10),12:(58,24),13:(74,24)}
                    if index in slices:
                        start,count=slices[index]
                        return {'tool':'read_slice','arguments':{'file_path':'main.py','start':start,'count':count}}
                    if index in (9,14):return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'missing context '+str(index),'new_string':'different context'}}
                    self.assertEqual(index,16);self.assertEqual(options['native_required_tool'],'Write')
                    self.assertEqual(options['native_rewrite_paths'],['main.py'])
                    return {'tool':'Write','arguments':{'file_path':'main.py','content':source.replace('return a-b','return a+b') if corrected else source}}
                coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
                with patch('jarvis.native_coding.infer',side_effect=inference):
                    if corrected:
                        result=run(coder,root,'Repair addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
                        self.assertTrue(result['validation']['passed'])
                    else:
                        with self.assertRaisesRegex(StalledCoding,'12 tool turns'):
                            run(coder,root,'Repair addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
                        self.assertEqual((root/'main.py').read_text(),source)
                self.assertEqual(len(calls),16)
                self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_rejected_patch_contexts_switch_to_guarded_replacement_after_fresh_read(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            source='def add(a,b): return a-b\n'
            (root/'main.py').write_text(source);(root/'test_main.py').write_text(TEST)
            calls=[]
            def inference(messages,options,*args):
                calls.append(options.get('native_required_tool'));index=len(calls)
                if index==1:return {'tool':'run_checks','arguments':{}}
                if index in (2,4,6):
                    self.assertEqual((root/'main.py').read_text(),source)
                    return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==3:return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return missing','new_string':'return a+b'}}
                if index==5:return {'tool':'apply_patch','arguments':{'patch':'*** Begin Patch\n*** Update File: main.py\n@@\n-def missing(): pass\n+def add(a,b): return a+b\n*** End Patch'}}
                self.assertEqual(index,7);self.assertEqual(options['native_required_tool'],'Write')
                self.assertEqual(options['native_rewrite_paths'],['main.py'])
                self.assertIn(source.strip(),'\n'.join(m['content'] for m in messages))
                return {'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Repair addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),7)
            self.assertEqual((root/'test_main.py').read_text(),TEST)
            events=[json.loads(s) for s in (Path(result['directory'])/'file-events.jsonl').read_text().splitlines()]
            self.assertEqual(sum(e['stage']=='applied' for e in events),1)

    def test_repeated_noop_edits_can_regenerate_only_read_assigned_implementation(self):
        from jarvis.native_coding import run,scoped_schema
        from jarvis.coder import Coder
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            (root/'test_main.py').write_text(TEST);(root/'main.py').write_text('def add(a,b): return a-b\n')
            stages=[]
            def inference(messages,options,cancelled,deadline,report,directory):
                stages.append(options.get('native_required_tool'));index=len(stages)
                if index==1:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index==3:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index in (4,5):raise ModelOutputError('Edit old_string and new_string are identical; no action executed.')
                self.assertEqual(options['native_required_tool'],'Write')
                self.assertEqual(options['native_rewrite_paths'],['main.py'])
                text='\n'.join(m['content'] for m in messages if isinstance(m.get('content'),str))
                self.assertIn('complete current source',text)
                self.assertIn('def add(a,b): return a-b',text)
                self.assertIn('COMPLETE assigned implementation',messages[-1]['content'])
                self.assertNotIn('at most 60 lines',messages[-1]['content'])
                schema=scoped_schema(directory,force_tool='Write',force_rewrite_paths=['main.py','test_main.py','outside.py'])
                paths=schema['anyOf'][0]['properties']['arguments']['properties']['file_path']['enum']
                self.assertEqual(paths,['main.py'])
                return {'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertEqual((root/'test_main.py').read_text(),TEST)
            self.assertEqual(result['turns'][-1]['tool'],'Write')

    def test_noop_edit_regeneration_switches_to_source_bound_batch_without_replaying_edit(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            (root/'main.py').write_text('def add(a,b): return a-b\n')
            stages=[]
            def inference(messages,options,*args):
                stages.append(options.get('native_required_tool'))
                index=len(stages)
                if index==1:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index==3:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==4:raise ModelOutputError('Edit old_string and new_string are identical; no action executed.')
                self.assertEqual(options['native_required_tool'],'edit_batch')
                guidance='\n'.join(m['content'] for m in messages if isinstance(m.get('content'),str))
                self.assertIn('Fresh complete implementation (read-only DATA)',guidance)
                self.assertIn('def add(a,b): return a-b',guidance)
                self.assertNotIn('*** Update File: assigned/relative/path',guidance)
                self.assertNotIn(' exact current context',guidance)
                return {'tool':'edit_batch','arguments':{'file_path':'main.py',
                    'source_sha256':options['native_exact_edit_spans']['sha256'],
                    'changes':[{'old_string':'def add(a,b): return a-b','new_string':'def add(a,b): return a+b'}]}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual((root/'test_main.py').read_text(),TEST)
            self.assertFalse(any(r['tool']=='Edit' for r in result['turns']))
            self.assertEqual(result['turns'][-1]['tool'],'edit_batch')
            events=[json.loads(s) for s in (Path(result['directory'])/'file-events.jsonl').read_text().splitlines()]
            self.assertEqual(sum(r.get('stage')=='applied' for r in events),1)

    def test_unchanged_edit_is_rejected_at_inference_boundary_with_original_evidence(self):
        from jarvis.native_coding import inference_schema
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'main.py';source.write_text('VALUE = 1\n')
            raw=json.dumps({'tool':'Edit','arguments':{'file_path':'main.py','old_string':'VALUE = 1','new_string':'VALUE = 1'}})
            with self.assertRaisesRegex(ModelOutputError,'identical'):
                decode(raw,completed=True,reason='stop',schema=inference_schema(),directory=root,stage='tool')
            self.assertEqual(source.read_text(),'VALUE = 1\n')
            record=next(root.glob('model-responses/*/response.txt'));self.assertEqual(record.read_text(),raw)

    def test_repeated_unchanged_writes_keep_rejection_and_stop_without_replaying_save(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            proposal={'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a-b\n'}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',return_value=proposal):
                with self.assertRaisesRegex(ValueError,'same unchanged proposal'):
                    run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            directory=next((base/'.jarvis-runtime/native-code').iterdir())
            rows=[json.loads(s) for s in (directory/'tools.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),4);self.assertEqual(rows[-1]['result']['rejected_proposal']['count'],3)
            events=[json.loads(s) for s in (directory/'file-events.jsonl').read_text().splitlines()]
            self.assertEqual(sum(r.get('stage')=='applied' for r in events),1)
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_schema_rejected_object_is_diagnostic_only_but_truncation_is_not_parsed(self):
        schema={'type':'object','required':['path'],'properties':{'path':{'type':'string','pattern':r'.*\.js$'}}}
        value={'path':'test_api.py'}
        with self.assertRaises(ModelOutputError) as caught:decode(json.dumps(value),completed=True,schema=schema)
        self.assertEqual(caught.exception.previous_proposal,value)
        self.assertIn('test_api.py',str(caught.exception))
        with self.assertRaises(ModelOutputError) as truncated:decode(json.dumps(value),completed=True,reason='length',schema=schema)
        self.assertFalse(hasattr(truncated.exception,'previous_proposal'))

    def test_incomplete_valid_json_is_rejected_before_dispatch(self):
        for completed, reason in [(False,None),(True,'length'),(True,'cancelled')]:
            with self.assertRaises(ModelOutputError):
                decode('{"tool":"Write"}',completed=completed,reason=reason)

    def test_malformed_payloads_keep_exact_bytes_and_location(self):
        for text in ['{"files":["main.py" "test.py"]}', '{"files":["main.py', '```json\n{}\n```']:
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ModelOutputError):
                    decode(text,completed=True,directory=directory,stage='plan')
                evidence=next((Path(directory)/'model-responses').iterdir())
                self.assertEqual((evidence/'response.txt').read_bytes(),text.encode('utf-8'))
                meta=json.loads((evidence/'metadata.json').read_text())
                self.assertEqual(meta['error_type'],'JSONDecodeError')
                self.assertIn('column',meta)

    def test_schema_and_top_level_validation(self):
        schema={'type':'object','required':['files'],'additionalProperties':False,
                'properties':{'files':{'type':'array','items':{'type':'string'}}}}
        for text in ['[]','null','{"files":"main.py"}','{"files":[1]}']:
            with self.assertRaises(ModelOutputError):decode(text,completed=True,schema=schema)
        self.assertEqual(decode('{"files":["main.py"]}',completed=True,schema=schema),{'files':['main.py']})

    def test_windows_paths_are_not_unescaped_or_repaired(self):
        path="D:\\Long folder name\\O'Brien\\計算\\nested\\main.py"
        self.assertEqual(decode(json.dumps({'path':path}),completed=True)['path'],path)
        with self.assertRaises(ModelOutputError):decode('{"path":"D:\\Users\\new.py"}',completed=True)

    def test_actual_model_union_and_path_schemas(self):
        from jarvis.native_coding import inference_schema
        from jarvis.codex_workload import planning_schema
        from jarvis.structured_output import validate_contract
        validate_contract(inference_schema(),{'tool':'Read','arguments':{'file_path':'main.py'},'note':'Inspect'})
        with self.assertRaises(ValueError):
            validate_contract(inference_schema(),{'tool':'exec_command','arguments':{'content':'shell'},'note':'Invalid'})
        with self.assertRaises(ValueError):
            validate_contract({'type':'string','pattern':r'.*\.py$'},'main.html')
        # Uses the real browser union and nested source/task schema.
        from tests.test_codex_workload import proposal
        validate_contract(planning_schema(),proposal())

    def test_fullstack_schema_requires_server_and_typed_check_language(self):
        from jarvis.codex_workload import planning_schema
        from jarvis.structured_output import validate_contract
        schema=planning_schema(full_stack=True)['properties']['checks']['items']
        browser={'kind':'browser','path':'index.html','steps':[{'action':'text','selector':'body','value':'Ready'}]}
        with self.assertRaisesRegex(ValueError,'server'):validate_contract(schema,browser)
        browser['server']={'kind':'python','path':'backend.py'}
        validate_contract(schema,browser)
        with self.assertRaises(ValueError):validate_contract(schema,{'kind':'python_tests','path':'styles.css'})
        validate_contract(schema,{'kind':'python_tests','path':'test_backend.py'})

    def test_planner_rejects_length_even_when_json_is_valid(self):
        from jarvis.codex_workload import propose
        from tests.test_codex_workload import proposal
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def raise_for_status(self):pass
            def iter_lines(self,**kwargs):
                yield json.dumps({'done':True,'done_reason':'length','message':{'content':json.dumps(proposal())}}).encode()
        class Client(Response):
            def post(self,*args,**kwargs):return Response()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);audit=root/'audit'
            coder=SimpleNamespace(client=SimpleNamespace(options={}),actions=SimpleNamespace(report=lambda *args:None))
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),patch('jarvis.knowledge_worker.local_prompt_format',return_value='ollama_chat'):
                with self.assertRaisesRegex(ModelOutputError,'Incomplete'):
                    propose(coder,root,'Create independent Python modules',lambda:False,time.monotonic()+10,audit_directory=audit)
            evidence=next((audit/'model-responses').iterdir())
            self.assertEqual(json.loads((evidence/'metadata.json').read_text())['done_reason'],'length')
            self.assertEqual(list(root.glob('*.py')),[])

    def test_native_regenerates_invalid_proposal_without_replaying_action(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            observations=[];budgets=[];systems=[]
            proposals=iter([ModelOutputError('Malformed JSON'),
                {'tool':'Read','arguments':{'file_path':'test_main.py'}},
                {'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'},'note':'Implementation'},
                {'tool':'finish','arguments':{},'note':'Verify'}])
            def infer(messages,options,*args):
                observations.append(messages[-1]['content'])
                budgets.append(options.get('native_source_char_limit'))
                systems.append(messages[0]['content'])
                value=next(proposals)
                if isinstance(value,Exception):raise value
                return value
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            coder.workload_guidance={'code_intelligence':{'reusable_components':[{'name':'optional-reference-fixture'}],
                                                        'dependency_policy':{'offline':True}}}
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,root,'Implement addition',initial_plan=plan(),return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertIn('Nothing was executed',observations[1])
            self.assertEqual(budgets,[None,2400,2400,None])
            self.assertIn('optional-reference-fixture',systems[0])
            self.assertNotIn('optional-reference-fixture',systems[1])
            self.assertIn('"offline": true',systems[1])
            events=[json.loads(s) for s in (Path(result['directory'])/'file-events.jsonl').read_text().splitlines()]
            self.assertEqual(sum(row['stage']=='applied' for row in events),1)

    def test_python_desktop_cannot_drift_to_browser_stack(self):
        from jarvis.codex_workload import workload_contract, localgithub
        from tests.test_codex_workload import proposal
        utilities,_,_=localgithub({})
        value=proposal();value['files'][0]['path']='ui.html'
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'Python desktop'):
                workload_contract(Path(folder),'Create a Python desktop calculator with elegant UI',value,utilities)

    def test_wedged_owned_probe_preserves_timeout_and_closes_job(self):
        import subprocess
        from unittest.mock import Mock
        from jarvis.repo_acquisition import command
        process=Mock();process.poll.return_value=None
        process.wait.side_effect=subprocess.TimeoutExpired(['owned-probe'],1)
        job=Mock()
        with patch('jarvis.repo_acquisition.OwnedJob',return_value=job),patch('jarvis.repo_acquisition.hidden_spawn',return_value=lambda *args,**kwargs:process):
            with self.assertRaisesRegex(ValueError,'timed out'):
                command(['owned-probe'],timeout=-1)
        job.close.assert_called()
        process.kill.assert_called_once()

    def test_history_compaction_preserves_contract_and_latest_feedback(self):
        from jarvis.native_coding import compact_history,observation
        fixed=[{'role':'system','content':'Fixed plan and safety instructions'}, {'role':'user','content':'Original goal'}]
        turns=[{'role':'assistant','content':'x'*2000},{'role':'user','content':'y'*2000}]*10
        latest=[{'role':'assistant','content':'Latest proposal'},{'role':'user','content':'Fresh rejection with exact scope'}]
        packed=compact_history(fixed+turns+latest,limit=6000)
        self.assertEqual(packed[:2],fixed);self.assertEqual(packed[-2:],latest)
        self.assertLess(sum(len(m['content']) for m in packed),6000)
        observed=json.loads(observation({'path':'main.py','sha256':'checked','content':'a'*20000}))
        self.assertEqual(observed['sha256'],'checked')
        self.assertEqual(observed['content_characters'],20000)
        self.assertIn('read_slice',observed['instruction'])
        packet=json.loads(observation({'errors':[{'path':'main.py','error':'AssertionError: wrong arithmetic'}],
            'source_attachments':[{'current_source':'x'*20000}]}))
        self.assertEqual(packet['errors'][0]['path'],'main.py')
        self.assertIn('wrong arithmetic',packet['errors'][0]['error'])
        oversized=fixed+[{'role':'assistant','content':'Completed source proposal: '+'x'*10000},
                         {'role':'user','content':'Fresh error and exact scope'}]
        packed=compact_history(oversized,limit=6000)
        self.assertEqual(packed,fixed+[{'role':'user','content':'Fresh error and exact scope'}])

    def test_active_import_failure_survives_intervening_reads_and_compaction(self):
        from jarvis.native_coding import compact_history,current_diagnostics
        messages=[{'role':'system','content':'Immutable task contract'}, {'role':'user','content':'Original objective'}]
        messages += [{'role':'user','content':'Old failed check: ImportError'}]
        messages += [{'role':'user','content':'Read source: '+'x'*2000} for _ in range(8)]
        compacted=compact_history(messages,limit=6000)
        self.assertNotIn('Old failed check',str(compacted))
        failure={'passed':False,'errors':[{'path':'tests/test_calculator.py',
            'error':'traceback\n'*500+'File "logic/subtraction.py", line 12\n'+"ImportError: cannot import name 'sub' from 'logic.subtraction'"}]}
        payload=current_diagnostics(compacted,failure)
        self.assertIn("cannot import name 'sub'",payload[-2]['content'])
        self.assertIn('tests/test_calculator.py',payload[-2]['content'])
        self.assertIn('subtraction.py',payload[-2]['content']);self.assertIn('12',payload[-2]['content'])
        self.assertEqual(payload[-1],compacted[-1])
        self.assertEqual(compacted,current_diagnostics(compacted,{'passed':True,'errors':[]}))
        self.assertLess(len(payload[-2]['content']),2500)

    def test_locked_receipt_retains_checkpoint_without_replaying_replace(self):
        from jarvis.workload_state import save_checkpoint,latest_checkpoint
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertTrue(save_checkpoint(root,{'status':'planning'}))
            previous=(root/'receipt.json').read_bytes()
            with patch.object(Path,'replace',side_effect=PermissionError('injected sharing conflict')) as replace:
                self.assertFalse(save_checkpoint(root,{'status':'running'}))
            replace.assert_called_once()
            self.assertEqual((root/'receipt.json').read_bytes(),previous)
            self.assertEqual(latest_checkpoint(root)['status'],'running')
            self.assertEqual(len(list((root/'checkpoints').glob('*.json'))),2)
            self.assertTrue(list(root.glob('receipt-*.tmp')))

    def test_checkpoint_order_survives_equal_and_backwards_wall_clock(self):
        from jarvis.workload_state import save_checkpoint,latest_checkpoint
        with tempfile.TemporaryDirectory() as folder, patch('jarvis.workload_state.time.time_ns',side_effect=[42,42,41]):
            root=Path(folder)
            for state in ('planning','running','passed'):
                save_checkpoint(root,{'status':state})
                self.assertEqual(latest_checkpoint(root)['status'],state)
            self.assertEqual([int(p.name.split('-',1)[0]) for p in sorted((root/'checkpoints').glob('*.json'))],[42,43,44])

    def test_identical_rejected_write_stops_without_side_effects(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            proposal={'tool':'Write','arguments':{'file_path':'../outside.py','content':'pass\n'},'note':'Invalid destination fixture'}
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',return_value=proposal) as infer:
                with self.assertRaisesRegex(ValueError,'same rejected proposal'):
                    run(coder,root,'Implement addition',initial_plan=plan(),return_receipt=True)
            self.assertEqual(infer.call_count,3)
            self.assertFalse((base/'outside.py').exists())
            self.assertFalse((root/'main.py').exists())

    def test_empty_dependency_and_package_markers_are_valid_not_empty_implementations(self):
        from jarvis.coder import check_content
        from jarvis.native_coding import inference_schema
        from jarvis.structured_output import validate_contract
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            check_content(root/'requirements.txt','')
            check_content(root/'__init__.py','')
            with self.assertRaises(ValueError):check_content(root/'main.py','')
            with self.assertRaises(ValueError):check_content(root/'requirements.txt','\x00')
        for tool,args in [('Write',{'file_path':'main.py'}),('Read',{}),('Edit',{'file_path':'main.py','old_string':'x'})]:
            with self.assertRaises(ValueError):
                validate_contract(inference_schema(),{'tool':tool,'arguments':args,'note':'Invalid fixture'})
        # A display-only note is not an execution precondition.
        validate_contract(inference_schema(),{'tool':'Read','arguments':{'file_path':'main.py'}})
        validate_contract(inference_schema(),{'tool':'finish'})
        validate_contract(inference_schema(),{'tool':'run_checks'})
        for tool in ('Read','Write','Edit','exec_command'):
            with self.assertRaises(ValueError):validate_contract(inference_schema(),{'tool':tool})
        for tool in ('read_batch','write_stdin','apply_patch','tool_search'):
            with self.assertRaises(ValueError):validate_contract(inference_schema(),{'tool':tool,'arguments':{}})
        validate_contract(inference_schema(),{'tool':'read_batch','arguments':{'paths':['main.py']}})
        with self.assertRaises(ValueError):
            validate_contract(inference_schema(),{'tool':'read_batch','arguments':{'paths':['a.py']*5}})

    def test_interrupted_checkpoint_is_preserved_and_fallback_is_explicit(self):
        from jarvis.workload_state import save_checkpoint,latest_checkpoint
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_checkpoint(root,{'status':'planned'})
            damaged=root/'checkpoints'/'99999999999999999999-interrupted.json'
            damaged.write_text('{"status":',encoding='utf-8')
            observed=latest_checkpoint(root)
            self.assertEqual(observed['status'],'planned')
            self.assertTrue(observed['checkpoint_recovery_required'])
            self.assertEqual(observed['unreadable_newer_checkpoints'][0]['name'],damaged.name)
            self.assertEqual(damaged.read_text(),'{"status":')

    def test_scoped_schema_matches_tests_first_and_frozen_test_boundary(self):
        from jarvis.native_coding import scoped_schema
        from jarvis.structured_output import validate_contract
        from tests.test_native_coding import plan
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();run=Path(folder)/'run';run.mkdir()
            (root/'PROJECT.md').write_text('Fixture specification')
            (run/'request.json').write_text(json.dumps({'project':str(root),'validation_contract':plan(),
                'allowed_paths':['main.py','test_main.py'],'test_first':True}))
            schema=scoped_schema(run,[])
            validate_contract(schema,{'tool':'Read','arguments':{'file_path':'PROJECT.md'}})
            validate_contract(schema,{'tool':'Write','arguments':{'file_path':'test_main.py','content':'pass'}})
            with self.assertRaises(ValueError):validate_contract(schema,{'tool':'Write','arguments':{'file_path':'main.py','content':'pass'}})
            with self.assertRaises(ValueError):validate_contract(schema,{'tool':'Read','arguments':{'file_path':'missing.py'}})
            with self.assertRaises(ValueError):validate_contract(schema,{'tool':'write_stdin','arguments':{'session_id':'guessed'}})
            with self.assertRaises(ValueError):validate_contract(schema,{'tool':'Edit','arguments':{'file_path':'test_main.py','old_string':'a','new_string':'b'}})
            forced=scoped_schema(run,[],force_tool='Write')
            with self.assertRaises(ValueError):validate_contract(forced,{'tool':'Read','arguments':{'file_path':'PROJECT.md'}})
            validate_contract(forced,{'tool':'Write','arguments':{'file_path':'test_main.py','content':'import unittest'}})
            (root/'test_main.py').write_text('import unittest')
            schema=scoped_schema(run)
            validate_contract(schema,{'tool':'Write','arguments':{'file_path':'main.py','content':'pass'}})
            with self.assertRaises(ValueError):validate_contract(schema,{'tool':'Write','arguments':{'file_path':'test_main.py','content':'changed'}})
            # A saved module is not rewritten while another assigned file is missing.
            request=json.loads((run/'request.json').read_text());request['allowed_paths'].append('helper.py')
            request['validation_contract']['files'].append({'path':'helper.py','role':'logic','purpose':'Helper'})
            (run/'request.json').write_text(json.dumps(request));(root/'main.py').write_text('value=1')
            schema=scoped_schema(run)
            with self.assertRaises(ValueError):validate_contract(schema,{'tool':'Write','arguments':{'file_path':'main.py','content':'value=2'}})
            validate_contract(schema,{'tool':'Write','arguments':{'file_path':'helper.py','content':'value=1'}})

    def test_read_only_loop_advances_to_missing_source_generation(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            proposals=iter([{'tool':'Read','arguments':{'file_path':'test_main.py'}}]*3+[
                {'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'}},
                {'tool':'finish'}])
            modes=[]
            def infer(messages,options,*args):
                modes.append(options.get('native_required_tool'));return next(proposals)
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,root,'Implement addition',initial_plan=plan(),return_receipt=True)
            self.assertEqual(modes[3],'Write');self.assertIsNone(modes[4])
            self.assertTrue(result['validation']['passed'])

    def test_assigned_test_only_worker_runs_checks_without_extra_model_finish(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from tests.test_native_coding import TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            (root/'main.py').write_text('def add(a,b): return a+b\n')
            initial=(root/'main.py').read_bytes()
            plan={'files':[{'path':'main.py','role':'logic','purpose':'Existing preserved addition'},
                           {'path':'test_main.py','role':'test','purpose':'Verify existing addition'}],
                  'checks':[{'kind':'python_tests','path':'test_main.py'}]}
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            proposals=[{'tool':'Read','arguments':{'file_path':'main.py'}},
                       {'tool':'Write','arguments':{'file_path':'test_main.py','content':TEST}}]
            with patch('jarvis.native_coding.infer',side_effect=proposals) as infer:
                result=run(coder,root,'Add tests for existing addition',initial_plan=plan,
                    allowed_paths=['test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(infer.call_count,2)
            self.assertFalse(result['whole_goal_verified'])
            self.assertIn('Declared executable-check',result['functional_behavior_scope'])
            self.assertEqual((root/'main.py').read_bytes(),initial)

    def test_undiscoverable_new_tests_are_rejected_before_save_then_valid_tests_freeze(self):
        from tests.test_native_coding import files,TEST
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));name='test_main.py'
            draft='def test_addition():\n assert 2+3==5\n'
            with self.assertRaisesRegex(ValueError,'unittest discovery'):
                session.call('Write',{'file_path':name,'content':draft})
            self.assertFalse((session.root/name).exists());self.assertFalse(session.uncertain())
            rejected=json.loads((session.run/'test-draft-rejections.jsonl').read_text())
            self.assertEqual(rejected['proposed_source'],draft);self.assertFalse(rejected['saved'])
            session.call('Write',{'file_path':name,'content':TEST})
            with self.assertRaisesRegex(ValueError,'assertions are fixed'):
                session.call('Write',{'file_path':name,'content':TEST.replace('5','-1')})

    def test_new_test_discovery_supports_stdlib_aliases_and_async_cases(self):
        from jarvis.codex_validation import validate_test_draft
        plan={'checks':[{'kind':'python_tests','path':'test_api.py'}]}
        for source in ('import unittest as ut\nclass Check(ut.TestCase):\n def test_api(self): self.assertEqual(2+3,5)\n',
                       'from unittest import IsolatedAsyncioTestCase as AsyncCase\nclass Check(AsyncCase):\n async def test_api(self): self.assertEqual(2+3,5)\n'):
            validate_test_draft('test_api.py',source,plan)

    def test_gui_mock_roots_are_rejected_before_freezing_but_service_mocks_remain_allowed(self):
        from tests.test_native_coding import files
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));session.validation_goal='Create a Python Tkinter desktop GUI'
            session.plan['files'].append({'path':'ui_builder.py','role':'frontend','purpose':'Real original widgets'})
            prefix='import unittest\nimport unittest.mock\nfrom unittest.mock import MagicMock as Fake, patch\nfrom tkinter import Tk\nfrom ui_builder import CalculatorGUI as View\nclass Check(unittest.TestCase):\n def test_gui(self):\n'
            for body in ('self.root=unittest.mock.MagicMock()\n  View(self.root)',
                         'root=Fake()\n  other=root\n  View(root=other)',
                         'View(Fake())','Tk(Fake())',
                         'View=Fake()\n  View()',
                         'patch("ui_builder.CalculatorGUI")'):
                with self.subTest(body=body),self.assertRaisesRegex(ValueError,'mock|patches'):
                    session.call('Write',{'file_path':'test_main.py','content':prefix+'  '+body+'\n  self.assertEqual(1,1)\n'})
                self.assertFalse((session.root/'test_main.py').exists());self.assertFalse(session.uncertain())
            valid=prefix+'  service=Fake()\n  root=Tk()\n  gui=View(root, service=service)\n  self.assertEqual(gui.display.get(), "0")\n'
            session.call('Write',{'file_path':'test_main.py','content':valid})
            self.assertEqual((session.root/'test_main.py').read_text(),valid)

    def test_gui_toolkit_instance_methods_are_verified_without_constructing_windows(self):
        from tests.test_native_coding import files
        from jarvis.codex_validation import validate_test_draft
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));session.validation_goal='Create a Python Tkinter desktop GUI'
            prefix='import unittest\nimport tkinter as tk\nfrom tkinter import Event as E\nclass Check(unittest.TestCase):\n def setUp(self):\n  self.key=E()\n def test_keyboard(self):\n'
            for body in ('self.key.generate()', 'other=self.key\n  other.generate()',
                         'E().generate()', 'root=tk.Tk()\n  root.nonexistent_dispatch()',
                         'root=tk.Tk()\n  root.update("unsupported")'):
                with self.subTest(body=body),self.assertRaisesRegex(ValueError,'missing installed API|Installed method signature'):
                    session.call('Write',{'file_path':'test_main.py','content':prefix+'  '+body+'\n  self.assertEqual(1,1)\n'})
                self.assertFalse((session.root/'test_main.py').exists());self.assertFalse(session.uncertain())
            valid=prefix+'  root=tk.Tk()\n  self.key.keysym="Return"\n  root.event_generate("<KeyPress>", keysym="Return")\n  root.update()\n  root.destroy()\n  self.assertEqual(self.key.keysym,"Return")\n'
            session.call('Write',{'file_path':'test_main.py','content':valid})
            self.assertEqual((session.root/'test_main.py').read_text(),valid)
            # Unknown/reassigned objects remain outside static type attribution.
            unknown=prefix+'  item=self.application.event_factory()\n  item.generate()\n  self.assertEqual(1,1)\n'
            validate_test_draft('test_main.py',unknown,session.plan,session.validation_goal)

    def test_gui_dependency_constructor_signatures_are_checked_before_freezing(self):
        from tests.test_native_coding import files
        from jarvis.codex_validation import validate_test_draft
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));session.validation_goal='Create a Python Tkinter desktop GUI'
            prefix='import unittest\nimport tkinter as tk\nfrom tkinter import Event as E\nclass Check(unittest.TestCase):\n def test_keyboard(self):\n'
            for call in ('E(keysym="Return")','E("Return")','tk.Event(keysym="Return")','tk.Tk(1,2,3,4,5,6,7)'):
                with self.subTest(call=call),self.assertRaisesRegex(ValueError,'Installed stdlib signature'):
                    session.call('Write',{'file_path':'test_main.py','content':prefix+'  event = '+call+'\n  self.assertEqual(1,1)\n'})
                self.assertFalse((session.root/'test_main.py').exists());self.assertFalse(session.uncertain())
            valid=prefix+'  event = E()\n  event.keysym = "Return"\n  self.assertEqual(event.keysym, "Return")\n'
            session.call('Write',{'file_path':'test_main.py','content':valid})
            with self.assertRaisesRegex(ValueError,'assertions are fixed'):
                session.call('Write',{'file_path':'test_main.py','content':valid.replace('E()','E(keysym="Return")')})
            self.assertEqual((session.root/'test_main.py').read_text(),valid)
            # No execution/import of application code and no attribution through shadowed names.
            shadow='import unittest\nfrom tkinter import Event\ndef Event(value): return value\nclass Check(unittest.TestCase):\n def test_value(self): self.assertEqual(Event(1),1)\n'
            validate_test_draft('test_main.py',shadow,session.plan,session.validation_goal)
            validate_test_draft('test_main.py',prefix+'  E(keysym="Return")\n',session.plan,'Validate a Python network library')

    def test_gui_mainloop_drafts_are_rejected_without_freezing_or_rewriting_tests(self):
        from tests.test_native_coding import files
        from jarvis.codex_validation import validate_test_draft
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));session.validation_goal='Create a Python Tkinter desktop GUI'
            prefix='import unittest\nfrom tkinter import mainloop as loop\nclass Check(unittest.TestCase):\n def setUp(self):\n'
            for call in ('self.root.mainloop()','tk.mainloop()','mainloop()','loop()'):
                draft=prefix+'  '+call+'\n def test_display(self): self.assertEqual(1,1)\n'
                with self.subTest(call=call),self.assertRaisesRegex(ValueError,'persistent mainloop'):
                    session.call('Write',{'file_path':'test_main.py','content':draft})
                self.assertFalse((session.root/'test_main.py').exists());self.assertFalse(session.uncertain())
            valid=prefix+'  self.root.update()\n def test_display(self):\n  self.button.invoke()\n  self.root.update_idletasks()\n  self.assertEqual(self.display.get(), "5")\n'
            session.call('Write',{'file_path':'test_main.py','content':valid})
            with self.assertRaisesRegex(ValueError,'assertions are fixed'):
                session.call('Write',{'file_path':'test_main.py','content':valid.replace('self.root.update()','self.root.mainloop()')})
            self.assertEqual((session.root/'test_main.py').read_text(),valid)
            validate_test_draft('test_main.py',prefix+'  mainloop()\n def test_api(self): self.assertEqual(1,1)\n',session.plan,'Validate a Python network library')

    def test_gui_callback_replacements_are_rejected_before_test_freezing(self):
        from tests.test_native_coding import files
        from jarvis.codex_validation import validate_test_draft
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));session.validation_goal='Create a Python Tkinter desktop GUI'
            prefix='import unittest\nclass Check(unittest.TestCase):\n def test_keyboard(self):\n'
            for mutation in ("self.root.bind('<Key>', lambda e: self.fake())",
                             "self.root.bind('<Key>', lambda e: self.fake(), add='+')",
                             "self.root.bind_class('Entry', '<Key>', self.fake)",
                             "self.button.configure(command=self.fake)",
                             "self.button['command'] = self.fake",
                             "self.root.unbind('<Key>')"):
                with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'original controls'):
                    session.call('Write',{'file_path':'test_main.py','content':prefix+'  '+mutation+'\n'})
                self.assertFalse((session.root/'test_main.py').exists());self.assertFalse(session.uncertain())
            valid=prefix+"  self.button.invoke()\n  self.root.event_generate('<Key-5>')\n  self.root.update()\n  self.assertEqual(self.display.get(), '5')\n"
            session.call('Write',{'file_path':'test_main.py','content':valid})
            with self.assertRaisesRegex(ValueError,'assertions are fixed'):
                session.call('Write',{'file_path':'test_main.py','content':valid.replace("'5'","'6'")})
            # Non-GUI tests and binding queries are not callback replacements.
            validate_test_draft('test_main.py',prefix+"  self.root.bind('<Key>')\n",session.plan,session.validation_goal)
            validate_test_draft('test_main.py',prefix+"  self.root.bind('<Key>', self.fake)\n",session.plan,'Validate a Python network library')

    def test_failed_test_only_worker_stops_without_read_loop_or_source_repair(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from jarvis.coding_files import UncertainCoding
        from tests.test_native_coding import TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            original='def add(a,b): return a-b\n';(root/'main.py').write_text(original)
            plan={'files':[{'path':'main.py','role':'logic','purpose':'Preserved existing implementation'},
                           {'path':'test_main.py','role':'test','purpose':'Verify actual addition'}],
                  'checks':[{'kind':'python_tests','path':'test_main.py'}]}
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            proposals=[{'tool':'Read','arguments':{'file_path':'main.py'}},
                       {'tool':'Write','arguments':{'file_path':'test_main.py','content':TEST}}]
            with patch('jarvis.native_coding.infer',side_effect=proposals) as infer:
                with self.assertRaisesRegex(UncertainCoding,'Test-only verification failed'):
                    run(coder,root,'Add verification; preserve implementation',initial_plan=plan,
                        allowed_paths=['test_main.py'],return_receipt=True)
            self.assertEqual(infer.call_count,2);self.assertEqual((root/'main.py').read_text(),original)
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_new_assertions_require_fresh_existing_implementation_read(self):
        from tests.test_native_coding import files,TEST
        from jarvis.native_coding import scoped_schema
        from jarvis.structured_output import validate_contract
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));source=session.root/'main.py';source.write_text('def add(a,b): return a+b\n')
            self.assertEqual(session.pending_test_reads(),['main.py'])
            with self.assertRaisesRegex(ValueError,'existing implementation/protocol'):
                session.call('Write',{'file_path':'test_main.py','content':TEST})
            self.assertFalse((session.root/'test_main.py').exists())
            request=json.loads((session.run/'request.json').read_text());request.update(project=str(session.root),validation_contract=session.plan)
            (session.run/'request.json').write_text(json.dumps(request))
            schema=scoped_schema(session.run,force_tool='Read',force_read_paths=['main.py'])
            validate_contract(schema,{'tool':'Read','arguments':{'file_path':'main.py'}})
            with self.assertRaises(ValueError):validate_contract(schema,{'tool':'Write','arguments':{'file_path':'test_main.py','content':TEST}})
            session.call('Read',{'file_path':'main.py'});self.assertFalse(session.pending_test_reads())
            source.write_text('def add(a,b): return a-b\n')
            self.assertEqual(session.pending_test_reads(),['main.py'])
            with self.assertRaisesRegex(ValueError,'existing implementation/protocol'):
                session.call('Write',{'file_path':'test_main.py','content':TEST})
            session.call('Read',{'file_path':'main.py'});session.call('Write',{'file_path':'test_main.py','content':TEST})
            self.assertEqual((session.root/'test_main.py').read_text(),TEST)

    def test_stalled_failed_check_advances_to_read_then_focused_edit(self):
        from jarvis.native_coding import run,scoped_schema
        from jarvis.coder import Coder
        from jarvis.structured_output import validate_contract
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            proposals=iter([{'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a-b\n'}}]+
                [{'tool':'Read','arguments':{'file_path':'test_main.py'}}]+
                [{'tool':'Read','arguments':{'file_path':'main.py'}},
                 {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b'}}])
            modes=[]
            def infer(messages,options,*args):
                modes.append((options.get('native_required_tool'),options.get('native_required_edit_paths')))
                proposal=next(proposals)
                schema=scoped_schema(args[-1],options.get('native_session_ids'),options.get('native_required_tool'),
                    options.get('native_required_read_paths'),options.get('native_required_edit_paths'))
                validate_contract(schema,proposal)
                return proposal
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertEqual(modes[-2][0],'Read');self.assertEqual(modes[-1],('Edit',['main.py']))
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_worker_context_names_are_not_extra_user_output_requests(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from jarvis.codex_validation import inspect
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            coder.validation_goal='Implement addition with real tests'
            with patch('jarvis.native_coding.infer',return_value={'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'}}):
                result=run(coder,root,'Assigned addition. Model interface prose mentions unrelated.py.',initial_plan=plan(),
                    allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertFalse((root/'unrelated.py').exists())
            # A filename actually requested by the user still fails strictly.
            errors,_=inspect(root,plan(),['main.py'],'Implement addition and unrelated.py')
            self.assertTrue(any(e['path']=='unrelated.py' for e in errors))

    def test_inference_transport_timeout_is_retained_and_only_inference_is_regenerable(self):
        from jarvis.native_coding import infer
        from requests.exceptions import ReadTimeout
        class Client:
            post=lambda *a,**k:None
            def __enter__(self):return self
            def __exit__(self,*args):return False
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder)
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),\
                    patch('jarvis.knowledge_worker.chat',side_effect=ReadTimeout('injected local stream timeout')):
                with self.assertRaisesRegex(ModelOutputError,'no tool action executed'):
                    infer([{'role':'user','content':'Controlled read-only inference fault'}],{'coder':'qwen3.5:9b'},
                        lambda:False,time.monotonic()+10,lambda *args:None,run)
            metadata=json.loads(next(run.glob('model-responses/*/metadata.json')).read_text())
            self.assertEqual(metadata['error_type'],'ReadTimeout');self.assertFalse(metadata['completed'])
            self.assertFalse((run/'file-events.jsonl').exists())

    def test_large_repair_source_requires_bounded_slice_before_edit(self):
        from jarvis.native_coding import run,scoped_schema
        from jarvis.coder import Coder
        from jarvis.structured_output import validate_contract
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            source='# fixture filler\n'*600+'def add(a,b): return a-b\n'
            proposals=iter([{'tool':'Write','arguments':{'file_path':'main.py','content':source}}]+
                [{'tool':'Read','arguments':{'file_path':'test_main.py'}}]+
                [{'tool':'Read','arguments':{'file_path':'main.py'}},
                 {'tool':'read_slice','arguments':{'file_path':'main.py','start':598,'count':10}},
                 {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b'}}])
            modes=[]
            def infer(messages,options,*args):
                modes.append(options.get('native_required_tool'));proposal=next(proposals)
                schema=scoped_schema(args[-1],options.get('native_session_ids'),options.get('native_required_tool'),
                    options.get('native_required_read_paths'),options.get('native_required_edit_paths'),options.get('native_read_line_limit',24))
                validate_contract(schema,proposal)
                if modes[-1]=='read_slice':
                    invalid={'tool':'read_slice','arguments':{'file_path':'main.py','count':80}}
                    with self.assertRaises(ValueError):validate_contract(schema,invalid)
                return proposal
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(modes[-3:],['Read','read_slice','Edit'])
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_isolated_worker_handoff_uses_original_research_channel_without_parent_writes(self):
        from jarvis.native_coding import run
        from jarvis.coder import Coder
        from tests.test_native_coding import plan,TEST
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);origin=base/'original';origin.mkdir();(origin/'sentinel.txt').write_text('unchanged')
            root=base/'worker';root.mkdir();(root/'test_main.py').write_text(TEST)
            seen=[]
            def handoff(project):
                seen.append(project)
                return [{'name':'Validated candidate fixture','source':'controlled-regression','copy_allowed':False}]
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            coder.research_project_root=origin;coder.native_actions=SimpleNamespace(code_intel=SimpleNamespace(handoff=handoff))
            calls=[]
            def infer(messages,*args):
                calls.append(messages)
                if len(calls)==1:return {'tool':'Read','arguments':{'file_path':'test_main.py'}}
                self.assertIn('Validated candidate fixture',str(messages))
                return {'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'}}
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(seen,[origin])
            self.assertEqual([p.name for p in origin.iterdir()],['sentinel.txt'])
            self.assertEqual((origin/'sentinel.txt').read_text(),'unchanged')


if __name__=='__main__':unittest.main()
