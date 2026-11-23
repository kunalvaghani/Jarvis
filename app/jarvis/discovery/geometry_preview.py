"""CPU orthographic diagnostics from the actual qualified mesh inventory.

Decimated source geometry only: neither a beauty render nor a physics result.
No source scripts, model calls, remote assets or GPU context are involved.
"""
import hashlib
import io
from pathlib import Path


def build(base,observed,asset,*,journal=None,grant_sha=None):
    if journal is None:return render(base,observed,asset)
    import time,uuid
    from .adapters.asset_resources import budget as admitted_budget
    budget=admitted_budget(journal,grant_sha);identity='source-diagnostic-'+uuid.uuid4().hex
    budget.reserve(identity,cpu_s=2,disk_bytes=2_000_000)
    existed=(Path(base)/observed['receipt']['relative_file']).with_name('geometry-preview.png').exists()
    started=time.process_time()
    try:
        result=render(base,observed,asset)
        budget.settle(identity,cpu_s=time.process_time()-started,
            disk_bytes=0 if existed else (Path(base)/result['relative_file']).stat().st_size)
        return result
    except BaseException:
        budget.settle(identity,uncertain=True)
        raise


def render(base,observed,asset):
    from PIL import Image,ImageDraw
    from .adapters.assets import local_bytes
    from ..skill_memory import linked
    receipt=observed['receipt'];data=observed['inspection'];base=Path(base).resolve()
    image=Image.new('RGB',(1290,530),'#101b2b');draw=ImageDraw.Draw(image)
    draw.text((18,16),'ACTUAL IMPORTED SOURCE - DECIMATED GEOMETRY DIAGNOSTIC',fill='white')
    draw.text((18,36),'Not a functional rig or physics result. Colors identify geometric inventory only.',fill='#c4d7ea')
    bounds=[[min(p['bounds'][0][i] for p in data['parts']) for i in range(3)],
            [max(p['bounds'][1][i] for p in data['parts']) for i in range(3)]]
    triangles=sum(len(p['preview_triangles']) for p in data['parts'])
    if triangles>5000:raise ValueError('preview triangle budget exceeded')
    for panel,(horizontal,vertical,depth,label) in enumerate(((0,1,2,'X/Y'),(2,1,0,'Z/Y'),(0,2,1,'X/Z'))):
        left=panel*430+15;top=78;width=400;height=360
        scale=min(width/max(1e-9,bounds[1][horizontal]-bounds[0][horizontal]),height/max(1e-9,bounds[1][vertical]-bounds[0][vertical]))
        center=[(a+b)/2 for a,b in zip(*bounds)]
        def project(point):return (left+width/2+(point[horizontal]-center[horizontal])*scale,top+height/2-(point[vertical]-center[vertical])*scale)
        faces=[]
        for part in data['parts']:
            color=tuple(85+v%145 for v in hashlib.sha256(part['component_id'].encode()).digest()[:3])
            for indices in part['preview_triangles']:
                points=[part['preview_vertices'][index] for index in indices]
                faces.append((sum(p[depth] for p in points),[project(p) for p in points],color))
        for _,points,color in sorted(faces,key=lambda face:face[0]):draw.polygon(points,fill=color,outline='#33485c')
        draw.rectangle((left-5,top-5,left+width+5,top+height+5),outline='#668099')
        draw.text((left,top+height+15),label+' orthographic; units: '+data['units'],fill='white')
    draw.text((18,478),f"{len(data['parts'])} geometric records; {triangles} sampled triangles. Original SHA256: {receipt['original_sha256'][:24]}...",fill='white')
    draw.text((18,500),(asset.creator+' | '+asset.license_spdx+' | '+asset.source_url)[:195],fill='#c4d7ea')
    buffer=io.BytesIO();image.save(buffer,format='PNG');raw=buffer.getvalue()
    if len(raw)>2_000_000:raise ValueError('source diagnostic exceeded admitted bytes')
    folder=(base/receipt['relative_file']).parent
    if any(linked(p) for p in (folder,*folder.parents)):raise ValueError('linked diagnostic output refused')
    target=folder/'geometry-preview.png'
    if target.exists():
        if linked(target) or local_bytes(base,target.relative_to(base).as_posix(),2_000_000)!=raw:raise ValueError('retained diagnostic differs')
    else:
        with target.open('xb') as file:file.write(raw)
    return {'relative_file':target.relative_to(base).as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),
        'inspection_sha256':receipt['sha256'],'original_sha256':receipt['original_sha256'],
        'scope':'actual decimated source projection only; no functional or physical validation'}
