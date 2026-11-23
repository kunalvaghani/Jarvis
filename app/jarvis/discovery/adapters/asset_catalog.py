"""Bounded public Sketchfab metadata. No login, binary download or viewer scraping.

Provider fields remain assertions, not verified engineering identity or rights.
Actual downloads require the official authenticated Download API separately.
"""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlsplit
import urllib.request
from .literature import public_query

ORIGIN='https://api.sketchfab.com'
CAP=1_000_000


class SameOrigin(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        p=urlsplit(newurl)
        if p.scheme!='https' or p.hostname!='api.sketchfab.com' or p.username or p.password or p.port not in (None,443):
            raise ValueError('public catalog redirect left the approved API origin')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch(url):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),SameOrigin())
    req=urllib.request.Request(url,headers={'User-Agent':'Jarvis-public-asset-metadata/1.0','Accept':'application/json'})
    with opener.open(req,timeout=20) as response:
        if response.headers.get('Content-Length') and int(response.headers['Content-Length'])>CAP:
            raise ValueError('catalog metadata exceeds 1 MB cap')
        raw=response.read(CAP+1)
    if len(raw)>CAP:raise ValueError('catalog metadata exceeds 1 MB cap')
    return raw


def parse(raw,mode='search'):
    data=json.loads(raw)
    if mode not in ('search','detail'):raise ValueError('unsupported metadata mode')
    if mode=='detail':data={'results':[data]}
    if not isinstance(data,dict) or not isinstance(data.get('results'),list):raise ValueError('invalid public model search response')
    rows=[]
    for r in data['results'][:8]:
        if not isinstance(r,dict) or not re.fullmatch('[a-f0-9]{32}',str(r.get('uid',''))):continue
        user=r.get('user') if isinstance(r.get('user'),dict) else {}
        license=r.get('license')
        if isinstance(license,dict):license={k:str(license.get(k,''))[:400] for k in ('uid','label','fullName','url','requirements')}
        elif isinstance(license,str):license={'provider_reference':license[:400]}
        else:license=None
        rows.append({'uid':r['uid'],'name':str(r.get('name',''))[:240],
            'description':str(r.get('description',''))[:6000],
            'description_partial':len(str(r.get('description','')))>6000,
            'viewer_url':str(r.get('viewerUrl',''))[:1000],'creator':str(user.get('username',''))[:160],
            'downloadable_declared':r.get('isDownloadable') is True,'license_declared':license,
            'geometry_acquired':False,'identity_verified':False,'engineering_suitability':'UNASSESSED'})
    return rows


def search(base,query,fetcher=None):
    query=public_query(query)
    if not 4<=len(query)<=240:raise ValueError('public catalog query must be 4..240 characters')
    endpoint=ORIGIN+'/v3/search?'+urlencode({'type':'models','downloadable':'true','count':8,'q':query})
    return _collect(base,endpoint,query,'search',fetcher)


def detail(base,uid,fetcher=None):
    if not isinstance(uid,str) or not re.fullmatch('[a-f0-9]{32}',uid):raise ValueError('public model UID required')
    return _collect(base,ORIGIN+'/v3/models/'+uid,'model:'+uid,'detail',fetcher)


def _collect(base,endpoint,query,mode,fetcher):
    raw=(fetcher or fetch)(endpoint)
    if not isinstance(raw,bytes) or len(raw)>CAP:raise ValueError('bounded raw metadata bytes required')
    rows=parse(raw,mode);sha=hashlib.sha256(raw).hexdigest()
    if mode=='detail' and (len(rows)!=1 or rows[0]['uid']!=query.removeprefix('model:')):
        raise ValueError('model metadata identity differs from requested UID')
    from ...skill_memory import linked
    directory=Path(base).resolve()/'.jarvis-runtime/discovery/public-catalogs/sketchfab'
    if any(linked(p) for p in (directory,*directory.parents)):raise ValueError('linked catalog cache refused')
    directory.mkdir(parents=True,exist_ok=True);path=directory/(sha+'.json')
    if path.exists():
        if linked(path) or path.read_bytes()!=raw:raise ValueError('catalog cache changed; no overwrite')
    else:
        with path.open('xb') as f:f.write(raw)
    return {'provider':'Sketchfab public Data API v3','query':query,'endpoint':endpoint,
        'lookup_mode':mode,
        'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
        'items':rows,'payload_sha256':sha,'cached_metadata':path.relative_to(Path(base).resolve()).as_posix(),
        'content_is_untrusted':True,'download_authentication_required':True,'binary_download_performed':False,
        'evidence_status':'INSUFFICIENT_EVIDENCE',
        'limits':'Published search metadata only; current license/identity, actual asset availability and engineering suitability require independent checks. No viewer assets, login or download restriction is bypassed.'}
