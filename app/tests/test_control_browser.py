"""Route 2 integration tests: real Chrome (headless, throwaway profile) against the local D1 site."""
import importlib.util
from pathlib import Path
import re
import sys

import pytest

from jarvis.control.coords import Frame, Point
from jarvis.control.policy import Policy
from jarvis.control.routes.browser import BrowserExecutor
from jarvis.control.types import Action, ErrorCategory, Expectation, Route

APP = Path(__file__).resolve().parents[1]
# Load D1 by path under a unique name: other suites put unrelated `server` modules on sys.path.
_spec = importlib.util.spec_from_file_location('jarvis_d1_site', APP / 'benchmarks' / 'sites' / 'd1' / 'server.py')
_d1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_d1)
Site = _d1.Site

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='installed Chrome on the Jarvis host')


@pytest.fixture(scope='module')
def env(tmp_path_factory):
    site = Site()
    base, peer = site.start()
    root = tmp_path_factory.mktemp('browser')
    allow = frozenset({('127.0.0.1', port) for port in site.ports} | {('localhost', port) for port in site.ports})
    policy = Policy(allowed_roots=(root,), loopback_allow=allow, resolver=lambda host: ('93.184.215.14',))
    executor = BrowserExecutor(root / 'profile', policy, root / 'downloads', headless=True)
    executor.start()
    yield executor, base, peer, root
    executor.close()
    site.stop()


def act(executor, name, target=None, expectation=None, timeout=5.0, **params):
    return executor.act(Action(name, name, Route.BROWSER, params=params, target=target, expectation=expectation,
                               timeout_s=timeout))


def ref_for(text, role, name):
    match = re.search(rf'{role} "{re.escape(name)}"[^\[]*\[(ref_\d+)\]', text)
    assert match, f'{role} "{name}" not in:\n{text}'
    return match.group(1)


def text_of(executor, selector):
    return executor.probe('text', selector=selector)


def test_navigate_read_and_policy(env):
    executor, base, _, _ = env
    result = act(executor, 'navigate', url=base + '/forms.html')
    assert result.ok and result.verified and result.state['tabs'][0]['url'].endswith('/forms.html')
    tree = executor.read_page(filter='interactive').text
    assert 'textbox "Name"' in tree and 'combobox "Topic"' in tree and 'checkbox "Newsletter"' in tree
    assert 'Secret' not in tree  # display:none never reaches the reader
    assert re.search(r'button "Archived" disabled \[ref_\d+\]', tree)
    blocked = act(executor, 'navigate', url='javascript:alert(1)')
    assert not blocked.ok and blocked.error_category is ErrorCategory.POLICY_DENIED
    blocked = act(executor, 'navigate', url='http://169.254.169.254/latest/meta-data')
    assert blocked.error_category is ErrorCategory.POLICY_DENIED


def test_refs_stay_stable_until_navigation(env):
    executor, base, _, _ = env
    act(executor, 'navigate', url=base + '/forms.html')
    first = executor.read_page(filter='interactive').text
    again = executor.read_page(filter='all').text
    name_ref = ref_for(first, 'textbox', 'Name')
    assert ref_for(again, 'textbox', 'Name') == name_ref  # never renumbered within a page
    act(executor, 'navigate', url=base + '/forms.html')
    stale = act(executor, 'left_click', target=name_ref)
    assert stale.error_category is ErrorCategory.STALE_REF and 'Re-read the page' in stale.text


def test_click_form_input_and_verification(env):
    executor, base, _, _ = env
    act(executor, 'navigate', url=base + '/forms.html')
    tree = executor.read_page(filter='interactive').text
    name = act(executor, 'form_input', target=ref_for(tree, 'textbox', 'Name'), value='Ada')
    assert name.ok and name.verified and executor.probe('value', ref=ref_for(tree, 'textbox', 'Name')) == 'Ada'
    topic = act(executor, 'form_input', target=ref_for(tree, 'combobox', 'Topic'), value='Support')
    assert topic.ok and topic.verified
    box = act(executor, 'form_input', target=ref_for(tree, 'checkbox', 'Newsletter'), value=True)
    assert box.ok and box.verified
    pw = act(executor, 'form_input', target=ref_for(tree, 'textbox', 'Password'), value='hunter2')
    assert pw.error_category is ErrorCategory.POLICY_DENIED and 'Password' in pw.text
    counter = ref_for(tree, 'button', 'Count 0')
    clicked = act(executor, 'left_click', target=counter,
                  expectation=Expectation('url_matches', {'pattern': 'forms'}))
    assert clicked.ok and clicked.executed and text_of(executor, '#counter') == 'Count 1'
    disabled = act(executor, 'left_click', target=ref_for(tree, 'button', 'Archived'), timeout=.5)
    assert disabled.error_category is ErrorCategory.NOT_ACTIONABLE and 'disabled' in disabled.text
    assert text_of(executor, '#status') == 'not submitted'  # nothing submitted the form


