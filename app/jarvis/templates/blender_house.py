"""Plan-driven house builder for the live Blender template (imported by blender_live.py inside Blender).

`steps(plan)` returns the build as a list of small functions; the template runs one per timer tick, so the
user watches the house go up: ground, foundation, walls floor by floor with real openings cut through them
(Boolean modifiers against hidden cutters), framed windows and a door, floor slabs, interior partitions with
doorways, stairs, furniture for every planned room, the roof (gable, hip or flat), chimney and porch, then the
procedural materials (brick, plaster, wood siding, stone, tiles, slate, metal, wood floors, glass).
"""
import math

import bpy

T = 0.25          # Exterior wall thickness.
SLAB = 0.2        # Floor slab thickness.
STOREY = 2.9


def rgb(hex_colour, fallback=(0.8, 0.8, 0.8)):
    try:
        value = hex_colour.lstrip('#')
        return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (AttributeError, ValueError):
        return fallback


def darker(colour, k=0.75):
    return tuple(max(0.0, c * k) for c in colour[:3])


# ---- Materials (procedural, no image files) ---------------------------------------------------------------
def material(name, kind, colour, metallic=0.0, roughness=0.6, transmission=0.0):
    found = bpy.data.materials.get(name)
    if found:
        return found
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*colour[:3], 1)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    if transmission:
        for key in ('Transmission Weight', 'Transmission'):
            if key in shader.inputs:
                shader.inputs[key].default_value = transmission
        shader.inputs['IOR'].default_value = 1.45
    coords = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    links.new(coords.outputs['Object'], mapping.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    base = (*colour[:3], 1)
    if kind in ('brick', 'tiles', 'slate', 'shingles'):
        tex = nodes.new('ShaderNodeTexBrick')
        tex.inputs['Color1'].default_value = base
        tex.inputs['Color2'].default_value = (*darker(colour, 0.82), 1)
        tex.inputs['Mortar'].default_value = (0.72, 0.7, 0.66, 1) if kind == 'brick' else (*darker(colour, 0.5), 1)
        tex.inputs['Scale'].default_value = {'brick': 4.0, 'tiles': 3.0, 'slate': 3.5, 'shingles': 3.2}[kind]
        tex.inputs['Mortar Size'].default_value = 0.015 if kind == 'brick' else 0.01
        links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
        links.new(tex.outputs['Color'], shader.inputs['Base Color'])
        links.new(tex.outputs['Fac'], bump.inputs['Height'])
    elif kind in ('wood', 'floor', 'metal'):
        tex = nodes.new('ShaderNodeTexWave')
        tex.bands_direction = 'Z' if kind == 'wood' else 'X'
        tex.inputs['Scale'].default_value = {'wood': 6.0, 'floor': 3.0, 'metal': 9.0}[kind]
        tex.inputs['Distortion'].default_value = 2.0 if kind != 'metal' else 0.0
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (*darker(colour, 0.7), 1)
        ramp.color_ramp.elements[1].color = base
        links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
        links.new(tex.outputs['Fac'], ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'], shader.inputs['Base Color'])
        links.new(tex.outputs['Fac'], bump.inputs['Height'])
    elif kind == 'stone':
        tex = nodes.new('ShaderNodeTexVoronoi')
        tex.inputs['Scale'].default_value = 3.0
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (*darker(colour, 0.6), 1)
        ramp.color_ramp.elements[1].color = base
        links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
        links.new(tex.outputs['Distance'], ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'], shader.inputs['Base Color'])
        links.new(tex.outputs['Distance'], bump.inputs['Height'])
    else:  # plaster, paint, fabric, grass: fine noise in colour and surface
        tex = nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = {'grass': 40.0, 'fabric': 60.0}.get(kind, 18.0)
        mix = nodes.new('ShaderNodeValToRGB')
        mix.color_ramp.elements[0].color = (*darker(colour, 0.9), 1)
        mix.color_ramp.elements[1].color = base
        links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
        links.new(tex.outputs['Fac'], mix.inputs['Fac'])
        links.new(mix.outputs['Color'], shader.inputs['Base Color'])
        links.new(tex.outputs['Fac'], bump.inputs['Height'])
        bump.inputs['Strength'].default_value = 0.12
    return mat


# ---- Geometry helpers ---------------------------------------------------------------------------------------
def collection(name):
    found = bpy.data.collections.get(name)
    if found is None:
        found = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(found)
    return found


def boxes(name, parts, mat, bevel=0.0, where='House'):
    """One object from several axis-aligned boxes: parts = [(centre, size), ...]."""
    verts, faces = [], []
    for (cx, cy, cz), (sx, sy, sz) in parts:
        base = len(verts)
        for dx in (-.5, .5):
            for dy in (-.5, .5):
                for dz in (-.5, .5):
                    verts.append((cx + dx * sx, cy + dy * sy, cz + dz * sz))
        faces += [(base + a, base + b, base + c, base + d) for a, b, c, d in
                  ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    obj = bpy.data.objects.new(name, mesh)
    collection(where).objects.link(obj)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new('Bevel', 'BEVEL')
        modifier.width, modifier.segments, modifier.limit_method = bevel, 3, 'ANGLE'
    return obj


def cutter(name, centre, size, group):
    obj = boxes(name, [(centre, size)], material('Cutter', 'paint', (1, 0, 1)), where=group)
    obj.hide_viewport = obj.hide_render = True
    obj.display_type = 'WIRE'
    return obj


def cut(wall, group_name):
    modifier = wall.modifiers.new('Openings', 'BOOLEAN')
    modifier.operation, modifier.operand_type = 'DIFFERENCE', 'COLLECTION'
    modifier.collection = bpy.data.collections[group_name]
    for solver in ('MANIFOLD', 'FAST', 'FLOAT', 'EXACT'):  # Names differ across Blender versions.
        try:
            modifier.solver = solver
            break
        except TypeError:
            continue


# ---- Furniture ----------------------------------------------------------------------------------------------
def furniture_parts(kind):
    """(size, parts relative to the item's floor centre) for each furniture type."""
    if kind == 'sofa':
        return (2.1, 0.9), [((0, 0, .22), (2.1, .9, .44)), ((0, .35, .62), (2.1, .2, .5)), ((-.98, 0, .5), (.16, .9, .3)),
                            ((.98, 0, .5), (.16, .9, .3))]
    if kind == 'armchair':
        return (.9, .9), [((0, 0, .22), (.9, .9, .44)), ((0, .35, .62), (.9, .2, .5))]
    if kind in ('coffee table', 'dining table', 'desk', 'bedside table'):
        w, d, h = {'coffee table': (1.1, .6, .45), 'dining table': (1.6, .9, .76), 'desk': (1.3, .65, .75),
                   'bedside table': (.5, .45, .55)}[kind]
        legs = [((x * (w / 2 - .05), y * (d / 2 - .05), h / 2 - .02), (.06, .06, h - .04)) for x in (-1, 1) for y in (-1, 1)]
        return (w, d), [((0, 0, h - .02), (w, d, .04))] + legs
    if kind == 'chair':
        return (.5, .5), [((0, 0, .45), (.46, .46, .05)), ((0, .21, .7), (.46, .05, .5))] + [
            ((x * .19, y * .19, .22), (.04, .04, .44)) for x in (-1, 1) for y in (-1, 1)]
    if kind == 'tv stand':
        return (1.6, .45), [((0, 0, .25), (1.6, .45, .5)), ((0, .05, 1.0), (1.3, .06, .75))]
    if kind == 'rug':
        return (2.4, 1.6), [((0, 0, .005), (2.4, 1.6, .01))]
    if kind == 'floor lamp':
        return (.4, .4), [((0, 0, .02), (.35, .35, .04)), ((0, 0, .8), (.04, .04, 1.55)), ((0, 0, 1.6), (.4, .4, .3))]
    if kind == 'kitchen counter':
        return (2.6, .65), [((0, 0, .45), (2.6, .62, .88)), ((0, 0, .91), (2.64, .66, .04))]
    if kind == 'fridge':
        return (.75, .7), [((0, 0, .9), (.75, .7, 1.8))]
    if kind == 'coat rack':
        return (.4, .4), [((0, 0, .9), (.05, .05, 1.8)), ((0, 0, 1.7), (.45, .05, .05)), ((0, 0, .02), (.4, .4, .04))]
    if kind == 'bed':
        return (1.7, 2.1), [((0, 0, .2), (1.7, 2.1, .4)), ((0, -.02, .5), (1.6, 2.0, .2)), ((0, .98, .7), (1.7, .1, 1.0)),
                            ((-.4, .75, .66), (.6, .35, .12)), ((.4, .75, .66), (.6, .35, .12))]
    if kind == 'wardrobe':
        return (1.3, .62), [((0, 0, 1.0), (1.3, .6, 2.0)), ((0, -.31, 1.0), (.02, .02, 1.9))]
    if kind == 'bookshelf':
        return (1.0, .35), [((0, 0, 1.0), (1.0, .35, 2.0))] + [((0, -.02, z), (.96, .33, .02)) for z in (.4, .8, 1.2, 1.6)]
    if kind == 'bathtub':
        return (1.7, .78), [((0, 0, .28), (1.7, .78, .56)), ((0, 0, .5), (1.5, .6, .14))]
    if kind == 'sink':
        return (.7, .5), [((0, 0, .4), (.7, .5, .8)), ((0, 0, .84), (.55, .4, .08))]
    if kind == 'toilet':
        return (.45, .7), [((0, -.05, .2), (.4, .55, .4)), ((0, .27, .55), (.45, .18, .4))]
    return (.6, .6), [((0, 0, .4), (.6, .6, .8))]


FURNITURE_COLOURS = {'sofa': ('fabric', '#55657a'), 'armchair': ('fabric', '#7a5a45'), 'rug': ('fabric', '#a4483a'),
                     'bed': ('fabric', '#e8e2d6'), 'kitchen counter': ('wood', '#d9d4cc'), 'fridge': ('metal', '#d0d3d6'),
                     'bathtub': ('paint', '#f4f4f2'), 'sink': ('paint', '#f4f4f2'), 'toilet': ('paint', '#f4f4f2'),
                     'floor lamp': ('metal', '#2a2a2a'), 'tv stand': ('wood', '#3b2b20')}


def place(room, items, z, rotation_seed):
    """Positions for the room's items: along the back wall, then the side walls, rug in the middle; no overlaps."""
    (x0, x1), (y0, y1) = room
    taken, placed = [], []
    margin = .15
    for index, kind in enumerate(items):
        (w, d), _ = furniture_parts(kind)
        if kind == 'rug':
            spot = ((x0 + x1) / 2, (y0 + y1) / 2)
            if (x1 - x0) > w + .4 and (y1 - y0) > d + .4:
                placed.append((kind, spot, 0))
            continue
        candidates = []
        steps = 6
        for k in range(steps):
            t = (k + .5) / steps
            candidates.append(((x0 + margin + w / 2) + t * max(0, (x1 - x0) - w - 2 * margin), y1 - margin - d / 2, 0))
            candidates.append((x0 + margin + d / 2, (y0 + margin + w / 2) + t * max(0, (y1 - y0) - w - 2 * margin),
                               math.pi / 2))
            candidates.append((x1 - margin - d / 2, (y0 + margin + w / 2) + t * max(0, (y1 - y0) - w - 2 * margin),
                               -math.pi / 2))
        for cx, cy, angle in candidates[(rotation_seed + index) % 3:] + candidates[:(rotation_seed + index) % 3]:
            hw, hd = (w / 2, d / 2) if angle == 0 else (d / 2, w / 2)
            rect = (cx - hw, cx + hw, cy - hd, cy + hd)
            inside = rect[0] >= x0 + .05 and rect[1] <= x1 - .05 and rect[2] >= y0 + .05 and rect[3] <= y1 - .05
            if inside and all(rect[1] <= o[0] or rect[0] >= o[1] or rect[3] <= o[2] or rect[2] >= o[3] for o in taken):
                taken.append(rect)
                placed.append((kind, (cx, cy), angle))
                break
    return [(kind, (x, y, z), angle) for kind, (x, y), angle in placed]


def furniture(name, kind, spot, angle):
    _, parts = furniture_parts(kind)
    style, colour = FURNITURE_COLOURS.get(kind, ('wood', '#8a6446'))
    obj = boxes(name, parts, material('Furniture ' + kind, style, rgb(colour)), bevel=.012, where='Interior')
    obj.location, obj.rotation_euler = spot, (0, 0, angle)
    return obj


# ---- The build ------------------------------------------------------------------------------------------------
def steps(plan):
    floors, width, depth = int(plan['floors']), float(plan['width']), float(plan['depth'])
    height = floors * STOREY
    walls_kind, wall_colour = plan['walls']['material'], rgb(plan['walls']['colour'])
    trim = material('Trim', 'paint', rgb(plan['walls']['trim_colour']), roughness=.4)
    wall_mat = material('Walls ' + walls_kind, walls_kind, wall_colour, roughness=.85)
    glass = material('Glass', 'paint', (0.6, 0.72, 0.8), roughness=.02, transmission=1.0)
    inner = material('Interior paint', 'plaster', (0.93, 0.91, 0.86), roughness=.9)
    floor_mat = material('Wood floor', 'floor', (0.55, 0.38, 0.24), roughness=.5)
    roof = plan['roof']
    roof_mat = material('Roof ' + roof['material'], roof['material'], rgb(roof['colour']),
                        metallic=.6 if roof['material'] == 'metal' else 0, roughness=.5)
    door_mat = material('Door', 'wood', rgb(plan['door']['colour']), roughness=.45)
    build = []
    x0, x1, y0, y1 = -width / 2, width / 2, -depth / 2, depth / 2
    base = 0.3

    build.append(lambda: boxes('Ground', [((0, 0, -.05), (width + 24, depth + 24, .1))],
                               material('Grass', 'grass', (0.22, 0.36, 0.14), roughness=1), where='Site'))
    build.append(lambda: boxes('House.Foundation', [((0, 0, base / 2), (width + .3, depth + .3, base))],
                               material('Concrete', 'plaster', (0.6, 0.6, 0.58)), bevel=.02))
    windows_front, windows_side = int(plan['windows']['per_floor_front']), int(plan['windows']['per_floor_side'])
    count = {'window': 0}

    def openings(floor):
        z = base + floor * STOREY + 1.45
        out = []
        xs = [x0 + (k + 1) * width / (windows_front + 1) for k in range(windows_front)]
        door_x = 0.0
        for x in xs:
            if floor == 0 and abs(x - door_x) < 1.2:
                continue
            out.append(('front', x, y0, z))
            out.append(('back', x, y1, z))
        for k in range(windows_side):
            y = y0 + (k + 1) * depth / (windows_side + 1)
            out.append(('left', x0, y, z))
            out.append(('right', x1, y, z))
        return out

    for floor in range(floors):
        zc = base + floor * STOREY + STOREY / 2
        group = f'Cutters.F{floor}'

        def walls(floor=floor, zc=zc, group=group):
            collection(group).hide_viewport = True
            pieces = {'front': ((0, y0 + T / 2, zc), (width, T, STOREY)), 'back': ((0, y1 - T / 2, zc), (width, T, STOREY)),
                      'left': ((x0 + T / 2, 0, zc), (T, depth - 2 * T, STOREY)),
                      'right': ((x1 - T / 2, 0, zc), (T, depth - 2 * T, STOREY))}
            for side, part in pieces.items():
                boxes(f'House.Wall.F{floor}.{side}', [part], wall_mat, bevel=.015)
        build.append(walls)

        def holes(floor=floor, group=group):
            w, h = float(plan['windows']['width']), float(plan['windows']['height'])
            for side, x, y, z in openings(floor):
                along = side in ('front', 'back')
                cutter(f'Cut.F{floor}.{side}.{x:.2f}.{y:.2f}', (x, y, z), (w, T * 3, h) if along else (T * 3, w, h), group)
            if floor == 0:
                cutter('Cut.Door', (0, y0, base + 1.05), (1.0, T * 3, 2.1), group)
            for side in ('front', 'back', 'left', 'right'):
                cut(bpy.data.objects[f'House.Wall.F{floor}.{side}'], group)  # The openings appear in the walls.
        build.append(holes)

        def fittings(floor=floor):
            w, h = float(plan['windows']['width']), float(plan['windows']['height'])
            for side, x, y, z in openings(floor):
                count['window'] += 1
                n = count['window']
                along = side in ('front', 'back')
                inset = (0, T / 2 if side == 'front' else -T / 2, 0) if along else (T / 2 if side == 'left' else -T / 2, 0, 0)
                cx, cy = x + inset[0], y + inset[1]
                pane = (w - .1, .02, h - .1) if along else (.02, w - .1, h - .1)
                boxes(f'House.Window.{n}', [((cx, cy, z), pane)], glass)
                frame = [((cx, cy, z + h / 2 - .03), (w, .08, .06) if along else (.08, w, .06)),
                         ((cx, cy, z - h / 2 + .03), (w, .08, .06) if along else (.08, w, .06)),
                         ((cx + (w / 2 - .03 if along else 0), cy + (0 if along else w / 2 - .03), z),
                          (.06, .08, h) if along else (.08, .06, h)),
                         ((cx - (w / 2 - .03 if along else 0), cy - (0 if along else w / 2 - .03), z),
                          (.06, .08, h) if along else (.08, .06, h)),
                         ((cx, cy, z), (.04, .06, h) if along else (.06, .04, h))]
                boxes(f'House.Window.{n}.Frame', frame, trim, bevel=.006)
                sill_y = y - .12 if side == 'front' else y + .12 if side == 'back' else y
                sill_x = x - .12 if side == 'left' else x + .12 if side == 'right' else x
                boxes(f'House.Window.{n}.Sill', [((sill_x, sill_y, z - h / 2 - .04), (w + .2, .22, .06) if along
                                                  else (.22, w + .2, .06))], trim, bevel=.01)
            if floor == 0:
                boxes('House.Door', [((0, y0 + .06, base + 1.05), (.96, .06, 2.08))], door_mat, bevel=.01)
                boxes('House.Door.Frame', [((0, y0 + .02, base + 2.14), (1.16, .12, .1)), ((-.53, y0 + .02, base + 1.05),
                      (.1, .12, 2.1)), ((.53, y0 + .02, base + 1.05), (.1, .12, 2.1)), ((.32, y0, base + 1.0),
                      (.06, .08, .06))], trim, bevel=.008)
                boxes('House.Step', [((0, y0 - .4, base / 2), (1.6, .6, base))], material('Stone step', 'stone', (.6, .6, .58)),
                      bevel=.02)
        build.append(fittings)

        def interior(floor=floor):
            z = base + floor * STOREY
            boxes(f'House.Floor.{floor}', [((0, 0, z + .02), (width - 2 * T, depth - 2 * T, .04))], floor_mat)
            if floor > 0:
                boxes(f'House.Slab.{floor}', [((0, 0, z - SLAB / 2), (width - 2 * T, depth - 2 * T, SLAB))], inner)
            rooms = [r for r in plan['rooms'] if int(r['floor']) == floor]
            edges = [x0 + T + k * (width - 2 * T) / len(rooms) for k in range(len(rooms) + 1)]
            for k in range(1, len(rooms)):  # Partitions with a doorway near the front.
                x = edges[k]
                door_at = y0 + T + 1.6
                boxes(f'House.Partition.{floor}.{k}', [((x, (y0 + T + door_at - .5) / 2, z + STOREY / 2),
                                                        (.1, door_at - .5 - (y0 + T), STOREY)),
                                                       ((x, (door_at + .5 + y1 - T) / 2, z + STOREY / 2),
                                                        (.1, y1 - T - (door_at + .5), STOREY))], inner)
            for index, room in enumerate(rooms):
                bounds = ((edges[index] + .05, edges[index + 1] - .05), (y0 + T, y1 - T))
                items = [i for i in room['furniture'] if i != 'stairs']
                for n, (kind, spot, angle) in enumerate(place(bounds, items, z + .04, floor + index)):
                    furniture(f'Furniture.F{floor}.{room["name"].replace(" ", "_")}.{kind.replace(" ", "_")}.{n}', kind,
                              spot, angle)
            if floor < floors - 1:
                steps_n, run = 15, 3.6
                rise = STOREY / steps_n
                sx = x1 - T - .55
                boxes(f'House.Stairs.{floor}', [((sx, y1 - T - run + (k + .5) * run / steps_n, z + rise * (k + .5)),
                                                 (.95, run / steps_n + .02, rise)) for k in range(steps_n)],
                      material('Stair wood', 'floor', (0.45, 0.3, 0.18)), bevel=.01)
        build.append(interior)

    top = base + height

    def roofing():
        over = .45
        kind, pitch = roof['type'], math.radians(float(roof.get('pitch_deg') or 0))
        if kind == 'flat':
            boxes('House.Roof', [((0, 0, top + .15), (width + .2, depth + .2, .3)),
                                 ((0, y0 - .05, top + .5), (width + .2, .15, .4)), ((0, y1 + .05, top + .5), (width + .2, .15, .4)),
                                 ((x0 - .05, 0, top + .5), (.15, depth + .2, .4)), ((x1 + .05, 0, top + .5), (.15, depth + .2, .4))],
                  roof_mat, bevel=.02)
            return
        rise = (depth / 2 + over) * math.tan(pitch)
        a, b = -width / 2 - over, width / 2 + over
        if kind == 'hip':
            inset = min(width / 2 - .2, depth / 2 + over)
            ridge = [(a + inset, 0, top + rise), (b - inset, 0, top + rise)]
        else:
            ridge = [(a, 0, top + rise), (b, 0, top + rise)]
        verts = [(a, y0 - over, top), (b, y0 - over, top), (b, y1 + over, top), (a, y1 + over, top), *ridge]
        faces = [(0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)]
        mesh = bpy.data.meshes.new('House.Roof')
        mesh.from_pydata(verts, [], faces)
        obj = bpy.data.objects.new('House.Roof', mesh)
        collection('House').objects.link(obj)
        obj.data.materials.append(roof_mat)
        solid = obj.modifiers.new('Thickness', 'SOLIDIFY')
        solid.thickness = .18
        if plan.get('chimney'):
            boxes('House.Chimney', [((width * .25, depth * .15, top + rise * .7), (.7, .7, rise * 1.1 + 1.2)),
                                    ((width * .25, depth * .15, top + rise * .7 + rise * .55 + .62), (.85, .85, .12))],
                  material('Chimney brick', 'brick', (0.55, 0.25, 0.18)), bevel=.01)
    build.append(roofing)

    if plan.get('porch'):
        build.append(lambda: boxes('House.Porch', [((0, y0 - 1.4, base / 2), (width * .6, 2.4, base))] + [
            ((x, y0 - 2.45, base + 1.3), (.16, .16, 2.6)) for x in (-width * .28, width * .28)] + [
            ((0, y0 - 1.4, base + 2.7), (width * .62, 2.6, .14))], trim, bevel=.02))
    return build
