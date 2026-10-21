# All 203 Jarvis Blender MCP commands

Exactly **200** Blender operations + **3** bridge/job helpers. All command names are prefixed `blender_`.

## Parameter representation

`str`, `int`, `float`, `bool`, `list`, `dict`, `json`; a trailing `=...` indicates optional default. All filesystem/destructive commands require Jarvis host approval. `write` actions still need normal Jarvis tool permissions.

| Group | Commands |
|---|---:|
| system | 19 |
| scene | 36 |
| mesh | 28 |
| modifier | 16 |
| material | 15 |
| nodes | 12 |
| studio | 17 |
| animation | 15 |
| render | 12 |
| file | 16 |
| physics | 9 |
| assets | 5 |

## System

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_health` | `—` | read | Check live Blender connection, version and current file |
| `blender_version` | `—` | read | Get installed Blender version and build info |
| `blender_capabilities` | `—` | read | List supported commands and approval classes |
| `blender_scene_summary` | `—` | read | Summarize objects, materials, collections, frame and render settings |
| `blender_list_scenes` | `—` | read | List scenes |
| `blender_list_objects` | `type: str = '', limit: int = 250` | read | List named objects with optional type filter |
| `blender_list_materials` | `limit: int = 250` | read | List materials |
| `blender_list_images` | `limit: int = 250` | read | List loaded images |
| `blender_list_actions` | `limit: int = 250` | read | List animation actions |
| `blender_list_collections` | `—` | read | List collections |
| `blender_get_object` | `name: str` | read | Inspect object, transforms and optional mesh statistics |
| `blender_get_material` | `name: str` | read | Inspect a material and its nodes |
| `blender_get_scene` | `—` | read | Inspect scene configuration |
| `blender_get_selection` | `—` | read | Read selected and active objects |
| `blender_get_dependencies` | `name: str` | read | Get object linked dependencies |
| `blender_get_mesh_stats` | `name: str` | read | Get polygon/edge/vertex statistics |
| `blender_get_render_status` | `—` | read | Inspect render output/settings |
| `blender_get_job_hint` | `—` | read | Explain asynchronous long-running operation behavior |
| `blender_batch` | `steps: list` | write | Execute safe bounded sequence of other actions |

## Scene

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_new_scene` | `name: str` | write | Create a new scene |
| `blender_set_scene` | `name: str` | write | Switch active scene |
| `blender_rename_scene` | `old_name: str, new_name: str` | write | Rename scene |
| `blender_delete_scene` | `name: str` | destructive | Delete named scene |
| `blender_set_frame` | `frame: int` | write | Set current frame |
| `blender_set_frame_range` | `start: int, end: int, fps: int = 24` | write | Set frame start/end and optional FPS |
| `blender_set_units` | `system: str = 'METRIC', scale: float = 1.0` | write | Set units system and length scale |
| `blender_set_world_color` | `color: list` | write | Set world background color |
| `blender_new_collection` | `name: str, parent: str = ''` | write | Create collection |
| `blender_delete_collection` | `name: str, delete_objects: bool = False` | destructive | Delete collection; objects remain if linked elsewhere |
| `blender_rename_collection` | `old_name: str, new_name: str` | write | Rename a collection |
| `blender_move_to_collection` | `name: str, collection: str, exclusive: bool = False` | write | Link object to collection, optionally unlink others |
| `blender_hide_collection` | `name: str, hidden: bool = True` | write | Hide collection in renders and viewports |
| `blender_select_object` | `name: str, add: bool = False` | write | Select object and make it active |
| `blender_select_all` | `—` | write | Select all objects |
| `blender_deselect_all` | `—` | write | Deselect every object |
| `blender_select_by_type` | `type: str, add: bool = False` | write | Select objects of type |
| `blender_set_active_object` | `name: str` | write | Make object active |
| `blender_rename_object` | `old_name: str, new_name: str` | write | Rename object |
| `blender_delete_object` | `name: str` | destructive | Delete object |
| `blender_delete_selected` | `—` | destructive | Delete selected objects |
| `blender_duplicate_object` | `name: str, new_name: str = '', linked: bool = False` | write | Duplicate object, linked data optional |
| `blender_set_transform` | `name: str, location: list = None, rotation: list = None, scale: list = None` | write | Set absolute location/rotation/scale |
| `blender_move_object` | `name: str, offset: list` | write | Move object relative to current location |
| `blender_rotate_object` | `name: str, degrees_xyz: list` | write | Rotate object relative to Euler rotation |
| `blender_scale_object` | `name: str, factor: list` | write | Multiply object scale |
| `blender_set_visibility` | `name: str, viewport: bool = None, render: bool = None` | write | Set hide viewport/render on object |
| `blender_set_parent` | `child: str, parent: str` | write | Parent to object, preserving world matrix |
| `blender_clear_parent` | `name: str` | write | Remove object parenting, preserving world transform |
| `blender_set_custom_property` | `name: str, key: str, value: json` | write | Set a JSON-compatible custom property value |
| `blender_remove_custom_property` | `name: str, key: str` | write | Remove custom property |
| `blender_join_objects` | `names: list` | destructive | Join mesh objects into active mesh |
| `blender_apply_transform` | `name: str, location: bool = False, rotation: bool = True, scale: bool = True` | write | Apply location, rotation, or scale to object data |
| `blender_set_origin` | `name: str, mode: str = 'ORIGIN_GEOMETRY'` | write | Set object origin to geometry or cursor |
| `blender_smooth_shading` | `name: str, smooth: bool = True` | write | Smooth or flat shade mesh faces |
| `blender_add_empty` | `name: str = 'Empty', location: list = [0, 0, 0]` | write | Create an Empty object |

