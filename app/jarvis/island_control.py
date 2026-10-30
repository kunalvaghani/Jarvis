"""Dynamic Island cards for browser and PC control: one animated tile per route, live step progress.

UI metadata only: what the island shows never authorizes or changes an action. Tiles are drawn
every frame by island.animate_frame (via draw_tile), so motion stays smooth while the static
card text is rendered about once a second.
"""
import math
import time

SERVICES = {'browser': ('#4f9dff', 'Browser'), 'desktop': ('#2fd1c5', 'Windows apps'),
            'vision': ('#ff7ad9', 'Vision'), 'api': ('#ffc857', 'Apps & files')}
ROUTE_SERVICE = {'browser': 'browser', 'uia': 'desktop', 'vision': 'vision', 'api': 'api'}
TILE_FILL = {'browser': '#0f1d33', 'desktop': '#0d2726', 'vision': '#2a1028', 'api': '#2b2410'}
PHASES = {'checking': 'Checking connection', 'observing': 'Reading', 'locating': 'Finding it on screen',
          'acting': 'Working', 'verifying': 'Checking the result', 'waiting_approval': 'Waiting for your approval',
          'done': 'Done and checked', 'refused': 'Stopped safely', 'failed': "Couldn't finish", 'blocked': 'Needs you'}
WORKING = frozenset({'checking', 'observing', 'locating', 'acting', 'verifying'})
SHOW_SECONDS = {'checking': 30, 'observing': 120, 'locating': 120, 'acting': 120, 'verifying': 60,
                'waiting_approval': 180, 'done': 6, 'refused': 12, 'failed': 12, 'blocked': 30}
OUTCOME = {'done': ('#5ad48a', 'check'), 'refused': ('#f1c580', 'pause'), 'blocked': ('#f1c580', 'bang'),
           'failed': ('#ff8a80', 'cross'), 'waiting_approval': ('#b9c9ff', 'dots')}


def is_control(media):
    return isinstance(media, dict) and media.get('service') in SERVICES


def caption(media):
    phase = media.get('phase', '')
    text = media.get('detail') or PHASES.get(phase, '')
    return text


def step_text(media):
    step, steps = int(media.get('step') or 0), int(media.get('steps') or 0)
    return f'Step {step} of {steps}' if step and steps else (f'Step {step}' if step else '')


def fraction(media):
    step, steps = int(media.get('step') or 0), int(media.get('steps') or 0)
    if not steps:
        return None
    finished = step if media.get('phase') not in WORKING else step - 1
    return max(0., min(1., finished / steps))


def _box(values, s):
    return tuple(round(v * s) for v in values)


def _glyph(draw, kind, cx, cy, r, color, s, t):
    """Outcome badge: a filled circle with a check, pause, exclamation, cross or pulsing dots."""
    draw.ellipse(_box((cx - r, cy - r, cx + r, cy + r), s), fill=color)
    ink, width = '#101114', max(1, round(1.8 * s))
    if kind == 'check':
        draw.line([_box((cx - r * .45, cy), s), _box((cx - r * .1, cy + r * .4), s), _box((cx + r * .5, cy - r * .4), s)],
                  fill=ink, width=width)
    elif kind == 'pause':
        for dx in (-.28, .28):
            draw.rectangle(_box((cx + dx * r - r * .12, cy - r * .45, cx + dx * r + r * .12, cy + r * .45), s), fill=ink)
    elif kind == 'bang':
        draw.rectangle(_box((cx - r * .12, cy - r * .55, cx + r * .12, cy + r * .15), s), fill=ink)
        draw.ellipse(_box((cx - r * .15, cy + r * .3, cx + r * .15, cy + r * .6), s), fill=ink)
    elif kind == 'cross':
        for a, b in (((-.4, -.4), (.4, .4)), ((-.4, .4), (.4, -.4))):
            draw.line([_box((cx + a[0] * r, cy + a[1] * r), s), _box((cx + b[0] * r, cy + b[1] * r), s)], fill=ink, width=width)
    else:
        for i in range(3):
            lift = 1.5 * abs(math.sin(t * 4 + i))
            x = cx + (i - 1) * r * .5
            draw.ellipse(_box((x - r * .14, cy - r * .14 - lift, x + r * .14, cy + r * .14 - lift), s), fill=ink)


