import asyncio
import unittest
from blender_connector.connector import BlenderConnector
from blender_connector.base import ConnectorError

class FakeTransport:
    def __init__(self):self.calls=[];self.state='done';self.queued=None
    def __call__(self,method,path,data):
        self.calls.append((method,path,data))
        if path=='/v1/health':return {'ok':True,'connected':True,'queue_depth':0}
        if path=='/v1/execute':self.queued=data;return {'ok':True,'job_id':'a'*32}
        return {'ok':True,'job':{'status':self.state,'result':{'action':self.queued['action']} if self.queued else None,'error':{'message':'failure'}}}

class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tx=FakeTransport();self.c=BlenderConnector(transport=self.tx)
    async def test_info(self):
        self.assertEqual(self.c.info.namespace,'blender')
        self.assertEqual(len(self.c.info.capabilities),200)
    async def test_connect_health(self):
        await self.c.connect();health=await self.c.health()
        self.assertTrue(health['reachable']);await self.c.close()
    async def test_read(self):
        r=await self.c.execute('scene_summary')
        self.assertTrue(r['ok']);self.assertEqual(r['result']['action'],'scene_summary')
    async def test_safe_write(self):
        r=await self.c.execute('add_cube',{'size':1.0,'name':'My Cube'})
        self.assertTrue(r['ok']);self.assertEqual(self.tx.queued['params']['name'],'My Cube')
    async def test_denied_destructive(self):
        with self.assertRaisesRegex(ConnectorError,'approval required'):
            await self.c.execute('delete_object',{'name':'Cube'})
        self.assertFalse(self.tx.calls)
    async def test_denied_filesystem(self):
        with self.assertRaisesRegex(ConnectorError,'approval required'):
            await self.c.execute('save_project',{'filepath':'C:/project.blend'})
    async def test_permitted_approval_callback(self):
        self.c.approval_callback=lambda name,p,risk:True
        result=await self.c.execute('delete_object',{'name':'Cube'})
        self.assertTrue(result['ok'])
    async def test_rejected_approval_callback(self):
        self.c.approval_callback=lambda name,p,risk:False
        with self.assertRaisesRegex(ConnectorError,'rejected'):
            await self.c.execute('delete_object',{'name':'Cube'})
    async def test_async_approval_callback(self):
        async def approve(name,p,risk):return True
        self.c.approval_callback=approve
        self.assertTrue((await self.c.execute('delete_object',{'name':'Cube'}))['ok'])
    async def test_queued_result(self):
        r=await self.c.execute('add_cube',wait=False)
        self.assertEqual(r['status'],'queued')
    async def test_job_status(self):
        self.assertEqual((await self.c.job_status('a'*32))['status'],'done')
    async def test_bad_job_id(self):
        with self.assertRaises(ConnectorError):await self.c.job_status('../../etc')
    async def test_failed_job(self):
        self.tx.state='error'
        with self.assertRaises(ConnectorError):await self.c.execute('scene_summary')
    async def test_timed_out_job(self):
        self.tx.state='running'
        res=await self.c.execute('scene_summary',timeout=0.02,poll_seconds=.02)
        self.assertFalse(res['ok']);self.assertIn('may still run',res['note'])
    async def test_client_rejects_unknown_param(self):
        with self.assertRaises(ConnectorError):await self.c.execute('add_cube',{'shell':'!rm -rf'})
        self.assertFalse(self.tx.calls)
    async def test_no_retry_on_timeout(self):
        self.tx.state='running'
        res=await self.c.execute('add_cube',timeout=.02,poll_seconds=.02)
        self.assertEqual(len([x for x in self.tx.calls if x[0]=='POST']),1)
        self.assertFalse(res['ok'])

if __name__=='__main__':unittest.main()
