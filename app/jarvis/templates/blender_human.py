"""Realistic finishing for a human head or body (imported by blender_live.py inside Blender).

`steps(main, parts, look)` returns small functions the live template runs one per tick, so each layer is seen
appearing: skin shader (tone variation, subsurface scattering, pores, faint veins), eyes (patterned iris,
glossy sclera with fine vessels), then hair grown as particle strands from regions found on the mesh itself:
scalp hair (its length grows on screen), eyebrows, eyelashes, a beard or stubble for men, fine body hair on
bodies. `look` sets skin tone, hair colour and length, eye colour and beard, and differs per run.
"""
import bpy

SKIN_TONES = {'light': (0.93, 0.76, 0.66), 'fair': (0.87, 0.67, 0.55), 'medium': (0.76, 0.55, 0.42),
              'olive': (0.66, 0.48, 0.34), 'brown': (0.48, 0.31, 0.2), 'dark': (0.3, 0.18, 0.11)}
HAIR_MELANIN = {'black': (1.0, 0.0), 'dark brown': (0.75, 0.05), 'brown': (0.55, 0.1), 'blonde': (0.2, 0.08),
                'red': (0.45, 0.9), 'grey': (0.05, 0.0)}
EYES = {'blue': (0.12, 0.3, 0.55), 'green': (0.18, 0.4, 0.2), 'hazel': (0.42, 0.3, 0.12), 'brown': (0.25, 0.13, 0.05),
        'grey': (0.4, 0.45, 0.5)}


def skin_material(tone):
    base = SKIN_TONES.get(tone, SKIN_TONES['medium'])
    mat = bpy.data.materials.new('Skin ' + tone)
    mat.use_nodes = True
    mat.diffuse_color = (*base, 1)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    if 'Subsurface Weight' in shader.inputs:
        shader.inputs['Subsurface Weight'].default_value = 0.3
    if 'Subsurface Radius' in shader.inputs:
        shader.inputs['Subsurface Radius'].default_value = (1.0, 0.25, 0.12)
    shader.inputs['Roughness'].default_value = 0.42
    coords = nodes.new('ShaderNodeTexCoord')
    mottle = nodes.new('ShaderNodeTexNoise')  # Uneven real skin colour.
    mottle.inputs['Scale'].default_value = 35.0
    tone_ramp = nodes.new('ShaderNodeValToRGB')
    tone_ramp.color_ramp.elements[0].color = (*(c * 0.88 for c in base), 1)
    tone_ramp.color_ramp.elements[1].color = (*(min(1, c * 1.05) for c in base), 1)
    links.new(coords.outputs['Object'], mottle.inputs['Vector'])
    links.new(mottle.outputs['Fac'], tone_ramp.inputs['Fac'])
    veins = nodes.new('ShaderNodeTexVoronoi')  # Thin cell borders read as faint veins under the skin.
    veins.feature = 'DISTANCE_TO_EDGE'
    veins.inputs['Scale'].default_value = 9.0
    vein_mask = nodes.new('ShaderNodeMapRange')
    vein_mask.inputs['From Min'].default_value, vein_mask.inputs['From Max'].default_value = 0.0, 0.035
    vein_mask.inputs['To Min'].default_value, vein_mask.inputs['To Max'].default_value = 0.22, 0.0
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs[7].default_value = (0.35, 0.42, 0.62, 1)
    links.new(coords.outputs['Object'], veins.inputs['Vector'])
    links.new(veins.outputs['Distance'], vein_mask.inputs['Value'])
    links.new(vein_mask.outputs['Result'], mix.inputs['Factor'])
    links.new(tone_ramp.outputs['Color'], mix.inputs[6])
    links.new(mix.outputs[2], shader.inputs['Base Color'])
    pores = nodes.new('ShaderNodeTexVoronoi')
    pores.inputs['Scale'].default_value = 900.0
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.08
    links.new(coords.outputs['Object'], pores.inputs['Vector'])
    links.new(pores.outputs['Distance'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    return mat


def iris_material(colour):
    base = EYES.get(colour, EYES['brown'])
    mat = bpy.data.materials.new('Iris ' + colour)
    mat.use_nodes = True
    mat.diffuse_color = (*base, 1)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = 0.05
    coords = nodes.new('ShaderNodeTexCoord')
    streaks = nodes.new('ShaderNodeTexWave')  # Radial fibres of a real iris.
    streaks.wave_type = 'RINGS'
    streaks.inputs['Scale'].default_value = 80.0
    streaks.inputs['Distortion'].default_value = 12.0
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*(c * 0.45 for c in base), 1)
    ramp.color_ramp.elements[1].color = (*(min(1, c * 1.4) for c in base), 1)
    links.new(coords.outputs['Object'], streaks.inputs['Vector'])
    links.new(streaks.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], shader.inputs['Base Color'])
    return mat


def sclera_material():
    mat = bpy.data.materials.new('Sclera')
    mat.use_nodes = True
    mat.diffuse_color = (0.93, 0.91, 0.88, 1)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = 0.03  # A wet, glossy eye.
    coords = nodes.new('ShaderNodeTexCoord')
    vessels = nodes.new('ShaderNodeTexVoronoi')
    vessels.feature = 'DISTANCE_TO_EDGE'
    vessels.inputs['Scale'].default_value = 60.0
    red = nodes.new('ShaderNodeMapRange')
    red.inputs['From Min'].default_value, red.inputs['From Max'].default_value = 0.0, 0.02
    red.inputs['To Min'].default_value, red.inputs['To Max'].default_value = 0.35, 0.0
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs[6].default_value = (0.93, 0.91, 0.88, 1)
    mix.inputs[7].default_value = (0.75, 0.2, 0.18, 1)
    links.new(coords.outputs['Object'], vessels.inputs['Vector'])
    links.new(vessels.outputs['Distance'], red.inputs['Value'])
    links.new(red.outputs['Result'], mix.inputs['Factor'])
    links.new(mix.outputs[2], shader.inputs['Base Color'])
    return mat


