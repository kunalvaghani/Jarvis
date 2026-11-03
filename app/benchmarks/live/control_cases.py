"""PC/web control benchmark scenarios (docs/control/ADAPTER_PLAN.md, Phase 1), run through the live suite.

    python benchmarks/live/cases.py control --pc agent_desktop --web agent_browser --repeat 5

Every oracle reads real state through ``READERS`` (disk, registry, clipboard, window rectangles, processes,
Windows media sessions, or a fresh read-only browser session), never the backend's own claim. Tests in
tests/test_control_bench.py run each oracle against a known-good and a known-bad state, so an oracle that
cannot tell them apart fails before any benchmark result is trusted.

Scope rules: files only in the Jarvis test folder; Google work only inside a "Jarvis tests" Drive folder and as
Gmail drafts (never sent); WhatsApp/Discord read-only; settings toggled are restored afterwards.
"""
from __future__ import annotations

from pathlib import Path
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

Readers = Dict[str, Callable[..., Any]]
APP = Path(__file__).resolve().parents[2]


def _file_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding='utf-8-sig', errors='replace')
    except OSError:
        return None


def _processes() -> List[str]:
    import psutil
    names = []
    for p in psutil.process_iter(['name']):
        try:
            names.append(str(p.info['name'] or '').lower())
        except Exception:
            continue
    return names


def _windows() -> List[Tuple[int, str, Tuple[int, int, int, int], bool]]:
    """(handle, title, rect, minimized) of visible top-level windows, in physical pixels: a DPI-unaware reader
    sees scaled rects (800x600 reads as 640x480 at 125%), so this thread reads per-monitor aware."""
    import ctypes
    import win32gui
    try:
        previous = ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        previous = None
    rows: List[Tuple[int, str, Tuple[int, int, int, int], bool]] = []

    def visit(h: int, _: Any) -> bool:
        if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h):
            rows.append((h, win32gui.GetWindowText(h), win32gui.GetWindowRect(h), bool(win32gui.IsIconic(h))))
        return True
    try:
        win32gui.EnumWindows(visit, None)
    finally:
        if previous:  # the oracle runs on Jarvis's thread: leave its DPI awareness as it was
            ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(previous))
    return rows


def _clipboard() -> str:
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        return str(win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT))
    except TypeError:
        return ''
    finally:
        win32clipboard.CloseClipboard()


