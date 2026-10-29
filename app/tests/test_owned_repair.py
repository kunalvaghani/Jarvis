"""The selected owned-interface strategy cannot dispatch a borrowed value."""
import hashlib,json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.repair_contract import compile_owned_binding,owned_methods,owned_change_schema,frozen_failure_observations
from jarvis.structured_output import ModelOutputError,validate_contract
from jarvis.codex_validation import validate_project
from jarvis.coder import Coder
from jarvis.native_coding import run


DEFINITION={'name':'OwnedPort','methods':{
    '__init__':'def __init__(self,port): self.port=port',
    'send':'def send(self): return self.port.send()',
    '__getitem__':'def __getitem__(self,key):\n if key!=0: raise IndexError(key)\n return self'}}


class OwnedRepair(unittest.TestCase):
    def test_failure_facts_survive_rebuilding_without_old_source_or_string_values(self):
        frozen={'test_worker.py':'e'*64}
        def record(source,fact=None):return {'passed':False,'hashes':{'test_worker.py':'e'*64,'worker.py':source},
            'python_test_outcomes':[{'path':'test_worker.py','test_sha256':'e'*64,'partial':False,'successful':False,
                'failed_ids':[],'error_ids':['test_worker.Checks.test_protocol']}],
            'errors':[{'path':'test_worker.py','error':'MUST_NOT_FORWARD_ERROR_TEXT','proposed_source':'MUST_NOT_FORWARD_SOURCE',
                'runtime_failure_facts':[fact] if fact else []}]}
        fact={'test_method':'test_protocol','exception_type':'TypeError','frames':[{'module_path':'dependency.py','sha256':'a'*64,
            'line':7,'function':'getitem','operands':{'key':{'type':'int','value':0},'text':{'type':'str','value':'MUST_NOT_FORWARD_SECRET'},
                'large':{'type':'int'},'not_finite':{'type':'float','value':float('nan')}}}]}
        current=record('current');old=record('older',fact);wrong=record('wrong',fact);wrong['hashes']['test_worker.py']='f'*64
        rows=frozen_failure_observations(current,[current,old,wrong],frozen)
        self.assertEqual([row['kind'] for row in rows],['current_failed_check','historical_counterexample'])
        self.assertNotEqual(rows[0]['source_fingerprint'],rows[1]['source_fingerprint'])
        text=json.dumps(rows);self.assertNotIn('MUST_NOT_FORWARD',text);self.assertIn('TypeError',text)
        self.assertTrue(all(not row['current_check_credit'] for row in rows));self.assertLessEqual(len(text),3000)
        self.assertEqual(rows[1]['checks'][0]['runtime_failure_facts'][0]['frames'][0]['operands']['key']['value'],0)
        self.assertNotIn('value',rows[1]['checks'][0]['runtime_failure_facts'][0]['frames'][0]['operands']['large'])
        self.assertNotIn('NaN',text)

    def test_all_independent_component_errors_are_reported_together(self):
        args={'changes':[{'old_string':'   self.channels[name]=[item]',
            'owned_definition':{'name':'OwnedPort','methods':{**DEFINITION['methods'],
                '__getitem__':'def wrong_name(self,key): return self.port',
                'send':'def send(self): return ('}},'constructor_arguments':['item']}]}
        with self.assertRaises(ModelOutputError) as caught:compile_owned_binding(args,['__getitem__','send'])
        text=str(caught.exception)
        self.assertIn('__getitem__',text);self.assertIn('send',text)
        self.assertIn('complete def __getitem__',text)

    def test_schema_requires_every_method_and_forbids_assignment_arguments(self):
        old='   self.channels[name]=[item]';schema=owned_change_schema([old],['__getitem__','send'])
        row={'old_string':old,'owned_definition':DEFINITION,'constructor_arguments':['item']}
        validate_contract(schema,row)
        self.assertEqual(schema['properties']['constructor_arguments']['items']['enum'],['item','[item]'])
        for bad in [{**row,'constructor_arguments':['self.channels[name] = OwnedPort(item)']},
                    {**row,'owned_definition':{**DEFINITION,'methods':{'__init__':DEFINITION['methods']['__init__'],'send':DEFINITION['methods']['send']}}},
                    {**row,'owned_definition':'class Incomplete: pass'}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_contract(schema,bad)

    def test_owned_contract_requires_model_type_methods_and_construction(self):
        old='   self.channels[name]=[item]';args={'file_path':'worker.py','source_sha256':'a'*64,
            'changes':[{'old_string':old,'owned_definition':DEFINITION,'constructor_arguments':['item']}]}
        methods=owned_methods([old],{'obligations':[{'method':'send','accesses':[{'subscripts_after_key':0},{'subscripts_after_key':1}]}]})
        self.assertEqual(methods,['__getitem__','send'])
        compiled,proof=compile_owned_binding(args,methods)
        self.assertIn('self.channels[name] = OwnedPort(item)',compiled['changes'][0]['new_string'])
        self.assertFalse(proof[0]['controller_supplied_method_bodies']);self.assertEqual(args['changes'][0]['owned_definition'],DEFINITION)
        for change in [{'old_string':old,'new_string':'self.channels[name]=item'},
                       {**args['changes'][0],'constructor_arguments':['unobserved_object']},
                       {**args['changes'][0],'owned_definition':'class Empty:\n pass'},
                       {**args['changes'][0],'owned_definition':{**DEFINITION,'name':'class'}}]:
            with self.subTest(change=change),self.assertRaises(ModelOutputError):compile_owned_binding({**args,'changes':[change]},methods)

    def test_real_frozen_checks_require_owned_generation_and_keep_original_objects(self):
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
            plan={'files':[{'path':'worker.py','role':'logic','purpose':'Service'}, {'path':'test_worker.py','role':'test','purpose':'Fixed checks'}],
                  'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
            prior=validate_project(project,prior_dir,'Repair service',[],plan,lambda:False,lambda *a:None);calls=[]
            def infer(messages,options,*args):
                calls.append(options);index=len(calls)
                if index==1:
                    self.assertIn('DISTRACTING_UI_REFERENCE',messages[0]['content'])
                    return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                if index==2:return {'tool':'run_checks','arguments':{}}
                if index==3:return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                if index==4:return {'tool':'read_slice','arguments':{'file_path':'worker.py','start':1,'count':24}}
                if index==5:return {'tool':'update_plan','arguments':{'observed_cause':'Coexisting access routes.',
                    'strategy':'owned_compatible_interface','uncertainty':'Full frozen checks required.'}}
                spans=options['native_exact_edit_spans'];self.assertEqual(spans['owned_methods'],['__getitem__','send'])
                self.assertTrue(any(message['content'].startswith('Verified frozen-check observations') for message in messages))
                self.assertNotIn('DISTRACTING_UI_REFERENCE',messages[0]['content'])
                for mandatory in ['KEEP_REPOSITORY_RULE','KEEP_EXPLICIT_SKILL','KEEP_DEPENDENCY_BOUNDARY']:
                    self.assertIn(mandatory,messages[0]['content'])
                proposal={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':spans['sha256'],
                    'changes':[{'old_string':'   self.channels[name]=[item]','owned_definition':DEFINITION,'constructor_arguments':['item']}]}}
                if index==6:proposal['arguments']['changes']=[{'old_string':'   self.channels[name]=[item]','new_string':'   self.channels[name]=item'}]
                if index==7:self.assertIn('requires owned_definition',json.dumps(messages))
                return proposal
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_require_repair_progress':True,'native_prior_validation_paths':['controlled'],
                'native_max_repairs':6,'native_max_turns':32}))
            coder.workload_guidance={'repository_instructions':['KEEP_REPOSITORY_RULE'],
                'selected_skills':['KEEP_EXPLICIT_SKILL'],'code_intelligence':{
                    'dependency_policy':{'rule':'KEEP_DEPENDENCY_BOUNDARY'},
                    'design_spec':{'note':'DISTRACTING_UI_REFERENCE'+' unrelated design context'*40}}}
            with patch('jarvis.workload_state.load_validation_history',return_value=([prior],[{'accepted':True}])),patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,project,'Repair service',initial_plan=plan,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),7)
            self.assertEqual((project/'test_worker.py').read_text(),frozen)
            self.assertEqual(len(result['candidate_decisions']),1)
            self.assertTrue(result['candidate_decisions'][0]['verified_case_progress'])
            self.assertTrue(all(row['actual_system_characters']<row['original_system_characters'] for row in result['bounded_stage_contexts']))


if __name__=='__main__':unittest.main()
