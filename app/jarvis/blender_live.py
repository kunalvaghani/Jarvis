"""Live Blender modelling in a visible window (flag control.api_routes, default off).

User request 2026-11-01: Blender should not just open a saved project; the user wants to watch the default cube
being transformed (into a sphere, cylinder, cone or resized cube) and, as the hardest case, a human head with
proper eyes, built live. This module turns a clear request into one fixed template run
(`templates/blender_live.py`, no model-written code), then checks the saved file in a separate background
Blender process before reporting success:

1. parse the request (shape and sizes, or "human head"; object name, .blend name, folder) or return None;
2. refuse an existing target; ask for approval like every Blender write;
3. write a factory-default start scene (background, ~2 s) and open it in a VISIBLE Blender with the template
   (opening a file skips the splash screen that would cover the cube);
4. wait for the template's result, then read the saved .blend back independently.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional

TEMPLATE = Path(__file__).resolve().parent / 'templates' / 'blender_live.py'
NUMBER = r'(\d+(?:\.\d+)?)'
UNIT = r'\s*(?:m\b|metres?\b|meters?\b)?'
SHAPES = ('sphere', 'cylinder', 'cone', 'cube')
HEAD = re.compile(r'\b(?:human|person\'?s?|man\'?s?|woman\'?s?)?\s*(?:head|face)\b', re.I)
HEAD_PARTS = ['Head', 'Ear.L', 'Ear.R', 'Eye.L', 'Eye.R', 'Pupil.L', 'Pupil.R', 'Nose', 'Mouth']
WAIT_SECONDS = 300.0
# Blender Studio "Human Base Meshes" v1.4.1 (CC0), downloaded with the user's approval on 2026-11-01.
HUMAN_ASSET = Path('.jarvis-runtime') / 'assets' / 'human-base-meshes' / 'human_base_meshes_bundle.blend'
PAINT_WORDS = ('red', 'silver', 'blue', 'yellow', 'black')
# The parts each operation must leave in the saved file (checked by an independent background Blender).
EXPECTED = {
    'human_head': ['Head', 'GEO-head_sculpting_realistic.sclera.L', 'GEO-head_sculpting_realistic.sclera.R',
                   'GEO-head_sculpting_realistic.iris.L', 'GEO-head_sculpting_realistic.iris.R'],
    'human_body_male': ['Body', 'GEO-body_male_realistic.eye.L', 'GEO-body_male_realistic.eye.R'],
    'human_body_female': ['Body', 'GEO-body_female_realistic.eye.L', 'GEO-body_female_realistic.eye.R'],
    'car': ['Car.Body', 'Car.Wheel.FL', 'Car.Wheel.FR', 'Car.Wheel.RL', 'Car.Wheel.RR', 'Car.Glass'],
    'house': ['House.Foundation', 'House.Wall.F0.front', 'House.Roof', 'House.Door', 'House.Window.1',
              'House.Floor.0'],
}


SKINS = ('light', 'fair', 'medium', 'olive', 'brown', 'dark')
HAIRS = ('black', 'dark brown', 'brown', 'blonde', 'red', 'grey')
EYE_COLOURS = ('blue', 'green', 'hazel', 'brown', 'grey')


def look_of(goal: str, operation: str, rng: Any = None) -> Dict[str, str]:
    """Skin tone, hair colour and length, eye colour and beard: from the request's words, otherwise varied."""
    import random
    rng = rng or random.Random()

    def named(options: 'tuple[str, ...]', after: str = '') -> Optional[str]:
        for option in sorted(options, key=len, reverse=True):
            if re.search(r'\b' + option + r'\b' + after, goal, re.I):
                return option
        return None
    female = operation.endswith('female')
    beard = 'none' if female or re.search(r'\b(?:no beard|clean[- ]shaven)\b', goal, re.I) else (
        'stubble' if re.search(r'\bstubble\b', goal, re.I) else 'full' if re.search(r'\bbeard\b', goal, re.I)
        else rng.choice(['none', 'stubble', 'full']))
    return {'skin': named(SKINS, r'(?:[- ]skin(?:ned)?)') or rng.choice(SKINS),
            'hair': named(HAIRS, r'\s+hair') or rng.choice(HAIRS),
            'hair_length': named(('short', 'medium', 'long'), r'\s+(?:\w+\s+)?hair') or rng.choice(['short', 'medium', 'long']),
            'eyes': named(EYE_COLOURS, r'\s+eyes?') or rng.choice(EYE_COLOURS), 'beard': beard}


