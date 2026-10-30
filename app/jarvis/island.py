"""Native Dynamic Island layout, rendering and cancellable display-only motion."""
from functools import lru_cache
import math
import re
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont, ImageTk
from .display import window_scale

KEY = "#ff00ff"
BLACK = "#000000"
ACCENTS = {"STANDBY": "#b1b1bc", "LISTENING": "#8bdda8", "THINKING": "#b4a1ff",
           "WORKING": "#b4a1ff", "SPEAKING": "#b9c9ff", "ATTENTION": "#f1c580"}
SERVICE = {"youtube": ("#ff3b3b", "YouTube"), "spotify": ("#1ed760", "Spotify"), "whatsapp": ("#25d366", "WhatsApp"),
           "weather": ("#f5a623", "Weather"), "github": ("#a371f7", "GitHub"), "godseye": ("#ff9f1c", "God's Eye"),
           "buddy": ("#ff9ecb", "Pip"), "evolve": ("#5fd3bf", "Learning")}
WORKING = {"searching", "loading", "drafting", "sending", "choose", "learning", "opening", "eating", "reading", "indexing",
           "thinking"}  # Shimmer bar and pulsing meter.
MEDIA_HEIGHT = 126
MEDIA_PHASES = {"searching": "Searching", "loading": "Starting", "playing": "Playing", "paused": "Paused",
                "error": "Couldn't play", "control": "", "choose": "Choose who you mean", "drafting": "Drafting",
                "preview": "Waiting for your approval", "sending": "Sending", "sent": "Done", "call": "Incoming call",
                "message": "New message", "alert": "Weather alert", "notice": "Heads up", "learning": "Learning",
                "learned": "Learned and saved", "opening": "Opening", "showing": "On screen",
                "hungry": "Drop it here — I'll eat it!", "eating": "Nom nom…", "reading": "Reading it",
                "indexing": "Building its knowledge graph", "ready": "What should I do with it?", "thinking": "Thinking",
                "happy": "Done!", "sad": "Oops"}
from . import island_control as control
SERVICE.update(control.SERVICES)
MEDIA_PHASES.update(control.PHASES)
WORKING |= control.WORKING
BUDDY_TILE = (54, 54 + 54)  # Pip's square on the left of a card (x0, x1), top at card top + 8.


def clock_text(seconds):
    seconds = max(0, int(seconds or 0))
    return (f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}" if seconds >= 3600
            else f"{seconds // 60}:{seconds % 60:02d}")


