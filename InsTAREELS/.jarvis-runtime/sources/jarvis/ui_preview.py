"""Export the actual Tk widget layout as an image without capturing the desktop."""
from pathlib import Path
import tkinter.font as tkfont
from PIL import Image, ImageDraw, ImageFont
from .interface import BG, CARD, CYAN, TEXT, MUTED, LINE
from .hud import render_hud


def export_preview(app, path):
    panel = app.panel
    image = Image.new("RGB", (panel.winfo_width(), panel.winfo_height()), BG)
    draw = ImageDraw.Draw(image)
    origin = panel.winfo_rootx(), panel.winfo_rooty()

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
        if widget == app.panel_logo:
            image.paste(render_hud(size=app.hud_size), (x, y))
        elif kind in {"Frame", "Toplevel", "Label", "Text"}:
            try:
                bg = widget.cget("background")
            except Exception:
                bg = BG
            draw.rectangle((x, y, x+width, y+height), fill=tuple(value//256 for value in widget.winfo_rgb(str(bg))))
            if kind == "Label":
                text = widget.cget("text")
                if widget.cget("textvariable"):
                    text = widget.getvar(widget.cget("textvariable"))
                color = widget.cget("foreground")
                if text:
                    pad = int(str(widget.cget("padx")))
                    wrap = int(str(widget.cget("wraplength")))
                    lines, line = [], ""
                    for word in str(text).split():
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
                ImageDraw.Draw(layer).multiline_text((14, 12), text[:1800], fill=TEXT, font=font, spacing=5)
                image.paste(layer, (x, y))
        elif kind == "Scrollbar":
            draw.rectangle((x, y, x+width, y+height), fill=BG)
            draw.rounded_rectangle((x+4, y+8, x+width-4, y+height-8), radius=3, fill=LINE)
        elif kind == "TButton":
            primary = widget.cget("style") == "Accent.TButton"
            draw.rounded_rectangle((x, y, x+width-1, y+height-1), radius=4, fill=CYAN if primary else LINE)
            draw.text((x+width/2, y+height/2), widget.cget("text"), anchor="mm", fill=BG if primary else TEXT, font=font)
        elif kind in {"TEntry", "TCombobox"}:
            draw.rounded_rectangle((x, y, x+width-1, y+height-1), radius=4, fill=CARD, outline=LINE)
            text = widget.get()
            draw.text((x+10, y+height/2), text or "Ask Jarvis anything…", anchor="lm", fill=TEXT if text else MUTED, font=font)
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
