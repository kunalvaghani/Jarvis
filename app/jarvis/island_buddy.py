"""Pip, the little friend who lives in the island.

Drawn with PIL so it stays sharp at any scale:

* **Body:** a superellipse marshmallow, |x/rx|^2.7 + |y/ry|^2.7 = 1, shaded with light from the top left. It has a
  specular highlight, rim shadow and soft floor shadow, and takes the tint of its emotion. It morphs into a box when it
  is about to eat a file.
* **Eyes:** dark, glossy and placed on a sphere, so looking (yaw, pitch) moves them like a turning head. Their shape
  changes with the emotion: dot, happy, closed, half, wide, spiral, heart, x, laugh, wink, star, sad, angry and focus.
* **Details:** mouths, blush, little arms, a status badge pill, particles (hearts, sparks, zzz, notes, sweat, stars,
  confetti, steam, question marks), and outfits (glasses, sunglasses, headphones, beanie, santa hat, witch hat, party
  hat, crown, bow).

``pose_for(emotion, t)`` turns an emotion and the time into a pose: each emotion is its own animation.
``paint(image, cx, cy, size, pose, sampling)`` draws a pose. buddy_engine.py decides the emotion from Jarvis, the
mouse, the screen and Pip's own mood. ``draw_buddy`` keeps the simple call used by the island.
"""
from functools import lru_cache
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

EYE, BLUSH, MOUTH = (24, 22, 32), (255, 150, 180), (70, 30, 50)
TINTS = {"white": (250, 250, 255), "blue": (150, 190, 255), "purple": (190, 160, 255), "amber": (255, 205, 140),
         "cyan": (130, 225, 235), "red": (255, 150, 160), "green": (150, 230, 190), "pink": (255, 185, 220),
         "night": (190, 195, 225), "gold": (255, 225, 140), "grey": (215, 215, 225)}
EMOTIONS = {}  # name -> short description (filled below), for docs, tests and the engine.


def register(name, description):
    EMOTIONS[name] = description


for _name, _what in [
        ("idle", "bobs, blinks and glances around"), ("greeting", "waves both arms with happy eyes and a hop"),
        ("listening", "leans in with wide attentive eyes, cyan"), ("talking", "mouth moves while Jarvis speaks"),
        ("thinking", "purple, eyes up, animated … badge"), ("working", "blue, focused eyes, … badge, busy jiggle"),
        ("searching", "eyes scan left and right, ⌕ badge"), ("reading", "puffed cheeks, half-closed eyes, dots"),
        ("question", "cyan, head tilt, ? badge"), ("approval", "amber, hops, ! badge"),
        ("error", "red, shakes, x eyes, sweat drop"), ("finished", "green, happy eyes, sparks burst, ✓ badge"),
        ("proud", "green, closed smile, crown and stars"), ("love", "pink, heart eyes, hearts float up, ♥ badge"),
        ("surprised", "jumps, wide eyes, O mouth"), ("wink", "winks and smiles"),
        ("laughing", "> < eyes, open mouth, shakes with laughter"), ("annoyed", "flat eyes, puffed, steam puffs"),
        ("dizzy", "pink, spiral eyes spinning, wobbles, stars orbit"),
        ("sleeping", "closed eyes, slow breathing, zzz, beanie at night"),
        ("yawn", "stretches, yawns, then blinks"), ("bored", "half-lidded eyes looking away, sighs"),
        ("curious", "head tilt, one eye bigger, looks at your pointer"), ("excited", "bounces with star eyes and confetti"),
        ("dancing", "sways and hops to the beat with headphones and notes, ♪ badge"),
        ("focused", "glasses on, determined eyes (you're coding)"), ("watching", "relaxed, eyes down at the screen"),
        ("chatty", "little talking bubbles (you're chatting)"), ("hungry", "turns into a box with an open lid: drop it!"),
        ("eating", "chomps as a page falls in"), ("sad", "blue-grey, teary eyes, worried brows"),
        ("shy", "blushes hard and looks away"), ("ouch", "squashed flat by a slap, stars"),
        ("whee", "excited while you drag the island"), ("sleepy", "heavy eyelids, slow sway")]:
    register(_name, _what)


# --- helpers -----------------------------------------------------------------------------------------------------
def lerp(a, b, k):
    return a + (b - a) * k


def mix(c1, c2, k):
    return tuple(int(round(lerp(a, b, k))) for a, b in zip(c1, c2))


def blink(t, period=4.2):
    """Short blink every few seconds, with an occasional double blink."""
    phase = t % period
    return phase < .12 or (int(t / period) % 3 == 0 and .24 < phase < .34)


def ease(x):
    x = max(0., min(1., x))
    return x * x * (3 - 2 * x)


def superellipse(cx, cy, rx, ry, n=2.7, steps=72, morph=0.):
    """Points of |x/rx|^n + |y/ry|^n = 1; morph 0..1 squares it towards a box."""
    n = lerp(n, 9., morph)
    points = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        c, s = math.cos(a), math.sin(a)
        points.append((cx + rx * math.copysign(abs(c) ** (2 / n), c), cy + ry * math.copysign(abs(s) ** (2 / n), s)))
    return points


