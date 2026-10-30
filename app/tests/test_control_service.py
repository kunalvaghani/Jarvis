"""The control service as the planner tools use it: real headless Chrome against the local D1 site."""
import importlib.util
import json
from pathlib import Path
import re
import sys

import pytest

from jarvis.control.policy import Policy
from jarvis.control.progress import ProgressEvent
from jarvis.control.service import ControlService, labels_for_tests
from jarvis.control.settings import ControlSettings
from jarvis.control.types import Route

APP = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('jarvis_d1_site', APP / 'benchmarks' / 'sites' / 'd1' / 'server.py')
_d1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_d1)

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='installed Chrome on the Jarvis host')


@pytest.fixture
def env(tmp_path):
    site = _d1.Site()
    base, _ = site.start()
    allow = frozenset({('127.0.0.1', port) for port in site.ports})
    policy = Policy(allowed_roots=(tmp_path,), loopback_allow=allow, resolver=lambda host: ('93.184.215.14',))
    settings = ControlSettings(allowed_roots=(tmp_path,), test_profile=tmp_path / 'profile',
                               downloads=tmp_path / 'downloads', headless=True)
    events, asked = [], []

    def approve(action):
        asked.append(action.goal)
        return False  # The user says no in these tests.
    service = ControlService(settings, approve, events.append, policy)
    yield service, base, events, asked
    service.close()
    site.stop()


def head(text):
    return json.loads(text.splitlines()[0])


def ref(text, kind, name):
    for k, n, r in labels_for_tests(text):
        if k == kind and n == name:
            return r
    raise AssertionError(f'{kind} "{name}" not in:\n{text}')


def test_open_fill_and_click_with_fresh_refs_and_island_progress(env):
    service, base, events, asked = env
    page = service.web_open(f'{base}/forms.html', lambda: False)
    assert head(page)['ok'] and 'textbox "Name"' in page
    filled = service.web_act('fill', {'ref': ref(page, 'textbox', 'Name'), 'text': 'Ada Lovelace'}, lambda: False)
    assert head(filled)['ok'] and head(filled)['verified'] and head(filled)['target'] == 'textbox "Name"'
    counter = ref(filled, 'button', 'Count 0')
    clicked = service.web_act('click', {'ref': counter}, lambda: False)
    assert head(clicked)['ok'] and 'button "Count 1"' in clicked  # The fresh read shows the page's new state.
    routes = {e.route for e in events}
    phases = [e.phase for e in events]
    assert routes == {Route.BROWSER} and 'acting' in phases and 'done' in phases and not asked
    assert all(isinstance(e, ProgressEvent) and e.at > 0 for e in events)


def test_send_like_targets_ask_first_and_a_no_sends_nothing(env):
    service, base, events, asked = env
    page = service.web_open(f'{base}/forms.html', lambda: False)
    result = head(service.web_act('click', {'ref': ref(page, 'button', 'Send message')}, lambda: False))
    assert result['error'] == 'approval_denied' and not result['executed']
    assert asked and 'Send message' in asked[0] and 'waiting_approval' in [e.phase for e in events]
    status = service.web_read(lambda: False, 'all')
    assert 'not submitted' in status  # The form was never submitted.


def test_stale_refs_and_bad_arguments_come_back_readable(env):
    service, base, events, asked = env
    page = service.web_open(f'{base}/forms.html', lambda: False)
    old = ref(page, 'textbox', 'Name')
    service.web_open(f'{base}/index.html', lambda: False)
    stale = head(service.web_act('fill', {'ref': old, 'text': 'x'}, lambda: False))
    assert stale['error'] == 'stale_ref' and not stale['executed']
    with pytest.raises(Exception) as caught:
        service.web_act('teleport', {}, lambda: False)
    assert 'web_act value must be one of' in str(caught.value)


def test_blocked_sites_are_refused(env):
    service, base, events, asked = env
    result = head(service.web_open('http://169.254.169.254/latest/meta-data', lambda: False))
    assert not result['ok'] and result['error'] == 'policy_denied'


def test_labels_parser_reads_both_route_formats():
    text = 'button "Send message" [ref_5]\n  Button "Seven" [u12] aid=num7Button\ntextbox "Name" [ref_2]'
    assert labels_for_tests(text) == [('button', 'Send message', 'ref_5'), ('Button', 'Seven', 'u12'),
                                      ('textbox', 'Name', 'ref_2')]


def test_labels_survive_element_state_so_risk_checks_see_submit():
    text = "button \"Submit\" focused [ref_9]\ntextbox \"Email\" required value='a@b.c' [ref_3]\n  CheckBox \"Agree\" checked [u4]"
    assert labels_for_tests(text) == [('button', 'Submit', 'ref_9'), ('textbox', 'Email', 'ref_3'), ('CheckBox', 'Agree', 'u4')]


def test_a_label_used_as_a_ref_resolves_only_when_unique():
    from jarvis.control.service import resolve_ref
    from jarvis.control.types import ControlError
    read = 'Window "Calculator" [u1]\n  Button "Clear" [u17]\n  link "edit" [ref_3]\n  link "edit" [ref_9]'
    assert resolve_ref('Clear', read) == 'u17' and resolve_ref('u17', read) == 'u17'
    assert resolve_ref('Missing', read) == 'Missing'  # The route then reports it as not found.
    with pytest.raises(ControlError, match='matches 2 elements'):
        resolve_ref('edit', read)


