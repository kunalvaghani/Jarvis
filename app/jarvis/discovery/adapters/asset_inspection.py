"""Qualified fixed geometry worker, using the existing approved tool environment.

Shared non-refundable mechanics 50-call ledger, measured Journal admission and
owned Windows CPU/memory limits. No main-environment install or GPU residency.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import uuid
import zipfile
from . import mechanics
from .assets import local_bytes
from .asset_files import archive_inventory
from .asset_acquisition import verify as verified_download
from ..sandbox.budget import Budget

WORKER=Path(__file__).with_name('asset_inspection_worker.py')


def completed_record(slot,digest):
    """Read retained output and bind it to the non-refundable dispatch ledger."""
    from ...skill_memory import linked
    if type(slot) is not int or not 0<=slot<50:raise ValueError('invalid inspection slot')
    path=mechanics.SETUP/'invocations'/('inspection-result-'+str(slot)+'.json')
    ledger=mechanics.SETUP/'invocations'/f'slot-{slot:02}.json'
    if linked(path) or linked(ledger) or path.stat().st_size>5_000_000:raise ValueError('invalid inspection evidence')
    record=json.loads(path.read_text(encoding='utf-8'));claim=json.loads(ledger.read_text(encoding='utf-8'))
    if (record['slot']!=slot or record['worker_sha256']!=digest or claim['worker_sha256']!=digest
            or claim.get('operation')!='asset_inspection' or claim['request_ref']!=record['request_ref']):
        raise ValueError('inspection evidence differs from dispatch ledger')
    body=json.dumps(record['inspection'],allow_nan=False,separators=(',',':')).encode()
    if hashlib.sha256(body).hexdigest()!=record['result_sha256']:raise ValueError('inspection result changed')
    return record


def golden_checks(records):
    """Independent analytic checks on actual retained worker output, not pass flags."""
    import math
    if len(records)!=2 or len({r['slot'] for r in records})!=2:raise ValueError('two distinct golden dispatches required')
    cube,rejection=(r['inspection'] for r in records)
    validate(cube,cube['source_sha256'])
    if len(cube['parts'])!=1 or cube['units']!='m' or cube['units_resolved'] is not True:raise ValueError('cube inventory differs')
    part=cube['parts'][0]
    if (part['vertex_count']!=8 or part['triangle_count']!=12 or not part['watertight']
            or not part['winding_consistent'] or part['source_name']!='analytic cube'):
        raise ValueError('analytic cube topology differs')
    if any(abs(a-b)>1e-7 for row,want in zip(part['bounds'],[[4,-1,-1],[6,1,1]]) for a,b in zip(row,want)):
        raise ValueError('world transform or cube scale differs')
    if not math.isclose(part['enclosed_volume_if_watertight_m3'],8,abs_tol=1e-7):raise ValueError('cube volume differs')
    if rejection.get('status')!='REJECTED' or rejection.get('code')!='EXTERNAL_OR_ESCAPING_RESOURCE':
        raise ValueError('external resource was not rejected before import')


def worker_hash():
    from ...skill_memory import linked
    paths=[WORKER,Path(__file__),Path(mechanics.__file__),Path(__file__).parents[2]/'harness_process.py',Path(__file__).parents[2]/'repo_acquisition.py',Path(__file__).with_name('asset_resources.py'),Path(__file__).with_name('asset_files.py'),Path(__file__).with_name('asset_inspection_goldens.py')]
    digest=hashlib.sha256()
    for path in paths:
        if linked(path) or not path.is_file():raise ValueError('owned inspector source missing or linked')
        digest.update(path.name.encode());digest.update(path.read_bytes())
    return digest.hexdigest()


def proof_path(sha,resource_grant_sha256=None):
    return mechanics.SETUP/('asset-inspector-golden-'+sha+('-full-a-'+resource_grant_sha256[:12] if resource_grant_sha256 else '')+'.json')


def qualification(resource_grant_sha256=None):
    state=mechanics.environment();problems=list(state['problems']);sha=worker_hash()
    proof=proof_path(sha,resource_grant_sha256)
    try:
        from ...skill_memory import linked
        if linked(proof) or proof.stat().st_size>64000:raise ValueError('invalid inspector proof')
        data=json.loads(proof.read_text(encoding='utf-8'))
        if resource_grant_sha256:
            from .asset_resources import grant
            grant(resource_grant_sha256)
        if data.get('resource_grant_sha256')!=resource_grant_sha256:raise ValueError('inspector profile differs from golden proof')
        if data.get('worker_sha256')!=sha or data.get('parser')!='trimesh' or data.get('version')!='5.2.0' or not data.get('goldens'):
            raise ValueError('inspector golden proof missing')
        if {x['case'] for x in data['goldens']}!={'analytic_cube','external_uri_rejected'} or not all(x['passed'] is True for x in data['goldens']):
            raise ValueError('inspector golden cases incomplete')
        rows={x['case']:x for x in data['goldens']}
        records=[completed_record(rows[name]['slot'],sha) for name in ('analytic_cube','external_uri_rejected')]
        if any(record.get('resource_grant_sha256')!=resource_grant_sha256 for record in records):raise ValueError('golden dispatch resource profile differs')
        if any(record['result_sha256']!=rows[name]['result_sha256'] for name,record in zip(('analytic_cube','external_uri_rejected'),records)):
            raise ValueError('golden result receipt differs')
        golden_checks(records)
    except (OSError,ValueError,KeyError,TypeError) as exc:problems.append(type(exc).__name__+': current inspector proof unavailable')
    return {'runtime_ready':not problems,'problems':problems,'worker_sha256':sha,'parser':'trimesh','version':'5.2.0',
        'remaining_shared_invocations':50-state['used_slots'],'gpu_required':False,'isolation':'fixed data-only worker with CPU/committed-memory limits; not an OS security sandbox'}


def ensure_qualified(journal,*,resource_grant_sha256=None,cancelled=lambda:False):
    status=qualification(resource_grant_sha256)
    if status['runtime_ready']:return status
    if resource_grant_sha256:
        from .asset_resources import grant
        grant(resource_grant_sha256)  # Never learn permission from a previous pass.
    if cancelled():raise ValueError('qualification cancelled before claim')
    environment=mechanics.environment()
    if not environment['ready']:raise ValueError('mechanics environment unavailable before qualification')
    if environment['used_slots']>48:raise PermissionError('two approved mechanics calls required for qualification')
    sha=worker_hash();path=proof_path(sha,resource_grant_sha256)
    claim=path.with_suffix('.claim')
    from ...skill_memory import linked
    if linked(path) or linked(claim):raise ValueError('linked inspector qualification refused')
    if path.exists():raise ValueError('retained qualification is invalid; no automatic rerun')
    with claim.open('x',encoding='utf-8') as file:
        json.dump({'worker_sha256':sha,'resource_grant_sha256':resource_grant_sha256,'state':'claimed-before-goldens'},file)
    records=[]
    try:
        from .asset_inspection_goldens import cases
        for payload in cases():
            records.append(invoke(payload,journal,qualifying=True,cancelled=cancelled,resource_grant_sha256=resource_grant_sha256))
        golden_checks(records)
        if worker_hash()!=sha:raise ValueError('inspector source changed during qualification')
        proof={'worker_sha256':sha,'parser':'trimesh','version':'5.2.0','resource_grant_sha256':resource_grant_sha256,
            'physical_validation':False,'scope':'analytic parser/profile verification only; no autonomous full-A claim',
            'goldens':[{'case':name,'slot':record['slot'],'result_sha256':record['result_sha256'],'passed':True}
                for name,record in zip(('analytic_cube','external_uri_rejected'),records)]}
        with path.open('x',encoding='utf-8') as file:json.dump(proof,file,indent=2)
        journal.put({'qualification':'asset_inspector','worker_sha256':sha,'resource_grant_sha256':resource_grant_sha256,
            'outcome':'GOLDENS_PASSED','slots':[r['slot'] for r in records]},'Report')
        return qualification(resource_grant_sha256)
    except BaseException as exc:
        journal.put({'qualification':'asset_inspector','worker_sha256':sha,'outcome':'FAILED_OR_UNCERTAIN',
            'slots':[r['slot'] for r in records],'error_type':type(exc).__name__},'Report')
        raise


def validate(result,source_sha,maximum_cpu=18):
    import math
    if (result.get('parser')!='trimesh' or result.get('version')!='5.2.0' or result.get('source_sha256')!=source_sha
            or result.get('physical_validation') is not False or result.get('original_modified') is not False):raise ValueError('inspector output identity differs')
    parts=result.get('parts')
    if not isinstance(parts,list) or not 1<=len(parts)<=500 or len({p['component_id'] for p in parts})!=len(parts):raise ValueError('invalid geometric part inventory')
    triangles=0
    for part in parts:
        if part['mass_kg'] is not None or part['inertia_kg_m2'] is not None or part['joints_verified'] is not False:
            raise ValueError('geometry cannot fabricate physical properties or joints')
        if 'geometric_connectivity' in part:
            regions=part.get('connected_regions')
            if (type(regions) is not int or not 1<=regions<=part['triangle_count']
                    or part['geometric_connectivity'] not in ('CONNECTED_REGION','DISCONNECTED_SOURCE_NODE_AGGREGATE')
                    or (part['geometric_connectivity']=='CONNECTED_REGION' and regions!=1)
                    or (part['geometric_connectivity']=='DISCONNECTED_SOURCE_NODE_AGGREGATE' and regions<=1)):
                raise ValueError('geometric connectivity claim differs from bounded inventory')
        bounds=part['bounds']
        if len(bounds)!=2 or any(len(row)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in row) for row in bounds):raise ValueError('invalid source bounds')
        if any(bounds[0][i]>bounds[1][i] for i in range(3)):raise ValueError('inverted source bounds')
        points=part['preview_vertices'];faces=part['preview_triangles'];triangles+=len(faces)
        if any(len(p)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in points):raise ValueError('invalid preview positions')
        if any(len(face)!=3 or any(type(i) is not int or not 0<=i<len(points) for i in face) for face in faces):raise ValueError('invalid preview triangle')
    if triangles>5000:raise ValueError('preview exceeded fixed triangle budget')
    if type(result.get('cpu_s')) not in (float,int) or not 0<=result['cpu_s']<=maximum_cpu:raise ValueError('inspector CPU bound exceeded')
    return result


def invoke(payload,journal,*,cancelled=lambda:False,qualifying=False,context=None,resource_grant_sha256=None):
    if cancelled():raise ValueError('inspection cancelled before resource admission')
    if not qualifying and not qualification(resource_grant_sha256)['runtime_ready']:
        ensure_qualified(journal,resource_grant_sha256=resource_grant_sha256,cancelled=cancelled)
    from . import asset_resources
    permission=asset_resources.grant(resource_grant_sha256) if resource_grant_sha256 else None
    if permission:payload={**payload,'resource_grant_sha256':resource_grant_sha256}
    maximum_cpu=permission['parser_cpu_seconds'] if permission else 18
    maximum_memory=permission['parser_memory_bytes'] if permission else 1024**3
    timeout=75 if permission else 30
    raw=json.dumps(payload,allow_nan=False,separators=(',',':')).encode()
    if len(raw)>(160_000_000 if permission else 70_000_000):raise ValueError('inspector request exceeded fixed byte cap')
    digest=worker_hash();request=journal.put({'source_sha256':payload['source_sha256'],'format':payload['format'],
        'worker_sha256':digest,'entrypoint':payload['entrypoint'],'operation':'asset_inspection','context':context,
        'resource_grant_sha256':resource_grant_sha256},'Report')
    identity='inspect-'+uuid.uuid4().hex;budget=asset_resources.budget(journal,resource_grant_sha256);budget.reserve(identity,cpu_s=maximum_cpu,disk_bytes=4_000_000)
    slot=None
    try:
        slot=mechanics.reserve(request,operation='asset_inspection')
        from ...repo_acquisition import command
        usage={}
        output=command([str(mechanics.ENV/('Scripts/python.exe' if os.name=='nt' else 'bin/python')),'-I','-B',str(WORKER)],
            cancelled,timeout,raw,4_000_000,resource_limits={'memory_bytes':maximum_memory,'cpu_seconds':maximum_cpu},usage=usage)
        result=json.loads(output)
        rejected=result.get('status')=='REJECTED'
        if rejected:
            import math
            if (type(result.get('cpu_s')) not in (int,float) or not math.isfinite(result['cpu_s'])
                    or not 0<=result['cpu_s']<=maximum_cpu or not isinstance(result.get('code'),str) or len(result['code'])>100):
                raise ValueError('invalid inspector rejection')
        else:validate(result,payload['source_sha256'],maximum_cpu)
        budget.settle(identity,cpu_s=result['cpu_s'],disk_bytes=len(output))
        record={'inspection':result,'worker_sha256':digest,'request_ref':request,'slot':slot,'stdout_sha256':hashlib.sha256(output).hexdigest(),'budget_id':identity,
            'resource_grant_sha256':resource_grant_sha256,
            'result_sha256':hashlib.sha256(json.dumps(result,allow_nan=False,separators=(',',':')).encode()).hexdigest(),
            'resource_usage':{**usage,'committed_memory_limit_bytes':maximum_memory,'user_cpu_limit_s':maximum_cpu,'wall_timeout_s':timeout}}
        path=mechanics.SETUP/'invocations'/('inspection-result-'+str(slot)+'.json')
        from ...skill_memory import linked
        if linked(path):raise ValueError('linked inspection evidence refused')
        with path.open('x',encoding='utf-8') as file:json.dump(record,file,allow_nan=False,separators=(',',':'))
        if rejected and not qualifying:raise ValueError('inspection rejected: '+result['code'])
        return record
    except BaseException:
        if slot is None:budget.settle(identity,cpu_s=0,disk_bytes=0)
        else:budget.settle(identity,uncertain=True)
        raise


def inspect_download(base,journal,download_ref,*,cancelled=lambda:False):
    base=Path(base).resolve();download=verified_download(base,journal,download_ref)['download']
    digest=worker_hash()
    with journal.tx() as db:
        db.execute('CREATE TABLE IF NOT EXISTS discovery_asset_inspections '
            '(download_ref TEXT,worker_sha256 TEXT,attempt_id TEXT,state TEXT,result_ref TEXT,'
            'PRIMARY KEY(download_ref,worker_sha256))')
    rows=journal.rows('SELECT * FROM discovery_asset_inspections WHERE download_ref=? AND worker_sha256=?',(download_ref,digest))
    if rows:
        row=rows[0]
        if row['state']=='complete':return row['result_ref'],verify_inspection(base,journal,row['result_ref'])['receipt']
        # Reconcile only an independently retained completed invocation. Never
        # repeat a dispatch whose reply or publication might have been lost.
        from ..acceptance import artifact
        found=[]
        for path in (mechanics.SETUP/'invocations').glob('inspection-result-*.json'):
            try:
                slot=int(path.stem.rsplit('-',1)[1]);record=completed_record(slot,digest)
                request=artifact(journal,record['request_ref'])
                if request.get('context')=={'attempt_id':row['attempt_id'],'download_ref':download_ref}:found.append(record)
            except (OSError,ValueError,KeyError,TypeError):continue
        if len(found)!=1:raise ValueError('inspection outcome unresolved; no automatic dispatch replay')
        record=found[0]
        if record['inspection'].get('status')=='REJECTED':raise ValueError('retained inspection rejected: '+record['inspection']['code'])
        return publish_inspection(base,journal,download_ref,download,record)
    if cancelled():raise ValueError('inspection cancelled before claim')
    from .asset_rights import verify as rights
    from ..acceptance import artifact
    asset,_=rights(base,journal,download['acquisition_ref'])
    permission_sha=artifact(journal,asset.evidence_ref).get('resource_grant_sha256')
    raw=local_bytes(base,download['relative_file'],asset.maximum_bytes);kind=download['file_format'];entrypoint='original.'+kind;resources={}
    if kind=='zip':
        inventory=archive_inventory(raw,maximum=asset.maximum_bytes)
        names=[row['path'] for row in inventory['entries']]
        preferred=next((fmt for fmt in ('glb','gltf','obj','stl') if any(name.lower().endswith('.'+fmt) for name in names)),None)
        options=[name for name in names if preferred and name.lower().endswith('.'+preferred)]
        if len(options)!=1:raise ValueError('archive model entrypoint ambiguous or unsupported; preserve source and select a qualified alternative')
        entrypoint=options[0];kind=preferred
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            resources={name:base64.b64encode(archive.read(name)).decode() for name in names if name!=entrypoint}
            raw=archive.read(entrypoint)
    payload={'format':kind,'body':base64.b64encode(raw).decode(),'source_sha256':hashlib.sha256(raw).hexdigest(),
        'entrypoint':entrypoint,'resources':resources,'length_unit':'unknown'}
    attempt=uuid.uuid4().hex
    with journal.tx() as db:
        # Concurrent calls may prepare data, but only one owns the dispatch.
        prior=db.execute('SELECT state FROM discovery_asset_inspections WHERE download_ref=? AND worker_sha256=?',(download_ref,digest)).fetchone()
        if prior:raise ValueError('another inspection owns this source; observe instead of repeating')
        db.execute('INSERT INTO discovery_asset_inspections VALUES (?,?,?,?,?)',(download_ref,digest,attempt,'claimed',None))
    record=invoke(payload,journal,cancelled=cancelled,context={'attempt_id':attempt,'download_ref':download_ref},resource_grant_sha256=permission_sha)
    return publish_inspection(base,journal,download_ref,download,record)


def publish_inspection(base,journal,download_ref,download,record):
    """Publish a retained completed observation, including after a lost reply."""
    if record['worker_sha256']!=worker_hash():raise ValueError('inspector source changed before publication')
    from ..acceptance import artifact
    request=artifact(journal,record['request_ref']);entrypoint=request['entrypoint']
    verified_download(base,journal,download_ref)  # No stale file published after a concurrent change.
    root=base/'.jarvis-runtime/discovery/imports'/download['sha256']/record['worker_sha256']
    from ...skill_memory import linked
    if any(linked(p) for p in (root,*root.parents)):raise ValueError('linked inspection output root refused')
    root.mkdir(parents=True,exist_ok=True)
    path=root/('inspection-slot-'+str(record['slot'])+'.json')
    body=json.dumps(record['inspection'],allow_nan=False,separators=(',',':')).encode()
    if path.exists():
        if linked(path) or path.read_bytes()!=body:raise ValueError('retained inspection output differs')
    else:
        with path.open('xb') as file:file.write(body)
    receipt={k:v for k,v in record.items() if k!='inspection'}
    receipt.update(download_ref=download_ref,original_sha256=download['sha256'],entrypoint=entrypoint,
        relative_file=path.relative_to(base).as_posix(),sha256=hashlib.sha256(body).hexdigest(),
        part_count=len(record['inspection']['parts']),units_resolved=record['inspection']['units_resolved'])
    context=request.get('context') or {}
    if context.get('download_ref')!=download_ref:raise ValueError('inspection is not bound to this download')
    ref=journal.put(receipt,'Report')
    with journal.tx() as db:
        row=db.execute('SELECT attempt_id FROM discovery_asset_inspections WHERE download_ref=? AND worker_sha256=?',(download_ref,record['worker_sha256'])).fetchone()
        if row is None or row[0]!=context.get('attempt_id'):raise ValueError('inspection dispatch owner differs')
        db.execute('UPDATE discovery_asset_inspections SET state=?,result_ref=? WHERE download_ref=? AND worker_sha256=?',
            ('complete',ref,download_ref,record['worker_sha256']))
    verify_inspection(base,journal,ref)
    return ref,receipt


def verify_inspection(base,journal,ref):
    from ..acceptance import artifact
    base=Path(base).resolve();receipt=artifact(journal,ref);digest=worker_hash()
    if receipt['worker_sha256']!=digest or not qualification(receipt.get('resource_grant_sha256'))['runtime_ready']:raise ValueError('inspection worker is no longer qualified')
    download=verified_download(base,journal,receipt['download_ref'])['download']
    record=completed_record(receipt['slot'],digest);request=artifact(journal,record['request_ref'])
    from .asset_rights import verify as rights
    asset,_=rights(base,journal,download['acquisition_ref'])
    expected_grant=artifact(journal,asset.evidence_ref).get('resource_grant_sha256')
    if request.get('resource_grant_sha256')!=expected_grant or record.get('resource_grant_sha256')!=expected_grant:
        raise ValueError('inspection resource profile differs from source admission')
    rows=journal.rows('SELECT * FROM discovery_asset_inspections WHERE download_ref=? AND worker_sha256=? AND state=? AND result_ref=?',
        (receipt['download_ref'],digest,'complete',ref))
    if len(rows)!=1 or request.get('context')!={'attempt_id':rows[0]['attempt_id'],'download_ref':receipt['download_ref']}:
        raise ValueError('inspection has no matching completed dispatch')
    if any(receipt.get(key)!=value for key,value in record.items() if key!='inspection'):
        raise ValueError('inspection receipt differs from retained invocation')
    expected='.jarvis-runtime/discovery/imports/'+download['sha256']+'/'+digest+'/inspection-slot-'+str(receipt['slot'])+'.json'
    if receipt['relative_file']!=expected or receipt['original_sha256']!=download['sha256']:raise ValueError('inspection source binding differs')
    raw=local_bytes(base,expected,4_000_000)
    if hashlib.sha256(raw).hexdigest()!=receipt['sha256'] or json.loads(raw)!=record['inspection']:raise ValueError('inspection output changed')
    from .asset_resources import grant
    maximum_cpu=grant(request['resource_grant_sha256'])['parser_cpu_seconds'] if request.get('resource_grant_sha256') else 18
    inspection=validate(record['inspection'],request['source_sha256'],maximum_cpu)
    if len(inspection['parts'])!=receipt['part_count'] or inspection['units_resolved']!=receipt['units_resolved']:
        raise ValueError('inspection summary differs from actual output')
    return {'receipt':receipt,'inspection':inspection}