@lru_cache(maxsize=128)
def body_sprite(w, h, tint, morph_q):
    """Shaded body as an RGBA image (cached by size, tint and box morph)."""
    w, h = max(4, w), max(4, h)
    n = lerp(2.7, 9., morph_q / 10)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xs + .5) / w * 2 - 1
    v = (ys + .5) / h * 2 - 1
    r = (np.abs(u) ** n + np.abs(v) ** n) ** (1 / n)
    alpha = np.clip((1 - r) * min(w, h) * .5, 0, 1)  # Anti-aliased edge.
    base = np.array(mix((255, 255, 255), tint, .55), np.float32)
    shade = 1.04 - .16 * v - .06 * u                        # Light from the top left.
    shade -= .16 * np.clip((r - .72) / .28, 0, 1) ** 2      # Rim falls into shadow.
    glow = np.exp(-(((u + .32) / .42) ** 2 + ((v + .42) / .30) ** 2))
    color = base[None, None, :] * shade[..., None] + 255 * .20 * glow[..., None]
    rgba = np.dstack([np.clip(color, 0, 255), alpha * 255]).astype(np.uint8)
    sprite = Image.fromarray(rgba, "RGBA")
    # Specular highlight.
    spec = Image.new("L", (w, h), 0)
    ImageDraw.Draw(spec).ellipse((w * .17, h * .10, w * .40, h * .28), fill=150)
    spec = spec.filter(ImageFilter.GaussianBlur(max(1, w / 30)))
    white = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    white.putalpha(Image.fromarray(np.minimum(np.array(spec), (alpha * 255).astype(np.uint8))))
    sprite.alpha_composite(white)
    return sprite


@lru_cache(maxsize=16)
def shadow_sprite(w, h):
    shade = Image.new("L", (w * 2, h * 4), 0)
    ImageDraw.Draw(shade).ellipse((w * .5, h * 1.5, w * 1.5, h * 2.5), fill=120)
    shade = shade.filter(ImageFilter.GaussianBlur(max(1, h * .6)))
    sprite = Image.new("RGBA", shade.size, (0, 0, 0, 0))
    sprite.putalpha(shade)
    return sprite


@lru_cache(maxsize=32)
def font(size, symbol=False, bold=True):
    name = "seguisym.ttf" if symbol else ("segoeuib.ttf" if bold else "segoeui.ttf")
    try:
        return ImageFont.truetype("C:/Windows/Fonts/" + name, max(5, int(size)))
    except OSError:
        return ImageFont.load_default()


# --- poses: one animation per emotion -------------------------------------------------------------------------------
def base_pose():
    return {"tint": TINTS["white"], "sx": 1., "sy": 1., "dx": 0., "dy": 0., "rot": 0., "morph": 0.,
            "eyes": "dot", "eye_open": 1., "eye_scale": 1., "look": (0., 0.), "mouth": "smile", "mouth_open": 0.,
            "blush": .8, "arms": [], "badge": None, "particles": [], "outfit": [], "brows": None, "t": 0.}