def test_changes_show_what_an_action_did():
    from jarvis.control.service import changes
    before = 'Window "Calculator" [u1]\n  Text "Display is 0" [u7]\n  Button "Clear" [u17]'
    after = 'Window "Calculator" [u1]\n  Text "Display is 68,315" [u7]\n  Button "Clear" [u17]'
    assert changes(before, after) == ['Text "Display is 68,315"']
    assert changes(before, before) == []


def test_an_unclear_operation_is_inferred_from_the_arguments():
    from jarvis.control.service import infer_op, APP_OPS, WEB_OPS
    assert infer_op('shopping.txt', {'ref': 'u50', 'text': 'milk'}, APP_OPS, 'set_value') == 'set_value'
    assert infer_op('Calculator', {'text': '1+1='}, APP_OPS, 'set_value') == 'type'
    assert infer_op('the button', {'ref': 'ref_4'}, WEB_OPS, 'fill') == 'click'
    assert infer_op('Click', {}, APP_OPS, 'set_value') == 'click'
    assert infer_op('teleport', {}, APP_OPS, 'set_value') == 'teleport'  # Still refused downstream.


def test_key_chords_in_value_become_key_and_empty_input_is_refused(tmp_path, monkeypatch):
    from jarvis.control.service import CHORD
    from jarvis.control.types import ControlError
    assert CHORD.fullmatch('ctrl+s') and CHORD.fullmatch('Ctrl+Shift+S') and CHORD.fullmatch('enter')
    assert not CHORD.fullmatch('shopping.txt') and not CHORD.fullmatch('type')
    service = ControlService(ControlSettings(allowed_roots=(tmp_path,)), lambda action: False, lambda event: None,
                             Policy(allowed_roots=(tmp_path,)))
    sent = []
    monkeypatch.setattr(service, '_run', lambda route, action: sent.append((action.name, dict(action.params))) or
                        __import__('jarvis.control.types', fromlist=['ActionResult']).ActionResult.failure(
                            action, ControlError('stop here', __import__('jarvis.control.types', fromlist=['ErrorCategory']).ErrorCategory.CANCELLED)))
    monkeypatch.setattr(service, 'uia', lambda: None)
    service.app_scope = 'win-77'
    service.app_act('ctrl+s', {}, lambda: False)
    assert sent == [('key', {'handle': 77, 'text': 'ctrl+s'})]
    with pytest.raises(ControlError, match='needs text'):
        service.app_act('type', {'ref': 'u50'}, lambda: False)


def test_save_as_needs_a_full_new_path_and_never_overwrites(tmp_path):
    from jarvis.control.types import ControlError
    service = ControlService(ControlSettings(allowed_roots=(tmp_path,)), lambda action: False, lambda event: None,
                             Policy(allowed_roots=(tmp_path,)))
    service.app_scope = 'win-77'
    (tmp_path / 'shopping.txt').write_text('old')
    for path, message in (('shopping.txt', 'full file path'), (str(tmp_path / 'missing' / 'a.txt'), 'does not exist'),
                          (str(tmp_path / 'shopping.txt'), 'already exists')):
        with pytest.raises(ControlError, match=message):
            service.app_act('save_as', {'text': path}, lambda: False)
    assert (tmp_path / 'shopping.txt').read_text() == 'old'


NOTEPAD_NOTICE = '''Window "shopping.txt - Notepad" [u1]
  Pane "" [u2]
    Pane "" [u3] focused
      Window "Notepad" [u5]
        Pane "" [u6] aid=ContentScrollViewer
          Text "Notepad" [u7]
          Text "Cannot find the D:\Tests\shopping.txt file." [u8]
        Button "OK" [u9] aid=CloseButton focused
  Pane "" [u11]
    Document "Text editor" [u12]
          TabItem "shopping.txt. Unmodified." [u21] selected
            Button "Close Tab" [u23] aid=CloseButton'''


def test_notepad_missing_file_notice_is_found_and_a_fresh_tab_is_recognised():
    from jarvis.control.service import fresh_notepad_tab, notepad_notice
    assert notepad_notice(NOTEPAD_NOTICE) == 'u9'
    assert notepad_notice(NOTEPAD_NOTICE.replace('Cannot find the', 'Do you want to save')) == ''
    assert not fresh_notepad_tab(NOTEPAD_NOTICE)
    fresh = 'Window "Untitled - Notepad" [u1]\n  Document "Text editor" [u3] focused\n  TabItem "Untitled. Unmodified." [u10] selected'
    assert fresh_notepad_tab(fresh)
    assert not fresh_notepad_tab(fresh.replace('focused', "value='old text' focused"))


def test_typed_text_is_compared_with_what_the_editor_shows():
    from jarvis.control.service import field_text, typed_intact
    shown = field_text("Window \"x\" [u1]\n  Document \"Text editor\" [u3] value='Shopping List" + chr(92) + "r- Milk' focused")
    assert shown == 'Shopping List\n- Milk'
    assert typed_intact('Shopping List\n- Milk', shown)
    assert not typed_intact('milk\neggs', field_text("Document \"Text editor\" [u3] value='- " + chr(92) + "rdddddeggs' focused"))
    assert field_text('Window "x" [u1]\n  Button "OK" [u2]') is None


def test_plain_text_content_is_the_text_for_text_operations_only():
    from jarvis.control.service import parse_args
    from jarvis.control.types import ControlError
    assert parse_args('Shopping List\n- Milk', 'type') == {'text': 'Shopping List\n- Milk'}
    assert parse_args('{"ref": "u3", "text": "x"}', 'type') == {'ref': 'u3', 'text': 'x'}
    with pytest.raises(ControlError, match='JSON object'):
        parse_args('u3', 'click')
