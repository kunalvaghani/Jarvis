"""Immutable workload metadata checkpoints; a locked convenience index is not task failure."""
import json
from pathlib import Path
import time
import threading
from uuid import uuid4

_checkpoint_lock=threading.Lock()


def save_checkpoint(directory, receipt):
    directory=Path(directory)
    checkpoints=directory/'checkpoints';checkpoints.mkdir(exist_ok=True)
    # Wall-clock reads may tie or move backwards. UUID order does not represent
    # save order, so advance beyond retained timestamps under the owning
    # process's lock. Workload directories have one owning process.
    with _checkpoint_lock:
        previous=max((int(p.name.split('-',1)[0]) for p in checkpoints.glob('*.json')
                      if p.name.split('-',1)[0].isdigit()),default=0)
        name=f'{max(time.time_ns(),previous+1):020d}-{uuid4().hex}.json'
        snapshot={**receipt,'checkpoint':name}
        text=json.dumps(snapshot,indent=2)
        # The immutable checkpoint is authoritative. It is never replaced/replayed.
        with (checkpoints/name).open('x',encoding='utf-8') as output:output.write(text)
    temporary=directory/('receipt-'+uuid4().hex+'.tmp')
    with temporary.open('x',encoding='utf-8') as output:output.write(text)
    try:temporary.replace(directory/'receipt.json')
    except PermissionError as exc:
        # Preserve the temporary file and current index. Do not retry a save
        # after an uncertain failure; a later state gets a new checkpoint.
        with (directory/'receipt-index-errors.jsonl').open('a',encoding='utf-8') as output:
            output.write(json.dumps({'checkpoint':name,'error_type':type(exc).__name__,
                                     'index_updated':False,'replayed':False})+'\n')
        return False
    return True


def latest_checkpoint(directory):
    """Fresh read only; consumers can inspect newer state when the index is locked/stale."""
    directory=Path(directory)
    names=sorted((directory/'checkpoints').glob('*.json'))
    errors=[]
    for target in reversed(names or [directory/'receipt.json']):
        try:
            value=json.loads(target.read_text(encoding='utf-8'))
            if not isinstance(value,dict) or not isinstance(value.get('status'),str):
                raise ValueError('Invalid workload checkpoint contract.')
        except (OSError,ValueError) as exc:
            errors.append({'name':target.name,'error_type':type(exc).__name__});continue
        if errors:
            value={**value,'checkpoint_recovery_required':True,'unreadable_newer_checkpoints':errors}
        return value
    raise ValueError('No complete workload checkpoint; inspect retained state before any action.')


def load_validation_history(root, paths, fixed_hashes, checks):
    """Read explicitly selected old failures, never actions or cached success.

    Reuses immutable native/workload records. Each accepted observation needs a
    terminal owner, the same checks/frozen bytes, and an intact validated source
    snapshot. Callers choose the trusted namespace; page/model data cannot.
    """
    import hashlib
    import re
    from .codex_validation import source_path
    if not isinstance(paths,list) or len(paths)>4:raise ValueError('Select at most four historical validations.')
    if not paths:return [],[]
    root=Path(root).resolve(strict=True)
    if not fixed_hashes:raise ValueError('History requires current frozen-file bindings.')
    test_paths={check['path'] for check in checks if check['kind'] in {'python_tests','node_tests'}}
    if not test_paths or not test_paths.issubset(fixed_hashes):
        return [],[{'accepted':False,'reason':'History requires every current executable test file to be frozen.'} for _ in paths]
    canonical=lambda value:sorted(json.dumps(row,sort_keys=True) for row in value)
    wanted=canonical(checks);records=[];manifest=[]
    def read(path,limit):
        with path.open('rb') as stream:raw=stream.read(limit+1)
        if len(raw)>limit:raise ValueError('Historical metadata exceeds its size limit.')
        value=json.loads(raw.decode('utf-8'))
        if not isinstance(value,dict):raise ValueError('Historical metadata must be an object.')
        return value,hashlib.sha256(raw).hexdigest()
    seen=set()
    for name in paths:
        row={'accepted':False}
        try:
            if not isinstance(name,str):raise ValueError('History paths must be strings.')
            path=(root/name).resolve(strict=True)
            if not path.is_relative_to(root) or not re.fullmatch(r'validation-[a-f0-9]{32}\.json',path.name):
                raise ValueError('Historical validation is outside the approved namespace or has an invalid identity.')
            if path in seen:raise ValueError('Duplicate historical validation.')
            seen.add(path);row['path']=path.relative_to(root).as_posix()
            native=path.parent
            if (native.parent.name!='native-code' or native.parent.parent.name!='.jarvis-runtime'
                    or native.parent.parent.parent.parent!=root
                    or not re.fullmatch('[a-f0-9]{32}',native.name)
                    or not re.fullmatch('[a-f0-9]{32}',native.parent.parent.parent.name)):
                raise ValueError('Historical validation lacks a native owner.')
            campaign,_=read(native.parent.parent.parent/'campaign.json',2000000)
            result,_=read(native/'result.json',1000000)
            if not isinstance(campaign.get('finished_at'),str) or not campaign['finished_at'] or result.get('status') not in {'passed','failed','stopped'}:
                raise ValueError('Historical owner is not terminal.')
            request,request_sha=read(native/'request.json',128000)
            if canonical(request['validation_contract']['checks'])!=wanted:
                raise ValueError('Historical executable checks differ.')
            value,sha=read(path,200000)
            hashes=value.get('hashes',{})
            errors=value.get('errors')
            if (value.get('passed') is not False or not isinstance(errors,list) or not 1<=len(errors)<=32
                    or any(not isinstance(error,dict) or not isinstance(error.get('error'),str) for error in errors[:3])
                    or not isinstance(hashes,dict) or not 1<=len(hashes)<=32):
                raise ValueError('History requires an actual bounded failed validation.')
            if any(hashes.get(key)!=digest for key,digest in fixed_hashes.items()):
                raise ValueError('Historical frozen-file hashes differ.')
            if any(not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest) for digest in hashes.values()):
                raise ValueError('Historical source fingerprints are malformed.')
            snapshots=[]
            for error in value['errors'][:3]:
                for filename in re.findall(r'File "([^"\r\n]+)"',str(error.get('error','')))[:12]:
                    candidate=Path(filename.replace('\\\\','\\')).parent.resolve()
                    if candidate.parent==native and re.fullmatch(r'check-workspace-\d+',candidate.name) and candidate not in snapshots:
                        snapshots.append(candidate)
            verified=None
            for snapshot in snapshots[:4]:
                try:
                    valid=True
                    for key,digest in hashes.items():
                        source=source_path(snapshot,key)
                        with source.open('rb') as stream:raw=stream.read(80001)
                        if len(raw)>80000 or hashlib.sha256(raw).hexdigest()!=digest:valid=False;break
                    if valid:verified=snapshot;break
                except (OSError,ValueError):continue
            if verified is None:raise ValueError('Historical validated source snapshot is missing or changed.')
            selected=[error for error in value['errors'][:3] if error.get('path') in test_paths]
            if not selected:raise ValueError('Historical failure does not belong to the current frozen tests.')
            records.append({**value,'errors':selected})
            row.update(accepted=True,validation_sha256=sha,request_sha256=request_sha,
                       snapshot=verified.relative_to(root).as_posix(),frozen_hashes=dict(fixed_hashes),
                       source_fingerprint=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest())
        except (OSError,ValueError,KeyError,TypeError) as error:
            row['reason']=str(error)[:180]
        manifest.append(row)
    return records,manifest