def pose_for(emotion, t=0., look=None, outfit=(), extra=None):
    """The pose of one emotion at time t (seconds). Each branch is that emotion's own animation."""
    p = base_pose()
    p["t"] = t
    e = emotion if emotion in EMOTIONS else "idle"
    breath = math.sin(t * 2.1)
    p["dy"] = -1.2 * breath * .5
    p["sy"] = 1 + .015 * breath
    p["sx"] = 1 - .012 * breath
    wander = (.55 * math.sin(t * .7) + .25 * math.sin(t * 1.9), .2 * math.sin(t * .9))
    p["look"] = wander
    closed = blink(t)
    if e == "idle":
        p["eye_open"] = .08 if closed else 1.
    elif e == "greeting":
        hop = abs(math.sin(t * 6))
        p.update(dy=-4 * hop, eyes="happy", mouth="open", mouth_open=.5, blush=1.2, look=(0, 0))
        wave = math.sin(t * 12) * 35
        p["arms"] = [(-1, -60 + wave), (1, -60 - wave)]
    elif e == "listening":
        p.update(tint=TINTS["cyan"], eye_scale=1.15, mouth="smile", rot=-6 + 2 * math.sin(t * 2), look=(0, -.1))
        p["eye_open"] = .1 if closed else 1.
    elif e == "talking":
        p.update(tint=TINTS["blue"], mouth="talk", mouth_open=.25 + .75 * abs(math.sin(t * 11) * math.sin(t * 4.3)))
        p["eye_open"] = .1 if closed else 1.
        p["dy"] -= abs(math.sin(t * 5.5)) * 1.2
    elif e == "thinking":
        p.update(tint=TINTS["purple"], look=(.35 + .15 * math.sin(t), -.75), mouth="flat", badge="dots", rot=4 * math.sin(t * .8))
    elif e == "working":
        p.update(tint=TINTS["blue"], eyes="focus", mouth="flat", badge="dots", look=(.25 * math.sin(t * 3), .15))
        p["dx"] = .6 * math.sin(t * 23)
    elif e == "searching":
        p.update(tint=TINTS["blue"], badge="search", mouth="o", mouth_open=.3, look=(math.sin(t * 3.2), 0))
    elif e == "reading":
        p.update(eyes="half", blush=1.5, mouth="cat", look=(.3 * math.sin(t * 2.5), .5), sx=1.05, particles=["dots"])
    elif e == "question":
        p.update(tint=TINTS["cyan"], badge="?", rot=-10 + 3 * math.sin(t * 2), look=(.2, -.2), mouth="o", mouth_open=.25)
        p["eye_open"] = .1 if closed else 1.
    elif e == "approval":
        hop = abs(math.sin(t * 4))
        p.update(tint=TINTS["amber"], badge="!", dy=-3 * hop, sy=1 + .05 * hop, sx=1 - .04 * hop, eye_scale=1.1,
                 mouth="open", mouth_open=.35, arms=[(1, -70 + 20 * math.sin(t * 8))])
    elif e == "error":
        shake = math.sin(t * 40) * max(0., 1 - (t % 2.5)) * 2.5
        p.update(tint=TINTS["red"], eyes="x", mouth="frown", dx=shake, badge="x", particles=["sweat"], blush=.4)
    elif e == "finished":
        pop = ease(min(1, (t % 3) * 3))
        p.update(tint=TINTS["green"], eyes="happy", mouth="open", mouth_open=.6, badge="check",
                 sy=1 + .06 * (1 - pop), sx=1 - .05 * (1 - pop), particles=["sparks"], arms=[(-1, -50), (1, -50)])
    elif e == "proud":
        p.update(tint=TINTS["green"], eyes="happy", mouth="smile", blush=1.3, outfit=["crown"], particles=["stars"],
                 dy=-1.5 * abs(math.sin(t * 2)))
    elif e == "love":
        p.update(tint=TINTS["pink"], eyes="heart", mouth="cat", blush=1.8, badge="heart", particles=["hearts"],
                 sx=1 + .03 * math.sin(t * 7), sy=1 + .03 * math.sin(t * 7 + 1.5))
    elif e == "surprised":
        jump = math.exp(-((t % 3) * 4)) * 6
        p.update(eyes="wide", eye_scale=1.35, mouth="o", mouth_open=.8, dy=-jump, sy=1 + .06 * jump / 6, blush=.5)
    elif e == "wink":
        p.update(eyes="wink" if (t % 2) < 1.2 else "dot", mouth="smile", blush=1.3, rot=-5)
    elif e == "laughing":
        p.update(eyes="laugh", mouth="open", mouth_open=.5 + .4 * abs(math.sin(t * 14)), blush=1.6,
                 dy=-1.5 * abs(math.sin(t * 14)), rot=4 * math.sin(t * 7))
    elif e == "annoyed":
        p.update(eyes="half", brows="angry", mouth="flat", sx=1.06, sy=.95, particles=["steam"], tint=TINTS["grey"],
                 look=(-.5, 0))
    elif e == "dizzy":
        p.update(tint=TINTS["pink"], eyes="spiral", mouth="wavy", rot=10 * math.sin(t * 3), dx=2 * math.sin(t * 3),
                 particles=["orbit"])
    elif e == "sleeping":
        slow = math.sin(t * 1.2)
        p.update(tint=TINTS["night"], eyes="closed", mouth="o", mouth_open=.12 + .08 * slow, sy=1 + .03 * slow,
                 sx=1 - .02 * slow, dy=.5, particles=["zzz"], blush=.5, look=(0, .2))
    elif e == "yawn":
        k = (t % 4) / 4
        stretch = math.sin(min(1, k * 1.6) * math.pi)
        p.update(eyes="closed" if stretch > .3 else "half", mouth="yawn", mouth_open=stretch, sy=1 + .1 * stretch,
                 sx=1 - .06 * stretch, arms=[(-1, -100 * stretch), (1, -100 * stretch)] if stretch > .2 else [])
    elif e == "bored":
        p.update(eyes="half", mouth="flat", look=(-.8, .3), dy=1, rot=-3 + 2 * math.sin(t * .6), tint=TINTS["grey"])
        if (t % 6) < .8:
            p["mouth"], p["mouth_open"] = "o", .3  # A little sigh.
    elif e == "curious":
        p.update(rot=-12, eye_scale=1.1, mouth="o", mouth_open=.2, look=look or (.4, -.1))
        p["eye_open"] = .1 if closed else 1.
    elif e == "excited":
        bounce = abs(math.sin(t * 9))
        p.update(eyes="star", mouth="open", mouth_open=.7, dy=-5 * bounce, sy=1 + .08 * (1 - bounce), sx=1 - .05 * (1 - bounce),
                 particles=["confetti"], blush=1.4, arms=[(-1, -80), (1, -80)])
    elif e == "dancing":
        beat = t * 2.2 * math.pi
        p.update(rot=10 * math.sin(beat / 2), dx=3 * math.sin(beat / 2), dy=-2.5 * abs(math.sin(beat)),
                 eyes="happy", mouth="open", mouth_open=.4, badge="note", particles=["notes"],
                 outfit=["headphones"], arms=[(-1, -40 + 50 * math.sin(beat)), (1, -40 - 50 * math.sin(beat))])
    elif e == "focused":
        p.update(eyes="focus", mouth="flat", outfit=["glasses"], look=(.15 * math.sin(t * 1.3), .35), tint=TINTS["blue"])
        p["eye_open"] = .1 if closed else .8
    elif e == "watching":
        p.update(look=(0, .55), mouth="smile", eye_open=.1 if closed else .9, rot=2 * math.sin(t * .5))
    elif e == "chatty":
        p.update(mouth="talk", mouth_open=.3 + .3 * abs(math.sin(t * 6)), particles=["bubbles"], tint=TINTS["green"],
                 look=(.4, 0))
    elif e == "hungry":
        p.update(morph=.85, eyes="wide", eye_scale=1.05, mouth="lid", mouth_open=.6 + .3 * math.sin(t * 8),
                 dy=-1.5 * abs(math.sin(t * 8)), blush=.6, look=(0, -.5))
    elif e == "eating":
        chomp = abs(math.sin(t * 8))
        p.update(morph=.5 * (1 - min(1, t / 2)), mouth="chomp", mouth_open=chomp, sy=1 - .05 * chomp, sx=1 + .04 * chomp,
                 blush=1.4, particles=["page"])
    elif e == "sad":
        p.update(tint=TINTS["night"], eyes="sad", brows="worried", mouth="frown", particles=["tear"], dy=1.5, blush=.5)
    elif e == "shy":
        p.update(blush=2.4, look=(-.7, .3), mouth="cat", rot=-8, eye_open=.1 if closed else .85, sx=.97)
    elif e == "ouch":
        k = min(1, (t % 3) / .25)
        p.update(sy=.75 + .25 * ease(k), sx=1.2 - .2 * ease(k), eyes="laugh", mouth="frown", particles=["orbit"], dy=3 * (1 - k))
    elif e == "whee":
        p.update(eyes="happy", mouth="open", mouth_open=.7, rot=12 * math.sin(t * 5), arms=[(-1, -90), (1, -90)], blush=1.3)
    elif e == "sleepy":
        p.update(eyes="half", eye_open=.45 + .2 * math.sin(t * .8), rot=4 * math.sin(t * .7), mouth="o", mouth_open=.1,
                 tint=TINTS["night"])
    if look is not None and e not in {"thinking", "bored", "watching", "shy", "sleeping", "searching", "reading", "annoyed",
                                      "focused", "curious"}:
        p["look"] = look
    p["outfit"] = list(dict.fromkeys(list(p["outfit"]) + list(outfit)))
    if extra:
        p.update(extra)
    return p


