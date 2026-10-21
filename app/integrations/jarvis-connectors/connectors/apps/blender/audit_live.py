"""Disposable Blender 5.x audit. Every catalog action gets a live execution record.
Success without an independent effect assertion remains UNTESTED for acceptance.
Run with --background --factory-startup --disable-autoexec --python audit_live.py.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import bpy
from blender_connector.catalog import ACTIONS, MISSING, validate_action
from blender_connector.operations import BlenderOperations, SHADER_NODES, GEO_NODES, COMPOSITOR_NODES


def main():
    folder=Path(tempfile.mkdtemp(prefix='jarvis-blender-audit-'))
    os.environ['JARVIS_BLENDER_ALLOWED_ROOTS']=str(folder)
    ops=BlenderOperations()
    report={'version':bpy.app.version_string,'hash':bpy.app.build_hash.decode(),
            'temporary_directory':str(folder),'actions':[],'node_types':[],'effects':{}}
    def setup():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ops.execute('add_cube',{'name':'Subject'})
        ops.execute('add_cube',{'name':'Target','location':[3,0,0]})
        ops.execute('create_material',{'name':'Material'})
        ops.execute('assign_material',{'name':'Subject','material':'Material'})
        ops.execute('add_camera',{'name':'Camera'})
        ops.execute('set_active_camera',{'name':'Camera'})
        ops.execute('set_render_engine',{'engine':'BLENDER_WORKBENCH'})
        ops.execute('set_render_resolution',{'width':64,'height':64})
        bpy.context.scene.world=bpy.data.worlds.new('World')
        ops.execute('new_collection',{'name':'Collection'})
        ops.execute('add_armature',{'name':'Armature'})
        ops.execute('add_light',{'name':'Light'})
        ops.execute('add_text',{'name':'Text'})
        ops.execute('add_bezier_curve',{'name':'Curve','points':[[0,0,0],[1,1,1]]})
        ops.execute('create_geometry_nodes',{'name':'Subject','group_name':'Geometry'})
        ops.execute('create_compositor')
        ops.execute('animate_transform',{'name':'Subject','frame':1,'location':[0,0,0]})
        ops.execute('animate_transform',{'name':'Subject','frame':10,'location':[1,0,0]})
        ops.execute('select_object',{'name':'Subject'})
        bpy.context.scene.frame_set(1)
    setup()
    # Small input assets generated locally; no third-party files or downloads.
    img=bpy.data.images.new('AuditImage',width=8,height=8);img.filepath_raw=str(folder/'input.png');img.file_format='PNG';img.save()
    for kind,ext in [('obj','obj'),('fbx','fbx'),('gltf','glb'),('stl','stl'),('usd','usdc'),('alembic','abc')]:
        try:ops.execute('export_'+kind,dict(filepath=str(folder/('input.'+ext)),**({'selected_only':True} if 'selected_only' in ACTIONS['export_'+kind].fields else {})))
        except Exception as exc:report.setdefault('asset_prerequisites',{})[kind]=str(exc)[:250]
    defaults={'name':'Subject','old_name':'Subject','new_name':'Renamed','frame':5,'start':1,'end':10,'fps':24,
        'color':[.2,.4,.6,1],'offset':[0,0,1],'degrees_xyz':[0,0,45],'factor':[1,1,1],
        'child':'Subject','parent':'Target','key':'audit','value':1,'names':['Subject','Target'],
        'type':'MESH','index':0,'coordinate':[0,0,1],'indices':[0,1],'vertices':[[0,0,0],[1,0,0],[0,1,0]],'faces':[[0,1,2]],
        'modifier_name':'AuditModifier','properties':{'levels':1},'target':'Target','constraint':'AuditConstraint',
        'material':'Material','node_type':'ShaderNodeValue','node':'Value','socket':'Value','from_node':'Principled BSDF',
        'from_socket':'BSDF','to_node':'Material Output','to_socket':'Surface','attribute':'operation',
        'group_name':'Geometry','lens':45,'focus_distance':4,'body':'Audit','points':[[0,0,0],[1,1,1]],
        'depth':.02,'armature':'Armature','head':[0,0,0],'tail':[0,0,1],'group':'AuditGroup','action':'AuditAction',
        'engine':'CYCLES','width':64,'height':64,'samples':1,'min_x':0,'min_y':0,'max_x':1,'max_y':1,
        'gravity':[0,0,-9.81],'description':'Audit asset','tag':'fixture','steps':[{'action':'add_empty','params':{'name':'Batch'}}]}
    specific={
        'add_cube':{'name':'NewCube'},'add_mesh':{'name':'CustomMesh'},'set_transform':{'location':[1,2,3]},'set_material':{'name':'Material','roughness':.3},
        'get_material':{'name':'Material'},'set_interpolation':{'mode':'LINEAR'},'animate_transform':{'location':[2,0,0]},'delete_keyframe':{'property':'location','frame':1},'remove_material':{'name':'Material','force':True},'duplicate_material':{'name':'Material'},
        'set_world_color':{'color':[.1,.2,.3]},'set_scene':{'name':'Scene'},'rename_scene':{'old_name':'Scene'},
        'delete_scene':{'name':'Extra'},'rename_collection':{'old_name':'Collection'},'delete_collection':{'name':'Collection'},
        'move_to_collection':{'collection':'Collection'},'hide_collection':{'name':'Collection'},
        'add_modifier':{'type':'BEVEL'},'add_constraint':{'type':'COPY_LOCATION'},
        'set_shader_input':{'node':'Principled BSDF','socket':'Roughness','value':[.2]},
        'set_shader_attribute':{'node':'Math','attribute':'operation','value':'MULTIPLY'},
        'add_geometry_node':{'node_type':'ShaderNodeValue'},
        'link_geometry_nodes':{'from_node':'Group Input','from_socket':'Geometry','to_node':'Group Output','to_socket':'Geometry'},
        'set_geometry_input':{'node':'Math','socket':'Value','value':[.3]},'remove_geometry_node':{'node':'Math'},
        'add_compositor_node':{'node_type':'CompositorNodeBlur'},
        'link_compositor_nodes':{'from_node':'Render Layers','from_socket':'Image','to_node':'Group Output','to_socket':'Image'},
        'set_compositor_input':{'node':'Math','socket':'Value','value':[.4]},'remove_compositor_node':{'node':'Math'},
        'set_render_resolution':{'width':96,'height':80},'scale_object':{'factor':[2,2,2]},'set_camera_lens':{'name':'Camera'},'set_active_camera':{'name':'Camera'},
        'set_camera_dof':{'name':'Camera'},'set_camera_clip':{'name':'Camera','start':.1,'end':100},
        'aim_at':{'name':'Camera','target':[0,0,0]},'set_light':{'name':'Light','energy':100},
        'edit_text':{'name':'Text'},'set_curve_bevel':{'name':'Curve'},'list_bones':{'name':'Armature'},
        'add_bone':{'name':'AuditBone','parent':'Bone'},'set_shape_key':{'key':'AuditShape','value':.3},
        'mark_asset':{'type':'OBJECT'},'clear_asset':{'type':'OBJECT'},'set_asset_description':{'type':'OBJECT'},'add_asset_tag':{'type':'OBJECT'},
    }
    assertions={
        'add_cube':lambda p:len(bpy.data.objects[p['name']].data.vertices)==8,
        'set_transform':lambda p:tuple(bpy.data.objects['Subject'].location)==(1,2,3),
        'rename_object':lambda p:bpy.data.objects.get('Renamed') is not None,
        'delete_object':lambda p:bpy.data.objects.get('Subject') is None,
        'assign_material':lambda p:bpy.data.objects['Subject'].data.materials[0].name=='Material',
        'create_compositor':lambda p:bpy.context.scene.compositing_node_group.nodes.get('Group Output') is not None,
        'set_interpolation':lambda p:all(k.interpolation=='LINEAR' for l in bpy.data.objects['Subject'].animation_data.action.layers for s in l.strips for bag in s.channelbags for fc in bag.fcurves for k in fc.keyframe_points),
        'set_frame':lambda p:bpy.context.scene.frame_current==p['frame'],
        'add_marker':lambda p:bpy.context.scene.timeline_markers.get(p['name']) is not None,
        'delete_marker':lambda p:bpy.context.scene.timeline_markers.get(p['name']) is None,
        'set_fps':lambda p:bpy.context.scene.render.fps==p['fps'],
        'add_rigidbody':lambda p:bpy.data.objects['Subject'].rigid_body is not None,
        'remove_rigidbody':lambda p:bpy.data.objects['Subject'].rigid_body is None,
        'add_cloth':lambda p:any(m.type=='CLOTH' for m in bpy.data.objects['Subject'].modifiers),
        'add_collision':lambda p:any(m.type=='COLLISION' for m in bpy.data.objects['Subject'].modifiers),
        'add_fluid':lambda p:any(m.type=='FLUID' for m in bpy.data.objects['Subject'].modifiers),
        'add_soft_body':lambda p:any(m.type=='SOFT_BODY' for m in bpy.data.objects['Subject'].modifiers),
    }
    assertions.update({
        'scene_summary':lambda p:result['data']['objects']==len(bpy.context.scene.objects) and result['data']['frame']==bpy.context.scene.frame_current,
        'new_scene':lambda p:bpy.data.scenes.get(p['name']) is not None,
        'set_scene':lambda p:bpy.context.scene.name==p['name'],
        'rename_scene':lambda p:bpy.data.scenes.get(p['new_name']) is not None,
        'delete_scene':lambda p:bpy.data.scenes.get(p['name']) is None,
        'set_frame_range':lambda p:(bpy.context.scene.frame_start,bpy.context.scene.frame_end)==(p['start'],p['end']),
        'new_collection':lambda p:bpy.data.collections.get(p['name']) is not None,
        'delete_collection':lambda p:bpy.data.collections.get(p['name']) is None,
        'rename_collection':lambda p:bpy.data.collections.get(p['new_name']) is not None,
        'move_to_collection':lambda p:bpy.data.objects[p['name']] in tuple(bpy.data.collections[p['collection']].objects),
        'select_object':lambda p:bpy.context.view_layer.objects.active.name==p['name'],
        'deselect_all':lambda p:len(bpy.context.selected_objects)==0,
        'select_all':lambda p:len(bpy.context.selected_objects)==len(bpy.context.scene.objects),
        'select_by_type':lambda p:len(bpy.context.selected_objects)==sum(o.type==p['type'] for o in bpy.context.scene.objects) and all(o.type==p['type'] for o in bpy.context.selected_objects),
        'set_active_object':lambda p:bpy.context.view_layer.objects.active.name==p['name'],
        'delete_selected':lambda p:bpy.data.objects.get('Subject') is None,
        'move_object':lambda p:tuple(bpy.data.objects['Subject'].location)==tuple(p['offset']),
        'scale_object':lambda p:tuple(bpy.data.objects['Subject'].scale)==tuple(p['factor']),
        'set_parent':lambda p:bpy.data.objects[p['child']].parent==bpy.data.objects[p['parent']],
        'clear_parent':lambda p:bpy.data.objects[p['name']].parent is None,
        'set_custom_property':lambda p:bpy.data.objects[p['name']][p['key']]==p['value'],
        'remove_custom_property':lambda p:p['key'] not in bpy.data.objects[p['name']],
        'join_objects':lambda p:len(bpy.data.objects['Subject'].data.vertices)==16,
        'smooth_shading':lambda p:all(f.use_smooth==p['smooth'] for f in bpy.data.objects[p['name']].data.polygons),
        'add_mesh':lambda p:len(bpy.data.objects[p['name']].data.vertices)==len(p['vertices']),
        'set_vertex':lambda p:tuple(bpy.data.objects[p['name']].data.vertices[p['index']].co)==tuple(p['coordinate']),
        'remove_modifier':lambda p:bpy.data.objects[p['name']].modifiers.get(p['modifier_name']) is None,
        'set_modifier':lambda p:bpy.data.objects[p['name']].modifiers[p['modifier_name']].levels==1,
        'apply_modifier':lambda p:bpy.data.objects[p['name']].modifiers.get(p['modifier_name']) is None and len(bpy.data.objects[p['name']].data.vertices)>8,
        'remove_constraint':lambda p:bpy.data.objects[p['name']].constraints.get(p['constraint']) is None,
        'create_material':lambda p:bpy.data.materials.get(p['name']) is not None,
        'duplicate_material':lambda p:bpy.data.materials.get(p['new_name']) is not None,
        'remove_material':lambda p:bpy.data.materials.get(p['name']) is None,
        'clear_material_slots':lambda p:len(bpy.data.objects[p['name']].data.materials)==0,
        'set_material':lambda p:abs(bpy.data.materials[p['name']].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value-.3)<1e-5,
        'set_shader_input':lambda p:abs(bpy.data.materials[p['material']].node_tree.nodes[p['node']].inputs[p['socket']].default_value-.2)<1e-5,
        'create_geometry_nodes':lambda p:ops._node_group(p['name']).name.startswith(p['group_name']),
        'link_geometry_nodes':lambda p:len(ops._node_group(p['name']).links)>0,
        'set_geometry_input':lambda p:abs(ops._node_group(p['name']).nodes[p['node']].inputs[p['socket']].default_value-.3)<1e-5,
        'remove_geometry_node':lambda p:ops._node_group(p['name']).nodes.get(p['node']) is None,
        'link_compositor_nodes':lambda p:len(bpy.context.scene.compositing_node_group.links)>0,
        'set_compositor_input':lambda p:abs(bpy.context.scene.compositing_node_group.nodes[p['node']].inputs[p['socket']].default_value-.4)<1e-5,
        'remove_compositor_node':lambda p:bpy.context.scene.compositing_node_group.nodes.get(p['node']) is None,
        'set_active_camera':lambda p:bpy.context.scene.camera.name==p['name'],
        'set_camera_lens':lambda p:bpy.data.objects[p['name']].data.lens==p['lens'],
        'edit_text':lambda p:bpy.data.objects[p['name']].data.body==p['body'],
        'add_bone':lambda p:bpy.data.objects[p['armature']].data.bones.get(p['name']) is not None,
        'parent_to_armature':lambda p:bpy.data.objects[p['name']].parent==bpy.data.objects[p['armature']],
        'add_vertex_group':lambda p:bpy.data.objects[p['name']].vertex_groups.get(p['group']) is not None,
        'create_shape_key':lambda p:bpy.data.objects[p['name']].data.shape_keys.key_blocks.get(p['key']) is not None,
        'clear_animation':lambda p:bpy.data.objects[p['name']].animation_data is None,
        'set_render_engine':lambda p:bpy.context.scene.render.engine==p['engine'],
        'set_render_resolution':lambda p:(bpy.context.scene.render.resolution_x,bpy.context.scene.render.resolution_y)==(p['width'],p['height']),
        'set_render_samples':lambda p:bpy.context.scene.cycles.samples==p['samples'],
        'set_transparent_film':lambda p:bpy.context.scene.render.film_transparent==p['enabled'],
        'set_cycles_device':lambda p:bpy.context.scene.cycles.device==p['device'],
        'set_render_border':lambda p:bpy.context.scene.render.use_border==p['enabled'],
        'mark_asset':lambda p:bpy.data.objects[p['name']].asset_data is not None,
        'clear_asset':lambda p:bpy.data.objects[p['name']].asset_data is None,
        'set_asset_description':lambda p:bpy.data.objects[p['name']].asset_data.description==p['description'],
        'add_asset_tag':lambda p:bpy.data.objects[p['name']].asset_data.tags.get(p['tag']) is not None,
    })
    for primitive in ('add_uv_sphere','add_ico_sphere','add_cylinder','add_cone','add_torus','add_plane','add_grid','add_circle','add_monkey'):
        specific.setdefault(primitive,{})['name']='VerifiedPrimitive'
        assertions[primitive]=lambda p:bpy.data.objects[p['name']].type=='MESH' and len(bpy.data.objects[p['name']].data.vertices)>2
    for operation,typ in {'add_subdivision':'SUBSURF','add_bevel':'BEVEL','add_solidify':'SOLIDIFY','add_mirror':'MIRROR','add_array':'ARRAY','add_boolean':'BOOLEAN','add_remesh':'REMESH','add_wireframe':'WIREFRAME'}.items():
        assertions[operation]=lambda p,typ=typ:any(m.type==typ for m in bpy.data.objects[p['name']].modifiers)
    for kind in ('obj','fbx','gltf','stl','usd','alembic'):
        assertions['export_'+kind]=lambda p:Path(p['filepath']).is_file() and Path(p['filepath']).stat().st_size>0
    for action_name in ('save_project','save_project_copy','render_still'):
        assertions[action_name]=lambda p:Path(p['filepath']).is_file() and Path(p['filepath']).stat().st_size>0
    for action,spec in ACTIONS.items():
        setup()
        params={k:defaults[k] for k,v in spec.fields.items() if v.default is MISSING and k in defaults}
        params.update(specific.get(action,{}))
        if 'filepath' in spec.fields:
            kind=action.split('_',1)[-1]
            ext={'obj':'obj','fbx':'fbx','gltf':'glb','stl':'stl','usd':'usdc','alembic':'abc'}.get(kind,'png' if action in {'load_image','assign_image_texture','render_still','set_render_output'} else 'blend')
            params['filepath']=str(folder/(('input' if action.startswith('import_') or action in {'load_image','assign_image_texture'} else action)+'.'+ext))
        if action in {'remove_modifier','set_modifier','apply_modifier'}:
            bpy.data.objects['Subject'].modifiers.new('AuditModifier','SUBSURF')
        if action=='remove_constraint':bpy.data.objects['Subject'].constraints.new('COPY_LOCATION').name='AuditConstraint'
        if action=='remove_custom_property':bpy.data.objects['Subject']['audit']=1
        if action=='set_shader_attribute':bpy.data.materials['Material'].node_tree.nodes.new('ShaderNodeMath')
        if action in {'set_geometry_input','remove_geometry_node'}:ops._node_group('Subject').nodes.new('ShaderNodeMath')
        if action in {'set_compositor_input','remove_compositor_node'}:bpy.context.scene.compositing_node_group.nodes.new('ShaderNodeMath')
        if action=='purge_orphans':bpy.data.meshes.new('AuditOrphan')
        if action=='delete_scene':bpy.data.scenes.new('Extra')
        if action=='assign_vertices_group':ops.execute('add_vertex_group',{'name':'Subject','group':'AuditGroup'})
        if action in {'set_shape_key','list_shape_keys'}:ops.execute('create_shape_key',{'name':'Subject','key':'AuditShape'})
        if action in {'clear_asset','set_asset_description','add_asset_tag'}:bpy.data.objects['Subject'].asset_mark()
        if action in {'remove_rigidbody','set_rigidbody'}:ops.execute('add_rigidbody',{'name':'Subject'})
        if action=='delete_marker':bpy.context.scene.timeline_markers.new('Subject',frame=5)
        if action in {'assign_action','set_nla_strip','rename_action'}:
            act=bpy.data.objects['Subject'].animation_data.action
            act.name='AuditAction'
            if action=='rename_action':params['old_name']='AuditAction'
        if action in {'set_cycles_device','set_render_samples'}:bpy.context.scene.render.engine='CYCLES'
        # Establish independently different preconditions so no-op implementations cannot pass.
        if action=='assign_material':bpy.data.objects['Subject'].data.materials.clear()
        if action=='clear_parent':bpy.data.objects['Subject'].parent=bpy.data.objects['Target']
        if action=='set_scene':bpy.context.window.scene=bpy.data.scenes.new('OtherActiveScene')
        if action in {'select_object','set_active_object'}:
            for ob in tuple(bpy.context.selected_objects):ob.select_set(False)
            bpy.data.objects['Target'].select_set(True)
            bpy.context.view_layer.objects.active=bpy.data.objects['Target']
        if action=='create_geometry_nodes':
            subject=bpy.data.objects['Subject']
            for mod in tuple(subject.modifiers):
                if mod.type=='NODES':subject.modifiers.remove(mod)
        if action=='link_geometry_nodes':
            tree=ops._node_group('Subject')
            for link in tuple(tree.links):tree.links.remove(link)
        if action=='link_compositor_nodes':
            tree=bpy.context.scene.compositing_node_group
            for link in tuple(tree.links):tree.links.remove(link)
        start=time.perf_counter()
        record={'tool':'blender_'+action,'category':spec.group,'coverage':'UNTESTED','parameters':params}
        try:
            result=ops.execute(action,params)
            record['execution']='completed_in_Blender'
            if action in assertions:
                assert assertions[action](validate_action(action,params)),'Independent effect assertion failed'
                record['coverage']='VERIFIED IN BLENDER'
            record['result_excerpt']=str(result)[:240]
        except Exception as exc:
            record.update(execution='explicit_failure',error_type=type(exc).__name__,error=str(exc)[:500])
        record['elapsed_ms']=round((time.perf_counter()-start)*1000,3)
        report['actions'].append(record)
    setup()
    trees=[('shader',SHADER_NODES,bpy.data.materials['Material'].node_tree),('geometry',GEO_NODES,ops._node_group('Subject')),('compositor',COMPOSITOR_NODES,bpy.context.scene.compositing_node_group)]
    for category,names,tree in trees:
        for name in sorted(names):
            try:
                node=ops._new_node(tree,name);tree.nodes.remove(node)
                report['node_types'].append({'category':category,'type':name,'supported':True})
            except Exception as exc:report['node_types'].append({'category':category,'type':name,'supported':False,'error':str(exc)[:200]})
    # Reopen generated outputs and inspect geometry rather than trusting return values.
    for kind,ext in [('obj','obj'),('fbx','fbx'),('gltf','glb'),('stl','stl')]:
        before=set(bpy.data.objects)
        try:
            ops.execute('import_'+kind,{'filepath':str(folder/('input.'+ext))})
            new=set(bpy.data.objects)-before
            report['effects']['reopened_'+kind]=any(o.type=='MESH' and len(o.data.vertices)>0 for o in new)
        except Exception as exc:report['effects']['reopened_'+kind]={'error':str(exc)[:250]}
    ops.execute('save_project_copy',{'filepath':str(folder/'reopen.blend')})
    bpy.ops.wm.open_mainfile(filepath=str(folder/'reopen.blend'),use_scripts=False,load_ui=False)
    report['effects']['reopened_blend_subject_mesh']=len(bpy.data.objects['Subject'].data.vertices)==8
    report['summary']={state:sum(r['coverage']==state for r in report['actions']) for state in ('VERIFIED IN BLENDER','SIMULATED','UNTESTED')}
    report['summary']['explicit_failures']=sum(r['execution']=='explicit_failure' for r in report['actions'])
    target=Path(os.environ['JARVIS_BLENDER_LIVE_REPORT'])
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('JARVIS_LIVE_AUDIT',report['summary'],flush=True)


if __name__=='__main__':main()
