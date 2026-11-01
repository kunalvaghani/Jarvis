"""Live Blender modelling (control.api_routes): clear requests parse; the geometry verifier rejects wrong shapes."""
import math
from unittest.mock import Mock

import pytest

from jarvis.blender_live import expected_dims, live_request
from jarvis.learning.verifiers.blender_scene import head_problems, shape_problems

TEST = 'in my Jarvis test folder'


def sphere_points(r, n=20):
    return [[round(r * math.sin(a) * math.cos(b), 4), round(r * math.sin(a) * math.sin(b), 4), round(r * math.cos(a), 4)]
            for a in [math.pi * i / n for i in range(n + 1)] for b in [2 * math.pi * j / n for j in range(n)]]


CUBE = [[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]


def row(points, dims):
    return {'verts': len(points), 'points': points, 'dims': dims}


def test_requests_parse_to_live_operations():
    head = live_request(f'Open Blender and model a human head with eyes, and save it as head.blend {TEST}.')
    assert head['operation'] == 'head' and head['file'] == 'head.blend'
    sphere = live_request(f'Open Blender and turn the default cube into a sphere with radius 1.5 metres, name it S, '
                          f'and save it as s.blend {TEST}.')
    assert sphere['shape'] == {'type': 'sphere', 'radius': 1.5} and expected_dims(sphere) == [3.0, 3.0, 3.0]
    assert live_request(f'Open Blender, add a cube 20 cm on each side, name it X, save as x.blend {TEST}') is None
    assert live_request('Open Blender and add a sphere') is None  # No name, file or folder.


def test_a_real_sphere_passes_and_the_cube_does_not():
    assert shape_problems(row(sphere_points(1.5), [3, 3, 3]), {'type': 'sphere', 'radius': 1.5}, .02) == []
    assert 'cube' in shape_problems(row(CUBE, [2, 2, 2]), {'type': 'sphere', 'radius': 1.0}, .02)[0]
    squashed = [[x, y, z * .5] for x, y, z in sphere_points(1.0)]
    assert shape_problems(row(squashed, [2, 2, 1]), {'type': 'sphere', 'radius': 1.0}, .02)


def test_cone_and_cylinder_shapes_are_measured():
    cone = [[round(r * math.cos(b), 4), round(r * math.sin(b), 4), z]
            for z in (-1.5, -0.5, 0.5, 1.5) for r in [1.0 * (1.5 - z) / 3] for b in [2 * math.pi * j / 16 for j in range(16)]]
    assert shape_problems(row(cone, [2, 2, 3]), {'type': 'cone', 'radius': 1.0, 'depth': 3.0}, .02) == []
    cylinder = [[round(math.cos(b), 4), round(math.sin(b), 4), z] for z in (-1.5, 1.5)
                for b in [2 * math.pi * j / 16 for j in range(16)]]
    assert shape_problems(row(cylinder, [2, 2, 3]), {'type': 'cone', 'radius': 1.0, 'depth': 3.0}, .02)  # Not a cone.
    assert shape_problems(row(cylinder, [2, 2, 3]), {'type': 'cylinder', 'radius': 1.0, 'depth': 3.0}, .02) == []


def face(**moves):
    parts = {'Head': (0, 0, 0), 'Ear.L': (-1, 0, 0), 'Ear.R': (1, 0, 0), 'Eye.L': (-.38, -.92, .3),
             'Eye.R': (.38, -.92, .3), 'Pupil.L': (-.38, -1.1, .3), 'Pupil.R': (.38, -1.1, .3), 'Nose': (0, -1.2, -.05),
             'Mouth': (0, -.98, -.5), **moves}
    colours = {'Eye.L': [.95, .95, .95, 1], 'Pupil.L': [.05, .05, .08, 1]}
    return {name: {'verts': 500 if name == 'Head' else 50, 'loc': list(loc), 'dims': [2, 2.2, 2.6],
                   'colour': colours.get(name, [.8, .6, .5, 1])} for name, loc in parts.items()}


def test_a_proper_face_passes_and_misplaced_features_fail():
    assert head_problems(face()) == []
    assert 'mirrored' in head_problems(face(**{'Eye.R': (.38, -.92, .6)}))[0]
    assert any('Pupil.L' in p for p in head_problems(face(**{'Pupil.L': (-.38, -.7, .3)})))
    assert any('order' in p for p in head_problems(face(Nose=(0, -1.2, .6))))
    broken = face()
    del broken['Mouth']
    assert 'missing' in head_problems(broken)[0]


def test_the_route_prefers_the_live_blender_window(monkeypatch):
    from jarvis import fast_routes
    seen = []
    monkeypatch.setattr('jarvis.blender_live.run', lambda actions, request, cancelled: seen.append(request) or 'live')
    actions = Mock(config={'control': {'api_routes': True}})
    goal = f'Open Blender, add a cone with radius 1 metre and depth 3 metres, name it C, and save it as c.blend {TEST}.'
    assert fast_routes.run(actions, goal, lambda: False) == 'live' and seen[0]['shape']['type'] == 'cone'