# --- painting ---------------------------------------------------------------------------------------------------
def paint(image, cx, cy, size, pose, sampling=1.):
    """Draw a pose centred at (cx, cy) in logical units onto an RGB or RGBA image."""
    s = sampling
    t = pose.get("t", 0.)
    side = int(size * 2.4 * s)
    tile = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    ox = oy = side / 2  # Pip's centre inside the tile (pixels).
    w, h = size * pose["sx"] * s, size * .86 * pose["sy"] * s
    bx, by = ox + pose["dx"] * s * size / 40, oy + pose["dy"] * s * size / 40
    # Floor shadow (stays on the ground while Pip hops).
    shadow = shadow_sprite(max(4, int(w * .8)), max(2, int(h * .12)))
    tile.alpha_composite(shadow, (int(ox - shadow.width / 2), int(oy + size * .43 * s - shadow.height / 2)))
    # Arms behind the body.
    for side_sign, angle in pose["arms"]:
        a = math.radians(angle)
        ax = bx + side_sign * (w / 2 + size * .02 * s) + side_sign * math.cos(a) * size * .1 * s
        ay = by + h * .1 + math.sin(a) * size * .16 * s
        r = size * .09 * s
        draw.ellipse((ax - r, ay - r, ax + r, ay + r), fill=mix(pose["tint"], (255, 255, 255), .5) + (255,),
                     outline=(200, 200, 215, 255), width=max(1, int(s * size / 60)))
    body = body_sprite(int(w), int(h), pose["tint"], round(pose["morph"] * 10))
    tile.alpha_composite(body, (int(bx - body.width / 2), int(by - body.height / 2)))
    top = by - h / 2
    yaw, pitch = pose["look"]
    yaw, pitch = max(-1., min(1., yaw)), max(-1., min(1., pitch))
    eye_y = by - h * .02 + pitch * h * .12
    gap = w * .2 * (1 - .12 * abs(yaw))
    ex0 = bx + yaw * w * .13
    eye_w, eye_h = w * .085 * pose["eye_scale"], h * .14 * pose["eye_scale"]
    line = max(1, int(size * s * .045))
    shape = pose["eyes"]
    for side_sign in (-1, 1):
        ex = ex0 + side_sign * gap
        # Perspective: the eye on the far side of the turn is a little narrower.
        ew = eye_w * (1 - .25 * max(0., side_sign * -yaw))
        opened = pose["eye_open"]
        here = shape
        if shape == "wink":
            here = "happy" if side_sign > 0 else "dot"
        if here == "half" and opened >= .2:
            # Heavy lids: only the lower half of the eye, with the lid line on top.
            eh = eye_h * max(.5, opened)
            draw.chord((ex - ew, eye_y - eh * .9, ex + ew, eye_y + eh), 0, 180, fill=EYE + (255,))
            draw.line((ex - ew * 1.15, eye_y + eh * .05, ex + ew * 1.15, eye_y + eh * .05), fill=EYE + (255,), width=line)
        elif here in {"dot", "wide", "focus", "half", "sad"}:
            eh = eye_h * opened * (.55 if here == "focus" else 1.)
            if opened < .2:
                draw.line((ex - ew, eye_y, ex + ew, eye_y), fill=EYE + (255,), width=line)
            else:
                draw.ellipse((ex - ew, eye_y - eh, ex + ew, eye_y + eh), fill=EYE + (255,))
                gl = ew * .45
                draw.ellipse((ex - ew * .1, eye_y - eh * .7, ex - ew * .1 + gl, eye_y - eh * .7 + gl), fill=(255, 255, 255, 230))
        elif here == "happy":
            draw.arc((ex - ew * 1.3, eye_y - eye_h * .6, ex + ew * 1.3, eye_y + eye_h * .9), 200, 340, fill=EYE + (255,), width=line)
        elif here == "closed":
            draw.arc((ex - ew * 1.2, eye_y - eye_h * .8, ex + ew * 1.2, eye_y + eye_h * .3), 20, 160, fill=EYE + (255,), width=line)
        elif here == "laugh":
            d = side_sign
            pts = [(ex - d * ew * 1.1, eye_y - eye_h * .6), (ex + d * ew * .9, eye_y), (ex - d * ew * 1.1, eye_y + eye_h * .6)]
            draw.line(pts, fill=EYE + (255,), width=line, joint="curve")
        elif here == "x":
            r = ew * 1.1
            draw.line((ex - r, eye_y - r, ex + r, eye_y + r), fill=EYE + (255,), width=line)
            draw.line((ex - r, eye_y + r, ex + r, eye_y - r), fill=EYE + (255,), width=line)
        elif here == "spiral":
            pts, spin = [], t * 6 * side_sign
            for k in range(28):
                ang, rad = spin + k * .45, ew * 1.3 * k / 28
                pts.append((ex + rad * math.cos(ang), eye_y + rad * math.sin(ang)))
            draw.line(pts, fill=EYE + (255,), width=max(1, line - 1), joint="curve")
        elif here == "heart":
            heart(draw, ex, eye_y, ew * 1.5 * (1 + .12 * math.sin(t * 8)), (255, 80, 130, 255))
        elif here == "star":
            star(draw, ex, eye_y, ew * 1.6, (40, 30, 60, 255), spin=t * 2)
            star(draw, ex, eye_y, ew * .7, (255, 230, 120, 255), spin=t * 2)
    if pose.get("brows"):
        for side_sign in (-1, 1):
            ex = ex0 + side_sign * gap
            inner = 1 if pose["brows"] == "angry" else -1
            y1 = eye_y - eye_h * (1.5 + .35 * inner)
            y2 = eye_y - eye_h * (1.5 - .35 * inner)
            draw.line((ex - side_sign * eye_w * 1.4, y2, ex + side_sign * eye_w * .2, y1), fill=EYE + (255,), width=max(1, line - 1))
    # Blush.
    if pose["blush"] > 0:
        k = min(2.5, pose["blush"])
        for side_sign in (-1, 1):
            bxx = ex0 + side_sign * (gap + w * .1)
            byy = eye_y + eye_h * 1.05
            rr = w * .055 * (1 + .25 * (k - 1))
            draw.ellipse((bxx - rr * 1.3, byy - rr * .6, bxx + rr * 1.3, byy + rr * .6),
                         fill=BLUSH + (int(min(255, 110 * k)),))
    mouth(draw, ex0, eye_y + eye_h * 1.25, w, pose, line)
    for item in pose["outfit"]:
        wear(draw, item, bx, top, w, h, ex0, gap, eye_y, eye_w, eye_h, s, size, t)
    if pose["badge"]:
        badge(draw, pose["badge"], bx - w * .42, top - h * .02, size * s, t)
    for kind in pose["particles"]:
        particles(draw, kind, bx, by, w, h, size * s, t)
    if pose["rot"]:
        tile = tile.rotate(pose["rot"], resample=Image.BICUBIC, center=(bx, by + h * .3))
    left, upper = int(cx * s - ox), int(cy * s - oy)
    if image.mode == "RGBA":
        image.alpha_composite(tile, (max(0, left), max(0, upper)), (max(0, -left), max(0, -upper)))
    else:
        image.paste(tile, (left, upper), tile)


