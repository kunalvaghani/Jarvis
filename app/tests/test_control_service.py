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
