"""Reviewed procedural visual geometry, linked by IDs to the physical model.

An educational envelope surrogate, not reverse-engineered team bodywork. PNGs
are labelled mesh diagnostics, not screenshots or simulation validation.
"""
import base64,hashlib,json,math,struct
from pathlib import Path


def box(center,size):
    x,y,z=center;a,b,c=(v/2 for v in size)
    vertices=[[x+i*a,y+j*b,z+k*c] for i,j,k in
        [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    faces=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]]
    return vertices,faces


def cylinder(center,radius,width,n=24):
    x,y,z=center
    vertices=[[x,y-width/2,z],[x,y+width/2,z]]
    for side in (-1,1):
        vertices.extend([[x+radius*math.cos(2*math.pi*i/n),y+side*width/2,z+radius*math.sin(2*math.pi*i/n)] for i in range(n)])
    faces=[]
    for i in range(n):
        a=2+i;b=2+(i+1)%n;c=2+n+i;d=2+n+(i+1)%n
        faces.extend([[0,a,b],[1,d,c],[a,c,d],[a,d,b]])
    return vertices,faces


def components(case):
    data=case.model_dump(mode='json') if hasattr(case,'model_dump') else case
    wb=data['wheelbase_m'];track=data['track_m'];r=data['wheel_radius_m'];w=data['wheel_width_m']
    items=[]
    def add(identity,kind,shape,physical):
        items.append({'component_id':identity,'kind':kind,'vertices':shape[0],'triangles':shape[1],
            'physical_binding':physical,'geometry_origin':'explicit procedural envelope assumption'})
    add('chassis','chassis',box((0,0,.55),(wb*.85,.7,.3)),'chassis.json')
    add('front-wing','aero',box((wb*.6,0,.23),(.35,track+.1,.06)),'front aero coefficient load port')
    angle=math.radians(data['corner']['front_flap_angle_deg'])
    wing=items[-1]
    wing['vertices']=[[wb*.6+(p[0]-wb*.6)*math.cos(angle)+(p[2]-.23)*math.sin(angle),p[1],
        .23-(p[0]-wb*.6)*math.sin(angle)+(p[2]-.23)*math.cos(angle)] for p in wing['vertices']]
    wing['front_flap_angle_deg']=data['corner']['front_flap_angle_deg']
    add('rear-wing','aero',box((-wb*.55,0,.8),(.3,track*.7,.08)),'rear aero coefficient load port')
    for axle,x in [('front',wb/2),('rear',-wb/2)]:
        for side,y in [('left',track/2),('right',-track/2)]:
            identity=f'{axle}-{side}-wheel'
            add(identity,'wheel',cylinder((x,y,r),r,w),f'{axle}/{side}: wheel.json + tire.json')
            add(f'{axle}-{side}-suspension','suspension',box((x,y/2,.4),(.04,abs(y),.04)),
                f'{axle}/{side}: suspension.json double-wishbone joints, not a visual skeleton')
    return items


def validate(items,case):
    if len([i for i in items if i['kind']=='wheel'])!=4:raise ValueError('four visual wheels required')
    for item in items:
        if not item['physical_binding']:raise ValueError('missing visual/physical binding')
        v=item['vertices'];edges={}
        for tri in item['triangles']:
            if len(set(tri))!=3 or any(type(i) is not int or i<0 or i>=len(v) for i in tri):raise ValueError('invalid mesh indices')
            p,q,r=[v[i] for i in tri]
            a=[q[i]-p[i] for i in range(3)];b=[r[i]-p[i] for i in range(3)]
            area=sum(x*x for x in (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]))
            if area<1e-16:raise ValueError('degenerate mesh triangle')
            for i,j in zip(tri,tri[1:]+tri[:1]):edges[tuple(sorted((i,j)))]=edges.get(tuple(sorted((i,j))),0)+1
        if any(count!=2 for count in edges.values()):raise ValueError('non-manifold or open component')
        if any(len(p)!=3 or not all(math.isfinite(x) for x in p) for p in v):raise ValueError('nonfinite mesh')
    wheels=[i for i in items if i['kind']=='wheel']
    centers=[[sum(p[k] for p in i['vertices'])/len(i['vertices']) for k in range(3)] for i in wheels]
    if abs(max(p[0] for p in centers)-min(p[0] for p in centers)-case.wheelbase_m)>1e-8:raise ValueError('wheelbase mismatch')
    return {'units':'m','frame':'x forward, y left, z up','wheel_count':4,
        'manifold_components':len(items),'physical_bindings':len(items),'physical_validation':False,
        'limitation':'Envelope geometry only; not a full FIA bodywork-conformity test.'}