def body_color(pose):
    return mix(mix((255, 255, 255), pose["tint"], .55), (0, 0, 0), .06)


def heart(draw, x, y, r, fill):
    draw.ellipse((x - r, y - r * .9, x, y + r * .1), fill=fill)
    draw.ellipse((x, y - r * .9, x + r, y + r * .1), fill=fill)
    draw.polygon([(x - r * .98, y - r * .25), (x + r * .98, y - r * .25), (x, y + r * .95)], fill=fill)


def star(draw, x, y, r, fill, points=5, spin=0.):
    pts = []
    for k in range(points * 2):
        rad = r if k % 2 == 0 else r * .45
        a = spin + math.pi * k / points - math.pi / 2
        pts.append((x + rad * math.cos(a), y + rad * math.sin(a)))
    draw.polygon(pts, fill=fill)


def mouth(draw, x, y, w, pose, line):
    shape, k = pose["mouth"], pose["mouth_open"]
    m = w * .1
    fill = MOUTH + (255,)
    if shape == "smile":
        draw.arc((x - m, y - m * .6, x + m, y + m * .6), 20, 160, fill=fill, width=line)
    elif shape == "open":
        draw.chord((x - m, y - m * .4, x + m, y + m * (.4 + 1.2 * k)), 0, 180, fill=fill)
        draw.ellipse((x - m * .45, y + m * (.2 + .6 * k), x + m * .45, y + m * (.4 + 1.1 * k)), fill=(255, 120, 150, 255))
    elif shape in {"o", "yawn", "talk", "chomp"}:
        rw = m * (.45 if shape == "o" else .6 if shape == "talk" else .7)
        rh = m * (.3 + (1.6 if shape == "yawn" else 1.0) * k)
        draw.ellipse((x - rw, y - rh * .4, x + rw, y + rh), fill=fill)
    elif shape == "flat":
        draw.line((x - m * .6, y + m * .2, x + m * .6, y + m * .2), fill=fill, width=line)
    elif shape == "frown":
        draw.arc((x - m * .8, y + m * .1, x + m * .8, y + m * 1.0), 200, 340, fill=fill, width=line)
    elif shape == "wavy":
        pts = [(x - m + 2 * m * i / 10, y + m * .3 + m * .25 * math.sin(i * 1.6 + pose["t"] * 8)) for i in range(11)]
        draw.line(pts, fill=fill, width=line, joint="curve")
    elif shape == "cat":
        draw.arc((x - m * .9, y - m * .3, x, y + m * .5), 10, 170, fill=fill, width=line)
        draw.arc((x, y - m * .3, x + m * .9, y + m * .5), 10, 170, fill=fill, width=line)
    elif shape == "lid":
        # The box's open lid: a dark slot along the top that opens and closes.
        top = y - w * .48
        draw.rounded_rectangle((x - w * .4, top, x + w * .4, top + w * (.06 + .14 * k)), radius=int(w * .05), fill=(25, 22, 30, 255))


