"""Observe official download links through the existing owned browser.

No cookies, tokens from storage, viewer-file extraction, guessed endpoints,
login automation, paid actions or unbounded browser downloads. A signed href
stays in memory for the bounded byte transport; evidence contains only its hash.
"""
import hashlib
import base64
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit


class DownloadUnavailable(ValueError):pass
class AuthenticationRequired(DownloadUnavailable):pass


def download_option(contexts):
    """Smallest unambiguous format row, never the whole modal's combined sizes."""
    if not isinstance(contexts,list) or len(contexts)>6:return None
    for row in contexts:
        if not isinstance(row,dict) or not isinstance(row.get('text'),str) or len(row['text'])>1600:return None
        text=row['text'];kinds=set(re.findall(r'(?i)(?<!\w)\.?(glb|gltf|blend|usdz)\b',text))
        kinds={value.lower() for value in kinds}
        sizes=re.findall(r'(?i)(?<![\d.])(\d+(?:\.\d+)?)\s*(GiB|MiB|KiB|GB|MB|KB)\b',text)
        if len(kinds)!=1 or len(sizes)!=1:continue
        kind=next(iter(kinds));value,unit=sizes[0]
        scale={'kb':1000,'mb':1000**2,'gb':1000**3,'kib':1024,'mib':1024**2,'gib':1024**3}[unit.lower()]
        size=round(float(value)*scale)
        if not 4<=size<=2_000_000_000:return None
        return {'format':kind,'declared_bytes':size,'supported':kind in ('glb','gltf')}
    return None


