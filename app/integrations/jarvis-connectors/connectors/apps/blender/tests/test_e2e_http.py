"""End-to-end client -> real localhost HTTP server -> timer pump -> job response.
Uses fake Blender operations; demonstrates data transport without needing Blender installed.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from blender_connector.bridge import Bridge
from blender_connector.connector import BlenderConnector

class DummyBpyOps:
    def __init__(self):self.frame=1;self.executed=[]
    def execute(self,name,params):
        self.executed.append((name,params,threading.get_ident()))
        if name=='set_frame':self.frame=params['frame'];return {'action':name,'data':{'frame':self.frame}}
        if name=='health':return {'action':name,'data':{'ready':True}}
        raise ValueError('Operation unavailable in mock Blender')

class HttpIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.conf=Path(self.temp.name)/'bridge.json'
        self.patch=patch.dict(os.environ,{'JARVIS_BLENDER_CONFIG':str(self.conf)})
        self.patch.start()
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        self.ops=DummyBpyOps()
        self.bridge=Bridge(self.ops,port=port,token='t'*64).start()
        self.c=BlenderConnector(config_path=str(self.conf))
        self.stop=False;self.main=threading.get_ident()
        async def pump():
            while not self.stop:
                self.bridge.pump()
                await asyncio.sleep(.01)
        self.pump_task=asyncio.create_task(pump())
    async def asyncTearDown(self):
        self.stop=True;await self.pump_task;await self.c.close()
        self.bridge.stop();self.patch.stop();self.temp.cleanup()
    async def test_full_lifecycle_and_state(self):
        await self.c.connect()
        result=await self.c.execute('set_frame',{'frame':84},timeout=2)
        self.assertTrue(result['ok']);self.assertEqual(self.ops.frame,84)
        self.assertEqual(result['result']['data']['frame'],84)
        self.assertEqual(self.ops.executed[-1][2],self.main)
        r=await self.c.job_status(result['job_id']);self.assertEqual(r['status'],'done')
    async def test_unknown_command_refused_before_network(self):
        with self.assertRaises(Exception):await self.c.execute('python_exec',{'source':'quit()'})
        self.assertFalse(self.ops.executed)
    async def test_error_job_from_blender(self):
        with self.assertRaisesRegex(Exception,'mock Blender'):
            await self.c.execute('set_fps',{'fps':24},timeout=2)
    async def test_health_after_disconnect(self):
        self.assertTrue((await self.c.health())['reachable'])
        self.bridge.stop()
        self.assertFalse((await self.c.health())['reachable'])

if __name__=='__main__':unittest.main()
