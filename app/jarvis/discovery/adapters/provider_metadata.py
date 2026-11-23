"""Bounded public provider reads, reservations and Sources in the existing Journal.

No authentication, binary model download, alternate database or implicit rights.
Failed requests consume the same per-project allowance across restarts.
"""
import hashlib
import io
import json
from datetime import datetime,timezone
from pathlib import Path
import re
import time
from urllib.parse import parse_qs,urlsplit,unquote
from .asset_transport import stream

HOSTS={'github':'api.github.com','sketchfab':'api.sketchfab.com','polyhaven':'api.polyhaven.com'}
CAP=1_000_000


def endpoint(provider,url):
    p=urlsplit(url)
    if (provider not in HOSTS or p.scheme!='https' or p.hostname!=HOSTS[provider] or p.port not in (None,443)
            or p.username or p.password or p.fragment or len(url)>3000 or any(ord(c)<32 for c in url)):
        raise ValueError('metadata endpoint is outside qualified public provider')
    if any(re.search(r'(?i)token|secret|password|credential|signature|authorization|api.?key',key) for key in parse_qs(p.query)):
        raise ValueError('authenticated URL is not a public metadata request')
    path=unquote(p.path)
    if any(part in ('.','..') for part in path.split('/')):raise ValueError('metadata path normalization refused')
    if provider=='github':
        repo=r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'
        allowed=path=='/search/repositories' or re.fullmatch(repo+r'(?:/(?:license|readme)|/commits/[^/]+|/git/trees/[^/]+)?',path)
        if not allowed and re.fullmatch(repo+r'/contents/.+',path):
            name=path.rsplit('/',1)[-1]
            allowed=bool(re.fullmatch(r'(?i)(?:LICENSE|COPYING|README)(?:\.(?:txt|md|json))?|(?:ASSET|MODEL)[_-]LICENSES?\.json|[^/]+\.license(?:\.txt)?',name))
        if not allowed:raise ValueError('GitHub metadata reader cannot acquire model binaries or arbitrary repository contents')
    elif provider=='sketchfab':
        if not re.fullmatch(r'/v3/(?:search|licenses|models/[a-f0-9]{32})',path):
            raise ValueError('unsupported Sketchfab metadata; downloads need an approved provider adapter')
    elif not re.fullmatch(r'/(?:assets|(?:info|files)/[A-Za-z0-9_-]{1,100})',path):
        raise ValueError('unsupported Poly Haven metadata operation')
    return p


def strict_json(raw):
    def reject(_):raise ValueError('nonfinite provider JSON refused')
    value=json.loads(raw,parse_constant=reject)
    if not isinstance(value,(dict,list)):raise ValueError('provider returned no metadata object')
    return value


