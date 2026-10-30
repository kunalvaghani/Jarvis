"""Route 4 vision executor: grounding geometry, staleness and refusals, with a deterministic fake grounder.

The fake "model" finds a colour by scanning pixels, so these tests check Jarvis's own mapping
(downscale, crop, negative monitor origins) without depending on a real model. The live model is
measured by benchmarks/vision_grounding.py and the desktop test at the end.
"""
import os
import sys

from PIL import Image, ImageDraw
import pytest

from jarvis.control.coords import Frame, Point, Rect, layout_from_rects
from jarvis.control.policy import Policy
from jarvis.control.routes.vision import OllamaGrounder, VisionExecutor, difference, parse_box
from jarvis.control.types import Action, ControlError, ErrorCategory, Route

DESKTOP = Rect(-1920, 0, 2560, 1440)  # Left 1080p monitor at a negative origin, right 1440p monitor.
LAYOUT = layout_from_rects([('LEFT', (-1920, 0, 0, 1080), 1.0), ('RIGHT', (0, 0, 2560, 1440), 1.5)])
COLOURS = {'red square': (220, 20, 20), 'blue square': (20, 20, 220)}


class Desktop:
    def __init__(self):
        self.image = Image.new('RGB', (DESKTOP.width, DESKTOP.height), (240, 240, 240))
        self.captures = 0

    def draw(self, rect, colour):
        ImageDraw.Draw(self.image).rectangle((rect[0] - DESKTOP.left, rect[1] - DESKTOP.top,
                                              rect[2] - DESKTOP.left - 1, rect[3] - DESKTOP.top - 1), fill=colour)

    def capture(self, region):
        self.captures += 1
        return self.image.crop((region.left - DESKTOP.left, region.top - DESKTOP.top,
                                region.right - DESKTOP.left, region.bottom - DESKTOP.top))


class ColourGrounder:
    name = 'colour-fake'

    def __init__(self, on_locate=None, shift=None, label=''):
        self.calls, self.on_locate, self.shift, self.label, self.reads = [], on_locate, shift, label, []

    def read(self, png, timeout_s):
        import io
        self.reads.append(Image.open(io.BytesIO(png)).size)
        return self.label

    def locate(self, png, target, timeout_s):
        import io
        image = Image.open(io.BytesIO(png)).convert('RGB')
        self.calls.append(image.size)
        if self.on_locate:
            self.on_locate(len(self.calls))
        want = COLOURS.get(target)
        xs, ys = [], []
        pixels = image.load()
        for y in range(0, image.height):
            for x in range(0, image.width):
                if want and all(abs(a - b) < 40 for a, b in zip(pixels[x, y], want)):
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return None
        box = (min(xs) / image.width, min(ys) / image.height, (max(xs) + 1) / image.width, (max(ys) + 1) / image.height)
        if self.shift and len(self.calls) == 2:
            box = tuple(min(1.0, v + self.shift) for v in box)
        return box


class FakeInput:
    def __init__(self):
        self.events = []

    def click(self, x, y, button='left', count=1, cancel=None):
        self.events.append(('click', x, y, button, count))
        return 'sendinput'

    def text(self, text, cancel=None):
        self.events.append(('text', text))

    def keys(self, text, repeat=1, cancel=None):
        self.events.append(('keys', text, repeat))

    def wheel(self, x, y, notches, cancel=None):
        self.events.append(('wheel', x, y, notches))


def make(desktop, grounder=None, window=(1, r'C:\Windows\notepad.exe', False), apps=frozenset({'notepad.exe'})):
    inp = FakeInput()
    executor = VisionExecutor(Policy(allowed_apps=apps), inp, grounder or ColourGrounder(), capture=desktop.capture,
                              layout=lambda: LAYOUT, window_at=lambda x, y: window)
    return executor, inp


def act(executor, name, point=None, **params):
    return executor.act(Action(name, name, Route.VISION, params=params, target=point, timeout_s=30))


@pytest.fixture(autouse=True)
def no_secure_desktop(monkeypatch):
    monkeypatch.setattr('jarvis.control.routes.vision.secure_desktop_active', lambda: False)


def test_parse_box_accepts_qwen_relative_boxes_only():
    assert parse_box('```json\n[{"bbox_2d": [329, 525, 389, 570], "label": "Save"}]\n```') == (.329, .525, .389, .57)
    assert parse_box('{"bbox_2d": null}') is None
    assert parse_box('no idea') is None
    assert parse_box('{"bbox_2d": [500, 10, 400, 20]}') is None    # Inverted.
    assert parse_box('{"bbox_2d": [10, 10, 1400, 20]}') is None    # Outside 0-1000: never clamped.
    assert parse_box('{"bbox_2d": [0, 0, 999, 998]}') is None      # "The whole image" is not an answer.
    assert parse_box('{"bbox_2d": [0, 0, 999, 300]}') == (0, 0, .999, .3)  # A wide toolbar is.


