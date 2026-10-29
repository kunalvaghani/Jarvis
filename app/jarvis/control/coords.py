"""The one owner of coordinate frames (prompt section 9, doc sections 3.3 and 11.3).

Every frame maps to SCREEN_PHYSICAL pixels through a Transform. Points are validated against
their frame bounds, their capture age and the real monitor layout. Invalid points are rejected,
never clamped, and a monitor origin is never guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import sys
import time
from typing import Any, Callable, Optional, Sequence, Tuple

MAX_LONG_EDGE = 2576       # Current Claude models (doc 3.3).
MAX_VISUAL_TOKENS = 4784   # ceil(w/28) * ceil(h/28).
PER_MONITOR_AWARE = 2      # PROCESS_PER_MONITOR_DPI_AWARE / DPI_AWARENESS_PER_MONITOR_AWARE.


class Frame(str, Enum):
    SCREEN_PHYSICAL = 'screen_physical'
    SCREEN_LOGICAL = 'screen_logical'
    MONITOR = 'monitor'
    WINDOW = 'window'
    CLIENT = 'client'
    VIEWPORT = 'viewport'
    SCREENSHOT = 'screenshot'
    CROP = 'crop'


class CoordinateError(ValueError):
    """A point cannot be mapped safely; no input may be sent."""


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        if self.right <= self.left or self.bottom <= self.top:
            raise CoordinateError(f'Empty or inverted rectangle {self}.')

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    frame: Frame
    source: str = ''  # Identity of the observation (screenshot id, viewport id) the point came from.


@dataclass(frozen=True)
class Monitor:
    name: str
    physical: Rect
    scale: float  # 1.0, 1.25, 1.5 ... (DPI / 96)

    def __post_init__(self) -> None:
        if not math.isfinite(self.scale) or not .5 <= self.scale <= 5:
            raise CoordinateError(f'Implausible monitor scale {self.scale}.')

    @property
    def logical(self) -> Rect:
        # Logical space keeps the physical top-left and divides extents by the monitor scale.
        return Rect(self.physical.left, self.physical.top,
                    self.physical.left + round(self.physical.width / self.scale),
                    self.physical.top + round(self.physical.height / self.scale))


@dataclass(frozen=True)
class Layout:
    monitors: Tuple[Monitor, ...]

    def __post_init__(self) -> None:
        if not self.monitors:
            raise CoordinateError('No monitors are known; refusing to guess a layout.')

    def monitor_at(self, x: float, y: float) -> Monitor:
        for monitor in self.monitors:
            if monitor.physical.contains(x, y):
                return monitor
        raise CoordinateError(f'Physical point ({x:.1f}, {y:.1f}) is on no monitor.')

    def logical_to_physical(self, point: Point) -> Point:
        if point.frame is not Frame.SCREEN_LOGICAL:
            raise CoordinateError('Expected a logical screen point.')
        for monitor in self.monitors:
            if monitor.logical.contains(point.x, point.y):
                left, top = monitor.physical.left, monitor.physical.top
                return Point(left + (point.x - left) * monitor.scale, top + (point.y - top) * monitor.scale,
                             Frame.SCREEN_PHYSICAL, point.source)
        raise CoordinateError(f'Logical point ({point.x:.1f}, {point.y:.1f}) is on no monitor.')

    def physical_to_logical(self, point: Point) -> Point:
        if point.frame is not Frame.SCREEN_PHYSICAL:
            raise CoordinateError('Expected a physical screen point.')
        monitor = self.monitor_at(point.x, point.y)
        left, top = monitor.physical.left, monitor.physical.top
        return Point(left + (point.x - left) / monitor.scale, top + (point.y - top) / monitor.scale,
                     Frame.SCREEN_LOGICAL, point.source)


@dataclass(frozen=True)
class Transform:
    """frame point p -> physical screen point origin + p * scale, valid for points inside bounds."""
    frame: Frame
    source: str
    origin_x: float
    origin_y: float
    scale_x: float
    scale_y: float
    width: int
    height: int
    captured_at: float
    max_age_s: float = 10.0

    def __post_init__(self) -> None:
        values = (self.origin_x, self.origin_y, self.scale_x, self.scale_y)
        if not all(math.isfinite(v) for v in values) or self.scale_x <= 0 or self.scale_y <= 0:
            raise CoordinateError('Transform needs finite positive scales.')
        if self.width <= 0 or self.height <= 0:
            raise CoordinateError('Transform needs a positive frame size.')

    @classmethod
    def identity_screen(cls, layout: Layout, clock: Callable[[], float] = time.monotonic) -> 'Transform':
        left = min(m.physical.left for m in layout.monitors)
        top = min(m.physical.top for m in layout.monitors)
        right = max(m.physical.right for m in layout.monitors)
        bottom = max(m.physical.bottom for m in layout.monitors)
        return cls(Frame.SCREEN_PHYSICAL, 'desktop', left, top, 1, 1, right - left, bottom - top, clock(), 1e9)

    @classmethod
    def for_region(cls, frame: Frame, source: str, region: Rect, image_size: Tuple[int, int],
                   clock: Callable[[], float] = time.monotonic, max_age_s: float = 10.0) -> 'Transform':
        """A capture of a physical region (monitor, window, client) stored at image_size pixels."""
        width, height = image_size
        return cls(frame, source, region.left, region.top, region.width / width, region.height / height,
                   width, height, clock(), max_age_s)

    @classmethod
    def for_viewport(cls, source: str, client: Rect, css_size: Tuple[int, int], device_pixel_ratio: float,
                     clock: Callable[[], float] = time.monotonic, max_age_s: float = 10.0) -> 'Transform':
        """Browser viewport CSS pixels; `client` is the page area in physical screen pixels."""
        width, height = css_size
        if abs(width * device_pixel_ratio - client.width) > 2 or abs(height * device_pixel_ratio - client.height) > 2:
            raise CoordinateError('Viewport size, devicePixelRatio and client area disagree; re-observe the page.')
        return cls(Frame.VIEWPORT, source, client.left, client.top, device_pixel_ratio, device_pixel_ratio,
                   width, height, clock(), max_age_s)

    def crop(self, region: Rect, out_size: Tuple[int, int], source: str) -> 'Transform':
        """A zoomed crop of this frame (crop-then-ground), resized to out_size pixels."""
        if region.left < 0 or region.top < 0 or region.right > self.width or region.bottom > self.height:
            raise CoordinateError('Crop region lies outside its source frame.')
        out_w, out_h = out_size
        return Transform(Frame.CROP, source, self.origin_x + region.left * self.scale_x,
                         self.origin_y + region.top * self.scale_y,
                         self.scale_x * region.width / out_w, self.scale_y * region.height / out_h,
                         out_w, out_h, self.captured_at, self.max_age_s)

    def scaled(self, factor: float, source: str) -> 'Transform':
        """The same frame stored at `factor` times its pixel size (screenshot downscaling)."""
        if not 0 < factor <= 1:
            raise CoordinateError('Screenshot scale factor must be in (0, 1].')
        return Transform(Frame.SCREENSHOT, source, self.origin_x, self.origin_y, self.scale_x / factor,
                         self.scale_y / factor, max(1, int(self.width * factor)), max(1, int(self.height * factor)),
                         self.captured_at, self.max_age_s)

    def to_physical(self, point: Point, layout: Layout, clock: Callable[[], float] = time.monotonic) -> Point:
        if point.frame is not self.frame or (point.source and point.source != self.source):
            raise CoordinateError(f'Point from {point.frame.value}/{point.source or "?"} does not belong to '
                                  f'{self.frame.value}/{self.source}.')
        if not (math.isfinite(point.x) and math.isfinite(point.y)):
            raise CoordinateError('Point is not finite.')
        if not (0 <= point.x < self.width and 0 <= point.y < self.height):
            raise CoordinateError(f'[{point.x:.1f},{point.y:.1f}] is outside the {self.width}x{self.height} '
                                  f'{self.frame.value}; refusing to clamp.')
        if clock() - self.captured_at > self.max_age_s:
            raise CoordinateError('The observation is stale; capture a fresh one before acting.')
        x, y = self.origin_x + point.x * self.scale_x, self.origin_y + point.y * self.scale_y
        layout.monitor_at(x, y)
        return Point(x, y, Frame.SCREEN_PHYSICAL, point.source)

    def from_physical(self, point: Point) -> Point:
        if point.frame is not Frame.SCREEN_PHYSICAL:
            raise CoordinateError('Expected a physical screen point.')
        x, y = (point.x - self.origin_x) / self.scale_x, (point.y - self.origin_y) / self.scale_y
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise CoordinateError('Physical point is outside this frame.')
        return Point(x, y, self.frame, self.source)


def visual_tokens(width: int, height: int) -> int:
    return math.ceil(width / 28) * math.ceil(height / 28)


def fit_scale(width: int, height: int, long_edge: int = MAX_LONG_EDGE, tokens: int = MAX_VISUAL_TOKENS) -> float:
    """Largest factor <= 1 whose resized image satisfies both image limits."""
    if width <= 0 or height <= 0:
        raise CoordinateError('Image size must be positive.')
    factor = min(1.0, long_edge / max(width, height))
    while visual_tokens(int(width * factor), int(height * factor)) > tokens:
        factor *= .99
    return factor


def ensure_per_monitor_dpi(user32: Optional[Any] = None) -> int:
    """Make the process per-monitor DPI aware once; return the effective awareness.

    main.py already does this through display.enable_high_dpi() before Tk. Calling again is
    harmless: Windows refuses a second change, so the current awareness is read back instead.
    """
    if user32 is None:
        if sys.platform != 'win32':  # pragma: no cover - Jarvis runs on Windows only
            return PER_MONITOR_AWARE
        import ctypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user32.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext(-4)  # PER_MONITOR_AWARE_V2; fails harmlessly if already set.
    awareness = int(user32.GetAwarenessFromDpiAwarenessContext(user32.GetThreadDpiAwarenessContext()))
    if awareness != PER_MONITOR_AWARE:
        raise CoordinateError(f'Process DPI awareness is {awareness}, not per-monitor; clicks would be offset.')
    return awareness


def layout_from_rects(rows: Sequence[Tuple[str, Tuple[int, int, int, int], float]]) -> Layout:
    return Layout(tuple(Monitor(name, Rect(*rect), scale) for name, rect, scale in rows))


def system_layout() -> Layout:
    """Enumerate real monitors (physical rects, effective DPI). Windows only."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    shcore = ctypes.WinDLL('shcore')
    rows: list[Tuple[str, Tuple[int, int, int, int], float]] = []

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT), ('rcWork', wintypes.RECT),
                    ('dwFlags', wintypes.DWORD), ('szDevice', wintypes.WCHAR * 32)]

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                       ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def collect(handle: Any, _dc: Any, _rect: Any, _data: Any) -> bool:
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            dpi_x, dpi_y = ctypes.c_uint(), ctypes.c_uint()
            if shcore.GetDpiForMonitor(handle, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                r = info.rcMonitor
                rows.append((info.szDevice, (r.left, r.top, r.right, r.bottom), dpi_x.value / 96))
        return True

    user32.EnumDisplayMonitors(None, None, callback_type(collect), 0)
    return layout_from_rects(rows)