def style_of(goal: str, file: str) -> int:
    for index, word in enumerate(PAINT_WORDS):
        if re.search(r'\b' + word + r'\b', goal, re.I):
            return index
    return sum(file.encode()) % 6  # Stable per file name, different across the test variants.


def _value(pattern: str, goal: str) -> Optional[float]:
    found = re.search(pattern, goal, re.I)
    return float(next(g for g in found.groups() if g)) if found else None


def live_request(goal: str) -> Optional[Dict[str, Any]]:
    """{operation, shape|None, name, file, folder} for a clear live-modelling request, else None."""
    if not re.search(r'\bblender\b', goal, re.I) or re.search(r'\d\s*(?:cm|mm|km|inch|inches|feet|foot|ft)\b', goal, re.I):
        return None
    files = set(re.findall(r'\b([\w.()-]+\.blend)\b', goal, re.I))
    folder = re.search(r'\.blend\s+(?:in|into|to)\s+(?:my\s+|the\s+)?([\w -]{1,60}?folder)\b', goal, re.I)
    if len(files) != 1 or not folder:
        return None
    base = {'file': files.pop(), 'folder': folder.group(1).strip()}
    building = re.search(r'\b(?:model|make|create|build|sculpt|turn|design)\b', goal, re.I)
    if building and re.search(r'\b(?:body|figure)\b', goal, re.I) and re.search(
            r'\b(?:human|person|man|woman|male|female)\b', goal, re.I):
        sex = 'female' if re.search(r'\b(?:woman|female|girl|lady)\b', goal, re.I) else 'male'
        return {**base, 'operation': 'human_body_' + sex, 'shape': None, 'name': 'Body', 'goal': goal}
    if building and re.search(r'\b(?:head|face)\b', goal, re.I) and HEAD.search(goal):
        realistic = re.search(r'\b(?:realistic|real|high[- ]?poly|lifelike|photo)', goal, re.I)
        return {**base, 'operation': 'human_head' if realistic else 'head', 'shape': None, 'name': 'Head', 'goal': goal}
    if building and re.search(r'\b(?:car|sports car|coupe|vehicle)\b', goal, re.I):
        return {**base, 'operation': 'car', 'shape': None, 'name': 'Car.Body', 'style': style_of(goal, base['file'])}
    if building and re.search(r'\b(?:house|home|cottage|villa)\b', goal, re.I):
        return {**base, 'operation': 'house', 'shape': None, 'name': 'House.Walls', 'style': style_of(goal, base['file']),
                'goal': goal}
    shapes = [s for s in SHAPES if re.search(r'\b' + s + r's?\b', goal, re.I) and not (
        s == 'cube' and re.search(r'\b(?:default|base|starting)\s+cube\b', goal, re.I))]
    named = re.search(r'\b(?:name|call)\s+it\s+["\']?([A-Za-z0-9_][A-Za-z0-9_.-]{0,62})', goal, re.I)
    if len(shapes) != 1 or not named or not re.search(r'\b(?:add|create|make|turn|transform|morph|change)\b', goal, re.I):
        return None
    kind = shapes[0]
    radius = _value(r'\bradius\s+(?:of\s+)?' + NUMBER + UNIT, goal)
    depth = _value(r'\b(?:depth|height)\s+(?:of\s+)?' + NUMBER + UNIT + r'|' + NUMBER + UNIT + r'\s+(?:deep|tall|high)\b',
                   goal)
    side = _value(NUMBER + UNIT + r'\s+on\s+each\s+side|\bside(?:\s+length)?\s+(?:of\s+)?' + NUMBER + UNIT, goal)
    shape: Dict[str, Any] = {'type': kind}
    if kind == 'sphere' and depth is None and side is None:
        shape['radius'] = radius or 1.0
    elif kind in ('cylinder', 'cone') and side is None:
        shape.update(radius=radius or 1.0, depth=depth or 2.0)
    elif kind == 'cube' and radius is None and depth is None:
        shape['side'] = side or 2.0
    else:
        return None
    return {**base, 'operation': 'morph', 'shape': shape, 'name': named.group(1).rstrip('.,')}


