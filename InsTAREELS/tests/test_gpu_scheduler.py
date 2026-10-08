import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import requests
from jarvis.gpu_scheduler import Registry, Lease, settings, allocation, install, status


class GPUSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.registry=Registry(self.temporary.name)
        self.policy=settings({'enabled':True,'wait_seconds':2})

    def state(self):return json.loads(self.registry.path.read_text())

    def response(self):
        response=requests.Response();response.status_code=200
        response._content=b'{}';response.raw=Mock()
        return response

    def transport(self,role='planner',response=None):
        method=patch('requests.sessions.Session.post',return_value=response or self.response()).start()
        observed=self.response();observed._content=b'{"models":[]}'
        patch('requests.sessions.Session.get',return_value=observed).start()
        self.addCleanup(patch.stopall)
        client=install(requests.Session(),role)
        self.addCleanup(client.close)
        for name,value in [('configured',self.policy),('Registry',self.registry),
                           ('memory',{'total_mb':4096,'used_mb':1041})]:
            patch('jarvis.gpu_scheduler.'+name,return_value=value).start()
        return client,method

    def test_reserves_speech_and_shrinks_layers_for_context(self):
        hardware={'total_mb':4096,'used_mb':1041}
        small=allocation('qwen3.5:9b',8192,self.policy,hardware)
        large=allocation('qwen3.5:9b',32768,self.policy,hardware)
        self.assertEqual(small,12);self.assertEqual(large,9)
        self.assertLess(large,small)
        self.assertEqual(allocation('qwen3.5:9b',8192,self.policy,{'total_mb':4096,'used_mb':3900}),0)
        self.assertEqual(allocation('unknown:70b',8192,self.policy,hardware),0)
        self.assertEqual(allocation('qwen3.5:9b',8192,self.policy,None),0)
        self.assertEqual(allocation('qwen3.5:9b',-1,self.policy,hardware),0)
        self.assertEqual(allocation('jarvis-codex-qwen3.5:9b',32768,{**self.policy,'primary_layers':0},hardware),9)
        self.assertEqual(allocation('jarvis-codex-qwen3.5:9b',32768,{**self.policy,'codex_layers':0},hardware),0)

    def test_small_models_use_gpu_only_with_reserved_capacity(self):
        self.assertEqual(allocation('qwen3.5:0.8b',2048,self.policy,{'total_mb':4096,'used_mb':0}),0)
        self.assertEqual(allocation('qwen3.5:0.8b',2048,{**self.policy,'helper_gpu':True},{'total_mb':4096,'used_mb':0}),-1)
        self.assertEqual(allocation('qwen3.5:0.8b',2048,self.policy,{'total_mb':4096,'used_mb':3000}),0)

    def test_priority_is_shared_across_actual_processes(self):
        owner=Lease('execution','fixture',self.policy,self.registry);owner.acquire()
        code=('import sys,time;from jarvis.gpu_scheduler import Registry,Lease,settings;'
              'r=Registry(sys.argv[1]);l=Lease(sys.argv[2],"fixture",settings({"wait_seconds":5}),r);'
              'l.acquire();time.sleep(.05);l.close()')
        processes=[]
        try:
            for role in ('coding','planner'):
                processes.append(subprocess.Popen([sys.executable,'-c',code,self.temporary.name,role],
                    stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
            deadline=time.monotonic()+5
            while len(self.state()['pending'])<2 and time.monotonic()<deadline:time.sleep(.02)
            self.assertEqual(len(self.state()['pending']),2)
            owner.close()
            for p in processes:
                _,error=p.communicate(timeout=6);self.assertEqual(p.returncode,0,error.decode())
            events=[json.loads(x) for x in (self.registry.root/'events.jsonl').read_text().splitlines()]
            self.assertEqual([r['role'] for r in events if r['stage']=='admitted'],['execution','planner','coding'])
            self.assertIsNone(self.state()['active'])
        finally:
            owner.close()
            for p in processes:
                if p.poll() is None:p.terminate();p.communicate(timeout=3)

    def test_actual_crashed_owner_is_reaped_without_replaying_work(self):
        code=('import sys,os;from jarvis.gpu_scheduler import Registry,Lease,settings;'
              'Lease("coding","fixture",settings(),Registry(sys.argv[1])).acquire();os._exit(0)')
        p=subprocess.run([sys.executable,'-c',code,self.temporary.name],capture_output=True,timeout=5,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.assertEqual(p.returncode,0,p.stderr.decode())
        dead=self.state()['active'];self.assertIsNotNone(dead)
        next_turn=Lease('planner','fixture',self.policy,self.registry)
        try:
            self.assertTrue(next_turn.acquire());self.assertNotEqual(self.state()['active']['token'],dead['token'])
        finally:next_turn.close()
        self.assertIsNone(self.state()['active'])

    def test_cancelled_waiter_leaves_active_owner_untouched(self):
        owner=Lease('coding','fixture',self.policy,self.registry);owner.acquire()
        stopped=threading.Event();errors=[]
        waiter=Lease('planner','fixture',self.policy,self.registry,cancelled=stopped.is_set)
        def work():
            try:waiter.acquire()
            except ValueError as exc:errors.append(str(exc))
        thread=threading.Thread(target=work);thread.start()
        try:
            deadline=time.monotonic()+2
            while not self.state()['pending'] and time.monotonic()<deadline:time.sleep(.01)
            stopped.set();thread.join(2)
            self.assertFalse(thread.is_alive());self.assertIn('cancelled',errors[0])
            self.assertEqual(self.state()['active']['token'],owner.row['token'])
            self.assertEqual(self.state()['pending'],[])
        finally:stopped.set();thread.join(2);owner.close()

    def test_queue_deadline_does_not_dispatch_or_clear_active_work(self):
        owner=Lease('coding','fixture',self.policy,self.registry);owner.acquire()
        try:
            waiter=Lease('planner','fixture',{**self.policy,'wait_seconds':1},self.registry)
            with self.assertRaisesRegex(ValueError,'deadline'):waiter.acquire()
            self.assertEqual(self.state()['pending'],[])
            self.assertEqual(self.state()['active']['token'],owner.row['token'])
        finally:owner.close()

    def test_corrupt_state_is_preserved_and_fails_closed(self):
        self.registry.path.write_text('not JSON')
        with self.assertRaises(ValueError):Lease('planner','fixture',self.policy,self.registry).acquire()
        self.assertEqual(self.registry.path.read_text(),'not JSON')

    @unittest.skipUnless(os.name=='nt','Windows file-sharing fault')
    def test_transient_atomic_promotion_lock_retries_only_local_state(self):
        real=os.replace;attempts=[]
        def replace(source,target):
            attempts.append(str(target))
            if len(attempts)<=2:raise PermissionError('reader sharing violation')
            return real(source,target)
        with patch('jarvis.gpu_scheduler.os.replace',side_effect=replace):
            lease=Lease('planner','fixture',self.policy,self.registry)
            try:
                self.assertTrue(lease.acquire())
                self.assertEqual(self.state()['active']['token'],lease.row['token'])
                self.assertEqual(self.state()['pending'],[])
            finally:lease.close()
        events=[json.loads(x) for x in (self.registry.root/'events.jsonl').read_text().splitlines()]
        self.assertEqual(sum(e['stage']=='admitted' for e in events),1)
        self.assertIsNone(self.state()['active'])

    @unittest.skipUnless(os.name=='nt','Windows file-sharing fault')
    def test_permanent_atomic_promotion_failure_is_bounded_and_preserves_state(self):
        with self.registry.state() as state:state['fixture']='preserved'
        before=self.registry.path.read_bytes();started=time.monotonic()
        with patch('jarvis.gpu_scheduler.os.replace',side_effect=PermissionError('permanent lock')):
            with self.assertRaises(PermissionError):
                with self.registry.state() as state:state['fixture']='new'
        self.assertLess(time.monotonic()-started,1)
        self.assertEqual(self.registry.path.read_bytes(),before)

    def test_stream_retains_slot_until_close_then_releases_once(self):
        client,method=self.transport()
        result=client.post('http://127.0.0.1:11434/api/chat',json={'model':'qwen3.5:9b','messages':[{'content':'fixture'}],
            'options':{'num_gpu':0,'num_ctx':8192}},stream=True)
        self.assertEqual(self.state()['active']['role'],'planner')
        self.assertEqual(method.call_args.kwargs['json']['options']['num_gpu'],11)
        self.assertEqual(method.call_args.kwargs['json']['options']['num_ctx'],16384)
        self.assertEqual(method.call_args.kwargs['json']['keep_alive'],30)
        result.close();result.close()
        self.assertIsNone(self.state()['active']);self.assertEqual(method.call_count,1)

    def test_transport_failure_releases_without_retry(self):
        client,method=self.transport();method.side_effect=requests.Timeout('uncertain')
        with self.assertRaises(requests.Timeout):
            client.post('http://127.0.0.1:11434/api/chat',json={'model':'qwen3.5:9b','messages':[{}]})
        self.assertEqual(method.call_count,1);self.assertIsNone(self.state()['active'])

    def test_response_close_failure_still_releases_slot(self):
        response=self.response();response.close=Mock(side_effect=OSError('close failed'))
        client,method=self.transport(response=response)
        result=client.post('http://127.0.0.1:11434/api/chat',json={'model':'qwen3.5:9b','messages':[{}]},stream=True)
        with self.assertRaises(OSError):result.close()
        self.assertEqual(method.call_count,1);self.assertIsNone(self.state()['active'])

    def test_busy_helper_runs_on_cpu_without_taking_foreground_slot(self):
        self.policy['helper_gpu']=True
        owner=Lease('coding','fixture',self.policy,self.registry);owner.acquire()
        client,method=self.transport('context')
        try:
            client.post('http://127.0.0.1:11434/api/chat',json={'model':'qwen3.5:0.8b','messages':[{}]})
            self.assertEqual(method.call_args.kwargs['json']['options']['num_gpu'],0)
            self.assertEqual(self.state()['active']['token'],owner.row['token'])
            self.assertEqual(self.state()['pending'],[])
        finally:owner.close()

    def test_default_idle_helper_never_takes_foreground_slot(self):
        client,method=self.transport('context')
        client.post('http://127.0.0.1:11434/api/chat',json={'model':'qwen3.5:0.8b','messages':[{}]})
        self.assertEqual(method.call_args.kwargs['json']['options']['num_gpu'],0)
        self.assertFalse(self.registry.path.exists())

    def test_codex_retains_api_body_and_limits_only_its_model_cache_after_turn(self):
        client,method=self.transport('coding')
        observed=self.response();observed._content=json.dumps({'models':[{'name':'jarvis-codex-qwen3.5:9b','context_length':32768,'size_vram':2200*1048576,'digest':'fixture'}]}).encode()
        patch('requests.sessions.Session.get',return_value=observed).start()
        body={'model':'jarvis-codex-qwen3.5:9b','input':'fixture','think':False}
        result=client.post('http://127.0.0.1:11434/v1/responses',json=body,stream=True)
        self.assertEqual(method.call_args.kwargs['json'],body)
        self.assertEqual(result.jarvis_gpu['num_gpu'],9)
        result.close()
        self.assertEqual(method.call_count,2)
        self.assertEqual(method.call_args.kwargs['json'],{'model':body['model'],'keep_alive':30})
        self.assertIsNone(self.state()['active'])

    def test_codex_failed_or_absent_cache_never_preloads_a_model_after_close(self):
        client,method=self.transport('coding')
        for status_code in (200,500):
            with self.subTest(status_code=status_code):
                method.reset_mock();response=self.response();response.status_code=status_code;method.return_value=response
                result=client.post('http://127.0.0.1:11434/v1/responses',json={'model':'jarvis-codex-qwen3.5:9b','input':'fixture'},stream=True)
                result.close()
                self.assertEqual(method.call_count,1)
                self.assertIsNone(self.state()['active'])
                self.assertFalse(self.state().get('resident'))

    def test_coding_cache_identity_survives_uncertain_duration_update(self):
        client,method=self.transport('coding')
        observed=self.response();observed._content=json.dumps({'models':[{'name':'jarvis-codex-qwen3.5:9b','context_length':32768,'size_vram':2200*1048576,'digest':'fixture'}]}).encode()
        timer=self.response();timer.status_code=500;method.side_effect=[self.response(),timer]
        with patch('requests.sessions.Session.get',return_value=observed):
            result=client.post('http://127.0.0.1:11434/v1/responses',json={'model':'jarvis-codex-qwen3.5:9b','input':'fixture'},stream=True);result.close()
        self.assertEqual(method.call_count,2);self.assertEqual(self.state()['resident']['digest'],'fixture')
        self.assertIsNone(self.state()['active'])

    def test_codex_refuses_low_vram_before_any_inference(self):
        client,method=self.transport('coding')
        with patch('jarvis.gpu_scheduler.memory',return_value={'total_mb':4096,'used_mb':3900}):
            with self.assertRaisesRegex(ValueError,'Insufficient'):
                client.post('http://127.0.0.1:11434/v1/responses',json={'model':'jarvis-codex-qwen3.5:9b','input':'fixture'})
        method.assert_not_called();self.assertIsNone(self.state()['active'])

    def test_explicit_cpu_coding_bounds_observed_alias_cache(self):
        self.policy['codex_layers']=0
        client,method=self.transport('coding')
        observation=self.response();observation._content=json.dumps({'models':[{'name':'jarvis-codex-qwen3.5:9b','digest':'fixture','size_vram':0,'context_length':32768}]}).encode()
        with patch('requests.sessions.Session.get',return_value=observation),patch('jarvis.gpu_scheduler.memory',return_value=None):
            result=client.post('http://127.0.0.1:11434/v1/responses',json={'model':'jarvis-codex-qwen3.5:9b','input':'fixture'},stream=True)
            result.close()
        self.assertEqual(result.jarvis_gpu['num_gpu'],0)
        self.assertEqual(method.call_args.kwargs['json']['keep_alive'],0)
        self.assertIsNone(self.state()['active']);self.assertFalse(self.state().get('resident'))

    def cache(self):
        row={'name':'qwen3.5:9b','digest':'fixture','context_length':16384,'size_vram':2400*1048576}
        with self.registry.state() as state:
            state['resident']={'model':row['name'],'digest':row['digest'],'context':16384,
                'num_gpu':11,'size_vram':row['size_vram'],'expires_at':time.time()+30}
        return row

    def test_same_model_reuses_owned_warm_gpu_cache(self):
        row=self.cache();client,method=self.transport()
        observation=self.response();observation._content=json.dumps({'models':[row]}).encode()
        with patch('requests.sessions.Session.get',return_value=observation), \
             patch('jarvis.gpu_scheduler.memory',return_value={'total_mb':4096,'used_mb':3500}):
            client.post('http://127.0.0.1:11434/api/chat',json={'model':row['name'],'messages':[{}],'options':{'num_ctx':8192}})
        self.assertEqual(method.call_count,1)
        self.assertEqual(method.call_args.kwargs['json']['options']['num_gpu'],11)
        self.assertEqual(self.state()['resident']['digest'],'fixture')

    def test_model_handoff_unloads_identified_cache_before_codex_once(self):
        row=self.cache();client,method=self.transport('coding')
        observation=self.response();observation._content=json.dumps({'models':[row]}).encode()
        with patch('requests.sessions.Session.get',return_value=observation), \
             patch('jarvis.gpu_scheduler.memory',side_effect=[{'total_mb':4096,'used_mb':3500},{'total_mb':4096,'used_mb':1041}]):
            result=client.post('http://127.0.0.1:11434/v1/responses',json={'model':'jarvis-codex-qwen3.5:9b','input':'fixture'},stream=True)
        self.assertEqual(method.call_count,2)
        self.assertEqual(method.call_args_list[0].kwargs['json'],{'model':row['name'],'keep_alive':0})
        self.assertTrue(method.call_args_list[1].args[0].endswith('/v1/responses'))
        result.close();self.assertEqual(method.call_count,2)
        self.assertIsNone(self.state()['resident']);self.assertIsNone(self.state()['active'])

    def test_changed_cache_identity_never_unloads_the_shared_model(self):
        row=self.cache();row['digest']='changed-by-another-client'
        client,method=self.transport()
        observation=self.response();observation._content=json.dumps({'models':[row]}).encode()
        with patch('requests.sessions.Session.get',return_value=observation), \
             patch('jarvis.gpu_scheduler.memory',return_value={'total_mb':4096,'used_mb':3900}):
            client.post('http://127.0.0.1:11434/api/chat',json={'model':row['name'],'messages':[{}]})
        self.assertEqual(method.call_count,1)
        self.assertTrue(method.call_args.args[0].endswith('/api/chat'))
        self.assertEqual(method.call_args.kwargs['json']['options']['num_gpu'],0)

    def test_malformed_context_never_takes_a_slot(self):
        client,method=self.transport()
        with self.assertRaisesRegex(ValueError,'Invalid inference context'):
            client.post('http://127.0.0.1:11434/api/chat',json={'model':'qwen3.5:9b','options':{'num_ctx':'bad'}})
        method.assert_not_called();self.assertFalse(self.registry.path.exists())

    def test_invalid_policy_is_rejected(self):
        for options in ([],{'enabled':'yes'},{'helper_gpu':'yes'},{'primary_layers':True},{'codex_layers':34},{'reserve_mb':0},{'wait_seconds':500}):
            with self.subTest(options=options),self.assertRaises(ValueError):settings(options)

    def test_heartbeat_excludes_private_request_content(self):
        lease=Lease('planner','qwen3.5:9b',self.policy,self.registry);lease.acquire()
        try:
            with self.registry.state() as state:state['active']['prompt']='private-fixture-content'
            value=status(self.temporary.name)
            self.assertEqual(value['active_role'],'planner');self.assertEqual(value['status'],'busy')
            self.assertNotIn('private-fixture-content',json.dumps(value))
            self.assertNotIn('token',value);self.assertNotIn('pid',value)
        finally:lease.close()

    def test_corrupt_heartbeat_state_does_not_repair_or_block_ui(self):
        self.registry.path.write_text('invalid JSON')
        self.assertEqual(status(self.temporary.name),{'status':'unavailable'})
        self.assertEqual(self.registry.path.read_text(),'invalid JSON')


if __name__=='__main__':unittest.main()
