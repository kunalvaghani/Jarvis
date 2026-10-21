import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from blender_connector.bridge import Bridge

class FakeOperations:
    def __init__(self):self.calls=[];self.error=False
    def execute(self,a,p):
        self.calls.append((a,p,threading.get_ident()))
        if self.error:raise ValueError('fail by design')
        return {'action':a,'data':{'done':True}}

def available_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.config=Path(self.temp.name)/'bridge.json'
        self.prev=os.environ.get('JARVIS_BLENDER_CONFIG')
        os.environ['JARVIS_BLENDER_CONFIG']=str(self.config)
        self.ops=FakeOperations()
        self.bridge=Bridge(self.ops,port=available_port(),token='x'*64).start()
    def tearDown(self):
        self.bridge.stop()
        if self.prev is None:os.environ.pop('JARVIS_BLENDER_CONFIG',None)
        else:os.environ['JARVIS_BLENDER_CONFIG']=self.prev
        self.temp.cleanup()
    def req(self,path='/v1/health',data=None,token='x'*64,method=None):
        body=json.dumps(data).encode() if data is not None else None
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
        request=Request(f'http://127.0.0.1:{self.bridge.port}{path}',data=body,headers=headers,method=method)
        try:
            with urlopen(request,timeout=3) as response:return response.status,json.load(response)
        except HTTPError as exc:return exc.code,json.load(exc)
    def test_health(self):
        status,data=self.req();self.assertEqual(status,200);self.assertTrue(data['connected'])
    def test_auth(self):
        self.assertEqual(self.req(token='not_the_token')[0],401)
        self.assertEqual(self.req('/v1/jobs/bad',token='')[0],401)
    def test_no_untrusted_paths(self):self.assertEqual(self.req('/secret')[0],404)
    def test_config_written_and_removed(self):
        self.assertEqual(json.loads(self.config.read_text())['port'],self.bridge.port)
        if os.name!='nt':self.assertEqual(self.config.stat().st_mode&0o777,0o600)
        self.bridge.stop();self.assertFalse(self.config.exists())
    def test_accept_validation_and_pump(self):
        main=threading.get_ident()
        code,data=self.req('/v1/execute',{'action':'add_cube','params':{}},method='POST')
        self.assertEqual(code,202)
        job_id=data['job_id']
        self.assertEqual(self.req('/v1/jobs/'+job_id)[1]['job']['status'],'queued')
        self.assertEqual(self.bridge.pump(),.01)
        result=self.req('/v1/jobs/'+job_id)[1]['job']
        self.assertEqual(result['status'],'done')
        self.assertEqual(self.ops.calls[0][2],main) # only explicitly invoked main-thread pump executes bpy
    def test_rejects_bad_action_before_queue(self):
        bad=[{'action':'run_script','params':{}},{'action':'add_cube','params':{'hack':'import os'}},
             {'action':'delete_object','params':{}},{'action':'set_frame','params':{'frame':True}}]
        for req in bad:
            with self.subTest(req=req):self.assertEqual(self.req('/v1/execute',req,method='POST')[0],400)
        self.assertEqual(self.bridge.pending.qsize(),0)
    def test_errors_in_job(self):
        self.ops.error=True
        code,res=self.req('/v1/execute',{'action':'scene_summary','params':{}},method='POST')
        self.bridge.pump()
        self.assertEqual(self.req('/v1/jobs/'+res['job_id'])[1]['job']['status'],'error')
    def test_missing_job(self):self.assertEqual(self.req('/v1/jobs/'+'a'*32)[0],404)
    def test_queue_full_returns_429(self):
        for _ in range(32):self.assertEqual(self.req('/v1/execute',{'action':'health','params':{}},method='POST')[0],202)
        self.assertEqual(self.req('/v1/execute',{'action':'health','params':{}},method='POST')[0],429)
    def test_token_timing_comparison_and_bind_local(self):
        self.assertEqual(self.bridge._server.server_address[0],'127.0.0.1')
        self.assertEqual(self.req(token='x'*63+'z')[0],401)
    def test_jobs_not_confused(self):
        ids=[self.req('/v1/execute',{'action':'health','params':{}},method='POST')[1]['job_id'] for _ in range(3)]
        self.assertEqual(len(set(ids)),3)
        self.bridge.pump();self.assertEqual(self.req('/v1/jobs/'+ids[2])[1]['job']['status'],'queued')
    def test_clean_expired_only(self):
        self.bridge.jobs['old']={'status':'done','finished':time.time()-1000}
        self.bridge.jobs['stillrunning']={'status':'running','finished':time.time()-1000}
        self.bridge._cleanup()
        self.assertNotIn('old',self.bridge.jobs);self.assertIn('stillrunning',self.bridge.jobs)

if __name__=='__main__':unittest.main()
