"""Fixed Blender operations run as: blender --background --factory-startup
--disable-autoexec --python blender_ops.py -- <request.json> <result.json>.

Only these templates execute inside Blender; the planner supplies validated JSON
arguments, never code. "create" starts from an empty factory scene and writes a
new .blend (and optional export); "inspect" opens a file with auto-run scripts
disabled and reports objects, types and mesh sizes for independent readback.
"""
import json
import sys

import bpy

PRIMITIVES = {
    'cube': lambda: bpy.ops.mesh.primitive_cube_add(),
    'sphere': lambda: bpy.ops.mesh.primitive_uv_sphere_add(),
    'cylinder': lambda: bpy.ops.mesh.primitive_cylinder_add(),
    'cone': lambda: bpy.ops.mesh.primitive_cone_add(),
    'plane': lambda: bpy.ops.mesh.primitive_plane_add(),
    'torus': lambda: bpy.ops.mesh.primitive_torus_add(),
}


def describe():
    rows = []
    for item in sorted(bpy.data.objects, key=lambda o: o.name):
        row = {'name': item.name, 'type': item.type, 'location': [round(v, 4) for v in item.location],
               'scale': [round(v, 4) for v in item.scale]}
        if item.type == 'MESH':
            row['vertices'] = len(item.data.vertices)
            row['polygons'] = len(item.data.polygons)
        rows.append(row)
    return {'objects': rows, 'blender_version': bpy.app.version_string}


def create(request):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for spec in request['objects']:
        PRIMITIVES[spec['type']]()
        item = bpy.context.active_object
        item.name = spec['name']
        item.location = spec.get('location', [0, 0, 0])
        item.scale = spec.get('scale', [1, 1, 1])
    bpy.ops.wm.save_as_mainfile(filepath=request['output'], check_existing=False)
    export = request.get('export')
    if export:
        bpy.ops.object.select_all(action='SELECT')
        if export['format'] == 'gltf':
            bpy.ops.export_scene.gltf(filepath=export['path'], export_format='GLB', use_selection=True)
        elif export['format'] == 'obj':
            bpy.ops.wm.obj_export(filepath=export['path'], export_selected_objects=True)
        elif export['format'] == 'stl':
            bpy.ops.wm.stl_export(filepath=export['path'], export_selected_objects=True)
        else:
            raise ValueError('Unsupported export format.')
    return describe()


def inspect(request):
    bpy.ops.wm.open_mainfile(filepath=request['path'], load_ui=False, use_scripts=False)
    return describe()


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:]
    request_path, result_path = arguments[0], arguments[1]
    try:
        with open(request_path, encoding='utf-8') as handle:
            request = json.load(handle)
        value = {'create': create, 'inspect': inspect}[request['operation']](request)
        result = {'ok': True, 'value': value}
    except Exception as error:  # Reported as a typed failure to the host.
        result = {'ok': False, 'error_type': type(error).__name__, 'error': str(error)[:500]}
    with open(result_path, 'w', encoding='utf-8') as handle:
        json.dump(result, handle)


main()