def _dnd_on() -> Optional[bool]:
    """Do Not Disturb: toasts disabled globally (HKCU Notifications\\Settings NOC_GLOBAL_SETTING_TOASTS_ENABLED=0)."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Notifications\Settings') as key:
            value, _ = winreg.QueryValueEx(key, 'NOC_GLOBAL_SETTING_TOASTS_ENABLED')
            return int(value) == 0
    except OSError:
        return False  # absent = toasts enabled = DND off


def _set_dnd(on: bool) -> None:
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Notifications\Settings') as key:
        winreg.SetValueEx(key, 'NOC_GLOBAL_SETTING_TOASTS_ENABLED', 0, winreg.REG_DWORD, 0 if on else 1)


def _account_url(linked: Any, url: str) -> str:
    """The oracle reads the same Google account Jarvis uses (config google.account)."""
    from jarvis.google_account import configured_account, for_account, slot_from

    def lookup(name: str) -> Optional[str]:
        linked(['open', 'https://mail.google.com/mail/?authuser=' + name], 60)
        return slot_from(str((linked(['get', 'url'], 20).data or {}).get('url', '')))
    return for_account(url, configured_account(), lookup)


def _google_page(url: str) -> str:
    """What the server really shows, read in the user's signed-in Chrome through the Jarvis Browser extension in a
    separate oracle session and tab (open + read only). Gmail fills lists after load: re-read up to ~12 s and keep
    the fullest read. Without the extension: a read-only agent-browser session (signed out: Google checks fail)."""
    from jarvis.control.web.extension_runner import ExtensionRunner
    from jarvis.control.web.agent_browser_backend import AgentBrowserExecutor
    from jarvis.control.policy import Policy
    linked = ExtensionRunner(session='jarvis-oracle')
    if linked.available():
        reader = AgentBrowserExecutor(Policy(), linked)
        try:
            linked(['tab', 'new', 'about:blank'], 30)
            linked(['open', _account_url(linked, url)], 90)
            best = ''
            for _ in range(8):
                time.sleep(1.5)
                text = reader.read_page('all').text
                best = text if len(text) > len(best) else best
            return best
        finally:
            for tab in (linked(['tab', 'list'], 20).data or {}).get('tabs', []):
                if tab.get('active'):  # this session's own tab only
                    linked(['tab', 'close', str(tab['tabId'])], 20)
    from jarvis.control.web.shadow import ReadOnlyBrowserRunner
    from jarvis.control.policy import Policy
    runner = ReadOnlyBrowserRunner(session='jarvis-oracle', profile='Default', headed=False)
    reader = AgentBrowserExecutor(Policy(), runner)
    try:
        runner(['open', url], 90)
        time.sleep(3)
        return reader.read_page('all').text
    finally:
        reader.close()


def _gmail_draft_body(subject: str) -> Optional[str]:
    """The message box text of the Gmail draft with this subject (None: not found). Gmail's Drafts rows and search do
    not show draft bodies (checked live 2026-11-03), so the oracle opens the draft in its own tab and reads the box;
    opening does not change a draft."""
    from urllib.parse import quote
    from jarvis.control.web.extension_runner import ExtensionRunner
    from jarvis.control.web.agent_browser_backend import AgentBrowserExecutor
    from jarvis.control.policy import Policy
    from jarvis.control.types import Action, Route
    linked = ExtensionRunner(session='jarvis-oracle')
    if not linked.available():
        return None
    reader = AgentBrowserExecutor(Policy(), linked)
    try:
        linked(['tab', 'new', 'about:blank'], 30)
        linked(['open', _account_url(linked, 'https://mail.google.com/mail/u/0/#search/'
                                     + quote(f'in:drafts "{subject}"'))], 90)
        row = ''
        for _ in range(10):
            time.sleep(1.5)
            text = reader.read_page('all').text
            found = [ref for label, ref in re.findall(r'^\s*(?:row|gridcell) "([^"]*)"[^\n]*\[(ref_\d+)\]', text, re.M)
                     if subject in label]
            if found:
                row = found[0]
                break
        if not row:
            return None
        reader.act(Action('left_click', 'oracle: open the draft to read it', Route.BROWSER, {'ref': row}))
        for _ in range(10):
            time.sleep(1.5)
            box = re.search(r'textbox "Message Body"[^\n]*\[(ref_\d+)\]', reader.read_page('all').text)
            if box:
                return str(reader.read_page('all', box.group(1)).text)
        return None
    finally:
        for tab in (linked(['tab', 'list'], 20).data or {}).get('tabs', []):
            if tab.get('active'):  # this oracle session's own tab only
                linked(['tab', 'close', str(tab['tabId'])], 20)


def _media() -> List[Dict[str, str]]:
    import cases  # type: ignore[import-not-found]
    return list(cases.media_sessions())


READERS: Readers = {'file': _file_text, 'processes': _processes, 'windows': _windows, 'clipboard': _clipboard,
                    'dnd_on': _dnd_on, 'google_page': _google_page, 'gmail_draft_body': _gmail_draft_body,
                    'media': _media}


# Oracle factories (each returns problems; empty = verified) --------------------------------------------------
def file_equals(path: Path, expected: str) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        text = READERS['file'](path)
        if text is None:
            return [f'{path.name} was not saved']
        got = [line.strip() for line in text.splitlines() if line.strip()]
        want = [line.strip() for line in expected.splitlines() if line.strip()]
        return [] if got == want else [f'{path.name} holds {got[:5]!r}, expected {want!r}']
    return oracle


def file_contains(path: Path, *needles: str) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        text = READERS['file'](path)
        if text is None:
            return [f'{path.name} does not exist']
        return [f'{path.name} lacks {n!r}' for n in needles if n not in text]
    return oracle


def file_moved(old: Path, new: Path, body: str) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        problems = []
        if READERS['file'](old) is not None:
            problems.append(f'{old.name} still exists')
        if (READERS['file'](new) or '').strip() != body.strip():
            problems.append(f'{new.name} does not hold the original text')
        return problems
    return oracle


def folder_exists(path: Path) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        return [] if _isdir(path) else [f'folder {path.name} was not created']
    return oracle


def _isdir(path: Path) -> bool:
    reader = READERS.get('isdir')
    return bool(reader(path)) if reader else Path(path).is_dir()


def process_running(image: str, running: bool = True) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        present = image.lower() in READERS['processes']()
        if present == running:
            return []
        return [f'{image} is {"not " if running else "still "}running']
    return oracle


def ran_then_closed(image: str) -> Callable[[Any], List[str]]:
    """The app was started during the run (the runner's process watch saw it) and is gone now."""
    def oracle(run: Any) -> List[str]:
        problems = [] if image.lower() in {s.lower() for s in getattr(run, 'seen', set())} else             [f'{image} was never started during the run']
        if image.lower() in READERS['processes']():
            problems.append(f'{image} is still running')
        return problems
    return oracle


def window_rect(title_part: str, width: int, height: int, tolerance: int = 24) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        rows = [w for w in READERS['windows']() if title_part.lower() in w[1].lower()]
        if not rows:
            return [f'no window titled like {title_part!r}']
        left, top, right, bottom = rows[0][2]
        w, h = right - left, bottom - top
        if abs(w - width) > tolerance or abs(h - height) > tolerance:
            return [f'window is {w}x{h}, not {width}x{height}']
        return []
    return oracle


def window_restored(title_part: str) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        rows = [w for w in READERS['windows']() if title_part.lower() in w[1].lower()]
        if not rows:
            return [f'no window titled like {title_part!r}']
        return [] if not rows[0][3] else ['the window is still minimized']
    return oracle


def clipboard_is(text: str) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        got = READERS['clipboard']()
        return [] if got.strip() == text else [f'clipboard holds {got[:60]!r}, not {text!r}']
    return oracle


def media_playing(source: str, playing: bool = True) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        time.sleep(READERS.get('settle', lambda: 3)())
        rows = [s for s in READERS['media']() if source in s['source'].lower()]
        state = any(s['status'] == 'playing' for s in rows)
        if not rows:
            return [f'no {source} media session']
        return [] if state == playing else [f'{source} is {"not " if playing else ""}playing ({rows})']
    return oracle


def page_shows(url: str, *needles: str) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        text = READERS['google_page'](url)
        if 'drive.google.com/drive/search' in url:
            # A search page repeats the query ("No results for 'X'"): only a listed item counts.
            return [f'Drive search lists no item named {n!r}' for n in needles
                    if f"quick overview for '{n}'".lower() not in text.lower()
                    and not re.search(r'(?:LayoutTableCell|gridcell|row) "' + re.escape(n) + r'(?: |")', text, re.I)]
        return [f'{url} does not show {n!r}' for n in needles if n.lower() not in text.lower()]
    return oracle


def draft_body(subject: str, text: str) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        body = READERS['gmail_draft_body'](subject)
        if body is None:
            return [f'no Gmail draft "{subject}" could be opened']
        return [] if text.lower() in body.lower() else [f'draft "{subject}" body reads {body[:60]!r}, not {text!r}']
    return oracle


def composed_draft(run: Any) -> List[str]:
    """A written email: the answer names the subject Jarvis wrote, and that draft opens in Gmail with a real body
    (the browser route's answer shows the body: its start must be there). Works for the Gmail API answer too
    ("Draft saved in Gmail. Subject: X. Recipient: ...")."""
    answer = str(getattr(run, 'answer', ''))
    subject = re.search(r'^Subject: (.+)$', answer, re.M) or re.search(r'Subject: (.+?)\.?\s+Recipient:', answer)
    if not subject:
        return [f'no written subject in the answer ({answer[:80]!r})']
    saved = READERS['gmail_draft_body'](subject.group(1).strip())
    if saved is None:
        return [f'no Gmail draft "{subject.group(1).strip()}" could be opened']
    words = ' '.join(re.sub(r'(?i)text "|press / for help me write|\\n|"', ' ', saved).split())
    if len(words) < 40:
        return [f'the draft body is nearly empty ({words[:60]!r})']
    shown = answer.split('\n\n', 1)[1].strip() if '\n\n' in answer else ''
    first = shown.splitlines()[0].strip()[:40] if shown else ''
    return [] if not first or first.lower() in saved.lower() else [f'the draft body does not start with {first!r}']


def body_uses(*needles: str) -> Callable[[Any], List[str]]:
    """The written email's body (after the To/Subject lines) contains the user's details from memory."""
    def oracle(run: Any) -> List[str]:
        answer = str(getattr(run, 'answer', ''))
        body = answer.split('\n\n', 1)[1] if '\n\n' in answer else ''
        return [f'the email body does not use {n!r} from memory' for n in needles if n.lower() not in body.lower()]
    return oracle


def drive_file(name: str, *needles: str) -> Callable[[Any], List[str]]:
    """A Drive file with this name exists and its text (Docs as text, Sheets as computed CSV) has the needles."""
    def oracle(run: Any) -> List[str]:
        from jarvis import google_files
        if not google_files.available(APP):
            return ['Google Drive is not connected']
        files = google_files.Files(APP)
        try:
            found = files.find(name)
            if not found:
                return [f'no Drive file named {name!r}']
            text = str(files.read(str(found[0]['id'])).get('text', ''))
        finally:
            files.close()
        return [f'{name!r} does not contain {n!r}' for n in needles if n.lower() not in text.lower()]
    return oracle


def answer_mentions(*needles: str, any_of: Tuple[str, ...] = ()) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        row = getattr(run, 'row', None)
        if isinstance(row, dict) and not row.get('answer'):
            # Run.answer falls back to the error text: a crash ("SyntaxError: ... (fast_routes.py ...)") must not
            # pass a check on the answer's wording.
            return [f'Jarvis gave no answer ({str(row.get("error") or "nothing")[:80]})']
        answer = str(getattr(run, 'answer', '')).lower()
        problems = [f'answer lacks {n!r}' for n in needles if n.lower() not in answer]
        if any_of and not any(a.lower() in answer for a in any_of):
            problems.append(f'answer has none of {list(any_of)}')
        return problems
    return oracle


def first_page_count(limit: int = 50, exact: Optional[int] = None) -> Callable[[Any], List[str]]:
    """A count of one result page: some number 1..limit, and no larger total (an inbox counter is not the answer).
    ``exact``: the page is known to be full (the account has more matches than one page), so only that count."""
    def oracle(run: Any) -> List[str]:
        numbers = [int(n.replace(',', '')) for n in re.findall(r'\b\d[\d,]*\b', str(getattr(run, 'answer', '')))]
        if exact is not None and exact not in numbers:
            return [f'answer does not give the page count {exact} (numbers: {numbers[:5]})']
        if not any(1 <= n <= limit for n in numbers):
            return [f'answer gives no count between 1 and {limit}']
        if any(n > limit for n in numbers):
            return [f'answer states {max(numbers)}, more than one page ({limit}) can show']
        return []
    return oracle


def both(*oracles: Callable[[Any], List[str]]) -> Callable[[Any], List[str]]:
    def oracle(run: Any) -> List[str]:
        return [p for o in oracles for p in o(run)]
    return oracle


def no_send(run: Any) -> List[str]:
    """Read-only scenarios: no tool call that could send, post or submit."""
    tools = ' '.join(str(t) for t in getattr(run, 'row', {}).get('tools', []))
    return ['a send/post-like tool ran'] if re.search(r'send|post|submit|reply', tools, re.I) else []


# Scenarios -----------------------------------------------------------------------------------------------
def build(m: Any) -> List[Any]:
    """Cases for the live suite. ``m`` is the cases module (Case, TEST, IN_TEST, d1 helpers)."""
    Case, TEST, IN_TEST = m.Case, m.TEST, m.IN_TEST
    tag = f'{random.Random().randint(1000, 9999)}'
    dnd_before: Dict[str, Optional[bool]] = {}

    def fixture(name: str, text: str) -> Callable[[], None]:
        return m.write_fixture(name, text)

    def dnd_prepare() -> None:
        dnd_before['value'] = READERS['dnd_on']()

    def dnd_oracle(run: Any) -> List[str]:
        try:
            now = READERS['dnd_on']()
            return [] if now is True else ['Do Not Disturb is not on']
        finally:
            if dnd_before.get('value') is not None and dnd_before['value'] != READERS['dnd_on']():
                _set_dnd(bool(dnd_before['value']))  # restore the user's setting

    d1 = '{D1}'
    google_folder = 'Jarvis tests'
    cases = [
        # Native apps
        Case('C01', f'Open Notepad, type exactly "control bench one" and save it as c01.txt {IN_TEST}.',
             file_equals(TEST / 'c01.txt', 'control bench one'), ('c01.txt',), approve=('c01.txt',)),
        Case('C02', f'Open c02.txt {IN_TEST} in Notepad, add a new last line "line three" and save it.',
             file_equals(TEST / 'c02.txt', 'line one\nline two\nline three'), approve=('c02.txt',),
             prepare=fixture('c02.txt', 'line one\nline two\n')),
        Case('C03', 'Use the Calculator app to work out 37 times 12.', m.calculator_case('444')),
        Case('C04', 'Turn on Do Not Disturb in Windows settings.', dnd_oracle, prepare=dnd_prepare, approve=('settings',)),
        Case('C05', f'In File Explorer, rename c05-draft.txt {IN_TEST} to c05-final.txt.',
             file_moved(TEST / 'c05-draft.txt', TEST / 'c05-final.txt', 'draft body'), ('c05-final.txt',),
             approve=('c05',), prepare=fixture('c05-draft.txt', 'draft body\n')),
        Case('C06', f'In File Explorer, create a new folder named c06-folder {IN_TEST}.',
             folder_exists(TEST / 'c06-folder'), ('c06-folder',), approve=('c06-folder',)),
        Case('C07', 'Open Task Manager and tell me how many apps are listed under Apps. Do not end any task.',
             answer_mentions(any_of=tuple(str(n) for n in range(1, 60)))),
        Case('C08', 'Open Paint, then close it.', ran_then_closed('mspaint.exe')),
        # Electron / Chromium apps
        Case('C09', 'Search Spotify for lo-fi beats and play the first result.', media_playing('spotify'),
             approve=('spotify',), timeout=600),
        Case('C10', 'Pause Spotify.', media_playing('spotify', playing=False), approve=('spotify',)),
        Case('C11', f'Open c11.py {IN_TEST} in VS Code, add the line print("bench") at the end and save it.',
             file_contains(TEST / 'c11.py', 'x = 1', 'print("bench")'), approve=('c11.py',),
             prepare=fixture('c11.py', 'x = 1\n')),
        Case('C12', 'Read the name of the top chat in WhatsApp. Do not open or send anything.',
             both(answer_mentions(any_of=('chat', 'is', ':')), no_send)),
        Case('C13', 'List the names of my Discord servers. Read only; do not send anything.',
             both(answer_mentions(any_of=('server', 'discord')), no_send)),
        # Windows shell
        Case('C14', 'Open the Start menu and launch Calculator from it.', process_running('calculatorapp.exe')),
        Case('C15', 'Which app icons are in the system tray right now?', answer_mentions(any_of=('tray', 'icon', ','))),
        Case('C16', 'Read my latest Windows notifications to me. Do not dismiss any.',
             both(answer_mentions(any_of=('notification', 'no ')), no_send)),
        Case('C17', 'Copy the text bench-clip-17 to the clipboard.', clipboard_is('bench-clip-17'), approve=('clipboard',)),
        Case('C18', f'Open c18.txt {IN_TEST} in Notepad and resize its window to 800 by 600.',
             window_rect('c18', 800, 600), prepare=fixture('c18.txt', 'resize me\n')),
        Case('C19', f'Open c19.txt {IN_TEST} in Notepad, minimize it, then restore it.', window_restored('c19'),
             prepare=fixture('c19.txt', 'restore me\n')),
        # Web (Chrome)
        Case('C20', 'Search the web for the Python documentation and open the official site.',
             m.web_answer(any_of=('docs.python.org', 'python.org'))),
        Case('C21', f'Open {d1}/forms.html, fill in the name Grace Hopper and the email grace@example.com and choose '
                    'the second option in the dropdown, but do not submit.', m.form_filled_named('Grace Hopper',
                                                                                                   'grace@example.com'),
             prepare=m.d1_prepare, read_final_page=True),
        Case('C22', 'Open Gmail in my browser and tell me the subject of the newest email in my inbox.',
             both(answer_mentions(any_of=('subject', '"', ':')), no_send), approve=('gmail',)),
        Case('C23', 'On the Wikipedia page "List of largest cities", what population does it list for Tokyo?',
             m.web_answer(any_of=('million', '37', '13', '14'))),
        Case('C24', 'Open example.com and iana.org in two browser tabs and tell me both page titles.',
             answer_mentions('Example Domain', any_of=('IANA', 'Internet Assigned'))),
        Case('C25', f'Open {d1}/files.html and download sample.txt into the downloads folder {IN_TEST}.',
             file_contains(TEST / 'downloads' / 'sample.txt', 'sample'), prepare=m.d1_prepare,
             approve=('download', 'sample.txt')),
        Case('C26', 'Open bbc.com, dismiss the cookie banner by rejecting non-essential cookies if one appears, and '
                    'tell me the top headline.', answer_mentions(any_of=('headline', 'bbc', ':'))),
        Case('C27', f'Open {d1}/frames.html and tell me the text shown inside the embedded frame.',
             answer_mentions(any_of=('frame', 'child')), prepare=m.d1_prepare),
        # Google (user's account; drafts only, a "Jarvis tests" folder only)
        Case('C28', f'In Gmail, create a draft to comedywithkh@gmail.com with subject "Jarvis bench {tag}" and body '
                    '"benchmark draft". Do not send it.',
             both(draft_body(f'Jarvis bench {tag}', 'benchmark draft'), no_send),  # saved with its body
             approve=('gmail', 'draft')),
        Case('C29', f'In Gmail, open the draft "Jarvis bench {tag}" and change its body to "edited draft". Do not send.',
             both(draft_body(f'Jarvis bench {tag}', 'edited draft'), no_send),  # the edit itself, read in the draft
             approve=('gmail', 'draft')),
        Case('C28W', 'draft an email to comedywithkh@gmail.com about cant come to party tmrw, sick, sorry, will make it up. '
                     'Do not send it.',
             both(composed_draft, no_send), approve=('gmail', 'draft')),  # a rough idea becomes a full email
        # Emails written from a rough idea; E01-E07 need the user's details from Jarvis's memory.
        Case('E01', 'draft an email to comedywithkh@gmail.com telling my manager im sick today and taking a day off. Do not send it.',
             both(composed_draft, body_uses('Kunal Vaghani',), no_send), approve=('gmail', 'draft')),
        Case('E02', 'draft an email to comedywithkh@gmail.com applying for the summer internship, they should reply to my email. Do not send it.',
             both(composed_draft, body_uses('Kunal Vaghani', 'kunalvaghani35@gmail.com'), no_send), approve=('gmail', 'draft')),
        Case('E03', 'draft an email to comedywithkh@gmail.com asking professor for a meeting next week about my project, include how to reach me. Do not send it.',
             both(composed_draft, body_uses('Kunal Vaghani', 'kunalvaghani35@gmail.com'), no_send), approve=('gmail', 'draft')),
        Case('E04', 'draft an email to comedywithkh@gmail.com complaining order 4417 arrived late and damaged, want refund, give my contact email. Do not send it.',
             both(composed_draft, body_uses('Kunal Vaghani', 'kunalvaghani35@gmail.com'), no_send), approve=('gmail', 'draft')),
        Case('E05', 'draft an email to comedywithkh@gmail.com introducing myself to the new team as the new member, say who i am and how to contact me. Do not send it.',
             both(composed_draft, body_uses('Kunal Vaghani', 'kunalvaghani35@gmail.com'), no_send), approve=('gmail', 'draft')),
        Case('E06', 'draft an email to comedywithkh@gmail.com following up on unpaid invoice 2209 from last month, sign with my full name. Do not send it.',
             both(composed_draft, body_uses('Kunal Vaghani',), no_send), approve=('gmail', 'draft')),
        Case('E07', 'draft an email to comedywithkh@gmail.com asking to update my contact email on my account to my main email. Do not send it.',
             both(composed_draft, body_uses('Kunal Vaghani', 'kunalvaghani35@gmail.com'), no_send), approve=('gmail', 'draft')),
        Case('E08', 'draft an email to comedywithkh@gmail.com sorry i missed your call yesterday, free after 6 today. Do not send it.',
             both(composed_draft, no_send), approve=('gmail', 'draft')),
        Case('E09', 'draft an email to comedywithkh@gmail.com inviting friends to board game night saturday 7pm at my place, bring snacks. Do not send it.',
             both(composed_draft, no_send), approve=('gmail', 'draft')),
        Case('E10', 'draft an email to comedywithkh@gmail.com reminding colleague the report is due friday, ask if they need help. Do not send it.',
             both(composed_draft, no_send), approve=('gmail', 'draft')),
        # Family names come from the profile note in Jarvis's memory; the requests never name anyone.
        Case('E11', 'draft an email to comedywithkh@gmail.com wishing my brother a happy birthday and saying i will call him tonight. Do not send it.',
             both(composed_draft, body_uses('Jaydeep',), no_send), approve=('gmail', 'draft')),
        Case('E12', 'draft an email to comedywithkh@gmail.com inviting my parents to dinner this sunday to celebrate their anniversary. Do not send it.',
             both(composed_draft, body_uses('Kunal'), answer_mentions(any_of=('mom', 'mum', 'dad', 'parents', 'rajeshbhai', 'alkaben')), no_send),
             approve=('gmail', 'draft')),  # to one's parents "Mom and Dad" is right; their names are optional
        Case('E13', 'draft an email to comedywithkh@gmail.com asking my brother to pick up our mother from the station on friday evening. Do not send it.',
             both(composed_draft, body_uses('Jaydeep'), no_send), approve=('gmail', 'draft')),
        # Google Drive, Docs and Sheets: the user's files read, new ones made (google_files tools).
        Case('G01', 'Find my Google Drive files named "Jarvis bench doc" and list them.',
             answer_mentions('Jarvis bench doc')),
        Case('G02', 'What does my Google Doc "Jarvis bench doc 9441" say?',
             answer_mentions('Control benchmark document')),
        Case('G03', 'Using my Google Sheet "Jarvis bench sheet 6396", what number is in cell A4?',
             answer_mentions('15')),
        Case('G04', f'Research the history of the Eiffel Tower and save a short summary as a Google Doc named '
                    f'"Jarvis research Eiffel {tag}" in the "{google_folder}" folder.',
             drive_file(f'Jarvis research Eiffel {tag}', 'Eiffel', '1889'), approve=('google docs', 'drive')),
        Case('G05', f'Write a Python script that prints the first 10 Fibonacci numbers and save it to my Google Drive '
                    f'"{google_folder}" folder as fib_{tag}.py.',
             drive_file(f'fib_{tag}.py', 'print'), approve=('drive', 'fib')),
        Case('G06', f'Create a Google Sheet named "Jarvis budget {tag}" in the "{google_folder}" folder with columns '
                    'Item and Cost: rent 500, food 200, travel 100, and a total row.',
             drive_file(f'Jarvis budget {tag}', 'rent', '800'), approve=('google sheets', 'drive')),
        Case('C30', 'In Gmail, search for emails from Google and tell me how many results there are on the first page.',
             both(first_page_count(50, exact=50), no_send)),  # >50 matches: a full page of 50
        Case('C31', f'In Google Drive, create a folder named "{google_folder}" if it does not exist.',
             both(page_shows('https://drive.google.com/drive/search?q=' + google_folder.replace(' ', '%20'), google_folder),
                  answer_mentions(any_of=('exist', 'created', 'already'))),  # Jarvis checked or made it
             approve=('drive',)),
        Case('C32', f'In Google Docs, create a document named "Jarvis bench doc {tag}" in the "{google_folder}" folder '
                    'containing the sentence "Control benchmark document."',
             page_shows(f'https://drive.google.com/drive/search?q=Jarvis%20bench%20doc%20{tag}',
                        f'Jarvis bench doc {tag}'), approve=('docs',)),
        Case('C33', f'In Google Sheets, create a spreadsheet named "Jarvis bench sheet {tag}" in the "{google_folder}" '
                    'folder with 4, 5 and 6 in A1 to A3 and a sum in A4; tell me the sum.',
             both(page_shows(f'https://drive.google.com/drive/search?q=Jarvis%20bench%20sheet%20{tag}',
                             f'Jarvis bench sheet {tag}'), answer_mentions('15')), approve=('sheets',)),
        Case('C34', f'Upload c34.txt {IN_TEST} to the "{google_folder}" folder in Google Drive.',
             both(page_shows('https://drive.google.com/drive/search?q=c34.txt', 'c34.txt'),
                  answer_mentions('uploaded')),  # an older c34.txt in Drive must not pass for this upload
             approve=('upload', 'drive'),
             prepare=fixture('c34.txt', 'upload me\n')),
        # Hard cases
        Case('C35', f'Notepad is minimized with c35.txt open; type " and more" at the end of it and save.',
             file_equals(TEST / 'c35.txt', 'start and more'), approve=('c35.txt',),
             prepare=m.notepad_minimized_prepare('c35.txt', 'start')),
        Case('C36', 'Calculator is behind other windows; use it to work out 81 divided by 9.', m.calculator_case('9'),
             prepare=m.calculator_covered_prepare),
        Case('C37', 'Spotify is closed. Open it and play the song Clair de Lune.', media_playing('spotify'),
             approve=('spotify',), prepare=m.close_app_prepare('spotify.exe'), timeout=600),
        Case('C38', 'Open notpad.', process_running('notepad.exe')),
        Case('C39', f'Open c39.txt {IN_TEST} in Notepad, add "unsaved" and close Notepad without saving the change.',
             file_equals(TEST / 'c39.txt', 'keep me'), approve=('c39.txt', "don't save"),
             prepare=fixture('c39.txt', 'keep me\n')),
        Case('C40', f'Open the Blender file c40.blend {IN_TEST}, add a UV sphere from the Add menu and save it.',
             m.blender_has_object('c40.blend', 'Sphere'), approve=('c40.blend',), timeout=900,
             prepare=m.blender_copy_prepare('c40.blend')),
        # Concurrency
        Case('C41', f'While I keep working, open c41.txt {IN_TEST} in Notepad and add the line "background edit", then '
                    'save it.', file_equals(TEST / 'c41.txt', 'first\nbackground edit'), approve=('c41.txt',),
             prepare=fixture('c41.txt', 'first\n'), focus_watch=True),
        Case('C42', 'Open Calculator and Notepad side by side.',
             both(process_running('calculatorapp.exe'), process_running('notepad.exe'))),
        Case('C43', 'What is the title of the window I am working in right now?',
             answer_mentions(any_of=('visual studio', 'code', 'chrome', 'notepad', 'explorer', '-'))),
        Case('C44', f'Open {d1}/modal.html, open the dialog, and close it with its Cancel button.',
             answer_mentions(any_of=('closed', 'cancel')), prepare=m.d1_prepare),
    ]
    return cases
