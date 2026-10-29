import sys

import pytest

from jarvis.control.coords import (CoordinateError, Frame, Layout, Monitor, Point, Rect, Transform, ensure_per_monitor_dpi,
                                   fit_scale, layout_from_rects, system_layout, visual_tokens)

# Primary 1920x1080 at 100%, left monitor 2560x1440 at 150% with a NEGATIVE origin,
# right monitor 1600x900 physical at 125%.
LAYOUT = layout_from_rects([
    ('primary', (0, 0, 1920, 1080), 1.0),
    ('left', (-2560, -360, 0, 1080), 1.5),
    ('right', (1920, 0, 3520, 900), 1.25),
])


def clock(value=100.0):
    return lambda: value


def test_rect_and_monitor_validation():
    with pytest.raises(CoordinateError):
        Rect(10, 10, 10, 20)
    with pytest.raises(CoordinateError):
        Monitor('bad', Rect(0, 0, 10, 10), 0)
    with pytest.raises(CoordinateError):
        Layout(())
    assert Rect(0, 0, 4, 2).width == 4 and Rect(0, 0, 4, 2).height == 2


def test_monitor_lookup_handles_negative_origins_and_gaps():
    assert LAYOUT.monitor_at(-1, 500).name == 'left'
    assert LAYOUT.monitor_at(-2560, -360).name == 'left'
    assert LAYOUT.monitor_at(1920, 0).name == 'right'
    with pytest.raises(CoordinateError):
        LAYOUT.monitor_at(2000, 1000)  # below the shorter right monitor: on no monitor, never guessed
    with pytest.raises(CoordinateError):
        LAYOUT.monitor_at(-2561, 0)


def test_logical_physical_round_trip_per_monitor_scale():
    left = LAYOUT.monitors[1]
    assert left.logical == Rect(-2560, -360, -2560 + 1707, -360 + 960)
    logical = Point(-2560 + 100, -360 + 100, Frame.SCREEN_LOGICAL)
    physical = LAYOUT.logical_to_physical(logical)
    assert (physical.x, physical.y) == (-2560 + 150, -360 + 150)
    back = LAYOUT.physical_to_logical(physical)
    assert (back.x, back.y) == (logical.x, logical.y)
    right = LAYOUT.logical_to_physical(Point(1920 + 80, 40, Frame.SCREEN_LOGICAL))
    assert (right.x, right.y) == (2020, 50)
    with pytest.raises(CoordinateError):
        LAYOUT.logical_to_physical(Point(0, 0, Frame.SCREEN_PHYSICAL))
    with pytest.raises(CoordinateError):
        LAYOUT.physical_to_logical(Point(0, 0, Frame.SCREEN_LOGICAL))
    with pytest.raises(CoordinateError):
        LAYOUT.logical_to_physical(Point(5000, 5000, Frame.SCREEN_LOGICAL))


def test_window_screenshot_scaled_and_cropped_maps_back_exactly():
    window = Rect(-2000, 100, -800, 900)  # 1200x800 physical window on the 150% monitor
    capture = Transform.for_region(Frame.WINDOW, 'win-1', window, (1200, 800), clock(10))
    shot = capture.scaled(.5, 'shot-1')
    assert (shot.width, shot.height) == (600, 400)
    p = shot.to_physical(Point(300, 200, Frame.SCREENSHOT, 'shot-1'), LAYOUT, clock(11))
    assert (p.x, p.y) == (-1400, 500)
    crop = shot.crop(Rect(200, 100, 300, 200), (400, 400), 'crop-1')  # 4x zoom of a 100x100 region
    q = crop.to_physical(Point(200, 200, Frame.CROP, 'crop-1'), LAYOUT, clock(12))
    assert (q.x, q.y) == (-2000 + (200 + 50) * 2, 100 + (100 + 50) * 2)
    assert crop.from_physical(q) == Point(200, 200, Frame.CROP, 'crop-1')


