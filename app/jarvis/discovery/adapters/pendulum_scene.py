"""Owned fixed Blender template; no user code/assets/add-ons are accepted.

Run with factory startup, disabled autoexec, offline mode and CPU rendering.
The native hinge rig is inspectable; its bob is kinematic and display motion is
driven by the actual SciPy trace, never reported as a Bullet dynamics test.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import bpy


def signature(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def describe(request):
    if {o.name for o in bpy.data.objects if o.type=='MESH'}!={'anchor','rod','bob'}:
        raise ValueError('unexpected native mesh parts')
    rows=[]
    for name in ('anchor','rod','bob'):
        obj=bpy.data.objects.get(name)
        if obj is None or obj.type!='MESH':raise ValueError('required native part missing')
        counts=[0]*len(obj.data.edges)
        # Edge-face incidence without relying on a render or a screenshot.
        lookup={tuple(sorted(e.vertices)):i for i,e in enumerate(obj.data.edges)}
        for face in obj.data.polygons:
            vertices=list(face.vertices)
            for a,b in zip(vertices,vertices[1:]+vertices[:1]):counts[lookup[tuple(sorted((a,b)))]]+=1
        if not counts or any(n!=2 for n in counts):raise ValueError('surface mesh is not closed manifold')
        if any(not math.isfinite(float(v)) for vertex in obj.data.vertices for v in vertex.co):raise ValueError('nonfinite mesh')
        rows.append({'name':name,'component_id':obj['component_id'],'vertices':len(obj.data.vertices),
                     'polygons':len(obj.data.polygons),'closed_manifold':True,
                     'mass_kg':float(obj.rigid_body.mass) if obj.rigid_body else None})
    joint=bpy.data.objects.get('joint.pivot')
    c=joint.rigid_body_constraint if joint else None
    if c is None or c.type!='HINGE' or c.object1.name!='anchor' or c.object2.name!='bob':
        raise ValueError('native hinge topology missing')
    bob=bpy.data.objects['bob'];rod=bpy.data.objects['rod'];model=request['run']['model']
    scene=bpy.context.scene
    if (abs(scene.gravity.z+model['gravity_m_s2'])>1e-5 or abs(scene.unit_settings.scale_length-1)>1e-8
            or abs(scene.render.fps/scene.render.fps_base-1/model['dt_s'])>1e-4):
        raise ValueError('native gravity, scale or frame time differs from the model')
    if not bob.rigid_body.kinematic or abs(bob.rigid_body.mass-model['mass_kg'])>1e-6:
        raise ValueError('native body mass or kinematic display mode mismatch')
    # Primitive geometry, not metadata alone, must match model dimensions.
    if max(abs(float(v.co.length)-model['radius_m']) for v in bob.data.vertices)>1e-5:
        raise ValueError('native bob radius differs from physical model')
    zs=[v.co.z for v in rod.data.vertices]
    if abs(max(zs)-min(zs)-model['length_m'])>1e-5:raise ValueError('native rod length mismatch')
    samples=request['run']['samples'];observed=[]
    for i in sorted({0,len(samples)//4,len(samples)//2,len(samples)-1}):
        bpy.context.scene.frame_set(i+1);bpy.context.view_layer.update()
        position=[float(v) for v in bob.matrix_world.translation]
        expected=[samples[i]['x_m'],0.0,samples[i]['z_m']]
        if max(abs(a-b) for a,b in zip(position,expected))>2e-5:
            raise ValueError('saved animation is not driven by numeric trajectory')
        observed.append({'sample_index':i,'position_m':position})
    return {'blender_version':bpy.app.version_string,'parts':rows,'hinge':'anchor->bob',
            'kinematic_display':bool(bob.rigid_body.kinematic),'trajectory_checks':observed,
            'model_sha256':bpy.context.scene['model_sha256'],
            'trajectory_sha256':bpy.context.scene['trajectory_sha256'],'bullet_dynamics_tested':False}


def material(name,color):
    mat=bpy.data.materials.new(name);mat.diffuse_color=(*color,1.0)
    return mat


def create(request):
    run=request['run'];p=run['model'];L=p['length_m'];r=p['radius_m'];samples=run['samples']
    output=Path(request['output'])
    if any(output.with_suffix(s).exists() for s in ('.blend','.obj','.png')):
        raise ValueError('native outputs already exist; use a new owned experiment directory')
    if not 1<=len(samples)<=2001 or not 0.1<=L<=5 or not 0.005<=r<=0.2:
        raise ValueError('bounded reviewed geometry required')
    for row in samples:
        if set(row)!={'t_s','theta_rad','omega_rad_s','x_m','z_m'} or any(not math.isfinite(float(v)) for v in row.values()):
            raise ValueError('invalid numeric trace')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    scene.gravity=(0,0,-p['gravity_m_s2']);scene.frame_start=1;scene.frame_end=len(samples)
    scene.render.fps=round(1/p['dt_s']);scene.render.fps_base=scene.render.fps*p['dt_s']
    scene['model_sha256']=signature(p);scene['trajectory_sha256']=signature(samples)
    scene['evidence']='Conditional SciPy rigid pendulum; kinematic visualization, not Bullet validation'
    bpy.ops.object.empty_add(type='PLAIN_AXES');root=bpy.context.object;root.name='pendulum.rig'
    bpy.ops.mesh.primitive_cube_add(size=0.08);anchor=bpy.context.object;anchor.name='anchor'
    bpy.ops.rigidbody.object_add();anchor.rigid_body.type='PASSIVE'
    anchor['component_id']=request['component_ids']['anchor']
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=min(r/5,L/100),depth=L,location=(0,0,-L/2))
    rod=bpy.context.object;rod.name='rod';rod.parent=root;rod['component_id']=request['component_ids']['rod']
    rod['model_assumption']='massless rigid connector; visual surface is not a structural-strength model'
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,radius=r,location=(0,0,-L))
    bob=bpy.context.object;bob.name='bob';bob.parent=root;bob['component_id']=request['component_ids']['bob']
    bpy.ops.rigidbody.object_add();bob.rigid_body.mass=p['mass_kg'];bob.rigid_body.collision_shape='SPHERE'
    bob.rigid_body.kinematic=True;bob['inertia_about_pivot_kg_m2']=run['metrics']['inertia_about_pivot_kg_m2']
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0));joint=bpy.context.object;joint.name='joint.pivot'
    joint.rotation_euler=(math.pi/2,0,0);bpy.ops.rigidbody.constraint_add()
    joint.rigid_body_constraint.type='HINGE';joint.rigid_body_constraint.object1=anchor;joint.rigid_body_constraint.object2=bob
    for i,row in enumerate(samples):
        root.rotation_euler=(0,-row['theta_rad'],0);root.keyframe_insert(data_path='rotation_euler',frame=i+1)
    anchor.data.materials.append(material('visual.anchor',(0.15,0.18,0.24)))
    rod.data.materials.append(material('visual.rod',(0.45,0.48,0.52)))
    bob.data.materials.append(material('visual.bob',(0.05,0.4,0.75)))
    scene.frame_set(1);bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in (anchor,rod,bob):obj.select_set(True)
    bpy.ops.wm.obj_export(filepath=str(output.with_suffix('.obj')),export_selected_objects=True)
    # CPU-only preview at a non-initial solver frame; no GPU renderer/model call.
    from mathutils import Vector
    bpy.ops.object.camera_add(location=(2.8*L,-4*L,0.7*L));camera=bpy.context.object
    camera.rotation_euler=(Vector((0,0,-L/2))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=1.6*L;scene.camera=camera
    bpy.ops.object.light_add(type='AREA',location=(L,-2*L,L));bpy.context.object.data.energy=500*L*L;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=3*L
    if scene.world is None:scene.world=bpy.data.worlds.new('World')
    scene.world.color=(0.15,0.15,0.15);scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8
    scene.render.resolution_x=480;scene.render.resolution_y=480;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.filepath=str(output.with_suffix('.png'))
    scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(output),check_existing=False)
    scene.frame_set(len(samples)//3+1);bpy.ops.render.render(write_still=True)
    return describe(request)


def main():
    args=sys.argv[sys.argv.index('--')+1:];request_path,result_path=map(Path,args)
    try:
        request=json.loads(request_path.read_text(encoding='utf-8'))
        if request['operation']=='create':value=create(request)
        elif request['operation']=='inspect':
            bpy.ops.wm.open_mainfile(filepath=request['output'],load_ui=False,use_scripts=False);value=describe(request)
        else:raise ValueError('unsupported fixed scene operation')
        response={'ok':True,'value':value,'cpu_s':time.process_time()}
    except Exception as exc:response={'ok':False,'error_type':type(exc).__name__,'error':str(exc)[:500]}
    result_path.write_text(json.dumps(response,allow_nan=False),encoding='utf-8')


if __name__=='__main__':main()