def wear(draw, item, bx, top, w, h, ex0, gap, eye_y, eye_w, eye_h, s, size, t):
    line = max(1, int(size * .03))
    if item in {"glasses", "sunglasses"}:
        r = eye_w * 2.1
        fill = (20, 20, 28, 230) if item == "sunglasses" else None
        for side_sign in (-1, 1):
            ex = ex0 + side_sign * gap
            draw.ellipse((ex - r, eye_y - r * .85, ex + r, eye_y + r * .85), outline=(60, 50, 40, 255), width=line, fill=fill)
        draw.line((ex0 - gap + r, eye_y, ex0 + gap - r, eye_y), fill=(60, 50, 40, 255), width=line)
    elif item == "headphones":
        draw.arc((bx - w * .55, top - h * .25, bx + w * .55, top + h * .7), 190, 350, fill=(60, 60, 75, 255), width=line * 2)
        for side_sign in (-1, 1):
            cx = bx + side_sign * w * .5
            draw.rounded_rectangle((cx - w * .09, top + h * .22, cx + w * .09, top + h * .55), radius=int(w * .05), fill=(255, 110, 140, 255))
    elif item == "beanie":
        draw.chord((bx - w * .42, top - h * .28, bx + w * .42, top + h * .36), 180, 360, fill=(90, 120, 210, 255))
        draw.rounded_rectangle((bx - w * .45, top + h * .02, bx + w * .45, top + h * .13), radius=int(h * .05), fill=(240, 240, 250, 255))
        draw.ellipse((bx - w * .08, top - h * .38, bx + w * .08, top - h * .2), fill=(240, 240, 250, 255))
    elif item == "santa":
        draw.polygon([(bx - w * .4, top + h * .08), (bx + w * .4, top + h * .08), (bx + w * .55, top - h * .35)], fill=(220, 40, 50, 255))
        draw.rounded_rectangle((bx - w * .45, top + h * .02, bx + w * .45, top + h * .15), radius=int(h * .06), fill=(250, 250, 250, 255))
        draw.ellipse((bx + w * .48, top - h * .43, bx + w * .64, top - h * .27), fill=(250, 250, 250, 255))
    elif item == "witch":
        draw.polygon([(bx - w * .25, top + h * .02), (bx + w * .25, top + h * .02), (bx + w * .12, top - h * .6)], fill=(110, 60, 170, 255))
        draw.ellipse((bx - w * .55, top - h * .02, bx + w * .55, top + h * .1), fill=(90, 45, 150, 255))
        draw.rectangle((bx - w * .24, top - h * .06, bx + w * .24, top + h * .0), fill=(255, 200, 80, 255))
    elif item == "party":
        draw.polygon([(bx - w * .2, top + h * .05), (bx + w * .2, top + h * .05), (bx + w * .05, top - h * .55)], fill=(255, 120, 200, 255))
        for k in range(3):
            y = top - h * (.05 + .17 * k)
            draw.line((bx - w * (.17 - .05 * k), y, bx + w * (.17 - .04 * k), y - h * .03), fill=(255, 240, 120, 255), width=line)
        draw.ellipse((bx + w * .0, top - h * .65, bx + w * .1, top - h * .55), fill=(255, 240, 120, 255))
    elif item == "crown":
        pts = [(bx - w * .3, top + h * .08), (bx - w * .3, top - h * .2), (bx - w * .15, top - h * .05), (bx, top - h * .28),
               (bx + w * .15, top - h * .05), (bx + w * .3, top - h * .2), (bx + w * .3, top + h * .08)]
        draw.polygon(pts, fill=(255, 205, 60, 255), outline=(200, 140, 20, 255))
        for k, color in enumerate(((240, 60, 90), (70, 140, 255), (90, 200, 120))):
            x = bx + w * (-.18 + .18 * k)
            draw.ellipse((x - w * .03, top - h * .04, x + w * .03, top + h * .03), fill=color + (255,))
    elif item == "bow":
        x, y = bx + w * .3, top + h * .05
        r = w * .1
        draw.polygon([(x, y), (x - r * 1.6, y - r), (x - r * 1.6, y + r)], fill=(255, 120, 170, 255))
        draw.polygon([(x, y), (x + r * 1.6, y - r), (x + r * 1.6, y + r)], fill=(255, 120, 170, 255))
        draw.ellipse((x - r * .4, y - r * .4, x + r * .4, y + r * .4), fill=(230, 80, 140, 255))


