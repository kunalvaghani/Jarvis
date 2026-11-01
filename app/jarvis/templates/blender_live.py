"""Live Blender modelling, run in a VISIBLE Blender as:
blender --factory-startup <start.blend> --python blender_live.py -- <request.json> <result.json>

Fixed template (no model-written code). The user watches the default cube change on screen:
- "morph": the cube is subdivided and every vertex moves smoothly onto the target surface (sphere, cylinder,
  cone or a resized cube), then the object is renamed;
- "head": the cube morphs into an egg-shaped head, then ears, eyes, pupils, a nose and a mouth appear one by
  one with their own colours.
The scene is then saved to the requested path (never over an existing file) and result.json describes it.
"""
import json
import math
import os
import sys

import bmesh
import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:]
REQUEST = json.loads(open(ARGS[0], encoding='utf-8').read())
RESULT = ARGS[1]
FPS = 30.0
COLOURS = {'Skin': (0.86, 0.67, 0.55, 1), 'White': (0.95, 0.95, 0.95, 1), 'Iris': (0.05, 0.05, 0.08, 1),
           'Lips': (0.7, 0.18, 0.2, 1)}


def finish(payload):
    with open(RESULT, 'w', encoding='utf-8') as out:
        json.dump(payload, out)


_REGISTER = bpy.app.timers.register


def _guarded(fn):
    """A failing live step is reported to Jarvis at once (it waited for its time limit before, 2026-11-02)."""
    def run():
        try:
            return fn()
        except Exception as error:  # noqa: BLE001 - reported; the window stays open for the user.
            finish({'ok': False, 'error': f'{type(error).__name__}: {error}'})
            return None
    return run


bpy.app.timers.register = lambda fn, first_interval=0.0, **kw: _REGISTER(_guarded(fn), first_interval=first_interval, **kw)


def material(name):
    found = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    found.diffuse_color = COLOURS[name]
    return found


def show_materials():
    for area in bpy.context.window_manager.windows[0].screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.shading.color_type = 'MATERIAL'


def subdivided_cube():
    cube = bpy.data.objects.get('Cube')
    if cube is None or cube.type != 'MESH':
        raise ValueError('The default cube is missing.')
    mesh = bmesh.new()
    mesh.from_mesh(cube.data)
    bmesh.ops.subdivide_edges(mesh, edges=mesh.edges[:], cuts=11, use_grid_fill=True)  # 12 segments: axis points exist.
    mesh.to_mesh(cube.data)
    mesh.free()
    return cube


def target_of(point, shape):
    x, y, z = point
    if shape['type'] == 'sphere':
        length = math.sqrt(x * x + y * y + z * z) or 1.0
        r = shape['radius']
        return (x / length * r * shape.get('sx', 1), y / length * r * shape.get('sy', 1), z / length * r * shape.get('sz', 1))
    if shape['type'] in ('cylinder', 'cone'):
        edge = max(abs(x), abs(y))
        flat = math.sqrt(x * x + y * y)
        scale = (edge / flat) if flat else 0.0
        radius = shape['radius'] * (1 - (z + 1) / 2 if shape['type'] == 'cone' else 1)
        return (x * scale * radius, y * scale * radius, z * shape['depth'] / 2)
    half = shape['side'] / 2  # cube
    return (x * half, y * half, z * half)


def morph(obj, shape, seconds, then):
    """Animate every vertex from its cube position to the target surface, then call `then`."""
    start = [tuple(v.co) for v in obj.data.vertices]
    goal = [target_of(p, shape) for p in start]
    clock = {'t': 0.0}

    def tick():
        clock['t'] = min(1.0, clock['t'] + 1.0 / (FPS * seconds))
        e = clock['t'] * clock['t'] * (3 - 2 * clock['t'])  # Smooth start and finish.
        for vertex, a, b in zip(obj.data.vertices, start, goal):
            vertex.co = (a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e, a[2] + (b[2] - a[2]) * e)
        obj.data.update()
        if clock['t'] >= 1.0:
            if shape['type'] in ('sphere', 'cylinder', 'cone'):
                for polygon in obj.data.polygons:
                    polygon.use_smooth = True
            bpy.app.timers.register(then, first_interval=0.3)
            return None
        return 1.0 / FPS
    return tick


