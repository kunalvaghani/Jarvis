"""Rounded native cards and an embedded island surface, with no extra windows."""
import re
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from .display import window_scale

BG = '#000000'


class RoundedCard(tk.Canvas):
    def __init__(self, parent, fill='#151515', radius=22, inset=12, **kw):
        super().__init__(parent, bg=BG, highlightthickness=0, **kw)
        self.fill, self.radius, self.inset = fill, radius, inset
        self.last_size = None
        self.surface = self.create_image(0, 0, anchor='nw')
        self.content = tk.Frame(self, bg=fill)
        self.slot = self.create_window(0, 0, window=self.content, anchor='nw')
        self.bind('<Configure>', self.resize)

    def resize(self, event):
        scale = window_scale(self.winfo_toplevel())
        width, height = max(1, event.width), max(1, event.height)
        if self.last_size == (width, height, scale):
            return
        self.last_size = (width, height, scale)
        from .glass_ui import render_glass
        self.preview_image = render_glass(width,height,field=True,scale=scale,radius=self.radius)
        self.photo = ImageTk.PhotoImage(self.preview_image, master=self)
        self.itemconfigure(self.surface, image=self.photo)
        inset = round(self.inset*scale)
        self.coords(self.slot, inset, inset)
        self.itemconfigure(self.slot, width=max(1, width-inset*2), height=max(1, height-inset*2))


class NotchPanel(tk.Frame):
    """Window-like visibility API for callers; all content belongs to the root."""
    def __init__(self, app):
        super().__init__(app.root, bg=BG)
        self.app = app
        self.bounds = None
        self.visible = False
        self.workspace = False
        self.layout_key = None
        self.placed_bounds = None

    def state(self):
        return 'normal' if self.visible else 'withdrawn'

    def withdraw(self):
        if not self.visible:
            return
        self.visible = False
        self.place_forget()
        self.placed_bounds = None

    def deiconify(self):
        if self.bounds:
            if self.placed_bounds != self.bounds:
                self.place(**self.bounds)
                self.placed_bounds = dict(self.bounds)
            self.visible = True

    def present(self, width, height, workspace):
        self.workspace = workspace
        scale = window_scale(self.app.root)
        self.bounds = dict(x=round(48*scale), y=round(44*scale),
            width=max(1, round((width-96)*scale)), height=max(1, round((height-66)*scale)))
        key = (workspace, bool(self.app.question.get()), self.app.island.features_open, self.app.desk.view)
        if key != self.layout_key:
            self.layout_key = key
            self.app.layout_notch(key[0])
        # Use the incoming width, not winfo_width from the previous geometry frame.
        wrap = max(120, self.bounds['width'] - round(30*scale))
        if int(float(self.app.question_label.cget('wraplength'))) != wrap:
            self.app.question_label.configure(wraplength=wrap)
        if self.visible and self.placed_bounds != self.bounds:
            self.place(**self.bounds)
            self.placed_bounds = dict(self.bounds)

    def geometry(self, geometry):
        """Explicit off-screen layout for existing hidden widget verification."""
        match = re.fullmatch(r'(\d+)x(\d+)\+(\d+)\+(\d+)', geometry)
        if not match:
            raise ValueError('Expected WIDTHxHEIGHT+X+Y')
        width, height, left, top = map(int, match.groups())
        scale = window_scale(self.app.root)
        self.app.root.geometry(f'{width+round(96*scale)}x{height+round(66*scale)}+{left}+{top}')
        self.app.root.deiconify()
        self.bounds = dict(x=round(48*scale), y=round(44*scale), width=width, height=height)
        self.app.layout_notch(True)
