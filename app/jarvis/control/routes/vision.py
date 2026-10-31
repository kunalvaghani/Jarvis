"""Route 4: vision fallback (doc sections 11.4, 12.4). Used only when no API, browser ref or UIA element exists.

Screens are captured with mss in physical pixels (the process is per-monitor DPI aware). A target is
grounded crop-then-ground: a coarse pass on a downscaled capture, then a refine pass on a
full-resolution crop around the coarse hit; both passes map back through coords.Transform, which
refuses (never clamps) points outside the frame. Screenshots never leave the PC: the grounder must be
a loopback model server. Before any click the target patch is re-captured and compared, so a screen
that changed while the model was thinking is reported as stale instead of clicked blind. Elevated or
non-allowlisted windows under the point are refused. All input goes through input.Input.
"""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, replace
import hashlib
import io
import itertools
import json
import os
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple
from urllib.parse import urlsplit
import urllib.request

from PIL import Image, ImageChops, ImageStat

from ..coords import CoordinateError, Frame, Layout, Point, Rect, Transform, ensure_per_monitor_dpi, fit_scale, system_layout
from ..executor import Health, RouteExecutor
from ..input import Input
from ..policy import Policy
from ..progress import ProgressEvent, Sink, emit
from ..timing import StageTimer
from ..types import Action, ActionResult, ControlError, ErrorCategory, Observation, Route
from .uia import _process_info, secure_desktop_active

COARSE_EDGE = 1280      # Long edge of the first grounding pass.
CROP_MIN = 384          # Smallest refine crop, physical pixels.
CROP_FACTOR = 4         # Refine crop = this many coarse boxes around the hit.
CHANGE_LIMIT = 12.0     # Mean absolute grey-level difference that counts as "the screen changed".
MAX_AGE_S = 60.0
WHOLE = .9               # A box this large on both axes is not an answer.
READ_PAD = 1.6           # Read-back crop = this many box widths around the point (labels sit beside checkboxes).        # Grounding takes seconds; the patch comparison is the real staleness check.
BOX = re.compile(r'"?bbox_2d"?\s*:\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]')
GA_ROOT = 2

Box = Tuple[float, float, float, float]  # Normalized 0-1 (left, top, right, bottom).


class Grounder(Protocol):
    name: str

    def locate(self, png: bytes, target: str, timeout_s: float) -> Optional[Box]:
        """Normalized box of `target` in the image, or None when it is not visible."""

    def read(self, png: bytes, timeout_s: float) -> str:
        """The text of the control at the centre of the image (OCR-style read-back)."""