## Mesh

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_add_cube` | `name: str = 'Cube', size: float = 2.0, location: list = [0, 0, 0]` | write | Create cube |
| `blender_add_uv_sphere` | `name: str = 'UVSphere', segments: int = 32, rings: int = 16, radius: float = 1.0, location: list = [0, 0, 0]` | write | Create UV sphere |
| `blender_add_ico_sphere` | `name: str = 'Icosphere', subdivisions: int = 2, radius: float = 1.0, location: list = [0, 0, 0]` | write | Create Icosphere |
| `blender_add_cylinder` | `name: str = 'Cylinder', vertices: int = 32, radius: float = 1.0, depth: float = 2.0, location: list = [0, 0, 0]` | write | Create cylinder |
| `blender_add_cone` | `name: str = 'Cone', vertices: int = 32, radius1: float = 1.0, radius2: float = 0.0, depth: float = 2.0, location: list = [0, 0, 0]` | write | Create cone |
| `blender_add_torus` | `name: str = 'Torus', major_radius: float = 1.0, minor_radius: float = 0.25, location: list = [0, 0, 0]` | write | Create torus |
| `blender_add_plane` | `name: str = 'Plane', size: float = 2.0, location: list = [0, 0, 0]` | write | Create plane |
| `blender_add_grid` | `name: str = 'Grid', x_subdivisions: int = 10, y_subdivisions: int = 10, size: float = 2.0, location: list = [0, 0, 0]` | write | Create subdivided grid |
| `blender_add_circle` | `name: str = 'Circle', vertices: int = 32, radius: float = 1.0, location: list = [0, 0, 0]` | write | Create mesh circle |
| `blender_add_monkey` | `name: str = 'Suzanne', location: list = [0, 0, 0]` | write | Create Suzanne mesh |
| `blender_add_mesh` | `name: str, vertices: list, faces: list` | write | Create custom mesh from vertices and face lists |
| `blender_mesh_vertices` | `name: str, limit: int = 200` | read | Get mesh vertex coordinates (limited) |
| `blender_set_vertex` | `name: str, index: int, coordinate: list` | write | Update mesh vertex coordinate |
| `blender_transform_vertices` | `name: str, indices: list, offset: list` | write | Offset vertices of mesh |
| `blender_flip_normals` | `name: str` | write | Reverse mesh polygon winding |
| `blender_recalculate_normals` | `name: str` | write | Recalculate normals |
| `blender_subdivide_mesh` | `name: str, cuts: int = 1` | write | Subdivide selected mesh |
| `blender_merge_by_distance` | `name: str, threshold: float = 0.0001` | write | Remove coincident vertices |
| `blender_triangulate_mesh` | `name: str` | write | Triangulate mesh faces |
| `blender_quadrangulate_mesh` | `name: str` | write | Convert eligible triangles to quads |
| `blender_extrude_region` | `name: str, offset: list = [0, 0, 1]` | write | Extrude all mesh regions |
| `blender_inset_faces` | `name: str, thickness: float = 0.05` | write | Inset all mesh faces |
| `blender_bevel_edges` | `name: str, offset: float = 0.05, segments: int = 2` | write | Bevel mesh edges |
| `blender_unwrap_uv` | `name: str, method: str = 'ANGLE_BASED'` | write | UV unwrap mesh faces |
| `blender_smart_uv_project` | `name: str, island_margin: float = 0.02` | write | Smart UV project mesh |
| `blender_voxel_remesh` | `name: str, voxel_size: float = 0.1` | write | Voxel remesh mesh |
| `blender_decimate_mesh` | `name: str, ratio: float = 0.5` | write | Create decimate modifier |
| `blender_make_single_user` | `name: str` | write | Make selected object mesh data unique |

## Modifier

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_add_modifier` | `name: str, type: str, modifier_name: str = ''` | write | Add allowlisted modifier by enum name |
| `blender_remove_modifier` | `name: str, modifier_name: str` | destructive | Remove named modifier |
| `blender_set_modifier` | `name: str, modifier_name: str, properties: dict` | write | Set whitelisted modifier properties |
| `blender_apply_modifier` | `name: str, modifier_name: str` | destructive | Apply named modifier destructively |
| `blender_list_modifiers` | `name: str` | read | Read mesh modifiers |
| `blender_add_subdivision` | `name: str, levels: int = 2, render_levels: int = 2` | write | Add subdivision modifier |
| `blender_add_bevel` | `name: str, width: float = 0.05, segments: int = 3` | write | Add bevel modifier |
| `blender_add_solidify` | `name: str, thickness: float = 0.05` | write | Add solidify modifier |
| `blender_add_mirror` | `name: str, axis: str = 'X'` | write | Add mirror modifier |
| `blender_add_array` | `name: str, count: int = 3, offset: list = [1, 0, 0]` | write | Add array modifier |
| `blender_add_boolean` | `name: str, target: str, operation: str = 'DIFFERENCE'` | write | Add Boolean modifier between mesh objects |
| `blender_add_remesh` | `name: str, octree_depth: int = 4` | write | Add remesh modifier |
| `blender_add_wireframe` | `name: str, thickness: float = 0.02` | write | Add wireframe modifier |
| `blender_add_constraint` | `name: str, type: str, target: str = ''` | write | Add allowlisted constraint type |
| `blender_remove_constraint` | `name: str, constraint: str` | destructive | Remove named constraint |
| `blender_list_constraints` | `name: str` | read | List constraints |