def test_grounder_refuses_non_loopback_servers():
    with pytest.raises(ControlError) as caught:
        OllamaGrounder(url='https://vision.example.com')
    assert caught.value.category is ErrorCategory.POLICY_DENIED
    OllamaGrounder(url='http://localhost:11434')


def test_grounder_parses_a_local_reply_without_network():
    class Reply:
        def read(self):
            return b'{"message": {"content": "100, 200, 300, 400]}"}}'  # Continuation of the prefilled answer.
    seen = {}

    def opener(request, timeout):
        seen['url'], seen['timeout'] = request.full_url, timeout
        seen['body'] = __import__('json').loads(request.data)
        return Reply()
    assert OllamaGrounder(opener=opener).locate(b'png', 'Save', 5) == (.1, .2, .3, .4)
    assert (seen['url'], seen['timeout']) == ('http://127.0.0.1:11434/api/chat', 5)
    assert seen['body']['messages'][-1] == {'role': 'assistant', 'content': OllamaGrounder.PREFIX}


@pytest.mark.parametrize('rect', [(-1500, 300, -1440, 360), (1800, 900, 1830, 930)])
def test_coarse_then_crop_clicks_the_true_centre_on_either_monitor(rect):
    desktop = Desktop()
    desktop.draw(rect, COLOURS['red square'])
    executor, inp = make(desktop)
    result = act(executor, 'click', target='red square', rect=(DESKTOP.left, DESKTOP.top, DESKTOP.right, DESKTOP.bottom))
    assert result.ok, result.text
    _, x, y, button, count = inp.events[0]
    assert (abs(x - (rect[0] + rect[2]) / 2) <= 1, abs(y - (rect[1] + rect[3]) / 2) <= 1) == (True, True)
    sizes = executor.grounder.calls
    assert max(sizes[0]) == 1280 and max(sizes[1]) <= 384  # Downscaled overview, then a native-resolution close-up.
    assert result.timings_ms['grounding'] >= 0 and 'capture' in result.timings_ms


def test_label_is_read_back_before_clicking():
    desktop = Desktop()
    desktop.draw((300, 300, 340, 340), COLOURS['red square'])
    executor, inp = make(desktop, ColourGrounder(label='Send  message, Archived'))
    result = act(executor, 'click', target='red square', label='send message', rect=(0, 0, 1600, 1000))
    assert result.ok and 'read back' in result.evidence, result.text
    assert executor.grounder.reads[0][0] >= 180  # Enlarged close-up for reading small UI text.
    wrong = make(desktop, ColourGrounder(label='Forms Dynamic'))
    refused = act(wrong[0], 'click', target='red square', label='Checkout', rect=(0, 0, 1600, 1000))
    assert refused.error_category is ErrorCategory.TARGET_NOT_FOUND and 'reads "Forms Dynamic"' in refused.text
    assert not wrong[1].events and not refused.executed


def test_missing_target_is_reported_and_nothing_is_clicked():
    desktop = Desktop()
    executor, inp = make(desktop)
    result = act(executor, 'click', target='blue square', rect=(0, 0, 800, 600))
    assert result.error_category is ErrorCategory.TARGET_NOT_FOUND and not result.executed and not inp.events


def test_overview_and_close_up_must_agree():
    desktop = Desktop()
    desktop.draw((300, 300, 340, 340), COLOURS['red square'])
    executor, inp = make(desktop, ColourGrounder(shift=.45))
    result = act(executor, 'click', target='red square', rect=(0, 0, 1600, 1000))
    assert result.error_category is ErrorCategory.TARGET_NOT_FOUND and 'disagree' in result.text and not inp.events
    # A matching label does not overrule the disagreement (measured: that caused a wrong click).
    labelled = make(desktop, ColourGrounder(shift=.45, label='Send'))
    refused = act(labelled[0], 'click', target='red square', label='Send', rect=(0, 0, 1600, 1000))
    assert 'disagree' in refused.text and not labelled[1].events


def test_screen_change_during_grounding_is_stale_not_clicked():
    desktop = Desktop()
    desktop.draw((300, 300, 340, 340), COLOURS['red square'])

    def move(call):
        if call == 2:  # The UI re-renders while the model is thinking.
            desktop.draw((300, 300, 340, 340), (240, 240, 240))
            desktop.draw((600, 300, 640, 340), COLOURS['red square'])
    executor, inp = make(desktop, ColourGrounder(on_locate=move))
    result = act(executor, 'click', target='red square', rect=(0, 0, 1600, 1000))
    assert result.error_category is ErrorCategory.STALE_REF and not result.executed and not inp.events


@pytest.mark.parametrize('window, category', [((1, r'C:\Windows\regedit.exe', True), ErrorCategory.ELEVATED_TARGET),
                                              ((1, r'C:\Tools\unknown.exe', False), ErrorCategory.POLICY_DENIED)])
def test_elevated_or_unlisted_window_under_the_point_is_refused(window, category):
    desktop = Desktop()
    desktop.draw((300, 300, 340, 340), COLOURS['red square'])
    executor, inp = make(desktop, window=window)
    result = act(executor, 'click', target='red square', rect=(0, 0, 1600, 1000))
    assert result.error_category is category and not inp.events