def offline_safe(actions: Any, research: Callable[[], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Photo research when the internet works; otherwise the build goes on from the built-in style notes
    (a live gate lost its connection mid-run on 2026-11-02 and two builds failed outright)."""
    try:
        return research()
    except OSError as error:
        actions.report('warning', 'Reference photos unavailable (' + str(error)[:80] + '); building from the built-in notes.')
        return []


def expected_dims(request: Dict[str, Any]) -> List[float]:
    shape = request['shape']
    if shape['type'] == 'sphere':
        return [2 * shape['radius']] * 3
    if shape['type'] in ('cylinder', 'cone'):
        return [2 * shape['radius'], 2 * shape['radius'], shape['depth']]
    return [shape['side']] * 3


def run(actions: Any, request: Dict[str, Any], cancelled: Callable[[], bool]) -> str:
    from .app_adapters import _approve, _blender, blender_executable, scoped_path
    folder = Path(actions._task_folder(request['folder'], cancelled)).resolve(strict=True)
    target = scoped_path(folder, request['file'])
    if target.suffix.casefold() != '.blend':
        raise ValueError('Name a .blend file.')
    if target.exists():
        raise ValueError(f'{target.name} already exists; existing scenes are never overwritten.')
    operation = request['operation']
    summary = {'head': 'a human head', 'human_head': 'a realistic high-poly human head',
               'human_body_male': 'a realistic high-poly male body', 'human_body_female': 'a realistic high-poly female body',
               'car': 'an original high-poly sports car', 'house': 'a detailed house'}.get(operation) or (
        f"{request['shape']['type']} {request['name']} from the default cube")
    asset = (Path(actions.base) / HUMAN_ASSET).resolve()
    if operation.startswith('human_') and not asset.is_file():
        raise ValueError('The realistic human meshes are not downloaded (' + str(HUMAN_ASSET) + ').')
    _approve(actions, 'blender_task', {'file': target.name, 'live': summary}, cancelled)
    executable = blender_executable(actions)
    actions.report('tool', f'control: app_open Blender (live: {summary})')
    work = Path(tempfile.mkdtemp(prefix='jarvis-blender-live-'))
    start, request_file, result_file = work / 'start.blend', work / 'request.json', work / 'result.json'
    subprocess.run([str(executable), '--background', '--factory-startup', '--python-expr',
                    'import bpy, sys; bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])', '--', str(start)],
                   capture_output=True, timeout=120, check=False)
    if not start.is_file():
        raise ValueError('Blender could not prepare the default scene.')
    payload = {'operation': operation, 'output': str(target), 'name': request['name'], 'shape': request['shape'],
               'seconds': 3.0, 'style': request.get('style', 0), 'asset': str(asset)}
    from . import flags
    research = flags.enabled(getattr(actions, 'config', None), 'learning', 'cloud_research')
    if operation.startswith('human_'):
        goal = request.get('goal', '')
        payload['look'] = look_of(goal, operation)
        if research:
            # Reference photos first: what they show replaces the random choices, never what the user named.
            import random
            from .reference_images import look_from_photos, study
            subject = 'woman' if operation.endswith('female') else 'man'
            studied = offline_safe(actions, lambda: study(actions, f'portrait photograph of a {subject} face', 'person', cancelled))
            seen = look_from_photos([s['reading'] for s in studied])
            named = {k for k, v in look_of(goal, operation, random.Random(1)).items()
                     if look_of(goal, operation, random.Random(2))[k] == v and look_of(goal, operation, random.Random(3))[k] == v}
            payload['look'].update({k: v for k, v in seen.items() if k not in named})
            payload['references'] = [{'title': s['title'], 'licence': s['licence']} for s in studied]
        look = payload['look']
        actions.report('brain', f"Look: {look['skin']} skin, {look['hair_length']} {look['hair']} hair, {look['eyes']} eyes"
                                + ('' if look['beard'] == 'none' else f", {look['beard']} beard"))
    if operation == 'house':
        # Reference first, then Jarvis's own plan; a different style each run unless the user named one.
        from .reference_research import ARTICLES, house_plan, validated
        client = getattr(getattr(actions, 'brain', None), 'client', None)
        plan = house_plan(request.get('goal', ''), getattr(client, 'request', None), cancelled, research)
        if research:
            # Then real photos of that style: what they show (floors, roof, materials, colours) shapes the plan.
            from .reference_images import house_from_photos, study
            studied = offline_safe(actions, lambda: study(actions, ARTICLES[plan['style']].replace(' architecture', '') +
                                                          ' house exterior', 'house', cancelled))
            photo_plan = house_from_photos([s['reading'] for s in studied])
            merged = json.loads(json.dumps(plan))
            for key, value in photo_plan.items():
                if isinstance(value, dict):
                    merged.setdefault(key, {}).update(value)
                else:
                    merged[key] = value
            plan = {**validated(merged, plan), 'references': plan.get('references', []),
                    'photos': [{'title': s['title'], 'licence': s['licence']} for s in studied]}
        payload['plan'] = plan
        reference = ARTICLES[plan['style']] + (' (Wikipedia)' if plan.get('references') else ' (built-in notes)') + (
            f" and {len(plan['photos'])} photos" if plan.get('photos') else '')
        actions.report('brain', f"House plan from {reference}: {plan['style'].replace('_', ' ')}, {plan['floors']} "
                                f"floor(s), {plan['roof']['type']} {plan['roof']['material']} roof, "
                                f"{plan['walls']['material']} walls {plan['walls']['colour']}, {len(plan['rooms'])} rooms")
    request_file.write_text(json.dumps(payload), encoding='utf-8')
    # A visible window the user keeps; Jarvis does not own or close it.
    subprocess.Popen([str(executable), '--factory-startup', str(start), '--python', str(TEMPLATE), '--',
                      str(request_file), str(result_file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + WAIT_SECONDS
    while not result_file.is_file():
        if cancelled():
            raise ValueError('Cancelled while Blender was modelling; check the open Blender window.')
        if time.monotonic() > deadline:
            raise ValueError('Blender did not finish the live modelling in time; check the open Blender window.')
        time.sleep(.25)
    time.sleep(.2)
    result = json.loads(result_file.read_text(encoding='utf-8'))
    if result.get('ok') is not True:
        raise ValueError('Blender refused the live modelling: ' + str(result.get('error'))[:300])
    # Independent readback in a fresh background process, scripts disabled.
    observed = _blender(actions, {'operation': 'inspect', 'path': str(target)}, cancelled)
    found = {row['name']: row for row in observed['objects']}
    wanted = HEAD_PARTS if operation == 'head' else EXPECTED.get(operation, [request['name']])
    missing = [name for name in wanted if name not in found or found[name].get('type') != 'MESH']
    if missing or any(found[name].get('vertices', 0) <= 8 for name in wanted[:1] if operation in ('morph', 'head')):
        raise ValueError(f'The saved scene does not contain the modelled objects ({", ".join(missing) or wanted[0]}).')
    actions.report('tool', f'control: app_act Blender saved {target.name}')
    if operation == 'house' and payload.get('plan'):
        plan = payload['plan']
        furnished = len([name for name in found if name.startswith('Furniture.')])
        return (f"Finished: built a {plan['style'].replace('_', ' ')} house live in Blender ({plan['floors']} floor(s), "
                f"{plan['roof']['type']} {plan['roof']['material']} roof, {plan['walls']['material']} walls, "
                f"{len(plan['rooms'])} rooms with {furnished} pieces of furniture) and saved it as {target}.")
    if operation in EXPECTED:
        return (f'Finished: built {summary} live in Blender and saved it as {target}. A separate Blender read back '
                f'{len(found)} objects including {", ".join(wanted[:3])}.')
    if operation == 'head':
        return (f'Finished: modelled a human head live in Blender (head, ears, eyes with pupils, nose and mouth) and '
                f'saved it as {target}. A separate Blender read back all {len(wanted)} parts.')
    return (f"Finished: turned the default cube into a {request['shape']['type']} named {request['name']} live in "
            f'Blender and saved it as {target}. A separate Blender read it back '
            f"({found[request['name']]['vertices']} vertices).")
