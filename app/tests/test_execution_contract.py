"""Actual failed-test calls constrain generic owned function repair, not app templates."""
import ast,hashlib,json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from jarvis.coder import Coder
from jarvis.codex_validation import validate_project
from jarvis.codex_unittest_check import read_evidence
from jarvis.execution_contract import focus,render,context,schema as function_schema,compile_definitions,function_id,statement_cells,compile_statements
from jarvis.native_coding import run,scoped_schema,StalledCoding
from jarvis.structured_output import ModelOutputError,validate_contract
from jarvis.source_observation import exact_python_edit_spans

SOURCE=('class Service:\n def __init__(self): self.private="DO_NOT_COLLECT_VALUE"\n'
        ' def ready(self): return True\n def send(self): return "bad"\n')
FROZEN=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
        ' def setUp(self): self.service=Service()\n'
        ' def test_ready(self): self.assertTrue(self.service.ready())\n'
        ' def test_send(self): self.assertEqual(self.service.send(),"ok")\n')
PLAN={'files':[{'path':'worker.py','role':'logic','purpose':'Service'},
               {'path':'test_worker.py','role':'test','purpose':'Fixed checks'}],
      'checks':[{'kind':'python_tests','path':'test_worker.py'}]}

LONG_SOURCE=('class Service:\n def send(self, route):\n  token = route\n'
    +''.join(('  if' if index==0 else '  elif')+' token == "legacy_'+str(index)+'":\n   return "legacy response preserved_'+str(index)+'"\n' for index in range(18))
    +'  return "bad"\n def other(self, route):\n  token = route\n  return token\n')
LONG_TEST=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
    ' def setUp(self): self.service=Service()\n'
    ' def test_legacy(self): self.assertEqual(self.service.send("legacy_0"),"legacy response preserved_0")\n'
    ' def test_other(self): self.assertEqual(self.service.other("west"),"west")\n'
    ' def test_west(self): self.assertEqual(self.service.send("west"),"WEST")\n'
    ' def test_east(self): self.assertEqual(self.service.send("east"),"EAST")\n')


def fixture(base):
    project=base/'project';project.mkdir();ledger=base/'ledger';ledger.mkdir()
    (project/'worker.py').write_text(SOURCE);(project/'test_worker.py').write_text(FROZEN)
    return project,ledger


