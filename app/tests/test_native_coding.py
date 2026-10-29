import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.coding_files import FileSession, patch_files, UncertainCoding
from jarvis.coding_processes import Processes
from jarvis.coding_programs import checked_argv, inventory
from jarvis.native_coding import run
from jarvis.coder import Coder


def plan():
    return {'files':[{'path':'main.py','role':'logic','purpose':'Implement addition'},
                     {'path':'test_main.py','role':'test','purpose':'Assert addition behavior'}],
            'checks':[{'kind':'python_tests','path':'test_main.py'}]}


def interface_plan(options,cause):
    if options.get('native_protocol_contract'):
        return {'tool':'update_plan','arguments':{'observed_cause':cause,
            'strategy':'owned_compatible_interface','uncertainty':'Fresh executable checks remain required.'}}
    return {'tool':'update_plan','arguments':{'observed_cause':cause,
        'permitted_strategy':'Preserve both forms with owned values.','verification':'Run unchanged checks.'}}


TEST='import unittest\nfrom main import add\nclass Addition(unittest.TestCase):\n def test_add(self):\n  self.assertEqual(add(2,3),5)\n  self.assertEqual(add(-2,3),1)\n'


def files(root):
    root.mkdir(exist_ok=True);run=root/'ledger';run.mkdir()
    (run/'request.json').write_text(json.dumps({'goal':'Create addition','require_validation':True,'test_first':True,'allowed_paths':['main.py','test_main.py']}))
    (run/'validation-contract.json').write_text(json.dumps(plan()))
    return FileSession(root,run)


