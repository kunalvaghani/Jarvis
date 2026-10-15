import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock,patch

from jarvis.cloud_policy import classify,settings,credential,screen_payload
from jarvis.cloud_quota import QuotaGuardian,QuotaDenied,duration
from jarvis.groq_adapter import GroqAdapter,CloudFailure
from jarvis.hybrid_inference import HybridGateway,control
from tests.fake_groq import server


class CloudCommandTests(unittest.TestCase):
    def test_exact_enable_phrase_survives_command_normalization(self):
        from jarvis.commands import Command, parse
        for text in ('Enable cloud AI for public tasks.', 'turn on cloud AI for public tasks',
                     'Jarvis, please enable cloud AI for public tasks.'):
            with self.subTest(text=text):
                self.assertEqual(parse(text), Command('cloud_control', 'enable'))

    def test_typed_ask_and_task_save_preference_without_inference(self):
        from jarvis.actions import Actions
        from jarvis.commands import Command
        from jarvis.hybrid_inference import policy
        with tempfile.TemporaryDirectory() as folder:
            actions = Actions.__new__(Actions)
            actions.base = Path(folder)
            actions.knowledge = Mock()
            actions.report = Mock()
            with patch('jarvis.hybrid_inference.get_service') as service:
                for kind in ('ask', 'task', 'cloud_control'):
                    value = 'enable' if kind == 'cloud_control' else 'Enable cloud AI for public tasks.'
                    actions.submit(Command(kind, value))
                    self.assertEqual(policy(actions.base)['routing'], 'public')
                actions.submit(Command('ask', 'Turn off cloud AI.'))
                self.assertEqual(policy(actions.base)['routing'], 'local')
                service.assert_not_called()
            actions.knowledge.submit.assert_not_called()
            actions.knowledge.cancel.assert_called_once()
            self.assertIn('preference saved', actions.report.call_args_list[0].args[1])

    def test_explanations_and_quoted_commands_are_not_settings(self):
        from jarvis.commands import cloud_command
        for text in ('What does enable cloud AI for public tasks mean?',
                     'Explain how to enable cloud AI for public tasks.',
                     '"Enable cloud AI for public tasks."'):
            self.assertIsNone(cloud_command(text))

    def test_enter_and_voice_only_dispatch_final_setting_command(self):
        from jarvis.engine import Engine
        from jarvis.commands import Command
        submit = Mock()
        engine = Engine(submit, Mock())
        engine.activate()
        engine.feed('Enable cloud AI for public tasks.', final=False)
        submit.assert_not_called()
        engine.feed('Enable cloud AI for public tasks.', final=True)
        submit.assert_called_once_with(Command('cloud_control', 'enable'))


