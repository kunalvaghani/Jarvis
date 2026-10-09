"""Jarvis HUD artwork renderer; no network or background workers."""
from functools import lru_cache
import math
from pathlib import Path
from PIL import Image, ImageDraw

BACKGROUND = "#070f16"
ACCENT = "#48d9f3"
ASSET = Path(__file__).resolve().parent / "assets" / "jarvis-reference.gif"
# The circular J.A.R.V.I.S. logo inside the README's 1440 x 900 animation.
LOGO_BOX = (165, 520, 390, 745)


@lru_cache(maxsize=2)
def logo_frames(size):
    """Decode a bounded set of locally bundled frames once per display size."""
    frames = []
    try:
        with Image.open(ASSET) as source:
            for index in range(min(source.n_frames, 32)):
                source.seek(index)
                logo = source.convert("RGBA").crop(LOGO_BOX)
                frames.append(logo.resize((size, size), Image.Resampling.LANCZOS))
    except (OSError, ValueError):
        return ()
    return tuple(frames)


def render_hud(phase=0, active=False, speaking=False, size=196):
    """Render the copied logo inside live status rings, with an offline fallback."""
    size = max(48, min(512, int(size)))
    image = Image.new("RGB", (size, size), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for offset in range(size // 16, size, max(8, size // 12)):
        draw.line((offset, 0, offset, size), fill="#0b1b26")
        draw.line((0, offset, size, offset), fill="#0b1b26")
    frames = logo_frames(max(32, int(size * .84)))
    inset = (size - int(size * .84)) // 2
    if frames:
        image.paste(frames[int(phase / .13) % len(frames)], (inset, inset))
    else:
        draw.ellipse((size * .16, size * .16, size * .84, size * .84), outline=ACCENT, width=2)
        draw.text((size / 2, size / 2), "J.A.R.V.I.S.", fill=ACCENT, anchor="mm")
    color = "#d6fbff" if speaking else ACCENT if active else "#24768c"
    margin = max(3, size // 32)
    bounds = (margin, margin, size-margin-1, size-margin-1)
    draw.arc(bounds, 210 + phase * 28, 310 + phase * 28, fill=color, width=max(1, size // 100))
    draw.arc(bounds, 30 - phase * 18, 115 - phase * 18, fill=color, width=max(1, size // 100))
    for index in range(36):
        angle = math.radians(index * 10)
        center, radius = size / 2, size * .48
        start = (center + math.cos(angle) * radius, center + math.sin(angle) * radius)
        end = (center + math.cos(angle) * (radius-3), center + math.sin(angle) * (radius-3))
        draw.line((*start, *end), fill=color)
    return image