def badge(draw, kind, x, y, px, t):
    """Status pill at Pip's top left (x, y: its top-left corner)."""
    colors = {"dots": (120, 110, 255), "search": (90, 150, 255), "?": (40, 190, 210), "!": (255, 160, 40),
              "x": (240, 70, 80), "check": (60, 190, 120), "heart": (255, 90, 140), "note": (170, 110, 255),
              "z": (130, 130, 170)}
    color = colors.get(kind, (120, 120, 140)) + (255,)
    h = px * .2
    w = h * (2.0 if kind == "dots" else 1.0)
    draw.rounded_rectangle((x - w * .3, y - h * .55, x - w * .3 + w, y + h * .45), radius=int(h / 2), fill=(20, 20, 26, 255))
    draw.rounded_rectangle((x - w * .3 + h * .1, y - h * .45, x - w * .3 + w - h * .1, y + h * .35), radius=int(h / 2.5), fill=color)
    cx, cy = x - w * .3 + w / 2, y - h * .05
    if kind == "dots":
        for k in range(3):
            up = .25 * max(0., math.sin(t * 6 - k * .9))
            r = h * .11
            dx = (k - 1) * h * .42
            draw.ellipse((cx + dx - r, cy - r - up * h, cx + dx + r, cy + r - up * h), fill=(255, 255, 255, 255))
        return
    glyph = {"search": "⌕", "?": "?", "!": "!", "x": "✕", "check": "✓", "heart": "♥", "note": "♪", "z": "z"}.get(kind, "")
    face = font(h * .8, symbol=kind in {"search", "x", "check", "heart", "note"})
    box = draw.textbbox((0, 0), glyph, font=face)
    draw.text((cx - (box[0] + box[2]) / 2, cy - (box[1] + box[3]) / 2), glyph, font=face, fill=(255, 255, 255, 255))