class OllamaGrounder:
    """Qwen3-VL through a local Ollama server. Qwen3-VL boxes are relative, 0-1000 on each axis.

    The installed Qwen3-VL builds think before answering even with think=false (measured: 150-400
    tokens, 10-35 s per pass). Starting the assistant turn with the answer prefix skips that: 20
    tokens, ~0.5 s warm on the 2B model. A 4k context keeps the model inside the 4 GB GPU.
    """
    PREFIX = '{"bbox_2d": ['

    def __init__(self, model: str = 'qwen3-vl:2b', url: str = 'http://127.0.0.1:11434', num_predict: int = 40,
                 num_ctx: int = 4096, opener: Optional[Callable[..., Any]] = None) -> None:
        host = (urlsplit(url).hostname or '').lower()
        if host not in ('127.0.0.1', 'localhost', '::1'):
            raise ControlError('Screenshots stay on this PC: the vision model must run on a loopback address.',
                               ErrorCategory.POLICY_DENIED)
        self.name, self.url, self.num_predict, self.num_ctx = model, url.rstrip('/'), num_predict, num_ctx
        self.opener = opener or urllib.request.urlopen

    def _chat(self, png: bytes, prompt: str, prefix: str, num_predict: int, timeout_s: float) -> str:
        body = {'model': self.name, 'stream': False, 'think': False, 'keep_alive': '10m',
                'options': {'temperature': 0, 'num_predict': num_predict, 'num_ctx': self.num_ctx},
                'messages': [{'role': 'user', 'images': [base64.b64encode(png).decode()], 'content': prompt},
                             {'role': 'assistant', 'content': prefix}]}
        request = urllib.request.Request(self.url + '/api/chat', json.dumps(body).encode(), {'Content-Type': 'application/json'})
        try:
            reply = json.loads(self.opener(request, timeout=timeout_s).read())
        except OSError as error:
            raise ControlError(f'The local vision model did not answer: {error}', ErrorCategory.TOOL_ERROR) from error
        return str(reply.get('message', {}).get('content', ''))

    def locate(self, png: bytes, target: str, timeout_s: float) -> Optional[Box]:
        content = self._chat(png, f'Locate "{target}" in the screenshot. Reply with JSON only: {{"bbox_2d": [x1, y1, x2, y2]}}',
                             self.PREFIX, self.num_predict, timeout_s)
        return parse_box(content if 'bbox_2d' in content else self.PREFIX + content)

    def release(self) -> None:
        """Unload the model from the GPU now (4 GB holds one vision model at a time). Best effort."""
        body = json.dumps({'model': self.name, 'keep_alive': 0}).encode()
        try:
            self.opener(urllib.request.Request(self.url + '/api/generate', body, {'Content-Type': 'application/json'}),
                        timeout=15).read()
        except OSError:
            pass

    def read(self, png: bytes, timeout_s: float) -> str:
        content = self._chat(png, 'Read the text of the control at the exact centre of this image.', 'Text: "', 24, timeout_s)
        return content.split('"', 1)[0].strip()


def parse_box(text: str) -> Optional[Box]:
    match = BOX.search(text)
    if match is None:
        return None
    x1, y1, x2, y2 = (float(v) for v in match.groups())
    if not (0 <= x1 < x2 <= 1000 and 0 <= y1 < y2 <= 1000):
        return None  # Inverted or out-of-range boxes are model noise, not a location.
    if x2 - x1 >= WHOLE * 1000 and y2 - y1 >= WHOLE * 1000:
        return None  # "The whole image" is how small models answer when the target is absent.
    return x1 / 1000, y1 / 1000, x2 / 1000, y2 / 1000


def normal(text: str) -> str:
    return ' '.join(re.sub(r'[^\w]+', ' ', text.casefold()).split())


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, 'PNG', optimize=False, compress_level=1)
    return buffer.getvalue()


def difference(a: Image.Image, b: Image.Image) -> float:
    """Mean absolute grey-level difference of two same-size images (0-255)."""
    return float(ImageStat.Stat(ImageChops.difference(a.convert('L'), b.convert('L'))).mean[0])


def mss_capture(region: Rect) -> Image.Image:
    import mss
    with mss.MSS() as grabber:
        shot = grabber.grab({'left': region.left, 'top': region.top, 'width': region.width, 'height': region.height})
        return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')


@dataclass(frozen=True)
class Shot:
    source: str
    region: Rect          # Physical screen pixels.
    image: Image.Image    # Full resolution, one pixel per physical pixel.
    transform: Transform  # SCREENSHOT frame at full resolution.
    view: Optional[Transform] = None  # The frame of the image handed out by observe(), if downscaled.


@dataclass(frozen=True)
class Located:
    point: Point          # Physical screen point.
    box: Rect             # Physical screen box.
    shot: Shot
    evidence: str


