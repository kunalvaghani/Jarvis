"""Bounded reviewed Docker jobs; no host notebook fallback."""
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4
from .repo_sandbox import RepositorySandbox


def run(operation,args,source=None,cancelled=lambda:False):
    runtime=RepositorySandbox('jarvis-utility-runtime:1')
    # This distinct image deliberately permits child kernels; validate its own identity.
    image=json.loads(runtime.cli(['image','inspect',runtime.image]))[0]
    if image.get('Config',{}).get('Labels',{}).get('org.jarvis.utility-runtime')!='1' or image.get('Os')!='linux' or image.get('Architecture')!='amd64':raise ValueError('Reviewed utility Linux image is unavailable.')
    name='jarvis-utility-'+uuid4().hex;runner=Path(__file__).with_name('utility_container_runner.py').absolute()
    command=['run','-i','--pull','never','--name',name,'--label','org.jarvis.utility-owned=1','--network','none' if operation=='notebook' or args.get('_fixture') else 'bridge',
        '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--memory-swap','512m','--pids-limit','64','--cpus','.5',
        '--tmpfs','/work:rw,nosuid,nodev,size=128m,uid=65534,gid=65534,mode=700',
        '--mount','type=bind,src='+str(runner)+',dst=/runner.py,readonly']
    if source:
        path=Path(source).resolve(strict=True)
        if ',' in str(path):raise ValueError('Unsupported input mount path.')
        command.extend(['--mount','type=bind,src='+str(path)+',dst=/input.ipynb,readonly'])
    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy'):command.extend(['--env',key+'='])
    command.extend(['--entrypoint','/usr/local/bin/python',image['Id'],'-I','-B','/runner.py'])
    try:
        raw=runtime.cli(command,cancelled,45,json.dumps({'operation':operation,**args}).encode())
        try:result=json.loads(raw)
        except ValueError as error:raise ValueError('Container utility protocol is invalid; output retained only locally, no automatic replay.') from error
        if result.get('ok') is not True:raise ValueError('Isolated utility failed: '+str(result.get('error_type'))+': '+str(result.get('error')))
        return result['value']
    finally:
        try:runtime.cli(['rm','--force',name])
        except ValueError:pass
