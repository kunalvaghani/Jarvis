"""Provider-shaped doubles behind a network-deny guard; no cloud tokens."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import requests
from jarvis.cloud_policy import settings
from jarvis.cloud_quota import CloudQuotaManager
from jarvis.coding_cloud_policy import gemini_settings,approved_payload
from jarvis.coding_cloud_routes import CodingRoutes
from jarvis.gemini_adapter import GeminiAdapter
from jarvis.groq_adapter import GroqAdapter,CloudFailure
from jarvis.hybrid_inference import HybridGateway
from jarvis.native_coding import run,infer,UncertainCoding
from jarvis.coder import Coder

KEY='synthetic-key-no-real-credential'
CONTEXT={'provenance':'synthetic','restricted':False}
SCHEMA={'type':'object','additionalProperties':False,'required':['tool','arguments'],
        'properties':{'tool':{'type':'string','enum':['Read']},'arguments':{'type':'object','additionalProperties':False,
        'required':['file_path'],'properties':{'file_path':{'type':'string','enum':['worker.py']}}}}}
VALUE={'tool':'Read','arguments':{'file_path':'worker.py'}}


class Response:
    def __init__(self,data,status=200,headers=None,broken=False):
        self.data=data;self.status_code=status;self.headers=headers or {};self.broken=broken;self.closed=False
    def iter_content(self,*args,**kwargs):
        if self.broken:raise requests.Timeout('synthetic disconnect')
        yield self.data if isinstance(self.data,bytes) else json.dumps(self.data).encode()
    def close(self):self.closed=True


class Transport:
    def __init__(self,provider):self.provider=provider;self.calls=[];self.queue=[];self.mode='ok';self.clock=time.time;self.metadata_calls=0
    def close(self):pass
    def get(self,url,**kwargs):
        from email.utils import formatdate
        self.metadata_calls+=1
        return Response({'name':'models/gemini-3.8-flash'},headers={'Date':formatdate(self.clock(),usegmt=True)})
    def post(self,url,**kwargs):
        self.calls.append(kwargs['json'])
        mode=self.mode
        if mode=='timeout':raise requests.Timeout('synthetic timeout')
        if mode.isdigit():return Response({},int(mode),{'retry-after':'60'})
        if mode=='disconnect':return Response({},broken=True)
        if mode=='truncated_json':return Response(b'{"invalid":')
        value=self.queue.pop(0) if self.queue else VALUE
        text=json.dumps(value)
        if self.provider=='groq':
            return Response({'id':'synthetic','usage':{'prompt_tokens':80,'completion_tokens':40,'total_tokens':120},
                'choices':[{'finish_reason':'length' if mode=='length' else 'stop','message':{'content':text}}]})
        steps=[{'type':'model_output','content':[{'type':'text','text':text}]}]
        if mode=='tool':steps=[{'type':'function_call','name':'lookup','arguments':{'topic':'testing'},'id':'synthetic-call'}]
        if mode=='bad_tool':steps=[{'type':'function_call','name':'unoffered','arguments':{}}]
        return Response({'id':'synthetic','status':'incomplete' if mode=='length' else 'completed','steps':steps,
            'usage':{'total_input_tokens':80,'total_output_tokens':40,'total_tokens':120}})


class CloudCodingRoutes(unittest.TestCase):
    def test_rejection_feedback_does_not_echo_regex_as_a_host_path(self):
        from jarvis.execution_contract import node_schema
        from jarvis.structured_output import validate_contract
        from jarvis.coding_cloud_policy import approved_payload
        with self.assertRaises(ValueError) as raised:
            validate_contract(node_schema(),{'kind':'expr','expression':'first\nsecond'})
        self.assertIn('required string pattern',str(raised.exception))
        message={'role':'user','content':json.dumps({'confirmed_rejection':str(raised.exception)})}
        self.assertEqual(approved_payload([message],{'provenance':'synthetic','restricted':False}),[message])
        with self.assertRaises(ValueError):
            approved_payload([{'role':'user','content':r'\\private-server\private-share\source.py'}],{'provenance':'synthetic','restricted':False})

    def test_cloud_configuration_sections_are_known_objects(self):
        import warnings
        from jarvis.config_contract import validate_root
        with warnings.catch_warnings(record=True) as seen:
            validate_root({'gemini':{},'coding_cloud':{}})
        self.assertFalse(seen)
        for section in ['gemini','coding_cloud']:
            with self.assertRaises(ValueError):validate_root({section:'not-an-object'})

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        # Any unexpected real HTTP request or socket connection fails this test.
        self.network=patch('requests.sessions.Session.request',side_effect=AssertionError('REAL_NETWORK_DENIED'));self.network.start();self.addCleanup(self.network.stop)
        self.socket=patch('socket.socket.connect',side_effect=AssertionError('REAL_SOCKET_DENIED'));self.socket.start();self.addCleanup(self.socket.stop)
        self.options=settings({'enabled':True,'account_plan':'free','free_tier_confirmed':True,'dedicated_quota_confirmed':True,'safety_margin':.2},environ={})
        self.gg=CloudQuotaManager(self.root/'groq.sqlite3',{**self.options,'provider':'groq','max_concurrent_calls':2})
        self.gt=Transport('groq');self.ga=GroqAdapter(KEY,self.options,self.gg,transport=self.gt);self.ga.available_until=time.monotonic()+300;self.addCleanup(self.ga.close)
        self.go=gemini_settings({'account_plan':'free','free_tier_confirmed':True,'billing_disabled_confirmed':True,
            'quota_verified':True,'key_project_confirmed':True,'api_project_id':'test-project','quota_project_id':'test-project',
            'quota_key_sha256':hashlib.sha256(KEY.encode()).hexdigest()})
        self.mg=CloudQuotaManager(self.root/'gemini.sqlite3',{**self.go,'provider':'gemini','keep_dispatch_time':True})
        self.mt=Transport('gemini');self.ma=GeminiAdapter(KEY,self.go,self.mg,transport=self.mt);self.addCleanup(self.ma.close)
        self.config={'coding_cloud':{'enabled':True,'dry_run_verified':True},'gemini':self.go}
        self.gateway=HybridGateway(self.root,self.options,adapter=self.ga,guardian=self.gg)
        self.route=CodingRoutes(self.gateway,self.config,gemini=self.ma);self.gateway.coding_routes=self.route
        self.run=self.root/'run';self.run.mkdir()
        self.messages=[{'role':'system','content':'Return the requested JSON proposal.'},{'role':'user','content':'Analyze a synthetic public service.'}]
        self.policy={'native_cloud_context':CONTEXT,'native_coding_provider':'groq','native_coding_complexity':'complex'}

    def complete(self,**kwargs):
        return self.route.complete(self.messages,SCHEMA,{**self.policy,**kwargs},self.run,lambda:False,time.monotonic()+10)

    def test_local_success_and_ordinary_task_make_no_cloud_request(self):
        self.assertIsNone(self.complete(native_coding_provider='auto',native_coding_complexity='ordinary'))
        self.assertEqual(self.gt.calls+self.mt.calls,[])
        self.assertIsNone(self.complete(native_coding_provider='local'))
        from jarvis.hybrid_inference import maybe_coding
        with patch('jarvis.hybrid_inference.get_service') as service:
            self.assertIsNone(maybe_coding(self.messages,SCHEMA,{**self.policy,'native_coding_provider':'local'},self.run,lambda:False,time.monotonic()+10))
        service.assert_not_called()
        from jarvis.model_selection import required_models
        required=required_models({'brain':{'enabled':True,'coder':'gemini-3.8-flash','planner':'qwen3.5:9b'}})
        self.assertNotIn('gemini-3.8-flash',required);self.assertIn('qwen3.5:9b',required)

    def test_direct_groq_and_gemini_coding_proposals_use_same_typed_contract(self):
        self.assertEqual(self.complete(),VALUE)
        self.assertEqual(self.complete(native_coding_provider='gemini'),VALUE)
        self.assertFalse(self.gt.calls[0]['stream']);self.assertNotIn('tools',self.gt.calls[0])
        self.assertEqual(self.gt.calls[0]['response_format'],{'type':'json_object'})
        self.assertEqual(self.mt.calls[0]['model'],'gemini-3.8-flash');self.assertFalse(self.mt.calls[0]['store'])
        state=json.loads((self.run/'cloud-route-state.json').read_text())
        self.assertEqual(state['cloud_calls'],2)
        self.assertTrue(all(row['usage']['total_tokens']==120 and row['application_verified'] is False for row in state['attempts']))

    def test_groq_to_gemini_and_gemini_to_groq_fallback(self):
        self.gt.mode='503';self.assertEqual(self.complete(),VALUE)
        self.assertEqual(len(self.gt.calls),1);self.assertEqual(len(self.mt.calls),1)
        self.mg.block(60);self.ga.available_until=time.monotonic()+300;self.gg.block(1)
        with self.gg.connect() as db:self.gg.put(db,'blocked_until',0)
        self.gt.mode='ok';self.assertEqual(self.complete(native_coding_provider='gemini'),VALUE)
        self.assertEqual(len(self.gt.calls),2)

    def test_invalid_credentials_429_server_errors_timeout_and_truncation_are_bounded(self):
        for mode in ('401','429','500','503','timeout','disconnect','truncated_json','length'):
            with self.subTest(mode=mode):
                self.ga.guardian=CloudQuotaManager(self.root/('groq-'+mode+'.sqlite3'),{**self.options,'provider':'groq','max_concurrent_calls':2})
                self.gg=self.ga.guardian
                with self.gg.connect() as db:self.gg.put(db,'blocked_until',0)
                self.gt.mode=mode;self.ga.available_until=time.monotonic()+300
                self.policy['native_cloud_task_id']=hashlib.sha256(mode.encode()).hexdigest()[:32]
                self.run=self.root/('run-'+mode);self.run.mkdir()
                # Isolate Gemini task budget so fault scenarios don't spend one
                # synthetic task's entire three-call allowance.
                before=len(self.gt.calls);result=self.complete()
                self.assertEqual(len(self.gt.calls)-before,1)
                self.assertTrue(result is None or result==VALUE)

    def test_invalid_tool_schema_falls_back_without_dispatching_a_file_action(self):
        self.gt.queue=[{'tool':'Write','arguments':{'file_path':'outside.py','content':'bad'}}]
        self.assertEqual(self.complete(),VALUE)
        self.assertFalse((self.root/'outside.py').exists())
        self.assertEqual(len(self.gt.calls),1);self.assertEqual(len(self.mt.calls),1)
        recorded=next(row for row in self.gateway.performance.coding_summary('coding') if row['provider']=='groq')
        self.assertEqual(recorded['total_reported_tokens'],120)
        self.assertEqual(recorded['verified_results'],0)

    def test_cloud_unavailable_quota_unverified_and_missing_key_return_to_local(self):
        self.route.gemini=None;self.gateway.adapter=None
        self.assertIsNone(self.complete())
        self.assertEqual(self.gt.calls+self.mt.calls,[])
        from jarvis.coding_cloud_policy import gemini_eligible
        self.assertEqual(gemini_eligible(self.go,None),'missing_api_key')
        self.assertEqual(gemini_eligible({**self.go,'quota_verified':False},KEY),'quota_unverified')

    def test_privacy_restrictions_secrets_and_global_offline_precede_dispatch(self):
        for context in (None,{'provenance':'private','restricted':False},{'provenance':'synthetic','restricted':True}):
            self.assertIsNone(self.complete(native_cloud_context=context))
        self.messages=[{'role':'user','content':'api_key=do-not-upload'}]
        self.assertIsNone(self.complete());self.assertEqual(self.gt.calls+self.mt.calls,[])
        from jarvis.hybrid_inference import control
        control(self.root,'offline');self.assertIsNone(self.complete())

    def test_local_reasoning_failure_escalates_but_path_or_permission_defect_does_not(self):
        self.policy.update(native_coding_provider='auto',native_coding_complexity='ordinary')
        self.assertIsNone(self.route.complete(self.messages,SCHEMA,self.policy,self.run,lambda:False,time.monotonic()+10,failure='permission_denied'))
        self.assertIsNone(self.route.complete(self.messages,SCHEMA,self.policy,self.run,lambda:False,time.monotonic()+10,failure='invalid_structured_output'))
        self.assertEqual(self.route.complete(self.messages,SCHEMA,self.policy,self.run,lambda:False,time.monotonic()+10,failure='invalid_structured_output'),VALUE)
        self.assertEqual(len(self.gt.calls),1)

    def test_function_call_normalization_and_unsupported_mode_refusal(self):
        tools=[{'type':'function','function':{'name':'lookup','parameters':{'type':'object','additionalProperties':False,
            'required':['topic'],'properties':{'topic':{'type':'string'}}}}}]
        self.mt.mode='tool';message=self.ma.complete(self.messages,tools=tools,context=CONTEXT)
        self.assertEqual(message['tool_calls'][0]['function']['name'],'lookup')
        before=len(self.mt.calls)
        with self.assertRaises(CloudFailure):self.ma.complete(self.messages,tools=tools,schema=SCHEMA,context=CONTEXT)
        self.assertEqual(len(self.mt.calls),before)
        self.mt.mode='bad_tool'
        with self.assertRaises(CloudFailure):self.ma.complete(self.messages,tools=tools,context=CONTEXT)

    def test_user_cancellation_and_network_guard_prevent_dispatch(self):
        with self.assertRaises(CloudFailure):self.ma.complete(self.messages,schema=SCHEMA,context=CONTEXT,cancelled=lambda:True)
        self.assertEqual(self.mt.calls,[])
        with self.assertRaisesRegex(AssertionError,'REAL_NETWORK_DENIED'):requests.post('https://api.groq.com/openai/v1/chat/completions')

    def test_quota_exhaustion_and_capability_mismatch_do_not_post(self):
        self.gg.feedback('minute_requests',limit=1)
        self.assertEqual(self.complete(),VALUE)  # eligible difficult task falls to Gemini
        self.assertEqual(len(self.gt.calls),0);self.assertEqual(len(self.mt.calls),1)
        self.assertIsNone(self.complete(native_required_capabilities=['unsupported_vision_mode']))
        self.gg.feedback('daily_tokens',limit=1)
        self.assertEqual(self.complete(),VALUE)
        self.assertEqual(len(self.gt.calls),0)

    def test_same_provider_bound_and_restart_do_not_repeat_bad_proposals_indefinitely(self):
        self.route.gemini=None
        self.gt.queue=[{'tool':'Wrong','arguments':{}},{'tool':'Wrong','arguments':{}}]
        self.assertIsNone(self.complete());self.assertIsNone(self.complete())
        before=len(self.gt.calls)
        self.route=CodingRoutes(self.gateway,self.config,gemini=self.ma);self.route.gemini=None
        self.assertIsNone(self.complete());self.assertEqual(len(self.gt.calls),before)
        state=json.loads((self.run/'cloud-route-state.json').read_text())
        self.assertTrue(any(row['reason']=='same_source_provider_attempt_bound' for row in state['attempts']))

    def test_native_inference_escalates_two_invalid_local_responses_without_network(self):
        from jarvis.structured_output import ModelOutputError
        request={'project':str(self.root),'goal':'Inspect the synthetic worker','validation_contract':{'files':[{'path':'worker.py','role':'logic','purpose':'Synthetic'}],'checks':[]},'allowed_paths':['worker.py']}
        (self.root/'worker.py').write_text('def ready(): return True\n')
        (self.run/'request.json').write_text(json.dumps(request))
        (self.run/'validation-contract.json').write_text(json.dumps(request['validation_contract']))
        options={**self.policy,'native_coding_provider':'auto','native_coding_complexity':'ordinary','coder':'qwen3.5:9b'}
        with patch('jarvis.hybrid_inference.get_service',return_value=self.gateway),patch('jarvis.knowledge_worker.session',side_effect=ModelOutputError('synthetic invalid JSON')):
            with self.assertRaises(ModelOutputError):infer(self.messages,options,lambda:False,time.monotonic()+10,lambda *args:None,self.run)
            value=infer(self.messages,options,lambda:False,time.monotonic()+10,lambda *args:None,self.run)
        self.assertEqual(value,VALUE);self.assertEqual(len(self.gt.calls),1)

    def test_unknown_file_write_completion_never_replays_or_changes_provider(self):
        from jarvis.coding_files import FileSession
        project=self.root/'uncertain';project.mkdir();ledger=self.root/'uncertain-ledger';ledger.mkdir()
        (project/'worker.py').write_text('def send(): return "bad"\n')
        frozen='import unittest\nfrom worker import send\nclass Check(unittest.TestCase):\n def test_send(self): self.assertEqual(send(),"ok")\n'
        (project/'test_worker.py').write_text(frozen)
        plan={'files':[{'path':'worker.py','role':'logic','purpose':'Synthetic'},{'path':'test_worker.py','role':'test','purpose':'Frozen'}],
              'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
        self.gt.queue=[{'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}},
                       {'tool':'Write','arguments':{'file_path':'worker.py','content':'def send(): return "ok"\n'}}]
        original=FileSession.call;writes=[]
        def uncertain(files,name,args):
            result=original(files,name,args)
            if name=='Write':
                writes.append(name);raise UncertainCoding('synthetic uncertain completion after one confirmed fixture write')
            return result
        coder=Coder(SimpleNamespace(base=ledger,report=lambda *args:None),SimpleNamespace(options={
            'coder':'qwen3.5:9b','native_cloud_context':CONTEXT,'native_coding_provider':'groq','native_max_turns':10}))
        with patch('jarvis.hybrid_inference.get_service',return_value=self.gateway),patch.object(FileSession,'call',uncertain):
            with self.assertRaises(UncertainCoding):run(coder,project,'Repair the synthetic service; preserve its frozen tests.',initial_plan=plan,return_receipt=True)
        self.assertEqual(len(writes),1);self.assertEqual(len(self.gt.calls),2);self.assertEqual(len(self.mt.calls),0)
        self.assertEqual((project/'test_worker.py').read_text(),frozen)

    def test_two_local_function_rejections_allow_one_bounded_cloud_handoff(self):
        from tests.test_execution_contract import fixture,PLAN,function_id
        base=self.root/'bounded';base.mkdir();project,ledger=fixture(base)
        calls=[]
        def proposal(messages,options,*args):
            calls.append(options);index=len(calls)
            if index==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
            if index==2:return {'tool':'run_checks','arguments':{}}
            if index in (3,5,7):return {'tool':'Read','arguments':{'file_path':'worker.py'}}
            if index==9:return {'tool':'finish','arguments':{}}
            self.assertIn(index,(4,6,8));scope=options['native_exact_edit_spans']
            self.assertEqual(options['native_cloud_only_after_local_bound'],index==8)
            if index==8:self.assertEqual(options['native_verified_reasoning_failures'],2)
            definition='def send(self):\n return "bad"' if index==4 else 'def send(self, extra):\n return "ok"' if index==6 else 'def send(self):\n return "ok"'
            return {'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':scope['sha256'],
                'changes':[{'function_id':function_id(scope['function_contract']['functions'][0]),'definition':definition}]}}
        coder=Coder(SimpleNamespace(base=ledger,report=lambda *args:None),SimpleNamespace(options={
            'native_cloud_context':CONTEXT,'native_require_repair_progress':True,'native_execution_function_repair':True,
            'native_max_repairs':6,'native_max_turns':16}))
        with patch('jarvis.native_coding.infer',side_effect=proposal):
            receipt=run(coder,project,'Repair the owned synthetic service; preserve frozen tests.',initial_plan=PLAN,return_receipt=True)
        self.assertEqual(len(calls),9);self.assertTrue(receipt['validation']['passed'])

    def test_cloud_only_handoff_does_not_repeat_local_inference_when_cloud_is_unavailable(self):
        from jarvis.native_coding import StalledCoding
        request={'project':str(self.root),'goal':'Inspect the synthetic worker','validation_contract':{'files':[{'path':'worker.py','role':'logic','purpose':'Synthetic'}],'checks':[]},'allowed_paths':['worker.py']}
        (self.root/'worker.py').write_text('def ready(): return True\n');(self.run/'request.json').write_text(json.dumps(request));(self.run/'validation-contract.json').write_text(json.dumps(request['validation_contract']))
        self.gateway.adapter=None;self.route.gemini=None
        options={**self.policy,'native_cloud_only_after_local_bound':True,'native_verified_reasoning_failures':2}
        with patch('jarvis.hybrid_inference.get_service',return_value=self.gateway),patch('jarvis.knowledge_worker.session') as local:
            with self.assertRaises(StalledCoding):infer(self.messages,options,lambda:False,time.monotonic()+10,lambda *args:None,self.run)
        local.assert_not_called()

    def test_host_paths_are_redacted_without_turning_private_provenance_into_permission(self):
        result=approved_payload([{'role':'user','content':'Trace from C:\\Users\\person\\worker.py" failed'}],CONTEXT)
        self.assertNotIn('person',json.dumps(result));self.assertIn('worker.py',json.dumps(result))
        with self.assertRaises(ValueError):approved_payload(result,{'provenance':'private','restricted':False})

    def test_gemini_clock_recovery_uses_metadata_not_inference_after_idle(self):
        self.ma.complete(self.messages,schema=SCHEMA,context=CONTEXT)
        now=time.time()+400;self.mg.clock=lambda:now;self.mt.clock=lambda:now
        self.ma.complete(self.messages,schema=SCHEMA,context=CONTEXT)
        self.assertEqual(self.mt.metadata_calls,1);self.assertEqual(len(self.mt.calls),2)
        self.assertEqual(self.mg.snapshot(fresh=True)['used']['daily_requests'],2)

    def test_unverified_account_configuration_blocks_even_an_injected_eligible_adapter(self):
        self.route=CodingRoutes(self.gateway,{**self.config,'gemini':{**self.go,'quota_verified':False}},gemini=self.ma)
        self.gateway.adapter=None
        self.assertIsNone(self.complete(native_coding_provider='gemini'))
        self.assertEqual(self.mt.calls,[])

    def test_gemini_daily_429_records_dimension_and_waits_until_pacific_reset(self):
        body={'error':{'details':[{'@type':'type.googleapis.com/google.rpc.QuotaFailure',
            'violations':[{'quotaId':'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}]}}
        with patch.object(self.mt,'post',return_value=Response(body,429,{'retry-after':'2'})) as post:
            with self.assertRaises(CloudFailure):self.ma.complete(self.messages,schema=SCHEMA,context=CONTEXT)
            before=self.mt.metadata_calls
            from jarvis.cloud_quota import QuotaDenied
            with self.assertRaises(QuotaDenied):self.ma.complete(self.messages,schema=SCHEMA,context=CONTEXT)
            self.assertEqual(post.call_count,1);self.assertEqual(self.mt.metadata_calls,before)
        snapshot=self.mg.snapshot(fresh=True)
        self.assertEqual(snapshot['exhausted_dimension'],'daily_requests')
        self.assertGreater(snapshot['cooldown_until'],self.mg.clock()+60)

    def test_generic_context_uses_canonical_goal_and_fresh_owned_source_not_unrelated_history(self):
        from jarvis.coding_cloud_context import messages_for
        (self.root/'worker.py').write_text('def ready(): return True\n')
        request={'project':str(self.root),'goal':'untrusted worker hypothesis','validation_goal':'Canonical frozen requirement',
            'validation_contract':{'files':[{'path':'worker.py','role':'logic','purpose':'Synthetic'}],'checks':[]}}
        (self.run/'request.json').write_text(json.dumps(request))
        messages=[{'role':'system','content':'Optional unrelated reference'}, {'role':'user','content':'old duplicated request'},
                  {'role':'user','content':'UNAPPROVED_REFERENCE_BODY'}]
        result=messages_for(messages,{'native_cloud_context':CONTEXT,'native_cloud_policy':'Mandatory source and frozen policy'},self.run,'groq')
        text=json.dumps(result)
        self.assertIn('Canonical frozen requirement',text);self.assertIn('def ready()',text)
        self.assertNotIn('UNAPPROVED_REFERENCE_BODY',text);self.assertNotIn('untrusted worker hypothesis',text)
        self.assertNotIn('Optional unrelated reference',text)

    def test_forced_tool_contract_is_transmitted_in_json_object_mode(self):
        self.assertEqual(self.complete(native_required_tool='Read'),VALUE)
        text=json.dumps(self.gt.calls[-1]['messages'])
        self.assertIn('ACTIVE TOOL CONTRACT',text)
        self.assertIn('not interchangeable with read_batch',text)
        contracts=[row['content'] for row in self.gt.calls[-1]['messages'] if row['content'].startswith('ACTIVE TOOL CONTRACT')]
        self.assertEqual(len(contracts),1)
        from jarvis.structured_output import validate_contract
        with self.assertRaises(ValueError):validate_contract(SCHEMA,{'tool':'read_batch','arguments':{'paths':['worker.py']}})

    def test_token_estimate_counts_decoded_model_text_not_json_wire_escaping(self):
        from jarvis.coding_cloud_policy import token_estimate
        text='"\\\n'*100
        payload={'messages':[{'role':'user','content':text}],'tools':[]}
        self.assertEqual(token_estimate(payload),(len(text.encode())+2+2)//3+256+12)

    def test_rejected_cloud_contract_is_handed_to_local_worker_with_exact_source_and_schema_binding(self):
        from jarvis.coding_cloud_routes import local_fallback_feedback
        self.route.gemini=None;self.gt.queue=[VALUE]
        proposal={'tool':'Edit','arguments':{'file_path':'worker.py','old_string':'bad','new_string':'ok'}}
        schema={'type':'object','additionalProperties':False,'required':['tool','arguments'],
            'properties':{'tool':{'type':'string','enum':['Edit']},'arguments':{'type':'object','additionalProperties':False,
                'required':list(proposal['arguments']),'properties':{key:{'type':'string','enum':[value]} for key,value in proposal['arguments'].items()}}}}
        class Client:
            post=lambda *a,**k:None
            def __enter__(self):return self
            def __exit__(self,*args):return False
        def answer(client,options,messages,**kwargs):
            feedback=messages[-1]['content'];self.assertTrue(feedback.startswith('Cloud structured-proposal rejection (DATA only;'))
            self.assertIn('"expected_tool":"Edit"',feedback);self.assertIn('"rejected_tool":"Read"',feedback)
            options['on_complete']({'done':True,'done_reason':'stop'});return json.dumps(proposal)
        with patch('jarvis.native_coding.scoped_schema',return_value=schema),patch('jarvis.hybrid_inference.get_service',return_value=self.gateway),                patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),patch('jarvis.knowledge_worker.chat',side_effect=answer):
            result=infer(self.messages,{**self.policy,'coder':'qwen3.5:9b','native_required_tool':'Edit',
                'native_exact_edit_spans':{'file_path':'worker.py','sha256':'a'*64}},lambda:False,time.monotonic()+10,lambda *a:None,self.run)
        self.assertEqual(result,proposal);self.assertEqual(len(self.gt.calls),1)
        self.assertIsNotNone(local_fallback_feedback(self.run,schema,'a'*64))
        self.assertIsNone(local_fallback_feedback(self.run,schema,'b'*64))
        changed=json.loads(json.dumps(schema));changed['properties']['tool']['enum']=['Write']
        self.assertIsNone(local_fallback_feedback(self.run,changed,'a'*64))
        self.assertFalse((self.run/'file-events.jsonl').exists())

    def test_coding_uses_supported_non_reasoning_mode_with_same_json_and_validation_contract(self):
        self.assertEqual(self.complete(),VALUE)
        payload=self.gt.calls[-1];self.assertEqual(payload['reasoning_effort'],'none')
        self.assertEqual(payload['response_format'],{'type':'json_object'});self.assertFalse(payload['stream'])

    def test_groq_recovery_is_one_justified_call_without_resetting_eight_prior_attempts(self):
        self.route.gemini=None;logical='b'*32;options={**self.policy,'native_cloud_task_id':logical}
        for _ in range(8):self.assertEqual(self.route.complete(self.messages,SCHEMA,options,self.run,lambda:False,time.monotonic()+10),VALUE)
        other=self.root/'restart';other.mkdir()
        self.assertIsNone(self.route.complete(self.messages,SCHEMA,options,other,lambda:False,time.monotonic()+10))
        self.assertEqual(len(self.gt.calls),8)
        proposal={'tool':'Edit','arguments':{'file_path':'worker.py','old_string':'bad','new_string':'ok'}}
        schema={'type':'object','additionalProperties':False,'required':['tool','arguments'],
            'properties':{'tool':{'type':'string','enum':['Edit']},'arguments':{'type':'object','additionalProperties':False,
                'required':list(proposal['arguments']),'properties':{key:{'type':'string','enum':[value]} for key,value in proposal['arguments'].items()}}}}
        options.update(native_required_tool='Edit',native_exact_edit_spans={'file_path':'worker.py','sha256':'a'*64},native_groq_task_limit=9)
        self.assertIsNone(self.route.complete(self.messages,schema,options,other,lambda:False,time.monotonic()+10))
        self.assertEqual(len(self.gt.calls),8)
        options['native_groq_budget_reason']='Verified non-thinking protocol fix after reasoning exhausted structured output; preserve account capacity.'
        self.gt.queue=[proposal]
        self.assertEqual(self.route.complete(self.messages,schema,options,other,lambda:False,time.monotonic()+10),proposal)
        self.assertEqual(self.gg.task_usage(logical),9);self.assertEqual(len(self.gt.calls),9)
        self.assertIsNone(self.route.complete(self.messages,schema,options,other,lambda:False,time.monotonic()+10))
        self.assertEqual(len(self.gt.calls),9)

    def test_exception_clock_recovery_precedes_capacity_check_and_exhausted_task_skips_metadata(self):
        self.gateway.adapter=None;self.ma.options['max_task_calls']=4;self.route.gemini_options['max_task_calls']=4
        self.assertEqual(self.complete(native_coding_provider='gemini'),VALUE)
        now=time.time()+400;self.mg.clock=lambda:now;self.mt.clock=lambda:now
        proposal={'tool':'Edit','arguments':{'file_path':'worker.py','old_string':'bad','new_string':'ok'}}
        schema={'type':'object','additionalProperties':False,'required':['tool','arguments'],
            'properties':{'tool':{'type':'string','enum':['Edit']},'arguments':{'type':'object','additionalProperties':False,
                'required':list(proposal['arguments']),'properties':{key:{'type':'string','enum':[value]} for key,value in proposal['arguments'].items()}}}}
        options={**self.policy,'native_coding_provider':'gemini','native_required_tool':'Edit',
            'native_exact_edit_spans':{'file_path':'worker.py','sha256':'a'*64},'native_gemini_task_limit':4,
            'native_gemini_budget_reason':'Verified protocol fix on priority task; preserve daily capacity for other work.'}
        self.mt.queue=[proposal]*3
        for _ in range(3):self.assertEqual(self.route.complete(self.messages,schema,options,self.run,lambda:False,time.monotonic()+10),proposal)
        self.assertEqual(self.mt.metadata_calls,1);self.assertEqual(len(self.mt.calls),4)
        now+=400
        self.assertIsNone(self.route.complete(self.messages,schema,options,self.run,lambda:False,time.monotonic()+10))
        self.assertEqual(self.mt.metadata_calls,1);self.assertEqual(len(self.mt.calls),4)

    def test_larger_coding_output_reservation_still_refuses_unchanged_minute_cap(self):
        self.route.gemini=None;self.route.options['groq_max_output_tokens']=1536;self.ga.options['max_output_tokens']=1536
        self.messages=[{'role':'system','content':'Ordinary text '*980},{'role':'user','content':'Inspect approved synthetic source.'}]
        self.assertIsNone(self.complete())
        self.assertEqual(self.gt.calls,[])
        state=json.loads((self.run/'cloud-route-state.json').read_text())
        self.assertIn('quota_minute_tokens',[row.get('reason') for row in state['attempts']])

    def test_gemini_timeout_is_classified_without_losing_uncertain_reservation(self):
        self.gateway.adapter=None
        with patch.object(self.mt,'post',side_effect=requests.Timeout('PRIVATE_TRANSPORT_DETAIL')):
            self.assertIsNone(self.complete(native_coding_provider='gemini'))
        state=json.loads((self.run/'cloud-route-state.json').read_text());row=next(row for row in state['attempts'] if row.get('sent'))
        self.assertEqual(row['reason'],'gemini_timeout');self.assertEqual(row['provider_error']['phase'],'headers')
        self.assertFalse(row['usage']['exact_usage_available']);self.assertNotIn('PRIVATE_TRANSPORT_DETAIL',json.dumps(state))

    def test_priority_extension_is_one_call_only_and_does_not_change_normal_three_call_limit(self):
        self.gateway.adapter=None;self.ma.options['max_task_calls']=4;self.route.gemini_options['max_task_calls']=4
        for _ in range(3):self.assertEqual(self.complete(native_coding_provider='gemini'),VALUE)
        self.assertIsNone(self.complete(native_coding_provider='gemini'))
        self.assertEqual(len(self.mt.calls),3)
        proposal={'tool':'Edit','arguments':{'file_path':'worker.py','old_string':'bad','new_string':'ok'}}
        schema={'type':'object','additionalProperties':False,'required':['tool','arguments'],
            'properties':{'tool':{'type':'string','enum':['Edit']},'arguments':{'type':'object','additionalProperties':False,
                'required':list(proposal['arguments']),'properties':{key:{'type':'string','enum':[value]} for key,value in proposal['arguments'].items()}}}}
        options={**self.policy,'native_coding_provider':'gemini','native_required_tool':'Edit',
            'native_exact_edit_spans':{'file_path':'worker.py','sha256':'a'*64},'native_gemini_task_limit':4}
        self.assertIsNone(self.route.complete(self.messages,schema,options,self.run,lambda:False,time.monotonic()+10))
        self.assertEqual(len(self.mt.calls),3)
        self.mt.queue=[proposal]
        options['native_gemini_budget_reason']='Verified supported protocol repair; high priority task; preserve remaining daily capacity.'
        self.assertEqual(self.route.complete(self.messages,schema,options,self.run,lambda:False,time.monotonic()+10),proposal)
        self.assertEqual(len(self.mt.calls),4)
        self.assertIsNone(self.route.complete(self.messages,schema,options,self.run,lambda:False,time.monotonic()+10))
        self.assertEqual(len(self.mt.calls),4)
        self.assertEqual(self.mg.snapshot(fresh=True)['used']['daily_requests'],4)

    def test_priority_fifth_call_preserves_four_charges_default_three_and_stops_at_five(self):
        self.gateway.adapter=None;self.ma.options['max_task_calls']=5;self.route.gemini_options['max_task_calls']=5
        logical='a'*32
        for index in range(4):
            identifier=self.mg.reserve(self.go['model'],10,request_id=format(index+1,'032x'),
                input_tokens=5,output_tokens=5,task_id=logical,task_limit=5)
            self.mg.finish(identifier,status='failed')
        # Simulated older minute, same persistent task/day usage; never live counters.
        with self.mg.connect() as db:db.execute('UPDATE calls SET at=at-120')
        self.assertEqual(self.mg.task_usage(logical),4)
        self.assertIsNone(self.complete(native_coding_provider='gemini',native_cloud_task_id=logical))
        self.assertEqual(self.mt.calls,[])
        proposal={'tool':'Edit','arguments':{'file_path':'worker.py','old_string':'bad','new_string':'ok'}}
        schema={'type':'object','additionalProperties':False,'required':['tool','arguments'],
            'properties':{'tool':{'type':'string','enum':['Edit']},'arguments':{'type':'object','additionalProperties':False,
                'required':list(proposal['arguments']),'properties':{key:{'type':'string','enum':[value]} for key,value in proposal['arguments'].items()}}}}
        options={**self.policy,'native_coding_provider':'gemini','native_cloud_task_id':logical,'native_required_tool':'Edit',
            'native_exact_edit_spans':{'file_path':'worker.py','sha256':'a'*64},'native_gemini_task_limit':5}
        self.assertIsNone(self.route.complete(self.messages,schema,options,self.run,lambda:False,time.monotonic()+10))
        self.assertEqual(self.mt.calls,[])
        options['native_gemini_budget_reason']='Validated context and representation repairs after bounded local failures; priority source-bound repair retains other-task headroom.'
        self.mt.queue=[proposal]
        self.assertEqual(self.route.complete(self.messages,schema,options,self.run,lambda:False,time.monotonic()+10),proposal)
        self.assertEqual(self.mg.task_usage(logical),5);self.assertEqual(len(self.mt.calls),1)
        metadata_calls=self.mt.metadata_calls
        self.assertIsNone(self.route.complete(self.messages,schema,options,self.run,lambda:False,time.monotonic()+10))
        self.assertEqual(self.mt.metadata_calls,metadata_calls);self.assertEqual(len(self.mt.calls),1)
        self.assertEqual(self.mg.snapshot(fresh=True)['used']['daily_requests'],5)
        self.assertEqual(self.mg.options['max_daily_requests'],20)
        self.assertEqual(self.route.options['gemini_max_task_calls'],3)

    def test_priority_fifth_call_refuses_low_daily_capacity_and_configured_ceiling(self):
        self.gateway.adapter=None;self.ma.options['max_task_calls']=5;self.route.gemini_options['max_task_calls']=5
        options={**self.policy,'native_coding_provider':'gemini','native_required_tool':'Edit',
            'native_exact_edit_spans':{'file_path':'worker.py','sha256':'a'*64},'native_gemini_task_limit':5,
            'native_gemini_budget_reason':'Validated complex repair strategy; retain capacity for other tasks.'}
        with patch.object(self.mg,'snapshot',return_value={'remaining':{'daily_requests':8}}):
            self.assertIsNone(self.route.complete(self.messages,SCHEMA,options,self.run,lambda:False,time.monotonic()+10))
        self.assertEqual(self.mt.calls,[]);self.assertEqual(self.mg.task_usage('a'*32),0)
        options['native_gemini_task_limit']=6
        self.assertIsNone(self.route.complete(self.messages,SCHEMA,options,self.run,lambda:False,time.monotonic()+10))
        self.assertEqual(self.mt.calls,[])

    def test_private_provider_message_redacts_actual_key_and_never_enters_route_text(self):
        self.route.gemini=None
        body={'error':{'code':'invalid_request','message':'PRIVATE_ACCOUNT rejected key '+KEY}}
        with patch.object(self.gt,'post',return_value=Response(body,400)):
            self.assertIsNone(self.complete())
        state=json.loads((self.run/'cloud-route-state.json').read_text());row=next(row for row in state['attempts'] if row.get('sent'))
        path=self.run/row['private_provider_error_evidence']
        text=(path/'response.txt').read_text();self.assertIn('[REDACTED]',text);self.assertNotIn(KEY,text)
        self.assertFalse(json.loads((path/'metadata.json').read_text())['executable'])
        self.assertNotIn(KEY,json.dumps(state));self.assertNotIn('PRIVATE_ACCOUNT',json.dumps(state))

    def test_generate_content_transport_matches_advertised_api_and_reconciles_reasoning_tokens(self):
        self.ma.options['api_protocol']='generate_content'
        body={'responseId':'synthetic-content','candidates':[{'finishReason':'STOP','content':{'role':'model','parts':[{'text':json.dumps(VALUE)}]}}],
              'usageMetadata':{'promptTokenCount':11,'candidatesTokenCount':5,'thoughtsTokenCount':3,'totalTokenCount':19}}
        def post(url,**kwargs):
            self.assertTrue(url.endswith('/models/gemini-3.8-flash:generateContent'))
            payload=kwargs['json'];self.assertNotIn('store',payload);self.assertNotIn('previous_interaction_id',payload)
            self.assertEqual(payload['generationConfig']['thinkingConfig']['thinkingLevel'],'LOW')
            self.assertEqual(payload['generationConfig']['responseJsonSchema'],SCHEMA)
            self.assertEqual(payload['generationConfig']['responseMimeType'],'application/json')
            self.assertIn('systemInstruction',payload);self.assertIn('contents',payload)
            return Response(body)
        with patch.object(self.mt,'post',side_effect=post) as called:
            self.assertEqual(self.complete(native_coding_provider='gemini'),VALUE)
        self.assertEqual(called.call_count,1)
        state=json.loads((self.run/'cloud-route-state.json').read_text());usage=next(row['usage'] for row in state['attempts'] if row.get('sent'))
        self.assertEqual(usage['prompt_tokens'],11);self.assertEqual(usage['completion_tokens'],8);self.assertEqual(usage['total_tokens'],19)
        self.assertTrue(usage['exact_usage_available'])
        with self.assertRaisesRegex(CloudFailure,'function_mode_not_enabled'):
            self.ma.complete(self.messages,tools=[{'function':{'name':'Read','parameters':{}}}],context=CONTEXT)

    def test_gemini_schema_rejection_retains_categorical_diagnostic_without_private_message(self):
        body={'error':{'code':400,'status':'INVALID_ARGUMENT','message':'PRIVATE_ACCOUNT schema constraint has too many states'}}
        self.gateway.adapter=None
        with patch.object(self.mt,'post',return_value=Response(body,400)):
            self.assertIsNone(self.complete(native_coding_provider='gemini'))
        state=json.loads((self.run/'cloud-route-state.json').read_text());sent=next(row for row in state['attempts'] if row.get('sent'))
        self.assertEqual(sent['provider_error']['category'],'schema_too_complex')
        self.assertEqual(sent['provider_error']['status'],'INVALID_ARGUMENT')
        self.assertNotIn('PRIVATE_ACCOUNT',json.dumps(state))
        self.assertFalse(sent['usage']['exact_usage_available'])

    def test_targeted_repair_policy_reserves_gemini_for_source_bound_mutations(self):
        policy={**self.policy,'native_coding_provider':'gemini','native_cloud_targeted_repairs_only':True}
        for stage,extra in [('planning',{}),('coding',{}),('coding',{'native_required_tool':'Read','native_exact_edit_spans':{'file_path':'worker.py','sha256':'a'*64}})]:
            self.assertIsNone(self.route.complete(self.messages,SCHEMA,{**policy,**extra},self.run,lambda:False,time.monotonic()+10,stage=stage))
        self.assertEqual(self.gt.calls+self.mt.calls,[])
        proposal={'tool':'Edit','arguments':{'file_path':'worker.py','old_string':'bad','new_string':'ok'}}
        schema={'type':'object','additionalProperties':False,'required':['tool','arguments'],
            'properties':{'tool':{'type':'string','enum':['Edit']},'arguments':{'type':'object','additionalProperties':False,
                'required':['file_path','old_string','new_string'],'properties':{key:{'type':'string','enum':[value]} for key,value in proposal['arguments'].items()}}}}
        self.mt.queue=[proposal]
        result=self.route.complete(self.messages,schema,{**policy,'native_required_tool':'Edit',
            'native_exact_edit_spans':{'file_path':'worker.py','sha256':'a'*64}},self.run,lambda:False,time.monotonic()+10)
        self.assertEqual(result,proposal);self.assertEqual(len(self.mt.calls),1);self.assertEqual(self.gt.calls,[])
        self.assertEqual(self.mg.snapshot(fresh=True)['used']['daily_requests'],1)

    def test_http_rejected_generation_is_private_evidence_and_uncertain_charge_is_retained(self):
        raw='{"tool":"edit_batch","arguments":'
        body={'error':{'code':'json_validate_failed','type':'invalid_request_error','failed_generation':raw,
                       'message':'PRIVATE_ACCOUNT_MESSAGE'}}
        self.route.gemini=None
        with patch.object(self.gt,'post',return_value=Response(body,400)):
            self.assertIsNone(self.complete())
        state=json.loads((self.run/'cloud-route-state.json').read_text());sent=next(row for row in state['attempts'] if row.get('sent'))
        self.assertEqual(sent['provider_error']['code'],'json_validate_failed')
        path=self.run/sent['provider_rejection_evidence']
        self.assertEqual((path/'response.txt').read_text(),raw)
        self.assertFalse(json.loads((path/'metadata.json').read_text())['completed'])
        self.assertFalse(sent['usage']['exact_usage_available']);self.assertGreater(sent['usage']['estimated_total_tokens'],0)
        self.assertNotIn('PRIVATE_ACCOUNT_MESSAGE',json.dumps(state))

    def test_provider_error_diagnostics_never_publish_unknown_codes_or_secret_generation(self):
        private='gsk_'+'A'*40
        body={'error':{'code':private,'type':private,'failed_generation':private,'message':private}}
        self.route.gemini=None
        with patch.object(self.gt,'post',return_value=Response(body,400)):
            self.assertIsNone(self.complete())
        state=json.loads((self.run/'cloud-route-state.json').read_text());sent=next(row for row in state['attempts'] if row.get('sent'))
        self.assertEqual(sent['provider_error']['code'],'unclassified')
        self.assertTrue(sent['provider_error']['rejected_generation_withheld'])
        self.assertNotIn('provider_rejection_evidence',sent)
        self.assertNotIn(private,json.dumps(state))
        self.assertFalse(list(self.run.glob('model-responses/provider-rejected-*')))

    def test_function_stage_has_closed_tool_envelope_and_verified_local_read(self):
        from jarvis.coding_cloud_context import messages_for
        from jarvis.execution_contract import schema as function_schema
        from jarvis.structured_output import validate_contract
        project=self.root/'project';project.mkdir()
        source="class Service:\n def send(self):\n  current = 'bad'\n  return current\n"
        frozen="import unittest\nclass Checks(unittest.TestCase):\n def test_send(self): self.assertEqual('bad','ok')\n"
        (project/'worker.py').write_text(source);(project/'test_worker.py').write_text(frozen)
        sha=hashlib.sha256((project/'worker.py').read_bytes()).hexdigest()
        contract={'functions':[{'function':'send','definition_line':2}],
            'statement_cells':[{'function_id':'send:2','statement_id':0,'definition_line':3,'source':"current = 'bad'"}],
            'test_path':'test_worker.py','test_sha256':hashlib.sha256((project/'test_worker.py').read_bytes()).hexdigest(),'case_id':'test_worker.Checks.test_send'}
        plan={'files':[{'path':'worker.py','role':'logic'},{'path':'test_worker.py','role':'test'}],
              'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
        (self.run/'request.json').write_text(json.dumps({'goal':'Repair the synthetic service','project':str(project),'validation_contract':plan,'allowed_paths':['worker.py']}))
        arguments={'type':'object','additionalProperties':False,'required':['file_path','source_sha256','changes'],
            'properties':{'file_path':{'type':'string','enum':['worker.py']},'source_sha256':{'type':'string','enum':[sha]},
                'changes':{'type':'array','minItems':1,'maxItems':1,'items':function_schema(contract)}}}
        schema={'type':'object','additionalProperties':False,'required':['tool','arguments'],
            'properties':{'tool':{'type':'string','enum':['edit_batch']},'arguments':arguments}}
        before=json.dumps(schema,sort_keys=True)
        options={**self.policy,'native_required_tool':'edit_batch','native_exact_edit_spans':{'file_path':'worker.py','sha256':sha,'function_contract':contract}}
        for observed in [sha,'0'*64]:
            (self.run/'tools.jsonl').write_text(json.dumps({'tool':'Read','arguments':{'file_path':'worker.py'},'result':{'sha256':observed}})+'\n')
            result=messages_for(self.messages,options,self.run,'groq',schema)
            request=json.loads(result[1]['content']);self.assertEqual(request['goal'],'Repair the synthetic service')
            self.assertEqual(request['current_stage']['target_case_id'],contract['case_id'])
            self.assertIn('later stages',request['current_stage']['scope'])
            self.assertIn('"kind":"assign"',result[2]['content'])
            self.assertIn('At most 1 distinct offered cells',result[2]['content'])
            self.assertNotIn('At most four cells',result[2]['content'])
            active=next(row['content'] for row in result if row['content'].startswith('ACTIVE TOOL CONTRACT:'))
            envelope=json.loads(active[active.index('{'):]);envelope=envelope.get('anyOf',[envelope])[0];self.assertEqual(envelope['properties']['tool']['enum'],['edit_batch'])
            self.assertNotIn('items',envelope['properties']['arguments']['properties']['changes'])
            with self.assertRaises(ValueError):validate_contract(envelope,VALUE)
            self.assertEqual('local_read_evidence' in json.dumps(result),observed==sha)
            self.assertEqual('already executed the source-bound Read' in json.dumps(result),observed==sha)
            self.assertNotIn('No file action has executed yet',json.dumps(result))
        self.gateway.adapter=None
        bad={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':sha,'changes':[{'function_id':'send:2','statement_id':0,'placement':'replace','statements':[{'kind':'unknown'}]}]}}
        good={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':sha,'changes':[{'function_id':'send:2','statement_id':0,'placement':'replace','statements':[{'kind':'return','expression':"'ok'"}]}]}}
        self.mt.queue=[bad,good]
        opts={**options,'native_coding_provider':'gemini'}
        self.assertIsNone(self.route.complete(self.messages,schema,opts,self.run,lambda:False,time.monotonic()+10))
        self.assertEqual(self.route.complete(self.messages,schema,opts,self.run,lambda:False,time.monotonic()+10),good)
        wire=self.mt.calls[0]['response_format']['schema'];wire=wire.get('anyOf',[wire])[0]
        self.assertEqual(wire['properties']['arguments']['properties']['changes']['items'],{'type':'object'})
        self.assertEqual(hashlib.sha256((project/'worker.py').read_bytes()).hexdigest(),sha)
        self.assertEqual(json.dumps(schema,sort_keys=True),before)
        with self.assertRaises(ValueError):validate_contract(schema,{'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':sha,'changes':[{'function_id':'send:2','statement_id':0,'placement':'replace','statements':[{'kind':'unknown'}]}]}})

    def test_compact_node_contract_matches_executable_schema_and_current_cell_limit(self):
        from jarvis.execution_contract import statement_proposal_guidance,node_schema,program_nodes
        from jarvis.structured_output import validate_contract
        import ast
        for count in [1,2,5]:
            text=statement_proposal_guidance({'statement_cells':[{}]*count})
            self.assertIn('At most '+str(min(4,count))+' distinct offered cells',text)
            # This is a neutral wire-format example, never application code.
            example=json.loads(text[text.index('{'):text.index('}')+1])
            validate_contract(node_schema(),example)
            self.assertEqual(ast.unparse(ast.fix_missing_locations(program_nodes([example])[0])),'value = source')
            with self.assertRaises(ValueError):validate_contract(node_schema(),{'assign':{'target':'value','expression':'source'}})
        self.assertIn('At most 1 functions',statement_proposal_guidance({'functions':[{}]}))

    def test_python_source_representation_retains_complete_source_scope_and_frozen_case_in_local_context(self):
        from jarvis.coding_cloud_context import local_function_messages
        from jarvis.execution_contract import schema as function_schema
        from jarvis.structured_output import validate_contract
        project=self.root/'python-project';project.mkdir()
        (project/'worker.py').write_text("def send():\n value = 'bad'\n return value\n")
        (project/'test_worker.py').write_text("import unittest\nclass Checks(unittest.TestCase):\n def test_send(self): self.assertEqual('bad','ok')\n")
        sha=hashlib.sha256((project/'worker.py').read_bytes()).hexdigest()
        contract={'functions':[{'function':'send','definition_line':1}],
            'statement_cells':[{'function_id':'send:1','statement_id':0,'definition_line':2,'source':"value = 'bad'"}],
            'statement_representation':'python_source','source_sha256':sha,'test_path':'test_worker.py',
            'test_sha256':hashlib.sha256((project/'test_worker.py').read_bytes()).hexdigest(),'case_id':'test_worker.Checks.test_send'}
        plan={'files':[{'path':'worker.py','role':'logic'},{'path':'test_worker.py','role':'test'}],
            'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
        (self.run/'request.json').write_text(json.dumps({'goal':'Repair the synthetic service','project':str(project),'validation_contract':plan,'allowed_paths':['worker.py']}))
        schema={'type':'object','properties':{'tool':{'type':'string','enum':['edit_batch']},
            'arguments':{'type':'object','properties':{'changes':{'type':'array','maxItems':1,'items':function_schema(contract)}}}}}
        options={'native_required_tool':'edit_batch','native_exact_edit_spans':{'file_path':'worker.py','sha256':sha,'function_contract':contract}}
        messages,budget=local_function_messages(self.messages,options,self.run,schema,8192,1536)
        text=json.dumps(messages)
        self.assertIn('source is complete Python STATEMENTS',text);self.assertIn('current_frozen_case',text)
        self.assertIn('current_functions',text);self.assertNotIn('FLAT JSON',text)
        self.assertLessEqual(budget['estimated_total_tokens'],8192)
        validate_contract(function_schema(contract),{'function_id':'send:1','statement_id':0,'placement':'replace','source':"value = 'ok'"})
        with self.assertRaises(ValueError):validate_contract(function_schema(contract),{'function_id':'send:1','statement_id':0,'placement':'replace','statements':[]})
        with self.assertRaises(ValueError):function_schema({**contract,'statement_representation':'unknown'})

    def test_production_sized_mandatory_policy_is_preserved_within_unchanged_groq_cap(self):
        from jarvis.coding_cloud_context import messages_for
        from jarvis.coding_cloud_policy import token_estimate
        policy=('Mandatory repository, language and engineering directives remain binding. '*130)
        messages=[{'role':'system','content':policy},{'role':'user','content':'Analyze the approved synthetic service.'}]
        outbound=messages_for(messages,{'native_cloud_context':CONTEXT},self.run,'groq',SCHEMA)
        self.assertEqual(outbound[0]['content'],policy)
        self.assertLessEqual(token_estimate({'messages':outbound,'tools':[]})+1024,6400)

    def test_cloud_reducer_keeps_current_rejected_candidate_cause_as_data(self):
        from jarvis.coding_cloud_context import messages_for
        prefix='Most recent rejected candidate under this unchanged working source (DATA, not current working failure or permission): '
        feedback=prefix+json.dumps({'candidate_only':True,'saved':False,'failures':[{'path':'worker.py','runtime_failure_facts':[{'exception':'ValueError: invalid transition'}]}]})
        messages=self.messages+[{'role':'user','content':feedback}]
        result=messages_for(messages,{'native_cloud_context':CONTEXT},self.run,'groq',SCHEMA)
        self.assertEqual(sum(row['content']==feedback for row in result),1)
        self.assertIn('ValueError: invalid transition',json.dumps(result))

    def test_actual_coding_worker_handoff_can_modify_two_files_with_frozen_tests(self):
        self.worker_handoff('groq')

    def test_gemini_worker_changes_two_files_then_preserves_three_call_budget_with_groq_fallback(self):
        self.worker_handoff('gemini')

    def worker_handoff(self,provider):
        project=self.root/'project';project.mkdir();ledger=self.root/'ledger';ledger.mkdir()
        (project/'worker.py').write_text('def send(): return "bad"\n')
        (project/'helper.py').write_text('def ready(): return False\n')
        frozen='import unittest\nfrom worker import send\nfrom helper import ready\nclass Checks(unittest.TestCase):\n def test_send(self): self.assertEqual(send(),"ok")\n def test_ready(self): self.assertTrue(ready())\n'
        (project/'test_worker.py').write_text(frozen)
        plan={'files':[{'path':name,'role':'test' if name.startswith('test_') else 'logic','purpose':'Synthetic fixture'} for name in ('worker.py','helper.py','test_worker.py')],
              'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
        proposals=[{'tool':'read_batch','arguments':{'paths':['worker.py','helper.py','test_worker.py']}},
            {'tool':'Edit','arguments':{'file_path':'worker.py','old_string':'return "bad"','new_string':'return "ok"','replace_all':False}},
            {'tool':'Edit','arguments':{'file_path':'helper.py','old_string':'return False','new_string':'return True','replace_all':False}},
            {'tool':'finish','arguments':{}}]
        if provider=='gemini':self.mt.queue=proposals[:3];self.gt.queue=proposals[3:]
        else:self.gt.queue=proposals
        coder=Coder(SimpleNamespace(base=ledger,report=lambda *args:None),SimpleNamespace(options={
            'coder':'gemini-3.8-flash' if provider=='gemini' else 'qwen3.5:9b','native_cloud_context':CONTEXT,'native_coding_provider':provider,'native_max_turns':10}))
        with patch('jarvis.hybrid_inference.get_service',return_value=self.gateway):
            try:receipt=run(coder,project,'Repair the synthetic send and ready functions. Preserve the original tests.',initial_plan=plan,return_receipt=True)
            except AssertionError as error:
                details=[{'tool':row['tool'],'arguments':row['arguments'],'error':row.get('result',{}).get('error') if isinstance(row.get('result'),dict) else None}
                    for path in ledger.rglob('tools.jsonl') for row in [json.loads(line) for line in path.read_text().splitlines()]]
                raise AssertionError(str(error)+'; route states: '+json.dumps(details)) from error
        self.assertTrue(receipt['validation']['passed']);self.assertEqual((project/'test_worker.py').read_text(),frozen)
        self.assertEqual(len(self.gt.calls),4 if provider=='groq' else 1)
        self.assertEqual(len(self.mt.calls),0 if provider=='groq' else 3)


if __name__=='__main__':unittest.main()
