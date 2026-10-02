"""Native Dynamic Island layout, rendering and cancellable display-only motion."""
from functools import lru_cache
import math
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont, ImageTk
from .display import window_scale

KEY = "#ff00ff"
BLACK = "#08080a"
ACCENTS = {"STANDBY": "#b1b1bc", "LISTENING": "#8bdda8", "THINKING": "#b4a1ff",
           "WORKING": "#b4a1ff", "SPEAKING": "#b9c9ff", "ATTENTION": "#f1c580"}


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
    if width <= 0:
        return ''
    if draw.textlength(value, font=face) <= width:
        return value
    low, high, best = 0, len(value), 0
    while low <= high:
        middle = (low+high)//2
        if draw.textlength(value[:middle] + '…', font=face) <= width:
            best, low = middle, middle+1
        else:
            high = middle-1
    return value[:best].rstrip() + '…' if best else ''


def render_island(width=208, height=52, status="STANDBY", phase=0, message="", level=0, expanded=False,
                  detail='', scale=1.):
    width, height = max(170, int(width)), max(46, int(height))
    scale = min(3., max(1., float(scale))) if math.isfinite(float(scale)) else 1.
    sampling = scale * 2
    image = Image.new("RGBA", (round(width*sampling), round(height*sampling)))
    draw = ImageDraw.Draw(image)
    def rectangle(bounds, radius, **kwargs):
        if 'width' in kwargs:
            kwargs['width'] = max(1, round(kwargs['width'] * sampling))
        draw.rounded_rectangle(tuple(round(x*sampling) for x in bounds), radius=round(radius*sampling), **kwargs)
    def text(x, y, value, size, color, bold=False):
        draw.text((round(x*sampling), round(y*sampling)), value, font=font(round(size*sampling), bold), fill=color)
    radius = min(32, (height-8)//2)
    rectangle((4, 4, width-5, height-5), radius=radius, fill=BLACK, outline="#29292f", width=1)
    color = ACCENTS.get(status, ACCENTS["STANDBY"])
    y = 28 if height > 74 else height // 2
    # A quiet monogram replaces the constantly animated circular emblem.
    text(23, y-13, 'J', 19, '#f4f4f7', True)
    text(48, y-10, 'Jarvis', 14, '#f4f4f7', True)
    if width > 265:
        text(115, y-9, status.capitalize(), 13, color)
    if detail and width > 330:
        text(200, y-9, '·', 13, '#62626f')
        face = font(round(13*sampling))
        text(215, y-9, fit_text(draw, detail, face, (width-292)*sampling), 13, '#dedee6')
    active = status != "STANDBY"
    for i in range(9):
        amplitude = (2 + (5 + min(100, max(0, float(level)))*.055) *
                     abs(math.sin(phase * 2.8 + i*.65))) if active else 2
        x = width-64+i*4
        rectangle((x, y-amplitude, x+2, y+amplitude), radius=1, fill=color)
    if height > 82 and not expanded:
        # Content appears immediately; decorative motion never delays an answer.
        for i, line in enumerate(wrap(draw, message, font(round(14*sampling)), (width-48)*sampling, 3)):
            text(24, 56+i*21, line, 14, '#dedee6')
    image = image.resize((round(width*scale), round(height*scale)), Image.Resampling.LANCZOS)
    # Color-key transparency cannot represent fractional edge alpha; avoid pink fringes.
    output = Image.new('RGB', image.size, KEY)
    mask = image.getchannel('A').point(lambda alpha: 255 if alpha >= 128 else 0)
    output.paste(image.convert('RGB'), (0, 0), mask)
    return output


class Activity:
    """UI metadata only; never use displayed text as task execution authority."""
    def __init__(self):
        self.detail = ''
        self.updated = 0.
        self.active = False

    def notify(self, kind, value, now=None):
        now = time.monotonic() if now is None else now
        if kind == 'task_status' and isinstance(value, dict):
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
        self.size = (208., 52.)
        self.origin = self.target = self.size
        self.started = 0.

    def set_target(self, size, now):
        if tuple(size) != self.target:
            self.origin = self.sample(now)
            self.target = tuple(size)
            self.started = now

    def sample(self, now, reduced=False):
        p = 1 if reduced else min(1, max(0, (now-self.started)/.42))
        eased = 1-(1-p)**4
        self.size = tuple(a+(b-a)*eased for a, b in zip(self.origin, self.target))
        return self.size


class Island:
    def __init__(self, app, canvas):
        self.app, self.canvas = app, canvas
        self.motion = Morph()
        self.expanded = self.hover = False
        self.message = ""
        self.activity = Activity()
        self.message_until = 0.
        self.attention_until = 0.
        self.anchor_x = app.root.winfo_screenwidth() // 2
        self.top = 12
        self.drag = None
        self.moved = False
        self.last_frame = None
        self.last_geometry = None
        self.last_size = None
        self.item = canvas.create_image(0, 0, anchor="nw")
        canvas.bind("<Enter>", lambda _e: self.set_hover(True))
        canvas.bind("<Leave>", lambda _e: self.set_hover(False))
        canvas.bind("<Button-1>", self.press)
        canvas.bind("<B1-Motion>", self.move)
        canvas.bind("<ButtonRelease-1>", self.release)
        canvas.bind("<Button-3>", app.show_menu)

    def set_hover(self, value):
        self.hover = value

    def press(self, event):
        self.drag = (event.x_root, event.y_root, self.anchor_x, self.top)
        self.moved = False

    def move(self, event):
        if self.drag:
            x, y, anchor, top = self.drag
            if abs(event.x_root-x)+abs(event.y_root-y) > 5:
                self.moved = True
                self.anchor_x = anchor+event.x_root-x
                self.top = max(0, top+event.y_root-y)

    def release(self, event):
        if self.drag and not self.moved:
            self.app.toggle_panel(event)
        self.drag = None

    def expand(self, value):
        self.expanded = value
        self.app.panel.withdraw()
        if not value:
            self.message_until = self.attention_until = 0.
        self.last_frame = None

    def notify(self, kind, message):
        self.activity.notify(kind, message)
        if kind in {"answer", "spoken_reply", "question", "warning", "fatal"} and message:
            self.message = str(message)[:450]
            self.message_until = time.monotonic()+12
            if kind in {"warning", "fatal", "question"}:
                self.attention_until = self.message_until
        elif kind == "partial" and message:
            self.message = str(message)[:450]
            self.message_until = time.monotonic()+3

    def tick(self, status, level=0, speaking=False, listening=False):
        app, root = self.app, self.app.root
        now = time.monotonic()
        if now < self.attention_until and status == "STANDBY":
            status = "ATTENTION"
        message = self.message if now < self.message_until else ""
        scale = window_scale(root)
        detail = self.activity.caption(status, now, speaking, listening)
        max_width = max(170, root.winfo_screenwidth()/scale-20)
        max_height = max(180, root.winfo_screenheight()/scale-32)
        target = (min(560, max_width), min(660, max_height)) if self.expanded else (
            (min(600, max_width), 140) if message else (min(580, max_width), 64) if detail else (320, 60) if status != "STANDBY" else
            (260, 54) if self.hover else (208, 52))
        self.motion.set_target(target, now)
        reduced = bool(app.config.get("ui", {}).get("reduced_motion", False))
        width, height = (round(value) for value in self.motion.sample(now, reduced))
        pixels_w, pixels_h = round(width*scale), round(height*scale)
        left = max(0, min(root.winfo_screenwidth()-pixels_w, round(self.anchor_x-pixels_w/2)))
        top = max(0, min(root.winfo_screenheight()-pixels_h, self.top))
        geometry = f"{pixels_w}x{pixels_h}+{left}+{top}"
        if geometry != self.last_geometry:
            root.geometry(geometry)
            self.last_geometry = geometry
        if (pixels_w, pixels_h) != self.last_size:
            self.canvas.configure(width=pixels_w, height=pixels_h)
            self.last_size = (pixels_w, pixels_h)
        settled = abs(width-target[0])+abs(height-target[1]) <= 2
        phase = 0 if reduced or status == "STANDBY" else now
        frame_key = (width, height, status, message, detail, scale, round(phase*24), round(float(level)), self.expanded)
        if frame_key != self.last_frame:
            self.photo = ImageTk.PhotoImage(render_island(width, height, status, phase, message, level, self.expanded, detail, scale), master=root)
            self.canvas.itemconfigure(self.item, image=self.photo)
            self.last_frame = frame_key
        if self.expanded and settled and not getattr(app, "capture_count", 0) and root.state() != "withdrawn":
            app.panel.geometry(f"{round((width-40)*scale)}x{round((height-76)*scale)}+{left+round(20*scale)}+{top+round(56*scale)}")
            if app.panel.state() == "withdrawn":
                app.panel.deiconify()
                app.panel.lift()
                app.exclude_window_from_capture(app.panel)
                if getattr(getattr(app,'desk',None),'view',None)=='Games':
                    app.desk.game_canvas.focus_set()
                else:
                    app.preview.focus_set()


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
