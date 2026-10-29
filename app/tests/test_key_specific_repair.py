"""Per-key intent must carry explicit model selector/value decisions."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.repair_contract import key_specific_spec,key_specific_schema,compile_key_specific_binding
from jarvis.structured_output import ModelOutputError,validate_contract
from jarvis.codex_validation import validate_project
from jarvis.coder import Coder
from jarvis.native_coding import run


class KeySpecificRepair(unittest.TestCase):
    def test_per_key_schema_and_compiler_keep_model_choices_and_original_fallback(self):
        old='   self.channels[name]=[item]'
        contract={'members':['channels'],'obligations':[{'accesses':[
            {'key':'west','subscripts_after_key':0},{'key':'east','subscripts_after_key':1}]}]}
        spec=key_specific_spec([old],contract);schema=key_specific_schema(spec)
        row={'old_string':old,'when_keys':['west'],'value_expression':'item'}
        validate_contract(schema,row)
        args,proof=compile_key_specific_binding({'changes':[row]},spec)
        self.assertIn("item if name in ('west',) else [item]",args['changes'][0]['new_string'])
        self.assertTrue(proof[0]['original_fallback_retained']);self.assertFalse(proof[0]['controller_supplied_selector_choices'])
        for bad in [{'old_string':old,'new_string':'self.channels[name]=item'},
                    {**row,'when_keys':['west','east']},
                    {**row,'when_keys':['unobserved']},{**row,'value_expression':'make_new_object()'}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_contract(schema,bad)
        with self.assertRaisesRegex(ModelOutputError,'different frozen access routes'):
            compile_key_specific_binding({'changes':[{**row,'when_keys':['west','east']}]},spec)
        for unsafe in ['self.channels[next_key()]=[item]','self.channels[name]=make_item()']:
            self.assertIsNone(key_specific_spec([unsafe],contract))

    def test_real_worker_cannot_dispatch_uniform_edit_for_key_specific_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';project.mkdir();prior_dir=base/'prior';prior_dir.mkdir()
            source=('class Port:\n def send(self): return "ok"\nclass Service:\n def __init__(self):\n'
                    '  self.channels={}\n  for name in ("west","east"):\n   item=Port()\n   self.channels[name]=[item]\n'
                    +''.join('  self.state_'+str(i)+'="unrelated source context"\n' for i in range(100)))
            frozen=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
                    ' def setUp(self):\n  self.service=Service()\n  self.items=self.service.channels\n'
                    ' def test_direct(self): self.assertEqual(self.items["west"].send(),"ok")\n'
                    ' def test_indexed(self): self.assertEqual(self.items["east"][0].send(),"ok")\n')
            (project/'worker.py').write_text(source);(project/'test_worker.py').write_text(frozen)
            plan={'files':[{'path':'worker.py','role':'logic','purpose':'Service'},{'path':'test_worker.py','role':'test','purpose':'Fixed checks'}],
                  'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
            prior=validate_project(project,prior_dir,'Repair service',[],plan,lambda:False,lambda *a:None);calls=[]
            def infer(messages,options,*args):
                calls.append(options);index=len(calls)
                if index==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index==3:return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                if index==4:return {'tool':'read_slice','arguments':{'file_path':'worker.py','start':1,'count':24}}
                if index==5:return {'tool':'update_plan','arguments':{'observed_cause':'Different observed per-key access routes.',
                    'strategy':'key_specific_values','uncertainty':'Original checks remain required.'}}
                spans=options['native_exact_edit_spans'];self.assertIn('key_specific',spans)
                row={'old_string':'   self.channels[name]=[item]','when_keys':['west'],'value_expression':'item'}
                if index==6:row={'old_string':row['old_string'],'new_string':'   self.channels[name]=item'}
                if index==7:self.assertIn('when_keys',json.dumps(messages))
                return {'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':spans['sha256'],'changes':[row]}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_require_repair_progress':True,'native_prior_validation_paths':['controlled'],
                'native_max_repairs':6,'native_max_turns':32}))
            with patch('jarvis.workload_state.load_validation_history',return_value=([prior],[{'accepted':True}])),patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,project,'Repair service',initial_plan=plan,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),7)
            self.assertEqual((project/'test_worker.py').read_text(),frozen)
            self.assertEqual(len(result['candidate_decisions']),1)
            self.assertTrue(result['candidate_decisions'][0]['verified_case_progress'])
            self.assertEqual(result['bounded_stage_contexts'][0]['stage'],'key_specific_values')


if __name__=='__main__':unittest.main()
