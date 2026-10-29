import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.coder import Coder
from jarvis.codex_validation import validate_project
from jarvis.coding_files import UncertainCoding
from jarvis.native_coding import run,StalledCoding


class BoundedInterfaceCorrections(unittest.TestCase):
    def test_corrections_are_bounded_charged_and_never_replay_uncertain_or_changed_source(self):
        source=('class Service:\n def __init__(self):\n  self.nodes={"west":[],"east":[]}\n'
                +''.join('  self.state_'+str(i)+'="bounded independent fixture context"\n' for i in range(100)))
        frozen=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
                ' def setUp(self):\n  self.service=Service()\n  self.nodes=self.service.nodes\n'
                ' def test_direct(self): self.assertEqual(self.nodes["west"].send(),"ok")\n'
                ' def test_indexed(self): self.assertEqual(self.nodes["east"][0].send(),"ok")\n')
        plan={'files':[{'path':'worker.py','role':'logic','purpose':'Repair service'},
                       {'path':'test_worker.py','role':'test','purpose':'Keep original checks'}],
              'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
        fixed=('  class Endpoint:\n   def send(self): return "ok"\n'
               '   def __getitem__(self,key):\n    if key!=0: raise IndexError(key)\n    return self\n'
               '  self.nodes={"west":Endpoint(),"east":[Endpoint()]}')
        for mode in ('complete','candidate','repeat','cap','budget','drift','uncertain','rendered','equivalent'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);root=base/'project';root.mkdir();old_run=base/'prior';old_run.mkdir()
                (root/'worker.py').write_text(source);(root/'test_worker.py').write_text(frozen)
                prior=validate_project(root,old_run,'Repair service',[],plan,lambda:False,lambda *a:None)
                calls=[]
                def inference(messages,options,*args):
                    calls.append(options);index=len(calls)
                    if index==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                    if index==2:return {'tool':'run_checks','arguments':{}}
                    if index==3:return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                    if index==4:return {'tool':'read_slice','arguments':{'file_path':'worker.py','start':1,'count':24}}
                    if index==5:
                        self.assertTrue(options['native_diagnostic_plan'])
                        return {'tool':'update_plan','arguments':{'observed_cause':'Recorded interface mismatch.',
                            'strategy':'owned_compatible_interface','uncertainty':'Unchanged checks remain required.'}}
                    self.assertEqual(options['native_required_tool'],'edit_batch')
                    attempt=index-5;old='  self.nodes={"west":[],"east":[]}'
                    self.assertEqual(options['native_exact_edit_spans']['old_strings'],[old])
                    if attempt>1:
                        self.assertIn('Bounded corrective inference',json.dumps(messages))
                        self.assertNotIn('UNVERIFIED_NOTE_SUCCESS_SHOULD_NOT_FORWARD',json.dumps(messages))
                        if mode=='candidate':self.assertIn('rejected_candidate_failures',json.dumps(messages))
                        self.assertEqual((root/'worker.py').read_text(),source)
                    if mode=='uncertain':
                        (Path(args[-1])/'file-events.jsonl').write_text(json.dumps({'stage':'attempted','signature':'controlled-uncertain'})+'\n')
                    if mode=='drift':(root/'worker.py').write_text(source+'# external edit\n')
                    new=fixed if mode in ('complete','candidate') and attempt==2 else ' '* (4 if mode!='cap' else 2+2*attempt)+'self.nodes=( # incomplete fixture expression'
                    if mode=='rendered':new='\n'.join(line[2:] for line in fixed.splitlines())
                    if mode=='candidate' and attempt==1 or mode=='equivalent':new=' '* (2*attempt)+'self.nodes={"west":[],"east":[object()]}'
                    return {'tool':'edit_batch','note':'UNVERIFIED_NOTE_SUCCESS_SHOULD_NOT_FORWARD','arguments':{'file_path':'worker.py',
                        'source_sha256':options['native_exact_edit_spans']['sha256'],
                        'changes':[{'old_string':old,'new_string':new}]}}
                coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                    'native_require_repair_progress':True,'native_prior_validation_paths':['controlled-only'],
                    'native_max_repairs':1 if mode=='budget' else 6,'native_max_turns':32}))
                with patch('jarvis.workload_state.load_validation_history',return_value=([prior],[{'accepted':True}])),patch('jarvis.native_coding.infer',side_effect=inference):
                    if mode in ('complete','candidate','rendered'):
                        result=run(coder,root,'Repair service',initial_plan=plan,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
                        self.assertTrue(result['validation']['passed'])
                    else:
                        with self.assertRaises(UncertainCoding if mode=='uncertain' else StalledCoding):
                            run(coder,root,'Repair service',initial_plan=plan,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
                        result=json.loads(next((base/'.jarvis-runtime/native-code').glob('*/result.json')).read_text())
                        self.assertEqual((root/'worker.py').read_text(),source+('# external edit\n' if mode=='drift' else ''))
                self.assertEqual((root/'test_worker.py').read_text(),frozen)
                corrections=result.get('bounded_interface_corrections',[])
                self.assertEqual(len(corrections),1 if mode in ('complete','candidate','repeat','equivalent') else 2 if mode=='cap' else 0)
                if mode=='rendered':self.assertTrue(result['binding_renderings'][0]['changes'][0]['ast_unchanged'])
                if mode=='equivalent':self.assertEqual(len(result['candidate_decisions']),1)
                self.assertTrue(all(item['repair_turn_charged'] and not item['action_replayed'] for item in corrections))
                self.assertLessEqual(len(calls),8)
                self.assertEqual(result['progress']['diagnostic_plan_attempts'],1)


if __name__=='__main__':unittest.main()
