"""Native rounded glass controls. Shared artwork drives Tk and rendered previews."""
from functools import lru_cache
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

from .display import window_scale


@lru_cache(maxsize=64)
def _glass_tile(width, height, state='normal', field=False, scale=1., radius=12):
    width, height = max(8, int(width)), max(8, int(height))
    factor = 2
    size = width*factor, height*factor
    radius = min(height/2, radius*scale)*factor
    image = Image.new('RGBA', size)
    layer = Image.new('RGBA', size)
    draw = ImageDraw.Draw(layer)
    top, bottom = ((34,35,40),(22,23,27)) if field else ((53,54,60),(30,31,36))
    border = (255,255,255,46)
    if state in {'active','focus'}:
        top, bottom, border = (66,74,87),(37,44,56),(185,212,255,125)
    elif state == 'pressed':
        top, bottom, border = (31,39,53),(42,53,73),(170,201,255,115)
    elif state == 'disabled':
        top, bottom, border = (30,31,35),(24,25,28),(255,255,255,22)
    for y in range(size[1]):
        ratio = y/max(1,size[1]-1)
        color = tuple(round(a+(b-a)*ratio) for a,b in zip(top,bottom))+(255,)
        draw.line((0,y,size[0],y),fill=color)
    mask = Image.new('L',size)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,size[0]-1,size[1]-1),radius=radius,fill=255)
    image.paste(layer,(0,0),mask)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1,1,size[0]-2,size[1]-2),radius=max(1,radius-1),outline=border,width=factor)
    draw.line((radius,2,size[0]-radius,2),fill=(255,255,255,65),width=1)
    return image.resize((width,height),Image.Resampling.LANCZOS)


@lru_cache(maxsize=64)
def render_glass(width, height, state='normal', field=False, scale=1., radius=12):
    """Stretch small antialiased tiles instead of supersampling a full large card."""
    width,height = max(8,int(width)),max(8,int(height))
    corner = max(1,round(min(radius*scale,width/2,height/2)))
    side = max(corner*2+8,round(64*scale))
    tile = _glass_tile(side,side,state,field,scale,corner/scale)
    result = Image.new('RGBA',(width,height))
    source = (0,corner,side-corner,side)
    horizontal = (0,corner,width-corner,width)
    vertical = (0,corner,height-corner,height)
    for row in range(3):
        for column in range(3):
            target = horizontal[column+1]-horizontal[column],vertical[row+1]-vertical[row]
            if min(target)<=0:
                continue
            piece = tile.crop((source[column],source[row],source[column+1],source[row+1]))
            if piece.size != target:
                piece = piece.resize(target,Image.Resampling.BILINEAR)
            result.paste(piece,(horizontal[column],vertical[row]))
    return result


def install_glass(root, style):
    """Nine-slice elements keep rounded edges while controls resize at native DPI."""
    scale = window_scale(root)
    size = round(48*scale), round(36*scale)
    border = round(12*scale)
    pictures = []
    def element(name, field=False):
        images = {state:ImageTk.PhotoImage(render_glass(*size,state,field,scale),master=root)
                  for state in ('normal','active','pressed','disabled','focus')}
        pictures.extend(images.values())
        style.element_create(name,'image',images['normal'],('disabled',images['disabled']),
            ('pressed',images['pressed']),('focus',images['focus']),('active',images['active']),
            border=(border,border,border,border),padding=0,width=0,height=round(28*scale),sticky='nsew')
    element('GlassButton.surface')
    style.layout('TButton',[('GlassButton.surface',{'sticky':'nswe','children':[
        ('Button.padding',{'sticky':'nswe','children':[('Button.label',{'sticky':'nswe'})]})]})])
    style.configure('TButton',padding=(10,6),background='#000000',foreground='#e8e9ee',borderwidth=0)
    style.map('TButton',background=[('active','#000000'),('pressed','#000000')])
    style.configure('Accent.TButton',foreground='#c5d8ff',background='#000000')
    style.map('Accent.TButton',background=[('active','#000000'),('pressed','#000000')])
    style.configure('Card.TButton',background='#151515')
    style.map('Card.TButton',background=[('active','#151515'),('pressed','#151515')])
    element('GlassEntry.surface',True)
    style.layout('TEntry',[('GlassEntry.surface',{'sticky':'nswe','children':[
        ('Entry.padding',{'sticky':'nswe','children':[('Entry.textarea',{'sticky':'nswe'})]})]})])
    style.configure('TEntry',padding=(12,7),background='#000000',fieldbackground='#1b1c21',
                    bordercolor='#343b49',lightcolor='#343b49',darkcolor='#343b49',foreground='#eeeeef',insertcolor='#c5d8ff')
    style.configure('Card.TEntry',background='#151515')
    element('GlassCombo.surface',True)
    style.layout('TCombobox',[('GlassCombo.surface',{'sticky':'nswe','children':[
        ('Combobox.downarrow',{'side':'right','sticky':'ns'}),
        ('Combobox.padding',{'sticky':'nswe','children':[('Combobox.textarea',{'sticky':'nswe'})]})]})])
    style.configure('TCombobox',padding=(10,6),fieldbackground='#1b1c21',background='#25262c')
    style.map('TCombobox',fieldbackground=[('readonly','#1b1c21')])
    indicator = {}
    for selected in (False,True):
        image = render_glass(round(18*scale),round(18*scale),'focus' if selected else 'normal',scale=scale).copy()
        if selected:
            ImageDraw.Draw(image).line([(round(x*scale),round(y*scale)) for x,y in ((5,9),(8,12),(13,6))],
                fill='#dce8ff',width=max(1,round(2*scale)))
        indicator[selected] = ImageTk.PhotoImage(image,master=root)
    pictures.extend(indicator.values())
    style.element_create('GlassCheck.indicator','image',indicator[False],('selected',indicator[True]),sticky='')
    style.layout('TCheckbutton',[('Checkbutton.padding',{'sticky':'nswe','children':[
        ('GlassCheck.indicator',{'side':'left','sticky':''}),('Checkbutton.label',{'side':'left','sticky':'nswe'})]})])
    style.configure('TCheckbutton',padding=(3,5))
    root._glass_resources = pictures


class GlassButton(tk.Button):
    """Wrapped, dynamically sized choice button with the same glass artwork."""
    def __init__(self, parent, **kwargs):
        kwargs.update(relief='flat',borderwidth=0,highlightthickness=0,padx=12,pady=10,compound='center')
        super().__init__(parent,**kwargs)
        self.glass_state = 'normal'
        self.last_glass = None
        self.bind('<Configure>',lambda _e:self.paint())
        self.bind('<Enter>',lambda _e:self.set_state('active'))
        self.bind('<Leave>',lambda _e:self.set_state('normal'))
        self.bind('<ButtonPress-1>',lambda _e:self.set_state('pressed'))
        self.bind('<ButtonRelease-1>',lambda _e:self.set_state('active'))

    def set_state(self,state):
        self.glass_state = state
        self.paint()

    def paint(self):
        width,height = self.winfo_width(),self.winfo_height()
        key = width,height,self.glass_state
        if width < 4 or height < 4 or key == self.last_glass:
            return
        self.last_glass = key
        scale = window_scale(self.winfo_toplevel())
        self.preview_image = render_glass(width,height,self.glass_state,scale=scale)
        # Background imagery does not change the button's requested text size.
        self.photo = ImageTk.PhotoImage(self.preview_image,master=self)
        self.configure(image=self.photo,width=max(1,width-24),height=max(1,height-20))
