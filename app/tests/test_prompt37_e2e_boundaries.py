"""Synthetic integration checks; no native input hook, account send or microphone."""
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jarvis.demonstration import DemonstrationSession, promote


def recording(tmp_path):
    hook = Mock()
    session = DemonstrationSession(tmp_path, lambda *a: None, hook_factory=lambda events: hook)
    session.state['status'] = 'recording'
    return session, hook


def test_pump_exception_stops_hook_and_persists_failure(tmp_path):
    session, hook = recording(tmp_path)
    session.start_hook()
    session.events.put((1, 2, 513, 0, 0))
    session.process = Mock(side_effect=RuntimeError('synthetic observation failure'))
    with pytest.raises(RuntimeError):
        session.pump()
    hook.stop.assert_called_once()
    assert session.hook is None
    assert json.loads(session.path.read_text())['status'] == 'failed'


def test_hook_start_failure_cleans_owned_hook(tmp_path):
    session, hook = recording(tmp_path)
    hook.start.side_effect = OSError('synthetic start failure')
    with pytest.raises(OSError):
        session.start_hook()
    hook.stop.assert_called_once()
    assert session.state['status'] == 'failed'
    assert session.hook is None


def test_second_start_cannot_replace_active_hook(tmp_path):
    session, hook = recording(tmp_path)
    session.start_hook()
    with pytest.raises(ValueError):
        session.start_hook()
    hook.start.assert_called_once()
    session.stop()


def test_cleanup_failure_is_persisted_and_can_be_retried(tmp_path):
    session, hook = recording(tmp_path)
    session.start_hook()
    hook.stop.side_effect = OSError('owned hook stop failed')
    with pytest.raises(OSError):
        session.stop('cancelled')
    assert session.hook is hook
    assert json.loads(session.path.read_text())['status'] == 'failed'
    hook.stop.side_effect = None
    session.stop('cancelled')
    assert session.hook is None


def test_actions_demo_exception_cleans_session_and_propagates(tmp_path, monkeypatch):
    from jarvis.actions import Actions
    session, hook = recording(tmp_path)
    session.request = Mock()
    session.pump = Mock(side_effect=OSError('synthetic observer failed'))
    monkeypatch.setattr('jarvis.demonstration.DemonstrationSession', lambda *a: session)
    actions = Actions({'files_root': 'files', 'apps': {}, 'demonstration': {'enabled': True}}, tmp_path, lambda *a: None)
    try:
        with pytest.raises(OSError):
            actions.request_demonstration('fixture', 42)
        hook.stop.assert_called_once()
        assert session.state['status'] == 'failed'
        assert session.hook is None
        actions.config['demonstration']['enabled'] = False
        assert actions.request_demonstration('fixture', 42) is None
        session.request.assert_called_once()
    finally:
        actions.close()


def test_cancel_halts_partial_recording_and_blocks_promotion(tmp_path):
    session, hook = recording(tmp_path)
    session.state['steps'] = [{'partial': True}]
    session.start_hook()
    session.pump(cancelled=lambda: True)
    hook.stop.assert_called_once()
    assert session.hook is None
    assert json.loads(session.path.read_text())['status'] == 'cancelled'
    with pytest.raises(ValueError, match='cancel|complete|eligible'):
        promote(None, session, {'verified': True}, 'synthetic-action')


def test_pump_cannot_resurrect_cancelled_partial_session(tmp_path):
    session, _ = recording(tmp_path)
    session.state.update(status='cancelled', steps=[{'partial': True}])
    with pytest.raises(ValueError):
        session.pump(timeout=0)
    assert session.state['status'] == 'cancelled'


def test_callback_stop_is_not_overwritten_as_complete(tmp_path):
    session, hook = recording(tmp_path)
    session.start_hook()
    session.events.put((1, 2, 513, 0, 0))
    session.process = lambda *args: session.state['steps'].append({'partial': True})
    def until(steps):
        session.stop('cancelled')
        return True
    session.pump(until=until)
    assert session.state['status'] == 'cancelled'
    hook.stop.assert_called_once()


@pytest.mark.parametrize('claim', ['false', 'true', 1, {}, []])
def test_promotion_requires_literal_verified_boolean(tmp_path, claim):
    session, _ = recording(tmp_path)
    session.skill_body = Mock(side_effect=AssertionError('must reject before skill creation'))
    with pytest.raises(ValueError, match='verified'):
        promote(None, session, {'verified': claim}, 'synthetic-action')


@pytest.mark.parametrize('change', ['cancel', 'owner'])
def test_request_revalidates_after_consent_before_observing(tmp_path, monkeypatch, change):
    owner = [100]
    cancelled = [False]
    desktop = Mock(side_effect=AssertionError('no UI observation after invalid consent'))
    monkeypatch.setitem(sys.modules, 'win32gui', SimpleNamespace(IsWindow=lambda h: True,
        GetWindowText=lambda h: 'Owned fixture'))
    monkeypatch.setitem(sys.modules, 'win32process', SimpleNamespace(GetWindowThreadProcessId=lambda h: (1, owner[0])))
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(Process=lambda pid: SimpleNamespace(name=lambda: 'fixture.exe')))
    monkeypatch.setitem(sys.modules, 'pywinauto', SimpleNamespace(Desktop=desktop))
    def approve(*args):
        if change == 'cancel': cancelled[0] = True
        else: owner[0] = 101
    session = DemonstrationSession(tmp_path, approve)
    with pytest.raises(ValueError):
        session.request('toggle fixture', 42, lambda: cancelled[0])
    desktop.assert_not_called()
    assert session.state['status'] != 'recording'


def test_uncertain_send_truth_reaches_worker_speech_and_restart(tmp_path):
    from jarvis.actions import Actions
    from jarvis.commands import Command
    from jarvis.task_state import TaskState
    events, sends, finishes = [], [], []
    actions = Actions({'files_root': 'files', 'apps': {}}, tmp_path, lambda *args: events.append(args))
    actions.task_state.on_finish = finishes.append
    def synthetic_send(goal, cancelled):
        sends.append('mock delivery attempted')
        actions.task_state.checkpoint('uncertain_external_write', action='send', target='owned-mock')
        return 'Finished. Message sent.'
    actions.brain.run = synthetic_send
    try:
        actions.start()
        actions.submit(Command('task', 'send a synthetic fixture message'))
        actions.queue.join()
        saved = actions.task_state.snapshot()
        assert saved['status'] == 'paused'
        assert ('spoken_reply', saved['result']) in events
        assert ('spoken_reply', 'Finished. Message sent.') not in events
        assert [row['status'] for row in finishes] == ['paused']
        restored = TaskState(tmp_path)
        assert restored.resume_blocker(restored.snapshot())
        assert len(sends) == 1
    finally:
        actions.close()
