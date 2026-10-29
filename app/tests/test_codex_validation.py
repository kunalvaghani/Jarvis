import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.codex_validation import contract, declare, inspect, validate_project, repair_packet, execute_check, test_evidence as validation_evidence, placeholders, error_summary


class CodexValidation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'project';self.root.mkdir()
        self.run=Path(self.temp.name)/'run';self.run.mkdir()
        self.plan={'files':[{'path':'logic.py','role':'logic','purpose':'Return the requested answer'},
            {'path':'test_logic.py','role':'test','purpose':'Verify the requested result is forty two'}],
            'checks':[{'kind':'python_tests','path':'test_logic.py'}]}
        (self.root/'test_logic.py').write_text('import unittest\nfrom logic import answer\nclass Checks(unittest.TestCase):\n    def test_answer(self): self.assertEqual(answer(),42)\n')

    def test_actual_failed_dependency_call_retains_scalar_operands_with_frozen_tests_unchanged(self):
        source=('from tkinter import Misc\nfrom types import SimpleNamespace\n'
                'def answer():\n return Misc.cget(SimpleNamespace(tk=SimpleNamespace(call=lambda *a: None),_w="."),0)\n')
        (self.root/'logic.py').write_text(source)
        before=(self.root/'test_logic.py').read_bytes()
        result=validate_project(self.root,self.run,'Return the requested answer',[],self.plan,lambda:False,Mock())
        self.assertFalse(result['passed'])
        facts=result['errors'][0]['runtime_failure_facts']
        frame=next(frame for row in facts for frame in row['frames'] if frame['module_path']=='tkinter/__init__.py')
        self.assertEqual(frame['operands']['key'],{'type':'int','value':0})
        from jarvis.source_observation import failure_context
        context=failure_context(result['errors'][0],SimpleNamespace(root=self.root,tests={'test_logic.py'}))
        self.assertEqual(context['installed_stdlib_source']['observed_operands']['key'],{'type':'int','value':0})
        self.assertIn('TypeError:',result['errors'][0]['error'])
        self.assertEqual((self.root/'test_logic.py').read_bytes(),before)
        self.assertEqual((self.root/'logic.py').read_text(),source)
        workspace=next(self.run.glob('check-workspace-*'))
        self.assertFalse(any(workspace.rglob('__pycache__')))

    def test_runtime_scalar_capture_omits_strings_objects_and_unbounded_numbers(self):
        from jarvis.codex_unittest_check import scalar_operands
        class NoRepr:
            def __repr__(self):raise AssertionError('Object repr must never run')
        values={'key':0,'text':'private_fixture_value','object':NoRepr(),'huge':10**100,'nan':float('nan')}
        facts=scalar_operands(values,set(values))
        self.assertEqual(facts['key'],{'type':'int','value':0})
        self.assertEqual(facts['text'],{'type':'str'})
        self.assertNotIn('object',facts)
        self.assertNotIn('value',facts['huge']);self.assertNotIn('value',facts['nan'])
        self.assertNotIn('private_fixture_value',json.dumps(facts,allow_nan=False))

    def test_unittest_check_rejects_application_role_before_generation(self):
        for role in ('entrypoint','logic','frontend'):
            value=json.loads(json.dumps(self.plan))
            value['files'][0]['role']=role
            value['checks'].append({'kind':'python_tests','path':'logic.py'})
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'test-role'):
                contract(self.root,'Create a Python graphical calculator',value)
            self.assertFalse((self.root/'logic.py').exists())
        self.assertEqual(contract(self.root,'Create a Python graphical calculator',self.plan),self.plan)

    def test_modular_gui_entrypoint_uses_declared_sources_at_checked_save_and_inspection(self):
        from jarvis.coding_files import FileSession
        ui='import tkinter as tk\ndef build_window():\n root=tk.Tk()\n button=tk.Button(root,text="Go",command=lambda:tk.Label(root,text="Done").pack())\n button.pack()\n return root\n'
        (self.root/'ui_builder.py').write_text(ui)
        value={'files':[{'path':'main.py','role':'entrypoint','purpose':'Launch the real graphical application'},
                        {'path':'ui_builder.py','role':'frontend','purpose':'Create real connected and laid out widgets'},
                        self.plan['files'][1]],'checks':self.plan['checks']}
        goal='Create a Python desktop calculator with a graphical interface'
        (self.run/'request.json').write_text(json.dumps({'project':str(self.root),'goal':goal,'validation_goal':goal,'allowed_paths':['main.py','ui_builder.py']}))
        (self.run/'validation-contract.json').write_text(json.dumps(value))
        session=FileSession(self.root,self.run)
        entry='from ui_builder import build_window\nif __name__=="__main__":\n build_window().mainloop()\n'
        test_before=(self.root/'test_logic.py').read_bytes()
        result=session.call('Write',{'file_path':'main.py','content':entry})
        self.assertTrue(result['saved'])
        errors,_=inspect(self.root,value,[],goal)
        self.assertFalse(any('graphical UI' in e['error'] for e in errors))
        # An unrelated UI or imported stub cannot manufacture structural success.
        (self.root/'ui_builder.py').write_text('def build_window():\n return None\n')
        session.call('Read',{'file_path':'main.py'})
        with self.assertRaisesRegex(ValueError,'graphical UI'):
            session.call('Write',{'file_path':'main.py','content':entry+'# preserve guarded save\n'})
        self.assertEqual((self.root/'main.py').read_text(),entry)
        self.assertEqual((self.root/'test_logic.py').read_bytes(),test_before)

    def test_preserved_named_inputs_are_not_required_generated_deliverables(self):
        from jarvis.codex_validation import preserved_named_files
        (self.root/'logic.py').write_text('def answer():\n return 42\n')
        for name in ('PROJECT.md','REQUIREMENTS.md','modify.py'):(self.root/name).write_text('original protected input\n')
        before={name:(self.root/name).read_bytes() for name in ('PROJECT.md','REQUIREMENTS.md','modify.py')}
        goal='Repair logic.py. Preserve PROJECT.md and REQUIREMENTS.md byte-for-byte. Do not modify modify.py.'
        errors,hashes=inspect(self.root,self.plan,[],goal)
        self.assertEqual(errors,[])
        self.assertTrue({'PROJECT.md','REQUIREMENTS.md','modify.py'}<=set(hashes))
        self.assertEqual(preserved_named_files('Keep modify.py unchanged and update missing.py'),{'modify.py'})
        errors,_=inspect(self.root,self.plan,[],'Preserve PROJECT.md byte-for-byte and update missing.py')
        self.assertTrue(any(e['path']=='missing.py' and 'expected deliverables' in e['error'] for e in errors))
        errors,_=inspect(self.root,self.plan,[],'Create missing.py.')
        self.assertTrue(any(e['path']=='missing.py' and 'expected deliverables' in e['error'] for e in errors))
        errors,_=inspect(self.root,self.plan,[],'Preserve absent.md byte-for-byte')
        self.assertTrue(any(e['path']=='absent.md' and 'preservation does not authorize' in e['error'] for e in errors))
        errors,_=inspect(self.root,self.plan,[],'Preserve calculations in modify.py while fixing its behavior')
        self.assertTrue(any(e['path']=='modify.py' and 'expected deliverables' in e['error'] for e in errors))
        self.assertEqual(before,{name:(self.root/name).read_bytes() for name in before})

    def test_preserved_input_bytes_remain_guarded_even_when_not_output_deliverables(self):
        (self.root/'logic.py').write_text('def answer():\n return 42\n')
        protected=self.root/'PROJECT.md';protected.write_text('original reference\n')
        frozen=(self.root/'test_logic.py').read_bytes()
        def mutated_check(*args,**kwargs):
            protected.write_text('changed during check\n')
            return {'exit_code':0,'output':'Ran 1 test in 0.001s\nOK\n','seconds':0.001}
        with patch('jarvis.codex_validation.execute_check',side_effect=mutated_check):
            with self.assertRaisesRegex(ValueError,'Source changed during validation: PROJECT.md'):
                validate_project(self.root,self.run,'Repair logic.py. Preserve PROJECT.md byte-for-byte.',[],self.plan,lambda:False,lambda *a:None)
        self.assertEqual((self.root/'test_logic.py').read_bytes(),frozen)

    def test_contract_requires_behavior_and_backend_integration(self):
        self.assertEqual(contract(self.root,'create a script',self.plan),self.plan)
        with self.assertRaisesRegex(ValueError,'behavioral'):contract(self.root,'create a script',{**self.plan,'checks':[{'kind':'python_script','path':'logic.py'}]})
        with self.assertRaisesRegex(ValueError,'frontend and backend'):contract(self.root,'create a full-stack app',self.plan)
        with self.assertRaisesRegex(ValueError,'relative'):contract(self.root,'create a script',{'files':[{'path':'../outside.py','role':'logic','purpose':'Implementation'}],'checks':self.plan['checks']})

    def test_new_python_application_requires_entrypoint_but_library_and_existing_scope_do_not(self):
        from jarvis.codex_validation import plain_python_application_goal
        goal='Create a new Python calculator application with input validation and tests.'
        with self.assertRaisesRegex(ValueError,'runnable .py entrypoint'):
            contract(self.root,goal,self.plan)
        value=json.loads(json.dumps(self.plan));value['files'][0]['role']='entrypoint'
        self.assertEqual(contract(self.root,goal,value),value)
        self.assertEqual(contract(self.root,'Create a Python library for a calculator application',self.plan),self.plan)
        self.assertFalse(plain_python_application_goal('Create a Python module app.py'))
        self.assertFalse(plain_python_application_goal('Create a Python desktop application'))
        self.assertFalse(plain_python_application_goal('Create a Python UI application using PySide6'))
        self.assertTrue(plain_python_application_goal('Create a Python application without GUI'))
        self.assertFalse(plain_python_application_goal('Create a Python backend application'))
        self.assertEqual(contract(self.root,goal,self.plan,partial=True),self.plan)
        (self.root/'existing.py').write_text('VALUE = 1\n')
        self.assertEqual(contract(self.root,goal,self.plan),self.plan)

    def test_declared_missing_file_reports_purpose_and_exact_path(self):
        errors,_=inspect(self.root,self.plan,[],'create a script')
        self.assertTrue(any(e['path']=='logic.py' and 'Return the requested answer' in e['error'] for e in errors))
        packet=repair_packet(self.root,{'errors':errors},self.plan)
        self.assertEqual(packet['expected_deliverables'],self.plan['files'])
        self.assertEqual(packet['source_attachments'][0]['path'],'test_logic.py')
        self.assertEqual(packet['source_attachments'][0]['sha256'],hashlib.sha256((self.root/'test_logic.py').read_bytes()).hexdigest())

    def test_early_source_failure_retains_full_validation_evidence(self):
        result=validate_project(self.root,self.run,'Create a script',[],self.plan,lambda:False,lambda *args:None)
        self.assertFalse(result['passed'])
        self.assertTrue(any(e['path']=='logic.py' for e in result['errors']))
        self.assertEqual(json.loads(Path(result['evidence']).read_text())['errors'],result['errors'])
        self.assertEqual(json.loads((self.run/'validation.json').read_text())['errors'],result['errors'])

    def test_placeholders_and_missing_frontend_resources_are_failures(self):
        quiet='from http.server import SimpleHTTPRequestHandler\nclass Quiet(SimpleHTTPRequestHandler):\n    def log_message(self,*args): pass\n'
        self.assertEqual(placeholders(Path('server.py'),quiet),[])
        factory='import http.server\ndef factory(base=http.server.BaseHTTPRequestHandler):\n    class Quiet(base):\n        def log_message(self,*args): pass\n    return Quiet\n'
        self.assertEqual(placeholders(Path('server.py'),factory),[])
        self.assertIn('Empty function: log_message',placeholders(Path('logic.py'),'class Worker:\n    def log_message(self,*args): pass\n'))
        (self.root/'logic.py').write_text('def answer():\n    pass\n')
        (self.root/'index.html').write_text('<html><script src="ui.js"></script><link rel="stylesheet" href="ui.css"></html>')
        errors,_=inspect(self.root,self.plan,['index.html'],'create a script')
        self.assertTrue(any('Empty function' in e['error'] for e in errors))
        self.assertEqual({e['path'] for e in errors if 'resource' in e['error']},{'ui.js','ui.css'})
        (self.root/'logic.py').write_text('def answer():\n    return 42\n')
        (self.root/'index.html').write_text('<html><script src="/ui.js?v=1"></script><link rel="stylesheet" href="/my%20style.css"></html>')
        (self.root/'ui.js').write_text('console.log("ready");')
        (self.root/'my style.css').write_text('body {color:white;}')
        errors,_=inspect(self.root,self.plan,['index.html'],'create a script with package.json')
        self.assertEqual([e['path'] for e in errors],['package.json'])

    def test_repair_cannot_drop_deliverables_or_weaken_checks(self):
        (self.run/'request.json').write_text(json.dumps({'goal':'create a script'}))
        declare(self.root,self.run,self.plan)
        before=(self.run/'validation-contract.json').read_bytes()
        self.assertEqual(declare(self.root,self.run,{})['checks'],self.plan['checks'])
        self.assertEqual((self.run/'validation-contract.json').read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'not a quoted JSON string'):
            declare(self.root,self.run,{**self.plan,'files':json.dumps(self.plan['files'])})
        with self.assertRaisesRegex(ValueError,'remove expected'):declare(self.root,self.run,{'files':self.plan['files'][1:],'checks':self.plan['checks']})
        with self.assertRaisesRegex(ValueError,'weaken'):declare(self.root,self.run,{**self.plan,'checks':[{'kind':'python_tests','path':'logic.py'}]})
        extended={**self.plan,'checks':self.plan['checks']+[{'kind':'python_script','path':'logic.py'}]}
        self.assertEqual(declare(self.root,self.run,extended)['checks'],extended['checks'])

    def test_declared_test_file_cannot_be_left_unexecuted(self):
        extra={**self.plan,'files':self.plan['files']+[{'path':'test_extra.py','role':'test','purpose':'Test additional requested behavior'}]}
        with self.assertRaisesRegex(ValueError,'test_extra.py'):contract(self.root,'create a script',extra)
        result=validate_project(self.root,self.run,'create a script',[],extra,lambda:False,Mock())
        self.assertFalse(result['passed']);self.assertIn('test_extra.py',result['errors'][0]['error'])

    def test_web_backend_does_not_require_desktop_window_but_gui_script_does(self):
        from jarvis.codex_files import execute, READS
        plan={'files':[{'path':'index.html','role':'frontend','purpose':'Visible web counter UI'},
                       {'path':'server.py','role':'backend','purpose':'Real HTTP server and counter API'}],
              'checks':[{'kind':'browser','path':'index.html','server':{'kind':'python','path':'server.py'},
                         'steps':[{'action':'text','selector':'h1','value':'Counter'}]}]}
        goal='Create a full-stack app in index.html and server.py with a working UI'
        (self.run/'request.json').write_text(json.dumps({'goal':goal,'require_validation':True}))
        READS.clear()
        with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(self.root),'JARVIS_CODEX_RUN':str(self.run)}):
            execute('Plan',plan)
            self.assertTrue(execute('Write',{'file_path':'server.py','content':'def serve():\n    return "http backend"\n'})['saved'])
        errors,_=inspect(self.root,plan,[],goal)
        self.assertFalse(any(e['path']=='server.py' for e in errors))
        from jarvis.codex_validation import desktop_gui_target
        test_plan={**plan,'files':plan['files']+[{'path':'test_server.py','role':'test','purpose':'Assert backend behavior'}],
                   'checks':plan['checks']+[{'kind':'python_tests','path':'test_server.py'}]}
        test_goal='Convert test_server.py to unittest and preserve the existing UI'
        self.assertFalse(desktop_gui_target(self.root,self.root/'test_server.py',test_goal,test_plan))
        unchecked={**test_plan,'checks':plan['checks']}
        self.assertTrue(desktop_gui_target(self.root,self.root/'test_server.py',test_goal,unchecked))
        (self.run/'request.json').write_text(json.dumps({'goal':test_goal,'require_validation':True}))
        (self.run/'validation-contract.json').write_text(json.dumps(test_plan))
        with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(self.root),'JARVIS_CODEX_RUN':str(self.run)}):
            self.assertTrue(execute('Write',{'file_path':'test_server.py','content':'import unittest\nclass Checks(unittest.TestCase):\n    def test_count(self): self.assertEqual(1,1)\n'})['saved'])
        desktop={**self.plan,'files':[{'path':'main.py','role':'entrypoint','purpose':'Desktop GUI application'},self.plan['files'][1]]}
        (self.run/'request.json').write_text(json.dumps({'goal':'Add a working UI to main.py','require_validation':True}))
        (self.run/'validation-contract.json').write_text(json.dumps(desktop))
        with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(self.root),'JARVIS_CODEX_RUN':str(self.run)}):
            with self.assertRaisesRegex(ValueError,'graphical UI'):
                execute('Write',{'file_path':'main.py','content':'def main():\n    return 1\n'})

    def test_actual_browser_rejects_static_backend_and_reports_http_failure(self):
        plan={'files':[{'path':'index.html','role':'frontend','purpose':'Counter UI fixture'},
                       {'path':'server.py','role':'backend','purpose':'Owned HTTP fixture server'}],
              'checks':[{'kind':'browser','path':'index.html','server':{'kind':'python','path':'server.py'},
                         'steps':[{'action':'text','selector':'h1','value':'Counter'}]}]}
        (self.root/'server.py').write_text('import argparse\nfrom http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler\n'
            'parser=argparse.ArgumentParser()\nparser.add_argument("--port",type=int)\nparser.add_argument("--data-dir")\n'
            'args=parser.parse_args()\nThreadingHTTPServer(("127.0.0.1",args.port),SimpleHTTPRequestHandler).serve_forever()\n')
        (self.root/'index.html').write_text('<html><meta name="viewport" content="width=device-width"><h1>Counter</h1></html>')
        result=validate_project(self.root,self.run,'create a full-stack app',[],plan,lambda:False,Mock())
        self.assertFalse(result['passed']);self.assertIn('No successful real frontend-to-backend',result['errors'][0]['error'])
        (self.root/'index.html').write_text('<html><meta name="viewport" content="width=device-width"><h1>Counter</h1>'
            '<div id="count">0</div><script>fetch("/missing-api");</script></html>')
        plan['checks'][0]['steps']=[{'action':'text','selector':'#count','value':'1'}]
        result=validate_project(self.root,self.run,'create a full-stack app',[],plan,lambda:False,Mock())
        self.assertFalse(result['passed']);error=result['errors'][0]['error']
        self.assertIn('Browser step failed',error);self.assertIn('404',error);self.assertIn('/missing-api',error)
        plan['checks'][0].pop('server')
        (self.root/'index.html').write_text('<html><meta name="viewport" content="width=device-width"><h1>Counter</h1><div id="count">10</div></html>')
        result=validate_project(self.root,self.run,'create a frontend site',[],plan,lambda:False,Mock())
        self.assertFalse(result['passed']);self.assertIn('Browser step failed',result['errors'][0]['error'])
        self.assertIn('10',result['errors'][0]['error'])

    def test_actual_browser_rejects_wrong_root_even_when_named_frontend_works(self):
        plan={'files':[{'path':'index.html','role':'frontend','purpose':'Counter UI fixture'},
                       {'path':'server.py','role':'backend','purpose':'Owned API fixture server'}],
              'checks':[{'kind':'browser','path':'index.html','server':{'kind':'python','path':'server.py'},
                         'steps':[{'action':'text','selector':'h1','value':'Counter'}]}]}
        (self.root/'index.html').write_text('<html><meta name="viewport" content="width=device-width">'
            '<h1>Counter</h1><script>fetch("/api/count")</script></html>')
        (self.root/'server.py').write_text('import argparse\nfrom http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler\n'
            'parser=argparse.ArgumentParser()\nparser.add_argument("--port",type=int)\nparser.add_argument("--data-dir")\n'
            'args=parser.parse_args()\nclass Handler(SimpleHTTPRequestHandler):\n'
            '    def do_GET(self):\n'
            '        if self.path not in ("/","/api/count"):\n            return super().do_GET()\n'
            '        body=b"<h1>Wrong homepage</h1>" if self.path=="/" else b"{\\"count\\":0}"\n'
            '        self.send_response(200)\n        self.send_header("Content-Length",str(len(body)))\n'
            '        self.end_headers()\n        self.wfile.write(body)\n'
            'ThreadingHTTPServer(("127.0.0.1",args.port),Handler).serve_forever()\n')
        result=validate_project(self.root,self.run,'create a full-stack app',[],plan,lambda:False,Mock())
        self.assertFalse(result['passed'])
        self.assertIn('Wrong homepage',result['errors'][0]['error'])

    def test_persistent_serial_backend_rejected_then_threaded_server_passes(self):
        plan={'files':[{'path':'index.html','role':'frontend','purpose':'Counter UI'},
                       {'path':'server.py','role':'backend','purpose':'Owned HTTP server'}],
              'checks':[{'kind':'browser','path':'index.html','server':{'kind':'python','path':'server.py'},
                         'steps':[{'action':'text','selector':'h1','value':'Counter'}]}]}
        (self.root/'index.html').write_text('<html><meta name="viewport" content="width=device-width">'
            '<h1>Counter</h1><script>fetch("/api/count")</script></html>')
        source=('import argparse\nfrom http.server import HTTPServer,ThreadingHTTPServer,SimpleHTTPRequestHandler\n'
                'p=argparse.ArgumentParser()\np.add_argument("--port",type=int)\np.add_argument("--data-dir")\na=p.parse_args()\n'
                'class Handler(SimpleHTTPRequestHandler):\n'
                '    protocol_version="HTTP/1.1"\n'
                '    def do_GET(self):\n'
                '        if self.path!="/api/count":\n            return super().do_GET()\n'
                '        body=b"{\\"count\\":0}"\n        self.send_response(200)\n'
                '        self.send_header("Content-Length",str(len(body)))\n'
                '        self.end_headers()\n        self.wfile.write(body)\n'
                'HTTPServer(("127.0.0.1",a.port),Handler).serve_forever()\n')
        (self.root/'server.py').write_text(source)
        first=validate_project(self.root,self.run,'create a full-stack app',[],plan,lambda:False,Mock())
        self.assertFalse(first['passed'])
        self.assertIn('independent GET /',first['errors'][0]['error'])
        (self.root/'server.py').write_text(source.replace('\nHTTPServer(', '\nThreadingHTTPServer('))
        second=validate_project(self.root,self.run,'create a full-stack app',[],plan,lambda:False,Mock())
        self.assertTrue(second['passed'],second['errors'])

    def test_actual_python_runtime_failure_then_fixed_retest(self):
        (self.root/'logic.py').write_text('def answer():\n    return 41\n')
        first=validate_project(self.root,self.run,'create a script',['logic.py'],self.plan,lambda:False,Mock())
        self.assertFalse(first['passed']);self.assertIn('41 != 42',first['errors'][0]['error'])
        self.assertIn('41 != 42',error_summary(first['errors'][0]))
        self.assertNotIn('Traceback',error_summary(first['errors'][0]))
        (self.root/'logic.py').write_text('def answer():\n    return 42\n')
        second=validate_project(self.root,self.run,'create a script',['logic.py'],self.plan,lambda:False,Mock())
        self.assertTrue(second['passed']);self.assertTrue(second['runtime_verified'])
        self.assertIn('Ran 1 test',second['checks'][0]['output'])

    def test_zero_tests_and_skipped_tests_do_not_pass(self):
        (self.root/'logic.py').write_text('def answer():\n    return 42\n')
        for content in ('import unittest\nclass Checks(unittest.TestCase):\n    def helper(self): self.assertTrue(True)\n','import unittest\nclass Checks(unittest.TestCase):\n    @unittest.skip("later")\n    def test_result(self): self.assertTrue(False)\n'):
            (self.root/'test_logic.py').write_text(content)
            result=validate_project(self.root,self.run,'create a script',[],self.plan,lambda:False,Mock())
            self.assertFalse(result['passed']);self.assertIn('unverified',result['errors'][0]['error'])

    def test_shared_deadline_stop_and_timeout_never_replay_check(self):
        with self.assertRaisesRegex(ValueError,'before launch'):
            execute_check([sys.executable,'-c','print(1)'],self.root,self.run,lambda:True)
        with self.assertRaisesRegex(ValueError,'timed out'):
            execute_check([sys.executable,'-c','import time;time.sleep(30)'],self.root,self.run,lambda:False,seconds=.3)

    def test_node_and_package_results_require_actual_unskipped_tests(self):
        for kind,output in [('node_tests','# tests 0\n# pass 0'),('node_tests','# tests 1\n# skipped 1'),
                            ('npm_test','Completed successfully'),('npm_test','Tests 1 passed | 1 todo')]:
            with self.subTest(kind=kind,output=output),self.assertRaisesRegex(ValueError,'unverified'):
                validation_evidence(kind,output)
        for kind,output in [('node_tests','# tests 2\n# pass 2\n# skipped 0'),
                            ('npm_test','Tests 3 passed (3)'),('npm_test','2 passed (1.2s)'),
                            ('npm_test','\x1b[32mTests\x1b[0m 3 passed (3)')]:
            validation_evidence(kind,output)

    def test_source_changed_during_test_stops_before_repair(self):
        source=self.root/'logic.py';source.write_text('def answer():\n    return 42\n')
        def change(*args,**kwargs):
            source.write_text('def answer():\n    return 99\n')
            return {'exit_code':0,'output':'Ran 1 test\nOK','seconds':0}
        with patch('jarvis.codex_validation.execute_check',side_effect=change):
            with self.assertRaisesRegex(ValueError,'changed during validation'):
                validate_project(self.root,self.run,'create a script',[],self.plan,lambda:False,Mock())

    def test_nested_package_check_launches_in_its_actual_manifest_directory(self):
        import shutil
        if not shutil.which('node'):self.skipTest('Installed Node runtime required; no installation attempted.')
        package=self.root/'web';package.mkdir()
        (package/'package.json').write_text(json.dumps({'name':'validation-fixture','private':True,
            'scripts':{'test':'node --test test_package.cjs'}}))
        (package/'test_package.cjs').write_text("const test = require('node:test');\nconst assert = require('node:assert/strict');\ntest('package cwd', () => assert.equal(process.cwd(), __dirname));\n")
        plan={'files':[{'path':'web/package.json','role':'configuration','purpose':'Declare a controlled Node test'},
                       {'path':'web/test_package.cjs','role':'test','purpose':'Assert real subprocess package directory'}],
              'checks':[{'kind':'npm_test','path':'web/package.json'}]}
        result=validate_project(self.root,self.run,'Validate a nested package',[],plan,lambda:False,Mock())
        self.assertTrue(result['passed'],result['errors'])
        self.assertIn('package cwd',result['checks'][0]['output'])
        invalid={**plan,'checks':[{'kind':'npm_test','path':'web/test_package.cjs'}]}
        with self.assertRaisesRegex(ValueError,'actual package.json'):contract(self.root,'Validate package',invalid)

    def test_missing_dependency_is_failure_not_installed_or_credited(self):
        (self.root/'logic.py').write_text('import jarvis_missing_fixture_dependency\ndef answer():\n    return 42\n')
        result=validate_project(self.root,self.run,'create a script',[],self.plan,lambda:False,Mock())
        self.assertFalse(result['passed']);self.assertIn('ModuleNotFoundError',result['errors'][0]['error'])

    def test_new_react_project_cannot_substitute_plain_files_or_omit_build(self):
        from jarvis.codex_validation import contract,inspect,react_goal
        with self.assertRaisesRegex(ValueError,'React project requires a declared package.json'):
            contract(self.root,'Create a React website',self.plan)
        plan={'files':self.plan['files']+[{'path':'package.json','role':'configuration','purpose':'Declare React build dependencies'}],
              'checks':self.plan['checks'][:]}
        with self.assertRaisesRegex(ValueError,'npm_build'):
            contract(self.root,'Create a React website',plan)
        plan['checks'].append({'kind':'npm_build','path':'package.json'})
        with self.assertRaisesRegex(ValueError,'actual declared HTML'):
            contract(self.root,'Create a React website',plan)
        plan['files'].append({'path':'index.html','role':'entrypoint','purpose':'Launch the actual React website'})
        plan['checks'].append({'kind':'browser','path':'index.html','steps':[{'action':'text','selector':'h1','value':'Website'}]})
        (self.root/'index.html').write_text('<html><body><h1>Website</h1></body></html>')
        contract(self.root,'Create a React website',plan)
        copy=json.loads(json.dumps(plan));copy['files'].append({'path':'test_ui.html','role':'test','purpose':'An unrelated static test copy'})
        copy['checks'][-1]['path']='test_ui.html'
        with self.assertRaisesRegex(ValueError,'actual declared HTML'):
            contract(self.root,'Create a React dashboard',copy)
        from jarvis.codex_validation import react_browser_goal
        self.assertFalse(react_browser_goal('Create a React helper library'))
        package=self.root/'package.json';package.write_text(json.dumps({'scripts':{'build':'vite build'}}))
        errors,_=inspect(self.root,plan,[],'Create a React website')
        self.assertTrue(any('does not declare the react dependency' in e['error'] for e in errors))
        package.write_text(json.dumps({'scripts':{'build':'vite build'},'dependencies':{'react':'18.2.0'}}))
        errors,_=inspect(self.root,plan,[],'Create a React website')
        self.assertFalse(any('react dependency' in e['error'] for e in errors))
        backend=self.root/'backend';backend.mkdir();(backend/'package.json').write_text(json.dumps({'name':'backend','dependencies':{}}))
        errors,_=inspect(self.root,plan,[],'Create a React website')
        self.assertFalse(any('react dependency' in e['error'] for e in errors))
        self.assertFalse(react_goal('Create a plain website without React'))

    def test_orchestrator_attaches_failure_to_new_codex_turn_then_retests(self):
        from jarvis.codex_code import run
        turns=[]
        def turn(coder,project,goal,cancelled,feedback,plan,deadline):
            folder=Path(self.temp.name)/('turn'+str(len(turns)));folder.mkdir()
            turns.append((feedback,plan));(folder/'result.json').write_text('{}')
            (self.root/'logic.py').write_text('def answer():\n    return '+('41' if len(turns)==1 else '42')+'\n')
            return {'directory':folder,'changed':['logic.py'],'report':'source saved','plan':self.plan}
        coder=SimpleNamespace(client=SimpleNamespace(options={}),actions=SimpleNamespace(report=Mock()))
        with patch('jarvis.codex_code._turn',side_effect=turn):
            result=run(coder,self.root,'create a script',lambda:False)
        self.assertEqual(len(turns),2);self.assertIn('41 != 42',turns[1][0]['errors'][0]['error'])
        self.assertEqual(turns[1][1],self.plan);self.assertIn('Repairs: 1',result)
        self.assertTrue(json.loads((Path(self.temp.name)/'turn1/result.json').read_text())['functional_behavior_verified'])

    def test_repair_limit_retains_partial_files_without_claiming_success(self):
        from jarvis.codex_code import run
        folder=Path(self.temp.name)/'turn';folder.mkdir();(folder/'result.json').write_text('{}')
        coder=SimpleNamespace(client=SimpleNamespace(options={'codex_max_repairs':0}),actions=SimpleNamespace(report=Mock()))
        with patch('jarvis.codex_code._turn',return_value={'directory':folder,'changed':[],'report':'done','plan':self.plan}) as turn:
            with self.assertRaisesRegex(ValueError,'verification failed'):run(coder,self.root,'create a script',lambda:False)
        turn.assert_called_once();self.assertTrue((self.root/'test_logic.py').exists())

    def test_shared_deadline_blocks_new_repair_turn(self):
        from jarvis.codex_code import run
        coder=SimpleNamespace(client=SimpleNamespace(options={'max_coding_seconds':60}),actions=SimpleNamespace(report=Mock()))
        with patch('jarvis.codex_code.time.monotonic',side_effect=[0,61]),patch('jarvis.codex_code._turn') as turn:
            with self.assertRaisesRegex(ValueError,'shared.*deadline'):run(coder,self.root,'create a script',lambda:False)
        turn.assert_not_called()

    def test_explicit_diagnostic_resume_validates_and_supplies_existing_plan(self):
        from jarvis.codex_code import run
        coder=SimpleNamespace(client=SimpleNamespace(options={}),actions=SimpleNamespace(report=Mock()))
        with patch('jarvis.codex_code._turn',side_effect=ValueError('boundary')) as turn:
            with self.assertRaisesRegex(ValueError,'boundary'):
                run(coder,self.root,'repair a script',lambda:False,initial_plan=self.plan,initial_feedback={'errors':[{'path':'logic.py','error':'Observed assertion failure'}]})
        self.assertEqual(turn.call_args.args[5],self.plan)
        self.assertEqual(turn.call_args.args[4]['errors'][0]['path'],'logic.py')
        with patch('jarvis.codex_code._turn') as turn:
            with self.assertRaisesRegex(ValueError,'behavioral'):
                run(coder,self.root,'repair a script',lambda:False,initial_plan={**self.plan,'checks':[{'kind':'python_script','path':'logic.py'}]})
        turn.assert_not_called()

    def test_file_writes_require_plan_before_any_mutation(self):
        from jarvis.codex_files import execute, READS
        (self.run/'request.json').write_text(json.dumps({'goal':'create a script','require_validation':True}))
        READS.clear()
        with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(self.root),'JARVIS_CODEX_RUN':str(self.run)}):
            with self.assertRaisesRegex(ValueError,'Call Plan'):execute('Write',{'file_path':'logic.py','content':'def answer():\n    return 42\n'})
            self.assertFalse((self.root/'logic.py').exists())
            self.assertFalse((self.run/'file-events.jsonl').exists())
            execute('Plan',self.plan)
            self.assertTrue(execute('Write',{'file_path':'logic.py','content':'def answer():\n    return 42\n'})['saved'])

    def test_rejected_syntax_proposal_attached_without_claiming_saved_file(self):
        from jarvis.codex_files import execute
        (self.run/'request.json').write_text(json.dumps({'goal':'create a script','require_validation':True}))
        broken='def answer():\n    try: return 42\n\nanswer()\n'
        with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(self.root),'JARVIS_CODEX_RUN':str(self.run)}):
            execute('Plan',self.plan)
            with self.assertRaisesRegex(ValueError,'preceding try'):
                execute('Write',{'file_path':'logic.py','content':broken})
        self.assertFalse((self.root/'logic.py').exists())
        rows=[json.loads(line) for line in (self.run/'file-events.jsonl').read_text().splitlines()]
        self.assertEqual([r['stage'] for r in rows],['rejected'])
        result=validate_project(self.root,self.run,'create a script',[],self.plan,lambda:False,Mock())
        packet=repair_packet(self.root,result,self.plan)
        proposal=packet['rejected_source_attachments'][0]
        self.assertTrue(proposal['not_applied']);self.assertEqual(proposal['proposed_source'],broken)

    def test_explicit_test_conversion_does_not_allow_app_interface_removal(self):
        from jarvis.codex_files import execute,READS
        (self.run/'request.json').write_text(json.dumps({'goal':'Convert test_logic.py to actual unittest assertions','require_validation':True}))
        (self.run/'validation-contract.json').write_text(json.dumps(self.plan))
        (self.root/'test_logic.py').write_text('def old_test_helper():\n    return True\n')
        (self.root/'logic.py').write_text('def answer():\n    return 42\n')
        READS.clear()
        with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(self.root),'JARVIS_CODEX_RUN':str(self.run)}):
            execute('Read',{'file_path':'test_logic.py'})
            self.assertTrue(execute('Write',{'file_path':'test_logic.py','content':'import unittest\nfrom logic import answer\nclass Tests(unittest.TestCase):\n    def test_answer(self): self.assertEqual(answer(),42)\n'})['saved'])
            execute('Read',{'file_path':'logic.py'})
            with self.assertRaisesRegex(ValueError,'removed existing functions'):
                execute('Write',{'file_path':'logic.py','content':'def new_answer():\n    return 42\n'})


if __name__=='__main__':unittest.main()
