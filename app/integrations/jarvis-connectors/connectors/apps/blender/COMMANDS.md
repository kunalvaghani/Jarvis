# Blender command inventory - 2026-10-21 IST

203 names using the actual centralized BaseConnector. Acceptance is specific to the disposable fixtures on Blender 5.2.2; successful execution alone does not prove correctness for arbitrary scenes. See the integration audit for effects, prerequisites and untested gates.

## animation (15)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_insert_keyframe` | write | UNTESTED |
| `blender_delete_keyframe` | destructive | UNTESTED |
| `blender_animate_transform` | write | UNTESTED |
| `blender_set_interpolation` | write | VERIFIED IN BLENDER |
| `blender_rename_action` | write | UNTESTED |
| `blender_assign_action` | write | UNTESTED |
| `blender_clear_animation` | destructive | VERIFIED IN BLENDER |
| `blender_create_shape_key` | write | VERIFIED IN BLENDER |
| `blender_set_shape_key` | write | UNTESTED |
| `blender_list_shape_keys` | read | UNTESTED |
| `blender_set_nla_strip` | write | UNTESTED |
| `blender_add_marker` | write | VERIFIED IN BLENDER |
| `blender_delete_marker` | destructive | VERIFIED IN BLENDER |
| `blender_list_markers` | read | UNTESTED |
| `blender_set_fps` | write | VERIFIED IN BLENDER |

## assets (5)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_mark_asset` | write | VERIFIED IN BLENDER |
| `blender_clear_asset` | destructive | VERIFIED IN BLENDER |
| `blender_set_asset_description` | write | VERIFIED IN BLENDER |
| `blender_add_asset_tag` | write | VERIFIED IN BLENDER |
| `blender_purge_orphans` | destructive | UNTESTED |

## bridge (3)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_bridge_health` | read | VERIFIED IN BLENDER |
| `blender_job_status` | read | VERIFIED IN BLENDER |
| `blender_wait_job` | read | VERIFIED IN BLENDER |

## file (16)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_save_project` | filesystem | VERIFIED IN BLENDER |
| `blender_save_project_copy` | filesystem | VERIFIED IN BLENDER |
| `blender_import_obj` | filesystem | UNTESTED |
| `blender_import_fbx` | filesystem | UNTESTED |
| `blender_import_gltf` | filesystem | UNTESTED |
| `blender_import_stl` | filesystem | UNTESTED |
| `blender_import_usd` | filesystem | UNTESTED |
| `blender_import_alembic` | filesystem | UNTESTED |
| `blender_export_obj` | filesystem | VERIFIED IN BLENDER |
| `blender_export_fbx` | filesystem | VERIFIED IN BLENDER |
| `blender_export_gltf` | filesystem | VERIFIED IN BLENDER |
| `blender_export_stl` | filesystem | VERIFIED IN BLENDER |
| `blender_export_usd` | filesystem | VERIFIED IN BLENDER |
| `blender_export_alembic` | filesystem | VERIFIED IN BLENDER |
| `blender_pack_resources` | filesystem | UNTESTED |
| `blender_unpack_resources` | filesystem | UNTESTED |

## material (15)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_create_material` | write | VERIFIED IN BLENDER |
| `blender_assign_material` | write | VERIFIED IN BLENDER |
| `blender_set_material` | write | VERIFIED IN BLENDER |
| `blender_remove_material` | destructive | VERIFIED IN BLENDER |
| `blender_duplicate_material` | write | VERIFIED IN BLENDER |
| `blender_clear_material_slots` | destructive | VERIFIED IN BLENDER |
| `blender_new_shader_node` | write | UNTESTED |
| `blender_list_shader_nodes` | read | UNTESTED |
| `blender_link_shader_nodes` | write | UNTESTED |
| `blender_unlink_shader_nodes` | write | UNTESTED |
| `blender_set_shader_input` | write | VERIFIED IN BLENDER |
| `blender_set_shader_attribute` | write | UNTESTED |
| `blender_load_image` | filesystem | UNTESTED |
| `blender_assign_image_texture` | filesystem | UNTESTED |
| `blender_set_object_color` | write | UNTESTED |

