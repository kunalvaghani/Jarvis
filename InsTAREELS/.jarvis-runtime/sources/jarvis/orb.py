"""Small animated, translucent assistant orb for the Windows overlay."""
import math
from functools import lru_cache

from PIL import Image


@lru_cache(maxsize=4)
def geometry(size, speaking):
    """Cache only phase-independent geometry, with bounded memory use."""
    points = []
    center = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            dx, dy = x - center, y - center
            radius = math.hypot(dx, dy)
            if radius >= size * .49:
                points.append(((0, 0, 0, 0),))
                continue
            angle = math.atan2(dy, dx)
            if radius > size * .39:
                fade = (size * .49 - radius) / (size * .10)
                points.append(((int(15 + 50 * fade), int(36 + (155 if not speaking else 85) * fade),
                               int(64 + 185 * fade), 255),))
                continue
            edge = min(1, radius / (size * .39))
            highlight = math.exp(-((dx + size * .13) ** 2 + (dy + size * .15) ** 2) / (size * 5))
            points.append((None, angle * 2.7, radius * .09, edge, highlight))
    return tuple(points)


def render_orb(phase, active=False, speaking=False, size=92):
    pixels = []
    brightness = 1.0 if active or speaking else .67
    for point in geometry(size, speaking):
        if point[0] is not None:
            pixels.append(point[0])
            continue
        _, angle, radius, edge, highlight = point
        swirl = (1 + math.sin(angle + phase + radius)) / 2
        red = (37 + 105 * swirl + 116 * highlight) * brightness
        green = (112 + 87 * (1 - swirl) + 88 * highlight) * brightness
        blue = (191 + 48 * edge + 15 * highlight) * brightness
        if speaking:
            red += 52
            green -= 20
        pixels.append((min(255, int(red)), min(255, max(0, int(green))),
                       min(255, int(blue)), 255))
    image = Image.new("RGBA", (size, size))
    image.putdata(pixels)
    return image
