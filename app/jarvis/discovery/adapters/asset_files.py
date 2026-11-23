"""Bounded inert-file and ZIP inspection; never imports or executes asset code."""
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import stat
import struct
import zipfile

MAXIMUM=20_000_000
MEMBERS=frozenset({'.glb','.gltf','.bin','.obj','.mtl','.stl','.ply','.step','.stp','.png','.jpg','.jpeg','.txt','.md','.license','.json'})


def member_path(name):
    if not isinstance(name,str) or not name or len(name)>240 or '\\' in name or ':' in name or any(ord(c)<32 for c in name):
        raise ValueError('unsafe archive path')
    path=PurePosixPath(name)
    if path.is_absolute() or len(path.parts)>8 or any(p in ('.','..') or p.endswith(('.', ' ')) for p in path.parts):
        raise ValueError('archive path escapes or is not portable')
    if any(re.fullmatch(r'(?i)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',p) for p in path.parts):
        raise ValueError('reserved Windows archive filename')
    return path


def archive_inventory(raw,*,maximum=MAXIMUM):
    if type(maximum) is not int or not 4<=maximum<=100_000_000:raise ValueError('bounded archive admission required')
    if not isinstance(raw,bytes) or len(raw)>maximum:raise ValueError('bounded archive bytes required')
    # Bound the central directory before ZipFile allocates one object per row.
    end=raw.rfind(b'PK\x05\x06',max(0,len(raw)-65557))
    if end<0 or len(raw)-end<22:raise ValueError('ZIP end record missing')
    _,disk,start_disk,on_disk,count,size,offset,comment=struct.unpack_from('<4s4H2IH',raw,end)
    if (disk or start_disk or on_disk!=count or not 1<=count<=256 or size>256_000
            or offset+size!=end or comment>1024 or end+22+comment!=len(raw)):
        raise ValueError('ZIP central directory exceeds bounded single-volume policy')
    rows=[];names=set();expanded=0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members=archive.infolist()
        if not members or len(members)>256:raise ValueError('archive entry count exceeds policy')
        for item in members:
            path=member_path(item.filename)
            normalized=str(path).casefold()
            if normalized in names:raise ValueError('duplicate or case-colliding archive entry')
            names.add(normalized)
            mode=stat.S_IFMT(item.external_attr>>16)
            if mode not in (0,stat.S_IFREG,stat.S_IFDIR) or item.flag_bits&1:
                raise ValueError('linked, special or encrypted archive member refused')
            if item.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):raise ValueError('unsupported archive compression')
            if item.is_dir():continue
            if path.suffix.lower() not in MEMBERS:raise ValueError('executable, script or unsupported archive member refused')
            expanded+=item.file_size
            if item.file_size>maximum or expanded>(maximum if maximum>MAXIMUM else 25_000_000) or item.file_size>max(1024,item.compress_size*100):
                raise ValueError('archive expansion exceeds policy')
            digest=hashlib.sha256();count=0
            with archive.open(item) as stream:
                while True:
                    chunk=stream.read(65536)
                    if not chunk:break
                    count+=len(chunk)
                    if count>item.file_size:raise ValueError('archive member exceeded declared bounds')
                    digest.update(chunk)
            if count!=item.file_size:raise ValueError('archive member is incomplete')
            rows.append({'path':str(path),'bytes':count,'sha256':digest.hexdigest()})
    if not rows:raise ValueError('archive has no eligible files')
    return {'entries':rows,'expanded_bytes':expanded,'code_executed':False,'extracted':False}


def inspect(raw,kind,*,maximum=MAXIMUM):
    if type(maximum) is not int or not 4<=maximum<=100_000_000:raise ValueError('bounded inert admission required')
    if not isinstance(raw,bytes) or not 4<=len(raw)<=maximum:raise ValueError('bounded inert asset required')
    if raw.startswith((b'MZ',b'\x7fELF',b'#!')):raise ValueError('program content is not a model asset')
    facts={'file_format':kind,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'code_executed':False,'geometry_imported':False}
    if kind=='zip':return {**facts,'archive':archive_inventory(raw,maximum=maximum)}
    if kind=='glb':
        if len(raw)<28:raise ValueError('truncated GLB')
        magic,version,total=struct.unpack_from('<4sII',raw)
        length,chunk=struct.unpack_from('<I4s',raw,12)
        if magic!=b'glTF' or version!=2 or total!=len(raw) or chunk!=b'JSON' or length>2_000_000 or length+20>len(raw):
            raise ValueError('invalid GLB header/chunk')
        data=json.loads(raw[20:20+length]);asset=data.get('asset',{})
        if asset.get('version')!='2.0':raise ValueError('unsupported glTF version')
        facts['required_extensions']=data.get('extensionsRequired',[])
    elif kind=='gltf':
        if len(raw)>2_000_000:raise ValueError('glTF metadata exceeds parser allowance')
        data=json.loads(raw)
        if data.get('asset',{}).get('version')!='2.0':raise ValueError('unsupported glTF JSON')
        facts['required_extensions']=data.get('extensionsRequired',[])
    elif kind=='stl':
        binary=len(raw)>=84 and 84+50*struct.unpack_from('<I',raw,80)[0]==len(raw)
        if not binary and not (raw.lstrip().startswith(b'solid') and b'facet' in raw and b'endsolid' in raw):
            raise ValueError('invalid STL structure')
    elif kind=='obj':
        text=raw.decode('utf-8-sig')
        if not re.search(r'^v\s+[-+.\d]',text,re.M) or not re.search(r'^f\s+\d',text,re.M):raise ValueError('OBJ requires vertices and faces')
    elif kind=='ply':
        if not raw.startswith(b'ply') or b'end_header' not in raw[:65536]:raise ValueError('invalid PLY header')
    elif kind in ('step','stp'):
        if not raw.lstrip().startswith(b'ISO-10303-21;') or b'END-ISO-10303-21;' not in raw:raise ValueError('invalid STEP exchange header')
    else:raise ValueError('file format has no qualified inert-file check')
    return facts
