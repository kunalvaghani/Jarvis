"""Reconcile a completed owned UI download; never click or search user files.

The literal public source slug and provider title must agree with one new file
in the default Downloads folder, created during the retained format action.
This is UI/file provenance, not an observed archive URL or engineering identity.
"""
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

DOWNLOADS=None  # Optional fixture override; production resolves the OS known folder lazily.


def downloads_folder():
    if DOWNLOADS is not None:return DOWNLOADS
    # The existing owned-worker environment intentionally omits USERPROFILE.
    # Resolve only this OS folder, without restoring credentials/environment or
    # assuming the user's profile name or configured folder location.
    import ctypes,uuid
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    ole=ctypes.WinDLL('ole32',use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetKnownFolderPath.restype=ctypes.c_long
    ole.CoTaskMemFree.argtypes=[ctypes.c_void_p];ole.CoTaskMemFree.restype=None
    guid=(ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID('374de290-123f-4565-9164-39c4925e467b').bytes_le)
    value=ctypes.c_void_p()
    result=shell.SHGetKnownFolderPath(ctypes.byref(guid),0,None,ctypes.byref(value))
    if result!=0 or not value.value:raise ValueError('Windows Downloads folder unavailable')
    try:return Path(ctypes.wstring_at(value))
    finally:ole.CoTaskMemFree(value)


def normalized(value):return re.sub('[^a-z0-9]','',value.casefold())


def identity(path):
    st=path.stat()
    return {'device':st.st_dev,'inode':st.st_ino,'bytes':st.st_size,'created_ns':st.st_ctime_ns,'modified_ns':st.st_mtime_ns}


def find(base,asset,title,options,grant_sha,cancelled=lambda:False):
    if os.name!='nt' or not title:return None  # st_ctime is creation time on this approved Windows path.
    from ...skill_memory import linked
    from .asset_resources import HOME,grant
    grant(grant_sha)
    folder=downloads_folder()
    uid=asset.candidate_id.split(':',1)[1]
    claim=Path(base)/'.jarvis-runtime/discovery/browser-handoffs'/(uid+'.json')
    if not claim.exists():return None
    if any(linked(p) for p in (claim,*claim.parents,folder,*folder.parents)):raise ValueError('linked browser download reconciliation refused')
    raw=claim.read_bytes()
    if len(raw)>16000:raise ValueError('browser claim exceeded byte bound')
    saved=json.loads(raw)
    if saved.get('uid')!=uid or saved.get('resource_grant_sha256')!=grant_sha or saved.get('maximum_bytes')!=asset.maximum_bytes:
        raise ValueError('browser claim source/resource scope differs')
    pairs=[]
    for slot in range(4):
        path=HOME/'transfer-pairs'/f'slot-{slot:02}.json'
        if not path.exists():continue
        if linked(path):raise ValueError('linked browser transfer admission')
        pair=json.loads(path.read_text(encoding='utf-8'))
        if pair.get('grant_sha256')==grant_sha and pair.get('request_ref')==saved['request_ref']:pairs.append(slot)
    if len(pairs)!=1:raise ValueError('one matching owned UI transfer-pair admission required')
    slug=urlsplit(asset.source_url).path.rsplit('/',1)[-1]
    if not slug.endswith('-'+uid):return None
    stem=normalized(slug[:-33])
    if not stem or stem!=normalized(title):return None
    start=claim.stat().st_mtime_ns;candidates=[]
    for declared,kind,_ in options:
        suffix='glb' if kind=='glb' else 'zip'
        # Only exact source-derived names; no recursive folder/user-file search.
        for path in folder.glob('*.'+suffix):
            if normalized(path.stem)!=stem:continue
            if linked(path) or not path.is_file():raise ValueError('linked or non-file download refused')
            info=identity(path)
            if not (start<=info['created_ns']<=info['modified_ns']<=start+75_000_000_000):continue
            if not 4<=info['bytes']<=asset.maximum_bytes:continue
            # The UI's rounded "MB" may denote decimal MB or binary MiB.
            if not any(abs(info['bytes']-declared*scale)<=1_048_576 for scale in (1,1.048576)):continue
            candidates.append((path,info))
    unique={str(path):(path,info) for path,info in candidates}
    if len(unique)!=1:return None
    path,info=next(iter(unique.values()));digest=hashlib.sha256();size=0
    with path.open('rb') as file:
        while chunk:=file.read(1024*1024):
            if cancelled():raise ValueError('browser source reconciliation cancelled')
            size+=len(chunk)
            if size>asset.maximum_bytes:raise ValueError('browser source grew beyond admitted bytes')
            digest.update(chunk)
    if identity(path)!=info:raise ValueError('download changed during reconciliation')
    return {'provider':'sketchfab','uid':uid,'source_url':asset.source_url,'source_title':title,
        'resolver':'owned-official-local-file-reconciliation-v1','file_format':path.suffix[1:],
        'source_filename':path.name,'source_identity':info,'source_sha256':digest.hexdigest(),
        'source_claim_sha256':hashlib.sha256(raw).hexdigest(),'native_request_ref':saved['request_ref'],
        'resource_pair_slot':pairs[0],'resource_grant_sha256':grant_sha,
        'ownership_basis':'selected-model UI claim, exact source/title filename and new-file creation window; no archive URL observed',
        'physical_identity_verified':False}


def copy(base,receipt,maximum,sink,cancelled=lambda:False):
    from ...skill_memory import linked
    name=receipt['source_filename']
    if Path(name).name!=name or '/' in name or '\\' in name:raise ValueError('invalid reconciled download filename')
    folder=downloads_folder();path=folder/name
    if any(linked(p) for p in (path,folder,*folder.parents)) or identity(path)!=receipt['source_identity']:raise ValueError('reconciled source changed')
    digest=hashlib.sha256();size=0
    with path.open('rb') as file:
        while chunk:=file.read(1024*1024):
            if cancelled():raise ValueError('reconciled copy cancelled')
            size+=len(chunk)
            if size>maximum:raise ValueError('reconciled copy exceeded admitted size')
            digest.update(chunk);sink.write(chunk)
    if digest.hexdigest()!=receipt['source_sha256'] or identity(path)!=receipt['source_identity']:
        raise ValueError('reconciled source changed during copy')
    return {'bytes':size,'kind':'owned_browser_file_copy','source_sha256':digest.hexdigest()}


def verify(base,asset,receipt):
    from ...skill_memory import linked
    from .asset_resources import grant
    grant(receipt['resource_grant_sha256'])
    claim=Path(base)/'.jarvis-runtime/discovery/browser-handoffs'/(receipt['uid']+'.json')
    if linked(claim) or hashlib.sha256(claim.read_bytes()).hexdigest()!=receipt['source_claim_sha256']:
        raise ValueError('browser source claim changed')
    saved=json.loads(claim.read_text(encoding='utf-8'))
    slug=urlsplit(asset.source_url).path.rsplit('/',1)[-1]
    info=receipt['source_identity'];start=claim.stat().st_mtime_ns
    if (not start<=info['created_ns']<=info['modified_ns']<=start+75_000_000_000
            or not 4<=info['bytes']<=asset.maximum_bytes or receipt['physical_identity_verified'] is not False):
        raise ValueError('local UI creation/size evidence differs')
    if (receipt['uid']!=asset.candidate_id.split(':',1)[1] or receipt['source_url']!=asset.source_url
            or normalized(Path(receipt['source_filename']).stem)!=normalized(receipt['source_title'])
            or not slug.endswith('-'+receipt['uid']) or normalized(slug[:-33])!=normalized(receipt['source_title'])
            or saved['request_ref']!=receipt['native_request_ref'] or saved['maximum_bytes']!=asset.maximum_bytes
            or saved['resource_grant_sha256']!=receipt['resource_grant_sha256']):raise ValueError('local UI source binding differs')