def glb(items):
    binary=bytearray();views=[];access=[];meshes=[];nodes=[]
    def add(values,fmt,component,kind):
        while len(binary)%4:binary.append(0)
        start=len(binary)
        for row in values:binary.extend(struct.pack('<'+fmt,*row))
        view=len(views);views.append({'buffer':0,'byteOffset':start,'byteLength':len(binary)-start})
        index=len(access);a={'bufferView':view,'componentType':component,'count':len(values),'type':kind}
        if kind=='VEC3':a.update(min=[min(v[k] for v in values) for k in range(3)],max=[max(v[k] for v in values) for k in range(3)])
        access.append(a);return index
    for item in items:
        pos=add(item['vertices'],'fff',5126,'VEC3')
        inds=add([[i] for t in item['triangles'] for i in t],'I',5125,'SCALAR')
        meshes.append({'name':item['component_id'],'primitives':[{'attributes':{'POSITION':pos},'indices':inds}]})
        nodes.append({'name':item['component_id'],'mesh':len(meshes)-1,'extras':{
            'component_id':item['component_id'],'physical_binding':item['physical_binding']}})
    # Root conversion keeps authoring x-forward/z-up coordinates explicit while
    # exporting glTF's y-up world orientation.
    nodes.append({'name':'SI authoring frame','children':list(range(len(items))),
                  'rotation':[-math.sqrt(.5),0,0,math.sqrt(.5)]})
    doc={'asset':{'version':'2.0','generator':'Jarvis explicit envelope surrogate v1'},'scene':0,
        'scenes':[{'nodes':[len(items)]}],'nodes':nodes,'meshes':meshes,'accessors':access,
        'bufferViews':views,'buffers':[{'byteLength':len(binary)}]}
    raw=json.dumps(doc,separators=(',',':')).encode()
    raw+=b' '*((-len(raw))%4);binary+=b'\0'*((-len(binary))%4)
    return struct.pack('<4sII',b'glTF',2,12+8+len(raw)+8+len(binary))+struct.pack('<I4s',len(raw),b'JSON')+raw+struct.pack('<I4s',len(binary),b'BIN\0')+binary


def render(items,path,axes=(0,1)):
    from PIL import Image,ImageDraw
    image=Image.new('RGB',(1000,600),'#111820');draw=ImageDraw.Draw(image)
    points=[p for item in items for p in item['vertices']];a,b=axes
    lo=[min(p[k] for p in points) for k in (a,b)];hi=[max(p[k] for p in points) for k in (a,b)]
    scale=min(850/max(hi[0]-lo[0],.01),400/max(hi[1]-lo[1],.01))
    faces=[]
    colors={'chassis':'#e5a05c','wheel':'#647789','suspension':'#79bbaa','aero':'#6a9bd1'}
    for item in items:
        for tri in item['triangles']:
            coords=[item['vertices'][i] for i in tri]
            xy=[(75+(p[a]-lo[0])*scale,500-(p[b]-lo[1])*scale) for p in coords]
            faces.append((sum(p[3-a-b] for p in coords),xy,colors[item['kind']]))
    for _,xy,color in sorted(faces,key=lambda row:row[0]):draw.polygon(xy,fill=color,outline='#222e3a')
    draw.text((30,20),'JARVIS: generated envelope mesh diagnostic (not a screenshot / not exact team CAD)',fill='white')
    draw.text((30,45),f'Authoring axes {a}/{b}, metres; 4 wheels; distinct components and physical bindings',fill='#aabccb')
    image.save(path)


def build(root,case):
    root=Path(root);items=components(case);checks=validate(items,case)
    files={'asset_or_surrogate.glb':glb(items),'geometry_manifest.json':json.dumps({'components':items,'checks':checks},indent=2).encode()}
    for name,body in files.items():
        with (root/name).open('xb') as stream:stream.write(body)
    for name,axes in [('top.png',(0,1)),('side.png',(0,2)),('front.png',(1,2))]:render(items,root/name,axes)
    return {'checks':checks,'components':len(items),'files':{name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in (*files,'top.png','side.png','front.png')},'geometry_manifest':'geometry_manifest.json'}
