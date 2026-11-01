"""Image references for live modelling: browse, look, and turn what is seen into a plan (user request 2026-11-02).

With ``learning.cloud_research`` on (default off), Jarvis:

1. opens Wikimedia Commons image search for the subject in its own visible browser window and scrolls through
   the results (Google Images forbids automated scraping; Commons has millions of free-licensed photos of real
   buildings and people and a keyless API);
2. opens a few of the photos one by one;
3. asks the local vision model (Qwen3-VL, on this PC) to describe each photo in fixed fields: for a house the
   floors, roof shape and material, wall material and colours; for a person skin tone, hair colour and length,
   eye colour and beard;
4. merges the readings (majority vote, colour names to real colours) into the build plan or look.

Only the search words leave the PC; the photos are read locally and never sent anywhere. Every reading is
treated as data with fixed allowed values; nothing in a photo or its page is followed as an instruction.
The Qwen3-VL builds installed here think before answering even with think=false, so the answer is started with
its first field (the same measured fix as the vision control route): about 6-15 s per photo on the 4B model.
"""
from __future__ import annotations

import base64
from collections import Counter
import json
import re
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

COMMONS = 'https://commons.wikimedia.org/w/api.php'
AGENT = {'User-Agent': 'JarvisReference/1.0 (local assistant)'}
VISION_MODEL = 'qwen3-vl:4b'
COLOURS = {'white': '#f2f0eb', 'cream': '#efe6d2', 'beige': '#d9c7a5', 'tan': '#c8a77e', 'yellow': '#e3c55a',
           'orange': '#d47a3a', 'terracotta': '#b5532f', 'red': '#9a3b2c', 'brick red': '#9a4a32', 'pink': '#d9a3a0',
           'brown': '#6b4a32', 'dark brown': '#3b2a1e', 'black': '#202020', 'charcoal': '#3a3b3f', 'grey': '#8b8c8e',
           'gray': '#8b8c8e', 'dark grey': '#4a4b50', 'dark gray': '#4a4b50', 'light grey': '#c4c4c2',
           'light gray': '#c4c4c2', 'blue': '#4f6f8f', 'navy': '#22344f', 'green': '#5c7350', 'dark green': '#2f4a2b',
           'sage': '#8a9a7a', 'olive': '#6b6b3a', 'silver': '#b8bbbe', 'stone': '#9b9488', 'slate': '#55575c',
           'dark': '#3a3a3a', 'light': '#d8d6d0'}
HOUSE_FIELDS = ('house', 'floors', 'roof', 'roof material', 'roof colour', 'walls', 'wall colour', 'trim colour', 'front windows',
                'chimney', 'porch')
PERSON_FIELDS = ('skin', 'hair colour', 'hair length', 'eyes', 'beard')
Fetch = Callable[[str], bytes]


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=30) as response:  # noqa: S310
        return bytes(response.read(8_000_000))


def find_images(query: str, count: int = 4, fetch: Fetch = _fetch, offset: int = 0) -> List[Dict[str, str]]:
    """Photos on Wikimedia Commons for `query`: title, 640 px thumbnail, licence, page."""
    url = COMMONS + '?' + urllib.parse.urlencode({
        'action': 'query', 'generator': 'search', 'gsrnamespace': 6, 'gsrsearch': query[:120] + ' filetype:bitmap',
        'gsrlimit': count * 3, 'gsroffset': max(0, int(offset)), 'prop': 'imageinfo', 'iiprop': 'url|mime|extmetadata', 'iiurlwidth': 640, 'format': 'json'})
    data = json.loads(fetch(url))
    found = []
    for page in sorted(data.get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 0)):
        info = (page.get('imageinfo') or [{}])[0]
        if info.get('mime') not in ('image/jpeg', 'image/png') or not info.get('thumburl'):
            continue
        licence = str(info.get('extmetadata', {}).get('LicenseShortName', {}).get('value', ''))
        found.append({'title': str(page.get('title', '')), 'thumb': str(info['thumburl']), 'licence': licence,
                      'page': str(info.get('descriptionurl', ''))})
    return found[:count]


