import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.native_coding import matching_prior_failure,run
from jarvis.coder import Coder


class SameSourceRecurrence(unittest.TestCase):
    def test_only_identical_current_bytes_and_failed_diagnostics_qualify(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'worker.py';path.write_text('value=[]\n')
            value={'passed':False,'hashes':{'worker.py':hashlib.sha256(path.read_bytes()).hexdigest()},
                   'errors':[{'path':'test_worker.py','error':'AttributeError: controlled failure'}]}
            self.assertEqual(matching_prior_failure(value,[value],root),0)
            for mutation in ('success','failure','source','empty'):
                old=json.loads(json.dumps(value))
                if mutation=='success':old['passed']=True
                if mutation=='failure':old['errors'][0]['error']='TypeError: another failure'
                if mutation=='source':old['hashes']['worker.py']='f'*64
                if mutation=='empty':old['hashes']={}
                self.assertIsNone(matching_prior_failure(value,[old],root))
            path.write_text('value={}\n');self.assertIsNone(matching_prior_failure(value,[value],root))

    def test_verified_recurrence_gets_one_plan_before_any_rejected_edit(self):
        from jarvis.codex_validation import validate_project
        source='class Service:\n def __init__(self): self.nodes={"west":[],"east":[]}\n'
        tests=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
               ' def setUp(self):\n  self.service=Service()\n  self.nodes=self.service.nodes\n'
               ' def test_direct(self): self.assertEqual(self.nodes["west"].send(),"ok")\n'
               ' def test_indexed(self): self.assertEqual(self.nodes["east"][0].send(),"ok")\n')
        fixed=('class Endpoint:\n def send(self): return "ok"\n'
               ' def __getitem__(self,key):\n  if key!=0: raise IndexError(key)\n  return self\n'
               'class Service:\n def __init__(self): self.nodes={"west":Endpoint(),"east":Endpoint()}\n')
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();ledger=base/'old';ledger.mkdir()
            (root/'worker.py').write_text(source);(root/'test_worker.py').write_text(tests)
            plan={'files':[{'path':'worker.py','role':'logic','purpose':'Repair service'},
                           {'path':'test_worker.py','role':'test','purpose':'Keep original checks'}],
                  'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
            old=validate_project(root,ledger,'Repair service',[],plan,lambda:False,lambda *a:None)
            calls=[]
            def inference(messages,options,*args):
                calls.append(options);index=len(calls)
                if index==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index==3:
                    current=json.loads((Path(args[-1])/'validation.json').read_text())
                    self.assertEqual(matching_prior_failure(current,[old],root),0,
                        json.dumps({'old_hashes':old['hashes'],'new_hashes':current['hashes'],
                                    'old_errors':old.get('errors'),'new_errors':current.get('errors')}))
                    return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                if index==4:
                    self.assertTrue(options['native_diagnostic_plan']);self.assertIsNotNone(options['native_protocol_contract'])
                    return {'tool':'update_plan','arguments':{'observed_cause':'Recorded access mismatch.',
                        'strategy':'owned_compatible_interface','uncertainty':'Original checks are required.'}}
                self.assertEqual(index,5);self.assertEqual(options['native_required_tool'],'Write')
                return {'tool':'Write','arguments':{'file_path':'worker.py','content':fixed}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_prior_validation_paths':['controlled-only'],'native_require_repair_progress':True}))
            with patch('jarvis.workload_state.load_validation_history',return_value=([old],[{'accepted':True}])),patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,root,'Repair service',initial_plan=plan,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),5)
            self.assertIn('source_bound_failure_recurrence',result)
            self.assertEqual(result['progress']['diagnostic_plan_attempts'],1)
            self.assertEqual(result['diagnostic_plans'][0]['rejected_repair_proposals'],0)
            self.assertEqual(result['progress']['failure_history_versions'],1)
            self.assertEqual((root/'test_worker.py').read_text(),tests)


if __name__=='__main__':unittest.main()
