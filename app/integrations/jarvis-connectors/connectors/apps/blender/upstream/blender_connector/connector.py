"""Jarvis BaseConnector child, standard-library HTTP client for Blender local bridge.
No paid APIs, cloud calls, or Blender imports in Jarvis process.
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request,urlopen
from .base import BaseConnector,ConnectorError,ConnectorInfo
from .catalog import ACTIONS,validate_action

class BlenderConnector(BaseConnector):
    def __init__(self,config_path: str|None=None,transport:Any=None,approval_callback=None):
        self.config_path=Path(config_path).expanduser() if config_path else Path(os.environ.get('JARVIS_BLENDER_CONFIG',str(Path.home()/'.jarvis'/'blender-bridge.json'))).expanduser()
        self.transport=transport
        self.approval_callback=approval_callback
        self._lock=asyncio.Lock()
        self._connection=None

    @property
    def info(self):
        return ConnectorInfo(name='Blender',version='1.0.0',namespace='blender',capabilities=tuple(ACTIONS))

    def _config(self):
        if self.transport:return {'host':'127.0.0.1','port':8769,'token':'test-token'}
        try: conf=json.loads(self.config_path.read_text('utf-8'))
        except (OSError,ValueError) as exc: raise ConnectorError('Blender bridge not configured. Run start_blender_bridge.py inside Blender first') from exc
        if conf.get('host')!='127.0.0.1' or type(conf.get('port'))!=int or not 1024<=conf['port']<=65535 or not isinstance(conf.get('token'),str) or len(conf['token'])<32:
            raise ConnectorError('Invalid bridge configuration')
        return conf

    def _request(self,method,path,data=None):
        conf=self._config()
        if path not in {'/v1/health','/v1/execute'} and not (path.startswith('/v1/jobs/') and len(path)==len('/v1/jobs/')+32 and all(c in '0123456789abcdef' for c in path[-32:])):
            raise ConnectorError('Invalid bridge request path')
        body=json.dumps(data,allow_nan=False).encode('utf-8') if data is not None else None
        if self.transport:return self.transport(method,path,data)
        req=Request(f"http://127.0.0.1:{conf['port']}{path}",data=body,method=method,headers={'Authorization':'Bearer '+conf['token'],'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=6) as resp:
                result=json.load(resp)
        except (HTTPError,URLError,TimeoutError,OSError,ValueError) as exc:
            raise ConnectorError(f'Blender bridge request failed: {type(exc).__name__}') from exc
        return result

    async def connect(self):
        h=await asyncio.to_thread(self._request,'GET','/v1/health')
        if not h.get('ok') or not h.get('connected'):raise ConnectorError('Blender bridge not ready')
        self._connection=True

    async def close(self):
        self._connection=None  # Does not shut Blender down; bridge lifecycle owned by Blender.

    async def health(self):
        try:
            response=await asyncio.to_thread(self._request,'GET','/v1/health')
            return {'connector':'blender','reachable':response.get('connected',False),'queue_depth':response.get('queue_depth',0),'commands':len(ACTIONS)}
        except ConnectorError as exc:
            return {'connector':'blender','reachable':False,'error':str(exc),'commands':len(ACTIONS)}

    async def execute(self,action:str,params:dict|None=None,*,wait:bool=True,timeout:float=30.0,poll_seconds:float=.15):
        try: validated=validate_action(action,params or {})
        except (ValueError,TypeError) as exc:raise ConnectorError(str(exc)) from exc
        spec=ACTIONS[action]
        if spec.risk in {'destructive','filesystem'}:
            if self.approval_callback is None:
                raise ConnectorError(f'Jarvis approval required for blender_{action} ({spec.risk}); configure ToolRegistry approval callback')
            approved=self.approval_callback('blender_'+action,validated,spec.risk)
            if asyncio.iscoroutine(approved):approved=await approved
            if not approved:raise ConnectorError('Operation rejected by Jarvis authorization')
        async with self._lock:
            accepted=await asyncio.to_thread(self._request,'POST','/v1/execute',{'action':action,'params':validated})
        if not accepted.get('ok') or 'job_id' not in accepted:raise ConnectorError(str(accepted.get('error','Bridge did not accept command')))
        job_id=accepted['job_id']
        if not wait:return {'ok':True,'status':'queued','job_id':job_id,'action':action}
        return await self.wait_job(job_id,timeout=timeout,poll_seconds=poll_seconds)

    async def job_status(self,job_id):
        if not isinstance(job_id,str) or len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id):
            raise ConnectorError('Invalid job identifier')
        response=await asyncio.to_thread(self._request,'GET','/v1/jobs/'+job_id)
        if not response.get('ok'):raise ConnectorError('Blender job not found')
        return response['job']

    async def wait_job(self,job_id,timeout=30.0,poll_seconds=.15):
        if not isinstance(job_id,str) or len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id):raise ConnectorError('Invalid job identifier')
        if not 0<timeout<=86400 or not .02<=poll_seconds<=10:raise ConnectorError('Invalid wait parameters')
        deadline=time.monotonic()+timeout
        while True:
            response=await asyncio.to_thread(self._request,'GET','/v1/jobs/'+job_id)
            if not response.get('ok'):raise ConnectorError('Unable to read Blender bridge job')
            job=response.get('job',{})
            if job.get('status')=='done':
                result=job.get('result')
                partial=bool(isinstance(result,dict) and isinstance(result.get('data'),dict) and result['data'].get('partial'))
                return {'ok':not partial,'status':'partial' if partial else 'done','job_id':job_id,'result':result}
            if job.get('status')=='error':raise ConnectorError(f"Blender operation failed: {job.get('error',{})}")
            if job.get('status') not in {'running','queued'}:raise ConnectorError('Unknown job state')
            remaining=deadline-time.monotonic()
            if remaining<=0:return {'ok':False,'status':job.get('status'),'job_id':job_id,'note':'Timed out waiting; job may still run. Poll job_id; do not blindly retry mutating operations.'}
            await asyncio.sleep(min(poll_seconds,remaining))