@lru_cache(maxsize=16)
def artwork(encoded, side):
    """Rounded square artwork from a base64 JPEG/PNG (cached per frame size)."""
    import base64
    import io
    try:
        image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB").resize((side, side), Image.Resampling.LANCZOS)
    except Exception:
        return None
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=max(2, side // 7), fill=255)
    return image, mask


def media_progress(media, now=None):
    """Position advanced locally while playing, so the bar moves between updates."""
    position, duration = float(media.get("position") or 0), float(media.get("duration") or 0)
    if media.get("phase") == "playing":
        position += max(0., (time.time() if now is None else now) - float(media.get("at") or 0))
    return (min(position, duration) if duration else position), duration


@lru_cache(maxsize=64)
def font(size, bold=False):
    try:
        return ImageFont.truetype(str(Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf")), size)
    except OSError:
        return ImageFont.load_default()


def wrap(draw, text, face, width, lines=3):
    result, current = [], ""
    for word in str(text).split():
        test = (current + " " + word).strip()
        if current and draw.textlength(test, font=face) > width:
            result.append(current)
            current = word
        else:
            current = test
    if current:
        result.append(current)
    if len(result) > lines:
        result = result[:lines]
        result[-1] = result[-1].rstrip("., ") + "…"
    return result


def fit_text(draw, value, face, width):
    value = ' '.join(str(value).split())[:200]
    return _fit_text(value, face, width)


@lru_cache(maxsize=256)
def _fit_text(value, face, width):
    if width <= 0:
        return ''
    if face.getlength(value) <= width:
        return value
    low, high, best = 0, len(value), 0
    while low <= high:
        middle = (low+high)//2
        if face.getlength(value[:middle] + '…') <= width:
            best, low = middle, middle+1
        else:
            high = middle-1
    return value[:best].rstrip() + '…' if best else ''


@lru_cache(maxsize=256)
def _text_tile(value, size, color, bold):
    face = font(size, bold)
    bounds = face.getbbox(value)
    tile = Image.new('RGBA', (max(1, math.ceil(face.getlength(value)) + 4), max(1, bounds[3] + 4)))
    ImageDraw.Draw(tile).text((0, 0), value, font=face, fill=color)
    return tile


@lru_cache(maxsize=64)
def _curve_tiles(shoulder, radius):
    """Only supersample the small curves, never the full tall workspace."""
    factor = 4
    def tile(width, points):
        result = Image.new('L', (width * factor, radius * factor))
        ImageDraw.Draw(result).polygon([(round(x * factor), round(y * factor)) for x, y in points], fill=255)
        return result.resize((width, radius), Image.Resampling.LANCZOS)
    angles = [i * math.pi / 128 for i in range(65)]
    top = tile(shoulder, [(0, 0), (shoulder, 0), (shoulder, radius)] +
               [(shoulder * math.sin(a), radius * (1 - math.cos(a))) for a in reversed(angles)])
    bottom = tile(radius, [(0, 0), (radius, 0), (radius, radius)] +
                  [(radius - radius * math.cos(a), radius * math.sin(a)) for a in reversed(angles)])
    return top, top.transpose(Image.Transpose.FLIP_LEFT_RIGHT), bottom, bottom.transpose(Image.Transpose.FLIP_LEFT_RIGHT)


@lru_cache(maxsize=8)
def contour_mask(pixels_w, pixels_h, shoulder, radius):
    mask = Image.new('L', (pixels_w, pixels_h))
    draw = ImageDraw.Draw(mask)
    # Exclusive right/bottom bounds: an inclusive wall used to leave a 1px tail.
    draw.rectangle((shoulder, 0, pixels_w - shoulder - 1, pixels_h - radius - 1), fill=255)
    draw.rectangle((shoulder + radius, pixels_h - radius, pixels_w - shoulder - radius - 1, pixels_h - 1), fill=255)
    top_left, top_right, bottom_left, bottom_right = _curve_tiles(shoulder, radius)
    mask.paste(top_left, (0, 0))
    mask.paste(top_right, (pixels_w - shoulder, 0))
    mask.paste(bottom_left, (shoulder, pixels_h - radius))
    mask.paste(bottom_right, (pixels_w - shoulder - radius, pixels_h - radius))
    return mask


def status_amplitude(phase, index, level):
    return 2 + (5 + min(100, max(0, float(level)))*.055) * abs(math.sin(phase*2.8 + index*.65))


def media_amplitude(state, phase, index):
    if state in {'playing','call','alert'}:
        return 3 + 9*abs(math.sin(phase*3.1 + index*1.3))*(.6 + .4*abs(math.sin(phase*1.7 + index)))
    if state in {'preview','message'}:
        return 2 + 3*(.5 + .5*math.sin(phase*2.2 - index*.7))
    if state in WORKING:
        return 3 + 4*(.5 + .5*math.sin(phase*5 - index*.9))
    return 2


def animate_frame(base, width, height, status, phase, level, scale, media=None, buddy=None, live=None):
    """`live` is the current browser/PC-control card: its route badge replaces the status bars in the header."""
    """Redraw the small moving regions; reuse all text, artwork and static glass."""
    image = base.copy()
    sampling = scale*2
    def sketch(bounds, fill, paint):
        """Like patch(), for free drawing (Pip)."""
        left, top, right, bottom = bounds
        pixels = tuple(round(value*scale) for value in bounds)
        tile = Image.new('RGB', (round((right-left)*sampling), round((bottom-top)*sampling)), fill)
        paint(ImageDraw.Draw(tile), left, top)
        image.paste(tile.resize((pixels[2]-pixels[0],pixels[3]-pixels[1]),Image.Resampling.LANCZOS),(pixels[0],pixels[1]))
    from .island_buddy import draw_buddy, mood_for
    pose = buddy if isinstance(buddy, dict) else None
    if buddy:
        # Pip lives in its own tile in the bar (drawn only here, so particles never leave stale marks).
        sketch((38,0,80,40),BLACK,lambda draw,left,top:draw_buddy(draw,59-left,21-top,26,
            buddy if isinstance(buddy,str) else 'idle',phase,sampling,pose=pose))
    if media and media.get('service') == 'buddy':
        art_x, art_y = 44+10, 46+8
        sketch((art_x,art_y,art_x+54,art_y+54),'#1f1a24',lambda draw,left,top:draw_buddy(
            draw,art_x+27-left,art_y+30-top,40,mood_for(media.get('phase')),phase,sampling,pose=pose))
    def patch(bounds, fill, paint):
        left, top, right, bottom = bounds
        pixels = tuple(round(value*scale) for value in bounds)
        tile = Image.new('RGB', (round((right-left)*sampling), round((bottom-top)*sampling)), fill)
        draw = ImageDraw.Draw(tile)
        def rectangle(box, radius, color):
            draw.rounded_rectangle(tuple(round(value*sampling) for value in box),radius=round(radius*sampling),fill=color)
        paint(rectangle, left, top)
        tile = tile.resize((pixels[2]-pixels[0],pixels[3]-pixels[1]),Image.Resampling.LANCZOS)
        image.paste(tile,(pixels[0],pixels[1]))
    if live:
        # Route badge: spinning ring while working, outcome glyph after, step pips; visible even with the workspace open.
        sketch((width-118,10,width-80,32),BLACK,lambda draw,left,top:control.draw_badge(draw,width-118-left,10-top,
            live['service'],live.get('phase',''),phase,sampling,live.get('step',0),live.get('steps',0)))
    elif status != 'STANDBY':
        color = ACCENTS.get(status,ACCENTS['STANDBY'])
        def header(rectangle,left,top):
            for index in range(9):
                amplitude = status_amplitude(phase,index,level)
                x = width-116+index*4-left
                rectangle((x,21-amplitude-top,x+2,21+amplitude-top),1,color)
        patch((width-118,5,width-80,37),BLACK,header)
    if media:
        state = media.get('phase','playing')
        accent = SERVICE.get(media.get('service'),('#b9c9ff','Media'))[0]
        right, top, bottom = width-44,46,height-10
        meter_x = right-58
        routed = control.is_control(media)
        if routed:
            tile_x, tile_y = 44+10, 46+8
            sketch((tile_x,tile_y,tile_x+54,tile_y+54),'#111216',lambda draw,left,y:control.draw_tile(
                draw,tile_x-left,tile_y-y,54,media['service'],state,phase,sampling))
        def meter(rectangle,left,y):
            for index in range(5 if media.get('service') != 'buddy' and not routed else 0):
                amplitude = media_amplitude(state,phase,index)
                x = meter_x+8+index*8-left
                rectangle((x,top+28-amplitude-y,x+4,top+28+amplitude-y),2,accent)
        patch((meter_x+6,top+14,right-12,top+42),'#111216',meter)
        bar_x1, bar_x2, bar_y = 44+10+54+14,right-14,bottom-10
        def progress(rectangle,left,y):
            rectangle((bar_x1-left,bar_y-y,bar_x2-left,bar_y+4-y),2,'#2a2b32')
            done = control.fraction(media) if routed else None
            if done is not None:
                # Determinate step bar; the current step's segment shimmers while it runs.
                steps = max(1,int(media.get('steps') or 1))
                span = (bar_x2-bar_x1)/steps
                if done > 0:
                    rectangle((bar_x1-left,bar_y-y,bar_x1+(bar_x2-bar_x1)*done-left,bar_y+4-y),2,accent)
                if state in WORKING:
                    seg = bar_x1+(bar_x2-bar_x1)*done
                    glow = .35+.65*abs(math.sin(phase*3))
                    end = min(bar_x2,seg+span*glow)
                    if end > seg:
                        rectangle((seg-left,bar_y-y,end-left,bar_y+4-y),2,'#ffffff' if glow > .9 else accent)
            elif state in WORKING:
                sweep = (phase*.6)%1.4-.2
                start = bar_x1+(bar_x2-bar_x1)*max(0.,sweep)
                end = bar_x1+(bar_x2-bar_x1)*min(1.,sweep+.25)
                if end>start:
                    rectangle((start-left,bar_y-y,end-left,bar_y+4-y),2,accent)
            else:
                position,duration = media_progress(media)
                if duration:
                    fill = bar_x1+(bar_x2-bar_x1)*min(1.,position/duration)
                    rectangle((bar_x1-left,bar_y-y,max(bar_x1+4,fill)-left,bar_y+4-y),2,accent)
                    rectangle((fill-4-left,bar_y-2-y,fill+4-left,bar_y+6-y),4,'#ffffff')
        patch((bar_x1-5,bar_y-3,bar_x2+5,bar_y+7),'#111216',progress)
    return image


def render_island(width=208, height=52, status="STANDBY", phase=0, message="", level=0, expanded=False,
                  detail='', scale=1., media=None, smooth_edges=False, edge_threshold=128, buddy=None):
    width, height = max(170, float(width)), max(40, float(height))
    scale = min(3., max(1., float(scale))) if math.isfinite(float(scale)) else 1.
    sampling = scale * 2
    band_height = min(height, 128)
    image = Image.new("RGB", (round(width*sampling), round(band_height*sampling)), BLACK)
    draw = ImageDraw.Draw(image)
    def rectangle(bounds, radius, **kwargs):
        if 'width' in kwargs:
            kwargs['width'] = max(1, round(kwargs['width'] * sampling))
        draw.rounded_rectangle(tuple(round(x*sampling) for x in bounds), radius=round(radius*sampling), **kwargs)
    def text(x, y, value, size, color, bold=False):
        tile = _text_tile(str(value), round(size*sampling), color, bold)
        image.paste(tile, (round(x*sampling), round(y*sampling)), tile)
    # Concave shoulders attach to the screen edge; only the bottom is convex.
    shoulder, radius = 32, min(32, height/2)
    color = ACCENTS.get(status, ACCENTS["STANDBY"])
    y = 21
    if buddy:
        pass  # Pip, Jarvis's little friend, is drawn every frame by animate_frame (buddy_engine.py decides how).
    else:
        rectangle((47, 10, 69, 32), radius=11, fill='#1d3e66')
        rectangle((49, 11, 67, 29), radius=9, fill='#729fcb')
        text(54, 10, 'J', 12, '#ffffff', True)
    text(79, y-10, 'Jarvis', 12, '#e8e8e8', True)
    if width > 265:
        text(145, y-9, status.capitalize(), 11, color)
    if detail and width > 330:
        text(200, y-9, '·', 13, '#62626f')
        face = font(round(13*sampling))
        text(215, y-9, fit_text(draw, detail, face, (width-340)*sampling), 13, '#dedee6')
    active = status != "STANDBY"
    for i in range(9 if active else 0):
        amplitude = status_amplitude(phase,i,level)
        x = width-116+i*4
        rectangle((x, y-amplitude, x+2, y+amplitude), radius=1, fill=color)
    if expanded:
        rectangle((width-79, 7, width-51, 35), radius=14, fill='#24252a',outline='#44464e',width=1)
        rectangle((width-69, 17, width-61, 25), radius=1, fill='#d8d8d8')
        rectangle((width-50, 9, width-34, 33),radius=8,fill='#202126',outline='#35363d',width=1)
        draw.line([(round(x*sampling), round(y*sampling)) for x,y in
                   ((width-47,24),(width-43,20),(width-39,24))], fill='#aaaaaa', width=max(1,round(sampling)))
    if media and height >= MEDIA_HEIGHT - 4:
        # Animated YouTube/Spotify card: artwork, title, artist, live progress and equalizer.
        accent, label = SERVICE.get(media.get("service"), ("#b9c9ff", "Media"))
        left, top, right, bottom = 44, 46, width - 44, height - 10
        rectangle((left, top, right, bottom), radius=16, fill="#111216", outline=accent, width=1)
        side = 54
        art_x, art_y = left + 10, top + 8
        art = artwork(media.get("image", ""), round(side * sampling)) if media.get("image") else None
        if art:
            image.paste(art[0], (round(art_x * sampling), round(art_y * sampling)), art[1])
        elif media.get("service") == "weather":
            # Pulsing warning triangle.
            glow = 2 * abs(math.sin(phase * 3))
            rectangle((art_x, art_y, art_x + side, art_y + side), radius=10, fill="#3a2a10")
            points = ((art_x + side / 2, art_y + 9 - glow), (art_x + side - 8 + glow, art_y + side - 11 + glow / 2),
                      (art_x + 8 - glow, art_y + side - 11 + glow / 2))
            draw.polygon([tuple(round(v * sampling) for v in p) for p in points], fill=accent)
            text(art_x + side / 2 - 3, art_y + side / 2 - 11, "!", 20, "#2a1a00", True)
        elif media.get("service") == "godseye":
            # Radar scope with a sweeping beam.
            rectangle((art_x, art_y, art_x + side, art_y + side), radius=10, fill="#2a1a06")
            cx, cy, r = art_x + side / 2, art_y + side / 2, side / 2 - 7
            for k in (1, .62, .3):
                draw.ellipse(tuple(round(v * sampling) for v in (cx - r * k, cy - r * k, cx + r * k, cy + r * k)),
                             outline=accent, width=max(1, round(1.2 * sampling)))
            angle = phase * 2.4
            draw.line([tuple(round(v * sampling) for v in (cx, cy)),
                       tuple(round(v * sampling) for v in (cx + r * math.cos(angle), cy + r * math.sin(angle)))],
                      fill="#ffe0a8", width=max(1, round(2 * sampling)))
            blip = (cx + r * .55 * math.cos(1.1), cy + r * .55 * math.sin(1.1))
            rectangle((blip[0] - 2, blip[1] - 2, blip[0] + 2, blip[1] + 2), radius=2, fill="#ffffff")
        elif media.get("service") == "github":
            # Code tile: angle brackets that pulse while learning.
            rectangle((art_x, art_y, art_x + side, art_y + side), radius=10, fill="#241a3a")
            spread = 2 * abs(math.sin(phase * 3)) if media.get("phase") == "learning" else 0
            text(art_x + 9 - spread, art_y + side / 2 - 14, "<", 22, accent, True)
            text(art_x + side - 21 + spread, art_y + side / 2 - 14, ">", 22, accent, True)
            text(art_x + side / 2 - 4, art_y + side / 2 - 14, "/", 22, "#e6dcff", True)
        elif media.get("service") == "evolve":
            # Learning tile: a central node with spokes that pulse outward while Jarvis studies.
            rectangle((art_x, art_y, art_x + side, art_y + side), radius=10, fill="#10241f")
            cx, cy = art_x + side / 2, art_y + side / 2
            pulse = 1 + (.5 * abs(math.sin(phase * 3)) if media.get("phase") == "learning" else 0)
            for i in range(6):
                a = phase * .8 + i * math.pi / 3
                ex, ey = cx + 13 * pulse * math.cos(a), cy + 13 * pulse * math.sin(a)
                draw.line([tuple(round(v * sampling) for v in (cx, cy)), tuple(round(v * sampling) for v in (ex, ey))],
                          fill=accent, width=max(1, round(1.4 * sampling)))
                draw.ellipse(tuple(round(v * sampling) for v in (ex - 2, ey - 2, ex + 2, ey + 2)), fill="#d7fff4")
            draw.ellipse(tuple(round(v * sampling) for v in (cx - 5, cy - 5, cx + 5, cy + 5)), fill=accent)
        elif control.is_control(media):
            rectangle((art_x, art_y, art_x + side, art_y + side), radius=10, fill=control.TILE_FILL[media["service"]])
        elif media.get("service") == "buddy":
            from .island_buddy import draw_buddy, mood_for
            # The tile; Pip on it is drawn every frame by animate_frame.
            tile = Image.new("RGB", (round(side * sampling), round(side * sampling)), "#1f1a24")
            if not buddy:
                draw_buddy(ImageDraw.Draw(tile), side / 2, side / 2 + 3, 40, mood_for(media.get("phase")), phase, sampling)
            image.paste(tile, (round(art_x * sampling), round(art_y * sampling)))
        elif media.get("service") == "whatsapp":
            # Contact avatar: initials on a soft green tile; it pulses while a call rings.
            ring = 3 * abs(math.sin(phase * 4)) if media.get("phase") == "call" else 0
            if ring:
                rectangle((art_x - ring, art_y - ring, art_x + side + ring, art_y + side + ring), radius=10 + ring,
                          fill=None, outline=accent, width=2)
            rectangle((art_x, art_y, art_x + side, art_y + side), radius=10, fill="#17392a")
            initials = "".join(w[0] for w in re.findall(r"[^\W\d_]+", media.get("title") or "")[:2]).upper() or "W"
            initials = "?" if media.get("phase") == "choose" else initials
            face_initials = font(round(20 * sampling), True)
            width_initials = draw.textlength(initials, font=face_initials) / sampling
            text(art_x + (side - width_initials) / 2, art_y + side / 2 - 13, initials, 20, "#b8f5cf", True)
        else:
            rectangle((art_x, art_y, art_x + side, art_y + side), radius=8, fill="#1e1f25")
        # Service badge on the artwork corner.
        bx, by = art_x + side - 16, art_y + side - 16
        if media.get("service") in {"weather", "github", "godseye", "buddy", "evolve"} or control.is_control(media):
            pass  # The tile itself is the badge.
        elif media.get("service") == "whatsapp":
            # Speech bubble with a handset, drawn as simple shapes.
            rectangle((bx, by, bx + 20, by + 20), radius=10, fill=accent)
            draw.polygon([tuple(round(v * sampling) for v in point) for point in
                          ((bx + 2, by + 19), (bx + 4, by + 13), (bx + 8, by + 17))], fill=accent)
            draw.ellipse(tuple(round(v * sampling) for v in (bx + 4, by + 4, bx + 16, by + 16)),
                         outline="#ffffff", width=max(1, round(1.4 * sampling)))
            draw.arc(tuple(round(v * sampling) for v in (bx + 7, by + 7, bx + 13, by + 13)), 100, 260,
                     fill="#ffffff", width=max(1, round(1.6 * sampling)))
        elif media.get("service") == "spotify":
            rectangle((bx, by, bx + 20, by + 20), radius=10, fill=accent)
            for i, (w, t) in enumerate(((12, 1.6), (10, 1.4), (7, 1.2))):
                y0 = by + 6 + i * 3.6
                draw.arc(tuple(round(v * sampling) for v in (bx + 10 - w / 2, y0, bx + 10 + w / 2, y0 + 7)),
                         200, 340, fill="#0b0b0b", width=max(1, round(t * sampling)))
        else:
            rectangle((bx - 3, by + 2, bx + 23, by + 19), radius=6, fill=accent)
            draw.polygon([tuple(round(v * sampling) for v in point) for point in
                          ((bx + 7, by + 6), (bx + 7, by + 15), (bx + 15, by + 10.5))], fill="#ffffff")
        text_x = art_x + side + 14
        meter_x = right - 58
        face_title, face_sub = font(round(13 * sampling), True), font(round(11 * sampling))
        text(text_x, top + 3, fit_text(draw, media.get("title") or label, face_title, (meter_x - text_x - 6) * sampling),
             13, "#f2f2f6", True)
        text(text_x, top + 21, fit_text(draw, media.get("subtitle", ""), face_sub, (meter_x - text_x - 6) * sampling),
             11, "#a7a8b3")
        state = media.get("phase", "playing")
        caption = media.get("detail") or MEDIA_PHASES.get(state, "")
        caption = (caption + " on " + label) if state in {"searching", "loading"} and media.get("service") != "whatsapp" else caption
        text(text_x, top + 37, fit_text(draw, caption, face_sub, (meter_x - text_x - 6) * sampling), 11,
             "#ff8a80" if state == "error" else accent)
        # Equalizer: live bars while playing, a gentle pulse while searching, flat when paused (not on Pip's cards).
        for i in range(5 if media.get("service") != "buddy" and not control.is_control(media) else 0):
            amplitude = media_amplitude(state,phase,i)
            x = meter_x + 8 + i * 8
            rectangle((x, top + 28 - amplitude, x + 4, top + 28 + amplitude), radius=2, fill=accent)
        # Progress bar (or a moving shimmer while searching).
        bar_y, bar_x1, bar_x2 = bottom - 10, text_x, right - 14
        rectangle((bar_x1, bar_y, bar_x2, bar_y + 4), radius=2, fill="#2a2b32")
        if control.is_control(media):
            stamp = control.step_text(media)
            if stamp:
                face_time = font(round(9 * sampling))
                text(bar_x2 - draw.textlength(stamp, font=face_time) / sampling, top + 39, stamp, 9, "#8e8f9a")
        elif state in WORKING:
            sweep = (phase * 0.6) % 1.4 - 0.2
            start = bar_x1 + (bar_x2 - bar_x1) * max(0., sweep)
            end = bar_x1 + (bar_x2 - bar_x1) * min(1., sweep + 0.25)
            if end > start:
                rectangle((start, bar_y, end, bar_y + 4), radius=2, fill=accent)
        else:
            position, duration = media_progress(media)
            if duration:
                fill = bar_x1 + (bar_x2 - bar_x1) * min(1., position / duration)
                rectangle((bar_x1, bar_y, max(bar_x1 + 4, fill), bar_y + 4), radius=2, fill=accent)
                rectangle((fill - 4, bar_y - 2, fill + 4, bar_y + 6), radius=4, fill="#ffffff")
                stamp = clock_text(position) + " / " + clock_text(duration)
                face_time = font(round(9 * sampling))
                text(bar_x2 - draw.textlength(stamp, font=face_time) / sampling, top + 39, stamp, 9, "#8e8f9a")
    if height > 82 and not expanded and not media:
        # Content appears immediately; decorative motion never delays an answer.
        for i, line in enumerate(wrap(draw, message, font(round(14*sampling)), (width-48)*sampling, 3)):
            text(24, 56+i*21, line, 14, '#dedee6')
    pixels_w,pixels_h = round(width*scale),round(height*scale)
    band = image.resize((pixels_w,round(band_height*scale)), Image.Resampling.LANCZOS)
    image = Image.new('RGB',(pixels_w,pixels_h),BLACK)
    image.paste(band,(0,0))
    mask = contour_mask(pixels_w, pixels_h, round(shoulder*scale), round(radius*scale))
    if smooth_edges:
        output = image.convert('RGBA')
        output.putalpha(mask)
        return output
    # With the native edge layer, only fully covered pixels belong to Tk. Other
    # platforms retain the thresholded color-key fallback with the corrected shape.
    output = Image.new('RGB', image.size, KEY)
    mask = mask.point(lambda alpha: 255 if alpha >= edge_threshold else 0)
    output.paste(image, (0, 0), mask)
    return output


class Activity:
    """UI metadata only; never use displayed text as task execution authority."""
    def __init__(self):
        self.detail = ''
        self.updated = 0.
        self.active = False

    def notify(self, kind, value, now=None):
        now = time.monotonic() if now is None else now
        if kind == 'answer_stream' and isinstance(value, dict):
            self.detail = value.get('phase', '')[:100]
            self.active = value.get('active', True)
            self.updated = now
        elif kind in {'answer', 'answer_error'}:
            self.active = False
            self.detail = ''
        elif kind == 'task_status' and isinstance(value, dict):
            from pathlib import PureWindowsPath
            from .obsidian_memory import clean
            phase = clean(value.get('phase', ''), 40)
            target = str(value.get('target', ''))
            if '/' in target or '\\' in target:
                target = PureWindowsPath(target).name
            target = clean(target, 70)
            self.detail = ' · '.join(part for part in (phase, target) if part)
            self.active = bool(value.get('active', True))
            self.updated = now
        elif kind in {'brain', 'tool', 'plan'} and isinstance(value, str):
            from .obsidian_memory import clean
            self.detail = clean(value, 110)
            self.updated = now

    def caption(self, status, now=None, speaking=False, listening=False):
        now = time.monotonic() if now is None else now
        if self.detail and (self.active or now-self.updated < 7):
            detail = self.detail
        else:
            detail = {'LISTENING': 'Ready for a command', 'WORKING': 'Executing your task',
                      'THINKING': 'Preparing an answer', 'SPEAKING': 'Listening for “Jarvis …”' if listening else 'Replying',
                      'STANDBY': ''}.get(status, '')
        if speaking and status in {'WORKING', 'THINKING'}:
            detail += ' · Speaking'
        return detail


class Morph:
    def __init__(self):
        self.size = (402., 40.)
        self.origin = self.target = self.size
        self.started = 0.

    def set_target(self, size, now):
        if tuple(size) != self.target:
            self.origin = self.sample(now)
            self.target = tuple(size)
            self.started = now

    def sample(self, now, reduced=False):
        p = 1 if reduced else min(1, max(0, (now-self.started)/.34))
        eased = 1-(1-p)**4
        self.size = tuple(a+(b-a)*eased for a, b in zip(self.origin, self.target))
        return self.size


class FrameClock:
    """Deadline pacing: render cost is inside the frame budget, no catch-up bursts."""
    def __init__(self):
        self.deadline = None
        self.period = None

    def delay(self, started, finished, fps):
        period = 1. / max(1., fps)
        if self.deadline is None or self.period != period:
            self.deadline = started + period
            self.period = period
        else:
            self.deadline += period
        if self.deadline <= finished:
            self.deadline += (math.floor((finished - self.deadline) / period) + 1) * period
        return max(1, math.ceil((self.deadline - finished) * 1000 - 1e-7))


class Island:
    def __init__(self, app, canvas):
        self.app, self.canvas = app, canvas
        self.motion = Morph()
        self.expanded = self.hover = False
        self.media, self.media_until = None, 0.
        self.message = ""
        self.activity = Activity()
        self.message_until = 0.
        self.attention_until = 0.
        self.anchor_x = app.root.winfo_screenwidth() // 2
        self.top = 0
        self.drag = None
        self.moved = False
        self.last_frame = None
        self.last_geometry = None
        self.last_size = None
        self.background_key = None
        self.static_key = None
        self.surface_open = False
        self.features_open = False
        self.focus_pending = False
        self.stream_active = False
        self.stream_hidden = False
        self.stream_height = 0
        self.work_completion_pending = False
        self.buddy = bool(app.config.get("ui", {}).get("buddy", True))  # Pip lives in the island.
        self.hungry_until = 0.
        self.pip = None
        if self.buddy:
            try:
                from .buddy_engine import Buddy
                self.pip = Buddy(app.config.get("buddy", {}), sense=app.config.get("_ui_verification", False) is not True)
            except Exception:
                self.pip = None  # Pip must never stop the island from starting.
        self.emotion = "idle"
        self.last_active = time.monotonic()
        self.drop_target = None
        from .island_surface import EdgeSurface, AnimationTimer
        self.edges = EdgeSurface(app.root)
        self.animation_timer = AnimationTimer() if isinstance(app.root.winfo_id(), int) else None
        self.item = canvas.create_image(0, 0, anchor="nw")
        self.header_item = canvas.create_image(0, 0, anchor='nw')
        canvas.bind("<Enter>", lambda _e: self.set_hover(True))
        canvas.bind("<Leave>", lambda _e: self.set_hover(False))
        canvas.bind("<Button-1>", self.press)
        canvas.bind("<B1-Motion>", self.move)
        canvas.bind("<ButtonRelease-1>", self.release)
        canvas.bind("<Button-3>", app.show_menu)
        canvas.bind("<Double-Button-1>", self.double_click)
        canvas.bind("<Motion>", self.pointer)

    def set_hover(self, value):
        self.hover = value

    def on_pip(self, event):
        """Is the pointer on Pip (in the bar, or on its card)?"""
        if self.pip is None:
            return False
        scale = window_scale(self.app.root)
        x, y = event.x / scale, event.y / scale
        if 38 <= x <= 80 and y <= 40:
            return True
        media = self.media if self.media and time.monotonic() < self.media_until else None
        return bool(media and media.get('service') == 'buddy' and 54 <= x <= 108 and 54 <= y <= 108)

    def pointer(self, event):
        if self.on_pip(event):
            self.pip.hover()

    def double_click(self, event):
        if self.on_pip(event):
            self.pip.pet()

    def press(self, event):
        self.drag = (event.x_root, event.y_root, self.anchor_x, self.top)
        self.moved = False

    def move(self, event):
        if self.drag:
            x, y, anchor, top = self.drag
            if abs(event.x_root-x)+abs(event.y_root-y) > 5:
                self.moved = True
                if self.pip is not None:
                    self.pip.drag()  # Whee!
                self.anchor_x = anchor+event.x_root-x
                self.top = 0  # The notch stays attached even when moved horizontally.

    def release(self, event):
        if self.drag and not self.moved:
            scale = window_scale(self.app.root)
            x = event.x/scale
            width = self.motion.size[0]
            if self.surface_open and width-79 <= x <= width-51:
                self.app.stop()
            elif self.surface_open and x > width-51:
                self.app.hide_panel()
            elif self.on_pip(event):
                self.pip.poke()  # Boop! (Clicking anywhere else on the island still opens the panel.)
            else:
                self.app.toggle_panel(event)
        self.drag = None

    def expand(self, value):
        self.stream_hidden = not value
        if not value:
            self.stream_height = 0
        if value == self.expanded:
            return
        self.expanded = value
        self.focus_pending = value
        if not value:
            self.app.panel.withdraw()
            self.features_open = False
            self.message_until = self.attention_until = 0.
        self.last_frame = None

    def notify(self, kind, message):
        self.activity.notify(kind, message)
        if kind == 'voice_transcript' and isinstance(message, dict):
            self.voice_language = message.get('language', 'en').upper()
            self.message = str(message.get('text', ''))[:450]
            self.message_until = time.monotonic() + 3
        elif kind == 'voice_interrupt':
            self.message = 'User interrupting · ' + str(message).lower()
            self.message_until = time.monotonic() + 3
        if self.pip is not None:
            self.pip.event(kind, message)  # Pip reacts to what Jarvis does.
        if kind == 'media_card' and isinstance(message, dict):
            # Shown while a media command runs and briefly after; never blocks other content.
            self.media = message
            self.media_until = time.monotonic() + {'searching': 40, 'loading': 40, 'playing': 10, 'paused': 6,
                                                   'control': 6, 'choose': 120, 'drafting': 90, 'preview': 180,
                                                   'sending': 30, 'sent': 8, 'call': 45, 'message': 15,
                                                   'error': 8, 'alert': 45, 'notice': 20, 'learning': 900,
                                                   'learned': 20, 'opening': 60, 'showing': 12, 'hungry': 1.2,
                                                   'eating': 60, 'reading': 120, 'indexing': 600, 'ready': 180,
                                                   'thinking': 120, 'happy': 10, 'sad': 10,
                                                   **(control.SHOW_SECONDS if control.is_control(message) else {})
                                                   }.get(message.get('phase'), 6)
            self.last_frame = None
            return
        if kind == 'task_status' and isinstance(message, dict) and message.get('reveal') is True and message.get('active'):
            # Reveal once at task start without taking typing focus. Subsequent
            # stream updates respect a user's deliberate collapse.
            self.expanded = True
            self.stream_hidden = False
            self.stream_height = 0
            self.focus_pending = False
            self.work_completion_pending = True
            self.last_frame = None
        if kind == 'answer_stream' and isinstance(message, dict):
            active = message.get('active', True)
            if active and not self.stream_active:
                self.stream_hidden = False
                self.stream_height = 0
                self.work_completion_pending = False
            self.stream_active = active
            self.message = (message.get('text') or message.get('phase', 'Generating answer'))[:450]
            self.message_until = time.monotonic()+12
        elif kind in {"answer", "answer_error", "spoken_reply", "question", "warning", "fatal", "action", "command_output"} and message:
            if kind in {'answer', 'answer_error'}:
                if not self.stream_active and not getattr(self,'work_completion_pending',False):
                    self.stream_height = 0
                    self.stream_hidden = False  # A fresh non-streamed answer may reveal itself normally.
                self.stream_active = False
                self.work_completion_pending = False
            self.message = str(message)[:450]
            self.message_until = time.monotonic()+12
            if kind in {"warning", "fatal", "question"}:
                self.attention_until = self.message_until
        elif kind == "partial" and message:
            self.message = str(message)[:450]
            self.message_until = time.monotonic()+3

    def layout_target(self, message, detail, status, max_width, max_height):
        desk = self.app.desk
        if (self.media and time.monotonic() < self.media_until and not self.expanded and not self.features_open
                and desk.view == 'Overview' and not desk.work.get('active') and not self.stream_active):
            return (min(560, max_width), MEDIA_HEIGHT), False, False
        workspace = self.features_open or desk.view != 'Overview' or desk.has_reply or desk.work['active'] or getattr(self,'work_completion_pending',False)
        opened = self.expanded or (not self.stream_hidden and (bool(message) or self.stream_active))
        if opened:
            if workspace:
                content = desk.reply + desk.work.get('preview', '')
                lines = sum(max(1, math.ceil(len(line)/60)) for line in content.splitlines())
                height = 660 if self.features_open or desk.view != 'Overview' else min(710, max(380, 230+lines*18))
                if not self.features_open and desk.view == 'Overview':
                    # Draft replacement, token gaps and final formatting never collapse a live answer.
                    height = max(height, self.stream_height)
                    if self.stream_active or desk.work.get('active'):
                        self.stream_height = height
            else:
                height = 144
            return (min(614, max_width), min(height, max_height)), workspace, opened
        return (min(614 if detail else 434 if self.hover or status != 'STANDBY' else 402, max_width),
                64 if detail else 44 if self.hover or status != 'STANDBY' else 40), False, False

    def tick(self, status, level=0, speaking=False, listening=False):
        app, root = self.app, self.app.root
        now = time.monotonic()
        if self.surface_open and self.hover and not self.expanded and self.message_until:
            self.message_until = max(self.message_until, now+12)
        if now < self.attention_until and status == "STANDBY":
            status = "ATTENTION"
        if status != "STANDBY":
            self.last_active = now
        if self.drop_target is not None:
            self.drop_target.poll()  # Files dropped on the island, handed over safely on the Tk loop.
        self.watch_drag(now)
        message = self.message if now < self.message_until else ""
        scale = window_scale(root)
        detail = self.activity.caption(status, now, speaking, listening)
        if listening and getattr(self, 'voice_language', None):
            detail += ' · ' + self.voice_language
        max_width = max(170, root.winfo_screenwidth()/scale-12)
        max_height = max(180, root.winfo_screenheight()/scale-70)
        target, workspace, self.surface_open = self.layout_target(message, detail, status, max_width, max_height)
        self.motion.set_target(target, now)
        reduced = bool(app.config.get("ui", {}).get("reduced_motion", False))
        width, height = self.motion.sample(now, reduced)
        pixels_w, pixels_h = round(width*scale), round(height*scale)
        left = max(0, min(root.winfo_screenwidth()-pixels_w, round(self.anchor_x-pixels_w/2)))
        top = 0
        if app.config.get('_ui_verification', False):
            left = top = 20000
        geometry = f"{pixels_w}x{pixels_h}+{left}+{top}"
        if geometry != self.last_geometry:
            root.geometry(geometry)
            self.last_geometry = geometry
        if (pixels_w, pixels_h) != self.last_size:
            self.canvas.configure(width=pixels_w, height=pixels_h)
            self.last_size = (pixels_w, pixels_h)
        settled = abs(width-target[0])+abs(height-target[1]) <= 2
        phase = 0 if reduced or status == "STANDBY" else now
        media = self.media if self.media and now < self.media_until and height >= MEDIA_HEIGHT - 4 and not self.surface_open else None
        live = self.media if control.is_control(self.media) and now < self.media_until and not media else None
        if live and not reduced:
            phase = now  # The route badge animates even when Jarvis's status is idle.
        if media:
            phase = 0 if reduced else now  # The card animates even while Jarvis is otherwise idle.
        mood = self.buddy_pose(now, status, speaking, listening) if self.pip is not None else None
        if mood and not reduced and phase == 0:
            phase = round(now * 15) / 15  # Pip keeps moving in standby, at about 15 frames a second.
        frame_key = (pixels_w, pixels_h, status, message, detail, scale, phase, round(float(level)), self.surface_open,
                     id(media), round(time.time()) if media else 0, self.edges.active, self.emotion if mood else None)
        if frame_key != self.last_frame:
            geometry_key = (pixels_w,pixels_h,scale,self.surface_open,self.edges.active)
            static_key = (geometry_key,status,detail,id(media),int(time.time()) if media else 0)
            complex_art = bool(media and (media.get('service')=='weather' or
                (media.get('service')=='whatsapp' and media.get('phase')=='call')))
            compact = height <= 96 or bool(media)
            if height <= 96 or geometry_key != self.background_key or media:
                if static_key != self.static_key or complex_art:
                    self.static_image = render_island(width,height,status,phase if complex_art else 0,'',
                        level,self.surface_open,detail,scale,media,edge_threshold=255 if self.edges.active else 128,buddy=mood)
                    self.static_key = static_key
                self.preview_image = (animate_frame(self.static_image,width,height,status,phase,level,scale,media,mood,live)
                                      if not complex_art else self.static_image)
                self.background_image = self.preview_image
                self.photo = ImageTk.PhotoImage(self.preview_image, master=root)
                self.canvas.itemconfigure(self.item, image=self.photo)
                self.canvas.itemconfigure(self.header_item,image='')
                self.background_key = geometry_key
            else:
                # A settled tall shell is static; redraw only its live top band.
                if static_key != self.static_key or self.static_image.height != round(44*scale):
                    self.static_image = render_island(width,96,status,0,'',level,self.surface_open,detail,scale,
                        edge_threshold=255 if self.edges.active else 128,buddy=mood).crop((0,0,pixels_w,round(44*scale)))
                    self.static_key = static_key
                header = animate_frame(self.static_image,width,96,status,phase,level,scale,buddy=mood,live=live)
                self.header_photo = ImageTk.PhotoImage(header,master=root)
                self.canvas.itemconfigure(self.header_item,image=self.header_photo)
                self.preview_image = self.background_image
                self.preview_image.paste(header,(0,0))
            self.canvas.preview_image = self.preview_image
            self.last_frame = frame_key
        mask = contour_mask(pixels_w, pixels_h, round(32*scale), round(min(32, height/2)*scale))
        self.edges.present(mask, left, top, float(app.config.get('ui', {}).get('opacity', 1.)),
                           root.state() != 'withdrawn' and not getattr(app, 'capture_count', 0))
        if self.surface_open and height >= 135 and not getattr(app, "capture_count", 0) and root.state() != "withdrawn":
            app.panel.present(width, height, workspace)
            if app.panel.state() == "withdrawn":
                app.panel.deiconify()
                app.panel.lift()
            if self.focus_pending and settled:
                grab = root.grab_current()
                focus = root.focus_get()
                interactive = focus is not None and focus.winfo_class() in {'TCombobox', 'Entry', 'TEntry', 'Text', 'Button', 'TButton'}
                if grab is not None:
                    return  # Preserve native combobox/menu selection until its grab ends.
                self.focus_pending = False
                if interactive:
                    return
                if getattr(getattr(app,'desk',None),'view',None)=='Games':
                    app.desk.game_canvas.focus_set()
                elif app.desk.view == 'Console':
                    app.command_entry.focus_set()
                else:
                    app.preview.focus_set()
        else:
            app.panel.withdraw()

    def buddy_pose(self, now, status, speaking, listening):
        """Ask Pip's brain (buddy_engine.py) for this frame's emotion and pose; its eyes follow the pointer."""
        look = None
        try:
            import win32api
            root = self.app.root
            scale = window_scale(root)
            cursor = win32api.GetCursorPos()
            from .buddy_engine import look_at
            look = look_at(cursor, (root.winfo_rootx() + 59 * scale, root.winfo_rooty() + 21 * scale))
        except Exception:
            pass
        media = self.media if self.media and now < self.media_until else None
        card_phase = media.get('phase') if media and media.get('service') == 'buddy' else None
        actions = getattr(self.app, 'actions', None)
        question = bool(getattr(actions, 'whatsapp_prompts', None))
        approval = bool(getattr(getattr(self.app, 'desk', None), 'approvals', None))
        try:
            self.emotion, pose = self.pip.update(now, status, speaking, listening, card_phase, question, approval, look)
        except Exception:
            self.emotion, pose = 'idle', None  # Pip must never take the island down.
        return pose or 'idle'

    def watch_drag(self, now):
        """A file dragged over the island (left button held, pointer over it, drag started elsewhere): Pip gets hungry.
        Windows only reports the drop itself, so this is how Pip knows to open its mouth."""
        if not self.buddy or self.drag is not None or self.drop_target is None:
            return
        try:
            import win32api
            if not win32api.GetAsyncKeyState(0x01) & 0x8000:
                return
            x, y = win32api.GetCursorPos()
            root = self.app.root
            left, top = root.winfo_rootx(), root.winfo_rooty()
            if left <= x <= left + root.winfo_width() and top <= y <= top + root.winfo_height() + 30:
                self.last_active = now
                if self.pip is not None:
                    self.pip.file_over(now)
                if now >= self.hungry_until:
                    from .media_player import card
                    self.notify('media_card', card('buddy', 'hungry', 'Feed me a file!',
                                                   'PDF, Word, text or code — then tell me what to do with it', '', 0, 0, ''))
                self.hungry_until = now + .6
                self.media_until = max(self.media_until, now + .6)
        except Exception:
            pass

    def close(self):
        self.edges.close()
        if self.animation_timer:
            self.animation_timer.close()


def export_preview(path):
    """Render representative states from the runtime renderer, never the desktop."""
    output = Image.new("RGB", (720, 650), "#16171c")
    draw = ImageDraw.Draw(output)
    draw.text((40, 30), "JARVIS / DYNAMIC ISLAND", font=font(22, True), fill="#eeeef3")
    draw.text((40, 67), "Rendered state previews • not a desktop screenshot", font=font(13), fill="#a0a0ad")
    states = [(208, 52, "STANDBY", "", 122), (300, 60, "LISTENING", "", 240),
              (480, 140, "SPEAKING", "Your project is ready. I found the folder and saved the summary in your memory.", 366)]
    for width, height, state, message, y in states:
        draw.text((40, y-28), state.capitalize(), font=font(12), fill="#a0a0ad")
        image = render_island(width, height, state, 1.2, message, 45)
        mask = Image.new("L", image.size)
        # Keyed transparent corners, matching the native overlay.
        pixels = image.load()
        mask.putdata([0 if pixels[x, row] == (255, 0, 255) else 255 for row in range(height) for x in range(width)])
        output.paste(image, ((720-width)//2, y), mask)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    output.save(path)


def export_animation(path):
    """Sample the same morph and renderer into a labelled demonstration GIF."""
    frames, motion = [], Morph()
    for index in range(150):
        now = index/30
        status, target, message = ("STANDBY",(208,52),"") if now < .6 or now > 4.3 else (
            ("LISTENING",(300,60),"") if now < 1.6 else ("THINKING",(300,60),"") if now < 2.6 else
            ("SPEAKING",(480,140),"I found your project folder. The summary is ready in your memory."))
        motion.set_target(target,now)
        width,height=(round(value) for value in motion.sample(now))
        island=render_island(width,height,status,now,message,35)
        frame=Image.new("RGB",(640,240),"#16171c")
        draw=ImageDraw.Draw(frame)
        draw.text((28,20),"JARVIS / RENDERED MOTION PREVIEW",font=font(13,True),fill="#b8b8c3")
        mask=Image.new("L",island.size)
        mask.putdata([0 if pixel == (255,0,255) else 255 for pixel in island.getdata()])
        frame.paste(island,((640-width)//2,70),mask)
        frames.append(frame)
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=33,loop=0,disposal=2)


def export_hd_preview(path):
    """Full HD rendered states at 200% scaling, using the actual native renderer."""
    output = Image.new('RGB', (1920, 1080), '#16171c')
    draw = ImageDraw.Draw(output)
    draw.text((80, 38), 'JARVIS / SHARP DISPLAY + LIVE TASK STATUS', font=font(32, True), fill='#eeeef3')
    draw.text((80, 90), 'Rendered at 200% scaling · not a desktop screenshot', font=font(20), fill='#a0a0ad')
    states = [(208, 52, 'STANDBY', '', '', 176),
              (580, 64, 'LISTENING', '', 'Ready for a command', 348),
              (600, 64, 'WORKING', '', 'Writing 482 chars · alarm.py · Speaking', 540),
              (600, 140, 'SPEAKING', 'You can give me another command while I reply. Say “Jarvis” and your request.',
               'Listening for “Jarvis …”', 742)]
    for width, height, state, message, detail, y in states:
        draw.text((80, y-36), state.capitalize(), font=font(18), fill='#a0a0ad')
        island = render_island(width, height, state, 1.2, message, 35, detail=detail, scale=2.)
        mask = Image.new('L', island.size)
        mask.putdata([0 if pixel == (255, 0, 255) else 255 for pixel in island.getdata()])
        output.paste(island, ((1920-island.width)//2, y), mask)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    output.save(path)