def part(name, kind, location, size, colour, rotation=(0, 0, 0)):
    mesh = bpy.data.meshes.new(name)
    shape = bmesh.new()
    if kind == 'sphere':
        bmesh.ops.create_uvsphere(shape, u_segments=32, v_segments=16, radius=1.0)
    else:
        bmesh.ops.create_cone(shape, cap_ends=True, segments=24, radius1=1.0, radius2=0.0, depth=2.0)
    shape.to_mesh(mesh)
    shape.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location, obj.scale, obj.rotation_euler = location, size, rotation
    obj.data.materials.append(material(colour))
    return obj


HEAD_PARTS = [
    ('Ear.L', 'sphere', (-1.0, 0.0, 0.05), (0.14, 0.28, 0.4), 'Skin', (0, 0, 0)),
    ('Ear.R', 'sphere', (1.0, 0.0, 0.05), (0.14, 0.28, 0.4), 'Skin', (0, 0, 0)),
    ('Eye.L', 'sphere', (-0.38, -0.92, 0.3), (0.2, 0.2, 0.2), 'White', (0, 0, 0)),
    ('Eye.R', 'sphere', (0.38, -0.92, 0.3), (0.2, 0.2, 0.2), 'White', (0, 0, 0)),
    ('Pupil.L', 'sphere', (-0.38, -1.1, 0.3), (0.09, 0.09, 0.09), 'Iris', (0, 0, 0)),
    ('Pupil.R', 'sphere', (0.38, -1.1, 0.3), (0.09, 0.09, 0.09), 'Iris', (0, 0, 0)),
    ('Nose', 'cone', (0.0, -1.2, -0.05), (0.14, 0.14, 0.18), 'Skin', (math.pi / 2, 0, 0)),
    ('Mouth', 'sphere', (0.0, -0.98, -0.5), (0.32, 0.08, 0.07), 'Lips', (0, 0, 0)),
]


def save_and_report(names):
    output = REQUEST['output']
    if os.path.exists(output):
        finish({'ok': False, 'error': 'The .blend already exists; existing scenes are never overwritten.'})
        return None
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.wm.save_as_mainfile(filepath=output, check_existing=False)
    rows = []
    for name in names:
        obj = bpy.data.objects[name]
        rows.append({'name': obj.name, 'vertices': len(obj.data.vertices),
                     'location': [round(v, 4) for v in obj.location], 'dims': [round(v, 4) for v in obj.dimensions]})
    finish({'ok': True, 'objects': rows, 'blender_version': bpy.app.version_string})
    return None


def run_morph():
    cube = subdivided_cube()
    shape = REQUEST['shape']

    def done():
        cube.name = cube.data.name = REQUEST['name']
        cube.location = REQUEST.get('location', [0, 0, 0])
        return save_and_report([cube.name])
    bpy.app.timers.register(morph(cube, shape, REQUEST.get('seconds', 3.0), done), first_interval=0.5)


def run_head():
    head = subdivided_cube()
    head.data.materials.append(material('Skin'))
    queue = list(HEAD_PARTS)

    def next_part():
        if not queue:
            return save_and_report(['Head'] + [p[0] for p in HEAD_PARTS])
        part(*queue.pop(0))
        return 0.45  # One feature at a time, so the face is seen being built.

    def shaped():
        head.name = head.data.name = 'Head'
        bpy.app.timers.register(next_part, first_interval=0.3)
        return None
    egg = {'type': 'sphere', 'radius': 1.0, 'sx': 1.0, 'sy': 1.1, 'sz': 1.3}
    bpy.app.timers.register(morph(head, egg, REQUEST.get('seconds', 3.0), shaped), first_interval=0.5)


