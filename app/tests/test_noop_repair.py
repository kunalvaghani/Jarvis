"""Invalid no-op inference must not erase implementation evidence then teach a fake patch."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from jarvis.coder import Coder
from jarvis.native_coding import run,scoped_schema
from jarvis.structured_output import ModelOutputError,validate_contract


class NoopRepair(unittest.TestCase):
    def test_recovery_batch_cannot_bypass_missing_key_data_only_guard(self):
        from tests.test_key_producer import SOURCE,OLD,NEW
        frozen=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
                ' def setUp(self):\n  self.service=Service()\n  self.items=self.service.channels\n'
                ' def test_west(self): self.assertEqual(self.items["west"].send(),"ok")\n'
                ' def test_east(self): self.assertEqual(self.items["east"][0].send(),"ok")\n'
                ' def test_north(self): self.assertEqual(self.items["north"][0].send(),"ok")\n')
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';project.mkdir();calls=[]
            (project/'worker.py').write_text(SOURCE);(project/'test_worker.py').write_text(frozen)
            plan={'files':[{'path':'worker.py','role':'logic','purpose':'Service'},
                           {'path':'test_worker.py','role':'test','purpose':'Fixed checks'}],
                  'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
            def infer(messages,options,*args):
                calls.append(options);index=len(calls)
                if index==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index in (3,6):
                    if index==6:
                        self.assertEqual((project/'worker.py').read_text(),SOURCE)
                        self.assertIn('No method, loop or existing binding edits',json.dumps(messages))
                    return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                if index==4:raise ModelOutputError('Edit old_string and new_string are identical; no action executed.')
                if index==5:
                    self.assertEqual(options['native_required_tool'],'edit_batch')
                    scope=options['native_exact_edit_spans'];self.assertIn('literal_producer',scope)
                    return {'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':scope['sha256'],
                        'changes':[{'old_string':OLD,'new_string':NEW+'\n  self.channels={}'}]}}
                self.assertEqual(index,7)
                return {'tool':'Edit','arguments':{'file_path':'worker.py','old_string':OLD,'new_string':NEW,'replace_all':False}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_require_repair_progress':True,'native_max_repairs':6,'native_max_turns':16}))
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,project,'Repair service',initial_plan=plan,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),7)
            self.assertEqual(len(result['candidate_decisions']),1)
            self.assertEqual((project/'worker.py').read_text(),SOURCE.replace(OLD,NEW))
            self.assertEqual((project/'test_worker.py').read_text(),frozen)

    def test_single_python_recovery_keeps_fresh_source_and_uses_only_exact_statement_batch(self):
        source='class Service:\n def ready(self): return True\n def send(self): return "bad"\n'
        frozen=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
                ' def test_ready(self): self.assertTrue(Service().ready())\n'
                ' def test_send(self): self.assertEqual(Service().send(),"ok")\n')
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';project.mkdir();calls=[]
            (project/'worker.py').write_text(source);(project/'test_worker.py').write_text(frozen)
            plan={'files':[{'path':'worker.py','role':'logic','purpose':'Service'},
                           {'path':'test_worker.py','role':'test','purpose':'Fixed checks'}],
                  'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
            def infer(messages,options,stop,deadline,report,run_path):
                calls.append(options);index=len(calls)
                if index==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index==3:return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                if index==4:raise ModelOutputError('Edit old_string and new_string are identical; no action executed.')
                self.assertEqual(index,5);self.assertEqual(options['native_required_tool'],'edit_batch')
                prefix='Bounded statement recovery after a rejected no-op. Fresh complete implementation (read-only DATA): '
                observed=next(message['content'] for message in messages if message['content'].startswith(prefix))
                packet=json.loads(observed[len(prefix):].split('\nThe previous inference',1)[0])
                self.assertEqual(packet['current_source'],source)
                self.assertNotIn(' exact current context',json.dumps(messages))
                spans=options['native_exact_edit_spans'];self.assertIsNone(options['native_diagnostic_window'])
                schema=scoped_schema(run_path,force_tool='edit_batch',force_edit_paths=['worker.py'],force_edit_spans=spans)
                self.assertEqual([variant['properties']['tool']['enum'][0] for variant in schema['anyOf']],['edit_batch'])
                value={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':spans['sha256'],
                    'changes':[{'old_string':' def send(self): return "bad"','new_string':' def send(self): return "ok"'}]}}
                validate_contract(schema,value)
                with self.assertRaises(ValueError):
                    validate_contract(schema,{'tool':'apply_patch','arguments':{'patch':'placeholder'}})
                stale=json.loads(json.dumps(value));stale['arguments']['source_sha256']='0'*64
                with self.assertRaises(ValueError):validate_contract(schema,stale)
                return value
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_require_repair_progress':True,'native_max_repairs':6,'native_max_turns':16}))
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,project,'Repair service',initial_plan=plan,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),5)
            self.assertEqual((project/'test_worker.py').read_text(),frozen)
            self.assertEqual((project/'worker.py').read_text(),source.replace('return "bad"','return "ok"'))
            self.assertTrue(result['noop_statement_recoveries'][0]['fresh_source_supplied'])
            self.assertTrue(result['candidate_decisions'][0]['verified_case_progress'])


if __name__=='__main__':unittest.main()