class PolicyTests(unittest.TestCase):
    def test_defaults_and_strict_configuration(self):
        value=settings(environ={})
        self.assertFalse(value['enabled']);self.assertFalse(value['live_tests_enabled'])
        for data in ({'free_only':False},{'allow_sensitive_data':True},{'max_minute_tokens':8001},{'enabled':'false'},{'safety_margin':float('nan')},{'endpoint':'http://evil'},{'model':'invented'}):
            with self.subTest(data=data),self.assertRaises(ValueError):settings(data,environ={})
        with self.assertRaises(ValueError):settings(environ={'GROQ_ENABLED':'yes'})
        self.assertTrue(settings(environ={'GROQ_ENABLED':'true'})['enabled'])

    def test_private_context_and_ambiguous_requests_stay_local(self):
        for question in ('Explain my private repository','Explain password=supersecret','Explain C:\\Users\\me\\project','Explain that algorithm','Open Chrome','अभी मेरे खाते को पढ़ो','Compare api_key=never-upload'):
            self.assertNotEqual(classify({'question':question})['privacy'],'PUBLIC')
        for field in ('history','screen','pc_context','memory_context','catalog_context','conversation_context'):
            self.assertNotEqual(classify({'question':'Explain quantum computing',field:True})['privacy'],'PUBLIC')
        self.assertEqual(classify({'question':'Compare distributed consistency models'})['privacy'],'PUBLIC')

    def test_payload_secret_screen_all_roles(self):
        with self.assertRaises(ValueError):screen_payload([{'role':'assistant','content':'password=never'}])
        with self.assertRaises(ValueError):screen_payload({'content':'x'*64001})
        self.assertGreater(screen_payload({'content':'Public topic'}),0)
        for text in ('Compare passwords=never','Explain tokens=never','Explain patient diagnosis','Compare accounts and financial records'):
            self.assertNotEqual(classify({'question':text})['privacy'],'PUBLIC')

    def test_credentials_local_and_missing(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{},clear=True):
            self.assertIsNone(credential(root))
            folder=Path(root)/'secrets';folder.mkdir()
            (folder/'groq.json').write_text('{"GROQ_API_KEY":"gsk_fakeonlytest123"}')
            self.assertEqual(credential(root),'gsk_fakeonlytest123')

    def test_commands_keep_direct_paths(self):
        from jarvis.commands import parse
        self.assertEqual(parse('Turn off cloud AI').kind,'cloud_control')
        self.assertEqual(parse('Use local model qwen3.5:4b').value,'local:qwen3.5:4b')
        self.assertEqual(parse('open Chrome').kind,'open')

    def test_live_smoke_requires_both_explicit_opt_ins(self):
        from jarvis.cloud_cli import main
        service=Mock();service.options={'live_tests_enabled':False}
        with patch('sys.argv',['cloud_cli','live-smoke','--authorize-live-free-request']),patch('jarvis.cloud_cli.get_service',return_value=service):
            with self.assertRaises(SystemExit):main()
        service.adapter.complete.assert_not_called();service.adapter.refresh.assert_not_called()
        service.options={'live_tests_enabled':True}
        with patch('sys.argv',['cloud_cli','live-smoke']),patch('jarvis.cloud_cli.get_service',return_value=service):
            with self.assertRaises(SystemExit):main()
        service.adapter.complete.assert_not_called()

    def test_manual_local_model_selection_uses_existing_inventory_contract(self):
        with tempfile.TemporaryDirectory() as root,patch('jarvis.knowledge_worker.session') as session,patch('jarvis.knowledge_worker.ensure_server',return_value={'models':[{'name':'qwen3.5:4b'}]}):
            self.assertIn('qwen3.5:4b',control(root,'local:qwen3.5:4b'))
            state=json.loads((Path(root)/'.jarvis-runtime/cloud/policy.json').read_text())
            self.assertEqual(state['local_model'],'qwen3.5:4b');self.assertEqual(state['routing'],'local')
            with self.assertRaises(ValueError):control(root,'local:missing')
            session.return_value.close.assert_called()

    def test_offline_control_bypasses_busy_action_queue(self):
        from jarvis.actions import Actions
        from jarvis.commands import Command
        actions=Mock();actions.base='unused';actions.task_active=True
        with patch('jarvis.hybrid_inference.control',return_value='Offline selected') as apply:
            Actions.submit(actions,Command('cloud_control','offline'))
        actions.knowledge.cancel.assert_called_once();apply.assert_called_once_with('unused','offline')
        actions.queue.put.assert_not_called()


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=100000.;self.options=settings(environ={})
        self.path=Path(self.temp.name)/'quota.db'
        self.guard=QuotaGuardian(self.path,self.options,clock=lambda:self.now)

    def test_daily_and_minute_limits_are_distinct(self):
        identifier=self.guard.reserve('qwen',100)
        self.guard.finish(identifier,{'total_tokens':50},headers={'x-ratelimit-remaining-requests':'0','x-ratelimit-reset-requests':'1h','x-ratelimit-remaining-tokens':'7000','x-ratelimit-reset-tokens':'5s'})
        self.assertEqual(self.guard.snapshot()['remaining']['daily_requests'],0)
        self.assertEqual(self.guard.snapshot()['used']['daily_tokens'],50)
        with self.assertRaises(QuotaDenied):self.guard.reserve('qwen',1)

    def test_atomic_reservations_across_instances(self):
        def reserve(_):
            other=QuotaGuardian(self.path,self.options,clock=lambda:self.now)
            try: return other.reserve('qwen',2000)
            except QuotaDenied:return None
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(reserve,range(8)))
        self.assertEqual(sum(bool(r) for r in results),3)
        self.assertEqual(self.guard.snapshot()['used']['minute_tokens'],6000)

    def test_crash_reservation_and_idempotent_finish(self):
        identifier=self.guard.reserve('qwen',1000)
        other=QuotaGuardian(self.path,self.options,clock=lambda:self.now)
        self.assertEqual(other.snapshot()['used']['daily_tokens'],1000)
        other.finish(identifier,{'total_tokens':80});other.finish(identifier,{'total_tokens':0})
        self.assertEqual(other.snapshot()['used']['daily_tokens'],80)
        with self.assertRaises(QuotaDenied):other.reserve('qwen',1000,identifier)

    def test_unknown_usage_not_zero_and_underestimate_pauses(self):
        identifier=self.guard.reserve('qwen',100)
        self.guard.finish(identifier)
        self.assertEqual(self.guard.snapshot()['used']['daily_tokens'],100)
        second=self.guard.reserve('qwen',10)
        self.guard.finish(second,{'total_tokens':11})
        self.assertEqual(self.guard.snapshot()['state'],'UNKNOWN')

    def test_clock_change_requires_provider_confirmation(self):
        self.guard.reserve('qwen',100)
        self.now-=100
        self.assertEqual(self.guard.snapshot()['state'],'UNKNOWN')
        self.now+=90000
        self.assertEqual(self.guard.snapshot()['state'],'UNKNOWN')
        self.guard.confirm_clock(self.now)
        self.assertEqual(self.guard.snapshot()['used']['daily_tokens'],0)
        with self.assertRaises(QuotaDenied):self.guard.confirm_clock(self.now-200)

    def test_rolling_reset_and_provider_backoff(self):
        identifier=self.guard.reserve('qwen',100);self.guard.finish(identifier,{'total_tokens':50})
        self.guard.block(2)
        with self.assertRaises(QuotaDenied):self.guard.reserve('qwen',10)
        self.now+=61
        self.assertEqual(self.guard.snapshot()['used']['minute_tokens'],0)
        self.assertEqual(self.guard.snapshot()['used']['daily_tokens'],50)
        self.assertEqual(duration('2m59.56s'),179.56)

    def test_exhausted_day_recovers_automatically_after_restart(self):
        options={**self.options,'enabled':True,'account_plan':'free','free_tier_confirmed':True,
            'dedicated_quota_confirmed':True,'max_daily_requests':2}
        guard=QuotaGuardian(Path(self.temp.name)/'day.db',options,clock=lambda:self.now)
        gateway=HybridGateway(self.temp.name,options,adapter=Mock(),guardian=guard)
        request={'question':'Explain quantum computing'}
        identifier=guard.reserve(options['model'],100);guard.finish(identifier,{'total_tokens':50})
        self.assertEqual(gateway.decide(request)['provider'],'local')
        self.assertFalse((Path(self.temp.name)/'.jarvis-runtime/cloud/policy.json').exists())
        self.now+=86401
        restored=QuotaGuardian(guard.path,options,clock=lambda:self.now)
        restored.confirm_clock(self.now)  # simulated fresh provider Date metadata
        restarted=HybridGateway(self.temp.name,options,adapter=Mock(),guardian=restored)
        self.assertEqual(restarted.decide(request)['provider'],'groq')
        restored.reserve(options['model'],100)

    def test_usage_overrun_pause_expires_instead_of_becoming_permanent(self):
        identifier=self.guard.reserve('qwen',10)
        self.guard.finish(identifier,{'total_tokens':11})
        self.assertEqual(self.guard.snapshot()['state'],'UNKNOWN')
        self.now+=86401;self.guard.confirm_clock(self.now)
        self.assertEqual(self.guard.snapshot()['state'],'NORMAL')
        self.guard.reserve('qwen',10)

    def test_provider_exhaustion_header_expires_and_manual_offline_is_preserved(self):
        identifier=self.guard.reserve('qwen',100)
        self.guard.finish(identifier,{'total_tokens':50},{'x-ratelimit-remaining-requests':'0','x-ratelimit-reset-requests':'1h'})
        self.assertEqual(self.guard.snapshot()['state'],'EXHAUSTED')
        self.now+=3601;self.guard.confirm_clock(self.now)
        self.assertGreater(self.guard.snapshot()['remaining']['daily_requests'],0)
        control(self.temp.name,'offline')
        gateway=HybridGateway(self.temp.name,{**self.options,'enabled':True,'routing':'local'},adapter=Mock(),guardian=self.guard)
        self.assertEqual(gateway.decide({'question':'Explain quantum computing'})['provider'],'local')

    def test_storage_corruption_fail_closed(self):
        self.path.write_bytes(b'corrupt')
        self.assertEqual(self.guard.snapshot()['state'],'UNKNOWN')
        with self.assertRaises(QuotaDenied):self.guard.reserve('qwen',100)

    def test_daily_tokens_and_request_limits_reject_before_dispatch(self):
        options={**self.options,'max_daily_tokens':100,'max_daily_requests':2}
        guard=QuotaGuardian(Path(self.temp.name)/'small.db',options,clock=lambda:self.now)
        first=guard.reserve('qwen',80);guard.finish(first,{'total_tokens':80})
        with self.assertRaises(QuotaDenied):guard.reserve('qwen',20)
        self.assertEqual(guard.snapshot()['used']['daily_requests'],1)

    def test_lower_provider_limits_are_never_upgraded(self):
        identifier=self.guard.reserve('qwen',10)
        self.guard.finish(identifier,{'total_tokens':10},{'x-ratelimit-limit-tokens':'20'})
        with self.assertRaises(QuotaDenied):self.guard.reserve('qwen',9)

    def test_stale_advisory_snapshot_cannot_authorize_dispatch(self):
        self.guard.snapshot()
        other=QuotaGuardian(self.path,self.options,clock=lambda:self.now)
        other.reserve('qwen',7000)
        with self.assertRaises(QuotaDenied):self.guard.reserve('qwen',500)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.options=settings({'enabled':True,'account_plan':'free','free_tier_confirmed':True,'dedicated_quota_confirmed':True},environ={})
        self.guard=QuotaGuardian(self.root/'quota.db',self.options)

    def adapter(self,endpoint):
        result=GroqAdapter('gsk_fakeonlytest123',self.options,self.guard,endpoint=endpoint,testing=True)
        self.addCleanup(result.close)
        result.refresh();self.assertTrue(result.ready());return result

    def test_first_eligible_question_waits_for_metadata_and_uses_cloud(self):
        with server() as (endpoint,state):
            adapter=GroqAdapter('gsk_fakeonlytest123',self.options,self.guard,endpoint=endpoint,testing=True)
            self.addCleanup(adapter.close)
            gateway=HybridGateway(self.root,self.options,adapter=adapter,guardian=self.guard)
            self.assertEqual(gateway.answer({'question':'Explain quantum computing'})['route']['provider'],'groq')
            self.assertEqual(state['calls'],1)

    def test_automatic_catalogue_is_not_added_to_fresh_public_question(self):
        import queue
        from jarvis.question_client import QuestionClient
        client=QuestionClient(self.root,Mock())
        self.addCleanup(client.close)
        client.process=Mock();client.responses=queue.Queue()
        client.responses.put(json.dumps({'answer':'Fake answer'}))
        client.memory=Mock();client.memory.profile_text.return_value='Local profile'
        client.memory.situation=None;client.memory.curator=None
        client.memory.task_context.return_value={'projects':['private project']}
        client.memory.recall.return_value=[{'observation':'private memory'}]
        with patch('jarvis.hybrid_inference.configured',return_value=self.options),patch.object(client,'_start'):
            client.request({'question':'Explain quantum computing'},lambda:False)
        outbound=json.loads(client.process.stdin.write.call_args.args[0])
        self.assertNotIn('catalog_context',outbound);self.assertNotIn('memory_context',outbound)
        client.memory.task_context.assert_not_called();client.memory.recall.assert_not_called()
        self.assertEqual(outbound['user_profile'],'Local profile')

    def test_standalone_gate_preserves_private_followup_and_offline_requests(self):
        from jarvis.hybrid_inference import standalone_public
        with patch('jarvis.hybrid_inference.configured',return_value=self.options):
            self.assertTrue(standalone_public(self.root,{'question':'Explain quantum computing'}))
            for request in ({'question':'Explain that quantum algorithm'},
                            {'question':'Explain my quantum computing project'},
                            {'question':'Explain quantum computing','history':[{'content':'private'}]},
                            {'question':'Explain quantum computing','screen':True},
                            {'question':'Explain quantum computing','web':True}):
                self.assertFalse(standalone_public(self.root,request))
        with patch('jarvis.hybrid_inference.configured',return_value={**self.options,'routing':'local'}):
            self.assertFalse(standalone_public(self.root,{'question':'Explain quantum computing'}))

    def test_fake_server_text_json_tools_and_stream(self):
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint)
            messages=[{'role':'user','content':'Explain quantum computing'}]
            self.assertEqual(adapter.complete(messages)['content'],'Public answer')
            self.assertEqual(json.loads(adapter.complete(messages,json_mode=True)['content'])['answer'],'Public answer')
            tools=[{'type':'function','function':{'name':'lookup','parameters':{'type':'object','properties':{'topic':{'type':'string'}},'required':['topic']}}}]
            self.assertEqual(adapter.complete(messages,tools=tools)['tool_calls'][0]['function']['name'],'lookup')
            chunks=[];self.assertEqual(adapter.complete(messages,on_chunk=chunks.append)['content'],'Public answer')
            self.assertEqual(chunks,['Public answer']);self.assertEqual(state['calls'],4)
            self.assertEqual(self.guard.snapshot()['used']['daily_tokens'],360)

    def test_private_enrichment_does_not_enter_public_payload(self):
        with server() as (endpoint,state):
            gateway=HybridGateway(self.root,self.options,adapter=self.adapter(endpoint),guardian=self.guard)
            result=gateway.answer({'question':'Explain quantum computing','options':{'answer_language':'hi'},'user_profile':'password=never','situation':'private paths'})
            self.assertIsNone(result)  # Explicit situation context now forces local inference.
            self.assertEqual(state['bodies'],[])
            result=gateway.answer({'question':'Explain quantum computing','options':{'answer_language':'hi'},'user_profile':'password=never'})
            self.assertEqual(result['answer'],'Public answer')
            self.assertNotIn('never',json.dumps(state['bodies']))
            self.assertNotIn('private paths',json.dumps(state['bodies']))
            self.assertIn('Hindi',state['bodies'][0]['messages'][0]['content'])

    def test_partial_stream_pauses_without_local_duplicate(self):
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint);state['mode']='disconnect'
            gateway=HybridGateway(self.root,self.options,adapter=adapter,guardian=self.guard)
            with self.assertRaises(CloudFailure) as error:
                gateway.answer({'question':'Explain quantum computing','stream_answer':True},lambda event:None)
            self.assertTrue(error.exception.partial);self.assertEqual(state['calls'],1)
            self.assertGreater(self.guard.snapshot()['used']['daily_tokens'],0)

    def test_many_stream_chunks_complete_without_per_byte_policy_reads(self):
        from jarvis.hybrid_inference import policy
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint);state['mode']='many_chunks'
            gateway=HybridGateway(self.root,self.options,adapter=adapter,guardian=self.guard)
            with patch('jarvis.hybrid_inference.policy',wraps=policy) as reads:
                result=gateway.answer({'question':'Prove why binary search has logarithmic time complexity.',
                                       'stream_answer':True},lambda event:None)
            self.assertEqual(result['answer'],'Proof αβγ. '*4000)
            self.assertLess(reads.call_count,50)
            self.assertEqual(state['calls'],1)
            self.assertTrue(result['route']['transport_complete'])

    def test_partial_token_limit_preserves_specific_reason_without_replay(self):
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint);state['mode']='length'
            gateway=HybridGateway(self.root,self.options,adapter=adapter,guardian=self.guard)
            with self.assertRaisesRegex(CloudFailure,'output token limit'):
                gateway.answer({'question':'Explain quantum computing','stream_answer':True},lambda event:None)
            route=json.loads((gateway.root/'last-route.json').read_text())
            self.assertEqual(route['interruption_reason'],'output_token_limit')
            self.assertFalse(route['fallback']);self.assertEqual(state['calls'],1)

    def test_errors_fallback_once_no_retry(self):
        for code in ('401','404','429','500','malformed'):
            with self.subTest(code=code),server() as (endpoint,state):
                guard=QuotaGuardian(self.root/(code+'.db'),self.options)
                adapter=GroqAdapter('gsk_fakeonlytest123',self.options,guard,endpoint=endpoint,testing=True)
                adapter.refresh();state['mode']=code
                gateway=HybridGateway(self.root,self.options,adapter=adapter,guardian=guard)
                self.assertIsNone(gateway.answer({'question':'Explain quantum computing'}))
                self.assertEqual(state['calls'],1);adapter.close()

    def test_disable_missing_credentials_manual_preference_and_paid_account(self):
        adapter=Mock();adapter.ready.return_value=True
        for changed,reason in [({'enabled':False},'offline_or_disabled'),({'account_plan':'paid'},'free_account_not_confirmed'),({'free_tier_confirmed':False},'free_account_not_confirmed')]:
            gateway=HybridGateway(self.root,{**self.options,**changed},adapter=adapter,guardian=self.guard)
            self.assertEqual(gateway.decide({'question':'Explain quantum computing'})['reason'],reason)
        control(self.root,'offline')
        self.assertEqual(HybridGateway(self.root,{**self.options,'routing':'local'},adapter=adapter,guardian=self.guard).decide({'question':'Explain quantum computing'})['provider'],'local')

    def test_production_endpoint_redirect_and_payload_guard(self):
        with self.assertRaises(ValueError):GroqAdapter('fake',self.options,self.guard,endpoint='http://evil')
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint)
            with self.assertRaises(ValueError):adapter.complete([{'role':'user','content':'password=secret'}])
            self.assertEqual(state['calls'],0)

    def test_real_worker_gateway_preserves_local_contract(self):
        from jarvis.knowledge_worker import handle_request
        result={'answer':'Public answer','route':{'provider':'groq'}}
        with patch('jarvis.hybrid_inference.maybe_answer',return_value=result),patch('jarvis.knowledge_worker.ensure_server') as local:
            self.assertEqual(handle_request({'question':'Explain quantum computing'},Mock()),result)
            local.assert_not_called()

    def test_bad_tool_arguments_are_rejected_and_never_executed(self):
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint);state['mode']='bad_tools'
            tools=[{'type':'function','function':{'name':'lookup','parameters':{'type':'object','properties':{'topic':{'type':'string'}},'required':['topic'],'additionalProperties':False}}}]
            with self.assertRaises(CloudFailure):adapter.complete([{'role':'user','content':'Explain physics'}],tools=tools)
            self.assertEqual(state['calls'],1)

    def test_exact_scoped_synthetic_image_and_refused_unapproved_image(self):
        import base64,hashlib,io
        from PIL import Image
        buffer=io.BytesIO();Image.new('RGB',(16,16),'green').save(buffer,format='PNG')
        raw=buffer.getvalue();url='data:image/png;base64,'+base64.b64encode(raw).decode()
        messages=[{'role':'user','content':[{'type':'text','text':'Describe public geometric artwork'},{'type':'image_url','image_url':{'url':url}}]}]
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint)
            with self.assertRaises(CloudFailure):adapter.complete(messages)
            self.assertEqual(state['calls'],0)
            self.assertEqual(adapter.complete(messages,output_tokens=100,approved_image_hashes=[hashlib.sha256(raw).hexdigest()])['content'],'Public answer')

    def test_cancel_before_dispatch_and_close_prevent_network(self):
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint)
            with self.assertRaises(CloudFailure):adapter.complete([{'role':'user','content':'Explain physics'}],cancelled=lambda:True)
            adapter.close()
            with self.assertRaises(CloudFailure):adapter.complete([{'role':'user','content':'Explain physics'}])
            self.assertEqual(state['calls'],0)

    def test_feedback_never_overrides_privacy_or_offline_mode(self):
        gateway=HybridGateway(self.root,self.options,adapter=Mock(),guardian=self.guard)
        for _ in range(3):gateway.performance.feedback('complex',self.options['model'],False)
        self.assertEqual(gateway.decide({'question':'Explain quantum computing'})['reason'],'validated_feedback_prefers_local')
        gateway.performance.reset()
        self.assertEqual(gateway.decide({'question':'Explain my private code'})['provider'],'local')

    def test_metadata_and_stream_have_wire_size_limits(self):
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint);state['mode']='big_metadata'
            adapter.refresh();self.assertFalse(adapter.ready())
            state['mode']='ok';adapter.refresh();state['mode']='big_stream'
            with self.assertRaises(CloudFailure):adapter.complete([{'role':'user','content':'Explain quantum computing'}],on_chunk=lambda text:None)
            self.assertEqual(state['calls'],1)

    def test_provider_timeout_retains_reservation_and_never_retries(self):
        with server() as (endpoint,state):
            adapter=self.adapter(endpoint);adapter.options={**self.options,'timeout_seconds':1};state['delay']=2
            with self.assertRaises(CloudFailure):adapter.complete([{'role':'user','content':'Explain physics'}])
            self.assertEqual(state['calls'],1)
            with self.guard.connect() as db:
                rows=db.execute('SELECT tokens,status FROM calls').fetchall()
            self.assertGreater(rows[0]['tokens'],0);self.assertEqual(rows[0]['status'],'uncertain')
