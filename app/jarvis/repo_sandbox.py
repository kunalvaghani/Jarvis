"""Fail-closed Linux Docker runtime. No host-process or venv fallback exists."""
import json
import hashlib
from pathlib import Path
import re
import shutil
import threading
import time
from uuid import uuid4

from .repo_acquisition import command
from .skill_memory import linked

DEFAULT_IMAGE='jarvis-repository-runtime:1'


class RepositorySandbox:
    def __init__(self,image=DEFAULT_IMAGE):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:@-]{0,200}',image):raise ValueError('Invalid reviewed runtime image.')
        self.image=image;self.lock=threading.BoundedSemaphore(1)
        self.cached=None;self.cached_at=0

    def cli(self,args,cancelled=lambda:False,timeout=8,input_bytes=None):
        binary=shutil.which('docker')
        if not binary:raise ValueError('Docker CLI is unavailable; untrusted skill execution remains disabled.')
        return command([binary,'--host','npipe:////./pipe/dockerDesktopLinuxEngine',*args],cancelled,timeout,input_bytes,1000000)

    def status(self,refresh=False):
        if not refresh and self.cached and time.monotonic()-self.cached_at<30:return self.cached
        try:
            info=json.loads(self.cli(['info','--format','{{json .}}']))
            if info.get('OSType')!='linux' or info.get('Architecture') not in {'x86_64','amd64'}:
                raise ValueError('A local Linux x86_64 Docker engine is required.')
            if not all(info.get(k) for k in ('MemoryLimit','PidsLimit')):raise ValueError('Required container resource limits are unavailable.')
            images=json.loads(self.cli(['image','inspect',self.image]))
            image=images[0]
            if image.get('Os')!='linux' or image.get('Architecture')!='amd64':raise ValueError('Reviewed runtime must be Linux amd64.')
            if not re.fullmatch(r'sha256:[a-f0-9]{64}',image.get('Id','')):raise ValueError('Runtime image identity is not immutable.')
            labels=image.get('Config',{}).get('Labels') or {}
            if labels.get('org.jarvis.repository-runtime')!='1':raise ValueError('Image lacks the reviewed Jarvis runtime identity.')
            row={'available':True,'backend':'docker-linux','image_id':image['Id'],
                 'runner_hash':hashlib.sha256(Path(__file__).with_name('repo_runtime_runner.py').read_bytes()).hexdigest(),
                 'network':'disabled','host_code_execution':False}
        except (ValueError,KeyError,TypeError) as error:
            row={'available':False,'backend':'docker-linux','reason':str(error)[:700],'host_code_execution':False}
        self.cached=row;self.cached_at=time.monotonic();return row

    def run(self,root,request,cancelled=lambda:False,timeout=15):
        status=self.status(refresh=True)
        if not status['available']:raise ValueError('Repository execution disabled: '+status['reason'])
        if not isinstance(request,dict) or len(json.dumps(request).encode())>16000:raise ValueError('Skill request exceeds budget.')
        root=Path(root).absolute();runner=Path(__file__).with_name('repo_runtime_runner.py').absolute()
        if any(linked(p) for p in [root,*root.parents]):raise ValueError('Container source must not be linked.')
        if any(',' in str(p) for p in (root,runner)):raise ValueError('Container mount paths cannot contain commas.')
        name='jarvis-skill-'+uuid4().hex
        queued=time.monotonic()
        while not self.lock.acquire(timeout=.05):
            if cancelled():raise ValueError('Skill execution cancelled in queue.')
            if time.monotonic()-queued>30:raise ValueError('Skill execution queue timed out.')
        try:
            if cancelled():raise ValueError('Skill cancelled before isolated execution.')
            args=['run','-i','--pull','never','--name',name,'--label','org.jarvis.skill-owned=1',
                '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--pids-limit','16','--memory','256m','--memory-swap','256m','--cpus','0.5',
                '--user','65534:65534','--ulimit','nofile=64:64','--log-driver','none',
                '--tmpfs','/work:rw,nosuid,nodev,noexec,size=16m,uid=65534,gid=65534,mode=700',
                '--workdir','/work','--mount','type=bind,src='+str(root)+',dst=/source,readonly',
                '--mount','type=bind,src='+str(runner)+',dst=/runner.py,readonly',
                '--env','PYTHONDONTWRITEBYTECODE=1','--env','PYTHONHASHSEED=0']
            # Override Docker client proxy injection before process creation, then
            # the trusted runner clears its Python environment before any import.
            for key in ('HTTP_PROXY','HTTPS_PROXY','FTP_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','ftp_proxy','all_proxy','no_proxy'):
                args.extend(['--env',key+'='])
            args.extend(['--entrypoint','/usr/local/bin/python',status['image_id'],'-I','-B','/runner.py'])
            raw=self.cli(args,cancelled,timeout,json.dumps(request).encode())
            result=json.loads(raw)
            if not isinstance(result,dict) or set(result)-{'ok','value','error_type','error'}:raise ValueError('Invalid isolated skill result protocol.')
            if result.get('ok') is not True:raise ValueError('Isolated skill failed: '+str(result.get('error_type'))+': '+str(result.get('error')))
            return result['value'],status['image_id']
        finally:
            # Only this unpredictable, Jarvis-owned container name is removed.
            # Timeout/cancellation never retries the invocation or stops user containers.
            try:self.cli(['rm','--force',name],timeout=8)
            except ValueError:pass
            self.lock.release()

