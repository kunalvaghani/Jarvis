"""Blender bpy command dispatcher. Import inside Blender; never import bpy in MCP process.
Designed for Blender 5.2 LTS. Only the Blender main thread may call execute().
"""
from __future__ import annotations
import math
from pathlib import Path
from typing import Any
from contextlib import contextmanager

from .catalog import ACTIONS, SAFE_BATCH, validate_action

MODIFIERS = {'SUBSURF','BEVEL','SOLIDIFY','MIRROR','ARRAY','BOOLEAN','REMESH','WIREFRAME','DECIMATE','TRIANGULATE',
             'NODES','WELD','WEIGHTED_NORMAL','SMOOTH','SIMPLE_DEFORM','SHRINKWRAP','CURVE','ARMATURE',
             'SKIN','LAPLACIANSMOOTH','DISPLACE','CAST','LATTICE','SCREW','BUILD','EDGE_SPLIT','MASK','MULTIRES'}
CONSTRAINTS = {'COPY_LOCATION','COPY_ROTATION','COPY_SCALE','COPY_TRANSFORMS','TRACK_TO','DAMPED_TRACK',
               'LIMIT_LOCATION','LIMIT_ROTATION','LIMIT_SCALE','CHILD_OF','FOLLOW_PATH','STRETCH_TO','IK','SHRINKWRAP'}
SHADER_NODES = {'ShaderNodeTexImage','ShaderNodeTexNoise','ShaderNodeTexVoronoi','ShaderNodeTexChecker',
                'ShaderNodeTexGradient','ShaderNodeTexCoord','ShaderNodeMapping','ShaderNodeBsdfPrincipled',
                'ShaderNodeBsdfDiffuse','ShaderNodeBsdfGlossy','ShaderNodeBsdfTransparent','ShaderNodeEmission',
                'ShaderNodeMixShader','ShaderNodeAddShader','ShaderNodeMix','ShaderNodeMath','ShaderNodeVectorMath',
                'ShaderNodeValToRGB','ShaderNodeRGB','ShaderNodeValue','ShaderNodeNormalMap','ShaderNodeBump',
                'ShaderNodeDisplacement','ShaderNodeOutputMaterial','ShaderNodeSeparateColor','ShaderNodeCombineColor',
                'ShaderNodeSeparateXYZ','ShaderNodeCombineXYZ','ShaderNodeAttribute','ShaderNodeFresnel','ShaderNodeLayerWeight'}
GEO_NODES = {'GeometryNodeJoinGeometry','GeometryNodeTransform','GeometryNodeMeshCube','GeometryNodeMeshUVSphere',
             'GeometryNodeMeshIcoSphere','GeometryNodeMeshGrid','GeometryNodeMeshCylinder', 'GeometryNodeMeshCircle',
             'GeometryNodeMeshBoolean','GeometryNodeSubdivideMesh','GeometryNodeSetPosition','GeometryNodeSetMaterial',
             'GeometryNodeDistributePointsOnFaces','GeometryNodeInstanceOnPoints','GeometryNodeRealizeInstances',
             'GeometryNodeCurvePrimitiveLine','GeometryNodeCurveToMesh','GeometryNodeMeshToCurve','GeometryNodeInputPosition',
             'GeometryNodeInputIndex','GeometryNodeInputNormal','GeometryNodeInputNamedAttribute',
             'GeometryNodeStoreNamedAttribute','GeometryNodeDeleteGeometry','GeometryNodeMergeByDistance',
             'GeometryNodeExtrudeMesh','GeometryNodeGeometryToInstance','GeometryNodeSetShadeSmooth',
             'ShaderNodeMath','ShaderNodeVectorMath','ShaderNodeValue','ShaderNodeCombineXYZ','ShaderNodeSeparateXYZ',
             'FunctionNodeCompare','GeometryNodeSwitch','GeometryNodeInputSceneTime'}
COMPOSITOR_NODES = {'CompositorNodeRLayers','CompositorNodeComposite','CompositorNodeViewer',
                    'CompositorNodeAlphaOver','CompositorNodeBlur','CompositorNodeGlare','CompositorNodeColorBalance',
                    'CompositorNodeHueSat','CompositorNodeBrightContrast','CompositorNodeMixRGB',
                    'CompositorNodeMapRange','CompositorNodeValToRGB','CompositorNodeRGB','CompositorNodeValue',
                    'CompositorNodeDenoise','CompositorNodeLensdist','CompositorNodeTranslate',
                    'CompositorNodeScale','CompositorNodeTransform','CompositorNodeImage',
                    'CompositorNodeNormalize','CompositorNodeMath'}
NODE_ATTRS = {'operation','blend_type','distribution','interpolation','mode','use_clamp','clamp','data_type'}
MOD_PROPS = {'levels','render_levels','width','segments','thickness','count','ratio','use_clip','show_viewport',
             'show_render','strength','angle_limit','offset','relative_offset_displace','use_relative_offset',
             'operation','solver','voxel_size','octree_depth','use_axis','decimate_type','vertex_group',
             'factor','deform_axis','deform_method','use_even_offset'}


def _vec(values, size=3):
    if not isinstance(values,list) or len(values)!=size or not all(isinstance(v,(float,int)) and
         not isinstance(v,bool) and math.isfinite(v) and abs(v)<=1e7 for v in values):
        raise ValueError(f'Expected {size} finite numeric values')
    return tuple(float(v) for v in values)

def _name(value):
    if not isinstance(value,str) or not value.strip() or len(value)>120:
        raise ValueError('Name must be 1..120 characters')
    return value.strip()

def _safe_number(v,lo,hi,what):
    if not isinstance(v,(float,int)) or isinstance(v,bool) or not math.isfinite(v) or not lo<=v<=hi:
        raise ValueError(f'{what} must be {lo}..{hi}')
    return v

def _enum(value, choices, label):
    if value not in choices:
        raise ValueError(f'{label}: expected one of {sorted(choices)}')
    return value

def _path(value, kind='read', suffixes=None):
    """Allow only explicitly approved filesystem roots. Resolved symlink targets stay within roots."""
    import os
    raw = str(value)
    if not raw or len(raw)>2048 or '\x00' in raw:
        raise ValueError('Absolute file path required')
    if raw.startswith(('http:','https:','file:')):raise ValueError('Filesystem path required, not a URI')
    if not os.getenv('JARVIS_BLENDER_ALLOWED_ROOTS',''):
        raise PermissionError('Set JARVIS_BLENDER_ALLOWED_ROOTS before file operations')
    p = Path(raw).expanduser()
    if not p.is_absolute():
        raise ValueError('Absolute file path required')
    p=p.resolve(strict=False)
    roots=os.getenv('JARVIS_BLENDER_ALLOWED_ROOTS','')
    if not roots:
        raise PermissionError('Set JARVIS_BLENDER_ALLOWED_ROOTS to authorized directories before file operations')
    allowed=[Path(s).expanduser().resolve(strict=False) for s in roots.split(os.pathsep) if s.strip()]
    if not any(p == root or root in p.parents for root in allowed):
        raise PermissionError('Path outside JARVIS_BLENDER_ALLOWED_ROOTS')
    if suffixes and p.suffix.lower() not in suffixes:
        raise ValueError('Unsupported file extension')
    if kind == 'read' and not p.is_file():
        raise FileNotFoundError(f'Input file not found: {p.name}')
    if kind == 'write' and p.exists():
        raise PermissionError('Output exists; overwrite is disabled. Choose a new output path.')
    if kind == 'write' and not p.parent.is_dir():
        raise FileNotFoundError('Output directory does not exist')
    return str(p)


def _ok_op(result, name):
    if result is not None and isinstance(result,set) and 'FINISHED' not in result:
        raise RuntimeError(f'Blender operator {name} did not finish: {sorted(result)}')

