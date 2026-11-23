"""Public asset research through Jarvis's existing tool registry and browser.

No second browser, arbitrary page script, credential access or binary download.
Every source record is bound to a fresh observed search URL and tool call IDs.
"""
import base64
import json
from urllib.parse import parse_qs,urlencode,urlsplit,urlunsplit
from .literature import public_query

PROVIDERS=frozenset({'github.com','sketchfab.com','grabcad.com','polyhaven.com','nasa3d.arc.nasa.gov'})


def public_asset_link(value):
    if not isinstance(value,str) or len(value)>8000:return None
    try:
        p=urlsplit(value)
        host=(p.hostname or '').lower().removeprefix('www.')
        params=parse_qs(p.query)
        if host=='bing.com' and p.path.startswith('/ck/'):
            encoded=params.get('u',[''])[0]
            if not encoded.startswith('a1'):return None
            encoded=encoded[2:];value=base64.urlsafe_b64decode(encoded+'='*((-len(encoded))%4)).decode('utf-8')
            p=urlsplit(value)
        elif host in ('google.com','google.co.in') and p.path=='/url':
            value=params.get('q',params.get('url',['']))[0];p=urlsplit(value)
        host=(p.hostname or '').lower().removeprefix('www.')
        if (p.scheme!='https' or host not in PROVIDERS or p.port not in (None,443) or p.username or p.password
                or any(ord(c)<32 for c in value) or len(value)>2048):return None
        # Provider object/repository identity lives in its path. Do not retain
        # session tokens, tracking queries or page fragments as source identity.
        return urlunsplit(('https',p.netloc,p.path,'',''))
    except (ValueError,UnicodeError):return None


def research(actions,query,cancelled=lambda:False,*,registry_factory=None):
    query=public_query(query)
    if not 4<=len(query)<=240:raise ValueError('bounded public object query required')
    if registry_factory is None:
        from ...tools import ToolRegistry
        registry_factory=ToolRegistry
    registry=registry_factory(actions)
    url='https://www.bing.com/search?'+urlencode({'q':query})
    observations=[];opened=None
    try:
        opened=registry.execute({'action':'web_open','value':url,
            'content':json.dumps({'profile':'personal','new_tab':True})},cancelled)
        header=json.loads(opened.evidence.splitlines()[0])
        observations.append({'call_id':opened.call_id,'action':'web_open','ok':header.get('ok') is True,
                             'executed':header.get('executed') is True})
        # A navigation may have happened even if its reply was lost. Read-only
        # reconciliation is allowed; never repeat an uncertain open/click here.
        read=registry.execute({'action':'web_read','value':'links'},cancelled)
        page=json.loads(read.evidence)
        if page.get('kind')!='browser_links' or page.get('content_is_untrusted') is not True:
            raise ValueError('browser link result schema mismatch')
        p=urlsplit(page['url']);actual=parse_qs(p.query).get('q',[])
        if p.scheme!='https' or p.hostname not in ('www.bing.com','bing.com') or p.path!='/search' or actual!=[query]:
            raise ValueError('observed research page does not match requested public query')
        rows=page.get('links')
        if not isinstance(rows,list) or len(rows)>200:raise ValueError('research links exceed contract')
        candidates=[];seen=set()
        for row in rows:
            if not isinstance(row,dict):raise ValueError('malformed browser link record')
            candidate=public_asset_link(row.get('url'))
            if candidate and candidate not in seen:
                candidates.append({'url':candidate,'label':str(row.get('text',''))[:240],
                    'provider':urlsplit(candidate).hostname.removeprefix('www.'),'identity_verified':False,'geometry_acquired':False})
                seen.add(candidate)
        observations.append({'call_id':read.call_id,'action':'web_read','ok':True})
        return {'status':'OBSERVED','query':query,'source_url':page['url'],'candidates':candidates,
            'observations':observations,'content_is_untrusted':True,
            'limits':'Browser search links only; rights, actual availability, identity and geometry require subsequent checks.'}
    except Exception as error:
        import traceback
        from pathlib import Path
        root=Path(__file__).resolve().parents[3]
        owned=[]
        for frame in traceback.extract_tb(error.__traceback__):
            try:owned.append(Path(frame.filename).resolve().relative_to(root).as_posix()+':'+str(frame.lineno))
            except ValueError:pass
        return {'status':'BLOCKED_BROWSER_RESEARCH','query':query,'source_url':url,'candidates':[],
            'observations':observations,'failure_type':type(error).__name__,
            'owned_failure_locations':owned[-8:],
            'reason':'Existing browser did not provide a matching source-bound link observation; use an eligible official API or retain this blocker.',
            'content_is_untrusted':True}