class MetadataClient:
    def __init__(self,base,journal,project_id,*,cancelled=lambda:False,fetcher=None):
        if not isinstance(project_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',project_id):raise ValueError('persisted bounded project identity required')
        self.base,self.journal,self.project_id=Path(base).resolve(),journal,project_id
        self.cancelled,self.fetcher=cancelled,fetcher or stream
        with journal.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS discovery_metadata_attempts '
                '(project_id TEXT,slot INTEGER,endpoint_hash TEXT,provider TEXT,state TEXT,result_ref TEXT, '
                'failure_kind TEXT,PRIMARY KEY(project_id,slot))')

    def get(self,provider,url):
        endpoint(provider,url);key=hashlib.sha256(url.encode()).hexdigest()
        old=self.journal.rows('SELECT result_ref FROM discovery_metadata_attempts WHERE project_id=? '
            'AND endpoint_hash=? AND state=? ORDER BY slot DESC',(self.project_id,key,'complete'))
        if old:return old[0]['result_ref'],load(self.base,self.journal,old[0]['result_ref'])[1]
        if self.cancelled():raise ValueError('metadata read cancelled before admission')
        with self.journal.tx() as db:
            count=db.execute('SELECT COUNT(*) FROM discovery_metadata_attempts WHERE project_id=?',(self.project_id,)).fetchone()[0]
            if count>=12:raise ValueError('12-request public metadata project allowance exhausted; no reset on restart')
            db.execute('INSERT INTO discovery_metadata_attempts VALUES (?,?,?,?,?,?,?)',
                (self.project_id,count,key,provider,'claimed',None,None))
        from ..sandbox.budget import Budget
        budget=Budget(self.journal);budget_identity='metadata-'+hashlib.sha256((self.project_id+':'+str(count)).encode()).hexdigest()[:48]
        reserved=False;started=time.process_time()
        try:
            budget.reserve(budget_identity,cpu_s=1,disk_bytes=CAP);reserved=True
            sink=io.BytesIO()
            self.fetcher(url,{HOSTS[provider]},CAP,sink,cancelled=self.cancelled,seconds=30)
            raw=sink.getvalue()
            if not 4<=len(raw)<=CAP:raise ValueError('provider metadata byte contract failed')
            value=strict_json(raw);sha=hashlib.sha256(raw).hexdigest()
            root=self.base/'.jarvis-runtime/discovery/provider-cache'/provider
            from ...skill_memory import linked
            if any(linked(p) for p in (root,*root.parents)):raise ValueError('linked metadata cache refused')
            root.mkdir(parents=True,exist_ok=True);path=root/(sha+'.json')
            if path.exists():
                if linked(path) or path.read_bytes()!=raw:raise ValueError('immutable metadata cache differs')
            else:
                with path.open('xb') as file:file.write(raw)
            from ..memory import LabMemory
            from ..contracts import Source
            memory=LabMemory(self.journal);memory.migrate();identity=provider+'-metadata-'+sha
            if memory.get(identity) is None:
                memory.put(Source(id=identity,locator=url,sha256=sha,author=provider+' public metadata API',
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    justification='Actual captured public metadata; not an asset license, engineering identity or acquired model.'))
            record={'version':2,'provider':provider,'endpoint':url,'sha256':sha,'source_id':identity,
                'cached_json':path.relative_to(self.base).as_posix(),'content_is_untrusted':True,'budget_id':budget_identity}
            ref=self.journal.put(record,'Report')
            budget.settle(budget_identity,cpu_s=max(0,time.process_time()-started),disk_bytes=len(raw))
            with self.journal.tx() as db:
                db.execute('UPDATE discovery_metadata_attempts SET state=?,result_ref=? WHERE project_id=? AND slot=?',('complete',ref,self.project_id,count))
            return ref,value
        except BaseException as exc:
            with self.journal.tx() as db:
                db.execute('UPDATE discovery_metadata_attempts SET state=?,failure_kind=? WHERE project_id=? AND slot=?',('failed',type(exc).__name__,self.project_id,count))
            if reserved:budget.settle(budget_identity,uncertain=True)
            raise


def load(base,journal,ref):
    from ..acceptance import artifact
    from .assets import local_bytes
    from ..memory import LabMemory
    record=artifact(journal,ref);endpoint(record['provider'],record['endpoint'])
    prefix='.jarvis-runtime/discovery/provider-cache/'+record['provider']+'/'
    if not record['cached_json'].startswith(prefix):raise ValueError('provider cache escaped its owned source root')
    raw=local_bytes(Path(base),record['cached_json'],CAP)
    if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('provider snapshot changed')
    source=LabMemory(journal).get(record['source_id'])
    if source is None or source.sha256!=record['sha256'] or source.locator!=record['endpoint']:
        raise ValueError('provider snapshot source binding missing')
    if record.get('version')==2:
        budget=journal.rows('SELECT state,disk_bytes FROM discovery_budget WHERE id=?',(record['budget_id'],))
        if len(budget)!=1 or budget[0]['state']!='done' or budget[0]['disk_bytes']<len(raw):
            raise ValueError('provider snapshot lacks settled resource evidence')
    return record,strict_json(raw)
