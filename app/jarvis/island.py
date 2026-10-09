"""Native Dynamic Island layout, rendering and cancellable display-only motion."""
from functools import lru_cache
import math
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont, ImageTk
from .display import window_scale

KEY = "#ff00ff"
BLACK = "#000000"
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
    width, height = max(170, int(width)), max(40, int(height))
    scale = min(3., max(1., float(scale))) if math.isfinite(float(scale)) else 1.
    sampling = scale * 2
    band_height = min(height, 128)
    image = Image.new("RGB", (round(width*sampling), round(band_height*sampling)), BLACK)
    silhouette = Image.new('L',(round(width*sampling),round(height*sampling)))
    draw = ImageDraw.Draw(image)
    def rectangle(bounds, radius, **kwargs):
        if 'width' in kwargs:
            kwargs['width'] = max(1, round(kwargs['width'] * sampling))
        draw.rounded_rectangle(tuple(round(x*sampling) for x in bounds), radius=round(radius*sampling), **kwargs)
    def text(x, y, value, size, color, bold=False):
        draw.text((round(x*sampling), round(y*sampling)), value, font=font(round(size*sampling), bold), fill=color)
    # Concave shoulders attach to the screen edge; only the bottom is convex.
    shoulder, radius = 32, min(32, height/2)
    points = [(0, 0), (width, 0)]
    for i in range(1, 25):
        angle = i*math.pi/48
        points.append((width-shoulder*math.sin(angle), radius*(1-math.cos(angle))))
    points.append((width-shoulder, height-radius))
    for i in range(1, 25):
        angle = i*math.pi/48
        points.append((width-shoulder-radius+radius*math.cos(angle), height-radius+radius*math.sin(angle)))
    points.append((shoulder+radius, height))
    for i in range(1, 25):
        angle = i*math.pi/48
        points.append((shoulder+radius-radius*math.sin(angle), height-radius+radius*math.cos(angle)))
    points.append((shoulder, radius))
    for i in range(24, -1, -1):
        angle = i*math.pi/48
        points.append((shoulder*math.sin(angle), radius*(1-math.cos(angle))))
    ImageDraw.Draw(silhouette).polygon([(round(x*sampling),round(y*sampling)) for x,y in points], fill=255)
    color = ACCENTS.get(status, ACCENTS["STANDBY"])
    y = 21
    rectangle((47, 10, 69, 32), radius=11, fill='#1d3e66')
    rectangle((49, 11, 67, 29), radius=9, fill='#729fcb')
    text(54, 10, 'J', 12, '#ffffff', True)
    text(79, y-10, 'Jarvis', 12, '#e8e8e8', True)
    if width > 265:
        text(145, y-9, status.capitalize(), 11, color)
    if detail and width > 330:
        text(200, y-9, '·', 13, '#62626f')
        face = font(round(13*sampling))
        text(215, y-9, fit_text(draw, detail, face, (width-292)*sampling), 13, '#dedee6')
    active = status != "STANDBY"
    for i in range(9 if active else 0):
        amplitude = (2 + (5 + min(100, max(0, float(level)))*.055) *
                     abs(math.sin(phase * 2.8 + i*.65))) if active else 2
        x = width-116+i*4
        rectangle((x, y-amplitude, x+2, y+amplitude), radius=1, fill=color)
    if expanded:
        rectangle((width-79, 7, width-51, 35), radius=14, fill='#24252a',outline='#44464e',width=1)
        rectangle((width-69, 17, width-61, 25), radius=1, fill='#d8d8d8')
        rectangle((width-50, 9, width-34, 33),radius=8,fill='#202126',outline='#35363d',width=1)
        draw.line([(round(x*sampling), round(y*sampling)) for x,y in
                   ((width-47,24),(width-43,20),(width-39,24))], fill='#aaaaaa', width=max(1,round(sampling)))
    if height > 82 and not expanded:
        # Content appears immediately; decorative motion never delays an answer.
        for i, line in enumerate(wrap(draw, message, font(round(14*sampling)), (width-48)*sampling, 3)):
            text(24, 56+i*21, line, 14, '#dedee6')
    pixels_w,pixels_h = round(width*scale),round(height*scale)
    band = image.resize((pixels_w,round(band_height*scale)), Image.Resampling.LANCZOS)
    image = Image.new('RGB',(pixels_w,pixels_h),BLACK)
    image.paste(band,(0,0))
    # Color-key transparency cannot represent fractional edge alpha; avoid pink fringes.
    output = Image.new('RGB', image.size, KEY)
    # Straight walls need no resampling. Only the four curved regions do.
    mask = Image.new('L',image.size)
    edge,corner = round(shoulder*scale),round(radius*scale)
    ImageDraw.Draw(mask).rectangle((edge,0,pixels_w-edge,pixels_h-1),fill=255)
    regions = ((0,0,edge,edge),(pixels_w-edge,0,pixels_w,edge),
               (edge,pixels_h-corner,edge+corner,pixels_h),
               (pixels_w-edge-corner,pixels_h-corner,pixels_w-edge,pixels_h))
    for x1,y1,x2,y2 in regions:
        patch = silhouette.crop((x1*2,y1*2,x2*2,y2*2)).resize((x2-x1,y2-y1),Image.Resampling.LANCZOS)
        mask.paste(patch,(x1,y1))
    mask = mask.point(lambda alpha: 255 if alpha >= 128 else 0)
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
        self.top = 0
        self.drag = None
        self.moved = False
        self.last_frame = None
        self.last_geometry = None
        self.last_size = None
        self.background_key = None
        self.surface_open = False
        self.features_open = False
        self.focus_pending = False
        self.stream_active = False
        self.stream_hidden = False
        self.stream_height = 0
        self.work_completion_pending = False
        self.item = canvas.create_image(0, 0, anchor="nw")
        self.header_item = canvas.create_image(0, 0, anchor='nw')
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
        message = self.message if now < self.message_until else ""
        scale = window_scale(root)
        detail = self.activity.caption(status, now, speaking, listening)
        max_width = max(170, root.winfo_screenwidth()/scale-12)
        max_height = max(180, root.winfo_screenheight()/scale-70)
        target, workspace, self.surface_open = self.layout_target(message, detail, status, max_width, max_height)
        self.motion.set_target(target, now)
        reduced = bool(app.config.get("ui", {}).get("reduced_motion", False))
        width, height = (round(value) for value in self.motion.sample(now, reduced))
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
        frame_key = (width, height, status, message, detail, scale, round(phase*24), round(float(level)), self.surface_open)
        if frame_key != self.last_frame:
            geometry_key = (width,height,scale,self.surface_open)
            if height <= 96 or geometry_key != self.background_key:
                self.preview_image = render_island(width, height, status, phase, '', level, self.surface_open, detail, scale)
                self.background_image = self.preview_image.copy()
                self.photo = ImageTk.PhotoImage(self.preview_image, master=root)
                self.canvas.itemconfigure(self.item, image=self.photo)
                self.canvas.itemconfigure(self.header_item,image='')
                self.background_key = geometry_key
            else:
                # A settled tall shell is static; redraw only its live top band.
                header = render_island(width,96,status,phase,'',level,self.surface_open,detail,scale).crop(
                    (0,0,pixels_w,round(44*scale)))
                self.header_photo = ImageTk.PhotoImage(header,master=root)
                self.canvas.itemconfigure(self.header_item,image=self.header_photo)
                self.preview_image = self.background_image.copy()
                self.preview_image.paste(header,(0,0))
            self.canvas.preview_image = self.preview_image
            self.last_frame = frame_key
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