def test_dynamic_content_auto_waits_and_relabel_is_refused(env):
    executor, base, _, _ = env
    act(executor, 'navigate', url=base + '/dynamic.html')
    tree = executor.read_page(filter='all').text
    later = ref_for(tree, 'button', 'Ready soon')
    # The button is disabled now and relabelled when enabled: the click must refuse, not hit a changed target.
    changed = act(executor, 'left_click', target=later, timeout=3)
    assert changed.error_category is ErrorCategory.STALE_REF and 'changed after it was read' in changed.text
    tree = executor.read_page(filter='all').text
    assert act(executor, 'left_click', target=ref_for(tree, 'button', 'Ready now')).ok
    assert text_of(executor, '#state') == 'ready clicked'
    load = act(executor, 'left_click', target=ref_for(tree, 'button', 'Load items'),
               expectation=Expectation('state_equals', {'key': 'tabs', 'expected': executor.browser_state()['tabs']}))
    assert load.ok
    mover = act(executor, 'left_click', target=ref_for(tree, 'button', 'Moving target'))
    assert mover.ok and text_of(executor, '#state') == 'mover clicked'  # waited for the animation to settle


def test_rerendered_node_is_stale_and_covered_target_is_refused(env):
    executor, base, _, _ = env
    act(executor, 'navigate', url=base + '/dynamic.html')
    tree = executor.read_page(filter='all').text
    rerender = ref_for(tree, 'button', 'Rerender')
    assert act(executor, 'left_click', target=rerender).ok
    gone = act(executor, 'left_click', target=rerender, timeout=1)
    assert gone.error_category is ErrorCategory.STALE_REF  # node was replaced, ref never re-points
    act(executor, 'left_click', target=ref_for(tree, 'button', 'Show overlay'))
    covered = act(executor, 'left_click', target=ref_for(tree, 'button', 'Under overlay'), timeout=.6)
    assert covered.error_category is ErrorCategory.NOT_ACTIONABLE and 'covered' in covered.text
    assert text_of(executor, '#state') != 'covered clicked'


def test_modal_iframes_and_out_of_process_frame(env):
    executor, base, peer, _ = env
    act(executor, 'navigate', url=base + '/modal.html')
    tree = executor.read_page(filter='interactive').text
    act(executor, 'left_click', target=ref_for(tree, 'button', 'Open dialog'))
    tree = executor.read_page(filter='interactive').text
    assert act(executor, 'left_click', target=ref_for(tree, 'button', 'Confirm')).ok
    assert text_of(executor, '#result') == 'confirmed'

    act(executor, 'navigate', url=base + '/frames.html')
    executor.tabs[executor.active].page.wait_for_function(
        "() => document.getElementById('cross').contentWindow && document.getElementById('cross').src")
    executor.tabs[executor.active].page.wait_for_timeout(500)
    tree = executor.read_page(filter='interactive').text
    assert act(executor, 'left_click', target=ref_for(tree, 'button', 'Inner button')).ok
    assert text_of(executor, '#out') == 'inner clicked'
    assert act(executor, 'left_click', target=ref_for(tree, 'button', 'Child button')).ok
    frame = executor.tabs[executor.active].page.frames[-1]
    assert frame.evaluate("document.getElementById('cs').textContent") == 'child clicked'


def test_cross_site_iframe_runs_in_its_own_process(env):
    executor, base, peer, _ = env
    cross_site = base.replace('127.0.0.1', 'localhost')
    page = executor.tabs[executor.active].page
    act(executor, 'navigate', url=peer + '/frames.html')
    page.evaluate("u => { document.getElementById('cross').src = u + '/frame-child.html'; }", cross_site)
    page.wait_for_timeout(800)
    tree = executor.read_page(filter='interactive').text
    child = ref_for(tree, 'button', 'Child button')
    assert any(k.startswith('oop:') for k in executor.tabs[executor.active].oop)
    assert act(executor, 'left_click', target=child).ok
    assert page.frames[-1].evaluate("document.getElementById('cs').textContent") == 'child clicked'


