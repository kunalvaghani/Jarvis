"""Route 3 integration tests against real Notepad, Calculator and Explorer.

They take focus and type on the real desktop, so they run only with JARVIS_DESKTOP_TESTS=1.
All files live in the approved test folder (ADR 0002). Tests skip rather than touch an app the
user already has open: Windows 11 Notepad opens new files as tabs in an existing window.
"""
import os
from pathlib import Path
import shutil
import sys
import time

import pytest

from jarvis.control.input import Input, parse_chord
from jarvis.control.locks import LockManager
from jarvis.control.policy import Policy
from jarvis.control.types import Action, ControlError, ErrorCategory, Expectation, Route

TEST_ROOT = Path(r'D:\Phython Project\TestCodes\jarvis-control-tests')
pytestmark = pytest.mark.skipif(sys.platform != 'win32' or os.environ.get('JARVIS_DESKTOP_TESTS') != '1',
                                reason='real-desktop test: set JARVIS_DESKTOP_TESTS=1')


@pytest.fixture(scope='module')
def uia():
    from jarvis.control.routes.uia import UIAExecutor
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    policy = Policy(allowed_roots=(TEST_ROOT,), allowed_apps=frozenset(
        {'notepad.exe', 'calculatorapp.exe', 'applicationframehost.exe', 'explorer.exe'}))
    executor = UIAExecutor(policy, Input(LockManager(), 'uia-tests', use_pointer=False))
    yield executor
    executor.close()


@pytest.fixture
def workdir():
    path = TEST_ROOT / f'uia-{int(time.time() * 1000)}'
    path.mkdir(parents=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)  # Only the test's own subfolder inside the approved root.


def ctypes_foreground():
    import ctypes
    return ctypes.WinDLL('user32').GetForegroundWindow()


def running(executor, stem):
    return [w for w in executor.windows() if Path(w.executable).stem.lower() == stem]


def act(executor, name, target=None, expectation=None, timeout=8.0, **params):
    return executor.act(Action(name, name, Route.UIA, params=params, target=target, expectation=expectation,
                               timeout_s=timeout))


def find(observation, kind, contains='', aid=''):
    for line, ref in zip(observation.text.splitlines(), observation.refs):
        stripped = line.strip()
        if stripped.startswith(kind) and contains.lower() in stripped.lower() and (not aid or f'aid={aid}' in stripped):
            return ref
    raise AssertionError(f'{kind} {contains or aid} not found in:\n{observation.text[:3000]}')


def test_environment_checks(uia):
    from jarvis.control.routes.uia import secure_desktop_active
    assert secure_desktop_active() is False
    assert uia.health_check().ok
    listed = act(uia, 'list_windows')
    assert listed.ok and listed.text
    with pytest.raises(ControlError):
        parse_chord('ctrl+nonsense')
    blocked = act(uia, 'launch', app='regedit')
    assert blocked.error_category is ErrorCategory.POLICY_DENIED
    outside = act(uia, 'launch', app='notepad', path=r'C:\Windows\win.ini')
    assert outside.error_category is ErrorCategory.POLICY_DENIED


def test_notepad_type_save_and_read_back(uia, workdir):
    if running(uia, 'notepad'):
        pytest.skip('Notepad is already open; Windows 11 would open the test file as a tab in the user window.')
    note = workdir / 'hello.txt'
    note.write_text('', encoding='utf-8')
    opened = act(uia, 'launch', app='notepad', path=str(note), timeout=15)
    assert opened.ok, opened.text
    handle = opened.state['handle']
    try:
        obs = uia.read_window(uia.window(handle=handle))
        editor = find(obs, 'Document') if 'Document' in obs.text else find(obs, 'Edit')
        typed = act(uia, 'set_value', target=editor, value='hello from Jarvis', expect_title=note.name)
        assert typed.ok and typed.verified, typed.text
        assert uia.probe('value', scope=obs.scope, ref=editor.id).rstrip('\r\n') == 'hello from Jarvis'
        saved = act(uia, 'key', handle=handle, text='ctrl+s', expect_title=note.name,
                    expectation=Expectation('file_contains', {'path': str(note), 'text': 'hello from Jarvis'}))
        assert saved.ok and saved.verified, saved.text  # independent check: the file on disk
    finally:
        act(uia, 'close_window', handle=handle)
        time.sleep(.5)
    stale = act(uia, 'set_value', target=editor, value='x')
    assert stale.error_category in (ErrorCategory.STALE_REF, ErrorCategory.UNCERTAIN) and not note.read_text().endswith('x')


def test_calculator_by_automation_id(uia):
    if running(uia, 'calculatorapp'):
        pytest.skip('Calculator is already open; the test would drive the user window.')
    opened = act(uia, 'launch', app='calculator', timeout=15)
    assert opened.ok, opened.text
    handle = opened.state['handle']
    try:
        window = uia.window(handle=handle)
        deadline = time.time() + 10
        obs = uia.read_window(window)
        while 'num2Button' not in obs.text and time.time() < deadline:  # UWP content loads after the frame
            time.sleep(.3)
            obs = uia.read_window(uia.window(handle=handle))
        for aid in ('clearButton', 'num2Button', 'plusButton', 'num3Button', 'equalButton'):
            result = act(uia, 'click', target=find(obs, 'Button', aid=aid))
            assert result.ok and 'Invoke' in result.evidence, (aid, result.text)
        display = find(uia.read_window(uia.window(handle=handle), 'all'), 'Text', aid='CalculatorResults')
        scope = f'win-{handle}'
        assert uia.probe('name', scope=scope, ref=display.id).replace('\u202f', ' ').endswith(' 5')
        result = lambda: uia.probe('name', scope=scope, ref=display.id).replace('\u202f', ' ')  # noqa: E731
        guarded = act(uia, 'key', handle=handle, text='9', expect_title='some-other-document.txt')
        typed = act(uia, 'key', handle=handle, text='escape 7', expect_title='Calculator')
        blocker = uia.protected_foreground()
        if blocker is not None and ctypes_foreground() != handle:
            # Windows drops injected keys while a protected window is in front: reported, never silent.
            for refused in (guarded, typed):
                assert refused.error_category is ErrorCategory.ELEVATED_TARGET and not refused.executed
                assert blocker in refused.text
            assert result().endswith(' 5')
        else:
            # Keyboard input is refused when the window in front does not show the expected document.
            assert guarded.error_category is ErrorCategory.FOCUS_LOST and not guarded.executed
            assert typed.ok, typed.text
            assert result().endswith(' 7')
    finally:
        act(uia, 'close_window', handle=handle)


def test_explorer_opens_the_approved_folder_only(uia, workdir):
    (workdir / 'reports').mkdir()
    opened = act(uia, 'launch', app='explorer', path=str(workdir), timeout=15)
    assert opened.ok, opened.text
    handle = opened.state['handle']
    try:
        obs = uia.read_window(uia.window(handle=handle), 'all')
        assert 'reports' in obs.text
        assert workdir.name in uia.probe('window_title', handle=handle)
    finally:
        act(uia, 'close_window', handle=handle)