## Material

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_create_material` | `name: str, color: list = [0.8, 0.8, 0.8, 1.0], metallic: float = 0.0, roughness: float = 0.5` | write | Create principled material |
| `blender_assign_material` | `name: str, material: str, slot: int = 0` | write | Assign material to object |
| `blender_set_material` | `name: str, color: list = None, metallic: float = None, roughness: float = None, alpha: float = None` | write | Update principled PBR values |
| `blender_remove_material` | `name: str, force: bool = False` | destructive | Delete material datablock if unused or forced |
| `blender_duplicate_material` | `name: str, new_name: str` | write | Duplicate existing material |
| `blender_clear_material_slots` | `name: str` | destructive | Clear all material slots of object |
| `blender_new_shader_node` | `material: str, node_type: str, label: str = ''` | write | Add shader node from allowlist |
| `blender_list_shader_nodes` | `material: str` | read | List nodes and sockets in shader material |
| `blender_link_shader_nodes` | `material: str, from_node: str, from_socket: str, to_node: str, to_socket: str` | write | Link shader nodes by node and socket names |
| `blender_unlink_shader_nodes` | `material: str, to_node: str, to_socket: str` | write | Remove shader link by target node socket |
| `blender_set_shader_input` | `material: str, node: str, socket: str, value: list` | write | Set a shader node socket default value |
| `blender_set_shader_attribute` | `material: str, node: str, attribute: str, value: str` | write | Set safe scalar/enum attribute on shader node |
| `blender_load_image` | `filepath: str` | filesystem | Load image into Blender |
| `blender_assign_image_texture` | `material: str, filepath: str` | filesystem | Create image texture node for material |
| `blender_set_object_color` | `name: str, color: list` | write | Set viewport RGBA object color |

## Nodes

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_create_geometry_nodes` | `name: str, group_name: str` | write | Create geometry node group and modifier |
| `blender_list_geometry_nodes` | `name: str` | read | Inspect geometry node tree on object |
| `blender_add_geometry_node` | `name: str, node_type: str, label: str = ''` | write | Add allowlisted node to geometry tree |
| `blender_link_geometry_nodes` | `name: str, from_node: str, from_socket: str, to_node: str, to_socket: str` | write | Connect sockets in object geometry node group |
| `blender_set_geometry_input` | `name: str, node: str, socket: str, value: list` | write | Set geometry node socket value |
| `blender_remove_geometry_node` | `name: str, node: str` | destructive | Remove node from geometry node tree |
| `blender_create_compositor` | `—` | write | Enable compositor scene nodes |
| `blender_list_compositor_nodes` | `—` | read | List compositor nodes |
| `blender_add_compositor_node` | `node_type: str, label: str = ''` | write | Add allowlisted compositor node |
| `blender_link_compositor_nodes` | `from_node: str, from_socket: str, to_node: str, to_socket: str` | write | Link compositor nodes |
| `blender_set_compositor_input` | `node: str, socket: str, value: list` | write | Set compositor node input |
| `blender_remove_compositor_node` | `node: str` | destructive | Remove compositor node |

