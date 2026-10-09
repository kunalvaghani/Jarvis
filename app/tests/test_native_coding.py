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


TEST='import unittest\nfrom main import add\nclass Addition(unittest.TestCase):\n def test_add(self):\n  self.assertEqual(add(2,3),5)\n  self.assertEqual(add(-2,3),1)\n'


def files(root):
    root.mkdir(exist_ok=True);run=root/'ledger';run.mkdir()
    (run/'request.json').write_text(json.dumps({'goal':'Create addition','require_validation':True,'test_first':True,'allowed_paths':['main.py','test_main.py']}))
    (run/'validation-contract.json').write_text(json.dumps(plan()))
    return FileSession(root,run)


class NativeCoding(unittest.TestCase):
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

    def test_native_localgithub_assembles_single_worker_after_real_checks(self):
        from jarvis.codex_workload import run as workload
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            specification={**plan(),'interfaces':'main.add(a,b) returns numeric addition.',
                'tasks':[{'key':'add','goal':'Implement addition and tests','estimated_minutes':2,'paths':['main.py','test_main.py'],'dependencies':[],'check_indices':[0]}]}
            proposals=iter([('Write',{'file_path':'test_main.py','content':TEST}),('Write',{'file_path':'main.py','content':'def add(a,b): return a+b\n'}),('finish',{})])
            def infer(*args):
                name,arguments=next(proposals);return {'tool':name,'arguments':json.dumps(arguments),'note':'fixture'}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
            with patch('jarvis.codex_workload.propose',return_value=specification),patch('jarvis.native_coding.infer',side_effect=infer),patch('jarvis.codex_code.run',side_effect=AssertionError('Codex must not launch')):
                outcome=workload(coder,root,'Create addition',executor=run,backend='Jarvis')
            self.assertIn('Combined checks passed',outcome);self.assertIn('return a+b',(root/'main.py').read_text())
            receipts=list((base/'.jarvis-runtime/native-workloads').glob('*/receipt.json'))
            receipt=json.loads(receipts[0].read_text());self.assertEqual(receipt['status'],'passed')
            self.assertEqual(len(receipt['workers']),1);self.assertTrue(receipt['validation']['passed'])


if __name__=='__main__':unittest.main()
