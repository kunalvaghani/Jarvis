"""Fixed CPU data-only mesh inspector for the approved isolated tool environment.

Input is bounded model bytes, never scripts, executable formats or host paths.
Resource limits are supplied by the parent Windows Job Object. Audit hooks are
additional restrictions, not an OS security sandbox.
"""
import base64
import hashlib
import io
import json
import math
import os
import posixpath
import re
import struct
import sys
import time
from urllib.parse import unquote,urlsplit
from pathlib import Path


class Rejected(ValueError):pass


def decode(value,limit):
    if not isinstance(value,str) or len(value)>4*((limit+2)//3):raise Rejected('INPUT_BYTE_LIMIT')
    raw=base64.b64decode(value,validate=True)
    if len(raw)>limit:raise Rejected('INPUT_BYTE_LIMIT')
    return raw


def gltf_preflight(raw,kind,entrypoint,resources,*,approved=False):
    vertex_limit=2_000_000 if approved else 1_000_000
    face_limit=2_000_000 if approved else 500_000
    buffer_limit=100_000_000 if approved else 25_000_000
    tail=b''
    if kind=='glb':
        if len(raw)<28:raise Rejected('TRUNCATED_GLB')
        magic,version,total,length,tag=struct.unpack_from('<4sIII4s',raw)
        if magic!=b'glTF' or version!=2 or total!=len(raw) or tag!=b'JSON' or length>2_000_000 or 20+length>len(raw):raise Rejected('INVALID_GLB_HEADER')
        doc=json.loads(raw[20:20+length]);tail=raw[20+length:]
    else:
        if len(raw)>2_000_000:raise Rejected('GLTF_METADATA_LIMIT')
        doc=json.loads(raw)
    if not isinstance(doc,dict) or doc.get('asset',{}).get('version')!='2.0':raise Rejected('GLTF_VERSION')
    allowed={'KHR_materials_unlit','KHR_materials_transmission','KHR_materials_clearcoat','KHR_materials_specular',
        'KHR_materials_ior','KHR_materials_sheen','KHR_materials_volume','KHR_texture_transform','KHR_lights_punctual','KHR_materials_emissive_strength'}
    if not set(doc.get('extensionsRequired',[]))<=allowed:raise Rejected('UNSUPPORTED_GLTF_EXTENSION')
    nodes=doc.get('nodes',[]);meshes=doc.get('meshes',[]);accessors=doc.get('accessors',[])
    if len(nodes)>4096 or len(meshes)>2048 or len(accessors)>10000:raise Rejected('SCENE_COMPLEXITY_LIMIT')
    labels={};parents={};visiting=set();done=set();vertices=0;faces=0
    def visit(index,depth=0):
        if type(index) is not int or not 0<=index<len(nodes) or depth>64 or index in visiting:raise Rejected('INVALID_NODE_GRAPH')
        if index in done:return
        visiting.add(index);node=nodes[index]
        values=[]
        for key,size in [('matrix',16),('translation',3),('rotation',4),('scale',3)]:
            if key in node:
                value=node[key]
                if not isinstance(value,list) or len(value)!=size or any(type(x) not in (int,float) or not math.isfinite(x) for x in value):raise Rejected('INVALID_TRANSFORM')
                values.extend(value)
        if 'matrix' in node and any(key in node for key in ('translation','rotation','scale')):raise Rejected('AMBIGUOUS_TRANSFORM')
        if 'matrix' in node and any(abs(node['matrix'][i]-value)>1e-9 for i,value in ((3,0),(7,0),(11,0),(15,1))):raise Rejected('NONAFFINE_TRANSFORM')
        if 'rotation' in node and abs(sum(x*x for x in node['rotation'])-1)>1e-4:raise Rejected('NONUNIT_ROTATION')
        for child in node.get('children',[]):
            if child in parents and parents[child]!=index:raise Rejected('MULTIPLE_NODE_PARENTS')
            parents[child]=index;visit(child,depth+1)
        visiting.remove(index);done.add(index)
    for i in range(len(nodes)):visit(i)
    for i in range(len(nodes)):
        current=i;depth=0
        while current in parents:
            current=parents[current];depth+=1
            if depth>64:raise Rejected('NODE_DEPTH_LIMIT')
    buffers=doc.get('buffers',[])
    if len(buffers)>256 or len(doc.get('bufferViews',[]))>10000:raise Rejected('BUFFER_COUNT_LIMIT')
    for buffer in buffers:
        if type(buffer.get('byteLength')) is not int or not 0<=buffer['byteLength']<=buffer_limit:raise Rejected('BUFFER_BYTE_LIMIT')
    for view in doc.get('bufferViews',[]):
        b=view.get('buffer');offset=view.get('byteOffset',0);size=view.get('byteLength')
        if type(b) is not int or not 0<=b<len(buffers) or type(offset) is not int or type(size) is not int or min(offset,size)<0 or offset+size>buffers[b]['byteLength']:
            raise Rejected('BUFFER_VIEW_BOUNDS')
    for accessor in accessors:
        if type(accessor.get('count')) is not int or not 0<=accessor['count']<=(6_000_000 if approved else 1_500_000):raise Rejected('ACCESSOR_COUNT_LIMIT')
    for i,node in enumerate(nodes):
        labels['source-node-'+str(i)]=str(node.get('name','unnamed node'))[:200]
        node['name']='source-node-'+str(i)
        if 'mesh' in node:
            index=node['mesh']
            if type(index) is not int or not 0<=index<len(meshes):raise Rejected('INVALID_MESH_REFERENCE')
            for primitive in meshes[index].get('primitives',[]):
                if primitive.get('mode',4)!=4:raise Rejected('NONTRIANGLE_PRIMITIVE')
                a=primitive.get('attributes',{}).get('POSITION')
                if type(a) is not int or not 0<=a<len(accessors):raise Rejected('POSITION_ACCESSOR_MISSING')
                position=accessors[a]
                if position.get('type')!='VEC3' or position.get('componentType')!=5126 or 'sparse' in position:raise Rejected('UNSUPPORTED_POSITION_ENCODING')
                count=position.get('count')
                if type(count) is not int or not 0<count<=vertex_limit:raise Rejected('VERTEX_LIMIT')
                vertices+=count
                indices=primitive.get('indices')
                count=accessors[indices].get('count',0) if type(indices) is int and 0<=indices<len(accessors) else count
                if type(count) is not int or count<0:raise Rejected('INVALID_INDEX_COUNT')
                faces+=count//3
    if vertices>vertex_limit or faces>face_limit:raise Rejected('EXPANDED_GEOMETRY_LIMIT')
    for i,mesh in enumerate(meshes):mesh['name']='source-mesh-'+str(i)
    resolved={}
    for item in [*doc.get('buffers',[]),*doc.get('images',[])]:
        uri=item.get('uri')
        if uri is None:continue
        if not isinstance(uri,str) or len(uri)>30_000_000 or any(ord(c)<32 for c in uri):raise Rejected('INVALID_RESOURCE_URI')
        if uri.startswith('data:'):
            if not re.match(r'^data:(?:application/octet-stream|application/gltf-buffer|image/png|image/jpeg);base64,',uri):raise Rejected('UNSUPPORTED_EMBEDDED_RESOURCE')
            continue
        p=urlsplit(uri);decoded=unquote(p.path)
        name=posixpath.normpath(posixpath.join(posixpath.dirname(entrypoint),decoded))
        if p.scheme or p.netloc or p.query or p.fragment or decoded.startswith('/') or name.startswith('../') or ':' in name or '\\' in name:
            raise Rejected('EXTERNAL_OR_ESCAPING_RESOURCE')
        if name not in resources:raise Rejected('REFERENCED_RESOURCE_MISSING')
        resolved[uri]=resources[name]
    encoded=json.dumps(doc,separators=(',',':'),allow_nan=False).encode()
    if kind=='glb':
        encoded+=b' '*((-len(encoded))%4)
        raw=struct.pack('<4sII',b'glTF',2,20+len(encoded)+len(tail))+struct.pack('<I4s',len(encoded),b'JSON')+encoded+tail
    else:raw=encoded
    return raw,resolved,labels,{'nodes':len(nodes),'meshes':len(meshes),'animations_present':bool(doc.get('animations')),'skins_present':bool(doc.get('skins'))}


def groups(vertices,faces,metadata=None,limit=500):
    parent=list(range(len(vertices)));seen={}
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def join(a,b):
        a,b=root(a),root(b)
        if a!=b:parent[b]=a
    # Exact coincident vertices join UV seams geometrically, not mechanically.
    for i,point in enumerate(vertices):
        key=tuple(point);previous=seen.get(key)
        if previous is None:seen[key]=i
        else:join(i,previous)
    for a,b,c in faces:join(int(a),int(b));join(int(a),int(c))
    result={}
    for i,face in enumerate(faces):result.setdefault(root(int(face[0])),[]).append(i)
    if metadata is not None:metadata.update(connected_regions=len(result),aggregated=len(result)>limit)
    # Dense visual sources may contain thousands of disconnected decorative
    # fragments. Retain that source node as one explicitly disconnected visual
    # aggregate; never claim a mechanical part or merge/rewrite original bytes.
    # The output inventory and preview remain bounded at 500/5000 respectively.
    if len(result)>limit:return [list(range(len(faces)))]
    return list(result.values())


def inspect(payload):
    started=time.process_time()
    required={'format','body','source_sha256','entrypoint','resources','length_unit'}
    if not isinstance(payload,dict) or set(payload) not in (required,required|{'resource_grant_sha256'}):raise Rejected('INPUT_SCHEMA')
    approved=False
    if payload.get('resource_grant_sha256'):
        permission_path=Path(__file__).resolve().parents[3]/'.jarvis-runtime/discovery/asset-authorizations/full-a-2026-11-06/authorization.json'
        if permission_path.is_symlink() or permission_path.stat().st_size>16000:raise Rejected('RESOURCE_APPROVAL_INVALID')
        permission_raw=permission_path.read_bytes();permission=json.loads(permission_raw)
        if (hashlib.sha256(permission_raw).hexdigest()!=payload['resource_grant_sha256'] or permission.get('approved') is not True
                or permission.get('scope')!='user-approved-full-a-assets-2026-11-06' or permission.get('maximum_parser_input_bytes')!=100_000_000
                or permission.get('parser_memory_bytes')!=2*1024**3 or permission.get('parser_cpu_seconds')!=60):raise Rejected('RESOURCE_APPROVAL_INVALID')
        approved=True
    input_limit=100_000_000 if approved else 20_000_000
    vertex_limit=2_000_000 if approved else 1_000_000;face_limit=2_000_000 if approved else 500_000
    kind=payload['format']
    if kind not in ('glb','gltf','obj','stl'):raise Rejected('IMPORTER_UNAVAILABLE')
    raw=decode(payload['body'],input_limit)
    if hashlib.sha256(raw).hexdigest()!=payload['source_sha256']:raise Rejected('SOURCE_HASH_MISMATCH')
    if not isinstance(payload['resources'],dict) or len(payload['resources'])>256:raise Rejected('RESOURCE_COUNT_LIMIT')
    resources={};resource_bytes=0
    for name,value in payload['resources'].items():
        if not isinstance(name,str) or len(name)>1024:raise Rejected('RESOURCE_NAME_LIMIT')
        remaining=(input_limit-len(raw)-resource_bytes) if approved else 25_000_000-resource_bytes
        if remaining<0:raise Rejected('RESOURCE_BYTE_LIMIT')
        data=decode(value,min(input_limit,remaining))
        resource_bytes+=len(data);resources[name]=data
    labels={};structure={}
    if kind in ('glb','gltf'):raw,resources,labels,structure=gltf_preflight(raw,kind,payload['entrypoint'],resources,approved=approved)
    elif kind=='obj':
        for line in raw.splitlines():
            if len(line)>8192:raise Rejected('OBJ_LINE_LIMIT')
            if line.startswith(b'f ') and len(line.split())>33:raise Rejected('OBJ_POLYGON_LIMIT')
        if raw.count(b'\nv ') + int(raw.startswith(b'v '))>vertex_limit or raw.count(b'\nf ')>face_limit:raise Rejected('EXPANDED_GEOMETRY_LIMIT')
    elif len(raw)>=84 and 84+50*struct.unpack_from('<I',raw,80)[0]==len(raw):
        if struct.unpack_from('<I',raw,80)[0]>face_limit:raise Rejected('EXPANDED_GEOMETRY_LIMIT')
    import numpy as np
    import trimesh
    if trimesh.__version__!='5.2.0':raise Rejected('UNQUALIFIED_GEOMETRY_VERSION')
    scene=trimesh.load_scene(io.BytesIO(raw),file_type=kind,resolver=resources,allow_remote=False,skip_materials=True,process=False)
    units='m' if kind in ('glb','gltf') else payload['length_unit']
    if units not in ('m','cm','mm','unknown'):raise Rejected('UNSUPPORTED_UNITS')
    factor={'m':1.,'cm':.01,'mm':.001,'unknown':1.}[units]
    output=[];geometry_data=[];remaining=5000;total_vertices=0;total_faces=0
    source_nodes=sorted(scene.graph.nodes_geometry)
    if len(source_nodes)>500:raise Rejected('SOURCE_NODE_LIMIT')
    for node_index,node in enumerate(source_nodes):
        matrix,geometry=scene.graph.get(node);mesh=scene.geometry[geometry]
        if not isinstance(mesh,trimesh.Trimesh) or not len(mesh.faces):raise Rejected('UNSUPPORTED_NONMESH_GEOMETRY')
        total_vertices+=len(mesh.vertices);total_faces+=len(mesh.faces)
        if total_vertices>vertex_limit or total_faces>face_limit:raise Rejected('EXPANDED_GEOMETRY_LIMIT')
        points=trimesh.transform_points(mesh.vertices,matrix)*factor
        if not np.isfinite(points).all() or np.abs(points).max()>10000 or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix[:3,:3]))<1e-12:
            raise Rejected('INVALID_WORLD_GEOMETRY')
        if mesh.faces.min()<0 or mesh.faces.max()>=len(points):raise Rejected('INVALID_FACE_REFERENCE')
        connectivity={}
        available=500-len(output)-(len(source_nodes)-node_index-1)
        for indices in groups(points,mesh.faces,connectivity,limit=available):
            faces=mesh.faces[indices];used=np.unique(faces.reshape(-1));bounds=np.array([points[used].min(axis=0),points[used].max(axis=0)])
            semantic=next((label for key,label in labels.items() if node==key or node.startswith(key+'_')),str(node)[:200] if kind not in ('glb','gltf') else 'unnamed geometry')
            identity=hashlib.sha256(payload['source_sha256'].encode()+str(node).encode()+points[used].tobytes()+faces.tobytes()).hexdigest()
            local=trimesh.Trimesh(vertices=points[used],faces=np.searchsorted(used,faces),process=False)
            closed=bool(local.is_watertight);winding=bool(local.is_winding_consistent)
            volume=abs(float(local.volume)) if closed and winding and units!='unknown' else None
            output.append({'component_id':'geometry-'+identity[:32],'source_name':semantic,'source_node':str(node)[:200],
                'vertex_count':len(used),'triangle_count':len(faces),'bounds':bounds.tolist(),'center':bounds.mean(axis=0).tolist(),
                'mechanical_role':'UNRESOLVED','mass_kg':None,'inertia_kg_m2':None,'joints_verified':False,
                'geometric_connectivity':'DISCONNECTED_SOURCE_NODE_AGGREGATE' if connectivity['aggregated'] else 'CONNECTED_REGION',
                'connected_regions':connectivity['connected_regions'] if connectivity['aggregated'] else 1,
                'watertight':closed,'winding_consistent':winding,'enclosed_volume_if_watertight_m3':volume})
            geometry_data.append((points,faces))
            if len(output)>500:raise Rejected('GEOMETRIC_COMPONENT_LIMIT')
        if time.process_time()-started>(55 if approved else 16):raise Rejected('INSPECTION_CPU_LIMIT')
    if not output:raise Rejected('NO_TRIANGULATED_GEOMETRY')
    for index,(record,(points,faces)) in enumerate(zip(output,geometry_data)):
        take=min(remaining-(len(output)-index-1),max(1,math.floor(len(faces)*5000/total_faces)))
        stride=max(1,math.ceil(len(faces)/take));preview=[];preview_points=[];lookup={}
        for face in faces[::stride][:take]:
            triangle=[]
            for vertex in face:
                key=int(vertex)
                if key not in lookup:lookup[key]=len(preview_points);preview_points.append(points[key].tolist())
                triangle.append(lookup[key])
            preview.append(triangle)
        remaining-=len(preview);record.update(preview_vertices=preview_points,preview_triangles=preview)
    return {'parser':'trimesh','version':trimesh.__version__,'source_sha256':payload['source_sha256'],
        'cpu_s':time.process_time()-started,'parts':output,'structure':structure,'units':units,
        'units_resolved':units!='unknown','frame':'gltf_y_up' if kind in ('glb','gltf') else 'source_axes_unresolved',
        'preview_decimated':True,'original_modified':False,'physical_validation':False,
        'disassembly_scope':'Source hierarchy and exact connectivity; dense disconnected source nodes remain labelled visual aggregates. No verified mechanical joints.'}


def main():
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
    raw=sys.stdin.buffer.read(160_000_001)
    if len(raw)>160_000_000:raise Rejected('INPUT_BYTE_LIMIT')
    payload=json.loads(raw)
    def guard(event,args):
        if event in ('socket.connect','socket.sendto','socket.bind','subprocess.Popen','os.system','os.startfile'):
            raise Rejected('INSPECTOR_NETWORK_OR_PROCESS_REFUSED')
    sys.addaudithook(guard)
    print(json.dumps(inspect(payload),allow_nan=False,separators=(',',':')))


if __name__=='__main__':
    started=time.process_time()
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'REJECTED','error_type':type(exc).__name__,
            'code':str(exc) if isinstance(exc,Rejected) else 'PARSER_OR_CONTRACT_FAILURE',
            'cpu_s':time.process_time()-started}))