## mesh (28)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_add_cube` | write | VERIFIED IN BLENDER |
| `blender_add_uv_sphere` | write | VERIFIED IN BLENDER |
| `blender_add_ico_sphere` | write | VERIFIED IN BLENDER |
| `blender_add_cylinder` | write | VERIFIED IN BLENDER |
| `blender_add_cone` | write | VERIFIED IN BLENDER |
| `blender_add_torus` | write | VERIFIED IN BLENDER |
| `blender_add_plane` | write | VERIFIED IN BLENDER |
| `blender_add_grid` | write | VERIFIED IN BLENDER |
| `blender_add_circle` | write | VERIFIED IN BLENDER |
| `blender_add_monkey` | write | VERIFIED IN BLENDER |
| `blender_add_mesh` | write | VERIFIED IN BLENDER |
| `blender_mesh_vertices` | read | UNTESTED |
| `blender_set_vertex` | write | VERIFIED IN BLENDER |
| `blender_transform_vertices` | write | UNTESTED |
| `blender_flip_normals` | write | UNTESTED |
| `blender_recalculate_normals` | write | UNTESTED |
| `blender_subdivide_mesh` | write | UNTESTED |
| `blender_merge_by_distance` | write | UNTESTED |
| `blender_triangulate_mesh` | write | UNTESTED |
| `blender_quadrangulate_mesh` | write | UNTESTED |
| `blender_extrude_region` | write | UNTESTED |
| `blender_inset_faces` | write | UNTESTED |
| `blender_bevel_edges` | write | UNTESTED |
| `blender_unwrap_uv` | write | UNTESTED |
| `blender_smart_uv_project` | write | UNTESTED |
| `blender_voxel_remesh` | write | UNTESTED |
| `blender_decimate_mesh` | write | UNTESTED |
| `blender_make_single_user` | write | UNTESTED |

## modifier (16)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_add_modifier` | write | UNTESTED |
| `blender_remove_modifier` | destructive | VERIFIED IN BLENDER |
| `blender_set_modifier` | write | VERIFIED IN BLENDER |
| `blender_apply_modifier` | destructive | VERIFIED IN BLENDER |
| `blender_list_modifiers` | read | UNTESTED |
| `blender_add_subdivision` | write | VERIFIED IN BLENDER |
| `blender_add_bevel` | write | VERIFIED IN BLENDER |
| `blender_add_solidify` | write | VERIFIED IN BLENDER |
| `blender_add_mirror` | write | VERIFIED IN BLENDER |
| `blender_add_array` | write | VERIFIED IN BLENDER |
| `blender_add_boolean` | write | VERIFIED IN BLENDER |
| `blender_add_remesh` | write | VERIFIED IN BLENDER |
| `blender_add_wireframe` | write | VERIFIED IN BLENDER |
| `blender_add_constraint` | write | UNTESTED |
| `blender_remove_constraint` | destructive | VERIFIED IN BLENDER |
| `blender_list_constraints` | read | UNTESTED |

## nodes (12)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_create_geometry_nodes` | write | VERIFIED IN BLENDER |
| `blender_list_geometry_nodes` | read | UNTESTED |
| `blender_add_geometry_node` | write | UNTESTED |
| `blender_link_geometry_nodes` | write | VERIFIED IN BLENDER |
| `blender_set_geometry_input` | write | VERIFIED IN BLENDER |
| `blender_remove_geometry_node` | destructive | VERIFIED IN BLENDER |
| `blender_create_compositor` | write | VERIFIED IN BLENDER |
| `blender_list_compositor_nodes` | read | UNTESTED |
| `blender_add_compositor_node` | write | UNTESTED |
| `blender_link_compositor_nodes` | write | VERIFIED IN BLENDER |
| `blender_set_compositor_input` | write | VERIFIED IN BLENDER |
| `blender_remove_compositor_node` | destructive | VERIFIED IN BLENDER |

## physics (9)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_add_rigidbody` | write | VERIFIED IN BLENDER |
| `blender_remove_rigidbody` | destructive | VERIFIED IN BLENDER |
| `blender_set_rigidbody` | write | UNTESTED |
| `blender_add_collision` | write | VERIFIED IN BLENDER |
| `blender_add_cloth` | write | VERIFIED IN BLENDER |
| `blender_add_fluid` | write | VERIFIED IN BLENDER |
| `blender_add_soft_body` | write | VERIFIED IN BLENDER |
| `blender_set_gravity` | write | UNTESTED |
| `blender_set_rigidbody_world` | write | UNTESTED |

## render (12)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_set_render_engine` | write | VERIFIED IN BLENDER |
| `blender_set_render_resolution` | write | VERIFIED IN BLENDER |
| `blender_set_render_samples` | write | VERIFIED IN BLENDER |
| `blender_set_render_format` | write | UNTESTED |
| `blender_set_render_output` | filesystem | UNTESTED |
| `blender_render_still` | filesystem | VERIFIED IN BLENDER |
| `blender_render_animation` | filesystem | UNTESTED |
| `blender_set_transparent_film` | write | VERIFIED IN BLENDER |
| `blender_set_camera_clip` | write | UNTESTED |
| `blender_set_cycles_device` | write | VERIFIED IN BLENDER |
| `blender_set_render_border` | write | VERIFIED IN BLENDER |
| `blender_render_preview` | filesystem | UNTESTED |