def resolve(actions,journal,asset,*,cancelled=lambda:False,registry_factory=None,source_title=None):
    if asset.provider!='sketchfab' or not re.fullmatch(r'sketchfab:[a-f0-9]{32}',asset.candidate_id):
        raise ValueError('only an admitted Sketchfab asset can use this resolver')
    uid=asset.candidate_id.split(':',1)[1]
    from ..acceptance import artifact
    from . import asset_resources
    permission_sha=artifact(journal,asset.evidence_ref).get('resource_grant_sha256') if hasattr(asset,'evidence_ref') else None
    if registry_factory is None:
        from ...tools import ToolRegistry
        registry_factory=ToolRegistry
    registry=registry_factory(actions);calls=[]
    def execute(step):
        if cancelled():raise DownloadUnavailable('download-link observation cancelled')
        result=registry.execute(step,cancelled);calls.append(result.call_id);return result
    # Never repeat an uncertain navigation: read the actual owned state once.
    try:execute({'action':'web_open','value':asset.source_url,'content':json.dumps({'profile':'personal','new_tab':True})})
    except Exception:
        if cancelled():raise DownloadUnavailable('download-link observation cancelled')
    route=actions.control().browser('personal')
    def page_matches():
        current=str(route.probe('url') or '');p=urlsplit(current)
        if (p.scheme!='https' or p.hostname not in ('sketchfab.com','www.sketchfab.com')
                or not p.path.endswith(uid)):raise DownloadUnavailable('selected official model page did not open; no download attempted')
        return current
    source=page_matches()
    screenshots=[]
    def capture(phase):
        if cancelled():return
        try:
            from ..sandbox.budget import Budget
            import uuid
            budget=asset_resources.budget(journal,permission_sha);identity='model-shot-'+uuid.uuid4().hex
            budget.reserve(identity,cpu_s=1,disk_bytes=3_000_000)
        except ValueError:return
        try:
            shot=route.probe('asset_screenshot',uid=uid)
            data=shot.get('data')
            if not isinstance(data,str) or len(data)>4_000_000:raise ValueError('screenshot byte cap exceeded')
            raw=base64.b64decode(data,validate=True)
            if len(raw)>3_000_000 or not raw.startswith(b'\xff\xd8\xff'):raise ValueError('invalid actual browser JPEG')
            sha=hashlib.sha256(raw).hexdigest();root=Path(actions.base)/'.jarvis-runtime/discovery/browser-observations'/uid
            from ...skill_memory import linked
            if any(linked(p) for p in (root,*root.parents)):raise ValueError('linked browser evidence root')
            root.mkdir(parents=True,exist_ok=True);path=root/(sha+'.jpg')
            if path.exists():
                if linked(path) or path.read_bytes()!=raw:raise ValueError('browser screenshot evidence differs')
            else:
                with path.open('xb') as file:file.write(raw)
            screenshots.append({'phase':phase,'relative_file':path.relative_to(actions.base).as_posix(),
                'sha256':sha,'source_url':source,'scope':'actual selected-model browser viewport; private, not physics proof'})
        except Exception:
            screenshots.append({'phase':phase,'status':'CAPTURE_UNAVAILABLE'})
        finally:
            # Browser-process CPU is unmeasured; retain the full admission rather
            # than label a guessed CPU number as an actual measurement.
            budget.settle(identity,uncertain=True)
    capture('official_model_page')
    from ...control.service import labels
    observed=None;controls={};reads=0
    def observe(after_opener=False):
        nonlocal observed,controls,reads
        for attempt in range(4):
            if after_opener:
                if cancelled():raise DownloadUnavailable('download-dialog observation cancelled')
                time.sleep(.5)
            # Full model descriptions can consume the page-view byte budget
            # before a login/download modal at the end of the AX tree appears.
            observed=execute({'action':'web_read','value':'interactive'});reads+=1
            page_matches();controls=labels(observed.evidence)
            modal=bool(re.search(r'(?im)^\s*(?:-\s*)?dialog\b|log\s*in\s+to\s+download|sign\s*in\s+to\s+download',observed.evidence))
            if modal or (not after_opener and any(re.search(r'\b(?:download|gltf|glb|zip|log\s*in|sign\s*in)\b',name,re.I) for role,name in controls.values())):break
            if attempt<3 and not after_opener:
                if cancelled():raise DownloadUnavailable('download-link observation cancelled')
                time.sleep(.5)  # bounded hydration wait; no navigation or click replay
    observe()
    # Only the official model page's primary download-dialog opener is eligible.
    # No final format/download link or login/authorization control is clicked.
    def auth_form():
        form=any(role.casefold() in ('textbox','edit') and re.search(r'(?i)email|password',name) for role,name in controls.values())
        heading=any(role.casefold()=='heading' and re.search(r'(?i)log\s*in|sign\s*in',name) for role,name in controls.values())
        return bool(form and heading)
    primary=[ref for ref,(role,name) in controls.items() if role.casefold()=='button'
        and re.sub(r'^[^\w]+','',name).strip().casefold()=='download 3d model']
    opener_acknowledged=False
    metadata={'candidates':[],'statuses':[]}
    if len(primary)==1 and not auth_form():
        page_matches()
        try:route.probe('asset_download_watch',uid=uid)
        except Exception:pass  # Older bridges can still expose normal download anchors.
        try:
            reply=execute({'action':'web_act','value':'click','content':json.dumps({'ref':primary[0]})})
            opener_acknowledged=json.loads(reply.evidence.splitlines()[0]).get('ok') is True
        except Exception:
            if cancelled():raise DownloadUnavailable('download-dialog observation cancelled')
            # The opener may have acted; observe once, never repeat the click.
        observe(after_opener=True)
        capture('after_download_opener')
        try:
            candidate_metadata=route.probe('asset_download_metadata',uid=uid)
            if isinstance(candidate_metadata,dict) and isinstance(candidate_metadata.get('candidates'),list):metadata=candidate_metadata
        except Exception:pass
    choices=[]
    for item in metadata.get('candidates',[])[:8]:
        if not isinstance(item,dict) or type(item.get('size')) is not int:continue
        p=urlsplit(str(item.get('url','')))
        kind='glb' if p.path.lower().endswith('.glb') else 'zip' if p.path.lower().endswith('.zip') else None
        if (kind and p.scheme=='https' and p.hostname=='media.sketchfab.com' and not p.username and not p.password
                and p.port in (None,443) and not p.fragment and p.path.startswith('/models/'+uid+'/')
                and 4<=item['size']<=asset.maximum_bytes):choices.append((item['size'],kind,item['url']))
    if choices:
        size,kind,href=min(choices)
        receipt={'provider':'sketchfab','uid':uid,'source_url':source,'observed_call_ids':calls,
            'url_sha256':hashlib.sha256(href.encode()).hexdigest(),'resolver':'owned-official-download-metadata-v1',
            'file_format':kind,'declared_bytes':size,'private_screenshots':screenshots}
        return {'url':href,'hosts':{'media.sketchfab.com'},'file_format':kind,'receipt_ref':journal.put(receipt,'Report')}
    format_rows=[];ui_options=[]
    for ref,(role,name) in list(controls.items()):
        if role.casefold() not in ('button','link') or name.strip().casefold()!='download':continue
        if cancelled():raise DownloadUnavailable('download-format observation cancelled')
        try:
            option=download_option(route.probe('asset_download_option',uid=uid,ref=ref).get('contexts'))
        except Exception:option=None
        if option:
            format_rows.append({**option,'within_admission':option['declared_bytes']<=asset.maximum_bytes})
            if option['supported'] and option['declared_bytes']<=asset.maximum_bytes:ui_options.append((option['declared_bytes'],option['format'],ref))
        if len(format_rows)>=8:break
    if ui_options:
        if permission_sha:
            from .browser_handoff import find
            local=find(actions.base,asset,source_title,ui_options,permission_sha,cancelled)
            if local:
                local.update(observed_call_ids=calls,private_screenshots=screenshots)
                return {'local_source':local,'file_format':local['file_format'],'receipt_ref':journal.put(local,'Report')}
        # Accessibility may expose an <a> as a button. Read its real archive
        # href before any click; do not require the role to be "link" or the
        # official variant to be ZIP. This also permits read-only recovery from
        # an uncertain earlier website transaction without another format click.
        for size,kind,ref in sorted(ui_options):
            result=route.probe('asset_download_link',uid=uid,ref=ref)
            if result.get('kind')=='archive':
                href=result['url'];actual_kind='glb' if urlsplit(href).path.lower().endswith('.glb') else 'zip'
                receipt={'provider':'sketchfab','uid':uid,'source_url':source,'observed_call_ids':calls,
                    'url_sha256':hashlib.sha256(href.encode()).hexdigest(),'resolver':'owned-official-download-anchor-v1',
                    'file_format':actual_kind,'declared_bytes':size,'private_screenshots':screenshots}
                return {'url':href,'hosts':{'media.sketchfab.com'},'file_format':actual_kind,'receipt_ref':journal.put(receipt,'Report')}
        size,kind,ref=min(ui_options)
        from ..sandbox.budget import Budget
        import uuid
        budget=asset_resources.budget(journal,permission_sha);identity='model-handoff-'+uuid.uuid4().hex
        # Conservatively retain one full browser-stage admission. The subsequent
        # HTTPS transfer has its own reservation and hard retained-byte limit.
        budget.reserve(identity,cpu_s=1,disk_bytes=asset.maximum_bytes)
        request_ref=journal.put({'operation':'official_model_format_click','uid':uid,'source_url':source,
            'declared_bytes':size,'maximum_bytes':asset.maximum_bytes,'format':kind,
            'per_file_rights_ref':asset.evidence_ref,'nonce':uuid.uuid4().hex},'Report')
        try:
            # The website may already have delivered a file even if the reply
            # was lost. Persist the click owner outside a per-task Journal so a
            # fresh request cannot repeat an unresolved format transaction.
            folder=Path(actions.base)/'.jarvis-runtime/discovery/browser-handoffs'
            from ...skill_memory import linked
            if any(linked(p) for p in (folder,*folder.parents)):raise DownloadUnavailable('linked download handoff ledger refused')
            folder.mkdir(parents=True,exist_ok=True)
            claim=folder/(uid+'.json')
            if linked(claim):raise DownloadUnavailable('linked download claim refused')
            try:
                with claim.open('x',encoding='utf-8') as file:
                    json.dump({'uid':uid,'request_ref':request_ref,'per_file_rights_ref':asset.evidence_ref,
                        'resource_grant_sha256':permission_sha,'maximum_bytes':asset.maximum_bytes,
                        'state':'claimed-before-format-click; reconcile before any repeat'},file)
            except FileExistsError:raise DownloadUnavailable('prior model format transaction requires read-only reconciliation; no repeat click')
            slot=asset_resources.reserve_pair(permission_sha,request_ref) if permission_sha else None
            try:actual=route.inner.capture_model_download(uid,ref,asset.maximum_bytes)
            except BaseException as exc:
                # Preserve actual post-failure observation before task cleanup
                # closes its owned tab. Never issue another format click.
                capture('after_uncertain_format_click')
                try:
                    after=execute({'action':'web_read','value':'interactive'})
                    snapshot=hashlib.sha256(after.evidence.encode()).hexdigest()
                except Exception:snapshot=None
                journal.put({'operation':'official_model_format_click','uid':uid,'request_ref':request_ref,
                    'state':'UNCERTAIN_NO_REPLAY','error_type':type(exc).__name__,'snapshot_sha256':snapshot,
                    'private_screenshots':screenshots,'resource_pair_slot':slot},'Report')
                raise
            href=actual['url']
            receipt={'provider':'sketchfab','uid':uid,'source_url':source,'observed_call_ids':calls,
                'url_sha256':hashlib.sha256(href.encode()).hexdigest(),'resolver':'owned-official-format-handoff-v1',
                'file_format':actual['format'],'declared_bytes':actual['declared_bytes'],
                'native_request_ref':request_ref,'browser_cancel_acknowledged':actual['browser_cancel_acknowledged'],
                'browser_observed_bytes':actual['browser_observed_bytes'],'browser_bytes_measured':actual.get('browser_bytes_measured',False),
                'handoff_event':actual.get('handoff_event'),'private_screenshots':screenshots,'resource_pair_slot':slot}
            return {'url':href,'hosts':{'media.sketchfab.com'},'file_format':actual['format'],'receipt_ref':journal.put(receipt,'Report')}
        finally:budget.settle(identity,uncertain=True)
    # Inspect only actual download-format anchors. Hrefs and signed query values
    # are never sent back to the language model or saved in Journal artifacts.
    options=[ref for ref,(role,name) in controls.items()
        if role.casefold()=='link' and re.search(r'\b(?:download|gltf|glb|zip)\b',name,re.I)]
    for ref in options[:12]:
        if cancelled():raise DownloadUnavailable('download-link observation cancelled')
        result=route.probe('asset_download_link',uid=uid,ref=ref)
        if result.get('kind')=='archive':
            href=result['url']
            receipt={'provider':'sketchfab','uid':uid,'source_url':source,'observed_call_ids':calls,
                'url_sha256':hashlib.sha256(href.encode()).hexdigest(),'resolver':'owned-official-download-anchor-v1',
                'file_format':'zip','private_screenshots':screenshots}
            return {'url':href,'hosts':{'media.sketchfab.com'},'file_format':'zip','receipt_ref':journal.put(receipt,'Report')}
    authentication_required=auth_form()
    diagnostic={'provider':'sketchfab','uid':uid,'source_url':source,'observed_call_ids':calls,
        'download_link_count':len(options),'status':'AUTHENTICATION_REQUIRED' if authentication_required else 'NO_QUALIFIED_OFFICIAL_DOWNLOAD_ANCHOR',
        'download_dialog_opener_acknowledged':opener_acknowledged,
        'private_screenshots':screenshots,
        'dialog_observed':bool(re.search(r'(?im)^\s*(?:-\s*)?dialog\b',observed.evidence)),
        'readiness_reads':reads,'snapshot_sha256':hashlib.sha256(observed.evidence.encode()).hexdigest(),
        'official_download_metadata_statuses':metadata.get('statuses',[])[:8],
        'official_download_sizes':[{'file_format':item.get('format'),'bytes':item.get('size')} for item in metadata.get('candidates',[])[:8]],
        'observed_format_rows':format_rows,'admitted_maximum_bytes':asset.maximum_bytes,
        'download_controls':[{'role':role,'name':name[:120]} for role,name in controls.values()
            if re.search(r'\b(?:download|gltf|glb|zip)\b',name,re.I)][:20],
        'login_control_present':any(re.fullmatch(r'(?i)log\s*in|sign\s*in',name.strip()) for role,name in controls.values()),
        'login_required_in_dialog':bool(re.search(r'(?i)(?:log\s*in|sign\s*in).{0,50}(?:to\s+)?download|download.{0,50}(?:log\s*in|sign\s*in)',observed.evidence)),
        'account_form_present':any(role.casefold() in ('textbox','edit') and re.search(r'(?i)email|password',name) for role,name in controls.values()),
        'download_or_login_headings':[name[:120] for role,name in controls.values() if role.casefold()=='heading' and re.search(r'(?i)download|log\s*in|sign\s*in',name)][:8],
        'traffic_challenge_present':bool(re.search(r'(?im)^.*(?:heading|RootWebArea|WebArea) "(?:Just a moment|Verify you are human|Access denied)',observed.evidence)),
        'account_actions_performed':False,'viewer_assets_extracted':False,
        'reason':'No admitted official archive handoff is available. Authentication, a supported file variant or resource approval is required; no bounded transport file was fetched.'}
    ref=journal.put(diagnostic,'Report')
    if authentication_required:
        raise AuthenticationRequired('official model download requires human sign-in; retained browser evidence '+ref)
    raise DownloadUnavailable('no qualified official model archive link; retained browser evidence '+ref)
