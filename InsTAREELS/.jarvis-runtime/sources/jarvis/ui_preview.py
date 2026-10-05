"""Export the actual Tk widget layout as an image without capturing the desktop."""
from pathlib import Path
import tkinter.font as tkfont
from PIL import Image, ImageDraw, ImageFont
from .interface import BG, CARD, CYAN, TEXT, MUTED, LINE
from .glass_ui import render_glass
from .display import window_scale


def export_preview(app, path):
    panel = app.panel
    source = getattr(app.island, 'preview_image', None)
    image = source.copy() if isinstance(source, Image.Image) else Image.new("RGB", (app.root.winfo_width(), app.root.winfo_height()), BG)
    draw = ImageDraw.Draw(image)
    origin = app.root.winfo_rootx(), app.root.winfo_rooty()

    def font_for(widget):
        try:
            spec = tkfont.Font(root=panel, font=widget.cget("font")).actual()
        except Exception:
            spec = {"family": "Segoe UI", "size": 10, "weight": "normal"}
        family = "consola" if "consolas" in spec["family"].lower() else "segoeui"
        filename = family + ("b" if spec["weight"] == "bold" else "") + ".ttf"
        pixels = max(10, round(abs(spec["size"]) * panel.winfo_fpixels("1i") / 72))
        try:
            return ImageFont.truetype(str(Path("C:/Windows/Fonts") / filename), pixels)
        except OSError:
            return ImageFont.load_default()

    def visit(widget):
        if widget != panel and not widget.winfo_ismapped():
            return
        x, y = widget.winfo_rootx()-origin[0], widget.winfo_rooty()-origin[1]
        width, height = widget.winfo_width(), widget.winfo_height()
        kind = widget.winfo_class()
        font = font_for(widget)
        if kind in {"Frame", "Toplevel", "Label", "Text"}:
            try:
                bg = widget.cget("background")
            except Exception:
                bg = BG
            draw.rectangle((x, y, x+width, y+height), fill=tuple(value//256 for value in widget.winfo_rgb(str(bg))))
            if kind == "Label":
                source = getattr(widget,'preview_image',None)
                if isinstance(source,Image.Image):
                    image.paste(source,(round(x+(width-source.width)/2),round(y+(height-source.height)/2)))
                text = widget.cget("text")
                if widget.cget("textvariable"):
                    text = widget.getvar(widget.cget("textvariable"))
                color = widget.cget("foreground")
                if text:
                    pad = int(str(widget.cget("padx")))
                    wrap = int(str(widget.cget("wraplength")))
                    lines = []
                    for paragraph in str(text).split('\n'):
                        line=''
                        for word in paragraph.split():
                            candidate = (line + " " + word).strip()
                            if wrap and line and font.getlength(candidate) > wrap:
                                lines.append(line)
                                line = word
                            else:
                                line = candidate
                        lines.append(line)
                    lines = "\n".join(lines)
                    draw.multiline_text((x+pad, y+int(str(widget.cget("pady")))+2), lines, font=font, fill=color, spacing=4)
            elif kind == "Text":
                text = widget.get("1.0", "end-1c")
                layer = Image.new("RGB", (width, height), CARD)
                painter = ImageDraw.Draw(layer)
                cursor = 8
                for index, paragraph in enumerate(text[:12000].splitlines(), 1):
                    code = 'code' in widget.tag_names(f'{index}.0')
                    face = font
                    if code:
                        try:
                            face = ImageFont.truetype('C:/Windows/Fonts/consola.ttf',max(10,round(10*panel.winfo_fpixels('1i')/72)))
                        except OSError:
                            pass
                    lines, line = [], ''
                    for character in paragraph:
                        if line and face.getlength(line+character)>width-28:
                            lines.append(line); line=''
                        line += character
                    lines.append(line)
                    for line in lines:
                        painter.text((14,cursor),line,fill='#c6d7ed' if code else TEXT,font=face)
                        cursor += face.getbbox('Ag')[3]+5
                image.paste(layer, (x, y))
        elif kind == 'Canvas' and isinstance(getattr(widget,'preview_image',None),Image.Image):
            artwork = widget.preview_image.resize((width,height))
            image.paste(artwork,(x,y),artwork.getchannel('A') if artwork.mode=='RGBA' else None)
        elif kind == "Scrollbar":
            draw.rectangle((x, y, x+width, y+height), fill=BG)
            draw.rounded_rectangle((x+4, y+8, x+width-4, y+height-8), radius=3, fill=LINE)
        elif kind in {"TButton","Button"}:
            primary = kind=='TButton' and widget.cget("style") == "Accent.TButton"
            glass = render_glass(width,height,scale=window_scale(app.root))
            image.paste(glass,(x,y),glass.getchannel('A'))
            draw.text((x+width/2, y+height/2), widget.cget("text"), anchor="mm", fill=CYAN if primary else TEXT, font=font)
        elif kind in {"TEntry", "TCombobox"}:
            glass = render_glass(width,height,field=True,scale=window_scale(app.root))
            image.paste(glass,(x,y),glass.getchannel('A'))
            text = widget.get()
            if text:
                draw.text((x+12, y+height/2), text, anchor="lm", fill=TEXT, font=font)
            if kind == "TCombobox":
                draw.text((x+width-18, y+height/2), "⌄", anchor="mm", fill=CYAN, font=font)
        elif kind == "TCheckbutton":
            draw.rectangle((x+3, y+height/2-6, x+15, y+height/2+6), outline=CYAN)
            if widget.getvar(widget.cget("variable")):
                draw.line((x+5, y+height/2, x+8, y+height/2+3, x+13, y+height/2-4), fill=CYAN, width=2)
            draw.text((x+24, y+height/2), widget.cget("text"), anchor="lm", fill=TEXT, font=font)
        elif kind == "TProgressbar":
            draw.rectangle((x, y+height/2, x+width, y+height/2+2), fill=LINE)
        elif kind == "TNotebook":
            draw.rectangle((x, y, x+width, y+height), fill=BG)
            for index, text in enumerate(("Conversation", "Voice & settings")):
                left = x + index*152
                draw.rectangle((left, y, left+148, y+32), fill=LINE if index == 0 else CARD)
                draw.text((left+12, y+16), text, anchor="lm", font=font, fill=CYAN if index == 0 else MUTED)
        for child in widget.winfo_children():
            visit(child)
    visit(panel)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
