"""Controlled executable candidate regressions; not application acceptance."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.candidate_checks import CandidateChecks,CandidateRegression,CandidateLimit
from jarvis.coding_files import UncertainCoding
from jarvis.codex_validation import validate_project
from jarvis.coder import Coder
from jarvis.native_coding import run


SOURCE='class Service:\n def __init__(self): self.value=0\n def ready(self): return self.value\n'
TESTS=('import unittest\nfrom main import Service\nclass Checks(unittest.TestCase):\n'
       ' def test_existing(self): self.assertEqual(Service().value,0)\n'
       ' def test_new(self): self.assertEqual(Service().ready(),1)\n')
PLAN={'files':[{'path':'main.py','role':'logic','purpose':'Repair owned service implementation'},
               {'path':'test_main.py','role':'test','purpose':'Keep original and new behavior checked'}],
      'checks':[{'kind':'python_tests','path':'test_main.py'}]}


def fixture(base):
    project=base/'project';project.mkdir();ledger=base/'ledger';ledger.mkdir()
    (project/'main.py').write_text(SOURCE);(project/'test_main.py').write_text(TESTS)
    baseline=validate_project(project,ledger,'Repair service',[],PLAN,lambda:False,lambda *a:None)
    checker=CandidateChecks(project,ledger,'Repair service',PLAN,lambda:False,lambda *a:None)
    return project,ledger,baseline,checker


class CandidateVerification(unittest.TestCase):
    def test_scoped_repair_policy_rejects_neutral_save_but_preserves_default_and_green_edits(self):
        for strict,green in ((True,False),(False,False),(True,True)):
            with self.subTest(strict=strict,green=green),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);project=base/'project';project.mkdir()
                source=SOURCE.replace('return self.value','return 1') if green else SOURCE
                (project/'main.py').write_text(source);(project/'test_main.py').write_text(TESTS)
                calls=[]
                def inference(messages,options,*args):
                    calls.append(options);index=len(calls)
                    if strict:self.assertIn('Scoped repair progress policy',messages[0]['content'])
                    if index==1:return {'tool':'read_batch','arguments':{'paths':['main.py','test_main.py']}}
                    if index==2:return {'tool':'Write','arguments':{'file_path':'main.py','content':source+'# neutral observation\n'}}
                    if strict and not green:
                        self.assertEqual((project/'main.py').read_text(),source)
                        if index==3:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                        self.assertEqual(index,4)
                    else:self.assertIn('# neutral observation',(project/'main.py').read_text())
                    return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return self.value','new_string':'return 1','replace_all':False}}
                coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={
                    'native_max_repairs':6,'native_require_repair_progress':strict}))
                with patch('jarvis.native_coding.infer',side_effect=inference):
                    result=run(coder,project,'Repair controlled service',initial_plan=PLAN,allowed_paths=['main.py','test_main.py'],return_receipt=True)
                self.assertTrue(result['validation']['passed'])
                decisions=result['candidate_decisions']
                self.assertEqual(decisions[0]['progress_required'],strict and not green)
                self.assertEqual(decisions[0]['accepted_for_save'],not (strict and not green))
                self.assertEqual(result['require_repair_progress'],strict)
                self.assertEqual((project/'test_main.py').read_text(),TESTS)
                events=[json.loads(line) for line in (Path(result['directory'])/'file-events.jsonl').read_text().splitlines()]
                self.assertEqual(sum(row['stage']=='applied' for row in events),1 if strict or green else 2)

    def test_first_existing_source_write_captures_baseline_before_proposal(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';project.mkdir()
            (project/'main.py').write_text(SOURCE);(project/'test_main.py').write_text(TESTS);calls=[]
            def inference(messages,options,*args):
                calls.append(1);index=len(calls)
                if index in (1,3):return {'tool':'Read','arguments':{'file_path':'main.py'}}
                if index==2:return {'tool':'Write','arguments':{'file_path':'main.py','content':SOURCE.replace('value=0','value=1')}}
                self.assertEqual(index,4)
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':' def ready(self): return self.value',
                    'new_string':' def ready(self): return 1','replace_all':False}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),4)
            self.assertIn('test_main.Checks.test_existing',result['candidate_decisions'][0]['lost_previously_passing_cases']['test_main.py'])
            self.assertFalse(result['candidate_decisions'][0]['accepted_for_save'])
            self.assertEqual((project/'main.py').read_text(),SOURCE.replace('return self.value','return 1'))
            self.assertEqual((project/'test_main.py').read_text(),TESTS)

    def test_stop_after_inference_blocks_first_source_action_without_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';project.mkdir()
            (project/'main.py').write_text(SOURCE);(project/'test_main.py').write_text(TESTS);stopped=[False]
            calls=[]
            def inference(*args):
                calls.append(1)
                if len(calls)==1:return {'tool':'Read','arguments':{'file_path':'main.py'}}
                stopped[0]=True
                return {'tool':'Write','arguments':{'file_path':'main.py','content':SOURCE.replace('value=0','value=1')}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={}))
            with patch('jarvis.native_coding.infer',side_effect=inference),self.assertRaises(UncertainCoding):
                run(coder,project,'Repair service',cancelled=lambda:stopped[0],initial_plan=PLAN,allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertEqual((project/'main.py').read_text(),SOURCE)
            self.assertFalse(list((base/'.jarvis-runtime/native-code').glob('*/file-events.jsonl')))
            checker=CandidateChecks(project,base,'Repair service',PLAN,lambda:True,lambda *a:None)
            with self.assertRaises(UncertainCoding):checker.check('main.py','unused',{'python_test_outcomes':[]})

    def test_planned_candidate_cannot_trade_a_pass_gain_for_a_new_runtime_error(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';project.mkdir();ledger=base/'ledger';ledger.mkdir()
            source=SOURCE+' def extra(self): return 0\n'
            tests=TESTS+' def test_extra(self): self.assertEqual(Service().extra(),1)\n'
            (project/'main.py').write_text(source);(project/'test_main.py').write_text(tests)
            baseline=validate_project(project,ledger,'Repair service',[],PLAN,lambda:False,lambda *a:None)
            checker=CandidateChecks(project,ledger,'Repair service',PLAN,lambda:False,lambda *a:None)
            candidate=source.replace('return self.value','return 1').replace('def extra(self): return 0','def extra(self): raise RuntimeError("controlled")')
            with self.assertRaisesRegex(CandidateRegression,'new runtime errors'):
                checker.check('main.py',candidate,baseline,require_progress=True)
            decision=checker.decisions[-1];self.assertTrue(decision['newly_passing_cases']);self.assertTrue(decision['new_runtime_errors'])
            self.assertFalse(decision['accepted_for_save']);self.assertEqual((project/'main.py').read_text(),source)
            self.assertEqual((project/'test_main.py').read_text(),tests)

    def test_planned_candidate_rejects_neutral_change_and_accepts_case_gain(self):
        with tempfile.TemporaryDirectory() as folder:
            project,ledger,baseline,checker=fixture(Path(folder));before=(project/'main.py').read_bytes()
            with self.assertRaisesRegex(CandidateRegression,'no verified'):
                checker.check('main.py',SOURCE+'# neutral source version\n',baseline,require_progress=True)
            self.assertFalse(checker.decisions[-1]['verified_case_progress'])
            self.assertEqual((project/'main.py').read_bytes(),before)
            checker.check('main.py',SOURCE.replace('return self.value','return 1'),baseline,require_progress=True)
            self.assertTrue(checker.decisions[-1]['verified_case_progress']);self.assertTrue(checker.decisions[-1]['newly_passing_cases'])
            self.assertEqual((project/'main.py').read_bytes(),before)  # candidate proof never applies source

    def test_planned_candidate_can_advance_error_to_assertion_but_not_incomplete_outcomes(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project,ledger,_,checker=fixture(base)
            broken=SOURCE.replace('return self.value','raise RuntimeError("controlled")');(project/'main.py').write_text(broken)
            baseline=validate_project(project,ledger,'Repair service',[],PLAN,lambda:False,lambda *a:None)
            checker.check('main.py',SOURCE,baseline,require_progress=True)
            decision=checker.decisions[-1];self.assertTrue(decision['errors_reaching_assertions']);self.assertFalse(decision['newly_passing_cases'])
            incomplete=json.loads(json.dumps(baseline));incomplete['python_test_outcomes'][0].pop('error_ids')
            with self.assertRaises(UncertainCoding):checker.check('main.py',SOURCE+'# another candidate\n',incomplete,require_progress=True)
            self.assertEqual((project/'main.py').read_text(),broken)

    def test_completed_regression_is_rejected_and_not_executed_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            project,ledger,baseline,checker=fixture(Path(folder))
            self.assertEqual(len(baseline['python_test_outcomes'][0]['passed_ids']),1)
            bad=SOURCE.replace('value=0','value=1')
            for _ in range(2):
                with self.assertRaises(CandidateRegression):checker.check('main.py',bad,baseline)
            self.assertEqual(checker.count,1)
            self.assertEqual((project/'main.py').read_text(),SOURCE)
            self.assertEqual((project/'test_main.py').read_text(),TESTS)
            decision=checker.decisions[0]
            self.assertIn('test_main.Checks.test_existing',decision['lost_previously_passing_cases']['test_main.py'])
            self.assertFalse(decision['applied']);self.assertFalse(decision['accepted_for_save'])
            self.assertFalse(decision['verified_case_progress'])
            self.assertTrue(decision['case_classifications_complete'])
            self.assertEqual(len(list((ledger/'candidate-checks').glob('*/candidate-decision.json'))),1)

    def test_cancelled_or_stale_candidate_never_saves(self):
        for state in ['cancel','stale','budget']:
            with self.subTest(state=state),tempfile.TemporaryDirectory() as folder:
                project,ledger,baseline,checker=fixture(Path(folder))
                if state=='cancel':checker.cancelled=lambda:True
                if state=='stale':(project/'main.py').write_text(SOURCE+'# external change\n')
                if state=='budget':checker.count=8
                before=(project/'main.py').read_bytes()
                with self.assertRaises(CandidateLimit if state=='budget' else UncertainCoding):
                    checker.check('main.py',SOURCE.replace('return self.value','return 1'),baseline)
                self.assertEqual((project/'main.py').read_bytes(),before)

    def test_native_preflight_preserves_passed_case_then_commits_real_fix(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';project.mkdir()
            (project/'main.py').write_text(SOURCE);(project/'test_main.py').write_text(TESTS)
            calls=[]
            def inference(messages,options,*args):
                calls.append(options);index=len(calls)
                if index==1:return {'tool':'read_batch','arguments':{'paths':['main.py','test_main.py']}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index==3:return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'value=0','new_string':'value=1','replace_all':False}}
                if index==4:
                    self.assertEqual((project/'main.py').read_text(),SOURCE)
                    return {'tool':'Read','arguments':{'file_path':'main.py'}}
                self.assertEqual(index,5)
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return self.value','new_string':'return 1','replace_all':False}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *args:None),SimpleNamespace(options={'native_max_repairs':6}))
            with patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed'])
            self.assertEqual([d['accepted_for_save'] for d in result['candidate_decisions']],[False,True])
            self.assertEqual((project/'test_main.py').read_text(),TESTS)
            self.assertEqual((project/'main.py').read_text(),SOURCE.replace('return self.value','return 1'))
            events=[json.loads(line) for line in (Path(result['directory'])/'file-events.jsonl').read_text().splitlines()]
            self.assertEqual(sum(row['stage']=='applied' for row in events),1)

    def test_cancellation_or_source_change_after_checks_blocks_the_save(self):
        for state in ['cancel','stale']:
            with self.subTest(state=state),tempfile.TemporaryDirectory() as folder:
                project,ledger,baseline,checker=fixture(Path(folder))
                cancelled=[False];checker.cancelled=lambda:cancelled[0]
                def validate_then_interrupt(*args,**kwargs):
                    value=validate_project(*args,**kwargs)
                    if state=='cancel':cancelled[0]=True
                    else:(project/'main.py').write_text(SOURCE+'# external change\n')
                    return value
                with patch('jarvis.candidate_checks.validate_project',side_effect=validate_then_interrupt):
                    with self.assertRaises(UncertainCoding):checker.check('main.py',SOURCE.replace('return self.value','return 1'),baseline)
                self.assertEqual((project/'main.py').read_text(),SOURCE if state=='cancel' else SOURCE+'# external change\n')
                self.assertEqual(checker.decisions,[])


if __name__=='__main__':unittest.main()