## scene (36)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_new_scene` | write | VERIFIED IN BLENDER |
| `blender_set_scene` | write | VERIFIED IN BLENDER |
| `blender_rename_scene` | write | VERIFIED IN BLENDER |
| `blender_delete_scene` | destructive | VERIFIED IN BLENDER |
| `blender_set_frame` | write | VERIFIED IN BLENDER |
| `blender_set_frame_range` | write | VERIFIED IN BLENDER |
| `blender_set_units` | write | UNTESTED |
| `blender_set_world_color` | write | UNTESTED |
| `blender_new_collection` | write | VERIFIED IN BLENDER |
| `blender_delete_collection` | destructive | VERIFIED IN BLENDER |
| `blender_rename_collection` | write | VERIFIED IN BLENDER |
| `blender_move_to_collection` | write | VERIFIED IN BLENDER |
| `blender_hide_collection` | write | UNTESTED |
| `blender_select_object` | write | VERIFIED IN BLENDER |
| `blender_select_all` | write | VERIFIED IN BLENDER |
| `blender_deselect_all` | write | VERIFIED IN BLENDER |
| `blender_select_by_type` | write | VERIFIED IN BLENDER |
| `blender_set_active_object` | write | VERIFIED IN BLENDER |
| `blender_rename_object` | write | VERIFIED IN BLENDER |
| `blender_delete_object` | destructive | VERIFIED IN BLENDER |
| `blender_delete_selected` | destructive | VERIFIED IN BLENDER |
| `blender_duplicate_object` | write | UNTESTED |
| `blender_set_transform` | write | VERIFIED IN BLENDER |
| `blender_move_object` | write | VERIFIED IN BLENDER |
| `blender_rotate_object` | write | UNTESTED |
| `blender_scale_object` | write | VERIFIED IN BLENDER |
| `blender_set_visibility` | write | UNTESTED |
| `blender_set_parent` | write | VERIFIED IN BLENDER |
| `blender_clear_parent` | write | VERIFIED IN BLENDER |
| `blender_set_custom_property` | write | VERIFIED IN BLENDER |
| `blender_remove_custom_property` | write | VERIFIED IN BLENDER |
| `blender_join_objects` | destructive | VERIFIED IN BLENDER |
| `blender_apply_transform` | write | UNTESTED |
| `blender_set_origin` | write | UNTESTED |
| `blender_smooth_shading` | write | VERIFIED IN BLENDER |
| `blender_add_empty` | write | UNTESTED |

## studio (17)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_add_camera` | write | UNTESTED |
| `blender_set_active_camera` | write | VERIFIED IN BLENDER |
| `blender_set_camera_lens` | write | VERIFIED IN BLENDER |
| `blender_set_camera_dof` | write | UNTESTED |
| `blender_aim_at` | write | UNTESTED |
| `blender_add_light` | write | UNTESTED |
| `blender_set_light` | write | UNTESTED |
| `blender_add_text` | write | UNTESTED |
| `blender_edit_text` | write | VERIFIED IN BLENDER |
| `blender_add_bezier_curve` | write | UNTESTED |
| `blender_set_curve_bevel` | write | UNTESTED |
| `blender_add_armature` | write | UNTESTED |
| `blender_add_bone` | write | VERIFIED IN BLENDER |
| `blender_parent_to_armature` | write | VERIFIED IN BLENDER |
| `blender_add_vertex_group` | write | VERIFIED IN BLENDER |
| `blender_assign_vertices_group` | write | UNTESTED |
| `blender_list_bones` | read | UNTESTED |

## system (19)

| Name | Risk | Acceptance coverage |
|---|---|---|
| `blender_health` | read | UNTESTED |
| `blender_version` | read | UNTESTED |
| `blender_capabilities` | read | UNTESTED |
| `blender_scene_summary` | read | VERIFIED IN BLENDER |
| `blender_list_scenes` | read | UNTESTED |
| `blender_list_objects` | read | UNTESTED |
| `blender_list_materials` | read | UNTESTED |
| `blender_list_images` | read | UNTESTED |
| `blender_list_actions` | read | UNTESTED |
| `blender_list_collections` | read | UNTESTED |
| `blender_get_object` | read | UNTESTED |
| `blender_get_material` | read | UNTESTED |
| `blender_get_scene` | read | UNTESTED |
| `blender_get_selection` | read | UNTESTED |
| `blender_get_dependencies` | read | UNTESTED |
| `blender_get_mesh_stats` | read | UNTESTED |
| `blender_get_render_status` | read | UNTESTED |
| `blender_get_job_hint` | read | UNTESTED |
| `blender_batch` | write | UNTESTED |
