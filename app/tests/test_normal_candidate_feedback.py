"""A normal worker keeps actual candidate failure feedback across source reads."""
import hashlib,json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from jarvis.coder import Coder
from jarvis.native_coding import run


class NormalCandidateFeedback(unittest.TestCase):
    def test_normal_rejection_keeps_actual_exception_then_expires_after_source_save(self):
        source='class Service:\n prefix=">"\n def send(self): return self.prefix + "payload"\n def receive(self): return 0\n def count(self): return 0\n'
        frozen=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
                ' def test_existing(self): self.assertEqual(Service().send(),">payload")\n'
                ' def test_receive(self): self.assertEqual(Service().receive(),1)\n'
                ' def test_count(self): self.assertEqual(Service().count(),1)\n')
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';project.mkdir();calls=[]
            (project/'worker.py').write_text(source);(project/'test_worker.py').write_text(frozen)
            original_sha=hashlib.sha256((project/'worker.py').read_bytes()).hexdigest()
            plan={'files':[{'path':'worker.py','role':'logic','purpose':'Service'},
                           {'path':'test_worker.py','role':'test','purpose':'Fixed checks'}],
                  'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
            def infer(messages,options,*args):
                calls.append(options);index=len(calls);text=json.dumps(messages)
                if index==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index in (3,5,7):
                    if index==5:self.assertIn('TypeError',text);self.assertIn('rejected_candidate',text)
                    return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                if index==4:return {'tool':'Edit','arguments':{'file_path':'worker.py','old_string':' prefix=">"','new_string':' prefix=0','replace_all':False}}
                if index==6:
                    self.assertIn('Most recent rejected candidate under this unchanged working source',text)
                    self.assertIn('test_worker.Checks.test_existing',text);self.assertIn('TypeError',text)
                    return {'tool':'Edit','arguments':{'file_path':'worker.py','old_string':' def receive(self): return 0','new_string':' def receive(self): return 1','replace_all':False}}
                if index==8:
                    self.assertNotIn('Most recent rejected candidate under this unchanged working source',text)
                    return {'tool':'Edit','arguments':{'file_path':'worker.py','old_string':' def count(self): return 0','new_string':' def count(self): return 1','replace_all':False}}
                self.fail('Unexpected inference '+str(index))
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_require_repair_progress':True,'native_max_repairs':6,'native_max_turns':16}))
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,project,'Repair service',initial_plan=plan,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),8)
            feedback=result['candidate_feedback_handoffs'];self.assertEqual(len(feedback),1)
            self.assertEqual(feedback[0]['failures'][0]['exception']['type'],'TypeError')
            self.assertLessEqual(len(json.dumps(feedback[0])),3000)
            self.assertEqual(feedback[0]['working_source_sha256']['worker.py'],original_sha)
            self.assertEqual((project/'test_worker.py').read_text(),frozen)
            self.assertNotIn('prefix=0',(project/'worker.py').read_text())


if __name__=='__main__':unittest.main()