## Studio

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_add_camera` | `name: str = 'Camera', location: list = [0, -6, 3], rotation: list = [1.25, 0, 0]` | write | Create camera |
| `blender_set_active_camera` | `name: str` | write | Set camera used for scene rendering |
| `blender_set_camera_lens` | `name: str, lens: float` | write | Set lens in millimeters |
| `blender_set_camera_dof` | `name: str, focus_distance: float, fstop: float = 2.8` | write | Set depth of field focus/aperture |
| `blender_aim_at` | `name: str, target: list, track_axis: str = '-Z', up_axis: str = 'Y'` | write | Rotate object toward target point |
| `blender_add_light` | `name: str = 'Light', type: str = 'AREA', energy: float = 1000.0, location: list = [0, 0, 4]` | write | Add POINT/SUN/SPOT/AREA light |
| `blender_set_light` | `name: str, energy: float = None, color: list = None, size: float = None` | write | Modify light energy and color |
| `blender_add_text` | `name: str = 'Text', body: str = 'Jarvis', size: float = 1.0, extrude: float = 0.0` | write | Add text object |
| `blender_edit_text` | `name: str, body: str, size: float = None, extrude: float = None` | write | Change font object text |
| `blender_add_bezier_curve` | `name: str = 'Curve', points: list, bevel_depth: float = 0.02` | write | Create 3D Bezier curve |
| `blender_set_curve_bevel` | `name: str, depth: float` | write | Adjust curve bevel |
| `blender_add_armature` | `name: str = 'Armature', location: list = [0, 0, 0]` | write | Create single-bone armature |
| `blender_add_bone` | `armature: str, name: str, head: list, tail: list, parent: str = ''` | write | Add armature edit bone |
| `blender_parent_to_armature` | `name: str, armature: str, add_modifier: bool = True` | write | Parent mesh to armature, creating modifier optionally |
| `blender_add_vertex_group` | `name: str, group: str` | write | Add vertex group |
| `blender_assign_vertices_group` | `name: str, group: str, indices: list, weight: float = 1.0` | write | Assign vertices with weight |
| `blender_list_bones` | `name: str` | read | List bones in armature |

## Animation

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_insert_keyframe` | `name: str, property: str = 'location', frame: int, index: int = -1` | write | Insert keyframe for object property |
| `blender_delete_keyframe` | `name: str, property: str, frame: int, index: int = -1` | destructive | Delete keyframe |
| `blender_animate_transform` | `name: str, frame: int, location: list = None, rotation: list = None, scale: list = None` | write | Keyframe location/rotation/scale at frame |
| `blender_set_interpolation` | `name: str, mode: str = 'BEZIER'` | write | Set keyframe interpolation in action |
| `blender_rename_action` | `old_name: str, new_name: str` | write | Rename animation action |
| `blender_assign_action` | `name: str, action: str` | write | Assign named action to object |
| `blender_clear_animation` | `name: str` | destructive | Clear object animation |
| `blender_create_shape_key` | `name: str, key: str` | write | Create shape key on mesh |
| `blender_set_shape_key` | `name: str, key: str, value: float, frame: int = None` | write | Set shape key value and optional keyframe |
| `blender_list_shape_keys` | `name: str` | read | Inspect mesh shape keys |
| `blender_set_nla_strip` | `name: str, action: str, frame: int` | write | Create NLA strip from action |
| `blender_add_marker` | `name: str, frame: int` | write | Create timeline marker |
| `blender_delete_marker` | `name: str` | destructive | Delete timeline marker |
| `blender_list_markers` | `—` | read | List timeline markers |
| `blender_set_fps` | `fps: int` | write | Set scene FPS |

