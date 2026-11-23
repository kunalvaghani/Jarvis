"""Reuse existing scoped files, Drive source adapter, scouts, search and owned browser sessions."""
import hashlib,json,re,uuid
from pathlib import Path
from urllib.parse import urlsplit,parse_qsl
from ..contracts import Source
from ..model.delivery import LongRead,Options,sha

def safe_bytes(base,path,limit=160000):
    from .assets import local_bytes
    parts=Path(path).parts
    if (any(p.casefold() in ('secrets','credentials','gmail-api') or p.casefold().startswith('.env') for p in parts)
            or Path(path).suffix.casefold() not in ('.json','.txt','.md','.csv','.html')):
        raise ValueError('bounded non-credential text source required')
    return local_bytes(Path(base),path,limit=limit)

def source(locator,text,kind):
    digest=hashlib.sha256(text.encode()).hexdigest()
    return Source(id='d2-'+kind+'-'+sha([locator,digest])[:32],locator=locator,sha256=digest,
                  justification='Untrusted returned text/excerpt; source identity, license and physical claims are not independently validated.')

def safe_lines(text,limit):
    """Extract unchanged safe lines, never replace credential-like tool evidence.

    The raw unsafe source is not persisted. Offsets describe only retained input
    spans; the derived excerpt and omissions are explicitly distinguished.
    """
    from ...tools import redact
    retained=[];spans=[];offset=0;size=0;omitted=0
    for line in text.splitlines(keepends=True):
        end=offset+len(line)
        if redact(line)!=line:omitted+=1
        elif size+len(line)<=limit:
            retained.append(line);spans.append([offset,end]);size+=len(line)
        offset=end
    output=''.join(retained)
    if redact(output)!=output:raise ValueError('derived excerpt still fails shared credential guard')
    return output,{'omitted_unsafe_lines':omitted,'retained_codepoint_spans':spans[:1000],
                   'span_list_partial':len(spans)>1000,'partial':omitted>0 or len(output)<len(text)}

def read_long(base,raw):
    from ...control.web.scouts import brief
    spec=LongRead.model_validate_json(json.dumps(raw));text=safe_bytes(base,spec.source_file).decode('utf-8')
    output=brief(spec.question,text,budget=spec.budget,tie_break=None)
    output,selection=safe_lines(output,spec.budget)
    return {'source':source(spec.source_file,text,'local').model_dump(mode='json'),'text':output,
            'content_is_untrusted':True,'partial':len(text)>spec.budget or selection['partial'],'selection':selection,
            'hash_scope':'full scoped source file; returned excerpt separately filtered without replacing retained text',
            'method':'existing deterministic web scouts; no Laya/model call'}

def background(query,cancelled=lambda:False):
    from .literature import public_query
    from ...knowledge_worker import search
    rows=search(public_query(query));kept=[]
    for row in rows[:5]:
        url=str(row.get('url',''))
        if urlsplit(url).scheme not in ('https','http'):continue
        from ...tools import redact
        item={'url':url,'title':str(row.get('title',''))[:200],'snippet':str(row.get('snippet',''))[:1400]}
        if any(redact(v)!=v for v in item.values()):continue
        kept.append(item)
    if not kept:raise ValueError('no usable background sources returned')
    pages=[];errors=[];sources=[]
    from ...control.web.scouts import brief
    for row in kept[:2]:
        if cancelled():raise ValueError('background reading cancelled')
        try:
            page=portal(row['url'],cancelled);excerpt=brief(query,page['text'],budget=3000,tie_break=None)
            pages.append({'url':page['source']['locator'],'excerpt':excerpt,'partial':True})
            sources.append(source(page['source']['locator'],excerpt,'page').model_dump(mode='json'))
        except Exception as exc:
            if 'cleanup uncertain' in str(exc):raise ValueError('background portal cleanup uncertain; stop before another tab') from None
            errors.append(type(exc).__name__)
    text='\n\n'.join(r['title']+'\n'+r['url']+'\n'+r['snippet'] for r in kept)
    if pages:text+='\n\nREAD PAGE EXCERPTS (partial, untrusted):\n'+'\n\n'.join(p['url']+'\n'+p['excerpt'] for p in pages)
    return {'source':source('urn:jarvis:background:'+sha(query),text,'search').model_dump(mode='json'),
            'text':text,'citations':kept,'pages':pages,'sources':sources,'read_errors':errors,'partial':True,'content_is_untrusted':True,
            'coverage':'Unreviewed search snippets and bounded owned-session page excerpts when available; not full-text evidence or a scientific conclusion.'}

