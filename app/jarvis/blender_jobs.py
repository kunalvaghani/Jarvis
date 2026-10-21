"""Bounded read-only monitoring of accepted Blender jobs; never replays scene actions."""
import json
from pathlib import Path
import re
import threading
import time
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

_LOCK=threading.Lock()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class BlenderJobs:
    def __init__(self,actions):
        self.actions=actions
        self.lock=threading.RLock()
        self.stop=threading.Event()
        self.jobs={}
        self.thread=None
        self.next_start=0
        self.path=Path(actions.base)/'.jarvis-runtime/blender/jobs.json'
        # Preserve receipts across host restart, without resuming an action or polling a new scope.
        try:
            saved=json.loads(self.path.read_text(encoding='utf-8'))
            for row in saved[-256:] if isinstance(saved,list) else []:
                if (isinstance(row,dict) and re.fullmatch('[0-9a-f]{32}',str(row.get('job_id','')))
                        and re.fullmatch('[0-9a-f]{32}',str(row.get('scope_id','')))):
                    if row.get('status') in {'queued','running'}:row=dict(row,status='interrupted_inspect_receipt')
                    self.jobs[row['job_id']]=row
        except (OSError,ValueError):pass

    def _save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(list(self.jobs.values()),indent=2),encoding='utf-8')
        temporary.replace(self.path)

    def submit(self,scope,job_id):
        from .mcp_bridge import configurations
        args=configurations(self.actions.base).get('blender',{}).get('args',[])
        if '--bridge-config' not in args:raise ValueError('Explicit Blender scope file required.')
        config=Path(args[args.index('--bridge-config')+1]).resolve(strict=True)
        if not re.fullmatch('[0-9a-f]{32}',scope) or not re.fullmatch('[0-9a-f]{32}',job_id):
            raise ValueError('Invalid Blender receipt identifiers.')
        with self.lock:
            active=[r for r in self.jobs.values() if r['status'] in {'queued','running'}]
            if len(active)>=32:
                raise ValueError('Monitor full; job already accepted. Poll its receipt; do not repeat.')
            if len(self.jobs)>=256:
                old=next((k for k,v in self.jobs.items() if v.get('status') not in {'queued','running'}),None)
                if old is not None:self.jobs.pop(old)
            self.jobs[job_id]={'job_id':job_id,'scope_id':scope,'config':str(config),'status':'queued','created':time.time(),'failures':0,'next_poll':0}
            self._save()
        self.repair()

    def _read(self,row):
        config=json.loads(Path(row['config']).read_text(encoding='utf-8'))
        if (config.get('host')!='127.0.0.1' or type(config.get('port')) is not int
                or not 1024<=config['port']<=65535 or config.get('scope_id')!=row['scope_id']
                or not isinstance(config.get('token'),str) or len(config['token'])<32):
            raise ValueError('Blender scope changed; monitor stopped without replay.')
        request=Request(f"http://127.0.0.1:{config['port']}/v1/jobs/{row['job_id']}",
                        headers={'Authorization':'Bearer '+config['token']})
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=2) as response:
            raw=response.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:raise ValueError('Job observation too large.')
        data=json.loads(raw)
        if not data.get('ok') or data.get('scope_id')!=row['scope_id']:raise ValueError('Job scope unavailable.')
        job=data['job']
        status=job.get('status')
        if status not in {'queued','running','done','error'}:raise ValueError('Unknown Blender job state.')
        result=job.get('result')
        data=result.get('data') if isinstance(result,dict) else None
        if status=='done' and isinstance(data,dict) and data.get('partial'):status='partial'
        return status

    def _run(self):
        while not self.stop.wait(.25):
            with self.lock:
                pending=[dict(r) for r in self.jobs.values() if r['status'] in {'queued','running'}]
            if not pending:return  # No polling or network access while idle.
            for row in pending:
                if self.stop.is_set() or self._closed():return
                if time.time()<row['next_poll']:continue
                try:
                    if time.time()-row['created']>1800:raise ValueError('Monitoring window ended; inspect original receipt.')
                    status=self._read(row)
                    failures=0
                except Exception:
                    failures=row['failures']+1
                    status='unready' if failures>=5 else row['status']
                with self.lock:
                    current=self.jobs.get(row['job_id'])
                    if current is None:continue
                    previous=current['status']
                    current.update(status=status,failures=failures,next_poll=time.time()+min(30,2**failures if failures else 1))
                    self._save()
                if previous!=status:
                    self.actions.report('state','Blender · '+status+' · '+row['job_id']+
                        (' · inspect receipt; never repeat an uncertain action' if status in {'unready','error','partial'} else ''))

    def _closed(self):
        return bool(getattr(getattr(self.actions,'closed',None),'is_set',lambda:False)())

    def healthy(self):
        with self.lock:
            active=any(r['status'] in {'queued','running'} for r in self.jobs.values())
        return not active or (self.thread is not None and self.thread.is_alive())

    def repair(self):
        # Only restart observations of known receipts, never Blender or a mutation.
        with self.lock:
            if self.stop.is_set() or self._closed():return False
            if self.thread is not None and self.thread.is_alive():return True
            if time.monotonic()<self.next_start:return None
            self.next_start=time.monotonic()+2
            self.thread=threading.Thread(target=self._run,name='jarvis-blender-jobs',daemon=True)
            self.thread.start()
            return True

    def close(self):
        self.stop.set()
        if self.thread is not None:self.thread.join(3)


def owner(actions):
    with _LOCK:
        current=getattr(actions,'_blender_jobs',None)
        if current is None:current=actions._blender_jobs=BlenderJobs(actions)
        return current