def _browser(draw, x, y, side, accent, state, t, s):
    working = state in WORKING
    draw.rounded_rectangle(_box((x + 5, y + 7, x + side - 5, y + side - 7), s), radius=round(5 * s), fill='#16263f',
                           outline=accent, width=max(1, round(s)))
    draw.rounded_rectangle(_box((x + 8, y + 10, x + 22, y + 15), s), radius=round(2 * s), fill=accent)   # Active tab.
    draw.rounded_rectangle(_box((x + 24, y + 10, x + 36, y + 15), s), radius=round(2 * s), fill='#2c3d5c')
    bar = (x + 8, y + 17, x + side - 8, y + 21)
    draw.rounded_rectangle(_box(bar, s), radius=round(2 * s), fill='#24344f')                          # Address bar.
    if working:
        sweep = (t * .9) % 1.3 - .15
        a = bar[0] + (bar[2] - bar[0]) * max(0., sweep)
        b = bar[0] + (bar[2] - bar[0]) * min(1., sweep + .3)
        if b > a:
            draw.rounded_rectangle(_box((a, bar[1], b, bar[3]), s), radius=round(2 * s), fill=accent)
    for i, w in enumerate((30, 22, 26)):                                                                # Page lines.
        draw.rounded_rectangle(_box((x + 9, y + 25 + i * 6, x + 9 + w, y + 28 + i * 6), s), radius=round(1 * s), fill='#3a4b6b')
    if working:
        # The cursor travels between targets and clicks with a ripple.
        cycle = (t * .7) % 1
        px = x + 14 + (side - 30) * (.5 + .45 * math.sin(t * 1.6))
        py = y + 27 + 10 * (.5 + .5 * math.sin(t * 2.3 + 1))
        if cycle > .7:
            ring = (cycle - .7) / .3 * 7
            draw.ellipse(_box((px - ring, py - ring, px + ring, py + ring), s), outline=accent, width=max(1, round(s)))
        draw.polygon([_box(p, s) for p in ((px, py), (px, py + 9), (px + 2.6, py + 6.6), (px + 6, py + 7))], fill='#ffffff')


def _desktop(draw, x, y, side, accent, state, t, s):
    working = state in WORKING
    draw.rounded_rectangle(_box((x + 5, y + 7, x + side - 5, y + side - 7), s), radius=round(4 * s), fill='#123331',
                           outline=accent, width=max(1, round(s)))
    draw.rectangle(_box((x + 6, y + 8, x + side - 6, y + 14), s), fill='#1c4744')                        # Title bar.
    for i, color in enumerate(('#ff6b6b', '#f1c580', '#5ad48a')):
        cx = x + side - 12 - i * 5
        draw.ellipse(_box((cx - 1.5, y + 9.5, cx + 1.5, y + 12.5), s), fill=color)
    lit = int(t * 2.2) % 4 if working else -1
    for i in range(4):                                                                                  # Controls.
        col, row = i % 2, i // 2
        box = (x + 10 + col * 18, y + 18 + row * 13, x + 26 + col * 18, y + 28 + row * 13)
        on = i == lit
        draw.rounded_rectangle(_box(box, s), radius=round(2 * s), fill=accent if on else '#24504d')
        if on and state == 'observing':
            draw.rounded_rectangle(_box((box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2), s), radius=round(3 * s),
                                   outline='#ffffff', width=max(1, round(s)))


def _vision(draw, x, y, side, accent, state, t, s):
    working = state in WORKING
    cx, cy = x + side / 2, y + side / 2
    w, h = side / 2 - 6, side / 2 - 14
    top = [(cx - w + 2 * w * k / 16, cy - h * math.sin(math.pi * k / 16)) for k in range(17)]
    bottom = [(cx + w - 2 * w * k / 16, cy + h * math.sin(math.pi * k / 16)) for k in range(17)]
    draw.polygon([_box(p, s) for p in top + bottom], fill='#3a1838', outline=accent)                     # Eye.
    look = math.sin(t * 1.3) * w * .45 if working else 0
    iris = 8.5
    draw.ellipse(_box((cx + look - iris, cy - iris, cx + look + iris, cy + iris), s), fill=accent)
    draw.ellipse(_box((cx + look - 3.5, cy - 3.5, cx + look + 3.5, cy + 3.5), s), fill='#120812')
    draw.ellipse(_box((cx + look + 1.5, cy - 4, cx + look + 3.5, cy - 2), s), fill='#ffffff')
    if working:
        scan = y + 9 + (side - 18) * ((t * .8) % 1)                                                     # Sweep line.
        draw.line([_box((x + 6, scan), s), _box((x + side - 6, scan), s)], fill='#ffd1f3', width=max(1, round(s)))
        r = 4 + 3 * abs(math.sin(t * 3))                                                                # Reticle.
        rx, ry = x + side - 13, y + 13
        draw.ellipse(_box((rx - r, ry - r, rx + r, ry + r), s), outline='#ffffff', width=max(1, round(s)))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            draw.line([_box((rx + dx * (r + 1), ry + dy * (r + 1)), s), _box((rx + dx * (r + 4), ry + dy * (r + 4)), s)],
                      fill='#ffffff', width=max(1, round(s)))