class BlenderOperations:
    def __init__(self,bpy_module=None):
        if bpy_module is None:
            import bpy as bpy_module
        self.bpy=bpy_module

    def _obj(self,name):
        obj=self.bpy.data.objects.get(_name(name))
        if obj is None:
            matches=[getattr(o,'name',str(o)) for o in self.bpy.data.objects if str(name).casefold() in getattr(o,'name',str(o)).casefold()][:12]
            raise ValueError(f'Exact object not found: {name}; candidates: {matches}')
        return obj

    def _mesh(self,name):
        obj=self._obj(name)
        if obj.type!='MESH': raise ValueError(f'Expected MESH object: {name}')
        return obj

    def _mat(self,name):
        m=self.bpy.data.materials.get(_name(name))
        if m is None: raise ValueError(f'Material not found: {name}')
        return m

    def _choose(self,obj,other=()):
        if getattr(self.bpy.context.object,'mode','OBJECT')!='OBJECT' and self.bpy.ops.object.mode_set.poll():
            self.bpy.ops.object.mode_set(mode='OBJECT')
        for ob in self.bpy.context.selected_objects: ob.select_set(False)
        for ob in other: ob.select_set(True)
        obj.select_set(True)
        self.bpy.context.view_layer.objects.active=obj

    @contextmanager
    def _edit(self,name):
        obj=self._mesh(name)
        self._choose(obj)
        self.bpy.ops.object.mode_set(mode='EDIT')
        try:
            yield obj
        finally:
            if obj.mode=='EDIT': self.bpy.ops.object.mode_set(mode='OBJECT')

    def _node_group(self, name):
        ob=self._obj(name)
        mod=next((m for m in ob.modifiers if m.type=='NODES' and m.node_group),None)
        if mod is None: raise ValueError(f'Object lacks geometry-node modifier: {name}')
        return mod.node_group

    def _new_node(self,tree,typ):
        aliases={'ShaderNodeBsdfGlossy':'ShaderNodeBsdfAnisotropic','CompositorNodeComposite':'NodeGroupOutput','CompositorNodeMapRange':'ShaderNodeMapRange','CompositorNodeMath':'ShaderNodeMath','CompositorNodeMixRGB':'ShaderNodeMixRGB','CompositorNodeValToRGB':'ShaderNodeValToRGB','CompositorNodeValue':'ShaderNodeValue'}
        if self.bpy.app.version >= (5,0,0): typ=aliases.get(typ,typ)
        if not hasattr(self.bpy.types,typ):raise ValueError(f'Node type {typ} unavailable in Blender {self.bpy.app.version_string}; supported-version prerequisite failed')
        return tree.nodes.new(typ)

    def _nodes(self,tree):
        if not tree: raise ValueError('Node tree is missing')
        return tree.nodes

    def _set_socket(self, node, socket, value):
        s=node.inputs.get(socket)
        if s is None: raise ValueError(f'Input socket not found: {socket}')
        if not hasattr(s,'default_value'): raise ValueError('Socket is not directly assignable')
        orig=s.default_value
        if isinstance(orig,(float,int,bool)):
            if len(value)!=1: raise ValueError('Expected a single scalar in value array')
            if isinstance(orig,bool): s.default_value=bool(value[0])
            else: s.default_value=_safe_number(value[0],-1e9,1e9,'socket value')
        else:
            count=len(orig)
            s.default_value=_vec(value,count)

    def _node_link(self,tree,src,src_socket,dst,dst_socket):
        a=tree.nodes.get(src); b=tree.nodes.get(dst)
        if a is None or b is None: raise ValueError('Source or destination node missing')
        x=a.outputs.get(src_socket); y=b.inputs.get(dst_socket)
        if x is None or y is None: raise ValueError('Node socket not found')
        tree.links.new(x,y)

    def execute(self,action: str,params: dict[str,Any]|None=None):
        p=validate_action(action,params or {})
        if action in {'open_project','revert_project','unpack_resources','render_animation'}:
            raise RuntimeError('Prerequisite: this action is disabled on a live bridge; use reviewed per-file launcher or new output paths.')
        if action=='batch':
            steps=p['steps']
            if len(steps)>25: raise ValueError('batch limited to 25 steps')
            validated=[]
            for step in steps:
                if not isinstance(step,dict) or set(step)!={'action','params'}: raise ValueError('Each step requires action and params')
                if step['action'] not in SAFE_BATCH: raise PermissionError('Batch action not permitted')
                validated.append((step['action'],validate_action(step['action'],step['params'])))
            # all validated upfront; failures mid-sequence are reported as partial, not rolled back
            results=[]
            for idx,(sub, args) in enumerate(validated):
                try: results.append({'action':sub,'result':self.execute(sub,args)})
                except Exception as e: return {'action':'batch','data':{'partial':True,'completed':idx,'error':str(e),'results':results}}
            return {'action':'batch','data':{'partial':False,'completed':len(results),'results':results}}
        group=ACTIONS[action].group
        fn=getattr(self,'_do_'+group)
        response=fn(action,p)
        return {'action':action,'data':response}

    def _do_system(self,a,p):
        b=self.bpy; scene=b.context.scene
        if a=='health': return {'version':b.app.version_string,'file':b.data.filepath,'scene':scene.name,'ready':True,'blender_main_thread':True}
        if a=='version': return {'version':b.app.version_string,'version_tuple':list(b.app.version),'binary_path':b.app.binary_path,'background':b.app.background}
        if a=='capabilities': return {'count':len(ACTIONS),'actions':[{'name':x.name,'risk':x.risk,'group':x.group} for x in ACTIONS.values()]}
        if a=='scene_summary': return {'scene':scene.name,'file':b.data.filepath,'objects':len(scene.objects),'materials':len(b.data.materials),'collections':len(b.data.collections),'frame':scene.frame_current,'fps':scene.render.fps,'engine':scene.render.engine,'camera':scene.camera.name if scene.camera else None}
        if a=='list_scenes': return [sc.name for sc in b.data.scenes]
        if a=='list_objects': return [{'name':o.name,'type':o.type} for o in scene.objects if not p['type'] or o.type==p['type'].upper()][:max(1,min(p['limit'],500))]
        if a=='list_materials': return [m.name for m in b.data.materials][:max(1,min(p['limit'],500))]
        if a=='list_images': return [{'name':m.name,'filepath':m.filepath} for m in b.data.images][:max(1,min(p['limit'],500))]
        if a=='list_actions': return [m.name for m in b.data.actions][:max(1,min(p['limit'],500))]
        if a=='list_collections': return [{'name':c.name,'objects':len(c.objects)} for c in b.data.collections]
        if a=='get_object':
            o=self._obj(p['name']); return {'name':o.name,'type':o.type,'location':list(o.location),'rotation':list(o.rotation_euler),'scale':list(o.scale),'parent':o.parent.name if o.parent else None,'materials':[m.name if m else None for m in o.data.materials] if hasattr(o.data,'materials') else [],'modifiers':[m.name for m in o.modifiers]}
        if a=='get_material':
            m=self._mat(p['name']); return {'name':m.name,'nodes':[{'name':n.name,'type':n.bl_idname} for n in m.node_tree.nodes] if m.use_nodes and m.node_tree else [],'diffuse_color':list(m.diffuse_color)}
        if a=='get_scene': return {'name':scene.name,'frame_start':scene.frame_start,'frame_end':scene.frame_end,'frame_current':scene.frame_current,'fps':scene.render.fps,'render_engine':scene.render.engine,'gravity':list(scene.gravity),'unit_system':scene.unit_settings.system}
        if a=='get_selection': return {'active':b.context.view_layer.objects.active.name if b.context.view_layer.objects.active else None,'selected':[ob.name for ob in b.context.selected_objects]}
        if a=='get_dependencies':
            o=self._obj(p['name']); return {'data':o.data.name if o.data else None,'parent':o.parent.name if o.parent else None,'children':[x.name for x in o.children],'modifiers':[{'name':m.name,'type':m.type} for m in o.modifiers],'constraints':[{'name':c.name,'type':c.type} for c in o.constraints]}
        if a=='get_mesh_stats':
            o=self._mesh(p['name']); m=o.data; return {'vertices':len(m.vertices),'edges':len(m.edges),'polygons':len(m.polygons),'triangles':sum(max(0,len(f.vertices)-2) for f in m.polygons)}
        if a=='get_render_status': return {'engine':scene.render.engine,'resolution_x':scene.render.resolution_x,'resolution_y':scene.render.resolution_y,'resolution_percentage':scene.render.resolution_percentage,'filepath':scene.render.filepath,'image_format':scene.render.image_settings.file_format}
        if a=='get_job_hint': return {'note':'Long renders and file loads run on Blender main thread. Poll bridge jobs; request timeouts do not cancel running Blender operators.'}
        raise NotImplementedError(a)

    def _do_scene(self,a,p):
        b=self.bpy; sc=b.context.scene
        if a=='new_scene':
            scene=b.data.scenes.new(_name(p['name'])); return {'scene':scene.name,'note':'Scene created; use set_scene to switch'}
        if a=='set_scene':
            target=b.data.scenes.get(p['name']);
            if target is None: raise ValueError('Scene not found')
            if b.context.window is None: raise RuntimeError('Switching active scene requires Blender UI window')
            b.context.window.scene=target; return {'scene':target.name}
        if a=='rename_scene':
            s=b.data.scenes.get(p['old_name']);
            if s is None: raise ValueError('Scene not found')
            s.name=_name(p['new_name']); return {'scene':s.name}
        if a=='delete_scene':
            s=b.data.scenes.get(p['name']);
            if s is None: raise ValueError('Scene not found')
            if len(b.data.scenes)<=1: raise ValueError('Cannot delete last scene')
            if s==sc: raise ValueError('Switch to another scene before deleting the active scene')
            b.data.scenes.remove(s);return {'deleted':p['name']}
        if a=='set_frame': sc.frame_set(p['frame']); return {'frame':sc.frame_current}
        if a=='set_frame_range':
            if not 1<=p['start']<=p['end']<=1000000:raise ValueError('Invalid frame range')
            sc.frame_start=p['start'];sc.frame_end=p['end'];sc.render.fps=int(_safe_number(p['fps'],1,240,'fps'));return {'start':sc.frame_start,'end':sc.frame_end,'fps':sc.render.fps}
        if a=='set_units':
            sc.unit_settings.system=_enum(p['system'],{'NONE','METRIC','IMPERIAL'},'unit system');sc.unit_settings.scale_length=_safe_number(p['scale'],0.000001,1000000,'scale');return {'system':sc.unit_settings.system}
        if a=='set_world_color':
            if sc.world is None:sc.world=b.data.worlds.new('Jarvis World')
            sc.world.color=_vec(p['color']);return {'color':list(sc.world.color)}
        if a=='new_collection':
            c=b.data.collections.new(_name(p['name']));parent=b.data.collections.get(p['parent']) if p['parent'] else sc.collection
            if parent is None:raise ValueError('Parent collection not found')
            parent.children.link(c);return {'collection':c.name}
        if a=='delete_collection':
            c=b.data.collections.get(p['name']);
            if c is None:raise ValueError('Collection not found')
            if p['delete_objects']:
                for o in list(c.objects):b.data.objects.remove(o,do_unlink=True)
            else:
                for o in list(c.objects):sc.collection.objects.link(o) if o.name not in sc.collection.objects else None
            b.data.collections.remove(c);return {'deleted':p['name']}
        if a=='rename_collection':
            c=b.data.collections.get(p['old_name']);
            if c is None:raise ValueError('Collection not found')
            c.name=_name(p['new_name']);return {'name':c.name}
        if a=='move_to_collection':
            o=self._obj(p['name']);c=b.data.collections.get(p['collection']);
            if c is None:raise ValueError('Collection not found')
            if o.name not in c.objects:c.objects.link(o)
            if p['exclusive']:
                for old in list(o.users_collection):
                    if old!=c:old.objects.unlink(o)
            return {'object':o.name,'collection':c.name}
        if a=='hide_collection':
            c=b.data.collections.get(p['name']);
            if c is None:raise ValueError('Collection not found')
            c.hide_render=p['hidden'];c.hide_viewport=p['hidden'];return {'hidden':p['hidden']}
        if a=='select_object':
            o=self._obj(p['name']);
            if not p['add']: self._choose(o)
            else:o.select_set(True);b.context.view_layer.objects.active=o
            return {'active':o.name}
        if a=='select_all':
            for o in sc.objects:o.select_set(True)
            return {'selected':len(sc.objects)}
        if a=='deselect_all':
            for o in b.context.selected_objects:o.select_set(False)
            return {'selected':0}
        if a=='select_by_type':
            typ=p['type'].upper();
            if not p['add']:
                for o in b.context.selected_objects:o.select_set(False)
            objs=[o for o in sc.objects if o.type==typ]
            for o in objs:o.select_set(True)
            if objs:b.context.view_layer.objects.active=objs[0]
            return {'selected':len(objs)}
        if a=='set_active_object':
            o=self._obj(p['name']);b.context.view_layer.objects.active=o;return {'active':o.name}
        if a=='rename_object':
            o=self._obj(p['old_name']);o.name=_name(p['new_name']);return {'name':o.name}
        if a=='delete_object':
            o=self._obj(p['name']);b.data.objects.remove(o,do_unlink=True);return {'deleted':p['name']}
        if a=='delete_selected':
            names=[o.name for o in b.context.selected_objects]
            for o in list(b.context.selected_objects): b.data.objects.remove(o,do_unlink=True)
            return {'deleted':names}
        if a=='duplicate_object':
            o=self._obj(p['name']);dup=o.copy();
            if o.data and not p['linked']:dup.data=o.data.copy()
            (o.users_collection[0] if o.users_collection else sc.collection).objects.link(dup)
            if p['new_name']:dup.name=_name(p['new_name'])
            return {'name':dup.name,'linked_data':p['linked']}
        if a=='set_transform':
            o=self._obj(p['name'])
            for attr in ('location','rotation','scale'):
                if p[attr] is not None: setattr(o,'rotation_euler' if attr=='rotation' else attr,_vec(p[attr]))
            return {'name':o.name,'location':list(o.location),'rotation':list(o.rotation_euler),'scale':list(o.scale)}
        if a=='move_object':
            o=self._obj(p['name']);o.location=[a+c for a,c in zip(o.location,_vec(p['offset']))];return {'location':list(o.location)}
        if a=='rotate_object':
            o=self._obj(p['name']);o.rotation_euler=[a+math.radians(c) for a,c in zip(o.rotation_euler,_vec(p['degrees_xyz']))];return {'rotation':list(o.rotation_euler)}
        if a=='scale_object':
            o=self._obj(p['name']);o.scale=[a*c for a,c in zip(o.scale,_vec(p['factor']))];return {'scale':list(o.scale)}
        if a=='set_visibility':
            o=self._obj(p['name']);
            if p['viewport'] is not None:o.hide_viewport=p['viewport']
            if p['render'] is not None:o.hide_render=p['render']
            return {'hide_viewport':o.hide_viewport,'hide_render':o.hide_render}
        if a=='set_parent':
            ch=self._obj(p['child']);pa=self._obj(p['parent']);
            if ch==pa:raise ValueError('Cannot parent object to itself')
            probe=pa
            while probe is not None:
                if probe==ch:raise ValueError('Parent cycle would be created')
                probe=probe.parent
            mx=ch.matrix_world.copy();ch.parent=pa;ch.matrix_world=mx;return {'child':ch.name,'parent':pa.name}
        if a=='clear_parent':
            o=self._obj(p['name']);mx=o.matrix_world.copy();o.parent=None;o.matrix_world=mx;return {'name':o.name,'parent':None}
        if a=='set_custom_property':
            o=self._obj(p['name']);o[_name(p['key'])]=p['value'];return {'name':o.name,'key':p['key']}
        if a=='remove_custom_property':
            o=self._obj(p['name']);
            if p['key'] not in o:raise ValueError('Custom property not found')
            del o[p['key']];return {'key':p['key']}
        if a=='join_objects':
            objs=[self._mesh(n) for n in p['names']]
            if len(set(o.name for o in objs))<2:raise ValueError('At least two different meshes required')
            self._choose(objs[0],objs[1:]);_ok_op(b.ops.object.join(),'object.join');return {'name':objs[0].name}
        if a=='apply_transform':
            o=self._obj(p['name']);self._choose(o);_ok_op(b.ops.object.transform_apply(location=p['location'],rotation=p['rotation'],scale=p['scale']),'transform_apply');return {'name':o.name}
        if a=='set_origin':
            o=self._obj(p['name']);self._choose(o)
            typ=_enum(p['mode'],{'ORIGIN_GEOMETRY','ORIGIN_CURSOR','GEOMETRY_ORIGIN','ORIGIN_CENTER_OF_MASS'},'origin mode')
            _ok_op(b.ops.object.origin_set(type=typ),'origin_set');return {'name':o.name,'mode':typ}
        if a=='smooth_shading':
            o=self._mesh(p['name'])
            for poly in o.data.polygons:poly.use_smooth=p['smooth']
            return {'name':o.name,'smooth':p['smooth']}
        if a=='add_empty':
            ob=b.data.objects.new(_name(p['name']),None);sc.collection.objects.link(ob);ob.location=_vec(p['location']);return {'name':ob.name,'type':'EMPTY'}
        raise NotImplementedError(a)

    def _do_mesh(self,a,p):
        b=self.bpy
        prims={
            'add_cube':('primitive_cube_add',lambda:{'size':_safe_number(p['size'],0.00001,100000,'size')}),
            'add_uv_sphere':('primitive_uv_sphere_add',lambda:{'segments':int(_safe_number(p['segments'],3,512,'segments')),'ring_count':int(_safe_number(p['rings'],3,256,'rings')),'radius':_safe_number(p['radius'],0.00001,100000,'radius')}),
            'add_ico_sphere':('primitive_ico_sphere_add',lambda:{'subdivisions':int(_safe_number(p['subdivisions'],1,7,'subdivisions')),'radius':_safe_number(p['radius'],0.00001,100000,'radius')}),
            'add_cylinder':('primitive_cylinder_add',lambda:{'vertices':int(_safe_number(p['vertices'],3,512,'vertices')),'radius':_safe_number(p['radius'],0.00001,100000,'radius'),'depth':_safe_number(p['depth'],0.00001,100000,'depth')}),
            'add_cone':('primitive_cone_add',lambda:{'vertices':int(_safe_number(p['vertices'],3,512,'vertices')),'radius1':_safe_number(p['radius1'],0,100000,'radius1'),'radius2':_safe_number(p['radius2'],0,100000,'radius2'),'depth':_safe_number(p['depth'],0.00001,100000,'depth')}),
            'add_torus':('primitive_torus_add',lambda:{'major_radius':_safe_number(p['major_radius'],0.0001,10000,'major_radius'),'minor_radius':_safe_number(p['minor_radius'],0.0001,10000,'minor_radius')}),
            'add_plane':('primitive_plane_add',lambda:{'size':_safe_number(p['size'],0.00001,100000,'size')}),
            'add_grid':('primitive_grid_add',lambda:{'x_subdivisions':int(_safe_number(p['x_subdivisions'],2,500,'x_subdivisions')),'y_subdivisions':int(_safe_number(p['y_subdivisions'],2,500,'y_subdivisions')),'size':_safe_number(p['size'],0.00001,100000,'size')}),
            'add_circle':('primitive_circle_add',lambda:{'vertices':int(_safe_number(p['vertices'],3,512,'vertices')),'radius':_safe_number(p['radius'],0.00001,100000,'radius')}),
            'add_monkey':('primitive_monkey_add',lambda:{}),
        }
        if a in prims:
            op_name, getter=prims[a]
            _ok_op(getattr(b.ops.mesh,op_name)(location=_vec(p['location']),**getter()),op_name)
            obj=b.context.object;obj.name=_name(p['name']);return {'name':obj.name,'type':obj.type}
        if a=='add_mesh':
            vertices=p['vertices']; faces=p['faces']
            if not 3<=len(vertices)<=50000 or len(faces)>100000:raise ValueError('Mesh size exceeds limits')
            vertices=[_vec(v) for v in vertices]
            faces_out=[]
            for face in faces:
                if not isinstance(face,list) or not 3<=len(face)<=1000 or any(type(i)!=int or i<0 or i>=len(vertices) for i in face):
                    raise ValueError('Face contains invalid indices')
                faces_out.append(tuple(face))
            m=b.data.meshes.new(_name(p['name'])+'Mesh');m.from_pydata(vertices,[],faces_out);m.update()
            ob=b.data.objects.new(_name(p['name']),m);b.context.scene.collection.objects.link(ob)
            return {'name':ob.name,'vertices':len(vertices),'faces':len(faces_out)}
        if a=='mesh_vertices':
            m=self._mesh(p['name']).data
            return {'count':len(m.vertices),'vertices':[list(v.co) for v in list(m.vertices)[:int(_safe_number(p['limit'],1,2000,'limit'))]]}
        if a=='set_vertex':
            mesh=self._mesh(p['name']).data;idx=p['index']
            if not 0<=idx<len(mesh.vertices):raise ValueError('Vertex index out of bounds')
            mesh.vertices[idx].co=_vec(p['coordinate']);mesh.update();return {'index':idx,'coordinate':list(mesh.vertices[idx].co)}
        if a=='transform_vertices':
            mesh=self._mesh(p['name']).data;idxs=p['indices'];off=_vec(p['offset'])
            if len(idxs)>50000 or any(type(idx)!=int or idx<0 or idx>=len(mesh.vertices) for idx in idxs):raise ValueError('Invalid vertex indices')
            for idx in idxs:
                v=mesh.vertices[idx];v.co=[v.co[i]+off[i] for i in range(3)]
            mesh.update();return {'changed':len(idxs)}
        if a=='flip_normals':
            m=self._mesh(p['name']).data;m.flip_normals();m.update();return {'name':p['name']}
        if a=='voxel_remesh':
            ob=self._mesh(p['name']);ob.data.remesh_voxel_size=_safe_number(p['voxel_size'],0.001,50,'voxel_size')
            self._choose(ob);_ok_op(b.ops.object.voxel_remesh(),'voxel_remesh');return {'name':ob.name}
        if a=='decimate_mesh':
            return self._do_modifier('add_modifier',{'name':p['name'],'type':'DECIMATE','modifier_name':'Jarvis Decimate'},extra={'ratio':_safe_number(p['ratio'],0.001,1,'ratio')})
        if a=='make_single_user':
            ob=self._mesh(p['name']);ob.data=ob.data.copy();return {'data':ob.data.name}
        if a in {'recalculate_normals','subdivide_mesh','merge_by_distance','triangulate_mesh','quadrangulate_mesh','extrude_region','inset_faces','bevel_edges','unwrap_uv','smart_uv_project'}:
            with self._edit(p['name']):
                b.ops.mesh.select_all(action='SELECT')
                if a=='recalculate_normals':
                    # Blender 4.1+ normals recalculate automatically on mesh updates;
                    # bmesh op explicitly checks topology and normal consistency.
                    import bmesh
                    bm=bmesh.from_edit_mesh(self._mesh(p['name']).data)
                    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.update_edit_mesh(self._mesh(p['name']).data)
                elif a=='subdivide_mesh': _ok_op(b.ops.mesh.subdivide(number_cuts=int(_safe_number(p['cuts'],1,12,'cuts'))),'subdivide')
                elif a=='merge_by_distance': _ok_op(b.ops.mesh.remove_doubles(threshold=_safe_number(p['threshold'],0.000001,10,'threshold')),'remove_doubles')
                elif a=='triangulate_mesh':_ok_op(b.ops.mesh.quads_convert_to_tris(),'triangulate')
                elif a=='quadrangulate_mesh':_ok_op(b.ops.mesh.tris_convert_to_quads(),'quads')
                elif a=='extrude_region':
                    _ok_op(b.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={'value':_vec(p['offset'])}),'extrude')
                elif a=='inset_faces':_ok_op(b.ops.mesh.inset(thickness=_safe_number(p['thickness'],0.000001,100,'thickness')),'inset')
                elif a=='bevel_edges':
                    b.ops.mesh.select_mode(type='EDGE')
                    _ok_op(b.ops.mesh.bevel(offset=_safe_number(p['offset'],0.000001,100,'offset'),segments=int(_safe_number(p['segments'],1,30,'segments'))),'bevel')
                elif a=='unwrap_uv':
                    _ok_op(b.ops.uv.unwrap(method=_enum(p['method'],{'ANGLE_BASED','CONFORMAL'},'unwrap method')),'unwrap')
                elif a=='smart_uv_project':
                    _ok_op(b.ops.uv.smart_project(island_margin=_safe_number(p['island_margin'],0,1,'island margin')),'smart_project')
            return {'name':p['name'],'operation':a}
        raise NotImplementedError(a)

    def _do_modifier(self,a,p,extra=None):
        b=self.bpy;ob=self._obj(p['name'])
        if a=='list_modifiers':return [{'name':m.name,'type':m.type} for m in ob.modifiers]
        if a=='list_constraints':return [{'name':c.name,'type':c.type,'target':c.target.name if hasattr(c,'target') and c.target else None} for c in ob.constraints]
        if a=='remove_modifier':
            mod=ob.modifiers.get(p['modifier_name']);
            if mod is None:raise ValueError('Modifier not found')
            ob.modifiers.remove(mod);return {'removed':p['modifier_name']}
        if a=='set_modifier':
            mod=ob.modifiers.get(p['modifier_name']);
            if mod is None:raise ValueError('Modifier not found')
            changes=p['properties']
            if len(changes)>20 or set(changes)-MOD_PROPS:raise ValueError('Unsupported modifier properties')
            for key,value in changes.items():
                if not hasattr(mod,key):raise ValueError(f'Property not valid for modifier: {key}')
                old=getattr(mod,key)
                if not isinstance(old,(float,int,str,bool,tuple)) and not hasattr(old,'__len__'):
                    raise ValueError('Modifier property type unsupported')
                if isinstance(value,(float,int)) and not isinstance(value,bool):_safe_number(value,-1e6,1e6,key)
                if isinstance(value,list):
                    if len(value)>4:raise ValueError('Modifier vector too long')
                    value=_vec(value,len(value))
                if not isinstance(value,(str,bool,int,float,tuple)):raise ValueError('Unsupported modifier property value')
                setattr(mod,key,value)
            return {'name':mod.name,'updated':list(changes)}
        if a=='apply_modifier':
            mod=ob.modifiers.get(p['modifier_name']);
            if mod is None:raise ValueError('Modifier not found')
            self._choose(ob);_ok_op(b.ops.object.modifier_apply(modifier=mod.name),'modifier_apply');return {'applied':p['modifier_name']}
        if a=='add_constraint':
            typ=_enum(p['type'].upper(),CONSTRAINTS,'constraint');constraint=ob.constraints.new(typ)
            if p['target'] and hasattr(constraint,'target'):constraint.target=self._obj(p['target'])
            return {'name':constraint.name,'type':constraint.type}
        if a=='remove_constraint':
            c=ob.constraints.get(p['constraint']);
            if c is None:raise ValueError('Constraint not found')
            ob.constraints.remove(c);return {'removed':p['constraint']}
        types={'add_subdivision':'SUBSURF','add_bevel':'BEVEL','add_solidify':'SOLIDIFY','add_mirror':'MIRROR','add_array':'ARRAY','add_boolean':'BOOLEAN','add_remesh':'REMESH','add_wireframe':'WIREFRAME'}
        typ=_enum(p['type'].upper(),MODIFIERS,'modifier') if a=='add_modifier' else types.get(a)
        if not typ:raise NotImplementedError(a)
        if typ in {'BOOLEAN','SUBSURF','MIRROR','REMESH','ARRAY','DECIMATE','WIREFRAME'} and ob.type!='MESH':raise ValueError('Modifier requires a mesh')
        mod=ob.modifiers.new(p.get('modifier_name') or 'Jarvis '+typ,typ)
        if a=='add_subdivision': mod.levels=int(_safe_number(p['levels'],0,6,'levels'));mod.render_levels=int(_safe_number(p['render_levels'],0,6,'render levels'))
        if a=='add_bevel':mod.width=_safe_number(p['width'],0,10000,'width');mod.segments=int(_safe_number(p['segments'],1,20,'segments'))
        if a=='add_solidify':mod.thickness=_safe_number(p['thickness'],-1000,1000,'thickness')
        if a=='add_mirror':mod.use_axis=tuple(axis==_enum(p['axis'],{'X','Y','Z'},'axis') for axis in 'XYZ')
        if a=='add_array':
            mod.count=int(_safe_number(p['count'],1,10000,'array count'));mod.relative_offset_displace=_vec(p['offset'])
        if a=='add_boolean':
            mod.operation=_enum(p['operation'],{'UNION','INTERSECT','DIFFERENCE'},'boolean operation');mod.object=self._mesh(p['target'])
            if mod.object==ob:ob.modifiers.remove(mod);raise ValueError('Cannot boolean with itself')
        if a=='add_remesh':mod.octree_depth=int(_safe_number(p['octree_depth'],1,10,'octree depth'))
        if a=='add_wireframe':mod.thickness=_safe_number(p['thickness'],0.000001,100,'thickness')
        if extra:
            for key,value in extra.items():setattr(mod,key,value)
        return {'modifier':mod.name,'type':mod.type,'object':ob.name}

    def _do_material(self,a,p):
        b=self.bpy
        if a=='create_material':
            m=b.data.materials.new(_name(p['name']));m.use_nodes=True
            principled=next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
            color=_vec(p['color'],4)
            if principled:
                principled.inputs['Base Color'].default_value=color
                principled.inputs['Metallic'].default_value=_safe_number(p['metallic'],0,1,'metallic')
                principled.inputs['Roughness'].default_value=_safe_number(p['roughness'],0,1,'roughness')
            m.diffuse_color=color
            return {'name':m.name}
        if a=='assign_material':
            ob=self._obj(p['name']);mat=self._mat(p['material'])
            if not getattr(ob.data,'materials',None) and not hasattr(ob.data,'materials'):
                raise ValueError('Object data does not support materials')
            slots=ob.data.materials;index=int(_safe_number(p['slot'],0,64,'slot'))
            if index>len(slots):raise ValueError('Material slot index must not skip slots')
            if index==len(slots): slots.append(mat)
            else:slots[index]=mat
            return {'object':ob.name,'material':mat.name,'slot':index}
        if a=='set_material':
            mat=self._mat(p['name']);mat.use_nodes=True
            bsdf=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
            if bsdf is None:raise ValueError('Material lacks principled BSDF')
            if p['color'] is not None:
                col=_vec(p['color'],4);bsdf.inputs['Base Color'].default_value=col;mat.diffuse_color=col
            for prop,sock in (('metallic','Metallic'),('roughness','Roughness'),('alpha','Alpha')):
                if p[prop] is not None:bsdf.inputs[sock].default_value=_safe_number(p[prop],0,1,prop)
            return {'material':mat.name}
        if a=='remove_material':
            mat=self._mat(p['name']);
            if mat.users>0 and not p['force']:raise ValueError('Material is in use (force=true requires approval)')
            b.data.materials.remove(mat,do_unlink=p['force']);return {'deleted':p['name']}
        if a=='duplicate_material':
            mat=self._mat(p['name']).copy();mat.name=_name(p['new_name']);return {'name':mat.name}
        if a=='clear_material_slots':
            ob=self._obj(p['name']);
            if not hasattr(ob.data,'materials'):raise ValueError('Object has no material slots')
            ob.data.materials.clear();return {'object':ob.name,'slots':0}
        if a=='set_object_color':
            ob=self._obj(p['name']);ob.color=_vec(p['color'],4);return {'color':list(ob.color)}
        if a=='load_image':
            file=_path(p['filepath'],suffixes={'.png','.jpg','.jpeg','.tif','.tiff','.exr','.hdr','.webp','.bmp'})
            img=b.data.images.load(file,check_existing=True);return {'image':img.name}
        if a in {'new_shader_node','list_shader_nodes','link_shader_nodes','unlink_shader_nodes','set_shader_input','set_shader_attribute','assign_image_texture'}:
            mat=self._mat(p['material']);mat.use_nodes=True;tree=mat.node_tree
            if a=='new_shader_node':
                typ=_enum(p['node_type'],SHADER_NODES,'shader node type');n=self._new_node(tree,typ)
                if p['label']:n.label=_name(p['label'])
                return {'node':n.name,'type':n.bl_idname}
            if a=='list_shader_nodes':return [{'name':n.name,'type':n.bl_idname,'inputs':[x.name for x in n.inputs],'outputs':[x.name for x in n.outputs]} for n in tree.nodes]
            if a=='link_shader_nodes':self._node_link(tree,p['from_node'],p['from_socket'],p['to_node'],p['to_socket']);return {'linked':True}
            if a=='unlink_shader_nodes':
                n=tree.nodes.get(p['to_node']);
                if n is None or n.inputs.get(p['to_socket']) is None:raise ValueError('Node socket missing')
                links=[link for link in tree.links if link.to_node==n and link.to_socket==n.inputs[p['to_socket']]]
                for link in links:tree.links.remove(link)
                return {'unlinked':len(links)}
            if a=='set_shader_input':
                n=tree.nodes.get(p['node']);
                if n is None:raise ValueError('Node not found')
                self._set_socket(n,p['socket'],p['value']);return {'node':n.name,'socket':p['socket']}
            if a=='set_shader_attribute':
                n=tree.nodes.get(p['node']);
                if n is None:raise ValueError('Node not found')
                attr=_enum(p['attribute'],NODE_ATTRS,'node attribute')
                if not hasattr(n,attr):raise ValueError('Node does not have requested attribute')
                old=getattr(n,attr)
                if not isinstance(old,str):raise ValueError('Only string node enumerations supported')
                setattr(n,attr,p['value']);return {'node':n.name,'attribute':attr}
            if a=='assign_image_texture':
                filename=_path(p['filepath'],suffixes={'.png','.jpg','.jpeg','.exr','.hdr','.webp','.tif','.tiff','.bmp'})
                img=b.data.images.load(filename,check_existing=True)
                n=tree.nodes.new('ShaderNodeTexImage');n.image=img;return {'image':img.name,'node':n.name}
        raise NotImplementedError(a)

    def _do_nodes(self,a,p):
        b=self.bpy
        if a=='create_geometry_nodes':
            ob=self._obj(p['name']);group=b.data.node_groups.new(_name(p['group_name']),'GeometryNodeTree')
            # Blender 4.0+: geometry group IO sockets are declared on the node group interface.
            group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
            group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
            input_node=group.nodes.new('NodeGroupInput');input_node.location=(-200,0)
            output_node=group.nodes.new('NodeGroupOutput');output_node.location=(200,0)
            group.links.new(input_node.outputs['Geometry'],output_node.inputs['Geometry'])
            modifier=ob.modifiers.new('Jarvis Geometry Nodes','NODES');modifier.node_group=group
            return {'group':group.name,'modifier':modifier.name}
        if a=='list_geometry_nodes':
            group=self._node_group(p['name']);return [{'name':n.name,'type':n.bl_idname} for n in group.nodes]
        if a in {'add_geometry_node','link_geometry_nodes','set_geometry_input','remove_geometry_node'}:
            group=self._node_group(p['name'])
            if a=='add_geometry_node':
                typ=_enum(p['node_type'],GEO_NODES,'geometry node');n=self._new_node(group,typ)
                if p['label']:n.label=_name(p['label'])
                return {'node':n.name,'type':n.bl_idname}
            if a=='link_geometry_nodes': self._node_link(group,p['from_node'],p['from_socket'],p['to_node'],p['to_socket']);return {'linked':True}
            n=group.nodes.get(p['node']);
            if n is None:raise ValueError('Node missing')
            if a=='set_geometry_input':self._set_socket(n,p['socket'],p['value']);return {'node':n.name,'socket':p['socket']}
            group.nodes.remove(n);return {'removed':p['node']}
        sc=b.context.scene
        if a=='create_compositor':
            if hasattr(sc,'compositing_node_group'):
                if sc.compositing_node_group is None:
                    ng=b.data.node_groups.new('Jarvis Compositor','CompositorNodeTree')
                    ng.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
                    inp=ng.nodes.new('CompositorNodeRLayers');out=ng.nodes.new('NodeGroupOutput')
                    ng.links.new(inp.outputs['Image'],out.inputs['Image']);sc.compositing_node_group=ng
                sc.render.use_compositing=True
            else:
                sc.use_nodes=True
            return {'enabled':True}
        tree=sc.compositing_node_group if hasattr(sc,'compositing_node_group') else sc.node_tree
        if a=='list_compositor_nodes':
            return [{'name':n.name,'type':n.bl_idname} for n in tree.nodes] if tree else []
        if tree is None:raise ValueError('Enable compositor nodes first')
        if a=='add_compositor_node':
            typ=_enum(p['node_type'],COMPOSITOR_NODES,'compositor node');n=self._new_node(tree,typ)
            if p['label']:n.label=_name(p['label'])
            return {'node':n.name}
        if a=='link_compositor_nodes':self._node_link(tree,p['from_node'],p['from_socket'],p['to_node'],p['to_socket']);return {'linked':True}
        if a=='set_compositor_input':
            n=tree.nodes.get(p['node']);
            if n is None:raise ValueError('Node missing')
            self._set_socket(n,p['socket'],p['value']);return {'node':n.name}
        if a=='remove_compositor_node':
            n=tree.nodes.get(p['node']);
            if n is None:raise ValueError('Node missing')
            tree.nodes.remove(n);return {'removed':p['node']}
        raise NotImplementedError(a)

    def _do_studio(self,a,p):
        b=self.bpy; sc=b.context.scene
        if a=='add_camera':
            d=b.data.cameras.new(_name(p['name']));ob=b.data.objects.new(p['name'],d)
            sc.collection.objects.link(ob);ob.location=_vec(p['location']);ob.rotation_euler=_vec(p['rotation'])
            if sc.camera is None:sc.camera=ob
            return {'camera':ob.name}
        if a=='set_active_camera':
            ob=self._obj(p['name']);
            if ob.type!='CAMERA':raise ValueError('Object is not a camera')
            sc.camera=ob;return {'camera':ob.name}
        if a=='set_camera_lens':
            ob=self._obj(p['name']);
            if ob.type!='CAMERA':raise ValueError('Object is not a camera')
            ob.data.lens=_safe_number(p['lens'],1,1000,'lens');return {'lens':ob.data.lens}
        if a=='set_camera_dof':
            ob=self._obj(p['name']);
            if ob.type!='CAMERA':raise ValueError('Object is not a camera')
            ob.data.dof.use_dof=True;ob.data.dof.focus_distance=_safe_number(p['focus_distance'],0.01,1e6,'focus distance')
            ob.data.dof.aperture_fstop=_safe_number(p['fstop'],0.5,64,'f-stop');return {'focus_distance':ob.data.dof.focus_distance}
        if a=='aim_at':
            from mathutils import Vector
            ob=self._obj(p['name']);direction=Vector(_vec(p['target']))-ob.location
            if direction.length<1e-8:raise ValueError('Target equals object location')
            ob.rotation_euler=direction.to_track_quat(_enum(p['track_axis'],{'-Z','Z','X','-X','Y','-Y'},'track axis'),_enum(p['up_axis'],{'Y','Z','X'},'up axis')).to_euler()
            return {'rotation':list(ob.rotation_euler)}
        if a=='add_light':
            typ=_enum(p['type'],{'POINT','SUN','SPOT','AREA'},'light type')
            d=b.data.lights.new(_name(p['name']),typ);ob=b.data.objects.new(p['name'],d)
            sc.collection.objects.link(ob);ob.location=_vec(p['location']);d.energy=_safe_number(p['energy'],0,1e8,'light energy');return {'light':ob.name,'type':typ}
        if a=='set_light':
            ob=self._obj(p['name']);
            if ob.type!='LIGHT':raise ValueError('Object is not a light')
            if p['energy'] is not None:ob.data.energy=_safe_number(p['energy'],0,1e8,'light energy')
            if p['color'] is not None:ob.data.color=_vec(p['color'])
            if p['size'] is not None:
                if not hasattr(ob.data,'size'):raise ValueError('Light has no size property')
                ob.data.size=_safe_number(p['size'],0.001,1e5,'size')
            return {'light':ob.name}
        if a=='add_text':
            d=b.data.curves.new(_name(p['name']),'FONT');d.body=p['body'][:5000]
            d.size=_safe_number(p['size'],0.001,1e5,'text size');d.extrude=_safe_number(p['extrude'],0,100,'extrude')
            ob=b.data.objects.new(_name(p['name']),d);sc.collection.objects.link(ob);return {'name':ob.name}
        if a=='edit_text':
            ob=self._obj(p['name']);
            if ob.type!='FONT':raise ValueError('Object is not text')
            ob.data.body=p['body'][:5000]
            if p['size'] is not None:ob.data.size=_safe_number(p['size'],0.001,1e5,'size')
            if p['extrude'] is not None:ob.data.extrude=_safe_number(p['extrude'],0,100,'extrude')
            return {'name':ob.name,'body':ob.data.body}
        if a=='add_bezier_curve':
            points=p['points'];
            if not 2<=len(points)<=2000:raise ValueError('Curve requires 2..2000 points')
            d=b.data.curves.new(_name(p['name']),'CURVE');d.dimensions='3D';d.bevel_depth=_safe_number(p['bevel_depth'],0,100,'bevel depth')
            spline=d.splines.new('BEZIER');spline.bezier_points.add(len(points)-1)
            for dst,src in zip(spline.bezier_points,points):
                dst.co=_vec(src);dst.handle_left_type='AUTO';dst.handle_right_type='AUTO'
            ob=b.data.objects.new(_name(p['name']),d);sc.collection.objects.link(ob);return {'curve':ob.name,'points':len(points)}
        if a=='set_curve_bevel':
            ob=self._obj(p['name']);
            if ob.type!='CURVE':raise ValueError('Object is not curve')
            ob.data.bevel_depth=_safe_number(p['depth'],0,100,'bevel depth');return {'bevel_depth':ob.data.bevel_depth}
        if a=='add_armature':
            d=b.data.armatures.new(_name(p['name']));ob=b.data.objects.new(_name(p['name']),d)
            sc.collection.objects.link(ob);ob.location=_vec(p['location']);self._choose(ob)
            b.ops.object.mode_set(mode='EDIT')
            try:bone=d.edit_bones.new('Bone');bone.head=(0,0,0);bone.tail=(0,0,1)
            finally:b.ops.object.mode_set(mode='OBJECT')
            return {'armature':ob.name}
        if a=='add_bone':
            ob=self._obj(p['armature']);
            if ob.type!='ARMATURE':raise ValueError('Object is not armature')
            head=_vec(p['head']);tail=_vec(p['tail'])
            if sum((x-y)**2 for x,y in zip(head,tail))<1e-8:raise ValueError('Bone head/tail must differ')
            self._choose(ob);b.ops.object.mode_set(mode='EDIT')
            try:
                bone=ob.data.edit_bones.new(_name(p['name']));bone.head=head;bone.tail=tail
                if p['parent']:
                    parent=ob.data.edit_bones.get(p['parent']);
                    if parent is None:raise ValueError('Parent bone missing')
                    bone.parent=parent
                created_name=bone.name
            finally:b.ops.object.mode_set(mode='OBJECT')
            return {'bone':created_name}
        if a=='parent_to_armature':
            mesh=self._mesh(p['name']);arm=self._obj(p['armature']);
            if arm.type!='ARMATURE':raise ValueError('Parent is not armature')
            world=mesh.matrix_world.copy();mesh.parent=arm;mesh.matrix_world=world
            if p['add_modifier']:
                mod=mesh.modifiers.new('Jarvis Armature','ARMATURE');mod.object=arm
            return {'mesh':mesh.name,'armature':arm.name}
        if a=='add_vertex_group':
            ob=self._mesh(p['name']);group=ob.vertex_groups.new(name=_name(p['group']));return {'group':group.name}
        if a=='assign_vertices_group':
            ob=self._mesh(p['name']);group=ob.vertex_groups.get(p['group'])
            if group is None:raise ValueError('Vertex group not found')
            indices=p['indices']
            if not indices or len(indices)>50000 or any(type(i)!=int or not 0<=i<len(ob.data.vertices) for i in indices):raise ValueError('Invalid vertex indices')
            group.add(indices,_safe_number(p['weight'],0,1,'weight'),'REPLACE');return {'assigned':len(indices)}
        if a=='list_bones':
            ob=self._obj(p['name']);
            if ob.type!='ARMATURE':raise ValueError('Object is not armature')
            return [{'name':bone.name,'head':list(bone.head_local),'tail':list(bone.tail_local),'parent':bone.parent.name if bone.parent else None} for bone in ob.data.bones]
        raise NotImplementedError(a)

    def _do_animation(self,a,p):
        b=self.bpy;sc=b.context.scene
        if a=='list_markers':return [{'name':m.name,'frame':m.frame} for m in sc.timeline_markers]
        if a=='add_marker':
            m=sc.timeline_markers.new(_name(p['name']),frame=p['frame']);return {'name':m.name,'frame':m.frame}
        if a=='delete_marker':
            m=sc.timeline_markers.get(p['name']);
            if m is None:raise ValueError('Marker not found')
            sc.timeline_markers.remove(m);return {'deleted':p['name']}
        if a=='set_fps':sc.render.fps=int(_safe_number(p['fps'],1,240,'fps'));return {'fps':sc.render.fps}
        if a=='rename_action':
            action=b.data.actions.get(p['old_name']);
            if action is None:raise ValueError('Action not found')
            action.name=_name(p['new_name']);return {'action':action.name}
        ob=self._obj(p['name'])
        if a=='insert_keyframe' or a=='delete_keyframe':
            prop=_enum(p['property'],{'location','rotation_euler','scale','hide_render','hide_viewport'},'keyframe property')
            fn=ob.keyframe_insert if a=='insert_keyframe' else ob.keyframe_delete
            success=fn(data_path=prop,frame=p['frame'],index=p['index'])
            if not success:raise ValueError('Blender did not insert/delete keyframe')
            return {'name':ob.name,'frame':p['frame'],'property':prop}
        if a=='animate_transform':
            props=[]
            for key,attr in [('location','location'),('rotation','rotation_euler'),('scale','scale')]:
                if p[key] is not None:
                    setattr(ob,attr,_vec(p[key]));ob.keyframe_insert(data_path=attr,frame=p['frame']);props.append(attr)
            if not props:raise ValueError('At least one transform required')
            return {'name':ob.name,'keyed':props,'frame':p['frame']}
        if a=='set_interpolation':
            mode=_enum(p['mode'],{'LINEAR','BEZIER','CONSTANT'},'interpolation')
            anim=ob.animation_data
            if not anim or not anim.action:raise ValueError('Object has no animation action')
            action=anim.action
            curves=list(getattr(action,'fcurves',()) or ())
            if hasattr(action,'layers'):
                for layer in action.layers:
                    for strip in layer.strips:
                        for bag in getattr(strip,'channelbags',[]):
                            if anim.action_slot and bag.slot_handle==anim.action_slot.handle:
                                curves.extend(bag.fcurves)
            if not curves:raise ValueError('No F-curves found for the active action slot')
            n=0
            for fc in curves:
                for kp in fc.keyframe_points:
                    kp.interpolation=mode;n+=1
            return {'keyframes':n,'mode':mode}
        if a=='assign_action':
            act=b.data.actions.get(p['action']);
            if act is None:raise ValueError('Action not found')
            ob.animation_data_create();ob.animation_data.action=act;return {'name':ob.name,'action':act.name}
        if a=='clear_animation':ob.animation_data_clear();return {'cleared':ob.name}
        if a=='create_shape_key':
            ob=self._mesh(p['name'])
            if ob.data.shape_keys is None:ob.shape_key_add(name='Basis',from_mix=False)
            shape=ob.shape_key_add(name=_name(p['key']),from_mix=False);return {'key':shape.name}
        if a=='list_shape_keys':
            ob=self._mesh(p['name']);return [{'name':k.name,'value':k.value} for k in ob.data.shape_keys.key_blocks] if ob.data.shape_keys else []
        if a=='set_shape_key':
            ob=self._mesh(p['name']);sk=ob.data.shape_keys
            if sk is None or p['key'] not in sk.key_blocks:raise ValueError('Shape key not found')
            key=sk.key_blocks[p['key']];key.value=_safe_number(p['value'],0,1,'shape key value')
            if p['frame'] is not None:key.keyframe_insert(data_path='value',frame=p['frame'])
            return {'key':key.name,'value':key.value}
        if a=='set_nla_strip':
            act=b.data.actions.get(p['action']);
            if act is None:raise ValueError('Action not found')
            ob.animation_data_create();track=ob.animation_data.nla_tracks.new();track.name='Jarvis NLA'
            strip=track.strips.new(act.name,p['frame'],act);return {'strip':strip.name,'track':track.name}
        raise NotImplementedError(a)

    def _do_render(self,a,p):
        b=self.bpy;sc=b.context.scene;rd=sc.render
        if a=='set_render_engine':
            options={'CYCLES','BLENDER_WORKBENCH','BLENDER_EEVEE_NEXT','BLENDER_EEVEE'}
            engine=_enum(p['engine'],options,'render engine')
            if engine.startswith('BLENDER_EEVEE'):
                # Blender 5.x renamed engine identifier to BLENDER_EEVEE_NEXT or BLENDER_EEVEE.
                available={opt.identifier for opt in rd.bl_rna.properties['engine'].enum_items}
                engine=next((e for e in ['BLENDER_EEVEE_NEXT','BLENDER_EEVEE'] if e in available),engine)
            rd.engine=engine;return {'engine':rd.engine}
        if a=='set_render_resolution':
            rd.resolution_x=int(_safe_number(p['width'],16,16384,'width'))
            rd.resolution_y=int(_safe_number(p['height'],16,16384,'height'))
            rd.resolution_percentage=int(_safe_number(p['percentage'],1,100,'percentage'))
            return {'resolution':[rd.resolution_x,rd.resolution_y,rd.resolution_percentage]}
        if a=='set_render_samples':
            samples=int(_safe_number(p['samples'],1,100000,'samples'))
            if rd.engine=='CYCLES':
                if p['preview']:sc.cycles.preview_samples=samples
                else:sc.cycles.samples=samples
            else:raise ValueError('Sample setting supported for Cycles engine only')
            return {'samples':samples}
        if a=='set_render_format':
            fmt=_enum(p['format'],{'PNG','JPEG','OPEN_EXR','TIFF','BMP','WEBP','TARGA','HDR','FFMPEG'},'image output format')
            mode=_enum(p['color_mode'],{'BW','RGB','RGBA'},'color mode')
            rd.image_settings.file_format=fmt
            if fmt!='FFMPEG':rd.image_settings.color_mode=mode
            return {'format':fmt,'color_mode':rd.image_settings.color_mode}
        if a=='set_render_output':rd.filepath=_path(p['filepath'],'write');return {'filepath':rd.filepath}
        if a=='render_still':
            filepath=_path(p['filepath'],'write', {'.png','.jpeg','.jpg','.exr','.tif','.tiff','.bmp','.webp'}) if p['filepath'] else None
            old=rd.filepath
            try:
                if filepath:rd.filepath=filepath
                _ok_op(b.ops.render.render(write_still=bool(filepath)), 'render_still')
                return {'rendered':True,'saved':bool(filepath),'filepath':filepath}
            finally:rd.filepath=old
        if a=='render_animation':
            # Must explicitly configure protected output directory before rendering.
            _path(rd.filepath,'write')
            _ok_op(b.ops.render.render(animation=True),'render_animation');return {'rendered':True,'output':rd.filepath}
        if a=='set_transparent_film':rd.film_transparent=p['enabled'];return {'transparent':rd.film_transparent}
        if a=='set_camera_clip':
            ob=self._obj(p['name']);
            if ob.type!='CAMERA':raise ValueError('Object not camera')
            start=_safe_number(p['start'],0.001,1e8,'clip start');end=_safe_number(p['end'],0.002,1e9,'clip end')
            if start>=end:raise ValueError('clip start must be less than end')
            ob.data.clip_start=start;ob.data.clip_end=end;return {'start':start,'end':end}
        if a=='set_cycles_device':
            if rd.engine!='CYCLES':raise ValueError('Cycles device requires Cycles renderer')
            sc.cycles.device=_enum(p['device'],{'CPU','GPU'},'cycles device')
            return {'device':sc.cycles.device,'note':'GPU requires configured Blender Cycles compute backend; hardware availability not verified'}
        if a=='set_render_border':
            vals=[_safe_number(p[key],0,1,key) for key in ('min_x','min_y','max_x','max_y')]
            if vals[0]>=vals[2] or vals[1]>=vals[3]:raise ValueError('Border min must be below max')
            rd.border_min_x,rd.border_min_y,rd.border_max_x,rd.border_max_y=vals;rd.use_border=p['enabled']
            return {'border':vals,'enabled':rd.use_border}
        if a=='render_preview':
            percent=int(_safe_number(p['percentage'],1,100,'percentage'))
            samples=int(_safe_number(p['samples'],1,1000,'samples'))
            old_percent=rd.resolution_percentage
            old_samples=sc.cycles.samples if rd.engine=='CYCLES' else None
            try:
                rd.resolution_percentage=percent
                if old_samples is not None:sc.cycles.samples=samples
                _ok_op(b.ops.render.render(write_still=False),'render_preview')
                return {'rendered':True,'resolution_percentage':percent}
            finally:
                rd.resolution_percentage=old_percent
                if old_samples is not None:sc.cycles.samples=old_samples
        raise NotImplementedError(a)

    def _do_file(self,a,p):
        b=self.bpy
        if a=='save_project':
            target=p['filepath'] or b.data.filepath
            if not target:raise ValueError('Provide project filepath for first save')
            target=_path(target,'write',{'.blend'})
            _ok_op(b.ops.wm.save_as_mainfile(filepath=target),'save_project');return {'filepath':target,'saved':True}
        if a=='save_project_copy':
            target=_path(p['filepath'],'write',{'.blend'})
            _ok_op(b.ops.wm.save_as_mainfile(filepath=target,copy=True),'save_project_copy')
            return {'filepath':target,'saved_copy':True}
        if a=='open_project':
            target=_path(p['filepath'],'read',{'.blend'})
            # IMPORTANT: File load can reset timers/handlers and interrupt the bridge.
            # Unsupported over live bridge; use Jarvis launcher to open saved project in new Blender process.
            raise RuntimeError('open_project requires launching new Blender with --python start_blender_bridge.py -- <path>; live file loads can destroy active bridge state')
        if a=='revert_project':
            raise RuntimeError('revert_project intentionally disabled over live bridge; use approved restart of Blender')
        if a=='pack_resources':
            for collection in ('images','sounds','fonts','movieclips','libraries'):
                for block in getattr(b.data,collection,()):
                    source=getattr(block,'filepath','')
                    if source and source!='<builtin>':
                        _path(b.path.abspath(source,library=getattr(block,'library',None)),'read')
            _ok_op(b.ops.file.pack_all(),'pack_all');return {'packed':True}
        if a=='unpack_resources':
            _ok_op(b.ops.file.unpack_all(method=_enum(p['method'],{'USE_LOCAL','WRITE_LOCAL','USE_ORIGINAL','WRITE_ORIGINAL'},'unpack method')),'unpack_all')
            return {'unpacked':True}
        if a.startswith('import_') or a.startswith('export_'):
            kind=a.split('_',1)[1];export=a.startswith('export_')
            ext={'obj':{'.obj'},'fbx':{'.fbx'},'gltf':{'.glb','.gltf'},'stl':{'.stl'},'usd':{'.usd','.usda','.usdc','.usdz'},'alembic':{'.abc'}}[kind]
            filename=_path(p['filepath'],'write' if export else 'read',ext)
            if not export:
                calls={'obj':(b.ops.wm.obj_import,{}),'fbx':(b.ops.import_scene.fbx,{}),'gltf':(b.ops.import_scene.gltf,{}),
                       'stl':(b.ops.wm.stl_import,{}),'usd':(b.ops.wm.usd_import,{}),'alembic':(b.ops.wm.alembic_import,{})}
            else:
                calls={'obj':(b.ops.wm.obj_export,{'export_selected_objects':p.get('selected_only',False)}),
                       'fbx':(b.ops.export_scene.fbx,{'use_selection':p.get('selected_only',False)}),
                       'gltf':(b.ops.export_scene.gltf,{'export_format':'GLB' if filename.lower().endswith('.glb') else 'GLTF_SEPARATE','use_selection':p.get('selected_only',False)}),
                       'stl':(b.ops.wm.stl_export,{'export_selected_objects':p.get('selected_only',False)}),
                       'usd':(b.ops.wm.usd_export,{}),'alembic':(b.ops.wm.alembic_export,{})}
            op,kwargs=calls[kind];_ok_op(op(filepath=filename,**kwargs),a)
            return {'filepath':filename,'format':kind,'export':export}
        raise NotImplementedError(a)

    def _do_physics(self,a,p):
        b=self.bpy;sc=b.context.scene
        if a=='set_gravity':sc.gravity=_vec(p['gravity']);return {'gravity':list(sc.gravity)}
        if a=='set_rigidbody_world':
            if not sc.rigidbody_world:
                if not b.ops.rigidbody.world_add.poll():raise ValueError('Rigid body world not available')
                b.ops.rigidbody.world_add()
            sc.rigidbody_world.substeps_per_frame=int(_safe_number(p['substeps'],1,500,'substeps'))
            sc.rigidbody_world.solver_iterations=int(_safe_number(p['iterations'],1,500,'iterations'))
            return {'substeps':p['substeps'],'iterations':p['iterations']}
        ob=self._mesh(p['name'])
        if a=='add_rigidbody':
            self._choose(ob);_ok_op(b.ops.rigidbody.object_add(),'rigidbody_add')
            ob.rigid_body.type=_enum(p['type'],{'ACTIVE','PASSIVE'},'rigidbody type');ob.rigid_body.mass=_safe_number(p['mass'],0.0001,1e9,'mass')
            return {'name':ob.name,'type':ob.rigid_body.type}
        if a=='remove_rigidbody':
            self._choose(ob);_ok_op(b.ops.rigidbody.object_remove(),'rigidbody_remove');return {'removed':ob.name}
        if a=='set_rigidbody':
            rb=ob.rigid_body
            if rb is None:raise ValueError('Object has no rigid body')
            for k in ('mass','friction','restitution'):
                if p[k] is not None:setattr(rb,k,_safe_number(p[k],0,1e9 if k=='mass' else 1,k))
            return {'name':ob.name}
        if a in {'add_collision','add_cloth','add_fluid','add_soft_body'}:
            typ={'add_collision':'COLLISION','add_cloth':'CLOTH','add_fluid':'FLUID','add_soft_body':'SOFT_BODY'}[a]
            mod=ob.modifiers.new('Jarvis '+typ,typ);return {'modifier':mod.name,'type':mod.type}
        raise NotImplementedError(a)

    def _do_assets(self,a,p):
        b=self.bpy
        if a=='purge_orphans':
            _ok_op(b.ops.outliner.orphans_purge(do_recursive=True),'orphans_purge');return {'purged':True}
        typ=_enum(p['type'].upper(),{'OBJECT','MATERIAL','COLLECTION','ACTION','WORLD','MESH','IMAGE','NODE_GROUP'},'asset type')
        collections={'OBJECT':b.data.objects,'MATERIAL':b.data.materials,'COLLECTION':b.data.collections,
                     'ACTION':b.data.actions,'WORLD':b.data.worlds,'MESH':b.data.meshes,'IMAGE':b.data.images,'NODE_GROUP':b.data.node_groups}
        block=collections[typ].get(p['name'])
        if block is None:raise ValueError('Asset datablock not found')
        if a=='mark_asset':block.asset_mark();return {'marked':block.name}
        if a=='clear_asset':block.asset_clear();return {'cleared':block.name}
        if block.asset_data is None:raise ValueError('Mark datablock as asset first')
        if a=='set_asset_description':block.asset_data.description=p['description'][:2000];return {'description':block.asset_data.description}
        if a=='add_asset_tag':tag=block.asset_data.tags.new(_name(p['tag']));return {'tag':tag.name}
        raise NotImplementedError(a)