# ---- Original procedural models: a sports car and a house ---------------------------------------------------
PAINTS = [(0.62, 0.04, 0.04, 1), (0.75, 0.76, 0.78, 1), (0.05, 0.18, 0.55, 1), (0.95, 0.72, 0.05, 1), (0.02, 0.02, 0.02, 1)]
WALLS = [(0.88, 0.84, 0.76, 1), (0.72, 0.42, 0.33, 1), (0.93, 0.93, 0.9, 1), (0.6, 0.66, 0.58, 1)]
ROOFS = [(0.25, 0.12, 0.1, 1), (0.2, 0.22, 0.25, 1), (0.42, 0.2, 0.12, 1)]


def coloured(name, rgba, metallic=0.0, roughness=0.5):
    found = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    found.diffuse_color = rgba
    found.metallic, found.roughness = metallic, roughness
    found.use_nodes = True
    principled = found.node_tree.nodes.get('Principled BSDF')
    if principled is not None:
        principled.inputs['Base Color'].default_value = rgba
        principled.inputs['Metallic'].default_value = metallic
        principled.inputs['Roughness'].default_value = roughness
    return found


def mesh_object(name, verts, faces, mat, smooth=True):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    for polygon in mesh.polygons:
        polygon.use_smooth = smooth
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def box(name, centre, size, mat, bevel=0.0):
    x, y, z = (s / 2 for s in size)
    verts = [(cx * x, cy * y, cz * z) for cx in (-1, 1) for cy in (-1, 1) for cz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    obj = mesh_object(name, verts, faces, mat, smooth=False)
    obj.location = centre
    if bevel:
        modifier = obj.modifiers.new('Bevel', 'BEVEL')
        modifier.width, modifier.segments = bevel, 4
    return obj


def ellipsoid(name, centre, radii, mat, segments=32):
    mesh = bpy.data.meshes.new(name)
    shape = bmesh.new()
    bmesh.ops.create_uvsphere(shape, u_segments=segments, v_segments=segments // 2, radius=1.0)
    shape.to_mesh(mesh)
    shape.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location, obj.scale = centre, radii
    obj.data.materials.append(mat)
    return obj


def ring(name, centre, radius, width, mat, inner=0.0, spokes=0, segments=48):
    """A wheel part along the y axis: a solid disc (tyre or rim), optionally with spokes cut as separate bars."""
    mesh = bpy.data.meshes.new(name)
    shape = bmesh.new()
    bmesh.ops.create_cone(shape, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=width)
    shape.to_mesh(mesh)
    shape.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location, obj.rotation_euler = centre, (math.pi / 2, 0, 0)
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new('Bevel', 'BEVEL')
    bevel.width, bevel.segments = min(width, radius) * 0.18, 4
    return obj


def smooth_profile(points, u):
    """Cosine interpolation through (u, value) keyframes."""
    for (u0, v0), (u1, v1) in zip(points, points[1:]):
        if u0 <= u <= u1:
            t = (u - u0) / (u1 - u0) if u1 > u0 else 0
            t = (1 - math.cos(t * math.pi)) / 2
            return v0 + (v1 - v0) * t
    return points[-1][1]


def car_parts(style):
    paint = coloured('Paint', PAINTS[style % len(PAINTS)], metallic=0.6, roughness=0.25)
    glass = coloured('Glass', (0.03, 0.05, 0.07, 1), metallic=0.2, roughness=0.05)
    rubber = coloured('Tyre', (0.03, 0.03, 0.03, 1), roughness=0.85)
    alloy = coloured('Alloy', (0.7, 0.71, 0.73, 1), metallic=1.0, roughness=0.2)
    lamp = coloured('Headlamp', (0.95, 0.95, 0.88, 1), roughness=0.1)
    tail = coloured('Taillamp', (0.75, 0.02, 0.02, 1), roughness=0.2)
    length, half_width = 4.3 + 0.15 * (style % 3), 0.92 + 0.03 * (style % 2)
    roof = 1.22 + 0.04 * (style % 3)
    top = [(0, 0.62), (0.05, 0.78), (0.3, 0.86), (0.42, 1.0), (0.52, roof), (0.66, roof - 0.02), (0.84, 1.0), (0.96, 0.92), (1, 0.7)]
    low = [(0, 0.34), (0.08, 0.26), (0.92, 0.26), (1, 0.36)]
    wide = [(0, 0.55), (0.08, 0.86), (0.25, 1.0), (0.75, 1.0), (0.92, 0.92), (1, 0.6)]
    sections, around = 72, 48
    verts, faces = [], []
    for i in range(sections + 1):
        u = i / sections
        x = (u - 0.5) * length
        z_top, z_low, w = smooth_profile(top, u), smooth_profile(low, u), half_width * smooth_profile(wide, u)
        mid, half = (z_top + z_low) / 2, (z_top - z_low) / 2
        for j in range(around):
            a = 2 * math.pi * j / around
            c, s = math.cos(a), math.sin(a)
            # A rounded-rectangle (superellipse) cross section: flat sides and roof, rounded edges.
            y = w * math.copysign(abs(c) ** 0.4, c)
            z = mid + half * math.copysign(abs(s) ** 0.6, s)
            if s > 0 and abs(c) < 0.75:
                z -= (1 - smooth_profile(wide, u)) * 0.05
            verts.append((x, y, z))
    for i in range(sections):
        for j in range(around):
            a, b = i * around + j, i * around + (j + 1) % around
            faces.append((a, b, b + around, a + around))
    faces.append(tuple(range(around))[::-1])
    faces.append(tuple(range(sections * around, (sections + 1) * around)))
    parts = [('Car.Body', lambda: mesh_object('Car.Body', verts, faces, paint))]
    wheel_x, wheel_r, track = length * 0.31, 0.34, half_width * 0.98
    for tag, x in (('F', wheel_x), ('R', -wheel_x)):
        for side, y in (('L', track), ('R', -track)):
            name = f'Car.Wheel.{tag}{side}'
            parts.append((name, (lambda n=name, x=x, y=y: ring(n, (x, y, wheel_r), wheel_r, 0.26, rubber))))
            parts.append((name + '.Rim', (lambda n=name + '.Rim', x=x, y=y: ring(
                n, (x, y + math.copysign(0.03, y), wheel_r), wheel_r * 0.66, 0.24, alloy, segments=10))))
    cabin = [((u - 0.5) * length, half_width * 0.9 * smooth_profile(wide, u), smooth_profile(top, u))
             for u in (0.42, 0.5, 0.58, 0.66, 0.76)]
    parts.append(('Car.Glass', lambda: mesh_object('Car.Glass', [
        (x, y * s, z - 0.02 - 0.2 * (1 - k)) for x, y, z in cabin for s in (1, -1) for k in (0, 1)],
        [(4 * i + 0, 4 * i + 4, 4 * i + 5, 4 * i + 1) for i in range(len(cabin) - 1)] +
        [(4 * i + 2, 4 * i + 3, 4 * i + 7, 4 * i + 6) for i in range(len(cabin) - 1)], glass)))
    for side in (1, -1):
        tag = 'L' if side > 0 else 'R'
        parts.append((f'Car.Headlamp.{tag}', (lambda s=side, t=tag: ellipsoid(
            f'Car.Headlamp.{t}', (length * 0.47, s * half_width * 0.62, 0.66), (0.08, 0.2, 0.06), lamp))))
        parts.append((f'Car.Taillamp.{tag}', (lambda s=side, t=tag: box(
            f'Car.Taillamp.{t}', (-length * 0.49, s * half_width * 0.6, 0.78), (0.04, 0.4, 0.07), tail, bevel=0.01))))
        parts.append((f'Car.Mirror.{tag}', (lambda s=side, t=tag: ellipsoid(
            f'Car.Mirror.{t}', (length * 0.06, s * (half_width + 0.1), 1.0), (0.1, 0.08, 0.06), paint))))
    parts.append(('Car.Spoiler', lambda: box('Car.Spoiler', (-length * 0.45, 0, 0.98), (0.22, half_width * 1.7, 0.03),
                                             paint, bevel=0.01)))
    return parts, 'Car.Body', (length, 2 * half_width, roof)


def house_parts(style):
    wall = coloured('Wall', WALLS[style % len(WALLS)], roughness=0.8)
    roof_mat = coloured('RoofTiles', ROOFS[style % len(ROOFS)], roughness=0.7)
    trim = coloured('Trim', (0.95, 0.95, 0.95, 1), roughness=0.5)
    glass = coloured('WindowGlass', (0.35, 0.5, 0.6, 1), metallic=0.1, roughness=0.05)
    door_mat = coloured('Door', (0.3, 0.16, 0.08, 1), roughness=0.6)
    floors, width, depth = 1 + style % 2, 8.0 + 2 * (style % 3), 6.5
    storey = 2.8
    height = floors * storey
    parts = [('House.Foundation', lambda: box('House.Foundation', (0, 0, 0.15), (width + 0.4, depth + 0.4, 0.3), trim,
                                              bevel=0.03)),
             ('House.Walls', lambda: box('House.Walls', (0, 0, 0.3 + height / 2), (width, depth, height), wall, bevel=0.04))]
    top, ridge = 0.3 + height, 0.3 + height + 2.2 + 0.3 * (style % 2)
    over = 0.45
    roof_verts = [(-width / 2 - over, -depth / 2 - over, top), (width / 2 + over, -depth / 2 - over, top),
                  (width / 2 + over, 0, ridge), (-width / 2 - over, 0, ridge),
                  (-width / 2 - over, depth / 2 + over, top), (width / 2 + over, depth / 2 + over, top)]
    parts.append(('House.Roof', lambda: mesh_object('House.Roof', roof_verts, [(0, 1, 2, 3), (3, 2, 5, 4), (0, 3, 4),
                                                                               (1, 5, 2), (0, 4, 5, 1)], roof_mat,
                                                    smooth=False)))
    parts.append(('House.Chimney', lambda: box('House.Chimney', (width * 0.28, depth * 0.18, ridge - 0.2),
                                               (0.6, 0.6, 2.0), wall, bevel=0.02)))
    parts.append(('House.Door', lambda: box('House.Door', (0, -depth / 2 - 0.03, 0.3 + 1.05), (1.0, 0.1, 2.1), door_mat,
                                            bevel=0.02)))
    parts.append(('House.Step', lambda: box('House.Step', (0, -depth / 2 - 0.45, 0.1), (1.6, 0.7, 0.2), trim, bevel=0.02)))
    count = 0
    for floor in range(floors):
        z = 0.3 + floor * storey + 1.55
        for x in (-width * 0.3, width * 0.3) if floor == 0 else (-width * 0.3, 0, width * 0.3):
            for y, face in ((-depth / 2, -1), (depth / 2, 1)):
                count += 1
                name = f'House.Window.{count}'
                parts.append((name, (lambda n=name, x=x, y=y, z=z, f=face: box(
                    n, (x, y + f * 0.04, z), (1.2, 0.08, 1.3), glass, bevel=0.01))))
                parts.append((name + '.Frame', (lambda n=name + '.Frame', x=x, y=y, z=z, f=face: box(
                    n, (x, y + f * 0.06, z - 0.72), (1.45, 0.16, 0.08), trim, bevel=0.01))))
    return parts, 'House.Walls', (width, depth, ridge)


BUILDERS = {'car': car_parts, 'house': house_parts}


def run_builder(kind):
    parts, main_name, size = BUILDERS[kind](int(REQUEST.get('style', 0)))
    cube = bpy.data.objects.get('Cube')
    if cube is None:
        raise ValueError('The default cube is missing.')
    created = []
    clock = {'t': 0.0}

    def grow():
        """The cube stretches live to the model's footprint, then the parts replace it one by one."""
        clock['t'] = min(1.0, clock['t'] + 1.0 / (FPS * 1.5))
        e = clock['t'] * clock['t'] * (3 - 2 * clock['t'])
        cube.scale = tuple(1 + (s / 2 - 1) * e for s in size)
        cube.location = (0, 0, size[2] / 2 * e)
        if clock['t'] >= 1.0:
            view_on([cube])
            bpy.app.timers.register(next_part, first_interval=0.5)
            return None
        return 1.0 / FPS

    def next_part():
        if parts:
            name, make = parts.pop(0)
            created.append(make())
            if len(created) == 1:
                bpy.data.objects.remove(cube)  # The first real part replaces the placeholder block.
                view_on(created)
            return 0.35
        if kind == 'car':  # The lofted body gets its high-poly smoothness live; the house keeps crisp bevels.
            detail = bpy.data.objects[main_name].modifiers.new('Detail', 'SUBSURF')
            detail.levels = detail.render_levels = 2
        view_on(created)
        return save_and_report([o.name for o in created])
    bpy.app.timers.register(grow, first_interval=0.5)


# ---- Realistic humans (Blender Studio "Human Base Meshes", CC0) ------------------------------------------------
HUMAN = {
    'human_head': {'collection': 'Head (Sculpting) - Realistic', 'main': 'GEO-head_sculpting_realistic',
                   'subdivide': 2, 'grain': ('CLOUDS', 0.004, 0.0006), 'name': 'Head'},
    'human_body_male': {'collection': 'Body Male - Realistic', 'main': 'GEO-body_male_realistic',
                        'subdivide': 0, 'grain': ('VORONOI', 0.03, 0.0025), 'name': 'Body'},
    'human_body_female': {'collection': 'Body Female - Realistic', 'main': 'GEO-body_female_realistic',
                          'subdivide': 0, 'grain': ('VORONOI', 0.03, 0.0025), 'name': 'Body'},
}
SKIN = {'Skin': (0.80, 0.58, 0.47, 1), 'Sclera': (0.93, 0.92, 0.9, 1), 'IrisBlue': (0.16, 0.33, 0.55, 1),
        'IrisBrown': (0.30, 0.17, 0.08, 1)}


def realistic_material(name, subsurface=0.0):
    found = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    found.diffuse_color = SKIN[name]
    found.use_nodes = True
    principled = found.node_tree.nodes.get('Principled BSDF')
    if principled is not None:
        principled.inputs['Base Color'].default_value = SKIN[name]
        if subsurface and 'Subsurface Weight' in principled.inputs:
            principled.inputs['Subsurface Weight'].default_value = subsurface
        principled.inputs['Roughness'].default_value = 0.45
    return found


def view_on(objects):
    """Frame the model in the 3D view so the user sees the detail being added."""
    window = bpy.context.window_manager.windows[0]
    for area in window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        region = next(r for r in area.regions if r.type == 'WINDOW')
        for obj in bpy.context.scene.objects:
            obj.select_set(obj in objects)
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.view3d.view_selected()


def run_human(kind):
    spec = HUMAN[kind]
    asset = REQUEST['asset']
    with bpy.data.libraries.load(asset, link=False) as (source, target):
        if spec['collection'] not in source.collections:
            raise ValueError('The human base mesh bundle has no ' + spec['collection'])
        target.collections = [spec['collection']]
    collection = target.collections[0]
    parts = list(collection.all_objects)
    main = next(o for o in parts if o.name.startswith(spec['main']))
    centre = main.matrix_world.translation.copy()
    for obj in parts:
        obj.location = obj.location - centre  # The model at the origin, where the cube was.
        obj.hide_viewport = True
    cube = subdivided_cube()
    size = max(main.dimensions)
    rough = {'type': 'sphere', 'radius': size / 2, 'sx': main.dimensions[0] / size, 'sy': main.dimensions[1] / size,
             'sz': main.dimensions[2] / size}
    steps = []

    def reveal():
        bpy.context.scene.collection.children.link(collection)
        for obj in parts:
            obj.hide_viewport = False
        bpy.data.objects.remove(cube)
        main.data.materials.clear()
        main.data.materials.append(realistic_material('Skin', subsurface=0.15))
        iris = 'IrisBlue' if REQUEST.get('eye_colour', 'blue') == 'blue' else 'IrisBrown'
        for obj in parts:
            if obj is main:
                continue
            obj.data.materials.clear()
            obj.data.materials.append(realistic_material(iris if 'iris' in obj.name.lower() else 'Sclera'))
        view_on(parts)
        multires = next((m for m in main.modifiers if m.type == 'MULTIRES'), None)
        if multires is not None:
            multires.levels = 0
            steps.extend(('multires', level) for level in range(1, multires.total_levels + 1))
        steps.extend(('subdivide', level) for level in range(1, spec['subdivide'] + 1))
        steps.append(('grain', 0))
        bpy.app.timers.register(refine, first_interval=0.6)
        return None

    finishing = []

    def refine():
        if not steps and not finishing and REQUEST.get('look') and 'started' not in REQUEST:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import blender_human
            REQUEST['started'] = True
            material_preview()
            finishing.extend(blender_human.steps(main, parts, REQUEST['look'], kind))
        if not steps and finishing:
            again = finishing[0]()
            if not again:
                finishing.pop(0)  # A step that returns True (hair growing) runs again on the next tick.
            return 0.7
        if not steps:
            for obj in parts:
                if obj is main:
                    obj.name = spec['name']
            return save_and_report([o.name for o in parts])
        kind_of, level = steps.pop(0)
        if kind_of == 'multires':
            next(m for m in main.modifiers if m.type == 'MULTIRES').levels = level  # Sculpted detail, level by level.
        elif kind_of == 'subdivide':
            modifier = main.modifiers.get('Detail') or main.modifiers.new('Detail', 'SUBSURF')
            modifier.levels = modifier.render_levels = level
        else:
            texture_type, size, strength = spec['grain']
            texture = bpy.data.textures.new('SkinGrain', texture_type)
            texture.noise_scale = size
            if texture_type == 'VORONOI':
                texture.distance_metric = 'DISTANCE'
                texture.color_mode = 'INTENSITY'
                texture.noise_intensity = 1.0
            displace = main.modifiers.new('Grain', 'DISPLACE')  # Pores on a face, a fine vein-like web on a body.
            displace.texture, displace.strength, displace.mid_level = texture, strength, 0.5
        return 0.9
    bpy.app.timers.register(morph(cube, rough, REQUEST.get('seconds', 2.5), reveal), first_interval=0.5)
    cube.location = (0, 0, 0)


def material_preview():
    for area in bpy.context.window_manager.windows[0].screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'MATERIAL'  # Textures and glass visible while it is built.


def run_house(plan):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import blender_house
    cube = bpy.data.objects.get('Cube')
    work = blender_house.steps(plan)
    size = (float(plan['width']), float(plan['depth']), int(plan['floors']) * blender_house.STOREY)
    clock = {'t': 0.0, 'framed': 0}

    def grow():
        clock['t'] = min(1.0, clock['t'] + 1.0 / (FPS * 1.2))
        e = clock['t'] * clock['t'] * (3 - 2 * clock['t'])
        cube.scale = tuple(1 + (s / 2 - 1) * e for s in size)
        cube.location = (0, 0, size[2] / 2 * e)
        if clock['t'] >= 1.0:
            view_on([cube])
            material_preview()
            bpy.app.timers.register(next_step, first_interval=0.4)
            return None
        return 1.0 / FPS

    def next_step():
        if work:
            work.pop(0)()
            if bpy.data.objects.get('Cube'):
                bpy.data.objects.remove(bpy.data.objects['Cube'])
            clock['framed'] += 1
            if clock['framed'] in (2, 6):
                view_on([o for o in bpy.context.scene.objects if o.name.startswith('House')])
            return 0.6
        view_on([o for o in bpy.context.scene.objects if o.name.startswith('House')])
        return save_and_report([o.name for o in bpy.context.scene.objects if o.type == 'MESH'
                                and not o.name.startswith('Cut')])
    bpy.app.timers.register(grow, first_interval=0.5)


def start():
    try:
        show_materials()
        for name in ('Camera', 'Light'):
            if bpy.data.objects.get(name):
                bpy.data.objects[name].hide_viewport = True  # Keep the view on the model.
        operation = REQUEST['operation']
        if operation == 'house' and REQUEST.get('plan'):
            run_house(REQUEST['plan'])
        elif operation in HUMAN:
            run_human(operation)
        elif operation in BUILDERS:
            run_builder(operation)
        else:
            run_head() if operation == 'head' else run_morph()
    except Exception as error:  # Reported to Jarvis; the window stays open for the user to see.
        finish({'ok': False, 'error': f'{type(error).__name__}: {error}'})
    return None


bpy.app.timers.register(start, first_interval=1.0)
