"""Condition waits (control.event_waits): end as soon as the state shows, never later than the fixed wait."""
import time

import pytest

from jarvis.control import service as service_module
from jarvis.control import settings as control_settings
from jarvis.control.service import ControlService
from jarvis.control.types import ControlError, ErrorCategory
from jarvis.control.waits import until


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_until_returns_at_once_when_already_done():
    clock = Clock()
    assert until(lambda: True, .5, clock=clock, sleep=clock.sleep) is True
    assert clock.sleeps == []


def test_until_returns_as_soon_as_the_probe_passes():
    clock, calls = Clock(), []

    def probe():
        calls.append(clock.now)
        return clock.now >= .1
    assert until(probe, .5, interval=.05, clock=clock, sleep=clock.sleep) is True
    assert clock.now == pytest.approx(.1)


def test_until_never_waits_longer_than_the_timeout():
    clock = Clock()
    assert until(lambda: False, .3, interval=.05, clock=clock, sleep=clock.sleep) is False
    assert sum(clock.sleeps) == pytest.approx(.3)
    clock = Clock()
    assert until(lambda: False, .12, interval=.05, clock=clock, sleep=clock.sleep) is False
    assert clock.sleeps[-1] == pytest.approx(.02) and sum(clock.sleeps) == pytest.approx(.12)


def test_a_failing_read_counts_as_not_yet():
    clock, reads = Clock(), iter([ControlError('gone', ErrorCategory.TARGET_NOT_FOUND), False, True])

    def probe():
        value = next(reads)
        if isinstance(value, Exception):
            raise value
        return value
    assert until(probe, 1, interval=.05, clock=clock, sleep=clock.sleep) is True
    with pytest.raises(ValueError):  # Anything else is a real error.
        until(lambda: (_ for _ in ()).throw(ValueError('bug')), 1, clock=clock, sleep=clock.sleep)


def test_real_clock_bound():
    started = time.perf_counter()
    assert until(lambda: False, .1) is False
    assert .095 <= time.perf_counter() - started < .5


def services(tmp_path):
    off = ControlService(control_settings.load(tmp_path, {}))
    on = ControlService(control_settings.load(tmp_path, {'control': {'event_waits': True}}))
    return off, on


def test_flag_off_keeps_the_exact_fixed_waits(tmp_path, monkeypatch):
    off, on = services(tmp_path)
    paused = []
    monkeypatch.setattr(service_module, 'pause', paused.append)
    probes = []
    off._wait(.6, lambda: probes.append(1) or True)
    assert paused == [.6] and probes == []  # Off: today's sleep, no probe.
    assert (off._interval(.4, .15), off._interval(.4, .1), off._interval(.3, .05)) == (.4, .4, .3)
    assert (on._interval(.4, .15), on._interval(.4, .1), on._interval(.3, .05)) == (.15, .1, .05)


def test_flag_on_ends_the_wait_when_the_state_shows(tmp_path, monkeypatch):
    _, on = services(tmp_path)
    paused = []
    monkeypatch.setattr(service_module, 'pause', paused.append)
    started = time.perf_counter()
    on._wait(.6, lambda: True)
    assert time.perf_counter() - started < .05 and paused == []
    garbled = ControlService(control_settings.load(tmp_path, {'control': {'event_waits': 'true'}}))
    garbled._wait(.6, lambda: True)
    assert paused == [.6]  # A malformed flag reads as off.


def reads(service, sequence):
    """Make the service's window reads return `sequence` (the last value repeats)."""
    seen = []

    def read(route, handle, filter):
        seen.append(sequence[min(len(seen), len(sequence) - 1)])
        return seen[-1]
    service._read_window = read
    return seen


def test_calculator_is_read_only_after_it_finishes(tmp_path):
    # Live S2, 2026-10-31: a fixed 0.3 s read caught "69104 Minus ( 7" and the planner pressed Equals again.
    _, on = services(tmp_path)
    before = 'Display is 0'
    seen = reads(on, ['Expression is 69104 Minus ( 7', 'Expression is 69104 Minus ( 789=', 'Display is 68,315',
                      'Display is 68,315'])
    on._settle_input(None, 1, '', before)
    assert seen[-1] == 'Display is 68,315' and seen[-2] == 'Display is 68,315'


def test_unchanged_window_costs_about_the_old_fixed_wait(tmp_path):
    _, on = services(tmp_path)
    reads(on, ['same'])
    started = time.perf_counter()
    on._settle_input(None, 1, '', 'same')
    assert .29 <= time.perf_counter() - started < .7


def test_typed_text_shown_in_the_field_ends_the_wait_at_once(tmp_path):
    _, on = services(tmp_path)
    seen = reads(on, ['Document "Untitled" [u1]\n  Edit "Text editor" [u2] value=\'milk\''])
    started = time.perf_counter()
    on._settle_input(None, 1, 'milk', 'before')
    assert time.perf_counter() - started < .1 and len(seen) == 1


def test_a_window_that_keeps_changing_is_capped_at_two_seconds(tmp_path):
    _, on = services(tmp_path)
    counter = iter(range(10 ** 6))
    on._read_window = lambda route, handle, filter: f'frame {next(counter)}'
    started = time.perf_counter()
    on._settle_input(None, 1, '', 'before')
    assert 1.9 <= time.perf_counter() - started < 2.6


def test_settle_with_the_flag_off_is_the_old_fixed_pause(tmp_path, monkeypatch):
    off, _ = services(tmp_path)
    paused = []
    monkeypatch.setattr(service_module, 'pause', paused.append)
    off._read_window = lambda *a: pytest.fail('no probe reads with the flag off')
    off._settle_input(None, 1, 'milk', 'before')
    assert paused == [.3]
