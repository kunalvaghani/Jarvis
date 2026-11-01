"""Blender scene geometry: headless Blender opens the .blend and measures shapes and a face's layout.

Two checks, both from the saved geometry, never from Jarvis's own report:
- ``shape``: the named mesh really is that shape. Sphere: every vertex at the radius from the object's centre.
  Cylinder: no vertex outside the radius or the depth, and the widest ring at the radius. Cone: no vertex
  outside the cone's radius at its height, the base at the full radius, the apex closed. Plus the dimensions.
- ``head``: parts named Head, Ear.L/R, Eye.L/R, Pupil.L/R, Nose, Mouth; the eyes mirrored at one height on the
  front of the head, each pupil in front of its eye, eyes above the nose above the mouth, ears at the sides,
  the head a rounded mesh (not the 8-vertex cube), eyes light and pupils dark.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional

from .base import Verdict, Verifier, judged, unverifiable

BLENDER = Path(r'D:\blender.exe')
SCRIPT = r'''
import bpy, json, math
rows = {}
graph = bpy.context.evaluated_depsgraph_get()
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    world = [o.matrix_world @ v.co for v in o.data.vertices]
    centre = o.matrix_world.translation
    evaluated = o.evaluated_get(graph).to_mesh()
    box = [o.matrix_world @ v.co for v in evaluated.vertices]
    count = len(evaluated.vertices)
    o.evaluated_get(graph).to_mesh_clear()
    colour = list(o.data.materials[0].diffuse_color) if o.data.materials and o.data.materials[0] else None
    rows[o.name] = {"verts": len(world), "evaluated": count, "loc": [round(v, 4) for v in centre],
                    "dims": [round(v, 4) for v in o.dimensions], "modifiers": [m.type for m in o.modifiers],
                    "min": [round(min(p[i] for p in box), 4) for i in range(3)] if box else [0, 0, 0],
                    "max": [round(max(p[i] for p in box), 4) for i in range(3)] if box else [0, 0, 0],
                    "points": [[round(p.x - centre.x, 4), round(p.y - centre.y, 4), round(p.z - centre.z, 4)]
                               for p in world] if len(world) <= 20000 else [],
                    "hair": [{"name": s.settings.name, "count": s.settings.count, "length": round(s.settings.hair_length, 4)}
                             for s in o.particle_systems if s.settings.type == "HAIR"],
                    "materials": [m.name for m in o.data.materials if m],
                    "colour": colour, "nodes": sorted({n.type for n in o.data.materials[0].node_tree.nodes})
                    if o.data.materials and o.data.materials[0] and o.data.materials[0].node_tree else [],
                    "transmission": next((float(n.inputs[k].default_value) for n in (o.data.materials[0].node_tree.nodes
                    if o.data.materials and o.data.materials[0] and o.data.materials[0].node_tree else [])
                    if n.type == "BSDF_PRINCIPLED" for k in ("Transmission Weight", "Transmission") if k in n.inputs), 0.0)}
print("SCENE" + json.dumps(rows))
'''
Run = Callable[..., Any]
HEAD_PARTS = ('Head', 'Ear.L', 'Ear.R', 'Eye.L', 'Eye.R', 'Pupil.L', 'Pupil.R', 'Nose', 'Mouth')


def scene(path: Path, blender: Path, run: Run = subprocess.run, timeout: float = 180) -> Optional[Dict[str, Any]]:
    with tempfile.TemporaryDirectory() as folder:
        script = Path(folder) / 'scene.py'
        script.write_text(SCRIPT, encoding='utf-8')
        out = run([str(blender), '-b', str(path), '--python', str(script)], capture_output=True, text=True,
                  timeout=timeout)
    match = re.search(r'SCENE(\{.*\})', str(getattr(out, 'stdout', '') or ''))
    rows = json.loads(match.group(1)) if match else None
    return rows if isinstance(rows, dict) else None


def shape_problems(row: Dict[str, Any], shape: Dict[str, Any], tolerance: float) -> List[str]:
    kind, points = shape['type'], row['points']
    radial = [(x * x + y * y) ** .5 for x, y, _ in points]
    problems: List[str] = []
    if row['verts'] <= 8:
        return [f'still the 8-vertex cube, not a {kind}']
    if kind == 'sphere':
        r = shape['radius']
        worst = max(abs((x * x + y * y + z * z) ** .5 - r) for x, y, z in points)
        if worst > tolerance * r:
            problems.append(f'not a sphere: a vertex is {worst:.3f} m off the {r} m radius')
        dims = [2 * r] * 3
    elif kind in ('cylinder', 'cone'):
        r, d = shape['radius'], shape['depth']
        for (x, y, z), flat in zip(points, radial):
            allowed = r * ((d / 2 - z) / d if kind == 'cone' else 1)
            if flat > allowed + tolerance * r or abs(z) > d / 2 + tolerance * d:
                problems.append(f'not a {kind}: vertex ({x}, {y}, {z}) is outside the shape')
                break
        if abs(max(radial) - r) > tolerance * r:
            problems.append(f'widest ring is {max(radial):.3f} m, expected the radius {r} m')
        if kind == 'cone':
            top = [flat for (_, _, z), flat in zip(points, radial) if z > d / 2 - tolerance * d]
            if top and max(top) > tolerance * r:
                problems.append('the cone has no point at its top')
        dims = [2 * r, 2 * r, d]
    else:
        dims = [shape['side']] * 3
        half = shape['side'] / 2
        if any(max(abs(c) for c in p) < half - tolerance * half for p in points):
            problems.append('not a cube: a vertex lies inside the faces')
    if any(abs(a - b) > tolerance * max(b, 1) for a, b in zip(row['dims'], dims)):
        problems.append(f'size wrong: dims {row["dims"]}, expected {dims}')
    return problems


def head_problems(rows: Dict[str, Any]) -> List[str]:
    missing = [name for name in HEAD_PARTS if name not in rows]
    if missing:
        return ['missing parts: ' + ', '.join(missing)]
    loc = {name: rows[name]['loc'] for name in HEAD_PARTS}
    problems: List[str] = []
    head = rows['Head']
    if head['verts'] <= 8 or not all(1.5 <= d <= 3.2 for d in head['dims']):
        problems.append(f'the head is not a rounded head shape (verts {head["verts"]}, dims {head["dims"]})')
    left, right = loc['Eye.L'], loc['Eye.R']
    if abs(left[0] + right[0]) > .05 or abs(left[2] - right[2]) > .05 or abs(left[1] - right[1]) > .05:
        problems.append(f'the eyes are not mirrored at one height ({left}, {right})')
    if not (left[0] < 0 < right[0]) or min(left[1], right[1]) > -0.5:
        problems.append('the eyes are not on the front of the face, one each side')
    for side in ('L', 'R'):
        eye, pupil = loc[f'Eye.{side}'], loc[f'Pupil.{side}']
        if not pupil[1] < eye[1] or abs(pupil[0] - eye[0]) > .1 or abs(pupil[2] - eye[2]) > .1:
            problems.append(f'Pupil.{side} is not in front of Eye.{side}')
    if not left[2] > loc['Nose'][2] > loc['Mouth'][2]:
        problems.append('the order eyes, nose, mouth from top to bottom is wrong')
    if not (loc['Ear.L'][0] < -0.8 and loc['Ear.R'][0] > 0.8):
        problems.append('the ears are not at the sides of the head')
    def brightness(name: str) -> float:
        return float(sum((rows[name]['colour'] or [0, 0, 0])[:3])) / 3
    if not (brightness('Eye.L') > 0.7 and brightness('Pupil.L') < 0.2):
        problems.append('the eyes are not light with dark pupils')
    return problems


def centre(row: Dict[str, Any]) -> List[float]:
    return [(a + b) / 2 for a, b in zip(row['min'], row['max'])]


def human_problems(rows: Dict[str, Any], main: str, min_vertices: int = 100_000) -> List[str]:
    """A realistic head or body: high poly, skin detail, two mirrored eyes on the front and upper part."""
    if main not in rows:
        return [f'no {main} mesh']
    body = rows[main]
    problems: List[str] = []
    if body['evaluated'] < min_vertices:
        problems.append(f'{main} is not high poly: {body["evaluated"]} vertices, expected at least {min_vertices}')
    if 'DISPLACE' not in body['modifiers']:
        problems.append(f'{main} has no fine skin detail (displacement)')
    eyes = sorted((name for name in rows if re.search(r'\.(?:sclera|eye)\.[LR]$', name)), key=lambda n: rows[n]['loc'][0])
    if len(eyes) != 2:
        return problems + [f'expected two eyes, found {eyes}']
    middle = centre(body)
    left, right = (centre(rows[name]) for name in eyes)
    height = body['max'][2] - body['min'][2]
    if abs((left[0] + right[0]) / 2 - middle[0]) > 0.02 * height or abs(left[2] - right[2]) > 0.01 * height:
        problems.append('the eyes are not mirrored at one height')
    if min(left[1], right[1]) > middle[1]:
        problems.append('the eyes are not on the front')
    if min(left[2], right[2]) < middle[2]:
        problems.append('the eyes are not in the upper part')
    skin = body['colour'] or [0, 0, 0]
    # Any real skin tone, light to dark, is warm (red >= green >= blue); brightness is not a test.
    if not (skin[0] >= skin[1] >= skin[2] and skin[0] > 0.1 and skin[0] - skin[2] > 0.08):
        problems.append('the skin material is missing')
    if body.get('materials'):
        names = ' '.join(body['materials']).lower()
        if 'skin' in names and not {'TEX_VORONOI', 'TEX_NOISE'} & set(body.get('nodes', [])):
            problems.append('the skin has no surface texture (pores, tone variation)')
    hair = {h['name']: h for h in body.get('hair', [])}  # Realistic humans always need strands (2026-11-01).
    scalp = hair.get('Scalp hair')
    if scalp is None or scalp['count'] < 1000 or scalp['length'] < 0.02:
        problems.append('the scalp hair is missing or was not grown')
    for needed in ('Eyebrows', 'Eyelashes'):
        if needed not in hair:
            problems.append(f'no {needed.lower()}')
    irises = [rows[n] for n in rows if '.iris.' in n]
    if irises and not all({'TEX_WAVE', 'TEX_NOISE', 'TEX_VORONOI'} & set(i.get('nodes', [])) for i in irises):
        problems.append('the irises have no pattern')
    return problems


def car_problems(rows: Dict[str, Any], min_vertices: int = 50_000) -> List[str]:
    wheels = {tag: rows.get(f'Car.Wheel.{tag}') for tag in ('FL', 'FR', 'RL', 'RR')}
    if 'Car.Body' not in rows or any(w is None for w in wheels.values()):
        return ['the body or a wheel is missing']
    body = rows['Car.Body']
    problems: List[str] = []
    if body['evaluated'] < min_vertices:
        problems.append(f'the body is not high poly: {body["evaluated"]} vertices')
    c = {tag: centre(w) for tag, w in wheels.items() if w}
    if abs(c['FL'][0] - c['FR'][0]) > .02 or abs(c['RL'][0] - c['RR'][0]) > .02 or c['FL'][0] <= c['RL'][0]:
        problems.append('the wheels are not in a front pair and a rear pair')
    if abs(c['FL'][1] + c['FR'][1]) > .02 or abs(c['RL'][1] + c['RR'][1]) > .02:
        problems.append('the wheels are not mirrored left and right')
    if any(abs(w['min'][2]) > .03 for w in wheels.values() if w):
        problems.append('a wheel does not touch the ground')
    if body['min'][2] < .1:
        problems.append('the body touches the ground')
    if not (body['min'][0] < c['RL'][0] and c['FL'][0] < body['max'][0]):
        problems.append('the wheels are outside the body')
    glass = rows.get('Car.Glass')
    if glass is None or centre(glass)[2] < centre(body)[2]:
        problems.append('the windows are missing or below the belt line')
    return problems


TEXTURES = {'TEX_BRICK', 'TEX_WAVE', 'TEX_VORONOI', 'TEX_NOISE'}


def house_problems(rows: Dict[str, Any]) -> List[str]:
    """A planned house: walls with cut openings on every floor, glazed windows in them, a front door at ground level,
    a roof on top, a floor per storey with stairs between, furniture on the floors, textured materials."""
    walls = {name: row for name, row in rows.items() if re.fullmatch(r'House\.Wall\.F\d+\.(?:front|back|left|right)', name)}
    floors = sorted({int(name.split('.')[2][1:]) for name in walls})
    if not walls or floors != list(range(len(floors))) or len(walls) != 4 * len(floors):
        return [f'the exterior walls are incomplete ({sorted(walls)})']
    problems: List[str] = []
    for name, wall in walls.items():
        if 'BOOLEAN' not in wall['modifiers'] or wall['evaluated'] <= 8:
            problems.append(f'{name} has no openings cut into it')
    low = min(w['min'][2] for w in walls.values())
    top = max(w['max'][2] for w in walls.values())
    x0, x1 = min(w['min'][0] for w in walls.values()), max(w['max'][0] for w in walls.values())
    y0, y1 = min(w['min'][1] for w in walls.values()), max(w['max'][1] for w in walls.values())
    windows = [rows[n] for n in rows if re.fullmatch(r'House\.Window\.\d+', n)]
    framed = [w for w in windows if (abs(centre(w)[1] - y0) < .4 or abs(centre(w)[1] - y1) < .4 or
                                     abs(centre(w)[0] - x0) < .4 or abs(centre(w)[0] - x1) < .4) and low < centre(w)[2] < top]
    if len(framed) < 4:
        problems.append(f'only {len(framed)} glazed windows sit in the walls')
    if windows and max(w['transmission'] for w in windows) < .5:
        problems.append('the window glass is not transparent')
    door = rows.get('House.Door')
    if door is None or abs(door['min'][2] - low) > .15 or abs(centre(door)[1] - y0) > .4:
        problems.append('no front door at ground level')
    roof = rows.get('House.Roof')
    if roof is None or roof['min'][2] < top - .3 or roof['max'][2] < top + .2:
        problems.append('the roof does not sit on top of the walls')
    if any(f'House.Floor.{f}' not in rows for f in floors):
        problems.append('a storey has no floor')
    stairs = [n for n in rows if n.startswith('House.Stairs.')]
    if len(stairs) < len(floors) - 1:
        problems.append('stairs are missing between storeys')
    levels = [rows[f'House.Floor.{f}']['max'][2] for f in floors if f'House.Floor.{f}' in rows]
    furniture = [rows[n] for n in rows if n.startswith('Furniture.')]
    if len(furniture) < 2 * len(floors):
        problems.append(f'only {len(furniture)} pieces of furniture')
    for item in furniture:
        if not (x0 - .05 <= item['min'][0] and item['max'][0] <= x1 + .05 and y0 - .05 <= item['min'][1] and
                item['max'][1] <= y1 + .05):
            problems.append('furniture stands outside the house')
            break
        if not any(abs(item['min'][2] - level) < .12 for level in levels):
            problems.append('furniture is not standing on a floor')
            break
    textured = [w for w in walls.values() if TEXTURES & set(w.get('nodes', []))]
    if len(textured) != len(walls):
        problems.append('the walls have no procedural texture')
    return problems


class BlenderScene(Verifier):
    NAME = 'blender_scene'
    READS = frozenset({'file', 'process'})

    def check(self, *, path: str | Path, shape: Optional[Dict[str, Any]] = None, name: str = '', head: bool = False,
              model: str = '', tolerance: float = 0.02, blender: str | Path = BLENDER, run: Run = subprocess.run,
              **_: Any) -> Verdict:
        target, executable = Path(path), Path(blender)
        evidence: Dict[str, Any] = {'path': str(target)}
        if not target.is_file():
            return judged([f'{target} was not saved'], evidence)
        if not executable.is_file():
            return unverifiable(f'Blender is not available at {executable}', evidence)
        try:
            rows = scene(target, executable, run)
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            return unverifiable(f'headless Blender failed: {type(error).__name__}', evidence)
        if rows is None:
            return unverifiable('headless Blender could not read the file', evidence)
        evidence['objects'] = sorted(rows)
        if model in ('Head', 'Body'):
            evidence['vertices'] = rows.get(model, {}).get('evaluated')
            return judged(human_problems(rows, model), evidence)
        if model == 'car':
            evidence['vertices'] = rows.get('Car.Body', {}).get('evaluated')
            return judged(car_problems(rows), evidence)
        if model == 'house':
            return judged(house_problems(rows), evidence)
        if head:
            return judged(head_problems(rows), evidence)
        if name not in rows or shape is None:
            return judged([f'no mesh named {name}'], evidence)
        return judged(shape_problems(rows[name], shape, tolerance), evidence)


def check(**params: Any) -> Verdict:
    return BlenderScene().check(**params)
