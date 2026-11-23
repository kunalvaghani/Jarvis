"""Rights-bound inert downloads and verifiable receipts in the existing Journal.

No caller URL/license flags, scripts, installer, browser replacement or overwrite.
Incomplete files stay unregistered. A restart reuses only independently checked
complete receipts; uncertain attempts require reconciliation before another effect.
"""
import hashlib
import json
from pathlib import Path
import time
import uuid
from .asset_rights import verify as rights
from .asset_files import inspect
from .asset_transport import stream
from .assets import local_bytes
from ..model.acquisition import DownloadResult
from ..sandbox.budget import Budget


class AcquisitionBlocked(ValueError):pass


def _validate(base,asset,availability,relative,file_format=None):
    raw=local_bytes(Path(base),relative,asset.maximum_bytes)
    checked=inspect(raw,file_format or asset.file_format,maximum=asset.maximum_bytes)
    if asset.expected_sha256 is not None and checked['sha256']!=asset.expected_sha256:
        raise ValueError('original differs from published SHA256')
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if availability.get('blob_sha1') and blob!=availability['blob_sha1']:
        raise ValueError('original differs from the selected pinned Git blob')
    return checked


def transfer(base,journal,acquisition_ref,*,cancelled=lambda:False,fetcher=None,actions=None):
    base=Path(base).resolve();asset,availability=rights(base,journal,acquisition_ref)
    from ..acceptance import artifact
    from . import asset_resources
    permission_sha=artifact(journal,asset.evidence_ref).get('resource_grant_sha256')
    with journal.tx() as db:
        db.execute('CREATE TABLE IF NOT EXISTS discovery_asset_transfers '
            '(acquisition_ref TEXT PRIMARY KEY,request_ref TEXT,state TEXT,relative_file TEXT,result_ref TEXT,failure_kind TEXT)')
    old=journal.rows('SELECT * FROM discovery_asset_transfers WHERE acquisition_ref=?',(acquisition_ref,))
    if old:
        if old[0]['state']=='complete':return old[0]['result_ref'],verify(base,journal,old[0]['result_ref'])
        raise AcquisitionBlocked('prior transfer is '+old[0]['state']+'; preserve and reconcile its actual file before another effect')
    if cancelled():raise AcquisitionBlocked('download cancelled before admission')
    locator_ref=None;file_format=asset.file_format;local_source=None
    if not availability.get('download_url') and asset.provider=='sketchfab' and actions is not None:
        from .asset_browser_download import resolve
        observed=resolve(actions,journal,asset,cancelled=cancelled,source_title=availability.get('title'))
        local_source=observed.get('local_source')
        if not local_source:availability={**availability,'download_url':observed['url'],'download_hosts':list(observed['hosts'])}
        locator_ref=observed['receipt_ref'];file_format=observed['file_format']
        if file_format not in availability.get('accepted_download_formats',[]):raise AcquisitionBlocked('unadmitted provider file format')
    if not local_source and (not availability.get('download_url') or not availability.get('download_hosts')):
        raise AcquisitionBlocked(availability.get('download_status','no qualified lawful file resolver is available'))
    from ...skill_memory import linked
    root=base/'.jarvis-runtime/discovery/acquired'/hashlib.sha256(acquisition_ref.encode()).hexdigest()
    if any(linked(p) for p in (root,*root.parents)):raise ValueError('linked acquisition root refused')
    if root.exists():raise AcquisitionBlocked('unregistered acquisition directory already exists; inspect instead of overwriting')
    target=root/('original.'+file_format);relative=target.relative_to(base).as_posix()
    request={'transfer_id':uuid.uuid4().hex,'acquisition_ref':acquisition_ref,'maximum_bytes':asset.maximum_bytes,'relative_file':relative,
        'source_revision':availability['revision'],'file_format':file_format,'code_executed':False,'locator_ref':locator_ref,
        'resource_grant_sha256':permission_sha}
    if permission_sha:
        locator=artifact(journal,locator_ref) if locator_ref else {}
        if locator.get('resource_pair_slot') is not None:
            request['resource_pair_slot']=locator['resource_pair_slot'];request['pair_admission_ref']=locator['native_request_ref']
        else:
            admission_ref=journal.put({'rights_ref':asset.evidence_ref,'acquisition_ref':acquisition_ref,
                'resource_grant_sha256':permission_sha,'nonce':request['transfer_id']},'Report')
            request['pair_admission_ref']=admission_ref;request['resource_pair_slot']=asset_resources.reserve_pair(permission_sha,admission_ref)
    request_ref=journal.put(request,'Report')
    identity='asset-'+request['transfer_id']
    budget=asset_resources.budget(journal,permission_sha);budget.reserve(identity,cpu_s=5,disk_bytes=asset.maximum_bytes)
    started=time.process_time()
    claimed=False
    try:
        with journal.tx() as db:
            concurrent=db.execute('SELECT state,result_ref FROM discovery_asset_transfers WHERE acquisition_ref=?',(acquisition_ref,)).fetchone()
            if not concurrent:
                db.execute('INSERT INTO discovery_asset_transfers VALUES (?,?,?,?,?,?)',
                    (acquisition_ref,request_ref,'claimed',relative,None,None));claimed=True
        if concurrent:
            budget.settle(identity,cpu_s=0,disk_bytes=0)
            if concurrent[0]=='complete':return concurrent[1],verify(base,journal,concurrent[1])
            raise AcquisitionBlocked('another transfer owns this asset; observe its receipt instead of repeating')
        root.mkdir(parents=True,exist_ok=False)
        with target.open('xb') as file:
            if local_source:
                from .browser_handoff import copy
                transport=copy(base,local_source,asset.maximum_bytes,file,cancelled)
            else:
                transport=(fetcher or stream)(availability['download_url'],set(availability['download_hosts']),
                    asset.maximum_bytes,file,cancelled=cancelled,seconds=40)
            file.flush()
            import os
            os.fsync(file.fileno())
        checked=_validate(base,asset,availability,relative,file_format)
        if transport.get('bytes')!=checked['bytes']:raise ValueError('completed transport and actual original byte counts differ')
        # Re-read the per-file source evidence before publishing acquired state.
        current,_=rights(base,journal,acquisition_ref)
        if current!=asset:raise ValueError('asset rights changed during transfer')
        result=DownloadResult(candidate_id=asset.candidate_id,acquisition_ref=acquisition_ref,relative_file=relative,
            sha256=checked['sha256'],bytes=checked['bytes'],file_format=file_format,source_revision=availability['revision'])
        report={'download':result.model_dump(mode='json'),'file_checks':checked,'transport':transport,'request_ref':request_ref}
        ref=journal.put(report,'Report')
        from ..memory import LabMemory
        from ..contracts import Source,RunArtifact
        memory=LabMemory(journal);memory.migrate();source_id='asset-'+result.sha256+'-'+hashlib.sha256(acquisition_ref.encode()).hexdigest()[:8]
        memory.put(Source(id=source_id,locator=asset.source_url,sha256=result.sha256,author=asset.creator,
            license=asset.license_spdx,justification='Acquired inert original with retained per-file rights; source-declared identity, not physical verification.'))
        memory.put(RunArtifact(id='original-'+result.sha256+'-'+hashlib.sha256(acquisition_ref.encode()).hexdigest()[:8],
            locator=relative,sha256=result.sha256,media_type='application/octet-stream',source_ids=(source_id,),
            justification='Actual completed original asset; not yet imported, disassembled or physically validated.'))
        budget.settle(identity,cpu_s=max(0,time.process_time()-started),disk_bytes=result.bytes)
        with journal.tx() as db:
            db.execute('UPDATE discovery_asset_transfers SET state=?,result_ref=? WHERE acquisition_ref=? AND request_ref=?',('complete',ref,acquisition_ref,request_ref))
        return ref,report
    except BaseException as exc:
        if claimed:
            with journal.tx() as db:
                db.execute('UPDATE discovery_asset_transfers SET state=?,failure_kind=? WHERE acquisition_ref=? AND request_ref=?',
                    ('uncertain',type(exc).__name__,acquisition_ref,request_ref))
            budget.settle(identity,uncertain=True)
        else:budget.settle(identity,cpu_s=0,disk_bytes=0)
        raise