class NativeCoding(unittest.TestCase):
    def test_ready_diagnosis_preempts_noop_patch_fallback_without_dispatching_patch(self):
        from jarvis.structured_output import ModelOutputError
        from jarvis.native_coding import StalledCoding
        frozen=('import unittest\nfrom main import Service\nclass Checks(unittest.TestCase):\n'
                ' def setUp(self):\n  self.service=Service()\n  self.nodes=self.service.nodes\n'
                ' def test_direct(self): self.assertEqual(self.nodes["a"].send(),"ok")\n'
                ' def test_indexed(self): self.assertEqual(self.nodes["b"][0].send(),"ok")\n')
        initial='class Service:\n def __init__(self): self.nodes={"a": [], "b": []}\n'
        corrected=('class Endpoint:\n def send(self): return "ok"\n'
                   ' def __getitem__(self,key):\n  if key!=0: raise IndexError(key)\n  return self\n'
                   'class Service:\n def __init__(self): self.nodes={"a": Endpoint(),"b": Endpoint()}\n')
        for completes in (True,False):
            with self.subTest(completes=completes),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);project=base/'project';project.mkdir()
                (project/'main.py').write_text(initial);(project/'test_main.py').write_text(frozen);calls=[]
                def inference(messages,options,*args):
                    calls.append(options);index=len(calls)
                    if index==1:return {'tool':'read_batch','arguments':{'paths':['main.py','test_main.py']}}
                    if index==2:return {'tool':'Edit','arguments':{'file_path':'main.py',
                        'old_string':'self.nodes={"a": [], "b": []}',
                        'new_string':'self.nodes={"a": [], "b": []} # neutral','replace_all':False}}
                    if index==3:
                        self.assertEqual((project/'main.py').read_text(),initial)
                        return {'tool':'Read','arguments':{'file_path':'main.py'}}
                    if index==4:
                        self.assertIn('coexisting_receiver_protocols',json.dumps(messages))
                        raise ModelOutputError('old_string and new_string are identical; no action executed')
                    if index==5:
                        self.assertEqual(options['native_required_tool'],'update_plan')
                        self.assertTrue(options['native_diagnostic_plan'])
                        self.assertNotIn('exact current context',json.dumps(messages))
                        if not completes:raise ModelOutputError('Controlled incomplete diagnosis; no action executed')
                        return interface_plan(options,'The owned values lack both required access forms.')
                    self.assertEqual(index,6);self.assertEqual(options['native_required_tool'],'Write')
                    return {'tool':'Write','arguments':{'file_path':'main.py','content':corrected}}
                coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                    'native_require_repair_progress':True,'native_max_repairs':6}))
                with patch('jarvis.native_coding.infer',side_effect=inference):
                    if completes:
                        result=run(coder,project,'Repair service',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
                        self.assertTrue(result['validation']['passed'])
                    else:
                        with self.assertRaises(StalledCoding):
                            run(coder,project,'Repair service',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
                        result=json.loads(next((base/'.jarvis-runtime/native-code').glob('*/result.json')).read_text())
                        self.assertEqual((project/'main.py').read_text(),initial)
                self.assertEqual(len(calls),6 if completes else 5)
                self.assertEqual(result['progress']['diagnostic_plan_attempts'],1)
                self.assertEqual(result['diagnostic_plans'][0]['rejected_repair_proposals'] if completes
                                 else result['progress']['rejected_repair_proposals'],2)
                self.assertFalse(any(row.get('native_required_tool')=='apply_patch' for row in calls))
                self.assertEqual((project/'test_main.py').read_text(),frozen)

    def test_atomic_edit_batch_saves_one_complete_postimage_and_refuses_partial_batches(self):
        from jarvis.coding_files import FileSession,UncertainCoding
        from jarvis.codex_files import digest
        from jarvis.codex_validation import validate_project
        from jarvis.native_coding import scoped_schema
        from jarvis.source_observation import exact_python_edit_spans
        from jarvis.structured_output import validate_contract
        source='def first():\n return 0\ndef second():\n return -1\n'
        frozen=('import unittest\nfrom main import first,second\nclass Checks(unittest.TestCase):\n'
            ' def test_first(self): self.assertEqual(first(),1)\n def test_second(self): self.assertEqual(second(),2)\n')
        for fault in (None,'overlap','stale','same','frozen','invalid_last','cancel','budget'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);root=base/'project';root.mkdir();ledger=base/'ledger';ledger.mkdir()
                (root/'main.py').write_text(source);(root/'test_main.py').write_text(frozen)
                (ledger/'request.json').write_text(json.dumps({'goal':'Repair controlled service.'}))
                (ledger/'validation-contract.json').write_text(json.dumps(plan()))
                files=FileSession(root,ledger);files.call('Read',{'file_path':'main.py'});seen=[]
                def candidate(name,content):
                    seen.append(content)
                    if fault=='cancel':raise UncertainCoding('Controlled cancellation; no batch saved.')
                files.candidate_check=candidate
                changes=[{'old_string':' return 0','new_string':' return 1'}, {'old_string':' return -1','new_string':' return 2'}]
                args={'file_path':'main.py','source_sha256':digest(root/'main.py'),'changes':changes}
                spans={'file_path':'main.py','sha256':args['source_sha256'],'old_strings':exact_python_edit_spans(source),'allow_batch':True}
                schema=scoped_schema(ledger,force_tool='edit_batch',force_edit_paths=['main.py'],force_edit_spans=spans)
                validate_contract(schema,{'tool':'edit_batch','arguments':args})
                if fault=='overlap':changes[1]={'old_string':'def first():\n return 0','new_string':'def first():\n return 9'}
                if fault=='stale':args['source_sha256']='0'*64
                if fault=='same':changes[0]['new_string']=changes[0]['old_string']
                if fault=='frozen':args['file_path']='test_main.py'
                if fault=='invalid_last':changes.append({'old_string':' invented context','new_string':' nope'})
                if fault=='budget':changes[0]['new_string']='x'*1201
                if fault:
                    with self.assertRaises(UncertainCoding if fault=='cancel' else ValueError):files.edit_batch(args)
                    self.assertEqual((root/'main.py').read_text(),source);self.assertEqual(files.changed(),[])
                else:
                    files.edit_batch(args)
                    self.assertEqual(len(seen),1);self.assertIn(' return 1',seen[0]);self.assertIn(' return 2',seen[0])
                    self.assertEqual(len([json.loads(s) for s in (ledger/'file-events.jsonl').read_text().splitlines() if json.loads(s)['stage']=='applied']),1)
                    self.assertTrue(validate_project(root,ledger,'Repair controlled service',[],plan(),lambda:False,lambda *a:None)['passed'])
                self.assertEqual((root/'test_main.py').read_text(),frozen)

    def test_normal_failed_check_edit_uses_exact_current_statement_schema(self):
        from jarvis.native_coding import scoped_schema
        from jarvis.structured_output import validate_contract
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            (root/'main.py').write_text('def add(a,b):\n return a-b\n');(root/'test_main.py').write_text(TEST)
            calls=[]
            def inference(messages,options,cancelled,deadline,report,run_dir):
                calls.append(options);index=len(calls)
                if index in (1,3):return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                self.assertEqual(index,4);self.assertEqual(options['native_required_tool'],'Edit')
                spans=options['native_exact_edit_spans'];self.assertIn(' return a-b',spans['old_strings'])
                self.assertTrue(any(m['content'].startswith('Grounded Edit stage.') for m in messages))
                schema=scoped_schema(run_dir,force_tool='Edit',force_edit_paths=['main.py'],force_edit_spans=spans)
                valid={'tool':'Edit','arguments':{'file_path':'main.py','old_string':' return a-b','new_string':' return a+b','replace_all':False}}
                validate_contract(schema,valid)
                with self.assertRaises(ValueError):
                    validate_contract(schema,{'tool':'Edit','arguments':{**valid['arguments'],'old_string':' return invented_context'}})
                return valid
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Repair addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),4)
            self.assertEqual(result['grounded_edit_stages'][0]['phase'],'normal_repair')
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_member_assignment_observations_are_bounded_source_facts_without_execution(self):
        from jarvis.source_observation import member_assignment_observations
        source=('raise RuntimeError("must never execute")\nclass Service:\n def __init__(self):\n'
            '  self.nodes = {}\n  handler = lambda value: value\n  item = make_node(handler)\n'
            '  self.nodes["a"] = item\n')
        rows=member_assignment_observations(source,{'nodes'})
        snippets={r['source'] for r in rows}
        self.assertIn('self.nodes = {}',snippets);self.assertIn('self.nodes["a"] = item',snippets)
        self.assertIn('item = make_node(handler)',snippets);self.assertIn('handler = lambda value: value',snippets)
        self.assertLessEqual(len(json.dumps(rows,ensure_ascii=False)),800)
        self.assertEqual(member_assignment_observations(source,{'unrelated'}),[])
        self.assertEqual(member_assignment_observations('invalid syntax !',{'nodes'}),[])
        self.assertEqual(member_assignment_observations(source+' '*80000,{'nodes'}),[])
        ambiguous=source.replace('  item = make_node(handler)','  item = first()\n  item = second()')
        self.assertFalse(any(r['kind']=='unique_local_definition' for r in member_assignment_observations(ambiguous,{'nodes'})))
        self.assertEqual(member_assignment_observations('class Service:\n @staticmethod\n def method(self):\n  self.nodes = {}\n',{'nodes'}),[])

    def test_current_member_facts_survive_compaction_with_fresh_hash_and_no_read_permission_grant(self):
        import hashlib
        from jarvis.native_coding import compact_history,current_test_interfaces
        from jarvis.coding_files import FileSession
        source=('raise RuntimeError("must never execute")\nclass Service:\n def __init__(self):\n'
            '  self.nodes = {}\n  item = make_node()\n  self.nodes["a"] = item\n')
        frozen=('import unittest\nfrom main import Service\nclass Checks(unittest.TestCase):\n'
            ' def setUp(self):\n  self.service=Service()\n  self.nodes=self.service.nodes\n'
            ' def test_forms(self):\n  self.nodes["a"].send()\n  self.nodes["b"][0].send()\n')
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();run=base/'run';run.mkdir()
            raw=source.replace('\n','\r\n').encode();(root/'main.py').write_bytes(raw);(root/'test_main.py').write_text(frozen)
            frozen_bytes=(root/'test_main.py').read_bytes()
            (run/'request.json').write_text(json.dumps({'goal':'Repair controlled service.'}))
            (run/'validation-contract.json').write_text(json.dumps(plan()))
            files=FileSession(root,run)
            messages=compact_history([{'role':'system','content':'Policy.'},{'role':'user','content':'Original goal.'},
                {'role':'assistant','content':'Read'},{'role':'user','content':'old_source_marker'*100},
                {'role':'assistant','content':'read_slice'},{'role':'user','content':'Unrelated current slice.'}],limit=100)
            self.assertNotIn('old_source_marker',json.dumps(messages))
            current=current_test_interfaces(messages,files)
            fact=next(m['content'] for m in current if m['content'].startswith('Current writable same-named member'))
            self.assertIn('self.nodes = {}',fact);self.assertIn(hashlib.sha256(raw).hexdigest(),fact)
            self.assertIn('coexisting_receiver_protocols',json.dumps(current));self.assertEqual(files.reads,{})
            self.assertEqual((root/'main.py').read_bytes(),raw)
            changed=raw.replace(b'self.nodes = {}',b'self.nodes = []');(root/'main.py').write_bytes(changed)
            refreshed=current_test_interfaces(messages,files)
            fact=next(m['content'] for m in refreshed if m['content'].startswith('Current writable same-named member'))
            self.assertIn(hashlib.sha256(changed).hexdigest(),fact);self.assertNotIn(hashlib.sha256(raw).hexdigest(),fact)
            self.assertEqual((root/'test_main.py').read_bytes(),frozen_bytes)
            files.allowed.remove('main.py')
            self.assertFalse(any(m['content'].startswith('Current writable same-named member') for m in current_test_interfaces(messages,files)))

    def test_selected_history_survives_inference_regeneration_without_becoming_a_current_check(self):
        from jarvis.structured_output import ModelOutputError
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            (root/'main.py').write_text('def add(a,b): return a-b\n');(root/'test_main.py').write_text(TEST)
            historical={'date':'2026-10-26','passed':False,
                'hashes':{'test_main.py':hashlib.sha256((root/'test_main.py').read_bytes()).hexdigest()},
                'errors':[{'path':'test_main.py','error':'ERROR: test_add (Addition)\nTraceback (most recent call last):\n'
                           '  File "old/test_main.py", line 5\nAttributeError: controlled_history_counterexample\n'}]}
            calls=[]
            def inference(messages,*args):
                calls.append(messages)
                self.assertIn('controlled_history_counterexample',json.dumps(messages))
                if len(calls)==1:raise ModelOutputError('Controlled incomplete inference; no action executed')
                if len(calls)==2:return {'tool':'read_batch','arguments':{'paths':['main.py','test_main.py']}}
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b','replace_all':False}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),
                        SimpleNamespace(options={'native_prior_validation_paths':['controlled-fixture-only']}))
            with patch('jarvis.workload_state.load_validation_history',return_value=([historical],[{'accepted':True,'fixture_only':True}])),patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Verify addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            # The pre-save baseline is now a real current failed check;
            # imported historical observations still do not count as checks.
            self.assertEqual(result['progress']['failure_history_versions'],1)
            validations=[json.loads(path.read_text()) for path in Path(result['directory']).glob('validation-*.json')]
            self.assertEqual(sorted(value['passed'] for value in validations if 'passed' in value),[False,True])
            self.assertEqual(len(calls),3)
            self.assertTrue(result['imported_failure_history'][0]['fixture_only'])
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_primary_library_exception_has_verified_installed_source_window(self):
        import traceback
        import tkinter
        from jarvis.source_observation import failure_context
        from jarvis.codex_unittest_check import observe_exception
        import sys
        # Exercise the actual stdlib argument expression without creating a
        # window or replacing any application callbacks or constructors.
        try:
            tkinter.Misc.cget(SimpleNamespace(tk=SimpleNamespace(call=lambda *a: None),_w='.'),0)
        except TypeError:
            error='ERROR: test_resource (Checks)\n'+traceback.format_exc()
            observation=observe_exception(sys.exc_info(),'test_resource')
        report={'path':'test_main.py','error':error,'runtime_failure_facts':[observation]}
        context=failure_context(report)
        window=context['installed_stdlib_source']
        self.assertEqual(window['module_path'],'tkinter/__init__.py')
        self.assertIn("'-' + key",window['numbered_source'])
        self.assertIn('__getitem__ = cget',window['numbered_source'])
        self.assertEqual(window['sha256'],hashlib.sha256(Path(tkinter.__file__).read_bytes()).hexdigest())
        self.assertLessEqual(len(json.dumps(window)),1000)
        self.assertEqual(window['observed_operands']['key'],{'type':'int','value':0})
        observation['frames'][0]['sha256']='0'*64
        self.assertNotIn('observed_operands',failure_context(report)['installed_stdlib_source'])
        observation['frames'][0]['sha256']=window['sha256'];observation['test_method']='test_other'
        self.assertNotIn('observed_operands',failure_context(report)['installed_stdlib_source'])

    def test_library_exception_window_refuses_external_and_invalid_frame_paths(self):
        import sysconfig
        from jarvis.source_observation import stdlib_failure_window
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'__init__.py';path.write_text('secret_fixture_data = 1\n')
            self.assertIsNone(stdlib_failure_window([(str(path),'1')]))
            library=Path(sysconfig.get_path('stdlib'))/'tkinter/__init__.py'
            self.assertIsNone(stdlib_failure_window([(str(library),'0')]))
            self.assertIsNone(stdlib_failure_window([(str(library),'999999')]))
            self.assertIsNone(stdlib_failure_window([(str(library.parent/'../../outside.py'),'1')]))

    def test_repeated_protocol_failure_gets_one_plan_before_fresh_guarded_replacement(self):
        frozen=('import unittest\nfrom main import Service\nclass Checks(unittest.TestCase):\n'
                ' def setUp(self):\n  self.service=Service()\n  self.nodes=self.service.nodes\n'
                ' def test_direct(self):\n  self.assertEqual(self.nodes["a"].send(), "ok")\n'
                ' def test_indexed(self):\n  self.assertEqual(self.nodes["b"][0].send(), "ok")\n')
        initial='class Service:\n def __init__(self): self.nodes={"a": [], "b": []}\n'
        corrected=('class Endpoint:\n def send(self): return "ok"\n'
                   ' def __getitem__(self, key):\n  if key != 0: raise IndexError(key)\n  return self\n'
                   'class Service:\n def __init__(self): self.nodes={"a": Endpoint(), "b": Endpoint()}\n')
        for succeeds,presave_rejections in ((True,False),(False,False),(True,True),(False,True)):
            with self.subTest(succeeds=succeeds,presave_rejections=presave_rejections), tempfile.TemporaryDirectory() as folder:
                base=Path(folder);root=base/'project';root.mkdir()
                (root/'main.py').write_text(initial);(root/'test_main.py').write_text(frozen)
                calls=[]
                def inference(messages,options,*args):
                    calls.append(options);index=len(calls)
                    plan_turn=6 if presave_rejections else 5
                    if index in (1,plan_turn-1,plan_turn+2):return {'tool':'Read','arguments':{'file_path':'main.py'}}
                    if index==2:return {'tool':'run_checks','arguments':{}}
                    if index==3:
                        if presave_rejections:
                            from jarvis.structured_output import ModelOutputError
                            raise ModelOutputError('old_string and new_string are identical; nothing executed')
                        return {'tool':'Write','arguments':{'file_path':'main.py','content':initial+'# observed version two\n'}}
                    if presave_rejections and index==4:
                        return {'tool':'apply_patch','arguments':{'patch':'*** Begin Patch\n*** Update File: main.py\n@@\n-missing_service_line\n+new_service_line\n*** End Patch'}}
                    if index==plan_turn:
                        self.assertEqual(options['native_required_tool'],'update_plan')
                        self.assertTrue(options['native_diagnostic_plan'])
                        self.assertFalse(any(m['role']=='assistant' for m in messages))
                        self.assertFalse(any(m['content'].startswith('Observed tool result') for m in messages))
                        self.assertTrue(messages[-1]['content'].startswith('Bounded root-cause planning stage.'))
                        self.assertTrue(any('coexisting_receiver_protocols' in m['content'] for m in messages))
                        self.assertTrue(any(m['content'].startswith('Current unresolved') for m in messages))
                        self.assertNotIn('UNVERIFIED_PLANNER_HYPOTHESIS',json.dumps(messages))
                        self.assertIn('Repair the service against its original interfaces',messages[1]['content'])
                        self.assertIn('read-only diagnostic stage',messages[0]['content'])
                        return interface_plan(options,'The receiver lacks both required access forms.')
                    if index==plan_turn+1:
                        self.assertEqual(options['native_required_tool'],'Write')
                        self.assertEqual(options['native_rewrite_paths'],['main.py'])
                        self.assertNotIn('read-only diagnostic stage',messages[0]['content'])
                        self.assertEqual((root/'main.py').read_text(),initial if presave_rejections else initial+'# observed version two\n')
                        self.assertEqual((root/'test_main.py').read_text(),frozen)
                        self.assertNotIn('UNVERIFIED_PLANNER_HYPOTHESIS',json.dumps(messages))
                        self.assertFalse(any(m['content'].startswith('Observed tool result') for m in messages))
                        self.assertTrue(any(m['content'].startswith('Unverified read-only plan') for m in messages))
                        self.assertIn('Repair the service against its original interfaces',messages[1]['content'])
                        return {'tool':'Write','arguments':{'file_path':'main.py',
                            'content':corrected if succeeds else initial+'# failed planned version\n'}}
                    self.assertEqual(index,plan_turn+3);self.assertFalse(options.get('native_diagnostic_plan'))
                    raise RuntimeError('bounded fixture exit')
                coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'native_max_repairs':6}))
                coder.validation_goal='Repair the service against its original interfaces'
                with patch('jarvis.native_coding.infer',side_effect=inference):
                    if succeeds:
                        result=run(coder,root,'UNVERIFIED_PLANNER_HYPOTHESIS: repair an unrelated callback',
                            initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
                        self.assertTrue(result['validation']['passed'])
                        self.assertEqual(result['progress']['diagnostic_plan_attempts'],1)
                        if presave_rejections:self.assertEqual(result['diagnostic_plans'][0]['rejected_repair_proposals'],2)
                    else:
                        with self.assertRaisesRegex(RuntimeError,'bounded fixture exit'):
                            run(coder,root,'UNVERIFIED_PLANNER_HYPOTHESIS: repair an unrelated callback',
                                initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
                self.assertEqual((root/'test_main.py').read_text(),frozen)

    def test_ready_presave_diagnosis_at_idle_limit_gets_one_plan_and_one_bounded_edit(self):
        from jarvis.native_coding import StalledCoding
        frozen=('import unittest\nfrom main import Service\nclass Checks(unittest.TestCase):\n'
                ' def setUp(self):\n  self.service=Service()\n  self.nodes=self.service.nodes\n'
                ' def test_direct(self):\n  self.assertEqual(self.nodes["a"].send(), "ok")\n'
                ' def test_indexed(self):\n  self.assertEqual(self.nodes["b"][0].send(), "ok")\n')
        initial=('class Service:\n def __init__(self):\n  self.nodes={"a": [], "b": []}\n'+
                 ''.join('  self.state_'+str(i)+'="bounded constructor source context"\n' for i in range(110)))
        corrected=('class Endpoint:\n def send(self): return "ok"\n def __getitem__(self,key):\n'
                   '  if key != 0: raise IndexError(key)\n  return self\n'
                   'class Service:\n def __init__(self): self.nodes={"a": Endpoint(), "b": Endpoint()}\n')
        for succeeds in (True,False,'malformed_plan','fragment_plan','noop_inference'):
            with self.subTest(succeeds=succeeds),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);root=base/'project';root.mkdir()
                (root/'main.py').write_text(initial);(root/'test_main.py').write_text(frozen)
                calls=[]
                def inference(messages,options,*args):
                    calls.append(options);index=len(calls)
                    if index in (1,4,9,14):return {'tool':'Read','arguments':{'file_path':'main.py'}}
                    if index==2:return {'tool':'Read','arguments':{'file_path':'test_main.py'}}
                    if index==3:return {'tool':'run_checks','arguments':{}}
                    if index in (5,10):return {'tool':'read_slice','arguments':{'file_path':'main.py','start':options.get('native_read_start') or 1,'count':24}}
                    if index in (6,7,11,12):
                        window=options['native_diagnostic_window'];self.assertTrue(window['starts'])
                        return {'tool':'read_slice','arguments':{'file_path':'main.py','start':window['starts'][0],'count':window['count']}}
                    if index in (8,13):return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'missing_context_'+str(index),'new_string':'changed_context'}}
                    if index==15:
                        self.assertEqual(options['native_required_tool'],'update_plan')
                        if succeeds=='malformed_plan':
                            from jarvis.structured_output import ModelOutputError
                            raise ModelOutputError('Incomplete read-only plan; nothing executed.')
                        if succeeds=='fragment_plan':
                            return {'tool':'update_plan','arguments':{'observed_cause':'An observed cause.',
                                'permitted_strategy':'+','verification':'3'}}
                        return interface_plan(options,'The current receiver lacks the required forms.')
                    self.assertEqual(index,16);self.assertEqual(options['native_required_tool'],'edit_batch')
                    old='  self.nodes={"a": [], "b": []}'
                    self.assertIn(old,options['native_exact_edit_spans']['old_strings'])
                    self.assertEqual(options['native_source_char_limit'],2400)
                    self.assertEqual((root/'main.py').read_text(),initial)
                    if succeeds=='noop_inference':
                        from jarvis.structured_output import ModelOutputError
                        raise ModelOutputError('Edit old_string and new_string are identical; no change was proposed and no action executed.')
                    replacement=('  class Endpoint:\n   def send(self): return "ok"\n'
                                 '   def __getitem__(self,key):\n    if key != 0: raise IndexError(key)\n'
                                 '    return self\n  self.nodes={"a": Endpoint(), "b": Endpoint()}')
                    return {'tool':'edit_batch','arguments':{'file_path':'main.py',
                        'source_sha256':options['native_exact_edit_spans']['sha256'],
                        'changes':[{'old_string':old,'new_string':replacement if succeeds else old}]}}
                coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'native_max_repairs':6}))
                with patch('jarvis.native_coding.infer',side_effect=inference):
                    if succeeds is True:
                        result=run(coder,root,'Repair the service',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
                        self.assertTrue(result['validation']['passed'])
                        self.assertTrue(result['candidate_decisions'][-1]['progress_required'])
                        self.assertTrue(result['candidate_decisions'][-1]['verified_case_progress'])
                    else:
                        with self.assertRaises(StalledCoding):
                            run(coder,root,'Repair the service',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
                        result=json.loads(next((base/'.jarvis-runtime/native-code').glob('*/result.json')).read_text())
                rejected_plan=succeeds in ('malformed_plan','fragment_plan')
                self.assertEqual(len(calls),15 if rejected_plan else 16)
                self.assertGreaterEqual(result['progress']['idle_turns'],12)
                self.assertEqual(result['progress']['diagnostic_plan_attempts'],1)
                self.assertEqual(result['progress']['guarded_replacement_attempts'],0 if rejected_plan else 1)
                if succeeds is not True:
                    self.assertEqual((root/'main.py').read_text(),initial)
                    self.assertFalse(result['bounded_recovery_rejection']['generic_fallback_allowed'])
                self.assertEqual((root/'test_main.py').read_text(),frozen)

    def test_exact_python_spans_are_unique_bounded_complete_source_only(self):
        from jarvis.source_observation import exact_python_edit_spans
        source='first = 1\nif True:\n    second = 2\nrepeat = 3\nrepeat = 3\na = 4; b = 5\n'
        spans=exact_python_edit_spans(source)
        self.assertIn('first = 1',spans)
        self.assertIn('    second = 2',spans)
        self.assertNotIn('repeat = 3',spans)
        self.assertNotIn('a = 4; b = 5',spans)
        self.assertTrue(all(source.count(span)==1 for span in spans))
        self.assertLessEqual(len(exact_python_edit_spans(''.join('value_'+str(i)+'='+str(i)+'\n' for i in range(100)))),32)
        self.assertEqual(exact_python_edit_spans('broken = ('),[])
        self.assertEqual(exact_python_edit_spans('x'*8001),[])

    def test_statement_recovery_grammar_binds_current_digest_scope_and_exact_old_text(self):
        from jarvis.native_coding import scoped_schema
        from jarvis.source_observation import exact_python_edit_spans
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);session=files(root)
            path=root/'main.py';path.write_text('value = 1\n');(root/'test_main.py').write_text(TEST)
            request=json.loads((session.run/'request.json').read_text())
            request.update(project=str(root),validation_contract=plan())
            (session.run/'request.json').write_text(json.dumps(request))
            spans={'file_path':'main.py','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                   'old_strings':exact_python_edit_spans(path.read_text())}
            schema=scoped_schema(session.run,force_tool='Edit',force_edit_paths=['main.py'],source_char_limit=2400,force_edit_spans=spans)
            fields=schema['anyOf'][0]['properties']['arguments']['properties']
            self.assertEqual(fields['old_string']['enum'],['value = 1'])
            self.assertEqual(fields['new_string']['maxLength'],1200)
            self.assertEqual(fields['replace_all']['enum'],[False])
            with self.assertRaisesRegex(ValueError,'editable owned'):
                scoped_schema(session.run,force_tool='Edit',force_edit_spans={**spans,'file_path':'test_main.py'})
            with self.assertRaisesRegex(ValueError,'spans do not match'):
                scoped_schema(session.run,force_tool='Edit',force_edit_spans={**spans,'old_strings':['not current']})
            path.write_text('value = 2\n')
            with self.assertRaisesRegex(ValueError,'source changed'):
                scoped_schema(session.run,force_tool='Edit',force_edit_spans=spans)

    def test_diagnostic_plan_schema_is_read_only_and_bounded(self):
        from jarvis.native_coding import diagnostic_plan_schema,diagnostic_steps
        from jarvis.structured_output import validate_contract
        schema=diagnostic_plan_schema()
        def proposal(*steps):
            return {'tool':'update_plan','arguments':dict(zip(('observed_cause','permitted_strategy','verification'),steps))}
        valid=proposal('Cause in owned source.', "Preserve the receiver's contract.", 'Run unchanged checks.')
        self.assertEqual(diagnostic_steps(valid),list(valid['arguments'].values()))
        # Quoted errors and even code-looking strings are data, not actions.
        diagnostic_steps(proposal('Observed error: str (not "int") to str.',
            r'Inspect C:\owned\source.py as data.', '`raise RuntimeError()` is unverified text.'))
        for bad in ({'tool':'Write','arguments':{'file_path':'main.py','content':'pass'}},
                    {'tool':'update_plan','arguments':{'steps':['one']}},
                    proposal('x'*241,'two','three'),
                    {'tool':'update_plan','arguments':{**valid['arguments'],'content':'unassigned source'}}):
            with self.assertRaises(ValueError):validate_contract(schema,bad)
        for fragment in ('+', '3', '   ', '`[0]`'):
            with self.assertRaisesRegex(ValueError,'operator-only'):
                diagnostic_steps(proposal('An observed cause.',fragment,'Run unchanged checks.'))
        from jarvis.native_coding import inference_schema
        validate_contract(inference_schema(),{'tool':'update_plan','arguments':{'steps':['Progress observation.']}})

    def test_failure_history_remains_visible_after_source_read(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            (root/'main.py').write_text('def add(a,b): return 0\n');(root/'test_main.py').write_text(TEST)
            calls=[]
            def inference(messages,options,*args):
                calls.append(1);index=len(calls)
                if index==1:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index==3:return {'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a-b\n'}}
                historical=next(m['content'] for m in messages if m['content'].startswith('Earlier distinct executable failures'))
                self.assertIn('0 != 5',historical);self.assertIn('source_fingerprint',historical)
                current=next(m['content'] for m in messages if m['content'].startswith('Current unresolved'))
                self.assertIn('-1 != 5',current)
                if index==4:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                self.assertEqual(index,5)
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b'}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Repair addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),5)
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_oscillating_failure_states_stop_despite_different_source_bytes(self):
        from jarvis.native_coding import StalledCoding
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            (root/'main.py').write_text('def add(a,b): return 0\n');(root/'test_main.py').write_text(TEST)
            calls=[]
            def inference(messages,options,*args):
                calls.append(1);index=len(calls)
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index in (1,4,6,8):return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index>9:raise AssertionError('An oscillating failure was allowed another model turn')
                expression='a-b' if index in (3,7) else '0'
                return {'tool':'Write','arguments':{'file_path':'main.py',
                    'content':'def add(a,b): return '+expression+'\n# distinct proposal '+str(index)+'\n'}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'native_max_repairs':6}))
            with patch('jarvis.native_coding.infer',side_effect=inference):
                with self.assertRaisesRegex(StalledCoding,'oscillating repair'):
                    run(coder,root,'Repair addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertEqual(len(calls),9);self.assertEqual((root/'test_main.py').read_text(),TEST)
            result=json.loads(next((base/'.jarvis-runtime/native-code').glob('*/result.json')).read_text())
            self.assertEqual(result['progress']['failure_state_revisits'],2)

    def test_prior_failure_observations_keep_different_failed_contracts_and_source_provenance(self):
        from jarvis.source_observation import prior_failure_observations
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            frozen='import unittest\nclass Check(unittest.TestCase):\n def test_api(self):\n  self.values["one"].use()\n  self.values["two"][0].use()\n'
            path=session.root/'test_main.py';path.write_text(frozen)
            sha=hashlib.sha256(path.read_bytes()).hexdigest()
            def failed(line,error,source):
                return {'passed':False,'hashes':{'test_main.py':sha,'main.py':source*64},'errors':[{'path':'test_main.py',
                    'error':'ERROR: test_api (Check)\nTraceback (most recent call last):\n  File "C:/owned/check-workspace-1/test_main.py", line '+str(line)+'\n'+error+'\n'}]}
            earlier=failed(4,'AttributeError: list has no use','a');current=failed(5,'TypeError: invalid index','b')
            rows=prior_failure_observations([earlier,current,earlier],current,session)
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['failure_line'],4)
            self.assertEqual(rows[0]['failed_statement'],'self.values["one"].use()')
            self.assertEqual(rows[0]['primary_error'],'AttributeError: list has no use')
            self.assertEqual(len(rows[0]['source_fingerprint']),64)
            self.assertLessEqual(len(json.dumps(rows)),1200)
            self.assertEqual(path.read_text(),frozen)
            earlier['hashes']['test_main.py']='f'*64
            self.assertEqual(prior_failure_observations([earlier],current,session),[])

    def test_frozen_receiver_protocols_preserve_coexisting_access_shapes(self):
        from jarvis.native_coding import current_test_interfaces
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            frozen='from main import Service\nclass Checks:\n def setUp(self):\n  self.service=Service()\n  self.channels=self.service.channels\n def test_direct(self):\n  self.channels["first"].send()\n def test_indexed(self):\n  self.channels["second"][0].send()\n'
            path=session.root/'test_main.py';path.write_text(frozen)
            result=current_test_interfaces([{'role':'system','content':'rules'},{'role':'user','content':'goal'}],session)
            packet=next(m['content'] for m in result if m['content'].startswith('Frozen test imports'))
            data=json.loads(packet.split(': ',1)[1].split('\n',1)[0])
            group=data[0]['coexisting_receiver_protocols'][0]
            self.assertEqual(group['receiver'],'self.channels');self.assertEqual(group['method'],'send')
            self.assertEqual(group['access_depths'],[1,2])
            self.assertEqual([x['line'] for x in group['observations']],[7,9])
            self.assertIn('self.channels[\'first\'].send()',group['observations'][0]['call'])
            self.assertIn('self.channels[\'second\'][0].send()',group['observations'][1]['call'])
            self.assertLessEqual(len(json.dumps(data,ensure_ascii=False)),2400)
            reference=next(m['content'] for m in result if m['content'].startswith('Python object protocol reference'))
            self.assertIn('docs.python.org/3.10',reference);self.assertIn('__getitem__',reference)
            self.assertNotIn('Calculator',reference)
            self.assertEqual(path.read_text(),frozen)

    def test_receiver_protocol_observation_skips_ambiguous_scopes(self):
        from jarvis.source_observation import receiver_protocols
        import ast
        source='class Checks:\n def setUp(self):\n  self.items=Factory()\n def test_one(self):\n  self.items["a"].send()\n def test_two(self):\n  self.items["b"][0].send()\n'
        self.assertTrue(receiver_protocols(ast.parse(source),lambda node:'main'))
        self.assertEqual(receiver_protocols(ast.parse(source+'class Other: pass\n'),lambda node:'main'),{})
        ambiguous=source.replace('  self.items["b"][0].send()', '  self.items=OtherFactory()\n  self.items["b"][0].send()')
        self.assertEqual(receiver_protocols(ast.parse(ambiguous),lambda node:'main'),{})

    def test_receiver_protocols_retain_distinct_keys_and_bound_large_groups(self):
        from jarvis.source_observation import receiver_protocols
        import ast
        source=('class Checks:\n def test_calls(self):\n'
                '  self.channels["direct"].send()\n'
                '  self.channels["operator"][0].send()\n'
                '  self.channels["digit"][0].send()\n'
                '  self.channels["digit"][0].send()\n')
        group=receiver_protocols(ast.parse(source),lambda node:'main')['main'][0]
        self.assertEqual(group['distinct_call_count'],3)
        self.assertEqual([row['line'] for row in group['observations']],[3,4,5])
        self.assertFalse(group['observations_partial'])
        large=source+''.join('  self.channels["key'+str(i)+'"][0].send()\n' for i in range(30))
        group=receiver_protocols(ast.parse(large),lambda node:'main')['main'][0]
        self.assertEqual(group['distinct_call_count'],33)
        self.assertEqual(len(group['observations']),8)
        self.assertTrue(group['observations_partial'])
        self.assertIn('direct',group['observations'][0]['call'])
        self.assertIn('operator',group['observations'][1]['call'])

    def test_primary_exception_locations_and_statement_exclude_later_test_failures(self):
        from jarvis.native_coding import current_diagnostics
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            frozen='import unittest\nclass Check(unittest.TestCase):\n def test_button(self):\n  self.buttons["2"].invoke()\n  self.buttons["+"][0].invoke()\n def test_keyboard(self):\n  self.assertEqual(self.display.get(), "3")\n'
            path=session.root/'test_main.py';path.write_text(frozen)
            raw=('ERROR: test_button (Check)\nTraceback (most recent call last):\n'
                 '  File "C:/owned/check-workspace-123/test_main.py", line 5, in test_button\n'
                 '  File "C:/Python/tkinter/__init__.py", line 1681, in cget\n'
                 'TypeError: can only concatenate str (not int) to str\n'
                 'FAIL: test_keyboard (Check)\nTraceback (most recent call last):\n'
                 '  File "C:/owned/check-workspace-123/test_main.py", line 7, in test_keyboard\n'
                 'AssertionError: wrong value\n')
            messages=current_diagnostics([{'role':'system','content':'rules'},{'role':'user','content':'goal'}],{'errors':[{'path':'test_main.py','error':raw}]},session)
            packet=next(m['content'] for m in messages if m['content'].startswith('Current unresolved'))
            data=json.loads(packet.split(': ',1)[1].split('\n',1)[0])[0]
            self.assertEqual(data['source_locations'],[{'file':'test_main.py','line':5},{'file':'__init__.py','line':1681}])
            context=data['primary_test_context'];self.assertEqual(context['failure_line'],5)
            self.assertEqual(context['failed_statement'],'self.buttons["+"][0].invoke()')
            self.assertEqual(path.read_text(),frozen)

    def test_diagnostic_windows_offer_unread_gap_inside_long_constructor(self):
        from jarvis.source_observation import diagnostic_windows
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));path=session.root/'main.py'
            source='# header\n'*5+'def build():\n'+' value=1\n'*40+'\n'+'def handle():\n'+' value=2\n'*24+'\n'+'def keyboard():\n'+' value=3\n'*17
            path.write_text(source);raw=path.read_bytes();lines=source.splitlines()
            def read(start,count):
                return {'tool':'read_slice','arguments':{'file_path':'main.py','start':start,'count':count},
                        'result':{'sha256':hashlib.sha256(raw).hexdigest(),
                                  'lines':[{'line':i+1,'text':lines[i]} for i in range(start-1,start+count-1)]}}
            data=diagnostic_windows(session,[read(48,10),read(1,24)],['main.py'])
            self.assertEqual(data['starts'],[25])
            self.assertEqual(data['count'],24);self.assertEqual(data['reads_used'],2)
            self.assertEqual(path.read_bytes(),raw)

    def test_diagnostic_windows_retain_same_hash_coverage_across_rejected_repairs(self):
        from jarvis.source_observation import diagnostic_windows
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));path=session.root/'main.py'
            source='def build():\n'+' value=1\n'*44+'\n'+'def handle():\n'+' value=2\n'*26+'\n'+'def keyboard():\n'+' value=3\n'*17
            path.write_text(source);raw=path.read_bytes();lines=source.splitlines()
            def read(start, count=24, sha=None):
                return {'tool':'read_slice','arguments':{'file_path':'main.py','start':start,'count':count},
                        'result':{'sha256':sha or hashlib.sha256(raw).hexdigest(),
                                  'lines':[{'line':i+1,'text':lines[i]} for i in range(start-1,min(start+count-1,len(lines)))]}}
            turns=[read(47,10),read(1),read(47),
                   {'tool':'apply_patch','arguments':{},'result':{'error':'Context does not match; nothing saved'}},
                   {'tool':'Read','arguments':{'file_path':'main.py'},'result':{'content':source}},read(1,10)]
            data=diagnostic_windows(session,turns,['main.py'])
            self.assertEqual(data['reads_used'],1)
            self.assertNotIn(1,data['starts']);self.assertNotIn(47,data['starts'])
            self.assertIn(25,data['starts'])
            self.assertLessEqual(len(json.dumps(data)),2400)
            self.assertEqual(path.read_bytes(),raw)
            # Source drift invalidates historical coverage, not the current read.
            path.write_text(source+'# new source\n');sha=hashlib.sha256(path.read_bytes()).hexdigest()
            data=diagnostic_windows(session,turns[:-1]+[read(47,10,sha)],['main.py'])
            self.assertIn(1,data['starts'])

    def test_diagnostic_windows_are_novel_bounded_and_scoped_to_editable_source(self):
        from jarvis.source_observation import diagnostic_windows
        from jarvis.native_coding import scoped_schema
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder));path=session.root/'main.py'
            source=''
            for name in ('first','second','third','fourth'):
                source+=f'def {name}():\n return 1\n'+'# context\n'*60
            path.write_text(source);original=path.read_bytes();lines=source.splitlines()
            (session.root/'test_main.py').write_text(TEST)
            request=json.loads((session.run/'request.json').read_text());request.update(project=str(session.root),validation_contract=plan(),test_first=False)
            (session.run/'request.json').write_text(json.dumps(request))
            def read(start):return {'tool':'read_slice','arguments':{'file_path':'main.py','start':start,'count':24},
                'result':{'sha256':hashlib.sha256(original).hexdigest(),'lines':[{'line':i+1,'text':lines[i]} for i in range(start-1,start+23)]}}
            turns=[read(1)];data=diagnostic_windows(session,turns,['main.py'])
            self.assertNotIn(1,data['starts']);self.assertIn(63,data['starts']);self.assertLessEqual(len(json.dumps(data)),2400)
            schema=scoped_schema(session.run,force_tool='Edit',force_edit_paths=['main.py'],diagnostic_window=data)
            variants={v['properties']['tool']['enum'][0]:v for v in schema['anyOf']}
            self.assertEqual(set(variants),{'Edit','read_slice'})
            args=variants['read_slice']['properties']['arguments']['properties']
            self.assertEqual(args['file_path']['enum'],['main.py']);self.assertEqual(args['count']['enum'],[24]);self.assertEqual(args['tail']['enum'],[False])
            self.assertNotIn(1,args['start']['enum'])
            turns.append(read(63));data=diagnostic_windows(session,turns,['main.py'])
            self.assertEqual(len(data['windows']),2);self.assertNotIn(63,data['starts'])
            turns.append(read(125));data=diagnostic_windows(session,turns,['main.py'])
            self.assertEqual(data['starts'],[]);self.assertEqual(data['reads_used'],3)
            self.assertEqual([v['properties']['tool']['enum'][0] for v in scoped_schema(session.run,force_tool='Edit',diagnostic_window=data)['anyOf']],['Edit'])
            self.assertIsNone(diagnostic_windows(session,turns,['unassigned.py']))
            self.assertEqual(path.read_bytes(),original)
            path.write_text(source+'# external drift\n')
            self.assertIsNone(diagnostic_windows(session,turns,['main.py']))

    def test_real_assertion_failure_can_read_complementary_source_before_guarded_edit(self):
        from jarvis.native_coding import scoped_schema
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            source='# filler source context for bounded observation\n'*120+'def add(a,b):\n return a-b\n'
            (root/'main.py').write_text(source);(root/'test_main.py').write_text(TEST)
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            calls=[]
            def inference(messages,options,*args):
                calls.append(1);index=len(calls)
                if index==1:return {'tool':'run_checks','arguments':{}}
                if index==2:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==3:return {'tool':'read_slice','arguments':{'file_path':'main.py','start':1,'count':24,'tail':False}}
                if index==4:
                    self.assertEqual(options['native_required_tool'],'Edit')
                    window=options['native_diagnostic_window'];self.assertIn(121,window['starts'])
                    schema=scoped_schema(args[-1],force_tool='Edit',force_edit_paths=['main.py'],diagnostic_window=window)
                    self.assertEqual({v['properties']['tool']['enum'][0] for v in schema['anyOf']},{'Edit','read_slice'})
                    return {'tool':'read_slice','arguments':{'file_path':'main.py','start':121,'count':24,'tail':False}}
                packet=next(m['content'] for m in reversed(messages) if m['content'].startswith('Diagnostic source windows'))
                self.assertIn('122:  return a-b',packet)
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b'}}
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Repair addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),5)
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_current_diagnostics_retains_multiple_distinct_failures_from_one_suite(self):
        from jarvis.native_coding import current_diagnostics
        error='ERROR: test_button (Checks)\nAttributeError: list has no invoke\nFAIL: test_keyboard (Checks)\nAssertionError: plus not found\n'
        messages=current_diagnostics([{'role':'system','content':'rules'},{'role':'user','content':'goal'}],{'errors':[{'path':'test_gui.py','error':error}]})
        packet=next(m['content'] for m in messages if m['content'].startswith('Current unresolved'))
        data=json.loads(packet.split(': ',1)[1].split('\n',1)[0])[0]
        self.assertEqual(data['failure_excerpts'],['AttributeError: list has no invoke','AssertionError: plus not found'])
        self.assertEqual(data['failed_tests'],['test_button (Checks)','test_keyboard (Checks)'])
        self.assertEqual(data['error'],'AttributeError: list has no invoke')

    def test_primary_failure_quotes_original_failing_method_not_later_assertion(self):
        from jarvis.native_coding import current_diagnostics
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            frozen='import unittest\nclass Check(unittest.TestCase):\n def test_button(self):\n  self.buttons["2"].invoke()\n  self.assertEqual(self.display.get(), "2")\n def test_keyboard(self):\n  self.assertEqual(self.display.get(), "3")\n'
            path=session.root/'test_main.py';path.write_text(frozen)
            raw='ERROR: test_button (Check)\nAttributeError: list has no invoke\nFAIL: test_keyboard (Check)\nAssertionError: wrong value\n'
            messages=current_diagnostics([{'role':'system','content':'rules'},{'role':'user','content':'goal'}],{'errors':[{'path':'test_main.py','error':raw}]},session)
            packet=next(m['content'] for m in messages if m['content'].startswith('Current unresolved'))
            data=json.loads(packet.split(': ',1)[1].split('\n',1)[0])[0]
            self.assertEqual(data['error'],'AttributeError: list has no invoke')
            context=data['primary_test_context'];self.assertEqual(context['test_method'],'test_button')
            self.assertIn('self.buttons["2"].invoke()',context['frozen_test_source'])
            self.assertNotIn('def test_keyboard',context['frozen_test_source'])
            self.assertEqual(path.read_text(),frozen)

    def test_explicit_preserved_source_is_readable_but_not_writable_and_drift_stops_tools(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);session=files(base)
            original='def add(a,b): return a+b\n';(base/'main.py').write_text(original)
            (base/'test_main.py').write_text(TEST)
            (base/'ui.py').write_text('def title(): return "Calculator"\n')
            (base/'PROJECT.md').write_text('protected specification\n')
            request=json.loads((session.run/'request.json').read_text())
            request['goal']='Repair other components. Preserve main.py and PROJECT.md byte-for-byte.'
            request['project']=str(base)
            request['validation_contract']=plan()
            request['allowed_paths'].append('ui.py')
            request['validation_contract']['files'].append({'path':'ui.py','role':'frontend','purpose':'Preserve writable UI ownership'})
            (session.run/'request.json').write_text(json.dumps(request))
            session=FileSession(base,session.run)
            self.assertIn('main.py',session.fixed_sources);self.assertIn('PROJECT.md',session.fixed_sources)
            from jarvis.native_coding import scoped_schema
            schema=scoped_schema(session.run)
            for variant in schema['anyOf']:
                if variant['properties']['tool']['enum'][0] in {'Write','Edit'}:
                    self.assertEqual(variant['properties']['arguments']['properties']['file_path']['enum'],['ui.py'])
            session.call('Read',{'file_path':'main.py'})
            for tool,args in [('Write',{'file_path':'main.py','content':original+'# different\n'}),
                              ('Edit',{'file_path':'main.py','old_string':'return a+b','new_string':'return a-b'})]:
                with self.subTest(tool=tool),self.assertRaisesRegex(ValueError,'explicitly preserved'):
                    session.call(tool,args)
                self.assertEqual((base/'main.py').read_text(),original)
            (base/'PROJECT.md').write_text('injected external drift\n')
            with self.assertRaisesRegex(UncertainCoding,'preserved source changed'):
                session.call('Read',{'file_path':'main.py'})
            self.assertEqual((base/'PROJECT.md').read_text(),'injected external drift\n')

    def test_changing_wrong_actual_text_is_not_frozen_assertion_progress(self):
        from jarvis.native_coding import validation_failure_fingerprint
        first={'errors':[{'path':'test_main.py','error':"test_invalid (tests.CLI) ... FAIL\nAssertionError: 'non-numeric input' not found in ''\nRan 1 test in 0.001s\nFAILED (failures=1)"}], 'checks':[]}
        original=json.dumps(first,sort_keys=True)
        second=json.loads(json.dumps(first));second['errors'][0]['error']=second['errors'][0]['error'].replace("in ''","in 'another wrong message'").replace('0.001s','0.325s')
        self.assertEqual(validation_failure_fingerprint(first),validation_failure_fingerprint(second))
        second['errors'][0]['error']=second['errors'][0]['error'].replace('test_invalid','test_other')
        self.assertNotEqual(validation_failure_fingerprint(first),validation_failure_fingerprint(second))
        second=json.loads(json.dumps(first));second['errors'][0]['error']=second['errors'][0]['error'].replace('non-numeric input','division by zero')
        self.assertNotEqual(validation_failure_fingerprint(first),validation_failure_fingerprint(second))
        self.assertEqual(json.dumps(first,sort_keys=True),original)

    def test_partial_saved_fix_immediately_refocuses_remaining_failed_entrypoint(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            main="def first(): return 'bad'\ndef second(): return 'bad'\n"
            source_test="import unittest\nfrom main import first,second\nclass Checks(unittest.TestCase):\n def test_first(self): self.assertEqual(first(),'fixed')\n def test_second(self): self.assertEqual(second(),'fixed')\n"
            (root/'main.py').write_text(main);(root/'test_main.py').write_text(source_test)
            (root/'calculator.py').write_text('VALUE=1\n')
            value=plan();value['files'][0]['role']='entrypoint'
            value['files'].insert(0,{'path':'calculator.py','role':'logic','purpose':'Preserve unrelated passing library'})
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            calls=[]
            def inference(messages,options,*args):
                calls.append(1);index=len(calls)
                if index in (1,3,5):
                    if index in (3,5):
                        self.assertEqual(options['native_required_tool'],'Read')
                        self.assertEqual(options['native_required_read_paths'],['main.py','test_main.py'])
                    return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                function='first' if index==4 else 'second'
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':f"def {function}(): return 'bad'",'new_string':f"def {function}(): return 'fixed'"}}
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Repair CLI results',initial_plan=value,allowed_paths=[f['path'] for f in value['files']],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertEqual((root/'test_main.py').read_text(),source_test)
            self.assertEqual((root/'calculator.py').read_text(),'VALUE=1\n')

    def test_exact_failed_target_read_and_rejected_patch_read_preserve_alternatives(self):
        from jarvis.native_coding import scoped_schema
        from jarvis.structured_output import ModelOutputError
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            calculator='def add(a,b): return a+b\n';main="def result(): return 'bad'\n"
            logic_test='import unittest\nfrom calculator import add\nclass Check(unittest.TestCase):\n def test_add(self): self.assertEqual(add(2,3),5)\n'
            cli_test="import unittest\nfrom main import result\nclass Check(unittest.TestCase):\n def test_result(self): self.assertEqual(result(),'fixed')\n"
            for name,text in {'calculator.py':calculator,'main.py':main,'test_calculator.py':logic_test,'test_main.py':cli_test}.items():(root/name).write_text(text)
            value={'files':[{'path':name,'role':role,'purpose':'Verify or implement result behavior'} for name,role in
                [('calculator.py','logic'),('main.py','entrypoint'),('test_calculator.py','test'),('test_main.py','test')]],
                'checks':[{'kind':'python_tests','path':name} for name in ('test_calculator.py','test_main.py')]}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            calls=[]
            def inference(messages,options,cancelled,deadline,report,directory):
                calls.append(1);index=len(calls)
                if index==1:return {'tool':'Read','arguments':{'file_path':'calculator.py'}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index in (3,6):
                    expected='main.py' if index==3 else 'calculator.py'
                    self.assertEqual(options['native_required_tool'],'Read')
                    expected_paths=[expected,'test_main.py'] if index==3 else [expected]
                    self.assertEqual(options['native_required_read_paths'],expected_paths)
                    schema=scoped_schema(directory,force_tool='Read',force_read_paths=options['native_required_read_paths'])
                    self.assertEqual(schema['anyOf'][0]['properties']['arguments']['properties']['file_path']['enum'],expected_paths)
                    return {'tool':'Read','arguments':{'file_path':expected}}
                if index==4:
                    raise ModelOutputError('Edit old_string and new_string are identical; no action executed.')
                if index==5:
                    self.assertEqual(options['native_required_tool'],'apply_patch')
                    return {'tool':'apply_patch','arguments':{'patch':'*** Begin Patch\n*** Update File: calculator.py\n@@\n-not current source\n+never saved\n*** End Patch'}}
                self.assertIn('calculator.py',options['native_required_edit_paths'])
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':main.strip(),'new_string':"def result(): return 'fixed'"}}
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Repair CLI result',initial_plan=value,allowed_paths=[f['path'] for f in value['files']],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertEqual((root/'calculator.py').read_text(),calculator)
            self.assertEqual((root/'test_main.py').read_text(),cli_test)
            self.assertEqual((root/'test_calculator.py').read_text(),logic_test)

    def test_validation_progress_ignores_owned_workspace_and_duration_only(self):
        from jarvis.native_coding import validation_failure_fingerprint
        first={'errors':[{'path':'test_main.py','error':'AssertionError: wrong result\nRan 2 tests in 0.001s\nFAILED (failures=1)'}], 'checks':[]}
        second=json.loads(json.dumps(first));second['errors'][0]['error']=second['errors'][0]['error'].replace('0.001s','0.714s')
        original=json.dumps(first,sort_keys=True)
        self.assertEqual(validation_failure_fingerprint(first),validation_failure_fingerprint(second))
        second['errors'][0]['error']=second['errors'][0]['error'].replace('wrong result','different result')
        self.assertNotEqual(validation_failure_fingerprint(first),validation_failure_fingerprint(second))
        self.assertEqual(json.dumps(first,sort_keys=True),original)

    def test_repeated_failing_checks_stop_even_when_observation_replies_vary(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            (root/'main.py').write_text('def add(a,b): return a-b\n');(root/'test_main.py').write_text(TEST)
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'native_max_turns':64}))
            count=[]
            def inference(*args):
                count.append(1)
                return {'tool':'run_checks','arguments':{}} if len(count)%2==0 else {'tool':'Read','arguments':{'file_path':'main.py'}}
            with patch('jarvis.native_coding.infer',side_effect=inference):
                with self.assertRaisesRegex(ValueError,'same executable-check failures recurred four times'):
                    run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertLess(len(count),12)
            directory=next((base/'.jarvis-runtime/native-code').glob('*'))
            result=json.loads((directory/'result.json').read_text())
            self.assertEqual(result['progress']['identical_failed_checks'],4)
            self.assertEqual(result['error_type'],'StalledCoding')
            self.assertEqual((root/'test_main.py').read_text(),TEST)
            self.assertEqual((root/'main.py').read_text(),'def add(a,b): return a-b\n')
            self.assertGreaterEqual(len(list(directory.glob('validation-*.json'))),4)

    def test_failed_validation_read_loop_stops_before_global_turn_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            (root/'main.py').write_text('def add(a,b): return a-b\n');(root/'test_main.py').write_text(TEST)
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'native_max_turns':64}))
            count=[]
            def inference(*args):
                count.append(1)
                return {'tool':'run_checks','arguments':{}} if len(count)==2 else {'tool':'Read','arguments':{'file_path':'main.py'}}
            with patch('jarvis.native_coding.infer',side_effect=inference):
                with self.assertRaisesRegex(ValueError,'12 tool turns without a confirmed source save'):
                    run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertLess(len(count),20)
            directory=next((base/'.jarvis-runtime/native-code').glob('*'))
            result=json.loads((directory/'result.json').read_text())
            self.assertEqual(result['progress']['idle_turns'],12)
            self.assertEqual(result['error_type'],'StalledCoding')
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_large_research_observation_keeps_remote_reader_instruction(self):
        from jarvis.native_coding import observation
        result={'id':'candidate','file_path':'src/widget.tsx','start':1,'total_lines':100,'line_count':40,
                'content':'x'*4000,'copy_allowed':True}
        value=json.loads(observation(result))
        self.assertEqual(value['id'],'candidate')
        self.assertIn('research_source',value['instruction'])
        self.assertEqual(result['content'],'x'*4000)

    def test_large_batch_reads_keep_bounded_source_from_each_requested_file(self):
        from jarvis.native_coding import observation
        rows=[{'path':'D:/owned/worker/'+name,'requested_path':name,'sha256':'a'*64,
               'content':'# '+name+'\n'+'def value(): return 42\n'*400} for name in ('src/logic.py','ui/window.py')]
        original=json.dumps(rows)
        text=observation(rows);data=json.loads(text)
        self.assertLessEqual(len(text),3000)
        self.assertEqual([r['file_path'] for r in data['reads']],['src/logic.py','ui/window.py'])
        for source,row in zip(rows,data['reads']):
            self.assertTrue(row['content_preview']);self.assertTrue(source['content'].startswith(row['content_preview']))
        self.assertIn('read_slice',data['instruction']);self.assertEqual(json.dumps(rows),original)

    def test_research_source_uses_owning_service_and_original_project_scope(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'worker';root.mkdir();(root/'test_main.py').write_text(TEST)
            source=Mock(return_value={'files':['LICENSE'],'copy_allowed':False})
            owner=SimpleNamespace(code_intel=SimpleNamespace(source=source))
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            coder.native_actions=owner;coder.research_project_root=base/'original-project'
            proposals=[{'tool':'research_source','arguments':{'candidate_id':'fixture-id'}},
                {'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'}}]
            with patch('jarvis.native_coding.infer',side_effect=proposals):
                result=run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            source.assert_called_once_with(base/'original-project',candidate_id='fixture-id')

    def test_explicit_verified_reuse_reads_scoped_source_before_generation(self):
        from unittest.mock import Mock
        from jarvis.native_coding import requested_reuse_sources,scoped_schema
        from jarvis.structured_output import validate_contract
        guidance={'code_intelligence':{'reusable_components':[{'id':'verified-id','source':'verified memory',
            'trust':'verified','copy_allowed':True}]}}
        self.assertEqual(requested_reuse_sources('Reuse verified code',guidance),['verified-id'])
        self.assertEqual(requested_reuse_sources('Do not reuse verified code',guidance),[])
        self.assertEqual(requested_reuse_sources('Do not use cloud APIs. Reuse verified code',guidance),['verified-id'])
        self.assertEqual(requested_reuse_sources('Reuse verified code',{'code_intelligence':None}),[])
        self.assertEqual(requested_reuse_sources('Implement addition',guidance),[])
        for unavailable in (False,None):
            blocked={'code_intelligence':{'reusable_components':[{**guidance['code_intelligence']['reusable_components'][0],'copy_allowed':unavailable}]}}
            self.assertEqual(requested_reuse_sources('Reuse verified code',blocked),[])
        for revoked in (False,True):
            with self.subTest(revoked=revoked),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);root=base/'worker';root.mkdir();(root/'test_main.py').write_text(TEST)
                source=Mock(side_effect=ValueError('Verified source revoked')) if revoked else Mock(return_value={
                    'content':'def add(a,b): return a+b','sha256':'a'*64,'partial':False})
                coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
                coder.native_actions=SimpleNamespace(code_intel=SimpleNamespace(source=source))
                coder.workload_guidance=guidance;coder.research_project_root=base/'original'
                stages=[]
                def inference(messages,options,*args,**kwargs):
                    stages.append(options.get('native_required_tool'))
                    if len(stages)==1:
                        schema=scoped_schema(args[-1],force_tool='research_source',force_reuse_candidates=['verified-id'])
                        validate_contract(schema,{'tool':'research_source','arguments':{'candidate_id':'verified-id','file_path':'source','count':80}})
                        with self.assertRaises(ValueError):validate_contract(schema,{'tool':'research_source','arguments':{'candidate_id':'verified-id','file_path':'source','start':999,'count':80}})
                        with self.assertRaises(ValueError):validate_contract(schema,{'tool':'Write','arguments':{'file_path':'main.py','content':'wrong'}})
                        return {'tool':'research_source','arguments':{'candidate_id':'verified-id','file_path':'source','count':80}}
                    return {'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'}}
                with patch('jarvis.native_coding.infer',side_effect=inference):
                    result=run(coder,root,'Reuse verified code to implement addition',initial_plan=plan(),
                        allowed_paths=['main.py','test_main.py'],return_receipt=True)
                self.assertTrue(result['validation']['passed']);self.assertEqual(stages[0],'research_source')
                self.assertEqual(result['reuse_source_observations'][0]['source_read'],not revoked)
                self.assertEqual(source.call_count,1)

    def test_regeneration_schema_bounds_source_without_removing_observation_tools(self):
        from jarvis.native_coding import scoped_schema
        from jarvis.structured_output import validate_contract
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);session=files(root)
            request={'project':str(root),'allowed_paths':['main.py','test_main.py'],'test_first':False,'validation_contract':plan()}
            (session.run/'request.json').write_text(json.dumps(request))
            schema=scoped_schema(session.run,source_char_limit=600)
            variants={v['properties']['tool']['enum'][0]:v for v in schema['anyOf']}
            self.assertIn('Read',variants)
            self.assertEqual(variants['Write']['properties']['arguments']['properties']['content']['maxLength'],600)
            with self.assertRaises(ValueError):validate_contract(schema,{'tool':'Write','arguments':{'file_path':'main.py','content':'x'*601}})
            validate_contract(schema,{'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'}})
            ordinary=scoped_schema(session.run)
            write=next(v for v in ordinary['anyOf'] if v['properties']['tool']['enum']==['Write'])
            self.assertNotIn('maxLength',write['properties']['arguments']['properties']['content'])

    def test_frozen_test_exports_survive_history_without_changing_source(self):
        from jarvis.native_coding import current_test_interfaces
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            test='from main import Addition as Selected, add\nfrom os import path\napp = Selected()\napp.calculate(2,3)\n'
            (session.root/'test_main.py').write_text(test)
            history=[{'role':'system','content':'scope'},{'role':'user','content':'goal'},
                     {'role':'user','content':'latest rejection'}]
            enriched=current_test_interfaces(history,session)
            self.assertEqual(enriched[-1],history[-1]);self.assertEqual(len(history),3)
            self.assertIn('"exports": ["Addition", "add"]',enriched[-2]['content'])
            self.assertIn('Selected()',enriched[-2]['content'])
            self.assertIn('app.calculate(2, 3)',enriched[-2]['content'])
            self.assertNotIn('"os"',enriched[-2]['content'])
            self.assertEqual((session.root/'test_main.py').read_text(),test)

    def test_frozen_assertion_context_keeps_expected_exceptions_and_nested_widget_calls(self):
        from jarvis.native_coding import current_test_interfaces,repair_focus
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            source="import unittest\nfrom main import Widget, evaluate\nclass Checks(unittest.TestCase):\n def setUp(self): self.gui=Widget()\n def test_zero(self):\n  with self.assertRaises(ZeroDivisionError):\n   evaluate('1/0')\n  self.assertEqual(self.gui.display.get(), '0')\n"
            (session.root/'test_main.py').write_text(source)
            messages=[{'role':'system','content':'Scope'},{'role':'user','content':'Goal'},
                      {'role':'user','content':'Latest error remains last'}]
            payload=current_test_interfaces(messages,session)
            self.assertIn('ZeroDivisionError',payload[-2]['content'])
            self.assertIn('self.gui.display.get()',payload[-2]['content'])
            self.assertIn('assertion_examples',payload[-2]['content'])
            self.assertEqual(payload[-1],messages[-1]);self.assertEqual((session.root/'test_main.py').read_text(),source)
            data=payload[-2]['content'].split(': ',1)[1].split('\nKeep ',1)[0]
            self.assertLessEqual(len(data),2400);json.loads(data)
        value={'files':[{'path':'main.py','role':'logic'},{'path':'package.json','role':'configuration'}]}
        self.assertEqual(repair_focus(value,{'errors':[{'error':'Unsupported test script in package.json'}]},None),['package.json'])

    def test_real_failed_check_drives_bounded_read_to_deep_application_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            source='# owned filler to exceed the full observation budget\n'*120+'def add(a,b):\n raise ValueError("broken")\n'
            (root/'main.py').write_text(source);(root/'test_main.py').write_text(TEST)
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            calls=[]
            def inference(messages,options,*args):
                calls.append(1);index=len(calls)
                if index==1:return {'tool':'run_checks','arguments':{}}
                if index==2:
                    self.assertEqual(options['native_required_tool'],'Read')
                    return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==3:
                    self.assertEqual(options['native_required_tool'],'read_slice')
                    start=options['native_read_start'];count=options['native_read_line_limit']
                    self.assertLessEqual(start,122);self.assertGreaterEqual(start+count-1,122)
                    return {'tool':'read_slice','arguments':{'file_path':'main.py','start':start,'count':count,'tail':False}}
                self.assertEqual(options['native_required_tool'],'Edit')
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'raise ValueError("broken")','new_string':'return a+b'}}
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Repair addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertEqual(len(calls),4)
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_traceback_window_is_owned_and_covers_failure_even_after_backoff(self):
        from jarvis.native_coding import traceback_read_start,scoped_schema
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            (session.root/'main.py').write_text('\n'*120+'raise ValueError("broken")\n')
            request=json.loads((session.run/'request.json').read_text())
            request['project']=str(session.root)
            request['validation_contract']=plan()
            (session.run/'request.json').write_text(json.dumps(request))
            failure={'errors':[{'error':'File "C:/owned/run/check-workspace-123/main.py", line 121, in build\nValueError: broken'}]}
            for count in (24,12,6,3,1):
                start=traceback_read_start(failure,session.root,'main.py',count)
                self.assertLessEqual(start,121);self.assertGreaterEqual(start+count-1,121)
                schema=scoped_schema(session.run,force_tool='read_slice',force_read_paths=['main.py'],read_line_limit=count,force_read_start=start)
                args=schema['anyOf'][0]['properties']['arguments']
                self.assertEqual(args['properties']['start']['enum'],[start])
                self.assertEqual(args['properties']['count']['enum'],[count])
                self.assertEqual(args['properties']['tail']['enum'],[False])
                self.assertTrue({'start','count','tail'}<=set(args['required']))
            for path in ('C:/Python/Lib/main.py','C:/unrelated/main.py','C:/owned/check-workspace-123/other/main.py'):
                self.assertIsNone(traceback_read_start({'errors':[{'error':f'File "{path}", line 121'}]},session.root,'main.py',24))
            owned={'errors':[{'error':f'File "{session.root / "main.py"}", line 121'}]}
            self.assertEqual(traceback_read_start(owned,session.root,'main.py',24),117)

    def test_frozen_context_retains_direct_state_assertions_and_aliased_widget_calls(self):
        from jarvis.native_coding import current_test_interfaces
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            session.plan['files'].append({'path':'ui_builder.py','role':'frontend'})
            source='import unittest\nfrom main import Calculator\nfrom ui_builder import Window\nclass Check(unittest.TestCase):\n def setUp(self):\n  self.calc=Calculator()\n  self.app=Window()\n  self.display=self.app.display\n  self.buttons=self.app.buttons\n def test_clear(self):\n  self.calc.input_text="123"\n  self.calc.clear()\n  self.assertEqual(self.calc.input_text, "")\n def test_button(self):\n  self.buttons["2"].invoke()\n  self.assertEqual(self.display.get(), "2")\n'
            path=session.root/'test_main.py';path.write_text(source)
            messages=current_test_interfaces([{'role':'system','content':'rules'},{'role':'user','content':'goal'}],session)
            packet=next(m['content'] for m in messages if m['content'].startswith('Frozen test imports'))
            payload=packet.split(': ',1)[1].split('\n',1)[0]
            self.assertLessEqual(len(payload),2400)
            rows={r['module']:r for r in json.loads(payload)}
            self.assertIn("self.calc.input_text = '123'",rows['main']['state_examples'])
            self.assertIn("self.assertEqual(self.calc.input_text, '')",rows['main']['assertion_examples'])
            self.assertIn("self.buttons['2'].invoke()",rows['ui_builder']['call_examples'])
            self.assertIn("self.assertEqual(self.display.get(), '2')",rows['ui_builder']['assertion_examples'])
            self.assertEqual(path.read_text(),source)

    def test_real_state_failure_context_drives_guarded_repair_with_frozen_test_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            source='class Calculator:\n def clear(self):\n  return None\n'
            frozen='import unittest\nfrom main import Calculator\nclass Check(unittest.TestCase):\n def test_clear(self):\n  self.calc=Calculator()\n  self.calc.input_text="123"\n  self.calc.clear()\n  self.assertEqual(self.calc.input_text, "")\n'
            (root/'main.py').write_text(source);(root/'test_main.py').write_text(frozen)
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            calls=[]
            def inference(messages,options,*args):
                calls.append(1)
                if len(calls)==1:return {'tool':'run_checks','arguments':{}}
                if len(calls)==2:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                packet=next(m['content'] for m in messages if m['content'].startswith('Frozen test imports'))
                self.assertIn("self.assertEqual(self.calc.input_text, '')",packet)
                self.assertIn("self.calc.input_text = '123'",packet)
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return None','new_string':'self.input_text = ""'}}
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Repair calculator clear state',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),3)
            self.assertEqual((root/'test_main.py').read_text(),frozen)

    def test_attribute_only_gui_failure_focuses_its_frozen_import_not_passing_library(self):
        from jarvis.native_coding import repair_focus
        value={'files':[{'path':'calculator_logic.py','role':'logic'},{'path':'main.py','role':'entrypoint'},
                        {'path':'ui_builder.py','role':'frontend'},{'path':'test_gui_behavior.py','role':'test'}]}
        failure={'errors':[{'path':'test_gui_behavior.py','error':"AttributeError: 'CalculatorApp' object has no attribute 'buttons'"}],
                 'checks':[{'path':'test_calculator.py','exit_code':0}]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'test_gui_behavior.py'
            source='from tkinter import Event\nfrom ui_builder import CalculatorApp\n';path.write_text(source)
            self.assertEqual(repair_focus(value,failure,None,root),['ui_builder.py','calculator_logic.py','main.py'])
            self.assertEqual(repair_focus(value,failure,['main.py'],root),['main.py'])
            direct={'errors':[{'path':'test_gui_behavior.py','error':'calculator_logic.py line 3 TypeError'}]}
            self.assertEqual(repair_focus(value,direct,None,root),['calculator_logic.py'])
            self.assertEqual(path.read_text(),source)

    def test_cli_assertion_focus_precedes_passing_library_without_excluding_it(self):
        from jarvis.native_coding import repair_focus,scoped_schema
        value={'files':[{'path':'calculator.py','role':'logic'},{'path':'main.py','role':'entrypoint'},
                        {'path':'test_main.py','role':'test'}]}
        failure={'errors':[{'path':'test_main.py','error':"AssertionError: 'non-numeric input' not found in ''"}],
                 'checks':[{'path':'test_calculator.py','exit_code':0}]}
        focus=repair_focus(value,failure,None)
        self.assertEqual(focus,['main.py','calculator.py'])
        self.assertEqual(repair_focus(value,{'errors':[{'path':'test_main.py','error':'calculator.py line3 TypeError'}]},None),['calculator.py'])
        self.assertEqual(repair_focus(value,failure,['calculator.py']),['calculator.py'])
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            (session.root/'calculator.py').write_text('VALUE=1\n')
            (session.root/'main.py').write_text('VALUE=2\n')
            (session.root/'test_main.py').write_text(TEST)
            request=json.loads((session.run/'request.json').read_text())
            request['allowed_paths']=['calculator.py','main.py','test_main.py']
            request['project']=str(session.root)
            request['validation_contract']={'files':value['files']}
            (session.run/'request.json').write_text(json.dumps(request))
            for tool in ('Read','Edit'):
                schema=scoped_schema(session.run,force_tool=tool,force_read_paths=focus,force_edit_paths=focus)
                self.assertEqual(schema['anyOf'][0]['properties']['arguments']['properties']['file_path']['enum'],focus)

    def test_missing_export_repair_preserves_existing_function_and_gets_actionable_feedback(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            original='def add(a,b): return a+b\n'
            (root/'main.py').write_text(original)
            (root/'test_main.py').write_text('import unittest\nfrom main import Addition,add\nclass Exports(unittest.TestCase):\n def test_both(self):\n  self.assertEqual(add(2,3),5)\n  self.assertEqual(Addition().calculate(2,3),5)\n')
            missing='class Addition:\n def calculate(self,a,b): return add(a,b)\n'
            proposals=iter([('Read',{'file_path':'main.py'}),
                ('Edit',{'file_path':'main.py','old_string':original,'new_string':missing}),
                ('Read',{'file_path':'main.py'}),
                ('Edit',{'file_path':'main.py','old_string':original,'new_string':original+missing})])
            observations=[]
            def propose(messages,*args):
                observations.append(messages[-1]['content']);name,arguments=next(proposals)
                return {'tool':name,'arguments':arguments}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=propose):
                result=run(coder,root,'Add the required export while preserving existing behavior',initial_plan=plan(),
                           allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertTrue((root/'main.py').read_text().startswith(original))
            self.assertTrue(any('add any missing required export alongside' in row for row in observations))

    def test_existing_implementation_need_not_be_rewritten_before_worker_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            original='def add(a,b): return a+b\n'
            (root/'main.py').write_text(original)
            (root/'README.md').write_text('Existing documentation\n')
            assigned=plan()
            assigned['files'] += [{'path':'helper.py','role':'logic','purpose':'Double using existing addition'},
                                  {'path':'README.md','role':'documentation','purpose':'Existing usage'}]
            source=TEST+'\nfrom helper import double\nclass Doubling(unittest.TestCase):\n def test_double(self): self.assertEqual(double(4),8)\n'
            proposals=[{'tool':'Read','arguments':{'file_path':'main.py'}},
                       {'tool':'Write','arguments':{'file_path':'test_main.py','content':source}},
                       {'tool':'Write','arguments':{'file_path':'helper.py','content':'from main import add\ndef double(a): return add(a,a)\n'}}]
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=proposals) as infer:
                result=run(coder,root,'Add doubling using the existing addition',initial_plan=assigned,
                           allowed_paths=[f['path'] for f in assigned['files']],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(infer.call_count,3)
            self.assertEqual((root/'main.py').read_text(),original)
            self.assertEqual(set(result['changed']),{'helper.py','test_main.py'})

    def test_forced_checks_remain_available_when_all_assigned_files_are_frozen_tests(self):
        from jarvis.native_coding import scoped_schema
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);session=files(root)
            (root/'test_main.py').write_text(TEST)
            request={'project':str(root),'allowed_paths':['test_main.py'],'test_first':True,'validation_contract':plan()}
            (session.run/'request.json').write_text(json.dumps(request))
            schema=scoped_schema(session.run,force_tool='run_checks')
            self.assertEqual([v['properties']['tool']['enum'] for v in schema['anyOf']],[['run_checks']])

    def test_command_generation_schema_rejects_observed_cross_tool_argument(self):
        from jarvis.native_coding import inference_schema,SCHEMA
        from jarvis.mcp_contract import validate_schema_value
        variants=inference_schema()['anyOf']
        command=next(v for v in variants if v['properties']['tool']['enum']==['exec_command'])
        proposal={'tool':'exec_command','arguments':{'argv':['python','-m','unittest']},'note':'Public test'}
        validate_schema_value(command,proposal,'proposal')
        proposal['arguments']['start']=0
        with self.assertRaises(ValueError):validate_schema_value(command,proposal,'proposal')
        self.assertEqual({name for variant in variants for name in variant['properties']['tool']['enum']},
                         set(SCHEMA['properties']['tool']['enum']))

    def test_rejected_inline_and_unassigned_write_get_concrete_safe_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            (root/'test_main.py').write_text(TEST)
            proposals=iter([
                ('Write',{'file_path':'main.py','content':'def add(a,b): return a+b\n'}),
                ('exec_command',{'argv':['python','-c','print(1)']}),
                ('Write',{'file_path':'README.md','content':'unassigned'}),
                ('run_checks',{}),('finish',{})])
            observations=[]
            def propose(messages,*args):
                observations.append(messages[-1]['content'])
                name,arguments=next(proposals)
                return {'tool':name,'arguments':arguments,'note':'Public recovery fixture'}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=propose):
                result=run(coder,root,'Implement addition only',initial_plan=plan(),return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertTrue(any('inline python -c is unavailable' in row and 'run_checks' in row for row in observations))
            self.assertTrue(any('Leave unassigned documentation unchanged' in row and 'finish' in row for row in observations))
            self.assertFalse((root/'README.md').exists())
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_platform_markup_finishes_only_after_real_component_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            assigned={'files':[{'path':'index.html','role':'frontend','purpose':'Visible required counter markup'}],
                'checks':[{'kind':'browser_component','path':'index.html','entry':'index.html','component':'markup',
                          'required_selectors':['#count','#increment'],'steps':[{'action':'text','selector':'#count','value':'0'}]}]}
            proposal={'tool':'Write','arguments':{'file_path':'index.html','content':'<!doctype html><html><head><title>Counter</title></head><body><span id="count">0</span><button id="increment">Add</button></body></html>'},'note':'Assigned markup'}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=[proposal]):
                result=run(coder,root,'Create counter markup',initial_plan=assigned,return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(result['turns']),1)
            self.assertEqual(result['validation']['checks'][0]['kind'],'browser_component')

    def test_reference_covers_all_pages_and_typed_source_operations(self):
        from jarvis.command_reference import search
        from jarvis.coding_operations import execute
        reference=search()
        self.assertEqual(len(reference['guides']),24)
        for number in range(1,7):self.assertIn('PAGE '+str(number),reference['reference_text'])
        self.assertIn('explicit user approval',next(g['when_and_how'] for g in reference['guides'] if g['topic']=='delete'))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);session=files(root)
            (root/'test_main.py').write_text(TEST);(root/'main.py').write_text('def add(a,b): return a+b\n# remove once\n')
            commands=Processes(root,session.run,lambda *a:None)
            head=execute(session,'read_slice',{'file_path':'main.py','start':1,'count':1},commands)
            self.assertEqual(head['lines'],[{'line':1,'text':'def add(a,b): return a+b'}])
            execute(session,'source_transform',{'file_path':'main.py','operation':'remove_lines','lines':['# remove once']},commands)
            self.assertNotIn('remove once',(root/'main.py').read_text())
            with self.assertRaisesRegex(ValueError,'test assertions'):execute(session,'source_transform',{'file_path':'test_main.py','operation':'append','content':'# changed\n'},commands)

    def test_typed_native_proposals_accept_object_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            proposals=iter([{'tool':'Write','arguments':{'file_path':'main.py','content':'def add(a,b): return a+b\n'},'note':'typed source'},
                            {'tool':'finish','arguments':{},'note':'independent checks'}])
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=lambda *a:next(proposals)):
                result=run(coder,root,'Implement addition',initial_plan=plan(),return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_worker_reads_and_ledgers_are_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);a=files(base/'a');b=files(base/'b')
            for session in (a,b):
                (session.root/'main.py').write_text('def add(a,b): return 0\n')
                (session.root/'test_main.py').write_text(TEST)
            a.call('Read',{'file_path':'main.py'})
            with self.assertRaisesRegex(ValueError,'Read'):b.call('Write',{'file_path':'main.py','content':'def add(a,b): return a+b\n'})
            a.call('Write',{'file_path':'main.py','content':'def add(a,b): return a+b\n'})
            self.assertIn('return 0',(b.root/'main.py').read_text())
            self.assertEqual(a.changed(),['main.py']);self.assertFalse(b.changed())

    def test_tests_first_and_frozen_during_repairs(self):
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            with self.assertRaisesRegex(ValueError,'test first'):session.call('Write',{'file_path':'main.py','content':'def add(a,b): return a+b\n'})
            session.call('Write',{'file_path':'test_main.py','content':TEST})
            sha=hashlib.sha256((session.root/'test_main.py').read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'test assertions'):session.call('Write',{'file_path':'test_main.py','content':TEST.replace('5','0')})
            self.assertEqual(sha,hashlib.sha256((session.root/'test_main.py').read_bytes()).hexdigest())

    def test_patch_prevalidates_all_files_before_any_save(self):
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            bad='*** Begin Patch\n*** Add File: test_main.py\n+'+TEST.replace('\n','\n+').rstrip('+')+'*** Add File: main.py\n+def broken(:\n*** End Patch'
            with self.assertRaises(ValueError):session.patch(bad)
            self.assertFalse((session.root/'test_main.py').exists())
            for header in ('*** Delete File: main.py','*** Move to: other.py','*** Add File: ../escape.py'):
                with self.assertRaises(ValueError):patch_files(session.root,'*** Begin Patch\n'+header+'\n+x=1\n*** End Patch')

    def test_uncertain_save_is_never_replayed(self):
        with tempfile.TemporaryDirectory() as folder:
            session=files(Path(folder))
            (session.run/'file-events.jsonl').write_text(json.dumps({'stage':'attempted','signature':'uncertain'})+'\n')
            with self.assertRaises(UncertainCoding):session.call('Write',{'file_path':'test_main.py','content':TEST})
            self.assertFalse((session.root/'test_main.py').exists())

    def test_program_policy_and_actual_owned_session(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'hello.py').write_text('import time\nprint("hello",flush=True)\ntime.sleep(.2)\nprint("done",flush=True)\n')
            commands=Processes(root,root,lambda *a:None)
            try:
                result=commands.start(['python','hello.py'],yield_time_ms=0)
                chunks=[result['output']];key=result['session_id']
                while result['running']:
                    result=commands.poll(key,yield_time_ms=100);chunks.append(result['output'])
                self.assertEqual(result['exit_code'],0);self.assertIn('hello',''.join(chunks));self.assertIn('done',''.join(chunks))
                with self.assertRaises(ValueError):commands.poll(key)
                for argv in (['python','-c','print(1)'],['git','push'],['cmd','/c','echo bypass'],['python','../bad.py']):
                    with self.assertRaises(ValueError):checked_argv(root,argv)
                self.assertTrue(next(row for row in inventory(root) if row['program']=='python')['available'])
            finally:commands.close()

    def test_windows_npm_shim_runs_without_shell_injection(self):
        from jarvis.coding_programs import locate
        if not locate('npm'):return
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);commands=Processes(root,root,lambda *a:None)
            try:
                result=commands.start(['npm','--version'])
                while result['running']:result=commands.poll(result['session_id'])
                self.assertEqual(result['exit_code'],0,result['output'])
                self.assertRegex(result['output'],r'\d+\.\d+\.\d+')
                with self.assertRaises(ValueError):checked_argv(root,['tsc','--noEmit','x.ts&echo'])
            finally:commands.close()

    def test_timeout_stops_owned_tree_and_blocks_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'slow.py').write_text('import time\ntime.sleep(30)\n')
            commands=Processes(root,root,lambda *a:None)
            with self.assertRaises(UncertainCoding):commands.start(['python','slow.py'],timeout_seconds=1,yield_time_ms=2000)
            self.assertFalse(commands.sessions)
            with self.assertRaises(UncertainCoding):commands.start(['python','--version'])

    def test_native_repairs_application_against_unchanged_real_test(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            proposals=iter([
                ('Write',{'file_path':'test_main.py','content':TEST}),
                ('Write',{'file_path':'main.py','content':'def add(a,b): return a-b\n'}),
                ('finish',{}),
                ('Write',{'file_path':'test_main.py','content':TEST.replace('5','-1')}),
                ('Read',{'file_path':'main.py'}),
                ('Edit',{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b'}),
                ('finish',{}),
            ])
            observations=[]
            def propose(messages,*args):
                observations.append(messages[-1]['content']);name,arguments=next(proposals)
                return {'tool':name,'arguments':json.dumps(arguments),'note':'fixture'}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=propose),patch('jarvis.codex_code.run',side_effect=AssertionError('Codex must not launch')):
                result=run(coder,root,'Create addition',initial_plan=plan(),return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(result['repair_turns'],1)
            self.assertEqual((root/'test_main.py').read_text(),TEST)
            self.assertTrue(any('test assertions are fixed' in row for row in observations))
            self.assertFalse(result['codex_launched'])

    def test_assigned_worker_checks_stalled_write_and_never_accepts_failing_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
            proposals=iter([
                ('Write',{'file_path':'main.py','content':'def add(a,b): return a-b\n'}),
                ('Write',{'file_path':'main.py','content':'def add(a,b): return a-b\n'}),
                ('Read',{'file_path':'main.py'}),
                ('Edit',{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b'}),
                ('run_checks',{})])
            observations=[]
            def propose(messages,*args):
                observations.append(messages[-1]['content'])
                name,arguments=next(proposals)
                return {'tool':name,'arguments':arguments,'note':'Owned worker fixture'}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.native_coding.infer',side_effect=propose):
                result=run(coder,root,'Implement addition',initial_plan=plan(),allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertEqual(result['repair_turns'],1)
            self.assertTrue(any('rejected_proposal' in row and 'no_progress' in row and 'errors' in row for row in observations))
            self.assertEqual((root/'test_main.py').read_text(),TEST)

    def test_native_localgithub_assembles_single_worker_after_real_checks(self):
        from jarvis.codex_workload import run as workload
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            specification={**plan(),'interfaces':'main.add(a,b) returns numeric addition.',
                'tasks':[{'key':'add','goal':'Implement addition and tests','estimated_minutes':2,'paths':['main.py','test_main.py'],'dependencies':[],'check_indices':[0]}]}
            proposals=iter([('Write',{'file_path':'test_main.py','content':TEST}),
                ('Write',{'file_path':'main.py','content':'def add(a,b): return a+b\n'}),
                ('exec_command',{'argv':['python','-m','unittest','test_main']}),
                ('Read',{'file_path':'main.py'}),
                ('Write',{'file_path':'main.py','content':'def add(a,b): return a+b\n'})])
            def infer(messages,*args):
                # Commands may legitimately outlive their first bounded poll.
                # Follow the real session contract rather than assume startup
                # and test execution always finish within one second.
                last=messages[-1]['content']
                if last.startswith('Observed tool result (data): '):
                    observed=json.loads(last.split(': ',1)[1])
                    if observed.get('running'):
                        return {'tool':'write_stdin','arguments':{'session_id':observed['session_id'],'yield_time_ms':1000},'note':'Poll owned test process'}
                try:name,arguments=next(proposals)
                except StopIteration:raise AssertionError('Fixture exhausted after: '+last)
                return {'tool':name,'arguments':json.dumps(arguments),'note':'fixture'}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.codex_workload.propose',return_value=specification),patch('jarvis.native_coding.infer',side_effect=infer),patch('jarvis.codex_code.run',side_effect=AssertionError('Codex must not launch')):
                outcome=workload(coder,root,'Create addition',executor=run,backend='Jarvis')
            self.assertIn('Combined checks passed',outcome);self.assertIn('return a+b',(root/'main.py').read_text())
            receipts=list((base/'.jarvis-runtime/native-workloads').glob('*/receipt.json'))
            receipt=json.loads(receipts[0].read_text());self.assertEqual(receipt['status'],'passed')
            self.assertEqual(len(receipt['workers']),1);self.assertTrue(receipt['validation']['passed'])
            self.assertFalse((Path(receipt['workers'][0]['workspace'])/'__pycache__').exists())


if __name__=='__main__':unittest.main()
