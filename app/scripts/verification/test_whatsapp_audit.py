"""Independent post-freeze boundary checks; reported separately from the full suite."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from jarvis import whatsapp as wa
from jarvis.task_state import TaskState
from tests.test_whatsapp import CHAT


def test_JRV_24_005_disconnect_after_enter(tmp_path):
    state = TaskState(tmp_path)
    state.start('fixture message', 'whatsapp_send')
    actions = SimpleNamespace(base=tmp_path, task_state=state)
    with patch.object(wa, 'type_draft'), patch.object(wa, 'document'), \
         patch.object(wa, 'read', side_effect=[CHAT, OSError('fixture disconnect')]), \
         patch.object(wa, 'compose_value', return_value='approved'), \
         patch.object(wa, 'keys') as keys, patch.object(wa.ctypes, 'windll', create=True) as dll:
        dll.user32.GetForegroundWindow.return_value = 7
        with pytest.raises(OSError):
            wa.send_approved_text(actions, 7, 'Jay Patel', 'approved', lambda: False)
        keys.assert_called_once_with((0x0D, 0), (0x0D, 1))
        with pytest.raises(wa.WhatsAppError, match='uncertain'):
            wa.send_approved_text(actions, 7, 'Jay Patel', 'approved', lambda: False)
        assert keys.call_count == 1
    restored = TaskState(tmp_path)
    assert restored.data['current']['status'] == 'interrupted'
    assert restored.data['current']['uncertain_external_writes'][0]['action'] == 'whatsapp_send'


def test_pending_bubble_is_not_verified_sent():
    outgoing = dict(sender='You', text='approved', outgoing=True, time='1:00 pm', status='Pending')
    with patch.object(wa, 'document'), patch.object(wa, 'read', return_value=CHAT), \
         patch.object(wa, 'messages', side_effect=[[], [outgoing]]), \
         patch.object(wa, 'compose_value', side_effect=['approved', '']), \
         patch.object(wa.time, 'monotonic', side_effect=[0, 1, 7]), \
         patch.object(wa, 'keys') as keys, patch.object(wa.ctypes, 'windll', create=True) as dll:
        dll.user32.GetForegroundWindow.return_value = 7
        with pytest.raises(wa.WhatsAppError, match='could not be confirmed'):
            wa.press_send(7, 'Jay Patel', 'approved', sleep=lambda _: None)
        keys.assert_called_once()


def test_JRV_24_022_long_title_still_incomplete():
    # Body Unicode/500 chars has proof; the catalog also requires a long title/path journey.
    pytest.skip('BLOCKED: Unicode message preview passed, but 500-character contact/title/path admission journey lacks executed proof')
