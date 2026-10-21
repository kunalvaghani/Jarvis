"""Generated typed tools; regenerate with generate_adapter.py, never model-generated code."""
from adapter import BlenderAdapter, tool
class BlenderConnector(BlenderAdapter):
    @tool(access='read', destructive=False)
    def blender_health(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Check live Blender connection, version and current file. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('health', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_version(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Get installed Blender version and build info. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('version', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_capabilities(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List supported commands and approval classes. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('capabilities', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_scene_summary(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Summarize objects, materials, collections, frame and render settings. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('scene_summary', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_scenes(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List scenes. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('list_scenes', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_objects(self, *, type: str = '', limit: int = 250, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List named objects with optional type filter. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('list_objects', {'type': type, 'limit': limit}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_materials(self, *, limit: int = 250, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List materials. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('list_materials', {'limit': limit}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_images(self, *, limit: int = 250, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List loaded images. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('list_images', {'limit': limit}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_actions(self, *, limit: int = 250, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List animation actions. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('list_actions', {'limit': limit}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_collections(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List collections. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('list_collections', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_get_object(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Inspect object, transforms and optional mesh statistics. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('get_object', {'name': name}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_get_material(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Inspect a material and its nodes. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('get_material', {'name': name}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_get_scene(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Inspect scene configuration. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('get_scene', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_get_selection(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Read selected and active objects. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('get_selection', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_get_dependencies(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Get object linked dependencies. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('get_dependencies', {'name': name}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_get_mesh_stats(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Get polygon/edge/vertex statistics. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('get_mesh_stats', {'name': name}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_get_render_status(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Inspect render output/settings. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('get_render_status', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_get_job_hint(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Explain asynchronous long-running operation behavior. Category system; risk read. Empty optional arrays omit changes."""
        return self._run('get_job_hint', {}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_new_scene(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create a new scene. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('new_scene', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_scene(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Switch active scene. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_scene', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_rename_scene(self, *, old_name: str, new_name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Rename scene. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('rename_scene', {'old_name': old_name, 'new_name': new_name}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_delete_scene(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Delete named scene. Category scene; risk destructive. Empty optional arrays omit changes."""
        return self._run('delete_scene', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_frame(self, *, frame: int, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set current frame. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_frame', {'frame': frame}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_frame_range(self, *, start: int, end: int, fps: int = 24, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set frame start/end and optional FPS. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_frame_range', {'start': start, 'end': end, 'fps': fps}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_units(self, *, system: str = 'METRIC', scale: float = 1.0, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set units system and length scale. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_units', {'system': system, 'scale': scale}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_world_color(self, *, color: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set world background color. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_world_color', {'color': color}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_new_collection(self, *, name: str, parent: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create collection. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('new_collection', {'name': name, 'parent': parent}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_delete_collection(self, *, name: str, delete_objects: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Delete collection; objects remain if linked elsewhere. Category scene; risk destructive. Empty optional arrays omit changes."""
        return self._run('delete_collection', {'name': name, 'delete_objects': delete_objects}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_rename_collection(self, *, old_name: str, new_name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Rename a collection. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('rename_collection', {'old_name': old_name, 'new_name': new_name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_move_to_collection(self, *, name: str, collection: str, exclusive: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Link object to collection, optionally unlink others. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('move_to_collection', {'name': name, 'collection': collection, 'exclusive': exclusive}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_hide_collection(self, *, name: str, hidden: bool = True, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Hide collection in renders and viewports. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('hide_collection', {'name': name, 'hidden': hidden}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_select_object(self, *, name: str, add: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Select object and make it active. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('select_object', {'name': name, 'add': add}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_select_all(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Select all objects. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('select_all', {}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_deselect_all(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Deselect every object. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('deselect_all', {}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_select_by_type(self, *, type: str, add: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Select objects of type. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('select_by_type', {'type': type, 'add': add}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_active_object(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Make object active. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_active_object', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_rename_object(self, *, old_name: str, new_name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Rename object. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('rename_object', {'old_name': old_name, 'new_name': new_name}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_delete_object(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Delete object. Category scene; risk destructive. Empty optional arrays omit changes."""
        return self._run('delete_object', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_delete_selected(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Delete selected objects. Category scene; risk destructive. Empty optional arrays omit changes."""
        return self._run('delete_selected', {}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_duplicate_object(self, *, name: str, new_name: str = '', linked: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Duplicate object, linked data optional. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('duplicate_object', {'name': name, 'new_name': new_name, 'linked': linked}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_transform(self, *, name: str, location: list[float] = [], rotation: list[float] = [], scale: list[float] = [], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set absolute location/rotation/scale. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_transform', {'name': name, 'location': (location or None), 'rotation': (rotation or None), 'scale': (scale or None)}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_move_object(self, *, name: str, offset: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Move object relative to current location. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('move_object', {'name': name, 'offset': offset}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_rotate_object(self, *, name: str, degrees_xyz: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Rotate object relative to Euler rotation. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('rotate_object', {'name': name, 'degrees_xyz': degrees_xyz}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_scale_object(self, *, name: str, factor: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Multiply object scale. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('scale_object', {'name': name, 'factor': factor}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_visibility(self, *, name: str, viewport: str = 'unchanged', render: str = 'unchanged', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set hide viewport/render on object. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_visibility', {'name': name, 'viewport': (None if viewport == 'unchanged' else {'true':True,'false':False}[viewport]), 'render': (None if render == 'unchanged' else {'true':True,'false':False}[render])}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_parent(self, *, child: str, parent: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Parent to object, preserving world matrix. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_parent', {'child': child, 'parent': parent}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_clear_parent(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove object parenting, preserving world transform. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('clear_parent', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_custom_property(self, *, name: str, key: str, value: dict, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set a JSON-compatible custom property value. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_custom_property', {'name': name, 'key': key, 'value': value.get('value')}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_remove_custom_property(self, *, name: str, key: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove custom property. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('remove_custom_property', {'name': name, 'key': key}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_join_objects(self, *, names: list[str], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Join mesh objects into active mesh. Category scene; risk destructive. Empty optional arrays omit changes."""
        return self._run('join_objects', {'names': names}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_apply_transform(self, *, name: str, location: bool = False, rotation: bool = True, scale: bool = True, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Apply location, rotation, or scale to object data. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('apply_transform', {'name': name, 'location': location, 'rotation': rotation, 'scale': scale}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_origin(self, *, name: str, mode: str = 'ORIGIN_GEOMETRY', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set object origin to geometry or cursor. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('set_origin', {'name': name, 'mode': mode}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_smooth_shading(self, *, name: str, smooth: bool = True, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Smooth or flat shade mesh faces. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('smooth_shading', {'name': name, 'smooth': smooth}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_empty(self, *, name: str = 'Empty', location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create an Empty object. Category scene; risk write. Empty optional arrays omit changes."""
        return self._run('add_empty', {'name': name, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_cube(self, *, name: str = 'Cube', size: float = 2.0, location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create cube. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_cube', {'name': name, 'size': size, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_uv_sphere(self, *, name: str = 'UVSphere', segments: int = 32, rings: int = 16, radius: float = 1.0, location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create UV sphere. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_uv_sphere', {'name': name, 'segments': segments, 'rings': rings, 'radius': radius, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_ico_sphere(self, *, name: str = 'Icosphere', subdivisions: int = 2, radius: float = 1.0, location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create Icosphere. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_ico_sphere', {'name': name, 'subdivisions': subdivisions, 'radius': radius, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_cylinder(self, *, name: str = 'Cylinder', vertices: int = 32, radius: float = 1.0, depth: float = 2.0, location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create cylinder. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_cylinder', {'name': name, 'vertices': vertices, 'radius': radius, 'depth': depth, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_cone(self, *, name: str = 'Cone', vertices: int = 32, radius1: float = 1.0, radius2: float = 0.0, depth: float = 2.0, location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create cone. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_cone', {'name': name, 'vertices': vertices, 'radius1': radius1, 'radius2': radius2, 'depth': depth, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_torus(self, *, name: str = 'Torus', major_radius: float = 1.0, minor_radius: float = 0.25, location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create torus. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_torus', {'name': name, 'major_radius': major_radius, 'minor_radius': minor_radius, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_plane(self, *, name: str = 'Plane', size: float = 2.0, location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create plane. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_plane', {'name': name, 'size': size, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_grid(self, *, name: str = 'Grid', x_subdivisions: int = 10, y_subdivisions: int = 10, size: float = 2.0, location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create subdivided grid. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_grid', {'name': name, 'x_subdivisions': x_subdivisions, 'y_subdivisions': y_subdivisions, 'size': size, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_circle(self, *, name: str = 'Circle', vertices: int = 32, radius: float = 1.0, location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create mesh circle. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_circle', {'name': name, 'vertices': vertices, 'radius': radius, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_monkey(self, *, name: str = 'Suzanne', location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create Suzanne mesh. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_monkey', {'name': name, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_mesh(self, *, name: str, vertices: list[list[float]], faces: list[list[int]], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create custom mesh from vertices and face lists. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('add_mesh', {'name': name, 'vertices': vertices, 'faces': faces}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_mesh_vertices(self, *, name: str, limit: int = 200, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Get mesh vertex coordinates (limited). Category mesh; risk read. Empty optional arrays omit changes."""
        return self._run('mesh_vertices', {'name': name, 'limit': limit}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_vertex(self, *, name: str, index: int, coordinate: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Update mesh vertex coordinate. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('set_vertex', {'name': name, 'index': index, 'coordinate': coordinate}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_transform_vertices(self, *, name: str, indices: list[int], offset: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Offset vertices of mesh. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('transform_vertices', {'name': name, 'indices': indices, 'offset': offset}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_flip_normals(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Reverse mesh polygon winding. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('flip_normals', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_recalculate_normals(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Recalculate normals. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('recalculate_normals', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_subdivide_mesh(self, *, name: str, cuts: int = 1, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Subdivide selected mesh. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('subdivide_mesh', {'name': name, 'cuts': cuts}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_merge_by_distance(self, *, name: str, threshold: float = 0.0001, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove coincident vertices. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('merge_by_distance', {'name': name, 'threshold': threshold}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_triangulate_mesh(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Triangulate mesh faces. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('triangulate_mesh', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_quadrangulate_mesh(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Convert eligible triangles to quads. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('quadrangulate_mesh', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_extrude_region(self, *, name: str, offset: list[float] = [0, 0, 1], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Extrude all mesh regions. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('extrude_region', {'name': name, 'offset': offset}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_inset_faces(self, *, name: str, thickness: float = 0.05, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Inset all mesh faces. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('inset_faces', {'name': name, 'thickness': thickness}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_bevel_edges(self, *, name: str, offset: float = 0.05, segments: int = 2, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Bevel mesh edges. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('bevel_edges', {'name': name, 'offset': offset, 'segments': segments}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_unwrap_uv(self, *, name: str, method: str = 'ANGLE_BASED', expected_scope: str = '', host_authorization: str = '') -> dict:
        """UV unwrap mesh faces. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('unwrap_uv', {'name': name, 'method': method}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_smart_uv_project(self, *, name: str, island_margin: float = 0.02, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Smart UV project mesh. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('smart_uv_project', {'name': name, 'island_margin': island_margin}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_voxel_remesh(self, *, name: str, voxel_size: float = 0.1, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Voxel remesh mesh. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('voxel_remesh', {'name': name, 'voxel_size': voxel_size}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_decimate_mesh(self, *, name: str, ratio: float = 0.5, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create decimate modifier. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('decimate_mesh', {'name': name, 'ratio': ratio}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_make_single_user(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Make selected object mesh data unique. Category mesh; risk write. Empty optional arrays omit changes."""
        return self._run('make_single_user', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_modifier(self, *, name: str, type: str, modifier_name: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add allowlisted modifier by enum name. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_modifier', {'name': name, 'type': type, 'modifier_name': modifier_name}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_remove_modifier(self, *, name: str, modifier_name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove named modifier. Category modifier; risk destructive. Empty optional arrays omit changes."""
        return self._run('remove_modifier', {'name': name, 'modifier_name': modifier_name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_modifier(self, *, name: str, modifier_name: str, properties: dict, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set whitelisted modifier properties. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('set_modifier', {'name': name, 'modifier_name': modifier_name, 'properties': properties}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_apply_modifier(self, *, name: str, modifier_name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Apply named modifier destructively. Category modifier; risk destructive. Empty optional arrays omit changes."""
        return self._run('apply_modifier', {'name': name, 'modifier_name': modifier_name}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_modifiers(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Read mesh modifiers. Category modifier; risk read. Empty optional arrays omit changes."""
        return self._run('list_modifiers', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_subdivision(self, *, name: str, levels: int = 2, render_levels: int = 2, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add subdivision modifier. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_subdivision', {'name': name, 'levels': levels, 'render_levels': render_levels}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_bevel(self, *, name: str, width: float = 0.05, segments: int = 3, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add bevel modifier. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_bevel', {'name': name, 'width': width, 'segments': segments}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_solidify(self, *, name: str, thickness: float = 0.05, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add solidify modifier. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_solidify', {'name': name, 'thickness': thickness}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_mirror(self, *, name: str, axis: str = 'X', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add mirror modifier. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_mirror', {'name': name, 'axis': axis}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_array(self, *, name: str, count: int = 3, offset: list[float] = [1, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add array modifier. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_array', {'name': name, 'count': count, 'offset': offset}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_boolean(self, *, name: str, target: str, operation: str = 'DIFFERENCE', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add Boolean modifier between mesh objects. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_boolean', {'name': name, 'target': target, 'operation': operation}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_remesh(self, *, name: str, octree_depth: int = 4, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add remesh modifier. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_remesh', {'name': name, 'octree_depth': octree_depth}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_wireframe(self, *, name: str, thickness: float = 0.02, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add wireframe modifier. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_wireframe', {'name': name, 'thickness': thickness}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_constraint(self, *, name: str, type: str, target: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add allowlisted constraint type. Category modifier; risk write. Empty optional arrays omit changes."""
        return self._run('add_constraint', {'name': name, 'type': type, 'target': target}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_remove_constraint(self, *, name: str, constraint: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove named constraint. Category modifier; risk destructive. Empty optional arrays omit changes."""
        return self._run('remove_constraint', {'name': name, 'constraint': constraint}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_constraints(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List constraints. Category modifier; risk read. Empty optional arrays omit changes."""
        return self._run('list_constraints', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_create_material(self, *, name: str, color: list[float] = [0.8, 0.8, 0.8, 1.0], metallic: float = 0.0, roughness: float = 0.5, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create principled material. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('create_material', {'name': name, 'color': color, 'metallic': metallic, 'roughness': roughness}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_assign_material(self, *, name: str, material: str, slot: int = 0, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Assign material to object. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('assign_material', {'name': name, 'material': material, 'slot': slot}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_material(self, *, name: str, color: list[float] = [], metallic: str = '', roughness: str = '', alpha: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Update principled PBR values. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('set_material', {'name': name, 'color': (color or None), 'metallic': (float(metallic) if metallic else None), 'roughness': (float(roughness) if roughness else None), 'alpha': (float(alpha) if alpha else None)}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_remove_material(self, *, name: str, force: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Delete material datablock if unused or forced. Category material; risk destructive. Empty optional arrays omit changes."""
        return self._run('remove_material', {'name': name, 'force': force}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_duplicate_material(self, *, name: str, new_name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Duplicate existing material. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('duplicate_material', {'name': name, 'new_name': new_name}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_clear_material_slots(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Clear all material slots of object. Category material; risk destructive. Empty optional arrays omit changes."""
        return self._run('clear_material_slots', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_new_shader_node(self, *, material: str, node_type: str, label: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add shader node from allowlist. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('new_shader_node', {'material': material, 'node_type': node_type, 'label': label}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_shader_nodes(self, *, material: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List nodes and sockets in shader material. Category material; risk read. Empty optional arrays omit changes."""
        return self._run('list_shader_nodes', {'material': material}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_link_shader_nodes(self, *, material: str, from_node: str, from_socket: str, to_node: str, to_socket: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Link shader nodes by node and socket names. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('link_shader_nodes', {'material': material, 'from_node': from_node, 'from_socket': from_socket, 'to_node': to_node, 'to_socket': to_socket}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_unlink_shader_nodes(self, *, material: str, to_node: str, to_socket: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove shader link by target node socket. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('unlink_shader_nodes', {'material': material, 'to_node': to_node, 'to_socket': to_socket}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_shader_input(self, *, material: str, node: str, socket: str, value: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set a shader node socket default value. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('set_shader_input', {'material': material, 'node': node, 'socket': socket, 'value': value}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_shader_attribute(self, *, material: str, node: str, attribute: str, value: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set safe scalar/enum attribute on shader node. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('set_shader_attribute', {'material': material, 'node': node, 'attribute': attribute, 'value': value}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_load_image(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Load image into Blender. Category material; risk filesystem. Empty optional arrays omit changes."""
        return self._run('load_image', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_assign_image_texture(self, *, material: str, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create image texture node for material. Category material; risk filesystem. Empty optional arrays omit changes."""
        return self._run('assign_image_texture', {'material': material, 'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_object_color(self, *, name: str, color: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set viewport RGBA object color. Category material; risk write. Empty optional arrays omit changes."""
        return self._run('set_object_color', {'name': name, 'color': color}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_create_geometry_nodes(self, *, name: str, group_name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create geometry node group and modifier. Category nodes; risk write. Empty optional arrays omit changes."""
        return self._run('create_geometry_nodes', {'name': name, 'group_name': group_name}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_geometry_nodes(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Inspect geometry node tree on object. Category nodes; risk read. Empty optional arrays omit changes."""
        return self._run('list_geometry_nodes', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_geometry_node(self, *, name: str, node_type: str, label: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add allowlisted node to geometry tree. Category nodes; risk write. Empty optional arrays omit changes."""
        return self._run('add_geometry_node', {'name': name, 'node_type': node_type, 'label': label}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_link_geometry_nodes(self, *, name: str, from_node: str, from_socket: str, to_node: str, to_socket: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Connect sockets in object geometry node group. Category nodes; risk write. Empty optional arrays omit changes."""
        return self._run('link_geometry_nodes', {'name': name, 'from_node': from_node, 'from_socket': from_socket, 'to_node': to_node, 'to_socket': to_socket}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_geometry_input(self, *, name: str, node: str, socket: str, value: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set geometry node socket value. Category nodes; risk write. Empty optional arrays omit changes."""
        return self._run('set_geometry_input', {'name': name, 'node': node, 'socket': socket, 'value': value}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_remove_geometry_node(self, *, name: str, node: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove node from geometry node tree. Category nodes; risk destructive. Empty optional arrays omit changes."""
        return self._run('remove_geometry_node', {'name': name, 'node': node}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_create_compositor(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Enable compositor scene nodes. Category nodes; risk write. Empty optional arrays omit changes."""
        return self._run('create_compositor', {}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_compositor_nodes(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List compositor nodes. Category nodes; risk read. Empty optional arrays omit changes."""
        return self._run('list_compositor_nodes', {}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_compositor_node(self, *, node_type: str, label: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add allowlisted compositor node. Category nodes; risk write. Empty optional arrays omit changes."""
        return self._run('add_compositor_node', {'node_type': node_type, 'label': label}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_link_compositor_nodes(self, *, from_node: str, from_socket: str, to_node: str, to_socket: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Link compositor nodes. Category nodes; risk write. Empty optional arrays omit changes."""
        return self._run('link_compositor_nodes', {'from_node': from_node, 'from_socket': from_socket, 'to_node': to_node, 'to_socket': to_socket}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_compositor_input(self, *, node: str, socket: str, value: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set compositor node input. Category nodes; risk write. Empty optional arrays omit changes."""
        return self._run('set_compositor_input', {'node': node, 'socket': socket, 'value': value}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_remove_compositor_node(self, *, node: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove compositor node. Category nodes; risk destructive. Empty optional arrays omit changes."""
        return self._run('remove_compositor_node', {'node': node}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_camera(self, *, name: str = 'Camera', location: list[float] = [0, -6, 3], rotation: list[float] = [1.25, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create camera. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('add_camera', {'name': name, 'location': location, 'rotation': rotation}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_active_camera(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set camera used for scene rendering. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('set_active_camera', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_camera_lens(self, *, name: str, lens: float, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set lens in millimeters. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('set_camera_lens', {'name': name, 'lens': lens}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_camera_dof(self, *, name: str, focus_distance: float, fstop: float = 2.8, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set depth of field focus/aperture. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('set_camera_dof', {'name': name, 'focus_distance': focus_distance, 'fstop': fstop}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_aim_at(self, *, name: str, target: list[float], track_axis: str = '-Z', up_axis: str = 'Y', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Rotate object toward target point. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('aim_at', {'name': name, 'target': target, 'track_axis': track_axis, 'up_axis': up_axis}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_light(self, *, name: str = 'Light', type: str = 'AREA', energy: float = 1000.0, location: list[float] = [0, 0, 4], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add POINT/SUN/SPOT/AREA light. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('add_light', {'name': name, 'type': type, 'energy': energy, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_light(self, *, name: str, energy: str = '', color: list[float] = [], size: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Modify light energy and color. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('set_light', {'name': name, 'energy': (float(energy) if energy else None), 'color': (color or None), 'size': (float(size) if size else None)}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_text(self, *, name: str = 'Text', body: str = 'Jarvis', size: float = 1.0, extrude: float = 0.0, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add text object. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('add_text', {'name': name, 'body': body, 'size': size, 'extrude': extrude}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_edit_text(self, *, name: str, body: str, size: str = '', extrude: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Change font object text. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('edit_text', {'name': name, 'body': body, 'size': (float(size) if size else None), 'extrude': (float(extrude) if extrude else None)}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_bezier_curve(self, *, name: str = 'Curve', points: list[list[float]], bevel_depth: float = 0.02, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create 3D Bezier curve. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('add_bezier_curve', {'name': name, 'points': points, 'bevel_depth': bevel_depth}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_curve_bevel(self, *, name: str, depth: float, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Adjust curve bevel. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('set_curve_bevel', {'name': name, 'depth': depth}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_armature(self, *, name: str = 'Armature', location: list[float] = [0, 0, 0], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create single-bone armature. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('add_armature', {'name': name, 'location': location}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_bone(self, *, armature: str, name: str, head: list[float], tail: list[float], parent: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add armature edit bone. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('add_bone', {'armature': armature, 'name': name, 'head': head, 'tail': tail, 'parent': parent}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_parent_to_armature(self, *, name: str, armature: str, add_modifier: bool = True, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Parent mesh to armature, creating modifier optionally. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('parent_to_armature', {'name': name, 'armature': armature, 'add_modifier': add_modifier}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_vertex_group(self, *, name: str, group: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add vertex group. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('add_vertex_group', {'name': name, 'group': group}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_assign_vertices_group(self, *, name: str, group: str, indices: list[int], weight: float = 1.0, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Assign vertices with weight. Category studio; risk write. Empty optional arrays omit changes."""
        return self._run('assign_vertices_group', {'name': name, 'group': group, 'indices': indices, 'weight': weight}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_bones(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List bones in armature. Category studio; risk read. Empty optional arrays omit changes."""
        return self._run('list_bones', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_insert_keyframe(self, *, name: str, property: str = 'location', frame: int, index: int = -1, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Insert keyframe for object property. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('insert_keyframe', {'name': name, 'property': property, 'frame': frame, 'index': index}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_delete_keyframe(self, *, name: str, property: str, frame: int, index: int = -1, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Delete keyframe. Category animation; risk destructive. Empty optional arrays omit changes."""
        return self._run('delete_keyframe', {'name': name, 'property': property, 'frame': frame, 'index': index}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_animate_transform(self, *, name: str, frame: int, location: list[float] = [], rotation: list[float] = [], scale: list[float] = [], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Keyframe location/rotation/scale at frame. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('animate_transform', {'name': name, 'frame': frame, 'location': (location or None), 'rotation': (rotation or None), 'scale': (scale or None)}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_interpolation(self, *, name: str, mode: str = 'BEZIER', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set keyframe interpolation in action. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('set_interpolation', {'name': name, 'mode': mode}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_rename_action(self, *, old_name: str, new_name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Rename animation action. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('rename_action', {'old_name': old_name, 'new_name': new_name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_assign_action(self, *, name: str, action: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Assign named action to object. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('assign_action', {'name': name, 'action': action}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_clear_animation(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Clear object animation. Category animation; risk destructive. Empty optional arrays omit changes."""
        return self._run('clear_animation', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_create_shape_key(self, *, name: str, key: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create shape key on mesh. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('create_shape_key', {'name': name, 'key': key}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_shape_key(self, *, name: str, key: str, value: float, frame: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set shape key value and optional keyframe. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('set_shape_key', {'name': name, 'key': key, 'value': value, 'frame': (int(frame) if frame else None)}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_shape_keys(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Inspect mesh shape keys. Category animation; risk read. Empty optional arrays omit changes."""
        return self._run('list_shape_keys', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_nla_strip(self, *, name: str, action: str, frame: int, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create NLA strip from action. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('set_nla_strip', {'name': name, 'action': action, 'frame': frame}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_marker(self, *, name: str, frame: int, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Create timeline marker. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('add_marker', {'name': name, 'frame': frame}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_delete_marker(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Delete timeline marker. Category animation; risk destructive. Empty optional arrays omit changes."""
        return self._run('delete_marker', {'name': name}, expected_scope, host_authorization)
    @tool(access='read', destructive=False)
    def blender_list_markers(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """List timeline markers. Category animation; risk read. Empty optional arrays omit changes."""
        return self._run('list_markers', {}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_fps(self, *, fps: int, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set scene FPS. Category animation; risk write. Empty optional arrays omit changes."""
        return self._run('set_fps', {'fps': fps}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_render_engine(self, *, engine: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Select BLENDER_EEVEE_NEXT / CYCLES / BLENDER_WORKBENCH. Category render; risk write. Empty optional arrays omit changes."""
        return self._run('set_render_engine', {'engine': engine}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_render_resolution(self, *, width: int, height: int, percentage: int = 100, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set resolution pixels and percentage. Category render; risk write. Empty optional arrays omit changes."""
        return self._run('set_render_resolution', {'width': width, 'height': height, 'percentage': percentage}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_render_samples(self, *, samples: int, preview: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set render samples. Category render; risk write. Empty optional arrays omit changes."""
        return self._run('set_render_samples', {'samples': samples, 'preview': preview}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_render_format(self, *, format: str = 'PNG', color_mode: str = 'RGBA', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set PNG/JPEG/OPEN_EXR/etc output format. Category render; risk write. Empty optional arrays omit changes."""
        return self._run('set_render_format', {'format': format, 'color_mode': color_mode}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_set_render_output(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set render output path. Category render; risk filesystem. Empty optional arrays omit changes."""
        return self._run('set_render_output', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_render_still(self, *, filepath: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Render current frame and optionally save image. Category render; risk filesystem. Empty optional arrays omit changes."""
        return self._run('render_still', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_render_animation(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Render animation to configured output. Category render; risk filesystem. Empty optional arrays omit changes."""
        return self._run('render_animation', {}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_transparent_film(self, *, enabled: bool = True, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Enable transparent-film rendering. Category render; risk write. Empty optional arrays omit changes."""
        return self._run('set_transparent_film', {'enabled': enabled}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_camera_clip(self, *, name: str, start: float, end: float, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set camera near/far clipping planes. Category render; risk write. Empty optional arrays omit changes."""
        return self._run('set_camera_clip', {'name': name, 'start': start, 'end': end}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_cycles_device(self, *, device: str = 'CPU', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set cycles scene device CPU or GPU. Category render; risk write. Empty optional arrays omit changes."""
        return self._run('set_cycles_device', {'device': device}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_render_border(self, *, min_x: float, min_y: float, max_x: float, max_y: float, enabled: bool = True, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set normalized crop border for scene. Category render; risk write. Empty optional arrays omit changes."""
        return self._run('set_render_border', {'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y, 'enabled': enabled}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_render_preview(self, *, percentage: int = 25, samples: int = 16, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Render still at temporary low resolution. Category render; risk filesystem. Empty optional arrays omit changes."""
        return self._run('render_preview', {'percentage': percentage, 'samples': samples}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_save_project(self, *, filepath: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Save current blend file. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('save_project', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_save_project_copy(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Save a copy preserving current working file. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('save_project_copy', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_import_obj(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Import Wavefront OBJ. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('import_obj', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_import_fbx(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Import FBX. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('import_fbx', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_import_gltf(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Import glTF/GLB. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('import_gltf', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_import_stl(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Import STL. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('import_stl', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_import_usd(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Import USD asset. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('import_usd', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_import_alembic(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Import Alembic asset. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('import_alembic', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_export_obj(self, *, filepath: str, selected_only: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Export Wavefront OBJ. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('export_obj', {'filepath': filepath, 'selected_only': selected_only}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_export_fbx(self, *, filepath: str, selected_only: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Export FBX. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('export_fbx', {'filepath': filepath, 'selected_only': selected_only}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_export_gltf(self, *, filepath: str, selected_only: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Export GLB/glTF. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('export_gltf', {'filepath': filepath, 'selected_only': selected_only}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_export_stl(self, *, filepath: str, selected_only: bool = False, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Export STL. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('export_stl', {'filepath': filepath, 'selected_only': selected_only}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_export_usd(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Export USD scene. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('export_usd', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_export_alembic(self, *, filepath: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Export Alembic scene. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('export_alembic', {'filepath': filepath}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_pack_resources(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Pack external resources in blend file. Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('pack_resources', {}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_unpack_resources(self, *, method: str = 'USE_LOCAL', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Unpack resources (writes filesystem). Category file; risk filesystem. Empty optional arrays omit changes."""
        return self._run('unpack_resources', {'method': method}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_rigidbody(self, *, name: str, type: str = 'ACTIVE', mass: float = 1.0, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Attach active/passive rigid body. Category physics; risk write. Empty optional arrays omit changes."""
        return self._run('add_rigidbody', {'name': name, 'type': type, 'mass': mass}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_remove_rigidbody(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove rigid body. Category physics; risk destructive. Empty optional arrays omit changes."""
        return self._run('remove_rigidbody', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_rigidbody(self, *, name: str, mass: str = '', friction: str = '', restitution: str = '', expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set rigid body physics settings. Category physics; risk write. Empty optional arrays omit changes."""
        return self._run('set_rigidbody', {'name': name, 'mass': (float(mass) if mass else None), 'friction': (float(friction) if friction else None), 'restitution': (float(restitution) if restitution else None)}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_collision(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add collision modifier. Category physics; risk write. Empty optional arrays omit changes."""
        return self._run('add_collision', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_cloth(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add cloth modifier. Category physics; risk write. Empty optional arrays omit changes."""
        return self._run('add_cloth', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_fluid(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add fluid modifier (requires configuration). Category physics; risk write. Empty optional arrays omit changes."""
        return self._run('add_fluid', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_soft_body(self, *, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add soft-body modifier. Category physics; risk write. Empty optional arrays omit changes."""
        return self._run('add_soft_body', {'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_gravity(self, *, gravity: list[float], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set scene gravity vector. Category physics; risk write. Empty optional arrays omit changes."""
        return self._run('set_gravity', {'gravity': gravity}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_rigidbody_world(self, *, substeps: int = 10, iterations: int = 10, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Configure rigid body scene substeps/iterations. Category physics; risk write. Empty optional arrays omit changes."""
        return self._run('set_rigidbody_world', {'substeps': substeps, 'iterations': iterations}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_mark_asset(self, *, type: str, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Mark local datablock as asset. Category assets; risk write. Empty optional arrays omit changes."""
        return self._run('mark_asset', {'type': type, 'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_clear_asset(self, *, type: str, name: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Clear local asset mark. Category assets; risk destructive. Empty optional arrays omit changes."""
        return self._run('clear_asset', {'type': type, 'name': name}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_set_asset_description(self, *, type: str, name: str, description: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Set asset description. Category assets; risk write. Empty optional arrays omit changes."""
        return self._run('set_asset_description', {'type': type, 'name': name, 'description': description}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_add_asset_tag(self, *, type: str, name: str, tag: str, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Add asset catalog tag. Category assets; risk write. Empty optional arrays omit changes."""
        return self._run('add_asset_tag', {'type': type, 'name': name, 'tag': tag}, expected_scope, host_authorization)
    @tool(access='write', destructive=True)
    def blender_purge_orphans(self, *, expected_scope: str = '', host_authorization: str = '') -> dict:
        """Remove unused datablocks. Category assets; risk destructive. Empty optional arrays omit changes."""
        return self._run('purge_orphans', {}, expected_scope, host_authorization)
    @tool(access='write', destructive=False)
    def blender_batch(self, *, steps: list[dict], expected_scope: str = '', host_authorization: str = '') -> dict:
        """Execute safe bounded sequence of other actions. Category system; risk write. Empty optional arrays omit changes."""
        return self._run('batch', {'steps': steps}, expected_scope, host_authorization)
    @tool()
    def blender_bridge_health(self, *, expected_scope: str = '') -> dict:
        """Read scoped Blender bridge_health; never resubmit a job."""
        return self._run('bridge_health', {}, expected_scope)
    @tool()
    def blender_job_status(self, *, job_id: str, expected_scope: str = '') -> dict:
        """Read scoped Blender job_status; never resubmit a job."""
        return self._run('job_status', {'job_id':job_id}, expected_scope)
    @tool()
    def blender_wait_job(self, *, job_id: str, timeout: float = 1.0, poll_seconds: float = 0.15, expected_scope: str = '') -> dict:
        """Read scoped Blender wait_job; never resubmit a job."""
        return self._run('wait_job', {'job_id':job_id, 'timeout':min(timeout, 8.0), 'poll_seconds':poll_seconds}, expected_scope)
if __name__ == '__main__':
    BlenderConnector.main()
