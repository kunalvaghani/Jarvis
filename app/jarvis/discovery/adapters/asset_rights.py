"""Re-derivable per-asset rights evidence, never a permission or physical proof.

Consumes only captured official provider snapshots. A repository code license
alone is insufficient: GitHub assets require a per-asset manifest or REUSE
sidecar. Sketchfab rights remain separate from authenticated file availability.
"""
import base64
import hashlib
import json
from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs,quote,urlsplit
from .provider_metadata import load
from .asset_files import member_path
from ..model.acquisition import Acquisition

LICENSE_URLS={'CC0-1.0':'https://creativecommons.org/publicdomain/zero/1.0/',
    'CC-BY-4.0':'https://creativecommons.org/licenses/by/4.0/',
    'MIT':'https://opensource.org/license/mit',
    'BSD-3-Clause':'https://opensource.org/license/bsd-3-clause',
    'Apache-2.0':'https://www.apache.org/licenses/LICENSE-2.0'}
FORMATS=frozenset({'glb','gltf','obj','stl','ply','step','stp','zip'})


def named_year(text):
    text=re.sub(r'20\d{2}[-_/]\d{2}[-_/]\d{2}','',text)
    text=re.sub(r'[_-]+',' ',text)
    if re.search(r'(?i)copyright|published|updated|created',text):return None
    if len(set(re.findall(r'(?<!\d)20\d{2}(?!\d)',text)))!=1:return None
    noun=r'(?:F1|Formula\s*(?:1|one)|car|vehicle|robot|engine|drone|mechanism)'
    values=re.findall(r'(?i)(?<!\d)(20\d{2})(?!\d).{0,30}?'+noun+'|'+noun+r'.{0,30}?(?<!\d)(20\d{2})(?!\d)',text)
    years={int(value) for pair in values for value in pair if value}
    return next(iter(years)) if len(years)==1 else None


def blob_text(data):
    if not isinstance(data,dict) or data.get('type')!='file' or data.get('encoding')!='base64':
        raise ValueError('actual text-file provider record required')
    content=data.get('content')
    if not isinstance(content,str) or len(content)>300000:raise ValueError('license evidence exceeds text budget')
    raw=base64.b64decode(''.join(content.split()),validate=True)
    if len(raw)>200000 or data.get('size')!=len(raw):raise ValueError('license evidence size differs')
    sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if data.get('sha')!=sha:raise ValueError('license text differs from provider Git blob identity')
    return raw.decode('utf-8-sig')