def _api(draw, x, y, side, accent, state, t, s):
    working = state in WORKING
    a, b = (x + 13, y + side / 2 + 6), (x + side - 13, y + side / 2 - 6)
    points = []
    for k in range(21):                                                                                 # Link curve.
        u = k / 20
        points.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u - 9 * math.sin(math.pi * u)))
    draw.line([_box(p, s) for p in points], fill='#6b5a24', width=max(1, round(2 * s)))
    if working:
        for k in range(3):                                                                              # Packets.
            u = (t * .8 + k / 3) % 1
            px, py = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u - 9 * math.sin(math.pi * u)
            draw.ellipse(_box((px - 2.2, py - 2.2, px + 2.2, py + 2.2), s), fill='#fff1c2')
    pulse = 1.5 * abs(math.sin(t * 3)) if working else 0
    for (nx, ny), fill in ((a, accent), (b, '#ffe7a3')):
        r = 6 + pulse
        draw.rounded_rectangle(_box((nx - r, ny - r, nx + r, ny + r), s), radius=round(3 * s), fill=fill)
    draw.rectangle(_box((a[0] - 2, a[1] - 2.5, a[0] + 2, a[1] + 2.5), s), fill='#2b2410')               # App glyph.
    draw.ellipse(_box((b[0] - 2.5, b[1] - 2.5, b[0] + 2.5, b[1] + 2.5), s), fill='#2b2410')            # Jarvis node.


TILES = {'browser': _browser, 'desktop': _desktop, 'vision': _vision, 'api': _api}


def draw_tile(draw, x, y, side, service, state, t, s):
    """Animated route tile at (x, y) in tile-local units; s is the supersampling factor."""
    accent = SERVICES[service][0]
    draw.rounded_rectangle(_box((x, y, x + side, y + side), s), radius=round(10 * s), fill=TILE_FILL[service])
    TILES[service](draw, x, y, side, accent, state, t, s)
    if state in OUTCOME:
        color, kind = OUTCOME[state]
        _glyph(draw, kind, x + side - 9, y + side - 9, 7.5, color, s, t)


def draw_badge(draw, x, y, service, state, t, s, step=0, steps=0):
    """Compact header badge (36x22 units): a spinning ring or outcome dot, then step pips."""
    accent = SERVICES[service][0]
    cx, cy, r = x + 9, y + 11, 7.5
    if state in WORKING:
        draw.ellipse(_box((cx - r, cy - r, cx + r, cy + r), s), outline='#2a2b32', width=max(1, round(2 * s)))
        start = (t * 360) % 360
        draw.arc(_box((cx - r, cy - r, cx + r, cy + r), s), start, start + 110, fill=accent, width=max(1, round(2.2 * s)))
        draw.ellipse(_box((cx - 2.5, cy - 2.5, cx + 2.5, cy + 2.5), s), fill=accent)
    else:
        color, kind = OUTCOME.get(state, (accent, 'dots'))
        _glyph(draw, kind, cx, cy, r, color, s, t)
    total = min(5, steps) if steps else 0
    done = min(total, step if state not in WORKING else step - 1) if total else 0
    for i in range(total):
        px = x + 22 + i * 3.4
        lit = i < done or (i == done and state in WORKING and int(t * 3) % 2 == 0)
        draw.ellipse(_box((px - 1.2, cy - 1.2, px + 1.2, cy + 1.2), s), fill=accent if lit else '#3a3b44')


class IslandProgress:
    """Progress sink: control ProgressEvents become island cards (de-duplicated, best effort)."""

    def __init__(self, actions):
        self.actions = actions
        self.last = None

    def __call__(self, event):
        from .media_player import card
        route = getattr(event.route, 'value', str(event.route))
        service = ROUTE_SERVICE.get(route, 'api')
        key = (service, event.phase, event.title, event.detail, event.step, event.steps)
        if key == self.last:
            return
        self.last = key
        data = card(service, event.phase, event.title, event.subtitle or SERVICES[service][1], '', 0, 0, event.detail)
        data.update({'step': int(event.step), 'steps': int(event.steps), 'at': time.time()})
        self.actions.report('media_card', data)