def test_points_from_a_downscaled_screenshot_map_back_to_physical_pixels():
    desktop = Desktop()
    executor, inp = make(desktop)
    obs = executor.observe(rect=(DESKTOP.left, DESKTOP.top, DESKTOP.right, DESKTOP.bottom))  # Both monitors: too big to send whole.
    image = Image.open(__import__('io').BytesIO(obs.screenshot))
    assert image.size == (obs.transform.width, obs.transform.height) and image.width < DESKTOP.width
    scale = image.width / DESKTOP.width
    result = act(executor, 'double_click', point=Point((1000 - DESKTOP.left) * scale, 500 * scale, Frame.SCREENSHOT, obs.scope))
    assert result.ok, result.text
    assert inp.events[0][:3] == ('click', 1000, 500) and inp.events[0][4] == 2
    outside = act(executor, 'click', point=Point(image.width + 5, 10, Frame.SCREENSHOT, obs.scope))
    assert outside.error_category is ErrorCategory.INVALID_ARGUMENTS and len(inp.events) == 1
    unknown = act(executor, 'click', point=Point(5, 5, Frame.SCREENSHOT, 'shot-999'))
    assert unknown.error_category is ErrorCategory.STALE_REF


def test_type_scroll_and_key_go_through_shared_input():
    desktop = Desktop()
    desktop.draw((100, 100, 300, 140), COLOURS['blue square'])
    executor, inp = make(desktop)
    assert act(executor, 'type', target='blue square', text='hello', rect=(0, 0, 1000, 800)).ok
    assert act(executor, 'scroll', target='blue square', notches=-2, rect=(0, 0, 1000, 800)).ok
    assert act(executor, 'key', text='ctrl+s').ok
    assert [e[0] for e in inp.events] == ['click', 'text', 'wheel', 'keys']
    assert inp.events[1] == ('text', 'hello') and inp.events[2][3] == -2


def test_signature_probe_and_difference():
    desktop = Desktop()
    executor, _ = make(desktop)
    before = executor.probe('signature', rect=(0, 0, 400, 400))
    desktop.draw((10, 10, 200, 200), (0, 0, 0))
    assert executor.probe('signature', rect=(0, 0, 400, 400)) != before
    a = Image.new('RGB', (10, 10), (0, 0, 0))
    assert difference(a, a) == 0 and difference(a, Image.new('RGB', (10, 10), (255, 255, 255))) == 255
    assert executor.probe('located', target='blue square', rect=(0, 0, 400, 400)) is False


def test_cancel_and_health():
    desktop = Desktop()
    desktop.draw((300, 300, 340, 340), COLOURS['red square'])
    executor, inp = make(desktop, ColourGrounder(on_locate=lambda call: executor.cancel()))
    result = act(executor, 'click', target='red square', rect=(0, 0, 1600, 1000))
    assert result.error_category is ErrorCategory.CANCELLED and not inp.events
    assert executor.health_check().ok and executor.health_check().capabilities['local_only']


@pytest.mark.skipif(sys.platform != 'win32' or os.environ.get('JARVIS_DESKTOP_TESTS') != '1',
                    reason='real-desktop test: set JARVIS_DESKTOP_TESTS=1')
def test_live_model_clicks_a_canvas_shape_in_a_real_chrome_window():
    """Canvas shapes have no DOM or UIA element: only the vision route can hit them."""
    import importlib.util
    from pathlib import Path
    import time
    from playwright.sync_api import sync_playwright
    from jarvis.control.input import Input
    from jarvis.control.locks import LockManager
    spec = importlib.util.spec_from_file_location('jarvis_d1_site', Path(__file__).parents[1] / 'benchmarks/sites/d1/server.py')
    d1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d1)
    site = d1.Site()
    base, _ = site.start()
    executor = VisionExecutor(Policy(allowed_apps=frozenset({'chrome.exe'})), Input(LockManager(), 'vision-tests', use_pointer=False),
                              OllamaGrounder('qwen3-vl:2b'))
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=False, args=['--window-position=40,40', '--window-size=900,600'])
            page = browser.new_page(viewport={'width': 860, 'height': 480})
            page.goto(f'{base}/canvas.html')
            page.bring_to_front()
            import ctypes
            handle = ctypes.WinDLL('user32').GetForegroundWindow()
            # A new window keeps changing for a moment (first paint, the automation infobar). Wait until two
            # signatures agree, as the planner would before relying on a screenshot.
            previous, deadline = None, time.time() + 10
            while time.time() < deadline:
                current = executor.probe('signature', handle=handle)
                if current == previous:
                    break
                previous = current
                time.sleep(.5)
            result = act(executor, 'click', target='the green square', handle=handle)
            assert result.ok, result.text
            assert page.inner_text('#hit') == 'green circle', (result.text, page.inner_text('#hit'))  # Independent DOM check.
            browser.close()
    finally:
        site.stop()
