"""Pip, the little friend who lives in the island: drawn with PIL so it stays sharp at any scale.

Moods: idle (bobbing, blinking, glancing around), hungry (a file is dragged over the island: mouth wide open),
eating (a page drops into its mouth, then chomping), reading (puffed cheeks, half-closed eyes, dots), thinking
(eyes up, "…" bubble), ready (waiting for an answer, little wave), happy (^ ^ eyes and floating hearts),
sad (droopy eyes, a tear), sleepy (closed eyes, a "z"). Everything is a pure function of the mood and the time,
so the island can redraw it every frame without state.
"""
import math

BODY, OUTLINE, EYE, BLUSH, MOUTH, HEART = "#fbfbff", "#d9dbe8", "#15151c", "#ffb3c7", "#3a2230", "#ff6b9a"
MOODS = {"idle", "hungry", "eating", "reading", "thinking", "ready", "happy", "sad", "sleepy"}


def blink(t, period=4.2):
    """True for a short moment every few seconds (with an occasional double blink)."""
    phase = t % period
    return phase < .12 or (int(t / period) % 3 == 0 and .24 < phase < .34)


def draw_buddy(draw, cx, cy, size, mood="idle", t=0.0, sampling=1.0, look=None):
    """Draw Pip centred at (cx, cy) in logical units; ``sampling`` converts to pixels."""
    mood = mood if mood in MOODS else "idle"
    s = sampling

    def box(x0, y0, x1, y1):
        return tuple(round(v * s) for v in (x0, y0, x1, y1))

    def width(value):
        return max(1, round(value * s))

    bob = {"idle": 1.2 * math.sin(t * 2.2), "hungry": 1.6 * math.sin(t * 9), "eating": 1.5 * abs(math.sin(t * 7)),
           "reading": .8 * math.sin(t * 3), "thinking": .6 * math.sin(t * 1.6), "ready": 2 * abs(math.sin(t * 3.2)),
           "happy": 3 * abs(math.sin(t * 5)), "sad": .4 * math.sin(t), "sleepy": 1 * math.sin(t * 1.1)}[mood]
    squash = {"eating": .06 * abs(math.sin(t * 7)), "happy": .05 * abs(math.sin(t * 5)), "hungry": .04}.get(mood, 0.)
    w = size * (1 + squash)
    h = size * .86 * (1 - squash)
    top = cy - h / 2 - bob
    left = cx - w / 2
    # Soft shadow, then the body (a rounded marshmallow).
    draw.ellipse(box(cx - w * .38, cy + h / 2 - size * .02, cx + w * .38, cy + h / 2 + size * .08), fill="#0d0d12")
    draw.rounded_rectangle(box(left, top, left + w, top + h), radius=round(size * .36 * s), fill=BODY,
                           outline=OUTLINE, width=width(size * .025))
    # Little arms: waving when ready or happy.
    if mood in {"ready", "happy", "hungry"}:
        wave = math.sin(t * (8 if mood != "ready" else 5)) * size * .08
        for side in (-1, 1):
            ax = cx + side * (w / 2 + size * .05)
            ay = top + h * .55 - (wave if side > 0 else -wave * .5)
            draw.ellipse(box(ax - size * .08, ay - size * .08, ax + size * .08, ay + size * .08), fill=BODY,
                         outline=OUTLINE, width=width(size * .02))
    if look is None:
        look = {"idle": .55 * math.sin(t * .7) + .25 * math.sin(t * 1.9), "thinking": .4, "reading": .25 * math.sin(t * 1.5),
                "ready": 0., "hungry": 0.}.get(mood, 0.)
    look_x = max(-1., min(1., look)) * size * .07
    look_y = -size * .05 if mood == "thinking" else size * .02 if mood == "reading" else 0.
    eye_y = top + h * .44 + look_y
    gap = size * .17
    eye_w, eye_h = size * .085, size * .13
    closed = blink(t) and mood in {"idle", "ready", "thinking", "hungry"}
    for side in (-1, 1):
        ex = cx + side * gap + look_x
        if mood == "happy":
            draw.arc(box(ex - eye_w * 1.2, eye_y - eye_h * .5, ex + eye_w * 1.2, eye_y + eye_h * .9), 200, 340,
                     fill=EYE, width=width(size * .045))
        elif mood == "sleepy" or closed:
            draw.line([tuple(round(v * s) for v in (ex - eye_w, eye_y)), tuple(round(v * s) for v in (ex + eye_w, eye_y))],
                      fill=EYE, width=width(size * .04))
        elif mood == "reading":
            draw.rounded_rectangle(box(ex - eye_w, eye_y - eye_h * .25, ex + eye_w, eye_y + eye_h * .45),
                                   radius=round(eye_w * s), fill=EYE)
        elif mood == "sad":
            draw.ellipse(box(ex - eye_w, eye_y - eye_h * .4, ex + eye_w, eye_y + eye_h * .6), fill=EYE)
            # Worried brows: the inner ends (towards the nose) are raised.
            draw.line([tuple(round(v * s) for v in (ex - eye_w * 1.4, eye_y - eye_h * (.6 if side < 0 else 1.1))),
                       tuple(round(v * s) for v in (ex + eye_w * 1.4, eye_y - eye_h * (1.1 if side < 0 else .6)))],
                      fill=EYE, width=width(size * .025))
        else:
            grow = 1.25 if mood == "hungry" else 1.
            draw.ellipse(box(ex - eye_w * grow, eye_y - eye_h * grow, ex + eye_w * grow, eye_y + eye_h * grow), fill=EYE)
            draw.ellipse(box(ex - eye_w * .2 + eye_w * .3, eye_y - eye_h * .55, ex + eye_w * .55, eye_y - eye_h * .15),
                         fill="#ffffff")
    # Cheeks.
    puff = 1.35 if mood in {"reading", "eating"} else 1.
    for side in (-1, 1):
        bx = cx + side * (gap + size * .12)
        by = eye_y + size * .12
        draw.ellipse(box(bx - size * .06 * puff, by - size * .035 * puff, bx + size * .06 * puff, by + size * .035 * puff),
                     fill=BLUSH)
    mouth_y = eye_y + size * .16
    if mood == "hungry":
        open_ = size * (.13 + .03 * math.sin(t * 9))
        draw.ellipse(box(cx - size * .1, mouth_y - open_ * .3, cx + size * .1, mouth_y + open_), fill=MOUTH)
    elif mood == "eating":
        chomp = abs(math.sin(t * 7)) * size * .1
        draw.ellipse(box(cx - size * .08, mouth_y - chomp * .3, cx + size * .08, mouth_y + chomp + size * .02), fill=MOUTH)
        # A little page falls into the mouth and shrinks.
        fall = (t * .8) % 1
        px, py, pw = cx + size * .02, top - size * .32 + fall * size * .55, size * .2 * (1 - fall * .8)
        if pw > size * .03:
            draw.rectangle(box(px - pw / 2, py - pw * .65, px + pw / 2, py + pw * .65), fill="#ffffff", outline="#ff5a5f",
                           width=width(size * .02))
            draw.line([tuple(round(v * s) for v in (px - pw * .3, py)), tuple(round(v * s) for v in (px + pw * .3, py))],
                      fill="#ff5a5f", width=width(size * .02))
    elif mood == "happy":
        draw.chord(box(cx - size * .1, mouth_y - size * .06, cx + size * .1, mouth_y + size * .1), 0, 180, fill=MOUTH)
    elif mood == "sad":
        draw.arc(box(cx - size * .08, mouth_y, cx + size * .08, mouth_y + size * .1), 200, 340, fill=MOUTH,
                 width=width(size * .03))
        drop = (t * .6) % 1
        tx, ty = cx - gap - size * .02, eye_y + size * .06 + drop * size * .18
        draw.ellipse(box(tx - size * .025, ty - size * .035, tx + size * .025, ty + size * .035), fill="#8ecbff")
    elif mood == "sleepy":
        draw.ellipse(box(cx - size * .03, mouth_y, cx + size * .03, mouth_y + size * .05), fill=MOUTH)
    else:
        smile = size * (.05 if mood in {"ready", "idle"} else .03)
        draw.arc(box(cx - size * .07, mouth_y - smile, cx + size * .07, mouth_y + smile), 20, 160, fill=MOUTH,
                 width=width(size * .03))
    # Extras floating around.
    if mood == "happy":
        for k in range(3):
            phase = (t * .7 + k / 3) % 1
            hx = cx + (k - 1) * size * .35 + math.sin(t * 3 + k) * size * .05
            hy = top - phase * size * .45
            r = size * .07 * (1 - phase * .5)
            if r > 0:
                draw.ellipse(box(hx - r, hy - r, hx, hy), fill=HEART)
                draw.ellipse(box(hx, hy - r, hx + r, hy), fill=HEART)
                draw.polygon([tuple(round(v * s) for v in p) for p in ((hx - r, hy - r * .45), (hx + r, hy - r * .45),
                                                                        (hx, hy + r * .8))], fill=HEART)
    elif mood == "thinking" or mood == "reading":
        for k in range(3):
            on = int(t * 3) % 4 > k
            dx = cx + w / 2 + size * (.1 + .12 * k)
            dy = top - size * (.02 + .07 * k)
            r = size * .035
            if on:
                draw.ellipse(box(dx - r, dy - r, dx + r, dy + r), fill="#c9c9d6")
    elif mood == "sleepy":
        z = (t * .5) % 1
        from PIL import ImageFont
        try:
            face = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", max(6, round(size * .28 * s)))
        except OSError:
            face = ImageFont.load_default()
        draw.text((round((cx + w / 2) * s), round((top - z * size * .3) * s)), "z", fill="#c9c9d6", font=face)


def mood_for(phase):
    """Island card phase -> Pip's mood."""
    return {"hungry": "hungry", "eating": "eating", "reading": "reading", "indexing": "reading", "ready": "ready",
            "choose": "ready", "preview": "ready", "thinking": "thinking", "drafting": "thinking", "sending": "thinking",
            "sent": "happy", "happy": "happy", "learned": "happy", "error": "sad", "sad": "sad",
            "sleepy": "sleepy"}.get(phase, "idle")
