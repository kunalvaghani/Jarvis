"""Process-shared, priority ordered inference leases; no external action retries.

The GPU belongs to the active inference turn, not permanently to a task/model.
Whisper and other applications are outside this coordinator and are reserved for.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import urlsplit
from uuid import uuid4

BASE = Path(__file__).resolve().parents[1]
PRIORITIES = {'planner':100, 'execution':90, 'coding':90, 'question':80,
              'cleanup':60, 'context':40, 'research':30, 'background':10}
HELPERS = {'cleanup', 'context', 'background'}
DEFAULTS = {'enabled':False, 'helper_gpu':False, 'primary_layers':12, 'codex_layers':9,
            'speech_reserve_mb':1024, 'reserve_mb':512, 'wait_seconds':120, 'warm_seconds':30}
_threads = threading.RLock()


def replace_state(temporary,path):
    # Windows observers/antivirus can briefly hold a read handle without delete
    # sharing. Retry only this atomic local promotion, never inference/actions.
    deadline=time.monotonic()+.5
    while True:
        try:
            os.replace(temporary,path);return
        except PermissionError:
            if os.name!='nt' or time.monotonic()>=deadline:raise
            time.sleep(.01)


def settings(options=None):
    if options is not None and not isinstance(options,dict):
        raise ValueError('gpu_scheduler must be an object.')
    value={**DEFAULTS, **(options or {})}
    for name in ('enabled','helper_gpu'):
        if type(value[name]) is not bool:raise ValueError('GPU '+name+' must be boolean.')
    for name,low,high in [('primary_layers',0,33),('codex_layers',0,33),
                          ('speech_reserve_mb',0,8192),('reserve_mb',128,8192),('wait_seconds',1,300),('warm_seconds',0,120)]:
        if type(value[name]) is not int or not low<=value[name]<=high:
            raise ValueError('Invalid GPU setting: '+name)
    return value


def configured():
    data=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    return settings(data.get('gpu_scheduler'))


def memory():
    """Read available physical VRAM only; unknown hardware means CPU admission."""
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=memory.total,memory.used',
            '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
        # This policy targets the measured single GPU. Never guess multi-GPU placement.
        rows=result.stdout.strip().splitlines()
        if len(rows)!=1:return None
        total,used=(int(x.strip()) for x in rows[0].split(','))
        return {'total_mb':total,'used_mb':used}
    except (OSError,ValueError,subprocess.SubprocessError):return None


def allocation(model,context,policy,hardware):
    if not hardware or type(context) is not int or context<1:return 0
    budget=hardware['total_mb']-max(hardware['used_mb'],policy['speech_reserve_mb'])-policy['reserve_mb']
    if model in {'qwen3.5:0.8b','qwen2.5:0.5b'}:
        return -1 if policy['helper_gpu'] and budget>=1024 else 0
    if model not in {'qwen3.5:9b','jarvis-codex-qwen3.5:9b','jarvis-claude-qwen3.5:9b'}:
        return 0  # Unknown model footprint cannot be guessed.
    # Conservative envelope above measured Q4_K_M residency on this 4 GB machine.
    ceiling=policy['codex_layers'] if model.startswith('jarvis-') else policy['primary_layers']
    return next((n for n in range(ceiling,0,-1)
                 if 600+145*n+.016*context<=budget),0)


def alive(row):
    import psutil
    try:
        p=psutil.Process(row['pid'])
        return p.is_running() and abs(p.create_time()-row['birth'])<.01
    except psutil.AccessDenied:return True  # Unknown owner liveness cannot grant another slot.
    except (psutil.Error,KeyError,TypeError):return False


def status(root=None):
    """Nonblocking read for the operational heartbeat, never prompt/task content."""
    path=Path(root or BASE/'.jarvis-runtime/gpu')/'state.json'
    try:
        if not path.exists():return {'status':'idle','pending':0}
        if path.stat().st_size>200000:return {'status':'unavailable'}
        value=json.loads(path.read_text())
        active=value.get('active');active=active if active and alive(active) else None
        return {'status':'busy' if active else 'idle',
            'active_role':active.get('role') if active else None,
            'active_model':active.get('model') if active else None,
            'pending':len(value.get('pending',[])),
            'warm_model':value.get('resident',{}).get('model') if value.get('resident',{} ) and value['resident'].get('expires_at',0)>time.time() else None}
    except (OSError,ValueError,TypeError,AttributeError):return {'status':'unavailable'}


class Registry:
    def __init__(self,root=None,live=alive):
        self.root=Path(root or BASE/'.jarvis-runtime/gpu');self.live=live
        self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'state.json'

    @contextmanager
    def state(self):
        # Short OS lock protects cross-process admission. Never hold it during inference.
        with _threads, (self.root/'state.lock').open('a+b') as lock:
            lock.seek(0,2)
            if not lock.tell():lock.write(b'0');lock.flush()
            deadline=time.monotonic()+2
            while True:
                try:
                    lock.seek(0)
                    if os.name=='nt':
                        import msvcrt
                        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                    else:
                        import fcntl
                        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic()>=deadline:raise ValueError('GPU admission lock unavailable; no inference issued.')
                    time.sleep(.01)
            try:
                value=json.loads(self.path.read_text()) if self.path.exists() else {'active':None,'pending':[]}
                if not isinstance(value,dict) or not isinstance(value.get('pending'),list):
                    raise ValueError('Invalid GPU lease state; no inference issued.')
                if value.get('active') and not self.live(value['active']):value['active']=None
                value['pending']=[r for r in value['pending'] if self.live(r)]
                if value.get('resident') and value['resident'].get('expires_at',0)<=time.time():value['resident']=None
                yield value
                temp=self.path.with_suffix('.tmp')
                temp.write_text(json.dumps(value)+'\n');replace_state(temp,self.path)
            finally:
                lock.seek(0)
                if os.name=='nt':msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(lock,fcntl.LOCK_UN)

    def event(self,**value):
        # Metadata only, never input/output, screenshots, URLs or tool arguments.
        try:
            with (self.root/'events.jsonl').open('a') as out:
                out.write(json.dumps({'at':time.time(),**value})+'\n')
        except OSError:pass


class Lease:
    def __init__(self,role,model,policy,registry=None,cancelled=lambda:False):
        import psutil
        if role not in PRIORITIES:raise ValueError('Unknown inference role.')
        self.role,self.model,self.policy=role,model,policy
        self.registry=registry or Registry();self.cancelled=cancelled;self.admitted=False
        self.row={'token':uuid4().hex,'pid':os.getpid(),'birth':psutil.Process().create_time(),
                  'role':role,'model':model,'priority':PRIORITIES[role],'queued_at':time.time()}

    def acquire(self):
        if self.role in HELPERS and not self.policy['helper_gpu']:return False
        started=time.monotonic()
        try:
            with self.registry.state() as state:
                # Tiny helper work can remain on CPU while foreground GPU work is queued.
                if self.role in HELPERS and (state['active'] or state['pending'] or state.get('resident')):return False
                state['pending'].append(self.row)
            while True:
                if self.cancelled():raise ValueError('GPU inference cancelled before dispatch.')
                with self.registry.state() as state:
                    if self.role in HELPERS and (state['active'] or any(r['priority']>self.row['priority'] for r in state['pending'])):
                        state['pending']=[r for r in state['pending'] if r['token']!=self.row['token']]
                        return False
                    winner=min(state['pending'],key=lambda r:(-r['priority'],r['queued_at'],r['token']),default=None)
                    if not state['active'] and winner and winner['token']==self.row['token']:
                        state['active']=self.row
                        state['pending']=[r for r in state['pending'] if r['token']!=self.row['token']]
                        self.admitted=True
                if self.admitted:
                    self.registry.event(stage='admitted',role=self.role,model=self.model,
                        wait_seconds=round(time.monotonic()-started,3));return True
                if time.monotonic()-started>=self.policy['wait_seconds']:
                    raise ValueError('GPU inference queue deadline reached; no request issued.')
                time.sleep(.05)
        except BaseException:
            self.close();raise

    def close(self):
        try:
            with self.registry.state() as state:
                state['pending']=[r for r in state['pending'] if r['token']!=self.row['token']]
                if state.get('active',{} ) and state['active']['token']==self.row['token']:state['active']=None
        finally:self.admitted=False


def install(client,role='question'):
    """Install once on a real requests session; caller-controlled phases are per client.

    Custom test transports remain unchanged. Production loopback requests use the
    same public HTTP API, with one admission and no automatic inference retry.
    """
    import requests
    if not isinstance(client,requests.sessions.Session) or getattr(client,'_jarvis_gpu_installed',False):return client
    original=client.post
    client.gpu_role=role;client._jarvis_gpu_installed=True
    def post(url,**kwargs):
        target=urlsplit(url);payload=kwargs.get('json')
        if (target.hostname not in {'127.0.0.1','localhost','::1'} or target.port!=11434
                or target.path not in {'/api/chat','/api/generate','/v1/responses','/v1/messages'}
                or not isinstance(payload,dict) or not payload.get('model')
                or payload.get('keep_alive')==0 and not any(payload.get(k) for k in ('messages','prompt','input'))):
            return original(url,**kwargs)
        policy=configured()
        if not policy['enabled']:return original(url,**kwargs)
        role=getattr(client,'gpu_role','question');model=payload['model']
        context=payload.get('options',{}).get('num_ctx',32768 if target.path.startswith('/v1/') else 4096)
        if type(context) is not int or not 1<=context<=262144:
            raise ValueError('Invalid inference context; no GPU slot or request issued.')
        if not target.path.startswith('/v1/') and model=='qwen3.5:9b':context=max(16384,context)
        wait=getattr(client,'gpu_wait_seconds',None)
        if wait is not None:
            if type(wait) not in (int,float) or not 1<=wait<=3600:raise ValueError('Invalid task GPU wait bound.')
            policy={**policy,'wait_seconds':wait}
        lease=Lease(role,model,policy,cancelled=getattr(client,'gpu_cancelled',lambda:False))
        admitted=lease.acquire()
        def loaded():
            observation=client.get('http://127.0.0.1:11434/api/ps',timeout=(2,3))
            try:
                observation.raise_for_status();return observation.json().get('models',[])
            finally:observation.close()
        hardware=memory() if admitted else None
        layers=0
        cached=None
        try:
            if admitted:
                with lease.registry.state() as state:previous=state.get('resident')
                if previous:
                    rows=loaded()
                    current=next((r for r in rows if r.get('name')==previous['model'] and
                        r.get('digest')==previous['digest'] and r.get('size_vram')==previous['size_vram']
                        and r.get('context_length')==previous['context']),None)
                    if current and model==previous['model'] and context==previous['context']:
                        if hardware:hardware={**hardware,'used_mb':max(0,hardware['used_mb']-int(current['size_vram']/1048576))}
                        cached=previous
                    elif current:
                        # One normal unload of the last identified Jarvis cache; no kill/replay.
                        unload=original('http://127.0.0.1:11434/api/generate',json={'model':previous['model'],'keep_alive':0},timeout=(2,3))
                        unload.raise_for_status();unload.close()
                        lease.registry.event(stage='handoff',role=role,model=model,previous_model=previous['model'])
                        hardware=memory()
                    with lease.registry.state() as state:state['resident']=None
                layers=allocation(model,context,policy,hardware)
                if cached:layers=min(layers,cached['num_gpu'])  # Never reload a healthy cache just to increase layers.
            if target.path.startswith('/v1/'):
                if model not in {'jarvis-codex-qwen3.5:9b','jarvis-claude-qwen3.5:9b'}:
                    raise ValueError('Priority-managed coding requires the owned Jarvis model alias; the shared base model was not changed.')
                # OpenAI-compatible routes use Modelfile parameters, not options.num_gpu.
                if admitted and layers<policy['codex_layers']:
                    raise ValueError('Insufficient reserved VRAM for local Codex; inference was not issued. Free GPU memory or configure CPU coding.')
            else:
                keep=policy['warm_seconds'] if admitted and layers>0 and model=='qwen3.5:9b' else 0
                kwargs['json']={**payload,'keep_alive':keep,'options':{**payload.get('options',{}),'num_ctx':context,'num_gpu':layers}}
            lease.registry.event(stage='dispatch',role=role,model=model,num_gpu=layers,
                context_tokens=context,gpu_slot=admitted)
            response=original(url,**kwargs)
            response.jarvis_gpu={'role':role,'num_gpu':policy['codex_layers'] if target.path.startswith('/v1/') else layers,
                                 'context_tokens':context,'gpu_slot':admitted}
        except BaseException:
            if admitted:lease.close()
            raise
        if not admitted:return response
        closed=False
        def release():
            nonlocal closed
            if closed:return
            closed=True
            try:
                row=None
                if response.ok and model in {'qwen3.5:9b','jarvis-codex-qwen3.5:9b','jarvis-claude-qwen3.5:9b'}:
                    try:
                        row=next((r for r in loaded() if r.get('name')==model and r.get('context_length')==context and r.get('digest') and isinstance(r.get('size_vram'),int)),None)
                    except (requests.RequestException,KeyError,ValueError):
                        lease.registry.event(stage='cache_identity_unconfirmed',role=role,model=model)
                if target.path.startswith('/v1/') and row:
                    try:
                        timer=original('http://127.0.0.1:11434/api/generate',
                            json={'model':model,'keep_alive':policy['warm_seconds'] if policy['codex_layers']>0 else 0},timeout=(2,3))
                        try:timer.raise_for_status()
                        finally:timer.close()
                    except requests.RequestException:
                        lease.registry.event(stage='cache_duration_unconfirmed',role=role,model=model)
                if row and layers>0 and policy['warm_seconds']:
                    try:
                        with lease.registry.state() as state:
                            state['resident']={'model':model,'digest':row['digest'],'context':context,
                                'size_vram':row['size_vram'],'num_gpu':policy['codex_layers'] if target.path.startswith('/v1/') else layers,
                                'expires_at':time.time()+policy['warm_seconds']}
                    except (requests.RequestException,KeyError,ValueError):
                        lease.registry.event(stage='cache_identity_unconfirmed',role=role,model=model)
            finally:
                lease.registry.event(stage='released',role=role,model=model)
                lease.close()
        if not kwargs.get('stream'):
            release();return response
        close=response.close
        def close_and_release():
            try:close()
            finally:release()
        response.close=close_and_release
        return response
    client.post=post
    return client