class ExecutionContract(unittest.TestCase):
    def test_python_source_representation_is_ast_equivalent_and_keeps_original_language_bounds(self):
        from jarvis.execution_contract import source_nodes
        text='value = source\nif value:\n receiver.send(value)\ntry:\n receiver.flush()\nexcept RuntimeError as error:\n raise error\n'
        self.assertEqual(ast.dump(ast.Module(body=source_nodes(text),type_ignores=[])),ast.dump(ast.parse(text)))
        for bad in ['import os','for x in values:\n receiver.send(x)','def helper(): return True',
                'with receiver: receiver.send()', 'a = b = source','return', 'raise Error from cause',
                'try:\n receiver.send()\nfinally:\n receiver.close()',
                'if ready:\n if other:\n  receiver.send()', 'receiver.send()\n'*9,
                'if ready:\n'+''.join(' receiver.send()\n' for _ in range(5))]:
            with self.subTest(bad=bad),self.assertRaises(ModelOutputError):source_nodes(bad)

    def test_real_worker_python_statements_use_same_scope_freeze_and_candidate_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project,_=fixture(base)
            (project/'worker.py').write_text(LONG_SOURCE);(project/'test_worker.py').write_text(LONG_TEST)
            calls=[]
            def infer(messages,options,*args):
                calls.append(options)
                if len(calls)==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                if len(calls)==2:return {'tool':'run_checks','arguments':{}}
                if len(calls)==3:return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                scope=options['native_exact_edit_spans'];contract=scope['function_contract']
                self.assertEqual(contract['statement_representation'],'python_source')
                self.assertIn('source is complete Python STATEMENTS',json.dumps(messages))
                change={'function_id':'send:2','statement_id':0,'placement':'after',
                    'source':'if token in ("west", "east"):\n return token.upper()'}
                value={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':scope['sha256'],'changes':[change]}}
                schema=scoped_schema(args[-1],force_tool='edit_batch',force_edit_paths=['worker.py'],force_edit_spans=scope)
                validate_contract(schema,value)
                nodes=json.loads(json.dumps(value));nodes['arguments']['changes'][0].pop('source')
                nodes['arguments']['changes'][0]['statements']=[{'kind':'expr','expression':'receiver.send()'}]
                with self.assertRaises(ValueError):validate_contract(schema,nodes)
                return value
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_require_repair_progress':True,'native_execution_function_repair':True,
                'native_statement_representation':'python_source','native_max_repairs':6,'native_max_turns':16}))
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),4)
            self.assertEqual((project/'test_worker.py').read_text(),LONG_TEST)
            proof=result['function_renderings'][0]['changes'][0]
            self.assertTrue(proof['model_statement_ast_preserved']);self.assertFalse(proof['controller_supplied_body'])

    def test_focused_correction_retains_rejected_proposal_after_history_is_rebuilt(self):
        for mode in ('compiler','inference','repeat','combined'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);project,_=fixture(base)
                (project/'worker.py').write_text(LONG_SOURCE);(project/'test_worker.py').write_text(LONG_TEST)
                attempts=[];rejected=[]
                def infer(messages,options,stop,deadline,report,run_path):
                    attempts.append(options)
                    if len(attempts)==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                    if len(attempts)==2:return {'tool':'run_checks','arguments':{}}
                    if options.get('native_required_tool')=='Read':return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                    scope=options['native_exact_edit_spans'];contract=scope['function_contract']
                    change={'function_id':'send:2','statement_id':0,'placement':'after',
                        'statements':[{'kind':'if','condition':'token in ("west", "east")',
                                      'body':[{'kind':'return','expression':'token.upper()'}]}]}
                    proposal={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':scope['sha256'],'changes':[change]}}
                    if not rejected:
                        bad=json.loads(json.dumps(proposal));bad['arguments']['changes']*=2;rejected.append(bad)
                        if mode=='combined':bad['arguments']['changes'][0]['statements']=[{'kind':'expr','expression':'token = route'}]
                        if mode=='inference':
                            error=ModelOutputError('Controlled complete proposal rejection.');error.previous_proposal=bad;raise error
                        return bad
                    prefix='Previous confirmed pre-save rejection in this unchanged scope (DATA): '
                    feedback=json.loads(next(row['content'][len(prefix):] for row in messages if row['content'].startswith(prefix)))
                    self.assertEqual(feedback['rejected_proposal'],rejected[0])
                    self.assertEqual(feedback['source_sha256'],scope['sha256'])
                    self.assertEqual(feedback['case_id'],contract['case_id'])
                    self.assertFalse(feedback['source_saved']);self.assertFalse(feedback['action_executed'])
                    self.assertIn('different proposal',feedback['instruction'])
                    if mode!='inference':self.assertIn('combine all nodes',feedback['error'])
                    if mode=='combined':
                        self.assertIn('assignment is a statement',feedback['error'])
                        self.assertTrue(any('Duplicate function statement selector' in row['error'] for row in feedback['validation_errors']))
                        self.assertTrue(any('assignment is a statement' in row['error'] for row in feedback['validation_errors']))
                    self.assertEqual((project/'worker.py').read_text(),LONG_SOURCE)
                    return rejected[0] if mode=='repeat' else proposal
                coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                    'native_require_repair_progress':True,'native_execution_function_repair':True,'native_max_repairs':6,'native_max_turns':16}))
                with patch('jarvis.native_coding.infer',side_effect=infer):
                    if mode=='repeat':
                        with self.assertRaisesRegex(StalledCoding,'Identical executed-function.*before dispatch'):
                            run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
                        result=json.loads(next((base/'.jarvis-runtime/native-code').glob('*/result.json')).read_text())
                        tools=[json.loads(line) for line in (Path(result['directory'])/'tools.jsonl').read_text().splitlines()]
                        self.assertEqual(sum(row['tool']=='edit_batch' for row in tools),1)
                        self.assertEqual((project/'worker.py').read_text(),LONG_SOURCE)
                    else:
                        result=run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
                        self.assertTrue(result['validation']['passed'])
                self.assertEqual((project/'test_worker.py').read_text(),LONG_TEST)
                self.assertEqual(len(attempts),5 if mode=='inference' else 6)
                self.assertEqual(len(result['function_feedback_handoffs']),1)
                self.assertEqual(result['function_feedback_handoffs'][0]['rejected_proposal'],rejected[0])

    def test_oversize_rejected_proposal_retains_selectors_without_truncated_source(self):
        from jarvis.execution_contract import rejection_feedback
        contract={'source_sha256':'a'*64,'case_id':'test_worker.Checks.test_send'}
        proposal={'tool':'edit_batch','arguments':{'changes':[{'function_id':'send:2','statement_id':0,'placement':'replace',
            'statements':[{'kind':'expr','expression':'PRIVATE_LONG_SOURCE'*200}]}]}}
        value=json.loads(rejection_feedback(ValueError('Rejected before save'),proposal,contract))
        self.assertNotIn('rejected_proposal',value)
        self.assertNotIn('PRIVATE_LONG_SOURCE',json.dumps(value))
        self.assertEqual(value['rejected_selectors'],[{'function_id':'send:2','statement_id':0,'placement':'replace'}])
        self.assertEqual(len(value['rejected_proposal_sha256']),64)

    def test_independent_statement_errors_are_collected_before_any_function_splice_or_save(self):
        contract={'functions':[{'function':'send','definition_line':2}]}
        contract['statement_cells']=statement_cells(LONG_SOURCE,contract['functions'])
        changes=[{'function_id':'send:2','statement_id':0,'placement':'replace',
            'statements':[{'kind':'expr','expression':'token = route'}]},
            {'function_id':'send:2','statement_id':0,'placement':'after',
             'statements':[{'kind':'expr','expression':'receiver.send()'}]}]
        with self.assertRaises(ModelOutputError) as caught:compile_statements(LONG_SOURCE,{'changes':changes},contract)
        message=str(caught.exception)
        self.assertIn('assignment is a statement',message);self.assertIn('Duplicate function statement selector',message)
        self.assertIn('"change_index":0',message);self.assertIn('"change_index":1',message)
        self.assertIn('No source saved',message)
        self.assertEqual(len(caught.exception.validation_errors),2)

    def test_expression_patterns_accept_real_python_and_reject_physical_newlines(self):
        from jarvis.execution_contract import node_schema,program_nodes
        for expression in ['current', 'str(number)', 'range(3)', "r'\\n'", "'north'", 'receiver.send()']:
            value={'kind':'expr','expression':expression}
            validate_contract(node_schema(),value)
            self.assertEqual(len(program_nodes([value])),1)
        for expression in ['first\nsecond','first\rsecond','trailing\n','trailing\r']:
            with self.assertRaises(ValueError):validate_contract(node_schema(),{'kind':'expr','expression':expression})
        for name in ['error','problem_2','_caught']:
            value={'kind':'try','body':[{'kind':'expr','expression':'receiver.send()'}],
                   'handlers':[{'exception':'RuntimeError','name':name,'body':[{'kind':'raise','expression':name}]}]}
            validate_contract(node_schema(),value)
            self.assertEqual(len(program_nodes([value])),1)
        for name in ['2error','bad-name','name\\w','trailing\n']:
            with self.assertRaises(ValueError):validate_contract(node_schema(),{'kind':'try','body':[{'kind':'expr','expression':'1'}],
                'handlers':[{'exception':'RuntimeError','name':name,'body':[{'kind':'raise','expression':'error'}]}]})

    def test_structured_python_nodes_compile_complete_control_flow_without_source_blocks(self):
        from jarvis.execution_contract import node_schema,program_nodes
        statements=[{'kind':'assign','target':'value','expression':"int('bad')"}]
        handler={'exception':'ValueError','body':[{'kind':'return','expression':'7'}]}
        value={'kind':'try','body':statements,'handlers':[handler]}
        validate_contract(node_schema(),value)
        nodes=program_nodes([value]);module=ast.Module(body=[ast.FunctionDef(name='probe',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),
            body=nodes,decorator_list=[])],type_ignores=[])
        namespace={};exec(compile(ast.fix_missing_locations(module),'<controlled grammar fixture>','exec'),namespace)
        self.assertEqual(namespace['probe'](),7)
        for bad in [{'kind':'expr','expression':'if value:'},{'kind':'assign','target':'value + 1','expression':'2'},
                    {'kind':'try','body':statements,'handlers':[{**handler,'exception':"(ValueError, unsafe())"}]}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):program_nodes([bad])
        with self.assertRaises(ValueError):validate_contract(node_schema(),{'kind':'if','condition':'True','body':[]})

    def test_long_function_cells_are_contextual_and_preserve_unedited_function_signature_and_body(self):
        functions=[{'function':'send','definition_line':2}];cells=statement_cells(LONG_SOURCE,functions)
        self.assertTrue(any(row['statement_id']==0 for row in cells))
        contract={'functions':functions,'statement_cells':cells}
        program=[{'kind':'if','condition':'token in ("west", "east")','body':[{'kind':'return','expression':'token.upper()'}]}]
        args={'changes':[{'function_id':'send:2','statement_id':0,'placement':'after','statements':program}]}
        validate_contract(function_schema(contract),args['changes'][0])
        result,proof=compile_statements(LONG_SOURCE,args,contract)
        self.assertTrue(result.endswith(LONG_SOURCE[LONG_SOURCE.index(' def other'):]))
        before=ast.parse(LONG_SOURCE).body[0].body[0];after=ast.parse(result).body[0].body[0]
        self.assertEqual(ast.dump(before.args),ast.dump(after.args))
        self.assertEqual(ast.dump(before.body[1]),ast.dump(after.body[2]))
        self.assertTrue(proof[0]['untouched_body_statements_retained']);self.assertFalse(proof[0]['controller_supplied_body'])
        for row in [{'function_id':'send:2','statement_id':99,'placement':'after','statements':program},
                    {'function_id':'send:2','statement_id':0,'source':'def send(self): return "x"'},
                    {'function_id':'send:2','statement_id':0,'placement':'after','statements':[{'kind':'expr','expression':'if True:'}]}]:
            with self.subTest(row=row),self.assertRaises((ValueError,SyntaxError)):
                compile_statements(LONG_SOURCE,{'changes':[row]},contract)
        with self.assertRaises(ModelOutputError):compile_statements(LONG_SOURCE,{'changes':args['changes']*2},contract)

    def test_real_worker_repairs_long_function_with_small_model_statement_and_no_global_duplicate_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project,ledger=fixture(base)
            (project/'worker.py').write_text(LONG_SOURCE);(project/'test_worker.py').write_text(LONG_TEST)
            calls=[]
            def infer(messages,options,*args):
                calls.append(options);index=len(calls)
                if index==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index==3:return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                self.assertEqual(index,4);self.assertEqual(options['native_required_tool'],'edit_batch')
                scope=options['native_exact_edit_spans'];contract=scope['function_contract']
                self.assertIn('statement_cells',contract);self.assertIn('including callers and state declarations',json.dumps(messages))
                self.assertIn('STRUCTURED Python nodes',json.dumps(messages))
                schema=scoped_schema(args[-1],force_tool='edit_batch',force_edit_paths=['worker.py'],force_edit_spans=scope)
                value={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':scope['sha256'],
                    'changes':[{'function_id':'send:2','statement_id':0,'placement':'after',
                                'statements':[{'kind':'if','condition':'token in ("west", "east")',
                                    'body':[{'kind':'return','expression':'token.upper()'}]}]}]}}
                validate_contract(schema,value);return value
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_require_repair_progress':True,'native_execution_function_repair':True,'native_max_repairs':6,'native_max_turns':16}))
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),4)
            self.assertTrue(result['candidate_decisions'][0]['verified_case_progress'])
            self.assertTrue((project/'worker.py').read_text().endswith(LONG_SOURCE[LONG_SOURCE.index(' def other'):]))
            self.assertEqual((project/'test_worker.py').read_text(),LONG_TEST)
            proof=result['function_renderings'][0]['changes'][0]
            self.assertTrue(proof['model_statement_ast_preserved']);self.assertTrue(proof['original_signature_retained'])

    def test_typed_definition_wire_omits_old_source_and_keeps_actual_syntax_feedback(self):
        old=' def send(self): return "bad"'
        contract={'functions':[{'function':'send','definition_line':4}]}
        row={'function_id':'send:4','definition':'def send(self): return "ok"'}
        validate_contract(function_schema(contract),row)
        compiled=compile_definitions({'changes':[row]},contract,[old])
        self.assertEqual(compiled['changes'][0],{'old_string':old,'new_string':row['definition']})
        for bad in [{'old_string':old,'new_string':row['definition']},{**row,'function_id':'unknown:1'},
                    {**row,'definition':'x'*1201}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_contract(function_schema(contract),bad)
        with self.assertRaises(ModelOutputError):compile_definitions({'changes':[row,row]},contract,[old])
        broken='def send(self):\n try:\n  return "ok"'
        with self.assertRaisesRegex(ModelOutputError,'expected.*except.*replacement line.*1200'):
            render({'changes':[{'old_string':old,'new_string':broken}]},contract)

    def test_zero_body_calls_remain_visible_without_inventing_an_edit_target_and_expire_on_source_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            project,ledger=fixture(Path(folder))
            frozen=FROZEN.replace('self.assertEqual(self.service.send(),"ok")','self.assertEqual(1,2)')
            (project/'test_worker.py').write_text(frozen)
            value=validate_project(project,ledger,'Repair service',[],PLAN,lambda:False,lambda *a:None,observe_execution=True)
            files=SimpleNamespace(root=project,fixed_tests={'test_worker.py':value['hashes']['test_worker.py']})
            packet=context(value,files);self.assertTrue(packet['cases'][0]['test_body_observed'])
            self.assertEqual(packet['cases'][0]['body_calls'],[])
            self.assertEqual(packet['cases'][0]['setup_calls'][0]['function'],'__init__')
            source={'file_path':'worker.py','sha256':value['hashes']['worker.py'],'current_source':SOURCE}
            self.assertIsNone(focus(source,value,exact_python_edit_spans(SOURCE),files.fixed_tests))
            (project/'worker.py').write_text(SOURCE+'# external source drift\n')
            self.assertIsNone(context(value,files))

    def test_actual_calls_are_phase_and_source_bound_without_values_and_bad_optional_facts_preserve_outcomes(self):
        with tempfile.TemporaryDirectory() as folder:
            project,ledger=fixture(Path(folder));before={path.name:path.read_bytes() for path in project.iterdir()}
            value=validate_project(project,ledger,'Repair service',[],PLAN,lambda:False,lambda *a:None,observe_execution=True)
            group=value['owned_execution_observations'][0];self.assertEqual(group['test_path'],'test_worker.py')
            self.assertEqual(len(group['cases']),1);row=group['cases'][0]
            self.assertFalse(row['partial']);self.assertTrue(row['test_body_seen'])
            self.assertEqual(row['case_id'],'test_worker.Checks.test_send')
            self.assertEqual([(call['function'],call['phase']) for call in row['calls']],[('__init__','setup'),('send','test_body')])
            self.assertNotIn('DO_NOT_COLLECT_VALUE',json.dumps(group))
            source={'file_path':'worker.py','sha256':value['hashes']['worker.py'],'current_source':SOURCE}
            contract=focus(source,value,exact_python_edit_spans(SOURCE),{'test_worker.py':value['hashes']['test_worker.py']})
            self.assertEqual(contract['functions'],[{'function':'send','definition_line':4}])
            self.assertIsNone(focus({**source,'sha256':'0'*64},value,exact_python_edit_spans(SOURCE),{'test_worker.py':value['hashes']['test_worker.py']}))
            facts=next(ledger.glob('python-runtime-*.json'));data=json.loads(facts.read_text());workspace=Path(data['root'])
            initial=read_evidence(facts,workspace,'test_worker.py',value['hashes']['test_worker.py'])
            for mode in ('sha','outside','missing','duplicate','oversize'):
                changed=json.loads(json.dumps(data));call=changed['owned_execution'][0]['calls'][0]
                if mode=='sha':call['source_sha256']='0'*64
                if mode=='outside':call['source_path']='../outside.py'
                if mode=='missing':call['source_path']='missing.py'
                if mode=='duplicate':changed['owned_execution']*=2
                if mode=='oversize':changed['owned_execution'][0]['calls']*=9
                facts.write_text(json.dumps(changed))
                observed=read_evidence(facts,workspace,'test_worker.py',value['hashes']['test_worker.py'])
                self.assertEqual(observed['execution'],[]);self.assertEqual(observed['outcomes'],initial['outcomes'])
            self.assertEqual({path.name:path.read_bytes() for path in project.iterdir() if path.is_file()},before)

    def test_rendering_preserves_model_ast_signature_and_scope(self):
        old='    def send(self, value: str = "x") -> str:\n        return value'
        contract={'functions':[{'function':'send','definition_line':1}]}
        new='def send(self, value: str = "x") -> str:\n return "\\n" + value'
        args={'changes':[{'old_string':old,'new_string':new}]}
        result,proof=render(args,contract)
        self.assertTrue(result['changes'][0]['new_string'].startswith('    def send'))
        self.assertEqual(ast.dump(ast.parse(new)),ast.dump(ast.parse(__import__('textwrap').dedent(result['changes'][0]['new_string']))))
        self.assertFalse(proof[0]['controller_supplied_body'])
        for bad in ['self.values = {}','def other(self): return "ok"',
                    'def send(self): return "ok"',new+'\noutside()',new.replace('-> str','-> int')]:
            with self.subTest(bad=bad),self.assertRaises(ModelOutputError):render({'changes':[{'old_string':old,'new_string':bad}]},contract)

    def test_real_worker_targets_executed_function_and_bounds_correction_without_initializer_escape(self):
        for mode in ('success','signature','incomplete','cap'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);project,_=fixture(base);calls=[]
                def infer(messages,options,stop,deadline,report,run_path):
                    calls.append(options);index=len(calls)
                    if index==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                    if index==2:return {'tool':'run_checks','arguments':{}}
                    if index==3 or index in (5,7) and mode in {'signature','cap'}:
                        return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                    scope=options['native_exact_edit_spans'];self.assertEqual(options['native_required_tool'],'edit_batch')
                    self.assertEqual(scope['old_strings'],[' def send(self): return "bad"'])
                    self.assertIsNone(options['native_diagnostic_window']);self.assertIn('Executed-function repair stage',json.dumps(messages))
                    schema=scoped_schema(run_path,force_tool='edit_batch',force_edit_paths=['worker.py'],force_edit_spans=scope)
                    value={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':scope['sha256'],
                        'changes':[{'function_id':function_id(scope['function_contract']['functions'][0]),'definition':'def send(self):\n return "ok"'}]}}
                    validate_contract(schema,value)
                    wrong=json.loads(json.dumps(value));wrong['arguments']['changes'][0]={'old_string':' def __init__(self): self.private="DO_NOT_COLLECT_VALUE"','new_string':'pass'}
                    with self.assertRaises(ValueError):validate_contract(schema,wrong)
                    if mode=='incomplete' and index==4:raise ModelOutputError('Controlled incomplete function response; no action executed.')
                    if mode=='signature' and index==4:value['arguments']['changes'][0]['definition']='def other(self): return "ok"'
                    if mode=='cap':value['arguments']['changes'][0]['definition']='def send(self): return "still_bad_'+str(index)+'"'
                    return value
                coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                    'native_require_repair_progress':True,'native_execution_function_repair':True,
                    'native_max_repairs':6,'native_max_turns':24}))
                with patch('jarvis.native_coding.infer',side_effect=infer):
                    if mode=='cap':
                        with self.assertRaisesRegex(StalledCoding,'failed twice'):run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
                        result=json.loads(next((base/'.jarvis-runtime/native-code').glob('*/result.json')).read_text())
                        self.assertEqual((project/'worker.py').read_text(),SOURCE);self.assertEqual(len(calls),7)
                    else:
                        result=run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
                        self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),{'success':4,'signature':6,'incomplete':5}[mode])
                self.assertEqual((project/'test_worker.py').read_text(),FROZEN)
                self.assertLessEqual(len(result['executed_function_stages']),2)
                self.assertFalse(any(row['controller_supplied_body'] for row in result['executed_function_stages']))


if __name__=='__main__':unittest.main()