def ask_vision(image: bytes, prompt: str, first_field: str, model: str = VISION_MODEL,
               post: Optional[Callable[[bytes], bytes]] = None) -> str:
    body = json.dumps({'model': model, 'stream': False, 'think': False, 'keep_alive': '5m',
                       'messages': [{'role': 'user', 'content': prompt, 'images': [base64.b64encode(image).decode()]},
                                    {'role': 'assistant', 'content': first_field + ':'}],
                       'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': 160}}).encode()
    if post is None:
        def post(data: bytes) -> bytes:
            request = urllib.request.Request('http://127.0.0.1:11434/api/chat', data, {'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310 - the local Ollama server.
                return bytes(response.read())
    reply = json.loads(post(body))
    return first_field + ':' + str(reply.get('message', {}).get('content', ''))


def fields(text: str, names: tuple[str, ...]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in text.splitlines():
        key, _, value = line.partition(':')
        key = key.strip().lower()
        if key in names and value.strip():
            out[key] = value.strip().strip('.').lower()[:40]
    return out


def describe_house(image: bytes, **kwargs: Any) -> Dict[str, str]:
    prompt = ('Look at the photo. Answer in exactly this format, one per line:\nhouse: <yes if it shows a house or '
              'home people live in, otherwise no>\nfloors: <1-3>\nroof: <gable|hip|flat>\n'
              'roof material: <tiles|slate|metal|shingles>\nroof colour: <colour name>\nwalls: <brick|plaster|wood|stone>\n'
              'wall colour: <colour name>\ntrim colour: <colour name>\nfront windows: <number>\nchimney: <yes|no>\n'
              'porch: <yes|no>')
    return fields(ask_vision(image, prompt, 'house', **kwargs), HOUSE_FIELDS)


def describe_person(image: bytes, **kwargs: Any) -> Dict[str, str]:
    prompt = ('Look at the person. Answer in exactly this format, one per line:\n'
              'skin: <light|fair|medium|olive|brown|dark>\nhair colour: <black|dark brown|brown|blonde|red|grey>\n'
              'hair length: <short|medium|long>\neyes: <blue|green|hazel|brown|grey>\nbeard: <none|stubble|full>')
    return fields(ask_vision(image, prompt, 'skin', **kwargs), PERSON_FIELDS)


def unload_vision(model: str = VISION_MODEL) -> None:
    """Free the 4 GB GPU for Blender right after the photos are read (a live gate face build ran out of time while
    the vision model was still loaded, 2026-11-02)."""
    body = json.dumps({'model': model, 'keep_alive': 0}).encode()
    try:
        request = urllib.request.Request('http://127.0.0.1:11434/api/generate', body, {'Content-Type': 'application/json'})
        urllib.request.urlopen(request, timeout=30).read()  # noqa: S310 - the local Ollama server.
    except OSError:
        pass


def colour_hex(name: str) -> Optional[str]:
    name = name.lower().strip()
    if name in COLOURS:
        return COLOURS[name]
    for known in sorted(COLOURS, key=len, reverse=True):
        if known in name:
            return COLOURS[known]
    return None


def vote(readings: List[Dict[str, str]], key: str, allowed: Optional[tuple[str, ...]] = None) -> Optional[str]:
    values = [r[key] for r in readings if r.get(key) and (allowed is None or r[key] in allowed)]
    return Counter(values).most_common(1)[0][0] if values else None


def house_from_photos(readings: List[Dict[str, str]]) -> Dict[str, Any]:
    """A partial plan (the keys `reference_research.validated` understands) from what the photos showed."""
    plan: Dict[str, Any] = {'roof': {}, 'walls': {}, 'windows': {}}
    floors = vote(readings, 'floors', ('1', '2', '3'))
    if floors:
        plan['floors'] = int(floors)
    for key, target, allowed in (('roof', ('roof', 'type'), ('gable', 'hip', 'flat')),
                                 ('roof material', ('roof', 'material'), ('tiles', 'slate', 'metal', 'shingles')),
                                 ('walls', ('walls', 'material'), ('brick', 'plaster', 'wood', 'stone'))):
        value = vote(readings, key, allowed)
        if value:
            plan[target[0]][target[1]] = value
    for key, target in (('roof colour', ('roof', 'colour')), ('wall colour', ('walls', 'colour')),
                        ('trim colour', ('walls', 'trim_colour'))):
        named = Counter(r[key] for r in readings if r.get(key) and colour_hex(r[key]))
        if named:  # The most common colour the photos agree on that names a real colour.
            plan[target[0]][target[1]] = colour_hex(named.most_common(1)[0][0])
    windows = vote([{'w': re.sub(r'\D', '', r.get('front windows', ''))} for r in readings], 'w')
    if windows:
        plan['windows']['per_floor_front'] = int(windows)
    for key in ('chimney', 'porch'):
        value = vote(readings, key, ('yes', 'no'))
        if value:
            plan[key] = value == 'yes'
    return plan


def look_from_photos(readings: List[Dict[str, str]]) -> Dict[str, str]:
    look: Dict[str, str] = {}
    for key, target, allowed in (('skin', 'skin', ('light', 'fair', 'medium', 'olive', 'brown', 'dark')),
                                 ('hair colour', 'hair', ('black', 'dark brown', 'brown', 'blonde', 'red', 'grey')),
                                 ('hair length', 'hair_length', ('short', 'medium', 'long')),
                                 ('eyes', 'eyes', ('blue', 'green', 'hazel', 'brown', 'grey')),
                                 ('beard', 'beard', ('none', 'stubble', 'full'))):
        value = vote(readings, key, allowed)
        if value:
            look[target] = value
    return look


def study(actions: Any, query: str, kind: str, cancelled: Callable[[], bool], count: int = 3,
          fetch: Fetch = _fetch, describe: Optional[Callable[[bytes], Dict[str, str]]] = None) -> List[Dict[str, Any]]:
    """Browse the photos in the visible browser, read each locally; [{title, licence, reading}, ...]."""
    import random
    describe = describe or (describe_house if kind == 'house' else describe_person)
    rng = random.Random()
    if kind != 'house':  # Different wording and a different page of results each run: new references every time.
        query = rng.choice(['headshot photograph of ', 'studio portrait of ', 'portrait photograph of ']) + query.split(' of ', 1)[-1]
    photos = (find_images(query, count * 2, fetch, offset=rng.randrange(0, 24)) or
              find_images(query, count * 2, fetch))
    control = actions.control() if actions is not None else None
    if control is not None:
        search = 'https://commons.wikimedia.org/w/index.php?' + urllib.parse.urlencode(
            {'search': query, 'title': 'Special:MediaSearch', 'type': 'image'})
        actions.report('tool', 'control: web_open ' + search)
        try:
            control.web_open(search, cancelled)
            for _ in range(2):
                control.web_act('scroll', {'scroll_direction': 'down', 'scroll_amount': 5}, cancelled)
        except Exception as error:  # noqa: BLE001 - showing the browsing is optional; reading the photos is not.
            actions.report('warning', 'Reference browsing was not shown: ' + str(error)[:120])
    studied: List[Dict[str, Any]] = []
    for photo in photos:
        if cancelled() or len(studied) >= count:
            break
        if control is not None:
            try:
                actions.report('tool', 'control: web_open ' + photo['page'])
                control.web_open(photo['thumb'], cancelled)
            except Exception:  # noqa: BLE001
                pass
        reading = describe(fetch(photo['thumb']))
        if kind == 'house' and reading.get('house') == 'no':
            if actions is not None:
                actions.report('brain', f"Skipped {photo['title'][5:60]}: not a house")
            continue
        if actions is not None:
            actions.report('brain', f"Reference {photo['title'][5:60]} ({photo['licence']}): " +
                           ', '.join(f'{k} {v}' for k, v in reading.items()))
        studied.append({'title': photo['title'], 'licence': photo['licence'], 'reading': reading})
    if describe in (describe_house, describe_person):
        unload_vision()
    return studied