def hair_material(colour):
    melanin, redness = HAIR_MELANIN.get(colour, HAIR_MELANIN['brown'])
    mat = bpy.data.materials.new('Hair ' + colour)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    output = nodes.get('Material Output')
    hair = nodes.new('ShaderNodeBsdfHairPrincipled')
    for key, value in (('Melanin', melanin), ('Melanin Redness', redness), ('Roughness', 0.3)):
        if key in hair.inputs:
            hair.inputs[key].default_value = value
    links.new(hair.outputs[0], output.inputs['Surface'])
    shade = (0.05 + 0.6 * (1 - melanin)) * (1 + 0.5 * redness)
    mat.diffuse_color = (min(1, shade * 1.1), shade * 0.85, shade * 0.6, 1)
    return mat


def region(obj, name, test):
    """A vertex group of the vertices (in object space) for which test(x, y, z) is true."""
    group = obj.vertex_groups.new(name=name)
    chosen = [v.index for v in obj.data.vertices if test(*v.co)]
    if chosen:
        group.add(chosen, 1.0, 'REPLACE')
    return len(chosen)


def hair_system(obj, name, group, count, length, children, material_index, segments=5):
    modifier = obj.modifiers.new(name, 'PARTICLE_SYSTEM')
    system = modifier.particle_system
    settings = system.settings
    settings.type = 'HAIR'
    settings.name = name
    settings.count = count
    settings.hair_length = length
    settings.hair_step = segments
    settings.emit_from = 'FACE'
    settings.use_advanced_hair = True
    settings.material = material_index
    settings.child_type = 'INTERPOLATED' if children else 'NONE'
    settings.child_percent = children  # Shown in the viewport.
    settings.rendered_child_count = children * 4
    settings.display_percentage = 100
    system.vertex_group_density = group
    return settings


def steps(main, parts, look, kind):
    """Live finishing steps; landmarks come from the eyes and the mesh bounds (object space)."""
    sclera = [o for o in parts if 'sclera' in o.name.lower() or o.name.lower().endswith(('.eye.l', '.eye.r'))]
    irises = [o for o in parts if 'iris' in o.name.lower()]
    inverse = main.matrix_world.inverted()
    eye_points = [inverse @ o.matrix_world.translation for o in sclera] or [main.location]
    eye_z = sum(p.z for p in eye_points) / len(eye_points)
    eye_x = max(abs(p.x) for p in eye_points) if eye_points else 0.03
    front = min(p.y for p in eye_points)
    zs = [v.co.z for v in main.data.vertices]
    ys = [v.co.y for v in main.data.vertices]
    top, bottom = max(zs), min(zs)
    depth_mid = (max(ys) + min(ys)) / 2
    is_body = kind.startswith('human_body')
    head_unit = 0.24 if is_body else (top - bottom)  # Head height in metres.
    crown_floor = eye_z + 0.12 * head_unit
    hairline_back = eye_z - 0.18 * head_unit

    def skin():
        main.data.materials.clear()
        main.data.materials.append(skin_material(look['skin']))
        for obj in sclera:
            obj.data.materials.clear()
            obj.data.materials.append(sclera_material())
        for obj in irises:
            obj.data.materials.clear()
            obj.data.materials.append(iris_material(look['eyes']))

    def scalp():
        main.data.materials.append(hair_material(look['hair']))
        index = len(main.data.materials)
        region(main, 'Scalp', lambda x, y, z: z > crown_floor or (z > hairline_back and y > depth_mid and z > eye_z - (
            0.5 if is_body else 0.3) * head_unit and z > top - 1.2 * head_unit))
        settings = hair_system(main, 'Scalp hair', 'Scalp', 2500, 0.004, 20, index)
        look['_scalp'] = settings

    def grow():
        target = {'short': 0.03, 'medium': 0.09, 'long': 0.2}[look['hair_length']]
        settings = look['_scalp']
        settings.hair_length = min(target, settings.hair_length + target / 3)  # The hair grows on screen.
        return settings.hair_length < target

    def brows():
        index = len(main.data.materials)
        region(main, 'Brows', lambda x, y, z: eye_z + 0.03 * head_unit < z < eye_z + 0.075 * head_unit and
               0.25 * eye_x < abs(x) < 1.9 * eye_x and y < front + 0.03)
        hair_system(main, 'Eyebrows', 'Brows', 600, 0.008, 4, index, segments=3)
        region(main, 'Lashes', lambda x, y, z: abs(z - eye_z) < 0.03 * head_unit and 0.4 * eye_x < abs(x) < 1.6 * eye_x
               and y < front + 0.012)
        hair_system(main, 'Eyelashes', 'Lashes', 300, 0.007, 0, index, segments=3)

    def beard():
        if look.get('beard') == 'none':
            return
        index = len(main.data.materials)
        chin = bottom if not is_body else eye_z - 0.75 * head_unit
        region(main, 'Beard', lambda x, y, z: chin < z < eye_z - 0.32 * head_unit and y < depth_mid and
               abs(x) < 2.6 * eye_x)
        hair_system(main, 'Beard', 'Beard', 1500, 0.004 if look['beard'] == 'stubble' else 0.018, 6, index, segments=4)

    def body_hair():
        if not is_body:
            return
        index = len(main.data.materials)
        region(main, 'Body', lambda x, y, z: z < eye_z - 0.9 * head_unit)
        hair_system(main, 'Body hair', 'Body', 4000, 0.006, 4, index, segments=3)

    return [skin, scalp, grow, grow, grow, brows, beard, body_hair]