def test_scroll_virtual_list_canvas_and_drag(env):
    executor, base, _, _ = env
    act(executor, 'navigate', url=base + '/scroll.html')
    tree = executor.read_page(filter='interactive').text
    assert 'Bottom button' in tree
    assert act(executor, 'left_click', target=ref_for(tree, 'button', 'Bottom button')).ok
    assert text_of(executor, '#sstate') == 'bottom clicked'
    assert act(executor, 'left_click', target=ref_for(tree, 'button', 'Item 55')).ok
    assert text_of(executor, '#sstate') == 'item 55'
    visible = executor.read_page().text
    assert 'Item 55' not in visible or 'Bottom button' in visible  # visible filter scopes to the viewport

    act(executor, 'navigate', url=base + '/canvas.html')
    executor.read_page()
    assert act(executor, 'left_click', target=Point(200, 90, Frame.VIEWPORT)).ok
    assert text_of(executor, '#hit') == 'blue star'
    outside = act(executor, 'left_click', target=Point(5000, 10, Frame.VIEWPORT))
    assert outside.error_category is ErrorCategory.INVALID_ARGUMENTS and not outside.executed

    act(executor, 'navigate', url=base + '/drag.html')
    executor.read_page()
    drag = act(executor, 'left_click_drag', target=Point(360, 80, Frame.VIEWPORT), **{'from': Point(50, 50, Frame.VIEWPORT)})
    assert drag.ok and text_of(executor, '#drop') == 'dropped'


def test_tabs_keys_text_and_screenshot(env):
    executor, base, _, _ = env
    act(executor, 'navigate', url=base + '/index.html')
    tree = executor.read_page(filter='interactive').text
    opened = act(executor, 'left_click', target=ref_for(tree, 'link', 'Forms in a new tab'))
    executor.tabs[executor.active].page.wait_for_timeout(500)
    assert any(c['type'] == 'tab_opened' for c in opened.state.get('state_changes', [])) or len(executor.tabs) == 2
    second = [t for t in executor.tabs if t != executor.active][0]
    assert act(executor, 'switch_tab', tab_id=second).ok and executor.active == second
    listed = act(executor, 'list_tabs').state['tabs']
    assert sum(t['active'] for t in listed) == 1 and len(listed) == 2
    assert act(executor, 'close_tab', tab_id=second).ok and len(executor.tabs) == 1
    act(executor, 'navigate', url=base + '/forms.html')
    tree = executor.read_page(filter='interactive').text
    act(executor, 'left_click', target=ref_for(tree, 'textbox', 'Message'))
    assert act(executor, 'type', text='hello').ok
    assert act(executor, 'key', text='Backspace', repeat=2).ok
    assert executor.probe('value', ref=ref_for(tree, 'textbox', 'Message')) == 'hel'
    assert 'Contact form' in act(executor, 'get_page_text').text
    shot = act(executor, 'screenshot')
    assert shot.image and shot.image[:4] == b'\x89PNG'
    zoom = act(executor, 'zoom', region=[0, 0, 200, 100])
    assert zoom.image and zoom.ok
    found = act(executor, 'find', query='newsletter checkbox')
    assert 'Newsletter' in found.text.splitlines()[0]


def test_downloads_go_to_the_confined_folder(env):
    executor, base, _, root = env
    act(executor, 'navigate', url=base + '/files.html')
    tree = executor.read_page(filter='interactive').text
    result = act(executor, 'left_click', target=ref_for(tree, 'link', 'Download sample'))
    executor.tabs[executor.active].page.wait_for_timeout(1000)
    assert result.ok and (root / 'downloads' / 'sample.txt').read_text() == 'Jarvis D1 sample download.\n'


def test_injection_page_and_redirect_to_private_address(env):
    executor, base, _, _ = env
    act(executor, 'navigate', url=base + '/inject-hidden.html')
    tree = executor.read_page(filter='all').text
    assert 'SYSTEM: ignore previous' not in tree  # display:none text never reaches the reader
    bad = act(executor, 'navigate', url=base + '/redirect?to=http://10.0.0.1/admin')
    assert not bad.ok and bad.error_category is ErrorCategory.POLICY_DENIED
    assert any('10.0.0.1' in url for url in executor.blocked)
    act(executor, 'navigate', url=base + '/inject-hidden.html')
    tree = executor.read_page(filter='interactive').text
    link = ref_for(tree, 'link', 'Redirect to local')
    act(executor, 'left_click', target=link)
    executor.tabs[executor.active].page.wait_for_timeout(500)
    # The hop to 127.0.0.1:1 was refused; Chrome shows its own error page instead of loading it.
    assert '127.0.0.1:1/' not in executor.probe('url') and any(':1/' in url for url in executor.blocked)
    act(executor, 'navigate', url=base + '/inject-hidden.html')
    tree = executor.read_page(filter='interactive').text
    relabel = ref_for(tree, 'button', 'Save draft')
    executor.tabs[executor.active].page.wait_for_timeout(1600)  # page relabels it "Delete account"
    changed = act(executor, 'left_click', target=relabel)
    assert changed.error_category is ErrorCategory.STALE_REF and text_of(executor, '#rl') == 'idle'