def _github(base,journal,proof):
    owner,repo,revision,path=(proof[k] for k in ('owner','repo','revision','path'))
    if not all(re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',v) for v in (owner,repo)) or not re.fullmatch(r'[a-f0-9]{40}',revision):
        raise ValueError('canonical repository identity/revision required')
    member_path(path);kind=PurePosixPath(path).suffix.lower().lstrip('.')
    if kind not in FORMATS:raise ValueError('asset format is outside the inert acquisition policy')
    root=f'https://api.github.com/repos/{owner}/{repo}'
    tree_record,tree=load(base,journal,proof['tree_ref'])
    tp=urlsplit(tree_record['endpoint'])
    if tree_record['provider']!='github' or tp.scheme+'://'+tp.netloc+tp.path!=root+'/git/trees/'+revision:
        raise ValueError('asset tree is not bound to selected repository revision')
    if not isinstance(tree,dict) or not isinstance(tree.get('tree'),list):raise ValueError('actual repository tree required')
    selected=[row for row in tree['tree'] if isinstance(row,dict) and row.get('path')==path]
    if len(selected)!=1 or selected[0].get('type')!='blob' or selected[0].get('mode') not in ('100644','100755'):
        raise ValueError('model is not a unique regular blob in captured revision')
    item=selected[0]
    if (not re.fullmatch(r'[a-f0-9]{40}',str(item.get('sha',''))) or type(item.get('size')) is not int
            or not 4<=item['size']<=20_000_000):
        raise ValueError('asset blob identity or size unsupported')
    rights_record,rights=load(base,journal,proof['rights_ref']);rp=urlsplit(rights_record['endpoint'])
    wanted=root+'/contents/'+quote(rights['path'],safe='/')
    if rights_record['provider']!='github' or rp.scheme+'://'+rp.netloc+rp.path!=wanted or parse_qs(rp.query).get('ref')!=[revision]:
        raise ValueError('asset license declaration is not pinned to selected revision')
    text=blob_text(rights);expected_sha=None;year=None;title=PurePosixPath(path).name;identity='unknown'
    if proof['rule']=='github-asset-manifest-v1':
        if PurePosixPath(rights['path']).name not in ('ASSET_LICENSES.json','MODEL_LICENSES.json'):
            raise ValueError('recognized per-asset declaration required')
        doc=json.loads(text)
        if doc.get('version')!=1 or not isinstance(doc.get('assets'),list) or len(doc['assets'])>256:
            raise ValueError('unsupported per-asset rights manifest')
        entries=[x for x in doc['assets'] if isinstance(x,dict) and x.get('path')==path]
        if len(entries)!=1:raise ValueError('asset has no unique per-file license declaration')
        entry=entries[0];license=entry.get('license');creator=entry.get('creator');title=entry.get('title',title)
        year=entry.get('year');expected_sha=entry.get('sha256');identity=entry.get('identity_status','unknown')
        if identity not in ('author_declared_replica','author_declared_concept','unknown'):identity='unknown'
    elif proof['rule']=='github-reuse-sidecar-v1':
        if rights['path']!=path+'.license':raise ValueError('REUSE sidecar belongs to another asset')
        licenses=re.findall(r'^SPDX-License-Identifier:\s*(\S+)\s*$',text,re.M)
        authors=re.findall(r'^SPDX-FileCopyrightText:\s*(.+?)\s*$',text,re.M)
        if len(licenses)!=1 or not authors:raise ValueError('unambiguous per-file SPDX grant and attribution required')
        license=licenses[0];creator='; '.join(authors)
        # A copyright date never establishes the object's model year.
        year=named_year(PurePosixPath(path).name)
    else:raise ValueError('unsupported per-asset license evidence rule')
    if license not in LICENSE_URLS or not isinstance(creator,str) or not creator.strip() or not isinstance(title,str):
        raise ValueError('supported explicit asset rights and creator required')
    if year is not None and (type(year) is not int or not 1800<=year<=2200):raise ValueError('invalid declared object year')
    if named_year(title) not in (None,year):raise ValueError('source title contradicts declared object year')
    source=f'https://github.com/{owner}/{repo}/blob/{revision}/'+quote(path,safe='/')
    return ({'candidate_id':'github:'+hashlib.sha256(source.encode()).hexdigest(),'provider':'github','source_url':source,
        'creator':creator,'license_spdx':license,'license_url':LICENSE_URLS[license],
        'attribution':f'{creator}; {title}; {source}; {license}', 'file_format':kind,
        'maximum_bytes':item['size'],'expected_sha256':expected_sha,'identity_status':identity,'year':year},
        {'blob_sha1':item['sha'],'revision':revision,'title':title,
         'download_url':f'https://raw.githubusercontent.com/{owner}/{repo}/{revision}/'+quote(path,safe='/'),
         'download_hosts':['raw.githubusercontent.com']})


def _sketchfab(base,journal,proof):
    record,model=load(base,journal,proof['model_ref']);uid=proof['uid']
    if record['provider']!='sketchfab' or record['endpoint']!='https://api.sketchfab.com/v3/models/'+uid or model.get('uid')!=uid:
        raise ValueError('actual selected Sketchfab model metadata required')
    catalog_record,catalog=load(base,journal,proof['licenses_ref'])
    if catalog_record['endpoint']!='https://api.sketchfab.com/v3/licenses':raise ValueError('official license catalog required')
    rows=catalog.get('results') if isinstance(catalog,dict) else catalog
    def license_identity(value):
        if not isinstance(value,dict):return None
        uid=value.get('uid');uri=value.get('uri')
        if uri is not None:
            match=re.fullmatch(r'https://api\.sketchfab\.com/v3/licenses/([a-f0-9]{32})',str(uri))
            if not match or (uid is not None and uid!=match[1]):raise ValueError('model license identity contradicts canonical provider URI')
            uid=match[1]
        return uid if isinstance(uid,str) and re.fullmatch(r'[a-f0-9]{32}',uid) else None
    declared=model.get('license');license_id=license_identity(declared)
    if not isinstance(rows,list) or not license_id:raise ValueError('model license identity missing')
    selected=[row for row in rows if license_identity(row)==license_id]
    if len(selected)!=1:raise ValueError('model license is not unique in official catalog')
    uri=selected[0].get('url','').replace('http://creativecommons.org/','https://creativecommons.org/')
    license=next((name for name,url in LICENSE_URLS.items() if uri.rstrip('/')==url.rstrip('/')),None)
    if license is None:raise ValueError('license version or permitted rights unresolved')
    creator=(model.get('user') or {}).get('username');title=model.get('name','');source=model.get('viewerUrl','')
    p=urlsplit(source)
    if p.hostname not in ('sketchfab.com','www.sketchfab.com') or not p.path.endswith(uid):raise ValueError('model viewer provenance differs')
    year=named_year(title)
    maximum_bytes=20_000_000
    if proof.get('resource_grant_sha256'):
        from .asset_resources import grant
        permission=grant(proof['resource_grant_sha256'])
        if year not in (2025,2026) or not re.search(r'(?i)\bF1\b|\bFormula\s*(?:1|one)\b',title):
            raise ValueError('resource approval is scoped to full-A vehicle assets')
        maximum_bytes=permission['maximum_asset_bytes']
    identity='author_declared_concept' if re.search(r'\b(?:concept|inspired)\b',title+' '+str(model.get('description','')),re.I) else 'unknown'
    return ({'candidate_id':'sketchfab:'+uid,'provider':'sketchfab','source_url':source,
        'creator':creator,'license_spdx':license,'license_url':LICENSE_URLS[license],
        'attribution':f'{creator}; {title}; {source}; {license}', 'file_format':'zip',
        'maximum_bytes':maximum_bytes,'expected_sha256':None,'identity_status':identity,'year':year},
        {'title':title,'downloadable_declared':model.get('isDownloadable') is True,
         'download_status':'BLOCKED_PROVIDER_AUTHENTICATION','download_url':None,
         'download_hosts':['media.sketchfab.com'],'revision':record['sha256'],'accepted_download_formats':['zip','glb']})


def derive(base,journal,proof):
    if proof.get('rule') in ('github-asset-manifest-v1','github-reuse-sidecar-v1'):return _github(base,journal,proof)
    if proof.get('rule')=='sketchfab-license-v1':return _sketchfab(base,journal,proof)
    raise ValueError('unknown per-asset rights proof')


def issue(base,journal,proof,*,target_year=None):
    data,availability=derive(base,journal,proof)
    if target_year is not None and data['year']!=target_year:raise ValueError('source does not declare the required object year')
    if data['provider']=='sketchfab' and target_year in (2025,2026) and not proof.get('resource_grant_sha256'):
        from .asset_resources import applicable
        permission=applicable(target_year,availability['title'])
        if permission:
            proof={**proof,'resource_grant_sha256':permission['sha256']};data,availability=derive(base,journal,proof)
    proof_ref=journal.put(proof,'Report');asset=Acquisition(**data,evidence_ref=proof_ref)
    return journal.put(asset.model_dump(mode='json'),'Report'),availability


def verify(base,journal,ref):
    from ..acceptance import artifact
    asset=Acquisition.model_validate_json(json.dumps(artifact(journal,ref)))
    proof=artifact(journal,asset.evidence_ref);data,availability=derive(base,journal,proof)
    expected=Acquisition(**data,evidence_ref=asset.evidence_ref)
    if asset!=expected:raise ValueError('asset admission differs from captured per-file rights evidence')
    return asset,availability
