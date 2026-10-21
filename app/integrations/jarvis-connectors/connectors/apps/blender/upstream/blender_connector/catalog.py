"""Declarative, allowlisted Blender actions, parameters and risk classifications.
All external input is validated twice: in the Jarvis client and inside Blender.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import math

MISSING = object()

@dataclass(frozen=True)
class Arg:
    kind: str
    default: Any = MISSING
    description: str = ""

@dataclass(frozen=True)
class Action:
    name: str
    group: str
    description: str
    fields: dict[str, Arg]
    risk: str = "write"

ACTIONS: dict[str, Action] = {}

def S(default=MISSING): return Arg("str", default)
def I(default=MISSING): return Arg("int", default)
def F(default=MISSING): return Arg("float", default)
def B(default=MISSING): return Arg("bool", default)
def L(default=MISSING): return Arg("list", default)
def D(default=MISSING): return Arg("dict", default)
def J(default=MISSING): return Arg("json", default)

def a(group, name, desc, fields=None, risk='write'):
    assert name not in ACTIONS, name
    ACTIONS[name] = Action(name, group, desc, fields or {}, risk)

# App and scene information
a('system','health','Check live Blender connection, version and current file',risk='read')
a('system','version','Get installed Blender version and build info',risk='read')
a('system','capabilities','List supported commands and approval classes',risk='read')
a('system','scene_summary','Summarize objects, materials, collections, frame and render settings',risk='read')
a('system','list_scenes','List scenes',risk='read')
a('system','list_objects','List named objects with optional type filter',{'type':S(''), 'limit':I(250)},'read')
a('system','list_materials','List materials',{'limit':I(250)},'read')
a('system','list_images','List loaded images',{'limit':I(250)},'read')
a('system','list_actions','List animation actions',{'limit':I(250)},'read')
a('system','list_collections','List collections',risk='read')
a('system','get_object','Inspect object, transforms and optional mesh statistics',{'name':S()},'read')
a('system','get_material','Inspect a material and its nodes',{'name':S()},'read')
a('system','get_scene','Inspect scene configuration',risk='read')
a('system','get_selection','Read selected and active objects',risk='read')
a('system','get_dependencies','Get object linked dependencies',{'name':S()},'read')
a('system','get_mesh_stats','Get polygon/edge/vertex statistics',{'name':S()},'read')
a('system','get_render_status','Inspect render output/settings',risk='read')
a('system','get_job_hint','Explain asynchronous long-running operation behavior',risk='read')

# Scene/selection/objects
a('scene','new_scene','Create a new scene',{'name':S()})
a('scene','set_scene','Switch active scene',{'name':S()})
a('scene','rename_scene','Rename scene',{'old_name':S(), 'new_name':S()})
a('scene','delete_scene','Delete named scene',{'name':S()},'destructive')
a('scene','set_frame','Set current frame',{'frame':I()})
a('scene','set_frame_range','Set frame start/end and optional FPS',{'start':I(),'end':I(),'fps':I(24)})
a('scene','set_units','Set units system and length scale',{'system':S('METRIC'),'scale':F(1.0)})
a('scene','set_world_color','Set world background color',{'color':L()})
a('scene','new_collection','Create collection',{'name':S(),'parent':S('')})
a('scene','delete_collection','Delete collection; objects remain if linked elsewhere',{'name':S(),'delete_objects':B(False)},'destructive')
a('scene','rename_collection','Rename a collection',{'old_name':S(),'new_name':S()})
a('scene','move_to_collection','Link object to collection, optionally unlink others',{'name':S(),'collection':S(),'exclusive':B(False)})
a('scene','hide_collection','Hide collection in renders and viewports',{'name':S(),'hidden':B(True)})
a('scene','select_object','Select object and make it active',{'name':S(),'add':B(False)})
a('scene','select_all','Select all objects')
a('scene','deselect_all','Deselect every object')
a('scene','select_by_type','Select objects of type',{'type':S(),'add':B(False)})
a('scene','set_active_object','Make object active',{'name':S()})
a('scene','rename_object','Rename object',{'old_name':S(),'new_name':S()})
a('scene','delete_object','Delete object',{'name':S()},'destructive')
a('scene','delete_selected','Delete selected objects',risk='destructive')
a('scene','duplicate_object','Duplicate object, linked data optional',{'name':S(),'new_name':S(''),'linked':B(False)})
a('scene','set_transform','Set absolute location/rotation/scale',{'name':S(),'location':L(None),'rotation':L(None),'scale':L(None)})
a('scene','move_object','Move object relative to current location',{'name':S(),'offset':L()})
a('scene','rotate_object','Rotate object relative to Euler rotation',{'name':S(),'degrees_xyz':L()})
a('scene','scale_object','Multiply object scale',{'name':S(),'factor':L()})
a('scene','set_visibility','Set hide viewport/render on object',{'name':S(),'viewport':B(None),'render':B(None)})
a('scene','set_parent','Parent to object, preserving world matrix',{'child':S(),'parent':S()})
a('scene','clear_parent','Remove object parenting, preserving world transform',{'name':S()})
a('scene','set_custom_property','Set a JSON-compatible custom property value',{'name':S(),'key':S(),'value':J()})
a('scene','remove_custom_property','Remove custom property',{'name':S(),'key':S()})
a('scene','join_objects','Join mesh objects into active mesh',{'names':L()},'destructive')
a('scene','apply_transform','Apply location, rotation, or scale to object data',{'name':S(),'location':B(False),'rotation':B(True),'scale':B(True)})
a('scene','set_origin','Set object origin to geometry or cursor',{'name':S(),'mode':S('ORIGIN_GEOMETRY')})
a('scene','smooth_shading','Smooth or flat shade mesh faces',{'name':S(),'smooth':B(True)})
a('scene','add_empty','Create an Empty object',{'name':S('Empty'),'location':L([0,0,0])})

# Primitives and geometry
a('mesh','add_cube','Create cube',{'name':S('Cube'),'size':F(2.0),'location':L([0,0,0])})
a('mesh','add_uv_sphere','Create UV sphere',{'name':S('UVSphere'),'segments':I(32),'rings':I(16),'radius':F(1.0),'location':L([0,0,0])})
a('mesh','add_ico_sphere','Create Icosphere',{'name':S('Icosphere'),'subdivisions':I(2),'radius':F(1.0),'location':L([0,0,0])})
a('mesh','add_cylinder','Create cylinder',{'name':S('Cylinder'),'vertices':I(32),'radius':F(1.0),'depth':F(2.0),'location':L([0,0,0])})
a('mesh','add_cone','Create cone',{'name':S('Cone'),'vertices':I(32),'radius1':F(1.0),'radius2':F(0.0),'depth':F(2.0),'location':L([0,0,0])})
a('mesh','add_torus','Create torus',{'name':S('Torus'),'major_radius':F(1.0),'minor_radius':F(0.25),'location':L([0,0,0])})
a('mesh','add_plane','Create plane',{'name':S('Plane'),'size':F(2.0),'location':L([0,0,0])})
a('mesh','add_grid','Create subdivided grid',{'name':S('Grid'),'x_subdivisions':I(10),'y_subdivisions':I(10),'size':F(2.0),'location':L([0,0,0])})
a('mesh','add_circle','Create mesh circle',{'name':S('Circle'),'vertices':I(32),'radius':F(1.0),'location':L([0,0,0])})
a('mesh','add_monkey','Create Suzanne mesh',{'name':S('Suzanne'),'location':L([0,0,0])})
a('mesh','add_mesh','Create custom mesh from vertices and face lists',{'name':S(),'vertices':L(),'faces':L()})
a('mesh','mesh_vertices','Get mesh vertex coordinates (limited)',{'name':S(),'limit':I(200)},'read')
a('mesh','set_vertex','Update mesh vertex coordinate',{'name':S(),'index':I(),'coordinate':L()})
a('mesh','transform_vertices','Offset vertices of mesh',{'name':S(),'indices':L(),'offset':L()})
a('mesh','flip_normals','Reverse mesh polygon winding',{'name':S()})
a('mesh','recalculate_normals','Recalculate normals',{'name':S()})
a('mesh','subdivide_mesh','Subdivide selected mesh',{'name':S(),'cuts':I(1)})
a('mesh','merge_by_distance','Remove coincident vertices',{'name':S(),'threshold':F(0.0001)})
a('mesh','triangulate_mesh','Triangulate mesh faces',{'name':S()})
a('mesh','quadrangulate_mesh','Convert eligible triangles to quads',{'name':S()})
a('mesh','extrude_region','Extrude all mesh regions',{'name':S(),'offset':L([0,0,1])})
a('mesh','inset_faces','Inset all mesh faces',{'name':S(),'thickness':F(0.05)})
a('mesh','bevel_edges','Bevel mesh edges',{'name':S(),'offset':F(0.05),'segments':I(2)})
a('mesh','unwrap_uv','UV unwrap mesh faces',{'name':S(),'method':S('ANGLE_BASED')})
a('mesh','smart_uv_project','Smart UV project mesh',{'name':S(),'island_margin':F(0.02)})
a('mesh','voxel_remesh','Voxel remesh mesh',{'name':S(),'voxel_size':F(0.1)})
a('mesh','decimate_mesh','Create decimate modifier',{'name':S(),'ratio':F(0.5)})
a('mesh','make_single_user','Make selected object mesh data unique',{'name':S()})

# Modifiers, constraints
a('modifier','add_modifier','Add allowlisted modifier by enum name',{'name':S(),'type':S(),'modifier_name':S('')})
a('modifier','remove_modifier','Remove named modifier',{'name':S(),'modifier_name':S()},'destructive')
a('modifier','set_modifier','Set whitelisted modifier properties',{'name':S(),'modifier_name':S(),'properties':D()})
a('modifier','apply_modifier','Apply named modifier destructively',{'name':S(),'modifier_name':S()},'destructive')
a('modifier','list_modifiers','Read mesh modifiers',{'name':S()},'read')
a('modifier','add_subdivision','Add subdivision modifier',{'name':S(),'levels':I(2),'render_levels':I(2)})
a('modifier','add_bevel','Add bevel modifier',{'name':S(),'width':F(0.05),'segments':I(3)})
a('modifier','add_solidify','Add solidify modifier',{'name':S(),'thickness':F(0.05)})
a('modifier','add_mirror','Add mirror modifier',{'name':S(),'axis':S('X')})
a('modifier','add_array','Add array modifier',{'name':S(),'count':I(3),'offset':L([1,0,0])})
a('modifier','add_boolean','Add Boolean modifier between mesh objects',{'name':S(),'target':S(),'operation':S('DIFFERENCE')})
a('modifier','add_remesh','Add remesh modifier',{'name':S(),'octree_depth':I(4)})
a('modifier','add_wireframe','Add wireframe modifier',{'name':S(),'thickness':F(0.02)})
a('modifier','add_constraint','Add allowlisted constraint type',{'name':S(),'type':S(),'target':S('')})
a('modifier','remove_constraint','Remove named constraint',{'name':S(),'constraint':S()},'destructive')
a('modifier','list_constraints','List constraints',{'name':S()},'read')

# Materials and shader nodes
a('material','create_material','Create principled material',{'name':S(),'color':L([0.8,0.8,0.8,1.0]),'metallic':F(0.0),'roughness':F(0.5)})
a('material','assign_material','Assign material to object',{'name':S(),'material':S(),'slot':I(0)})
a('material','set_material','Update principled PBR values',{'name':S(),'color':L(None),'metallic':F(None),'roughness':F(None),'alpha':F(None)})
a('material','remove_material','Delete material datablock if unused or forced',{'name':S(),'force':B(False)},'destructive')
a('material','duplicate_material','Duplicate existing material',{'name':S(),'new_name':S()})
a('material','clear_material_slots','Clear all material slots of object',{'name':S()},'destructive')
a('material','new_shader_node','Add shader node from allowlist',{'material':S(),'node_type':S(),'label':S('')})
a('material','list_shader_nodes','List nodes and sockets in shader material',{'material':S()},'read')
a('material','link_shader_nodes','Link shader nodes by node and socket names',{'material':S(),'from_node':S(),'from_socket':S(),'to_node':S(),'to_socket':S()})
a('material','unlink_shader_nodes','Remove shader link by target node socket',{'material':S(),'to_node':S(),'to_socket':S()})
a('material','set_shader_input','Set a shader node socket default value',{'material':S(),'node':S(),'socket':S(),'value':L()})
a('material','set_shader_attribute','Set safe scalar/enum attribute on shader node',{'material':S(),'node':S(),'attribute':S(),'value':S()})
a('material','load_image','Load image into Blender',{'filepath':S()},'filesystem')
a('material','assign_image_texture','Create image texture node for material',{'material':S(),'filepath':S()},'filesystem')
a('material','set_object_color','Set viewport RGBA object color',{'name':S(),'color':L()})

# Geometry node trees
a('nodes','create_geometry_nodes','Create geometry node group and modifier',{'name':S(),'group_name':S()})
a('nodes','list_geometry_nodes','Inspect geometry node tree on object',{'name':S()},'read')
a('nodes','add_geometry_node','Add allowlisted node to geometry tree',{'name':S(),'node_type':S(),'label':S('')})
a('nodes','link_geometry_nodes','Connect sockets in object geometry node group',{'name':S(),'from_node':S(),'from_socket':S(),'to_node':S(),'to_socket':S()})
a('nodes','set_geometry_input','Set geometry node socket value',{'name':S(),'node':S(),'socket':S(),'value':L()})
a('nodes','remove_geometry_node','Remove node from geometry node tree',{'name':S(),'node':S()},'destructive')
a('nodes','create_compositor','Enable compositor scene nodes',{})
a('nodes','list_compositor_nodes','List compositor nodes',{},'read')
a('nodes','add_compositor_node','Add allowlisted compositor node',{'node_type':S(),'label':S('')})
a('nodes','link_compositor_nodes','Link compositor nodes',{'from_node':S(),'from_socket':S(),'to_node':S(),'to_socket':S()})
a('nodes','set_compositor_input','Set compositor node input',{'node':S(),'socket':S(),'value':L()})
a('nodes','remove_compositor_node','Remove compositor node',{'node':S()},'destructive')

# Camera, lighting, curves, text
a('studio','add_camera','Create camera',{'name':S('Camera'),'location':L([0,-6,3]),'rotation':L([1.25,0,0])})
a('studio','set_active_camera','Set camera used for scene rendering',{'name':S()})
a('studio','set_camera_lens','Set lens in millimeters',{'name':S(),'lens':F()})
a('studio','set_camera_dof','Set depth of field focus/aperture',{'name':S(),'focus_distance':F(),'fstop':F(2.8)})
a('studio','aim_at','Rotate object toward target point',{'name':S(),'target':L(),'track_axis':S('-Z'),'up_axis':S('Y')})
a('studio','add_light','Add POINT/SUN/SPOT/AREA light',{'name':S('Light'),'type':S('AREA'),'energy':F(1000.0),'location':L([0,0,4])})
a('studio','set_light','Modify light energy and color',{'name':S(),'energy':F(None),'color':L(None),'size':F(None)})
a('studio','add_text','Add text object',{'name':S('Text'),'body':S('Jarvis'),'size':F(1.0),'extrude':F(0.0)})
a('studio','edit_text','Change font object text',{'name':S(),'body':S(),'size':F(None),'extrude':F(None)})
a('studio','add_bezier_curve','Create 3D Bezier curve',{'name':S('Curve'),'points':L(),'bevel_depth':F(0.02)})
a('studio','set_curve_bevel','Adjust curve bevel',{'name':S(),'depth':F()})
a('studio','add_armature','Create single-bone armature',{'name':S('Armature'),'location':L([0,0,0])})
a('studio','add_bone','Add armature edit bone',{'armature':S(),'name':S(),'head':L(),'tail':L(),'parent':S('')})
a('studio','parent_to_armature','Parent mesh to armature, creating modifier optionally',{'name':S(),'armature':S(),'add_modifier':B(True)})
a('studio','add_vertex_group','Add vertex group',{'name':S(),'group':S()})
a('studio','assign_vertices_group','Assign vertices with weight',{'name':S(),'group':S(),'indices':L(),'weight':F(1.0)})
a('studio','list_bones','List bones in armature',{'name':S()},'read')

# Animation, NLA and shape keys
a('animation','insert_keyframe','Insert keyframe for object property',{'name':S(),'property':S('location'),'frame':I(),'index':I(-1)})
a('animation','delete_keyframe','Delete keyframe',{'name':S(),'property':S(),'frame':I(),'index':I(-1)},'destructive')
a('animation','animate_transform','Keyframe location/rotation/scale at frame',{'name':S(),'frame':I(),'location':L(None),'rotation':L(None),'scale':L(None)})
a('animation','set_interpolation','Set keyframe interpolation in action',{'name':S(),'mode':S('BEZIER')})
a('animation','rename_action','Rename animation action',{'old_name':S(),'new_name':S()})
a('animation','assign_action','Assign named action to object',{'name':S(),'action':S()})
a('animation','clear_animation','Clear object animation',{'name':S()},'destructive')
a('animation','create_shape_key','Create shape key on mesh',{'name':S(),'key':S()})
a('animation','set_shape_key','Set shape key value and optional keyframe',{'name':S(),'key':S(),'value':F(),'frame':I(None)})
a('animation','list_shape_keys','Inspect mesh shape keys',{'name':S()},'read')
a('animation','set_nla_strip','Create NLA strip from action',{'name':S(),'action':S(),'frame':I()})
a('animation','add_marker','Create timeline marker',{'name':S(),'frame':I()})
a('animation','delete_marker','Delete timeline marker',{'name':S()},'destructive')
a('animation','list_markers','List timeline markers',risk='read')
a('animation','set_fps','Set scene FPS',{'fps':I()})

# Rendering, files, pipeline
#a version-specific EEVEE renderer is selected by detection
a('render','set_render_engine','Select BLENDER_EEVEE_NEXT / CYCLES / BLENDER_WORKBENCH',{'engine':S()})
a('render','set_render_resolution','Set resolution pixels and percentage',{'width':I(),'height':I(),'percentage':I(100)})
a('render','set_render_samples','Set render samples',{'samples':I(),'preview':B(False)})
a('render','set_render_format','Set PNG/JPEG/OPEN_EXR/etc output format',{'format':S('PNG'),'color_mode':S('RGBA')})
a('render','set_render_output','Set render output path',{'filepath':S()},'filesystem')
a('render','render_still','Render current frame and optionally save image',{'filepath':S('')},'filesystem')
a('render','render_animation','Render animation to configured output',risk='filesystem')
a('render','set_transparent_film','Enable transparent-film rendering',{'enabled':B(True)})
a('render','set_camera_clip','Set camera near/far clipping planes',{'name':S(),'start':F(),'end':F()})
a('render','set_cycles_device','Set cycles scene device CPU or GPU',{'device':S('CPU')})
a('render','set_render_border','Set normalized crop border for scene',{'min_x':F(),'min_y':F(),'max_x':F(),'max_y':F(),'enabled':B(True)})
a('render','render_preview','Render still at temporary low resolution',{'percentage':I(25),'samples':I(16)},'filesystem')
a('file','save_project','Save current blend file',{'filepath':S('')},'filesystem')
a('file','save_project_copy','Save a copy preserving current working file',{'filepath':S()},'filesystem')
a('file','import_obj','Import Wavefront OBJ',{'filepath':S()},'filesystem')
a('file','import_fbx','Import FBX',{'filepath':S()},'filesystem')
a('file','import_gltf','Import glTF/GLB',{'filepath':S()},'filesystem')
a('file','import_stl','Import STL',{'filepath':S()},'filesystem')
a('file','import_usd','Import USD asset',{'filepath':S()},'filesystem')
a('file','import_alembic','Import Alembic asset',{'filepath':S()},'filesystem')
a('file','export_obj','Export Wavefront OBJ',{'filepath':S(),'selected_only':B(False)},'filesystem')
a('file','export_fbx','Export FBX',{'filepath':S(),'selected_only':B(False)},'filesystem')
a('file','export_gltf','Export GLB/glTF',{'filepath':S(),'selected_only':B(False)},'filesystem')
a('file','export_stl','Export STL',{'filepath':S(),'selected_only':B(False)},'filesystem')
a('file','export_usd','Export USD scene',{'filepath':S()},'filesystem')
a('file','export_alembic','Export Alembic scene',{'filepath':S()},'filesystem')
a('file','pack_resources','Pack external resources in blend file',risk='filesystem')
a('file','unpack_resources','Unpack resources (writes filesystem)',{'method':S('USE_LOCAL')},'filesystem')

# Physics and simulation
a('physics','add_rigidbody','Attach active/passive rigid body',{'name':S(),'type':S('ACTIVE'),'mass':F(1.0)})
a('physics','remove_rigidbody','Remove rigid body',{'name':S()},'destructive')
a('physics','set_rigidbody','Set rigid body physics settings',{'name':S(),'mass':F(None),'friction':F(None),'restitution':F(None)})
a('physics','add_collision','Add collision modifier',{'name':S()})
a('physics','add_cloth','Add cloth modifier',{'name':S()})
a('physics','add_fluid','Add fluid modifier (requires configuration)',{'name':S()})
a('physics','add_soft_body','Add soft-body modifier',{'name':S()})
a('physics','set_gravity','Set scene gravity vector',{'gravity':L()})
a('physics','set_rigidbody_world','Configure rigid body scene substeps/iterations',{'substeps':I(10),'iterations':I(10)})

# Asset and metadata management
a('assets','mark_asset','Mark local datablock as asset',{'type':S(),'name':S()})
a('assets','clear_asset','Clear local asset mark',{'type':S(),'name':S()},'destructive')
a('assets','set_asset_description','Set asset description',{'type':S(),'name':S(),'description':S()})
a('assets','add_asset_tag','Add asset catalog tag',{'type':S(),'name':S(),'tag':S()})
a('assets','purge_orphans','Remove unused datablocks',risk='destructive')

# Generic safe batched plans, dry-run validation; no Python scripting
# Batches explicitly exclude file, destructive, and expensive render ops.
a('system','batch','Execute safe bounded sequence of other actions',{'steps':L()},'write')

def _check_value(arg: Arg, val: Any, label: str):
    if val is None and arg.default is None:
        return None
    if arg.kind == 'json':
        def visit(obj, depth=0):
            if depth>8:raise ValueError(f'{label} JSON nesting exceeds 8')
            if obj is None or isinstance(obj,(bool,str)):
                if isinstance(obj,str) and len(obj)>2048:raise ValueError(f'{label} string too long')
                return
            if type(obj) in (int,float):
                if not math.isfinite(obj) or abs(obj)>1e9:raise ValueError(f'{label} numeric outside supported range')
                return
            if isinstance(obj,(list,dict)):
                if len(obj)>1000:raise ValueError(f'{label} too many entries')
                if isinstance(obj,dict):
                    for key,v in obj.items():
                        if not isinstance(key,str) or len(key)>150:raise ValueError('JSON keys must be short strings')
                        visit(v,depth+1)
                else:
                    for v in obj:visit(v,depth+1)
                return
            raise ValueError(f'{label} contains non-JSON value')
        visit(val)
        return val
    expected = {"str":str,"int":int,"float":(float,int),"bool":bool,"list":list,"dict":dict}[arg.kind]
    if not isinstance(val, expected) or (arg.kind == 'int' and isinstance(val,bool)) or (arg.kind == 'float' and isinstance(val,bool)):
        raise ValueError(f"{label} must be {arg.kind}")
    if isinstance(val, str) and len(val) > 2048:
        raise ValueError(f"{label} exceeds 2048 characters")
    if isinstance(val, (list,dict)) and len(val)>20000:
        raise ValueError(f"{label} collection too large")
    if arg.kind == 'float' and not math.isfinite(val):
        raise ValueError(f"{label} must be finite")
    if arg.kind == 'int' and abs(val)>10_000_000:
        raise ValueError(f"{label} outside supported range")
    return val

def validate_action(name: str, params: dict[str,Any]) -> dict[str,Any]:
    if name not in ACTIONS:
        raise ValueError(f"Unknown Blender action: {name}")
    if not isinstance(params, dict):
        raise ValueError('params must be an object')
    spec = ACTIONS[name]
    extra = set(params)-set(spec.fields)
    if extra:
        raise ValueError(f"Unknown parameter(s) for {name}: {', '.join(sorted(extra))}")
    out = {}
    for key,arg in spec.fields.items():
        if key in params:
            value=params[key]
        elif arg.default is MISSING:
            raise ValueError(f"Missing required parameter: {key}")
        else:
            value=arg.default
        out[key]=_check_value(arg,value,key)
    return out

SAFE_BATCH = {name for name,spec in ACTIONS.items() if spec.risk=='write' and name!='batch'}