def particles(draw, kind, bx, by, w, h, px, t):
    top = by - h / 2
    if kind == "hearts":
        for k in range(3):
            ph = (t * .55 + k / 3) % 1
            heart(draw, bx + (k - 1) * w * .45 + math.sin(t * 3 + k) * w * .06, top - ph * h * .9,
                  px * .07 * (1 - ph * .5), (255, 90, 140, int(255 * (1 - ph))))
    elif kind == "sparks":
        burst = (t % 3) / 3
        for k in range(8):
            a = k * math.pi / 4
            d = w * (.55 + .5 * burst)
            star(draw, bx + math.cos(a) * d, by + math.sin(a) * d * .8, px * .05 * (1 - burst), (255, 230, 110, int(255 * (1 - burst))), 4)
    elif kind == "stars" or kind == "orbit":
        for k in range(3):
            a = t * (3 if kind == "orbit" else 1) + k * 2.09
            star(draw, bx + math.cos(a) * w * .55, top + h * (.05 if kind == "orbit" else -.15) + math.sin(a) * h * .12,
                 px * .055, (255, 225, 90, 255), 5, spin=t)
    elif kind == "zzz":
        for k in range(3):
            ph = (t * .35 + k / 3) % 1
            face = font(px * (.14 + .1 * ph), bold=True)
            draw.text((bx + w * (.45 + .3 * ph), top - h * ph * .7), "z", font=face, fill=(200, 205, 240, int(255 * (1 - ph))))
    elif kind == "notes":
        for k in range(2):
            ph = (t * .5 + k / 2) % 1
            face = font(px * .2, symbol=True)
            draw.text((bx + (w * .55 if k else -w * .8) + math.sin(t * 4 + k) * w * .05, top - ph * h * .6), "♪♫"[k], font=face,
                      fill=(200, 170, 255, int(255 * (1 - ph))))
    elif kind == "sweat":
        ph = (t * .8) % 1
        x, y = bx + w * .42, top + h * (.15 + .3 * ph)
        r = px * .04
        draw.polygon([(x, y - r * 2), (x - r, y), (x + r, y)], fill=(140, 200, 255, 230))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(140, 200, 255, 230))
    elif kind == "tear":
        ph = (t * .6) % 1
        x, y = bx - w * .25, by + h * (.05 + .25 * ph)
        r = px * .03
        draw.ellipse((x - r, y - r * 1.4, x + r, y + r * 1.4), fill=(140, 200, 255, int(255 * (1 - ph))))
    elif kind == "confetti":
        for k in range(10):
            ph = (t * .7 + k / 10) % 1
            a = k * 2.4
            x = bx + math.cos(a) * w * (.3 + .5 * ph)
            y = top - h * .1 + ph * h * .8 - math.sin(a) * h * .3
            color = [(255, 110, 150), (110, 200, 255), (255, 220, 90), (140, 230, 160)][k % 4]
            draw.rectangle((x, y, x + px * .03, y + px * .015), fill=color + (int(255 * (1 - ph)),))
    elif kind == "steam":
        for k in range(2):
            ph = (t * .9 + k / 2) % 1
            x = bx + (k * 2 - 1) * w * .4
            r = px * (.03 + .05 * ph)
            draw.ellipse((x - r, top - ph * h * .4 - r, x + r, top - ph * h * .4 + r), fill=(235, 235, 245, int(200 * (1 - ph))))
    elif kind == "dots":
        for k in range(3):
            on = int(t * 3) % 4 > k
            if on:
                r = px * .025
                x, y = bx + w * (.55 + .12 * k), top - h * (.0 + .08 * k)
                draw.ellipse((x - r, y - r, x + r, y + r), fill=(210, 210, 225, 255))
    elif kind == "bubbles":
        for k in range(2):
            ph = (t * .6 + k / 2) % 1
            x, y = bx + w * (.6 + .1 * k), top + h * (.2 - .5 * ph)
            r = px * (.05 + .03 * k)
            draw.rounded_rectangle((x - r * 1.4, y - r, x + r * 1.4, y + r), radius=int(r), fill=(240, 240, 250, int(255 * (1 - ph))))
    elif kind == "page":
        fall = (t * .8) % 1
        x, y = bx, top - h * .5 + fall * h * .75
        r = px * .1 * (1 - fall * .8)
        if r > px * .02:
            draw.rectangle((x - r * .75, y - r, x + r * .75, y + r), fill=(255, 255, 255, 255), outline=(240, 80, 90, 255))
            draw.line((x - r * .4, y, x + r * .4, y), fill=(240, 80, 90, 255), width=max(1, int(px * .015)))


# --- the simple call the island uses -----------------------------------------------------------------------------
def draw_buddy(draw, cx, cy, size, mood="idle", t=0.0, sampling=1.0, look=None, pose=None):
    """Draw Pip on an ImageDraw's image. ``pose`` (from buddy_engine) wins over ``mood``."""
    paint(draw._image, cx, cy, size, pose or pose_for(mood, t, look), sampling)


MOODS = set(EMOTIONS)


def mood_for(phase):
    """Island card phase -> Pip's emotion."""
    return {"hungry": "hungry", "eating": "eating", "reading": "reading", "indexing": "reading", "ready": "question",
            "choose": "question", "preview": "approval", "thinking": "thinking", "drafting": "working",
            "sending": "working", "sent": "finished", "happy": "finished", "learned": "proud", "error": "sad",
            "sad": "sad", "sleepy": "sleeping", "learning": "searching"}.get(phase, "idle")