## Render

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_set_render_engine` | `engine: str` | write | Select BLENDER_EEVEE_NEXT / CYCLES / BLENDER_WORKBENCH |
| `blender_set_render_resolution` | `width: int, height: int, percentage: int = 100` | write | Set resolution pixels and percentage |
| `blender_set_render_samples` | `samples: int, preview: bool = False` | write | Set render samples |
| `blender_set_render_format` | `format: str = 'PNG', color_mode: str = 'RGBA'` | write | Set PNG/JPEG/OPEN_EXR/etc output format |
| `blender_set_render_output` | `filepath: str` | filesystem | Set render output path |
| `blender_render_still` | `filepath: str = ''` | filesystem | Render current frame and optionally save image |
| `blender_render_animation` | `—` | filesystem | Render animation to configured output |
| `blender_set_transparent_film` | `enabled: bool = True` | write | Enable transparent-film rendering |
| `blender_set_camera_clip` | `name: str, start: float, end: float` | write | Set camera near/far clipping planes |
| `blender_set_cycles_device` | `device: str = 'CPU'` | write | Set cycles scene device CPU or GPU |
| `blender_set_render_border` | `min_x: float, min_y: float, max_x: float, max_y: float, enabled: bool = True` | write | Set normalized crop border for scene |
| `blender_render_preview` | `percentage: int = 25, samples: int = 16` | filesystem | Render still at temporary low resolution |

## File

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_save_project` | `filepath: str = ''` | filesystem | Save current blend file |
| `blender_save_project_copy` | `filepath: str` | filesystem | Save a copy preserving current working file |
| `blender_import_obj` | `filepath: str` | filesystem | Import Wavefront OBJ |
| `blender_import_fbx` | `filepath: str` | filesystem | Import FBX |
| `blender_import_gltf` | `filepath: str` | filesystem | Import glTF/GLB |
| `blender_import_stl` | `filepath: str` | filesystem | Import STL |
| `blender_import_usd` | `filepath: str` | filesystem | Import USD asset |
| `blender_import_alembic` | `filepath: str` | filesystem | Import Alembic asset |
| `blender_export_obj` | `filepath: str, selected_only: bool = False` | filesystem | Export Wavefront OBJ |
| `blender_export_fbx` | `filepath: str, selected_only: bool = False` | filesystem | Export FBX |
| `blender_export_gltf` | `filepath: str, selected_only: bool = False` | filesystem | Export GLB/glTF |
| `blender_export_stl` | `filepath: str, selected_only: bool = False` | filesystem | Export STL |
| `blender_export_usd` | `filepath: str` | filesystem | Export USD scene |
| `blender_export_alembic` | `filepath: str` | filesystem | Export Alembic scene |
| `blender_pack_resources` | `—` | filesystem | Pack external resources in blend file |
| `blender_unpack_resources` | `method: str = 'USE_LOCAL'` | filesystem | Unpack resources (writes filesystem) |

## Physics

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_add_rigidbody` | `name: str, type: str = 'ACTIVE', mass: float = 1.0` | write | Attach active/passive rigid body |
| `blender_remove_rigidbody` | `name: str` | destructive | Remove rigid body |
| `blender_set_rigidbody` | `name: str, mass: float = None, friction: float = None, restitution: float = None` | write | Set rigid body physics settings |
| `blender_add_collision` | `name: str` | write | Add collision modifier |
| `blender_add_cloth` | `name: str` | write | Add cloth modifier |
| `blender_add_fluid` | `name: str` | write | Add fluid modifier (requires configuration) |
| `blender_add_soft_body` | `name: str` | write | Add soft-body modifier |
| `blender_set_gravity` | `gravity: list` | write | Set scene gravity vector |
| `blender_set_rigidbody_world` | `substeps: int = 10, iterations: int = 10` | write | Configure rigid body scene substeps/iterations |

## Assets

| MCP tool | Parameters | Risk | Function |
|---|---|---|---|
| `blender_mark_asset` | `type: str, name: str` | write | Mark local datablock as asset |
| `blender_clear_asset` | `type: str, name: str` | destructive | Clear local asset mark |
| `blender_set_asset_description` | `type: str, name: str, description: str` | write | Set asset description |
| `blender_add_asset_tag` | `type: str, name: str, tag: str` | write | Add asset catalog tag |
| `blender_purge_orphans` | `—` | destructive | Remove unused datablocks |

## Bridge/job utilities

| MCP tool | Parameters | Function |
|---|---|---|
| `blender_bridge_health` | none | Check connected Blender bridge and queue |
| `blender_job_status` | `job_id: str` | Poll queue/running/done/error state |
| `blender_wait_job` | `job_id: str, timeout_seconds: float = 30.0` | Wait without resubmitting render/edit |

## Safety and support notes

- The bridge does **not** contain an arbitrary `execute_python` operation. To extend it, add a typed action and tested implementation to the catalog and regenerate the MCP adapter.
- File and destructive operations are refused by the standalone MCP child until a real Jarvis approval callback is supplied.
- Render actions are asynchronous: call `blender_job_status` or `blender_wait_job` with the returned job ID.
- Blender 5.2 changed the compositor API; this package uses `scene.compositing_node_group` when present.
- Live Blender testing is required to claim an action actually works on your installed version.