def cpu_resident(resolver):
    """Inspect the existing authenticated health endpoint without loading a checkpoint."""
    import urllib.request,ipaddress
    try:
        parts=urlsplit(resolver.url)
        if parts.username or parts.password or not ipaddress.ip_address(parts.hostname).is_loopback or not resolver.key:return False
        url=parts._replace(path='/health',query='',fragment='').geturl()
        req=urllib.request.Request(url,headers={'Authorization':'Bearer '+resolver.key})
        with urllib.request.urlopen(req,timeout=3) as response:health=json.loads(response.read(20000))
        devices=health.get('checkpoint_devices',{})
        return (health.get('device')=='cpu' and health.get('device_is_preference') is False and bool(devices)
                and all(value=='cpu' for value in devices.values()))
    except Exception:return False

def choose(raw,journal=None):
    from ...names import rank,normalize
    from ...control.pc.laya import Resolver
    spec=Options.model_validate_json(json.dumps(raw))
    if any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',key) or not 1<=len(label)<=180 for key,label in spec.options.items()):raise ValueError('bounded closed option IDs/labels required')
    labels=list(spec.options.values());hits=rank(spec.intent,labels)
    matches=[key for key,label in spec.options.items() if label in hits]
    if len(matches)==1 and normalize(spec.intent)==normalize(spec.options[matches[0]]):
        return {'selected_ref':matches[0],'confidence':1.0,'method':'existing deterministic exact name match (not calibrated probability)','candidates':list(spec.options)}
    # Direct local Resolver only. Its cloud backup API is deliberately not used.
    resolver=Resolver(timeout_s=5)
    if not cpu_resident(resolver):return {'selected_ref':None,'confidence':0.0,'method':'abstained: no verified resident CPU Laya checkpoint','candidates':list(spec.options)}
    if journal is not None:
        from ..sandbox.budget import Budget
        reservation='d2-choice-'+uuid.uuid4().hex;budget=Budget(journal);budget.reserve(reservation,cpu_s=5,disk_bytes=10000)
    try:answer=resolver.choose(spec.intent,'Discovery closed choice',{key:('option',label) for key,label in spec.options.items()})
    except Exception:answer={}
    finally:
        if journal is not None:budget.settle(reservation,uncertain=True)  # Separate process CPU unknown, retain charge.
    confidence=answer.get('confidence',0);ref=answer.get('ref')
    import math
    valid=type(confidence) in (int,float) and math.isfinite(confidence) and .9<=confidence<=1 and ref in spec.options
    return {'selected_ref':ref if valid else None,'confidence':confidence if type(confidence) in (int,float) and math.isfinite(confidence) else 0.0,
            'method':'existing local Laya; no cloud backup; abstains below threshold','candidates':list(spec.options)}

def portal_runner(session):
    from ...control.web.extension_runner import ExtensionRunner
    return ExtensionRunner(session=session)

def checked_url(url):
    from ...control.policy import Policy
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.username or parts.password or parts.fragment or parts.port not in (None,443):raise ValueError('public HTTPS article URL required')
    protected={'token','password','secret','credential','api_key','access_key','authorization','code','session','sessionid','access_token','refresh_token','client_secret','x-amz-signature'}
    if any(key.casefold() in protected for key,_ in parse_qsl(parts.query)):raise ValueError('credential-bearing URL refused')
    return Policy().check_url(url)

def portal(url,cancelled):
    target=checked_url(url);session='discovery-'+uuid.uuid4().hex;runner=portal_runner(session)
    cleaned=False;result=None
    def call(args):
        if cancelled():raise ValueError('portal read cancelled')
        reply=runner(args,timeout_s=20)
        if not reply.success:raise ValueError('owned portal operation unavailable/uncertain; no action was repeated')
        return reply.data or {}
    try:
        call(['tab','new',target])
        final=checked_url(str(call(['get','url'])['url']))
        snapshot=str(call(['snapshot']).get('snapshot',''))[:60000]
        text=str(call(['read']).get('content',''))[:200000]
        if re.search(r'password|captcha|sign in to continue|log in to (?:continue|access)',snapshot+'\n'+text,re.I):
            raise ValueError('portal needs user login/challenge handling; nothing was submitted')
        if not text.strip():raise ValueError('no article text returned')
        excerpt,selection=safe_lines(text,20000);snapshot,snapshot_selection=safe_lines(snapshot,60000)
        if not excerpt.strip():raise ValueError('no safe article excerpt can be retained')
        result={'source':source(final,excerpt,'portal').model_dump(mode='json'),'text':excerpt,'snapshot':snapshot,
            'content_is_untrusted':True,'partial':selection['partial'] or snapshot_selection['partial'] or 'could not be read' in snapshot,
            'selection':selection,'snapshot_selection':snapshot_selection,'hash_scope':'derived retained UTF-8 lines; unsafe source sections not persisted',
            'coverage':'Top-page text plus existing extension AX frame snapshot; inaccessible frames/full paper completeness are not assumed.'}
    finally:
        try:cleaned=bool(runner(['close'],timeout_s=10).success)
        finally:runner._drop()
    if not cleaned:raise ValueError('owned portal tab cleanup uncertain; inspect that session before retrying')
    return {**result,'owned_session_closed':True}