def verify(base,journal,ref):
    from ..acceptance import artifact
    report=artifact(journal,ref);download=DownloadResult.model_validate_json(json.dumps(report['download']))
    asset,availability=rights(base,journal,download.acquisition_ref)
    if (download.candidate_id!=asset.candidate_id or download.file_format not in availability.get('accepted_download_formats',[asset.file_format])
            or download.source_revision!=availability.get('revision')):raise ValueError('download identity differs from admitted source')
    rows=journal.rows('SELECT * FROM discovery_asset_transfers WHERE acquisition_ref=? AND state=? AND result_ref=?',
        (download.acquisition_ref,'complete',ref))
    if len(rows)!=1 or rows[0]['relative_file']!=download.relative_file or rows[0]['request_ref']!=report['request_ref']:
        raise ValueError('actual matching completed transfer receipt required')
    expected='.jarvis-runtime/discovery/acquired/'+hashlib.sha256(download.acquisition_ref.encode()).hexdigest()+'/original.'+download.file_format
    if download.relative_file!=expected:raise ValueError('download escaped its immutable acquisition root')
    request=artifact(journal,report['request_ref']);local_copy=False
    if request.get('resource_grant_sha256'):
        from .asset_resources import grant,HOME
        from ...skill_memory import linked
        grant(request['resource_grant_sha256'])
        slot=request['resource_pair_slot']
        if type(slot) is not int or not 0<=slot<4:raise ValueError('invalid full-A transfer-pair slot')
        path=HOME/'transfer-pairs'/f'slot-{slot:02}.json'
        if linked(path):raise ValueError('linked transfer-pair receipt')
        pair=json.loads(path.read_text(encoding='utf-8'))
        if pair['grant_sha256']!=request['resource_grant_sha256'] or pair['request_ref']!=request['pair_admission_ref']:
            raise ValueError('actual matching global transfer-pair admission required')
    if asset.provider=='sketchfab':
        locator=artifact(journal,request['locator_ref'])
        if (locator['provider']!='sketchfab' or locator['uid']!=asset.candidate_id.split(':',1)[1]
                or locator['source_url'].split('#',1)[0]!=asset.source_url
                or not locator.get('observed_call_ids') or locator.get('resolver') not in ('owned-official-download-anchor-v1','owned-official-download-metadata-v1','owned-official-format-handoff-v1','owned-official-local-file-reconciliation-v1')
                or locator.get('file_format')!=download.file_format
                or (locator['resolver']!='owned-official-local-file-reconciliation-v1' and
                    (not isinstance(locator.get('url_sha256'),str) or len(locator['url_sha256'])!=64))):
            raise ValueError('actual matching official browser download observation required')
        if locator['resolver']=='owned-official-local-file-reconciliation-v1':
            from .browser_handoff import verify as verify_local
            verify_local(base,asset,locator)
            local_copy=True
            if (locator['source_sha256']!=download.sha256 or locator['resource_grant_sha256']!=request.get('resource_grant_sha256')
                    or locator['source_title']!=availability.get('title') or report['transport'].get('kind')!='owned_browser_file_copy'
                    or report['transport'].get('source_sha256')!=download.sha256):raise ValueError('local UI original differs from completed copy')
        if locator['resolver']=='owned-official-format-handoff-v1':
            observed_request=artifact(journal,locator['native_request_ref'])
            if (observed_request['uid']!=locator['uid'] or observed_request['per_file_rights_ref']!=asset.evidence_ref
                    or observed_request['maximum_bytes']!=asset.maximum_bytes or locator['declared_bytes']>asset.maximum_bytes):
                raise ValueError('download format handoff differs from its prior rights/resource admission')
    if (request['acquisition_ref']!=download.acquisition_ref or request['relative_file']!=expected
            or request['file_format']!=download.file_format or request['maximum_bytes']!=asset.maximum_bytes
            or report['transport'].get('bytes')!=download.bytes
            or (not local_copy and report['transport'].get('final_host') not in availability['download_hosts'])):
        raise ValueError('original differs from the admitted transfer request or transport receipt')
    checked=_validate(base,asset,availability,download.relative_file,download.file_format)
    if checked!=report['file_checks'] or checked['sha256']!=download.sha256 or checked['bytes']!=download.bytes:
        raise ValueError('acquired original or checks changed')
    return report