def test_out_of_bounds_stale_foreign_and_nonfinite_points_are_rejected_not_clamped():
    t = Transform.for_region(Frame.WINDOW, 'w', Rect(0, 0, 100, 100), (100, 100), clock(0), max_age_s=5)
    for bad in (Point(100, 5, Frame.WINDOW, 'w'), Point(-1, 5, Frame.WINDOW, 'w'), Point(float('nan'), 1, Frame.WINDOW, 'w')):
        with pytest.raises(CoordinateError):
            t.to_physical(bad, LAYOUT, clock(1))
    with pytest.raises(CoordinateError, match='stale'):
        t.to_physical(Point(5, 5, Frame.WINDOW, 'w'), LAYOUT, clock(6))
    with pytest.raises(CoordinateError, match='does not belong'):
        t.to_physical(Point(5, 5, Frame.WINDOW, 'other'), LAYOUT, clock(1))
    with pytest.raises(CoordinateError, match='does not belong'):
        t.to_physical(Point(5, 5, Frame.SCREENSHOT, 'w'), LAYOUT, clock(1))
    off = Transform.for_region(Frame.WINDOW, 'off', Rect(1920, 950, 2020, 1050), (100, 100), clock(0))
    with pytest.raises(CoordinateError, match='no monitor'):
        off.to_physical(Point(50, 50, Frame.WINDOW, 'off'), LAYOUT, clock(1))


def test_viewport_uses_device_pixel_ratio_and_detects_mismatch():
    client = Rect(1930, 120, 1930 + 1250, 120 + 750)  # 1000x600 CSS at DPR 1.25
    view = Transform.for_viewport('tab-1', client, (1000, 600), 1.25, clock(0))
    p = view.to_physical(Point(400, 200, Frame.VIEWPORT, 'tab-1'), LAYOUT, clock(1))
    assert (p.x, p.y) == (1930 + 500, 120 + 250)
    with pytest.raises(CoordinateError, match='disagree'):
        Transform.for_viewport('tab-1', client, (1000, 600), 1.0, clock(0))


def test_transform_argument_validation():
    t = Transform.for_region(Frame.WINDOW, 'w', Rect(0, 0, 100, 100), (100, 100), clock(0))
    with pytest.raises(CoordinateError):
        t.crop(Rect(50, 50, 150, 150), (10, 10), 'c')
    with pytest.raises(CoordinateError):
        t.scaled(1.5, 's')
    with pytest.raises(CoordinateError):
        t.from_physical(Point(0, 0, Frame.WINDOW))
    with pytest.raises(CoordinateError):
        t.from_physical(Point(500, 500, Frame.SCREEN_PHYSICAL))
    with pytest.raises(CoordinateError):
        Transform(Frame.WINDOW, 'w', 0, 0, 0, 1, 10, 10, 0)
    with pytest.raises(CoordinateError):
        Transform(Frame.WINDOW, 'w', 0, 0, 1, 1, 0, 10, 0)
    desktop = Transform.identity_screen(LAYOUT, clock(0))
    assert (desktop.origin_x, desktop.origin_y, desktop.width, desktop.height) == (-2560, -360, 6080, 1440)


def test_fit_scale_matches_documented_limits():
    assert visual_tokens(1920, 1080) == 2691 and fit_scale(1920, 1080) == 1.0
    assert visual_tokens(2560, 1440) == 4784 and fit_scale(2560, 1440) == 1.0
    s = fit_scale(3840, 2160)
    assert s < 1 and visual_tokens(int(3840 * s), int(2160 * s)) <= 4784 and int(3840 * s) <= 2576
    square = fit_scale(2576, 2576)  # fits the long edge but not the token budget
    assert square < 1 and visual_tokens(int(2576 * square), int(2576 * square)) <= 4784
    with pytest.raises(CoordinateError):
        fit_scale(0, 10)


class FakeUser32:
    def __init__(self, awareness):
        self.awareness, self.calls = awareness, []

    def SetProcessDpiAwarenessContext(self, value):
        self.calls.append(value)
        return 0

    def GetThreadDpiAwarenessContext(self):
        return 'ctx'

    def GetAwarenessFromDpiAwarenessContext(self, _ctx):
        return self.awareness


def test_dpi_awareness_is_enforced():
    user = FakeUser32(2)
    assert ensure_per_monitor_dpi(user) == 2 and user.calls == [-4]
    with pytest.raises(CoordinateError, match='not per-monitor'):
        ensure_per_monitor_dpi(FakeUser32(0))


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows monitor enumeration')
def test_real_layout_and_awareness_are_readable():
    assert ensure_per_monitor_dpi() == 2
    layout = system_layout()
    assert layout.monitors and all(m.physical.width > 0 and .5 <= m.scale <= 5 for m in layout.monitors)
