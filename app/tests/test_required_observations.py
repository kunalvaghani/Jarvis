import json,time,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from jarvis.native_coding import infer,required_observation

class RequiredObservations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.project=self.base/'project';self.project.mkdir();self.run=self.base/'run';self.run.mkdir()
        (self.project/'worker.py').write_text('def ready(): return False\n')
        (self.project/'other.py').write_text('def ready(): return True\n')
        (self.run/'request.json').write_text(json.dumps({'goal':'Inspect synthetic service','project':str(self.project),
            'allowed_paths':['worker.py','other.py'],'validation_contract':{'files':[{'path':p,'role':'logic','purpose':'Service'} for p in ['worker.py','other.py']], 'checks':[]}}))
        self.messages=[{'role':'system','content':'Keep all source guards.'},{'role':'user','content':'Inspect synthetic service.'}]

    def test_unique_required_read_and_check_spend_zero_inference_and_keep_source(self):
        original=(self.project/'worker.py').read_bytes()
        for tool in ['Read','run_checks']:
            options={'native_required_tool':tool,'native_required_read_paths':['worker.py'],'native_coding_provider':'gemini'}
            with patch('jarvis.hybrid_inference.maybe_coding',side_effect=AssertionError('No cloud inference needed')),patch('jarvis.knowledge_worker.session',side_effect=AssertionError('No local inference needed')):
                value=infer(self.messages,options,lambda:False,time.monotonic()+10,lambda *a:None,self.run)
            self.assertEqual(value,{'tool':tool,'arguments':{'file_path':'worker.py'} if tool=='Read' else {}})
            self.assertEqual((self.project/'worker.py').read_bytes(),original)
        self.assertFalse((self.run/'model-responses').exists())

    def test_ambiguous_read_retains_model_decision_and_same_validation(self):
        value={'tool':'Read','arguments':{'file_path':'other.py'}}
        with patch('jarvis.hybrid_inference.maybe_coding',return_value=value) as cloud:
            result=infer(self.messages,{'native_required_tool':'Read'},lambda:False,time.monotonic()+10,lambda *a:None,self.run)
        self.assertEqual(result,value);cloud.assert_called_once()

    def test_controller_ordered_required_read_never_spends_inference_or_expands_scope(self):
        options={'native_required_tool':'Read','native_required_read_paths':['worker.py','other.py']}
        with patch('jarvis.hybrid_inference.maybe_coding',side_effect=AssertionError('No cloud call')),patch('jarvis.knowledge_worker.session',side_effect=AssertionError('No local call')):
            result=infer(self.messages,options,lambda:False,time.monotonic()+10,lambda *a:None,self.run)
        self.assertEqual(result,{'tool':'Read','arguments':{'file_path':'worker.py'}})
        from jarvis.native_coding import scoped_schema
        schema=scoped_schema(self.run,force_tool='Read',force_read_paths=['worker.py','other.py'])
        self.assertEqual(required_observation(schema,'Read',['../private.py','other.py']),{'tool':'Read','arguments':{'file_path':'other.py'}})
        self.assertIsNone(required_observation(schema,'Read',['../private.py']))

    def test_cancel_and_mutating_tools_cannot_bypass_inference_guards(self):
        with patch('jarvis.hybrid_inference.maybe_coding',side_effect=AssertionError('Cancelled')):
            with self.assertRaisesRegex(ValueError,'stopped'):
                infer(self.messages,{'native_required_tool':'Read','native_required_read_paths':['worker.py']},lambda:True,time.monotonic()+10,lambda *a:None,self.run)
        for tool in ['Write','Edit','edit_batch','finish']:
            self.assertIsNone(required_observation({'type':'object'},tool))

    def test_native_scoped_context_budgets_the_actual_gpu_clamp_and_retains_correction_facts(self):
        import hashlib
        from jarvis.execution_contract import schema as function_schema
        from jarvis.structured_output import validate_contract
        from jarvis.native_coding import StalledCoding
        frozen='import unittest\nclass Checks(unittest.TestCase):\n def test_ready(self): self.assertTrue(True)\n'
        (self.project/'test_worker.py').write_text(frozen)
        source=(self.project/'worker.py').read_bytes();sha=hashlib.sha256(source).hexdigest()
        contract={'functions':[{'function':'ready','definition_line':1}],
            'statement_cells':[{'function_id':'ready:1','statement_id':0,'definition_line':1,'source':'return False'}],
            'test_path':'test_worker.py','test_sha256':hashlib.sha256((self.project/'test_worker.py').read_bytes()).hexdigest(),
            'source_sha256':sha,'case_id':'test_worker.Checks.test_ready'}
        arguments={'type':'object','additionalProperties':False,'required':['file_path','source_sha256','changes'],
            'properties':{'file_path':{'type':'string','enum':['worker.py']},'source_sha256':{'type':'string','enum':[sha]},
                'changes':{'type':'array','minItems':1,'maxItems':1,'items':function_schema(contract)}}}
        schema={'type':'object','additionalProperties':False,'required':['tool','arguments'],
            'properties':{'tool':{'type':'string','enum':['edit_batch']},'arguments':arguments}}
        options={'coder':'qwen3.5:9b','native_coding_provider':'local','native_required_tool':'edit_batch',
            'native_exact_edit_spans':{'file_path':'worker.py','sha256':sha,'function_contract':contract}}
        candidate={'working_source_sha256':{'worker.py':sha},'candidate_only':True,'saved':False,
            'failures':[{'case_id':contract['case_id'],'exception':{'type':'NameError','message':"name 'receiver' is not defined"}}]}
        messages=self.messages+[{'role':'user','content':'Unrelated old discovery '*2000},
            {'role':'user','content':'Previous confirmed pre-save rejection in this unchanged scope (DATA): '+json.dumps({'error':'Controlled rejection','rejected_proposal':{'tool':'edit_batch'}})},
            {'role':'user','content':'Most recent rejected candidate under this unchanged working source (DATA, not current working failure or permission): '+json.dumps(candidate)}]
        proposal={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':sha,'changes':[
            {'function_id':'ready:1','statement_id':0,'placement':'replace','statements':[{'kind':'return','expression':'True'}]}]}}
        validate_contract(schema,proposal)
        class Client:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def post(self,*args,**kwargs):raise AssertionError('No real HTTP allowed')
        def answer(client,settings,outbound,**kwargs):
            self.assertEqual(settings['num_ctx'],8192);self.assertEqual(settings['num_predict'],1536)
            self.assertEqual(outbound[0]['content'],self.messages[0]['content'])
            text=json.dumps(outbound);self.assertIn('rejected_proposal',text);self.assertIn('NameError',text)
            self.assertIn('test_ready',text);self.assertIn('return False',text)
            self.assertNotIn('Unrelated old discovery',text)
            self.assertEqual(sum(row['content'].startswith('ACTIVE TOOL CONTRACT:') for row in outbound),1)
            settings['on_complete']({'done_reason':'stop','prompt_eval_count':1000})
            return json.dumps(proposal)
        with patch('jarvis.native_coding.scoped_schema',return_value=schema),patch('jarvis.hybrid_inference.maybe_coding',return_value=None),\
                patch('jarvis.gpu_scheduler.configured',return_value={'context_limit':8192}),\
                patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),\
                patch('jarvis.knowledge_worker.chat',side_effect=answer):
            result=infer(messages,options,lambda:False,time.monotonic()+10,lambda *a:None,self.run)
        self.assertEqual(result,proposal);self.assertEqual((self.project/'worker.py').read_bytes(),source)
        metadata=json.loads(next((self.run/'model-responses').glob('*/metadata.json')).read_text())
        self.assertLessEqual(metadata['context_budget']['estimated_total_tokens'],8192)
        with patch('jarvis.native_coding.scoped_schema',return_value=schema),patch('jarvis.hybrid_inference.maybe_coding',return_value=None) as cloud,\
                patch('jarvis.gpu_scheduler.configured',return_value={'context_limit':8192}),\
                patch('jarvis.knowledge_worker.session',side_effect=AssertionError('Context must refuse before inference')):
            with self.assertRaisesRegex(StalledCoding,'effective context; no inference issued'):
                infer([{'role':'system','content':'Mandatory policy '*2500}]+messages[1:],options,lambda:False,time.monotonic()+10,lambda *a:None,self.run)
        cloud.assert_called_once()