class VisionExecutor(RouteExecutor):
    route = Route.VISION

    def __init__(self, policy: Policy, input: Input, grounder: Grounder,
                 capture: Callable[[Rect], Image.Image] = mss_capture, layout: Optional[Callable[[], Layout]] = None,
                 window_at: Optional[Callable[[int, int], Tuple[int, str, bool]]] = None,
                 clock: Callable[[], float] = time.monotonic, fallbacks: Sequence[Grounder] = (),
                 tight_escalation: bool = False) -> None:
        """`fallbacks` are tried in order, each on a fresh capture, only when the previous model refused.
        With `tight_escalation` (flag vision.tight_escalation) a fallback whose predecessor found the target in the
        overview grounds only the close-up around that overview box instead of repeating the full-screen pass."""
        if os.name == 'nt' and capture is mss_capture:
            ensure_per_monitor_dpi()  # mss and SendInput must agree on physical pixels.
        self.policy, self.input, self.grounder, self.capture = policy, input, grounder, capture
        self.fallbacks = tuple(fallbacks)
        self.tight_escalation = tight_escalation
        self._overview: Optional[Box] = None  # The last overview box of a model that then refused.
        self.progress: Optional[Sink] = None  # Island updates while a model searches (display only).
        self.layout = layout or system_layout
        self.window_at = window_at or _window_at
        self.clock = clock
        self.shots: Dict[str, Shot] = {}
        self._ids = itertools.count(1)
        self._lock = threading.RLock()
        self._cancelled = threading.Event()

    # Lifecycle ------------------------------------------------------------------
    def health_check(self) -> Health:
        try:
            layout = self.layout()
        except Exception as error:
            return Health(False, f'No monitor layout: {error}')
        chain = [g.name for g in (self.grounder, *self.fallbacks)]
        return Health(True, f'{len(layout.monitors)} monitor(s), grounders {" -> ".join(chain)}',
                      {'grounder': self.grounder.name, 'chain': chain, 'local_only': True})

    def cancel(self) -> None:
        self._cancelled.set()

    def close(self) -> None:
        self.shots.clear()

    # Observation ----------------------------------------------------------------
    def region(self, handle: Optional[int] = None, rect: Optional[Sequence[int]] = None) -> Rect:
        layout = self.layout()
        if rect is not None:
            region = Rect(*(int(v) for v in rect))
        elif handle:
            box = wintypes.RECT()
            if not ctypes.WinDLL('user32').GetWindowRect(int(handle), ctypes.byref(box)):
                raise ControlError(f'Window {handle} no longer exists.', ErrorCategory.STALE_REF)
            region = Rect(box.left, box.top, box.right, box.bottom)
        else:
            user32 = ctypes.WinDLL('user32')
            box = wintypes.RECT()
            front = user32.GetForegroundWindow()
            if front and user32.GetWindowRect(front, ctypes.byref(box)):
                monitor = layout.monitor_at((box.left + box.right) / 2, (box.top + box.bottom) / 2)
            else:
                monitor = layout.monitors[0]
            return monitor.physical
        # Clip to the desktop: maximized windows overhang their monitor by a few pixels.
        left = max(region.left, min(m.physical.left for m in layout.monitors))
        top = max(region.top, min(m.physical.top for m in layout.monitors))
        right = min(region.right, max(m.physical.right for m in layout.monitors))
        bottom = min(region.bottom, max(m.physical.bottom for m in layout.monitors))
        return Rect(left, top, right, bottom)

    def shoot(self, region: Rect) -> Shot:
        image = self.capture(region)
        if image.size != (region.width, region.height):
            raise ControlError('The capture size does not match the region (DPI scaling mismatch); refusing to map points.',
                               ErrorCategory.TOOL_ERROR)
        source = f'shot-{next(self._ids)}'
        shot = Shot(source, region, image,
                    Transform.for_region(Frame.SCREENSHOT, source, region, image.size, self.clock, MAX_AGE_S))
        with self._lock:
            self.shots[source] = shot
            for old in list(self.shots)[:-8]:  # Keep the last few observations for Point targets.
                del self.shots[old]
        return shot

    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        region = self.region(options.get('handle'), options.get('rect'))
        shot = self.shoot(region)
        factor = min(1.0, fit_scale(*shot.image.size))
        image = shot.image if factor == 1 else shot.image.resize(
            (max(1, int(shot.image.width * factor)), max(1, int(shot.image.height * factor))), Image.Resampling.LANCZOS)
        transform = shot.transform if factor == 1 else shot.transform.scaled(factor, shot.source)
        with self._lock:
            self.shots[shot.source] = replace(shot, view=transform)
        return Observation(Route.VISION, shot.source, text=f'Screenshot {image.width}x{image.height} of {region}',
                           screenshot=png_bytes(image), transform=transform,
                           state={'local_only': True, 'region': (region.left, region.top, region.right, region.bottom)})

    # Grounding ------------------------------------------------------------------
    def locate(self, target: str, region: Rect, timeout_s: float = 60.0, timer: Optional[StageTimer] = None,
               label: str = '') -> Located:
        """`label` is the text the target shows, when known; it is read back at the point before anything is trusted."""
        if not target.strip() or len(target) > 200:
            raise ControlError('Describe the target in 1-200 characters.', ErrorCategory.INVALID_ARGUMENTS)
        timer = timer or StageTimer()
        with timer.stage('capture'):
            shot = self.shoot(region)
        deadline = self.clock() + timeout_s
        refusals: List[str] = []
        chain = (self.grounder, *self.fallbacks)
        try:
            for index, grounder in enumerate(chain):
                if index:  # Free the GPU for the bigger model instead of spilling both onto the CPU.
                    _release(chain[index - 1])
                    with timer.stage('capture'):  # The next model sees the screen as it is now, not as it was.
                        shot = self.shoot(region)
                emit(self.progress, ProgressEvent(Route.VISION, 'locating',
                                                  ('Looking closer' if index else 'Finding') + f' "{target[:50]}"',
                                                  grounder.name, 'Bigger model' if index else 'On-screen search'))
                hint = self._overview if index and self.tight_escalation else None
                self._overview = None
                try:
                    try:
                        found = self._locate_with(grounder, shot, target, deadline, timer, label, hint)
                    except ControlError as error:
                        if hint is None or error.category is not ErrorCategory.TARGET_NOT_FOUND:
                            raise
                        # The smaller model's overview box may be off target (D1 "Send message", 2026-10-31):
                        # the bigger model then makes its own full pass, as without tight escalation.
                        found = self._locate_with(grounder, shot, target, deadline, timer, label)
                except ControlError as error:
                    if error.category is not ErrorCategory.TARGET_NOT_FOUND:
                        raise  # Stale screen, timeout or cancel: a bigger model would not help.
                    refusals.append(f'{grounder.name}: {error}')
                    continue
                if refusals:
                    found = replace(found, evidence=found.evidence + f' after {len(refusals)} refusal(s)')
                return found
        finally:
            if refusals and len(chain) > 1:
                _release(chain[min(len(refusals), len(chain) - 1)])  # Give the GPU back to the everyday model.
        detail = refusals[-1].split(': ', 1)[1]
        raise ControlError(detail if len(refusals) == 1 else f'{detail} ({len(refusals)} models refused.)',
                           ErrorCategory.TARGET_NOT_FOUND)

    def _locate_with(self, grounder: Grounder, shot: Shot, target: str, deadline: float, timer: StageTimer,
                     label: str, overview: Optional[Box] = None) -> Located:
        """`overview`: a smaller model's overview box for this region; when given, only the close-up is grounded."""
        if overview is not None:
            coarse: Optional[Box] = overview
        else:
            factor = min(1.0, COARSE_EDGE / max(shot.image.size))
            coarse_image = shot.image if factor == 1 else shot.image.resize(
                (max(1, round(shot.image.width * factor)), max(1, round(shot.image.height * factor))), Image.Resampling.LANCZOS)
            with timer.stage('grounding'):
                coarse = self._ground(grounder, coarse_image, target, deadline)
        if coarse is None:
            raise ControlError(f'"{target[:80]}" is not visible on screen.', ErrorCategory.TARGET_NOT_FOUND)
        self._overview = coarse  # Kept for a bigger model if a later check refuses.
        width, height = shot.image.size
        cx, cy = (coarse[0] + coarse[2]) / 2 * width, (coarse[1] + coarse[3]) / 2 * height
        bw, bh = (coarse[2] - coarse[0]) * width, (coarse[3] - coarse[1]) * height
        side_w = min(width, max(CROP_MIN, round(bw * CROP_FACTOR)))
        side_h = min(height, max(CROP_MIN, round(bh * CROP_FACTOR)))
        left = int(min(max(0, cx - side_w / 2), width - side_w))
        top = int(min(max(0, cy - side_h / 2), height - side_h))
        crop_rect = Rect(left, top, left + side_w, top + side_h)
        crop_image = shot.image.crop((crop_rect.left, crop_rect.top, crop_rect.right, crop_rect.bottom))
        with timer.stage('grounding'):
            fine = self._ground(grounder, crop_image, target, deadline)
        if fine is None:
            raise ControlError(f'"{target[:80]}" was found in the overview but not up close; nothing was clicked.',
                               ErrorCategory.TARGET_NOT_FOUND)
        crop = shot.transform.crop(crop_rect, crop_image.size, shot.source)
        fx, fy = (fine[0] + fine[2]) / 2 * crop.width, (fine[1] + fine[3]) / 2 * crop.height
        # The close-up must agree with the overview; otherwise two similar targets competed. This stays
        # unconditional: letting a label read-back overrule it was measured to cause a wrong click (2026-10-30).
        sx, sy = crop_rect.left + fx, crop_rect.top + fy
        slack_x, slack_y = max(bw, 24), max(bh, 24)
        if abs(sx - cx) > slack_x or abs(sy - cy) > slack_y:
            raise ControlError(f'The overview and the close-up disagree about "{target[:80]}"; nothing was clicked.',
                               ErrorCategory.TARGET_NOT_FOUND)
        try:
            point = crop.to_physical(Point(fx, fy, Frame.CROP, shot.source), self.layout(), self.clock)
        except CoordinateError as error:  # Grounding outlived the capture, or the point fell off every monitor.
            raise ControlError(f'{error} Nothing was clicked.', ErrorCategory.STALE_REF) from error
        box = Rect(round(crop.origin_x + fine[0] * crop.width * crop.scale_x),
                   round(crop.origin_y + fine[1] * crop.height * crop.scale_y),
                   max(round(crop.origin_x + fine[2] * crop.width * crop.scale_x),
                       round(crop.origin_x + fine[0] * crop.width * crop.scale_x) + 1),
                   max(round(crop.origin_y + fine[3] * crop.height * crop.scale_y),
                       round(crop.origin_y + fine[1] * crop.height * crop.scale_y) + 1))
        evidence = f'{grounder.name} coarse+crop at ({point.x:.0f}, {point.y:.0f})'
        if label.strip():
            evidence += self._read_back(grounder, shot, sx, sy, box, label, deadline, timer)
        return Located(point, box, shot, evidence)

    def _read_back(self, grounder: Grounder, shot: Shot, x: float, y: float, box: Rect, text: str, deadline: float,
                   timer: StageTimer) -> str:
        """Read the label at the grounded point; a different label means the model picked the wrong control."""
        width, height = shot.image.size
        half_w = max(60, round(box.width * shot.transform.scale_x ** -1 * READ_PAD / 2) + 30)
        half_h = max(30, round(box.height * shot.transform.scale_y ** -1 * READ_PAD / 2))
        area = (max(0, round(x) - half_w), max(0, round(y) - half_h), min(width, round(x) + half_w), min(height, round(y) + half_h))
        patch = shot.image.crop(area)
        patch = patch.resize((patch.width * 3, patch.height * 3), Image.Resampling.LANCZOS)  # Small UI text reads better enlarged.
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise ControlError('Locating the target took too long.', ErrorCategory.TIMEOUT)
        with timer.stage('grounding'):
            seen = grounder.read(png_bytes(patch), remaining)
        if normal(text) not in normal(seen):
            raise ControlError(f'The control found for "{text[:60]}" reads "{seen[:60]}"; nothing was clicked.',
                               ErrorCategory.TARGET_NOT_FOUND)
        return f'; label read back "{seen[:60]}"'

    def _ground(self, grounder: Grounder, image: Image.Image, target: str, deadline: float) -> Optional[Box]:
        if self._cancelled.is_set():
            raise ControlError('Cancelled.', ErrorCategory.CANCELLED)
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise ControlError('Locating the target took too long.', ErrorCategory.TIMEOUT)
        return grounder.locate(png_bytes(image), target, remaining)

    # Safety checks before input ----------------------------------------------------
    def _unchanged(self, shot: Shot, box: Rect) -> None:
        """Re-capture the target's surroundings and compare with what the model saw."""
        margin = 8
        left, top = max(shot.region.left, box.left - margin), max(shot.region.top, box.top - margin)
        right, bottom = min(shot.region.right, box.right + margin), min(shot.region.bottom, box.bottom + margin)
        patch = Rect(left, top, right, bottom)
        before = shot.image.crop((left - shot.region.left, top - shot.region.top,
                                  right - shot.region.left, bottom - shot.region.top))
        now = self.capture(patch)
        change = difference(before, now)
        if change > CHANGE_LIMIT:
            raise ControlError(f'The screen changed around the target while it was being located (difference '
                               f'{change:.0f}); look again before clicking.', ErrorCategory.STALE_REF)

    def _admit(self, x: int, y: int) -> str:
        if secure_desktop_active():
            raise ControlError('A secure-desktop prompt (UAC, lock screen) is showing; only you can answer it.',
                               ErrorCategory.SECURE_DESKTOP)
        handle, executable, elevated = self.window_at(x, y)
        self.policy.check_app(executable or 'unknown.exe', elevated)
        return os.path.basename(executable)

    def _resolve(self, action: Action, timer: StageTimer) -> Located:
        target, p = action.target, action.params
        if isinstance(target, Point):
            shot = self.shots.get(target.source)
            if shot is None:
                raise ControlError(f'Screenshot {target.source or "?"} is no longer available; take a new one.',
                                   ErrorCategory.STALE_REF)
            transform = shot.view or shot.transform  # Points are read off the image observe() returned.
            try:
                point = transform.to_physical(target, self.layout(), self.clock)
            except CoordinateError as error:
                raise ControlError(str(error), ErrorCategory.STALE_REF if 'stale' in str(error) else
                                   ErrorCategory.INVALID_ARGUMENTS) from error
            x, y = round(point.x), round(point.y)
            return Located(point, Rect(x - 6, y - 6, x + 6, y + 6), shot, 'point from an earlier screenshot')
        description = str(p.get('target', '')).strip()
        if not description:
            raise ControlError('Give a target description or a screenshot point.', ErrorCategory.INVALID_ARGUMENTS)
        region = self.region(p.get('handle') or action.context.window, p.get('rect'))
        return self.locate(description, region, action.timeout_s, timer, str(p.get('label', '')))

    # Probes and actions -------------------------------------------------------------
    def probe(self, what: str, **params: Any) -> Any:
        if what == 'signature':
            region = self.region(params.get('handle'), params.get('rect'))
            small = self.capture(region).convert('L').resize((64, 64), Image.Resampling.BILINEAR)
            return hashlib.sha256(small.tobytes()).hexdigest()[:16]
        if what == 'located':
            region = self.region(params.get('handle'), params.get('rect'))
            try:
                self.locate(str(params['target']), region, float(params.get('timeout_s', 60)))
            except ControlError as error:
                if error.category is ErrorCategory.TARGET_NOT_FOUND:
                    return False
                raise
            return True
        raise ControlError(f'Unknown vision probe {what!r}.', ErrorCategory.UNSUPPORTED)

    def act(self, action: Action) -> ActionResult:
        timer = StageTimer()
        self._cancelled.clear()
        with self._lock:
            try:
                result = self._dispatch(action, timer)
            except ControlError as error:
                return ActionResult.failure(action, error, timings_ms=timer.result())
            except Exception as error:
                return ActionResult(action.action_id, False, Route.VISION, text=f'{type(error).__name__}: {error}'[:300],
                                    executed=True, error_category=ErrorCategory.UNCERTAIN, timings_ms=timer.result())
        verified, evidence = result.verified, result.evidence
        if result.ok and action.expectation is not None:
            from ..verify import default_verifier
            with timer.stage('verify'):
                verified, evidence = default_verifier.wait(action.expectation, self.probe, action.timeout_s, action.cancel)
        ok = result.ok and (verified or action.expectation is None)
        return ActionResult(action.action_id, ok, Route.VISION, text=result.text, image=result.image, state=result.state,
                            executed=result.executed, verified=verified, evidence=evidence or result.evidence,
                            error_category=ErrorCategory.NONE if ok else ErrorCategory.VERIFICATION_FAILED,
                            timings_ms=timer.result())

    def _done(self, action: Action, text: str, executed: bool = True, verified: bool = False, evidence: str = '',
              image: Optional[bytes] = None, **state: Any) -> ActionResult:
        return ActionResult(action.action_id, True, Route.VISION, text=text, image=image, executed=executed,
                            verified=verified, evidence=evidence, state=state)

    def _dispatch(self, action: Action, timer: StageTimer) -> ActionResult:
        name, p = action.name, action.params
        action.cancel.raise_if_cancelled()
        if name == 'screenshot':
            with timer.stage('capture'):
                obs = self.observe(handle=p.get('handle') or action.context.window, rect=p.get('rect'))
            return self._done(action, obs.text, executed=False, verified=True, image=obs.screenshot, scope=obs.scope)
        if name == 'locate':
            found = self._resolve(action, timer)
            return self._done(action, f'Found at ({found.point.x:.0f}, {found.point.y:.0f})', executed=False,
                              verified=True, evidence=found.evidence, point=(round(found.point.x), round(found.point.y)),
                              box=(found.box.left, found.box.top, found.box.right, found.box.bottom))
        if name in ('click', 'double_click', 'right_click', 'type', 'scroll'):
            found = self._resolve(action, timer)
            x, y = round(found.point.x), round(found.point.y)
            app = self._admit(x, y)
            with timer.stage('verify'):
                self._unchanged(found.shot, found.box)
            with timer.stage('input'):
                if name == 'scroll':
                    notches = int(p.get('notches', -3))
                    self.input.wheel(x, y, notches, action.cancel)
                    return self._done(action, f'Scrolled {notches} at ({x}, {y}) in {app}', evidence=found.evidence)
                button = 'right' if name == 'right_click' else 'left'
                method = self.input.click(x, y, button, 2 if name == 'double_click' else 1, action.cancel)
                if name == 'type':
                    self.input.enter(str(p['text']), action.cancel)
            label = str(p.get('target', 'point'))[:60]
            return self._done(action, f'{name.replace("_", " ")} "{label}" at ({x}, {y}) in {app} ({method})',
                              evidence=found.evidence, point=(x, y))
        if name == 'key':
            with timer.stage('input'):
                self.input.keys(str(p['text']), int(p.get('repeat', 1)), action.cancel)
            return self._done(action, f'Pressed {p["text"]}')
        raise ControlError(f'Unsupported vision action {name!r}.', ErrorCategory.UNSUPPORTED)


DEFAULT_CHAIN = ('qwen3-vl:2b', 'qwen3-vl:4b')  # ADR 0004: 2B every time, 4B only after a 2B refusal.


def default_grounders(url: str = 'http://127.0.0.1:11434') -> Tuple[Grounder, Tuple[Grounder, ...]]:
    """The measured default: (primary, fallbacks) for VisionExecutor."""
    chain = [OllamaGrounder(model, url) for model in DEFAULT_CHAIN]
    return chain[0], tuple(chain[1:])


def _release(grounder: Grounder) -> None:
    release = getattr(grounder, 'release', None)
    if callable(release):
        release()


def _window_at(x: int, y: int) -> Tuple[int, str, bool]:
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    handle = user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(x, y)), GA_ROOT)
    if not handle:
        raise ControlError(f'No window at ({x}, {y}).', ErrorCategory.TARGET_NOT_FOUND)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    executable, elevated = _process_info(pid.value)
    return int(handle), executable, elevated


def tool_members() -> Sequence[str]:
    return ('screenshot', 'locate', 'click', 'double_click', 'right_click', 'type', 'scroll', 'key')
