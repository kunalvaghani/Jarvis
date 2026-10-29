"""A later assertion cannot hide the runtime cause of a candidate regression."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from jarvis.candidate_checks import CandidateChecks,CandidateRegression,repair_feedback
from jarvis.codex_validation import validate_project,error_summary
from jarvis.candidate_checks import case_exception


class CandidateFeedback(unittest.TestCase):
    def test_case_traceback_exception_is_exactly_attributed_without_dependency_operands(self):
        value={'errors':[{'path':'test_worker.py','error':
            'ERROR: test_ready (test_worker.First)\nTraceback (most recent call last):\nRuntimeError: incompatible manager\n'
            'FAIL: test_ready (test_worker.Second.test_ready)\nAssertionError: different case\n'}]}
        first=case_exception(value,'test_worker.py','test_worker.First.test_ready')
        self.assertEqual(first['type'],'RuntimeError');self.assertEqual(first['message'],'incompatible manager')
        self.assertEqual(case_exception(value,'test_worker.py','test_worker.Second.test_ready')['type'],'AssertionError')
        self.assertIsNone(case_exception(value,'other.py','test_worker.First.test_ready'))
        self.assertIsNone(case_exception(value,'test_worker.py','test_worker.Third.test_ready'))
        value['errors'][0]['error']+='\nERROR: test_ready (test_worker.First)\nRuntimeError: ambiguous duplicate\n'
        self.assertIsNone(case_exception(value,'test_worker.py','test_worker.First.test_ready'))

    def test_actual_regressed_case_facts_survive_later_assertion_and_cached_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir();ledger=base/'ledger';ledger.mkdir()
            source='import textwrap\nclass Service:\n prefix=">"\n def send(self): return textwrap.indent("payload",self.prefix)\n'
            frozen=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
                    ' def test_saved_prefix(self): self.assertEqual(Service().send(),">payload")\n'
                    ' def test_z_unrelated(self): self.assertEqual(1,2)\n')
            (root/'worker.py').write_text(source);(root/'test_worker.py').write_text(frozen)
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
            plan={'files':[{'path':'worker.py','role':'logic','purpose':'Service'},
                           {'path':'test_worker.py','role':'test','purpose':'Fixed checks'}],
                  'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
            baseline=validate_project(root,ledger,'Repair service',[],plan,lambda:False,lambda *a:None)
            checker=CandidateChecks(root,ledger,'Repair service',plan,lambda:False,lambda *a:None)
            proposed=source.replace('prefix=">"','prefix=0')
            for attempt in range(2):
                with self.assertRaises(CandidateRegression) as caught:checker.check('worker.py',proposed,baseline,True)
                error=caught.exception
                self.assertIn('1 != 2',error_summary(error.validation['errors'][0]))
                rows=repair_feedback(error)
                self.assertEqual(len(rows),1);self.assertTrue(rows[0]['regressed']);self.assertTrue(rows[0]['new_runtime_error'])
                self.assertEqual(rows[0]['case_id'],'test_worker.Checks.test_saved_prefix')
                fact=rows[0]['runtime_failure_facts'][0]
                self.assertEqual(fact['exception_type'],'TypeError');self.assertEqual(fact['test_method'],'test_saved_prefix')
                self.assertIn('textwrap.py',json.dumps(fact));self.assertNotIn('1 != 2',json.dumps(rows))
            self.assertEqual(checker.count,1)
            self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()},before)

    def test_ambiguous_methods_and_mismatched_evidence_are_not_attributed(self):
        first='test_worker.First.test_shared';second='test_worker.Second.test_shared'
        value={'evidence':'owned','errors':[{'path':'test_worker.py','error':'AssertionError: unrelated',
                 'runtime_failure_facts':[{'test_method':'test_shared','exception_type':'TypeError'}]}],
               'python_test_outcomes':[{'path':'test_worker.py','passed_ids':[],'failed_ids':[], 'error_ids':[first,second]}]}
        decision={'candidate_evidence':'owned','lost_previously_passing_cases':{'test_worker.py':[first]},'new_runtime_errors':{}}
        rows=repair_feedback(CandidateRegression('Rejected',validation=value,decision=decision))
        self.assertNotIn('runtime_failure_facts',rows[0]);self.assertIn('details_unavailable',rows[0])
        self.assertEqual(repair_feedback(CandidateRegression('Rejected',validation=value,decision={**decision,'candidate_evidence':'other'})),[])


if __name__=='__main__':unittest.main()
