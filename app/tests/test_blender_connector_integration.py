"""Safety fixtures and real stdio transport; these do not certify bpy behavior."""
import asyncio
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

BASE=Path(__file__).resolve().parents[1]
ROOT=BASE/'integrations/jarvis-connectors/connectors/apps/blender'
sys.path.insert(0,str(ROOT))
from server import BlenderConnector
from adapter import approval_digest
from blender_connector.bridge import Bridge
from blender_connector.catalog import ACTIONS, validate_action
from blender_connector.operations import _path, BlenderOperations
from jarvis import blender_host, mcp_bridge
from jarvis.tools import ToolRegistry


class FakeOperations:
    def __init__(self): self.calls=[]
    def execute(self,name,params):
        self.calls.append((name,params))
        return {'action':name,'data':params}


class BlenderIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.base=Path(self.temp.name)
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        self.ops=FakeOperations()
        self.bridge=Bridge(self.ops,port=port,write_config=False).start()
        self.config=self.base/'scope.json'
        self.config.write_text(json.dumps({'host':'127.0.0.1','port':port,'token':self.bridge.token,'scope_id':self.bridge.scope_id}))
        self.stop=threading.Event()
        def pump():
            while not self.stop.wait(.01): self.bridge.pump()
        self.thread=threading.Thread(target=pump,daemon=True);self.thread.start()
        self.child={'enabled':True,'trusted':True,'approval_binding':'blender-v1','command':sys.executable,
            'args':[str(ROOT/'server.py'),'--runtime','builtin','--allow-write','--bridge-config',str(self.config)],
            'allow_tools':[r['tool'] for r in blender_host.catalog()],'env_names':[],'timeout_seconds':10}
        (self.base/'.jarvis').mkdir()
        (self.base/'.jarvis/mcp.json').write_text(json.dumps({'servers':{'blender':self.child}}))
        self.actions=SimpleNamespace(base=self.base,config={},report=Mock(),_approve=Mock(),skills=None,allowed_tools=None)

    def tearDown(self):
        child=getattr(self.actions,'_blender_mcp',None)
        if child is not None:child.close()
        monitor=getattr(self.actions,'_blender_jobs',None)
        if monitor is not None:monitor.close()
        self.stop.set();self.thread.join(2);self.bridge.stop();self.temp.cleanup()

    def call(self,name,args=None):
        step={'action':'mcp_call','value':'blender','content':json.dumps({'name':'blender_'+name,'arguments':args or {}})}
        return json.loads(ToolRegistry(self.actions).execute(step,lambda:False).evidence)

    def test_203_tools_real_wire_and_bounded_discovery(self):
        client=mcp_bridge.StdioClient(self.child,self.base,lambda:False)
        try:
            client.initialize();rows=client.tools()
            self.assertEqual(len(rows),203)
            self.assertEqual({r['name'] for r in rows},{'blender_'+a for a in ACTIONS}|{'blender_bridge_health','blender_job_status','blender_wait_job'})
            self.assertLessEqual(len(blender_host.discovery(rows,{})['tools']),3)
            self.assertLess(len(json.dumps(blender_host.discovery(rows,{'query':'object','limit':6}))),9500)
            self.assertEqual(blender_host.discovery(rows,{'query':'blender_add_cube'})['tools'][0]['name'],'blender_add_cube')
        finally:client.close()

    def test_host_approval_bound_write_and_job_scope(self):
        result=self.call('add_cube',{'name':'Fixture'})['structuredContent']['result']
        job=result['untrusted_data']['job_id']
        self.assertEqual(result['untrusted_data']['status'],'queued')
        time.sleep(.05)
        polled=self.call('job_status',{'job_id':job,'expected_scope':result['scope_id']})
        self.assertEqual(polled['structuredContent']['result']['untrusted_data']['status'],'done')
        self.assertEqual(sum(n=='add_cube' for n,p in self.ops.calls),1)
        self.assertGreaterEqual(self.actions._approve.call_count,3)

    def test_observer_completion_idle_shutdown_and_no_replay(self):
        result=self.call('add_cube',{'name':'Observed'})['structuredContent']['result']
        monitor=self.actions._blender_jobs
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            with monitor.lock:
                status=monitor.jobs[result['untrusted_data']['job_id']]['status']
            if status=='done':break
            time.sleep(.02)
        self.assertEqual(status,'done')
        self.assertEqual(sum(n=='add_cube' for n,p in self.ops.calls),1)
        monitor.close()
        self.assertFalse(monitor.repair())

    def test_observer_scope_drift_never_replays(self):
        from jarvis.blender_jobs import BlenderJobs
        monitor=BlenderJobs(self.actions)
        row={'config':str(self.config),'scope_id':'f'*32,'job_id':'a'*32}
        with self.assertRaisesRegex(ValueError,'scope changed'):monitor._read(row)
        self.assertFalse(self.ops.calls)
        monitor.close()

    def test_restart_preserves_receipts_without_automatic_action_or_poll(self):
        from jarvis.blender_jobs import BlenderJobs
        path=self.base/'.jarvis-runtime/blender/jobs.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps([{'job_id':'a'*32,'scope_id':'b'*32,'status':'running'}]))
        monitor=BlenderJobs(self.actions)
        self.assertEqual(monitor.jobs['a'*32]['status'],'interrupted_inspect_receipt')
        self.assertIsNone(monitor.thread)
        self.assertTrue(monitor.healthy())
        self.assertFalse(self.ops.calls)
        monitor.close()

    def test_bridge_auth_saturation_and_job_collision(self):
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        address='http://127.0.0.1:'+str(self.bridge.port)
        with self.assertRaises(HTTPError) as denied:urlopen(address+'/v1/health')
        self.assertEqual(denied.exception.code,401)
        self.stop.set();self.thread.join(2)
        def send():
            body=json.dumps({'action':'add_cube','params':{},'scope_id':self.bridge.scope_id}).encode()
            request=Request(address+'/v1/execute',data=body,headers={'Authorization':'Bearer '+self.bridge.token})
            with urlopen(request) as response:return json.load(response)['job_id']
        jobs=[send() for _ in range(32)]
        self.assertEqual(len(set(jobs)),32)
        with self.assertRaises(HTTPError) as full:send()
        self.assertEqual(full.exception.code,429)
        self.assertFalse(self.ops.calls)

    def test_host_denial_dispatches_no_mutation(self):
        self.actions._approve.side_effect=PermissionError('denied')
        with self.assertRaises(PermissionError):self.call('add_cube')
        self.assertFalse(self.ops.calls)

    def test_owned_child_crash_backoff_reconnect_never_replays_write(self):
        self.child['persistent']=True
        (self.base/'.jarvis/mcp.json').write_text(json.dumps({'servers':{'blender':self.child}}))
        receipt=self.call('add_cube',{'name':'Once'})['structuredContent']['result']
        time.sleep(.05)
        owner=self.actions._blender_mcp
        previous=owner.client.process.pid
        owner.client.process.kill();owner.client.process.wait(timeout=3)
        with self.assertRaisesRegex(ValueError,'backoff'):self.call('bridge_health')
        time.sleep(2.1)
        status=self.call('job_status',{'job_id':receipt['untrusted_data']['job_id'],'expected_scope':receipt['scope_id']})
        self.assertEqual(status['structuredContent']['result']['untrusted_data']['status'],'done')
        self.assertNotEqual(owner.client.process.pid,previous)
        self.assertFalse(hasattr(self.actions,'_spotify_mcp'))
        self.assertEqual(sum(n=='add_cube' for n,p in self.ops.calls),1)

    def test_fresh_scope_approval_denial_no_edit(self):
        self.actions._approve.side_effect=[None,PermissionError('scope denied')]
        with self.assertRaises(PermissionError):self.call('add_cube')
        self.assertFalse(self.ops.calls)

    def test_model_cannot_forge_approval(self):
        child=BlenderConnector(allow_write=True)
        child.service.config_path=self.config
        response=child.call('blender_delete_object',{'name':'Cube','host_authorization':'true'})
        self.assertTrue(response['isError']);self.assertFalse(self.ops.calls)

    def test_read_only_mode_hides_writes(self):
        self.assertNotIn('blender_add_cube',{r['name'] for r in BlenderConnector().describe()})

    def test_scope_mismatch_never_dispatches(self):
        with self.assertRaisesRegex(ValueError,'scope changed'):
            self.call('add_cube',{'expected_scope':'f'*32})
        self.assertFalse(self.ops.calls)

    def test_jobs_need_original_scope(self):
        with self.assertRaisesRegex(ValueError,'original job scope'):
            self.call('job_status',{'job_id':'a'*32})

    def test_nan_nested_and_type_confusion(self):
        for name,args in [('add_cube',{'size':math.nan}),('set_transform',{'name':'Cube','location':[0,math.inf,0]}),('add_cube',{'size':True}),('batch',{'steps':[{'action':'add_cube','params':{'location':[0,0,math.nan]}}]})]:
            with self.subTest(name=name),self.assertRaises(ValueError):validate_action(name,args)

    def test_bad_parameters_no_external_effect(self):
        for args in ({'size':'big'},{'name':'X','python':'print(1)'},{'name':'   '},{'name':'bad\x00name'}):
            with self.assertRaises(ValueError): self.call('add_cube',args)
        self.assertFalse(self.ops.calls)

    def test_path_traversal_extension_symlink_and_overwrite(self):
        safe=self.base/'safe';safe.mkdir();outside=self.base/'outside';outside.mkdir()
        with patch.dict(os.environ,{'JARVIS_BLENDER_ALLOWED_ROOTS':str(safe)}):
            for value in (safe/'../escape.blend',safe/'bad.exe'):
                with self.assertRaises((PermissionError,ValueError)):_path(str(value),'write',{'.blend'})
            target=safe/'existing.blend';target.write_bytes(b'fixture')
            with self.assertRaisesRegex(PermissionError,'overwrite'):_path(str(target),'write',{'.blend'})
            try:(safe/'link').symlink_to(outside,target_is_directory=True)
            except OSError: pass # Junction/symlink creation unavailable is a separate unexecuted gate.
            else:
                with self.assertRaises(PermissionError):_path(str(safe/'link/escape.blend'),'write',{'.blend'})

    def test_no_arbitrary_python_tool(self):
        with self.assertRaises(ValueError):validate_action('execute_python',{'code':'pass'})

    def test_pack_rejects_untrusted_external_resource_before_io(self):
        pack=Mock()
        fake=SimpleNamespace(data=SimpleNamespace(images=[SimpleNamespace(filepath=str(self.base/'private.png'),library=None)]),
            path=SimpleNamespace(abspath=lambda path,**kwargs:path),ops=SimpleNamespace(file=SimpleNamespace(pack_all=pack)))
        allowed=self.base/'allowed';allowed.mkdir()
        with patch.dict(os.environ,{'JARVIS_BLENDER_ALLOWED_ROOTS':str(allowed)}):
            with self.assertRaises(PermissionError):BlenderOperations(fake).execute('pack_resources')
        pack.assert_not_called()

    def test_namespace_and_other_config_preserved_in_registration(self):
        spec=importlib.util.spec_from_file_location('register_blender',BASE/'scripts/setup/register_blender_connector.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        path=self.base/'.jarvis/mcp.json';data=json.loads(path.read_text())
        data['servers']['youtube']={'fixture':'preserve'};data['servers']['spotify']={'fixture':'preserve'}
        path.write_text(json.dumps(data))
        # Registration fixture uses a copied canonical inventory; production config is untouched.
        dest=self.base/'integrations/jarvis-connectors/connectors/apps/blender';dest.mkdir(parents=True)
        (dest/'catalog.json').write_bytes((ROOT/'catalog.json').read_bytes())
        module.register(self.base,disable=True)
        updated=json.loads(path.read_text())
        self.assertEqual(updated['servers']['youtube'],data['servers']['youtube'])
        self.assertEqual(updated['servers']['spotify'],data['servers']['spotify'])
        self.assertFalse(updated['servers']['blender']['enabled'])


class BlenderLanguage(unittest.TestCase):
    def test_skill_memory_offers_blender_guidance_without_permission(self):
        from jarvis.obsidian_memory import ObsidianMemory
        from jarvis.skill_memory import SkillMemory
        from jarvis.capabilities import runtime_context
        with tempfile.TemporaryDirectory() as folder:
            memory=ObsidianMemory(Path(folder),{'enabled':True,'vault':'vault'})
            skills=SkillMemory(memory);skills.sync()
            context=runtime_context('create a bevel in Blender',ToolRegistry(None).catalog(),skills)
            self.assertIn('blender-modeling',[r['name'] for r in context['skills']])
            guide=next(r for r in context['skills'] if r['name']=='blender-modeling')
            self.assertEqual(guide['trust'],'untrusted_guidance')
            self.assertTrue((memory.vault/'Jarvis Skills/Builtins/blender-modeling/SKILL.md').is_file())

    def test_120_phrasings_through_actual_parser(self):
        from jarvis.commands import parse
        from jarvis.engine import FINAL_ONLY
        samples=[]
        for prefix in ('Blender, ','in Blender ',''):
            for shape in ('cube','sphere','plane','cylinder','cone'):
                for verb in ('add','create'):
                    for named in ('',' named Fixture'):
                        text=prefix+verb+' a '+shape+named+(' in Blender' if not prefix else '')
                        samples.append(text)
        samples += [x+' in Blender' for x in ('status','version','list objects','show scene','show selection','list materials')]*10
        timings=[]
        for text in samples:
            start=time.perf_counter();command=parse(text);timings.append((time.perf_counter()-start)*1000)
            self.assertEqual(command.kind,'blender_request',text)
        self.assertIn('blender_request',FINAL_ONLY)
        self.assertEqual(len(samples),120)
        timings.sort()
        (BASE/'artifacts/jarvis-audit/blender-connector/natural-language-fixture.json').write_text(json.dumps({'count':len(samples),'parse_ms':{'p50':timings[60],'p95':timings[114],'p99':timings[118]},'classification':'SIMULATED parsing only; no Blender processing or voice accuracy claim'},indent=2))


if __name__=='__main__':unittest.main()
