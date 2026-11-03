"""AgentBrowserExecutor: the browser route on agent-browser, same contract as routes.browser.BrowserExecutor.

ControlService calls it exactly as the Playwright route: navigate / new_tab / switch_tab / close_tab / list_tabs /
read_page / find / get_page_text / wait / form_input / left_click / double_click / hover / scroll / scroll_to /
type / key. Page reads come back as lines ``role "name" state [ref_N]`` and ``text "..."``.

Every call carries (tests fail if either is missing):
- ``--content-boundaries``: page output is marked as untrusted data; a page response without its boundary marker
  is refused, so tool output can never pose as instructions;
- ``--action-policy``: a generated policy that denies script evaluation, network rewriting, cookie/storage/
  credential writes and similar, and asks the user (Jarvis's approval card) before uploads and clipboard access.

Domains: ``--allowed-domains`` cannot be combined with a Chrome profile (agent-browser refuses), so Jarvis's own
URL policy (``Policy.check_url``) checks every navigation target and every final URL, as the legacy route does.

Retry: agent-browser errors carry no delivery field. Only errors that prove nothing ran (unknown ref, policy
denial, invalid arguments) may be retried or reported as not executed; any other failure after an action is
``uncertain`` and is never repeated blindly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from pydantic import BaseModel, ConfigDict

from ..executor import Health, RouteExecutor
from ..policy import Policy
from ..types import Action, ActionResult, ControlError, ErrorCategory, Observation, Ref as JarvisRef, Route

APP = Path(__file__).resolve().parents[3]
VERSION = '0.41.1'
DEFAULT_BINARY = APP / '.jarvis-runtime' / 'tools' / 'control-backends' / f'agent-browser-{VERSION}' / 'agent-browser.exe'
POLICY_FILE = APP / '.jarvis-runtime' / 'control' / 'agent-browser-policy.json'
KEY_FILE = APP / 'secrets' / 'agent-browser.key'
MAX_OUTPUT = 60000
# Protocol action names (agent-browser cli/src/native/actions.rs, v0.41.1).
DENY = ('evaluate', 'evalhandle', 'addinitscript', 'addscript', 'addstyle', 'expose', 'route', 'unroute', 'headers',
        'offline', 'permissions', 'credentials', 'credentials_set', 'credentials_get', 'credentials_delete',
        'credentials_list', 'cookies_get', 'cookies_set', 'cookies_clear', 'storage_get', 'storage_set', 'storage_clear',
        'state_save', 'state_load', 'state_clear', 'state_clean', 'state_rename', 'auth_save', 'auth_login', 'auth_delete',
        'auth_show', 'setcontent', 'har_start', 'har_stop', 'responsebody', 'request_detail', 'webmcp_invoke',
        'dispatch', 'recording_start', 'screencast_start', 'stream_enable', 'trace_start', 'profiler_start',
        'useragent', 'user_agent', 'geolocation', 'device')
CONFIRM = ('upload', 'clipboard', 'download', 'waitfordownload')
CONTENT_COMMANDS = frozenset({'open', 'snapshot', 'read', 'get'})
# The user's real, running Chrome profile ("Person 1"), reached through Chrome's own remote-debugging switch
# (chrome://inspect/#remote-debugging, Chrome 144+, each connection approved in Chrome). A copied profile would be
# signed out: Windows Chrome binds cookies to the original profile folder (checked 2026-11-02).
AUTO_CONNECT = 'auto-connect'
APPROVAL_PENDING = re.compile(r'waiting for remote-debugging approval', re.I)
APPROVAL_WAIT_S = 90.0
# Sites that only make sense signed in: never fall back to Jarvis's own (signed-out) profile for these.
ACCOUNT_SITES = re.compile(r'\b(?:mail|drive|docs|sheets|calendar|myaccount)\.google\.com\b|\bgmail\.com\b', re.I)
FALLBACK_PROFILE = str(APP / '.jarvis-runtime' / 'test-browser-profile')  # Jarvis's own persistent profile
NOT_RUN = re.compile(r'unknown ref|denied by policy|not in the allow list|invalid|unknown command|required argument|'
                     r'no such tab|not found', re.I)
LINE = re.compile(r'^(?P<indent>\s*)- (?P<role>[\w-]+)(?: "(?P<name>(?:[^"\\]|\\.)*)")?(?P<rest>.*)$')
REF = re.compile(r'\[ref=(e\d+)\]')


class Reply(BaseModel):
    model_config = ConfigDict(extra='allow')
    success: bool
    data: Any = None
    error: Optional[str] = None

    @property
    def boundary(self) -> Optional[Dict[str, Any]]:  # noqa: D401
        extra = self.model_extra or {}
        found = extra.get('_boundary')
        return found if isinstance(found, dict) else None


def write_policy(path: Path = POLICY_FILE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {'default': 'allow', 'deny': list(DENY), 'confirm': list(CONFIRM)}
    text = json.dumps(body, indent=1)
    if not path.exists() or path.read_text(encoding='utf-8') != text:
        path.write_text(text, encoding='utf-8')
    return path


def encryption_key(path: Path = KEY_FILE) -> Optional[str]:
    try:
        value = path.read_text(encoding='ascii').strip()
    except OSError:
        return None
    return value if re.fullmatch(r'[0-9a-f]{64}', value) else None


Run = Callable[..., 'subprocess.CompletedProcess[str]']


class BrowserRunner:
    def __init__(self, binary: Optional[Path] = None, session: str = 'jarvis', profile: str = '', headed: bool = True,
                 policy_file: Optional[Path] = None, run: Run = subprocess.run, chrome: str = '') -> None:
        self.binary = Path(binary or os.environ.get('JARVIS_AGENT_BROWSER') or DEFAULT_BINARY)
        self.session, self.profile, self.headed, self._run = session, profile, headed, run
        self.policy_file = policy_file or write_policy()
        self.chrome = chrome
        self.auto_connect = profile == AUTO_CONNECT
        self.calls: List[Dict[str, Any]] = []

    def argv(self, args: Sequence[str]) -> List[str]:
        argv = [str(self.binary), '--json', '--content-boundaries', '--max-output', str(MAX_OUTPUT),
                '--action-policy', str(self.policy_file), '--session', self.session]
        if self.auto_connect:
            argv.append('--auto-connect')  # the user's own running Chrome (signed in); never launched or closed by us
        elif self.profile:
            argv += ['--profile', self.profile]
        if self.headed and not self.auto_connect:
            argv.append('--headed')
        if self.chrome:
            argv += ['--executable-path', self.chrome]
        return argv + [str(a) for a in args]

    def __call__(self, args: Sequence[str], timeout_s: float = 60.0) -> Reply:
        env = dict(os.environ)
        key = encryption_key()
        if key:
            env['AGENT_BROWSER_ENCRYPTION_KEY'] = key
        env.pop('AGENT_BROWSER_ALLOWED_DOMAINS', None)  # cannot combine with profiles; Jarvis's policy applies instead
        started = time.perf_counter()
        try:
            done = self._run(self.argv(args), capture_output=True, text=True, encoding='utf-8', errors='replace',
                             timeout=timeout_s, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except FileNotFoundError:
            raise ControlError(f'agent-browser is not installed at {self.binary}; run '
                               'scripts/install_control_backends.ps1.', ErrorCategory.TOOL_ERROR) from None
        except subprocess.TimeoutExpired:
            raise ControlError(f'agent-browser {args[0] if args else ""} timed out', ErrorCategory.UNCERTAIN,
                               executed=True) from None
        reply = parse(done.stdout, done.stderr)
        if args and args[0] in CONTENT_COMMANDS and reply.success and reply.boundary is None:
            # Page text without its boundary marker must never reach the planner.
            raise ControlError('agent-browser returned page content without content boundaries; refused.',
                               ErrorCategory.POLICY_DENIED)
        if len(self.calls) < 500:
            self.calls.append({'command': args[0] if args else '', 'ok': reply.success,
                               'ms': round((time.perf_counter() - started) * 1000, 1)})
        return reply


def parse(stdout: str, stderr: str = '') -> Reply:
    text = (stdout or '').strip()
    for candidate in (text, text.splitlines()[-1] if text else ''):
        try:
            return Reply.model_validate(json.loads(candidate))
        except (ValueError, TypeError):
            continue
    return Reply(success=False, error=f'unreadable output: {(stderr or text or "no output")[-300:]}')


def to_error(reply: Reply, acting: bool) -> ControlError:
    message = str(reply.error or 'agent-browser failed')[:300]
    not_run = bool(NOT_RUN.search(message))
    if re.search(r'unknown ref', message, re.I):
        category = ErrorCategory.STALE_REF
    elif re.search(r'denied by policy|allow list', message, re.I):
        category = ErrorCategory.POLICY_DENIED
    elif re.search(r'timed? ?out', message, re.I):
        category = ErrorCategory.TIMEOUT
    elif not_run:
        category = ErrorCategory.INVALID_ARGUMENTS
    else:
        category = ErrorCategory.UNCERTAIN if acting else ErrorCategory.TOOL_ERROR
    return ControlError(message, category, executed=acting and not not_run)


def render(snapshot: str, refs: Dict[str, str]) -> List[str]:
    """agent-browser '- role "name" [ref=e3] [checked]' -> Jarvis 'role "name" checked [ref_3]' / 'text "..."'."""
    lines = []
    for raw in snapshot.splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        indent = len(m.group('indent')) // 2
        role, name, rest = m.group('role'), (m.group('name') or ''), m.group('rest')
        ref = REF.search(rest)
        state = ' '.join(s for s in re.findall(r'\[([^\]=]+(?:=[^\]]*)?)\]', rest) if not s.startswith('ref='))
        if role == 'StaticText':
            lines.append(f'{"  " * indent}text "{name[:300]}"')
        elif ref:
            jref = 'ref_' + ref.group(1)[1:]
            refs[jref] = '@' + ref.group(1)
            lines.append(f'{"  " * indent}{role} "{name[:200]}"' + (f' {state}' if state else '') + f' [{jref}]')
        elif name:
            lines.append(f'{"  " * indent}{role} "{name[:200]}"')
    return lines


class AgentBrowserExecutor(RouteExecutor):
    route = Route.BROWSER

    def __init__(self, policy: Policy, runner: Optional[BrowserRunner] = None,
                 confirm: Optional[Callable[[str], bool]] = None) -> None:
        self.policy, self.run, self.confirm = policy, runner or BrowserRunner(), confirm
        self.refs: Dict[str, str] = {}
        self.roles: Dict[str, str] = {}
        self.last_url = ''
        self.own_tab = ''  # with --auto-connect: the one tab Jarvis opened; the user's tabs are never driven
        self.mine: Set[str] = set()  # every tab Jarvis opened in the user's Chrome (only these are shown or driven)
        self.notice = ''
        self.on_notice: Optional[Callable[[str], None]] = None  # shows a notice to the user while Jarvis waits
        self._lock = threading.RLock()

    def start(self) -> None:
        return None  # The daemon starts on the first command.

    def health_check(self) -> Health:
        return Health(self.run.binary.is_file(), 'agent-browser ready' if self.run.binary.is_file() else 'missing')

    def cancel(self) -> None:
        return None

    def close(self) -> None:
        if getattr(self.run, 'auto_connect', False):
            for tab in sorted(self.mine | ({self.own_tab} if self.own_tab else set())):
                try:  # close only Jarvis's own tabs; the user's browser stays as it was
                    self.run(['tab', 'close', tab], timeout_s=20)
                except ControlError:
                    pass
            self.mine.clear()
            self.own_tab = ''
            return
        try:
            self.run(['close'], timeout_s=20)
        except ControlError:
            pass

    def _own_tab(self, url: str = '') -> bool:
        """Attached to the user's Chrome: make sure Jarvis acts in its own tab. True when a new tab was opened."""
        if not getattr(self.run, 'auto_connect', False):
            return False
        try:
            self._call(['tab', 'list'], acting=False, timeout_s=30)  # attachable? (falls back if not)
        except ControlError:
            pass
        if not getattr(self.run, 'auto_connect', False):
            return False
        tabs = self._tabs()
        if self.own_tab and any(t['tab_id'] == self.own_tab for t in tabs):
            if not any(t['tab_id'] == self.own_tab and t['active'] for t in tabs):
                self._call(['tab', self.own_tab], acting=False)
            return False
        before = {t['tab_id'] for t in tabs}
        self._call(['tab', 'new'] + ([url] if url else []), acting=True, timeout_s=60)
        fresh = [t for t in self._tabs() if t['tab_id'] not in before]
        self.own_tab = str(fresh[0]['tab_id']) if fresh else ''
        if self.own_tab:
            self.mine.add(self.own_tab)
        return True

    # Helpers ----------------------------------------------------------------------------
    def _call(self, args: List[str], acting: bool, timeout_s: float = 60.0) -> Reply:
        reply = self.run(args, timeout_s)
        if not reply.success and getattr(self.run, 'auto_connect', False) and APPROVAL_PENDING.search(str(reply.error)):
            # Chrome asks the user to allow this connection ("Allow remote debugging?"). That consent is the user's:
            # Jarvis never clicks it. Say so and wait; once allowed, the session daemon keeps the connection.
            self.notice = 'Click Allow on the "Allow remote debugging?" prompt in your Chrome so I can continue.'
            if self.on_notice is not None:
                self.on_notice(self.notice)
            deadline = time.monotonic() + APPROVAL_WAIT_S
            while not reply.success and APPROVAL_PENDING.search(str(reply.error)) and time.monotonic() < deadline:
                time.sleep(3)
                reply = self.run(args, timeout_s)
            if not reply.success and APPROVAL_PENDING.search(str(reply.error)):
                raise ControlError('Chrome is still waiting for you to allow remote debugging; nothing was done.',
                                   ErrorCategory.APPROVAL_DENIED)
            self.notice = ''
        if not reply.success and getattr(self.run, 'auto_connect', False) and \
                re.search(r'no running chrome|failed to connect', str(reply.error), re.I):
            if ACCOUNT_SITES.search(' '.join(str(a) for a in args)):
                # Signed-in sites must not silently open in Jarvis's signed-out profile.
                raise ControlError('Your Chrome (Person 1) is not open, so I cannot use your signed-in accounts; '
                                   'open Chrome and try again. Nothing was done.', ErrorCategory.TARGET_NOT_FOUND)
            # The user's Chrome is not attachable (chrome://inspect/#remote-debugging is off). Nothing was sent, so
            # use Jarvis's own browser profile for this session; signed-in sites will ask for the switch.
            self.run.auto_connect, self.run.profile = False, FALLBACK_PROFILE
            if hasattr(self.run, 'session') and not str(self.run.session).endswith('-own'):
                # The session's daemon is bound to the user's Chrome (CDP): a profile flag on the same session is
                # ignored and the retry fails the same way. Jarvis's own browser gets its own session.
                self.run.session = f'{self.run.session}-own'
            self.notice = ('Your Chrome (Person 1) is not open for remote debugging, so I used my own browser profile. '
                           'For signed-in sites, turn on chrome://inspect/#remote-debugging in your Chrome.')
            reply = self.run(args, timeout_s)
        data = reply.data if isinstance(reply.data, dict) else {}
        if reply.success and data.get('confirmation_required'):
            what, ident = str(data.get('action', '')), str(data.get('confirmation_id', ''))
            granted = False
            if self.confirm is not None:
                try:
                    granted = self.confirm(f'Allow the browser to {what}?') is True
                except Exception:
                    granted = False
            if not granted:
                self.run(['deny', ident], 20)
                raise ControlError(f'The user did not allow {what}; nothing was done.', ErrorCategory.APPROVAL_DENIED)
            reply = self.run(['confirm', ident], timeout_s)
        if not reply.success:
            raise to_error(reply, acting)
        return reply

    def _ref(self, jref: str) -> str:
        if jref not in self.refs:
            raise ControlError(f'{jref} is stale or not on the page. Re-read the page.', ErrorCategory.STALE_REF)
        return self.refs[jref]

    def _tabs(self) -> List[Dict[str, Any]]:
        try:
            reply = self.run(['tab', 'list'], 20)
        except ControlError:
            return []
        rows = (reply.data or {}).get('tabs', []) if isinstance(reply.data, dict) else []
        return [{'tab_id': t.get('tabId'), 'title': str(t.get('title', ''))[:300], 'url': str(t.get('url', ''))[:2000],
                 'active': bool(t.get('active'))} for t in rows if isinstance(t, dict)]

    def _visible_tabs(self) -> List[Dict[str, Any]]:
        """Tabs the planner may see: in the user's own Chrome only the ones Jarvis opened (the user's tabs, their
        titles included, stay private and are never taken for Jarvis's pages)."""
        tabs = self._tabs()
        if getattr(self.run, 'auto_connect', False):
            tabs = [t for t in tabs if str(t['tab_id']) in self.mine]
        return tabs

    def _final_url(self) -> str:
        reply = self._call(['get', 'url'], acting=False, timeout_s=20)
        url = str((reply.data or {}).get('url', '')) if isinstance(reply.data, dict) else ''
        if url.startswith(('http:', 'https:')):
            self.policy.check_url(url)  # The landing page must satisfy the policy too (redirects).
        self.last_url = url
        return url

    # Reading ----------------------------------------------------------------------------
    def read_page(self, filter: str = 'all', ref: Optional[str] = None) -> Observation:
        if getattr(self.run, 'auto_connect', False) and self.own_tab:
            self._own_tab()  # read Jarvis's tab, not whatever the user is looking at
        if ref:
            reply = self._call(['get', 'text', self._ref(ref)], acting=False)
            text = str((reply.data or {}).get('text', '')) if isinstance(reply.data, dict) else ''
            return Observation(Route.BROWSER, 'tab', f'text "{text[:4000]}"', state={'url': self.last_url})
        # -c (compact) drops all page text (checked live): only interactive reads may use it.
        args = ['snapshot'] + (['-i', '-c'] if filter == 'interactive' else [])
        reply = self._call(args, acting=False)
        data = reply.data if isinstance(reply.data, dict) else {}
        with self._lock:
            self.refs = {}
            lines = render(str(data.get('snapshot', '')), self.refs)
            self.roles = roles(str(data.get('snapshot', '')))
        if filter != 'interactive':
            # The tree omits the page title, which can be the only place a heading-like answer appears
            # (example.com today: "Example Domain" is the title only; live D12).
            try:
                titled = self.run(['get', 'title'], 20)
                title = str((titled.data or {}).get('title', '')) if titled.success and isinstance(titled.data, dict) else ''
            except ControlError:
                title = ''
            if title:
                lines.insert(0, f'title "{title[:300]}"')
        refs = tuple(JarvisRef(r, Route.BROWSER, 'tab', 0) for r in self.refs)
        return Observation(Route.BROWSER, 'tab', '\n'.join(lines), refs,
                           state={'url': str(data.get('origin', '')), 'boundary': bool(reply.boundary)})

    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        return self.read_page(str(options.get('filter', 'all')), options.get('ref'))

    def probe(self, what: str, **params: Any) -> Any:
        if what == 'url':
            return self._final_url()
        if what == 'title':
            reply = self._call(['get', 'title'], acting=False)
            return (reply.data or {}).get('title') if isinstance(reply.data, dict) else None
        if what == 'value':
            reply = self._call(['get', 'value', self._ref(str(params['ref']))], acting=False)
            return (reply.data or {}).get('value') if isinstance(reply.data, dict) else None
        raise ControlError(f'Unknown browser probe {what!r}.', ErrorCategory.UNSUPPORTED)

    # Acting -----------------------------------------------------------------------------
    def act(self, action: Action) -> ActionResult:
        try:
            with self._lock:
                result = self._dispatch(action)
        except ControlError as error:
            return ActionResult.failure(action, error, state={'tabs': self._visible_tabs()})
        except Exception as error:
            return ActionResult(action.action_id, False, Route.BROWSER, text=f'{type(error).__name__}: {error}'[:300],
                                executed=True, error_category=ErrorCategory.UNCERTAIN)
        return result

    def _done(self, action: Action, text: str = '', executed: bool = True, verified: bool = False,
              evidence: str = '', **state: Any) -> ActionResult:
        return ActionResult(action.action_id, True, Route.BROWSER, text=text, executed=executed, verified=verified,
                            evidence=evidence, state={'tabs': self._visible_tabs(), **state})

    def _dispatch(self, action: Action) -> ActionResult:
        name, p = action.name, action.params
        action.cancel.raise_if_cancelled()
        if self.own_tab and name not in ('navigate', 'new_tab', 'switch_tab', 'close_tab', 'list_tabs', 'read_page'):
            self._own_tab()
        if name == 'navigate':
            url = str(p.get('url', ''))
            if url in ('back', 'forward', 'reload'):
                self._own_tab()
                self._call([url], acting=True)
            else:
                checked = self.policy.check_url(url)
                opened = self._own_tab(checked)
                if self.run.profile == FALLBACK_PROFILE and ACCOUNT_SITES.search(checked):
                    # The user's Chrome could not be attached: a signed-in site would open signed out.
                    raise ControlError('Your Chrome (Person 1) is not open, so I cannot use your signed-in accounts; '
                                       'open Chrome and try again. Nothing was done.', ErrorCategory.TARGET_NOT_FOUND)
                if not opened:
                    self._call(['open', checked], acting=True, timeout_s=action.timeout_s + 15)
                else:  # 'tab new <url>' returns before the page starts loading (BBC read as about:blank)
                    try:
                        self._call(['wait', '--load', 'domcontentloaded'], acting=False, timeout_s=action.timeout_s + 15)
                    except ControlError:
                        pass  # judged by the final URL below
                final = self._final_url()
                deadline = time.monotonic() + 15  # the load wait can pass on the blank tab before navigation starts
                while not same_site(checked, final) and time.monotonic() < deadline:
                    action.cancel.raise_if_cancelled()
                    time.sleep(.5)
                    final = self._final_url()
                if not same_site(checked, final):
                    raise ControlError(f'The page did not load {checked} (the tab shows {final or "nothing"}).',
                                       ErrorCategory.VERIFICATION_FAILED, executed=True)
                return self._done(action, f'Navigated to {final}', verified=True, evidence=f'final URL {final}')
            final = self._final_url()
            return self._done(action, f'Navigated to {final}', verified=True, evidence=f'final URL {final}')
        if name == 'new_tab':
            args = ['tab', 'new'] + ([self.policy.check_url(str(p['url']))] if p.get('url') else [])
            attached = getattr(self.run, 'auto_connect', False)
            before = {t['tab_id'] for t in self._tabs()} if attached else set()
            self._call(args, acting=True)
            if attached:
                fresh = [str(t['tab_id']) for t in self._tabs() if t['tab_id'] not in before]
                self.mine.update(fresh)
                self.own_tab = fresh[0] if fresh else self.own_tab  # the new tab is where Jarvis works now
            if p.get('url'):
                self._final_url()
            return self._done(action, verified=True)
        if name in ('switch_tab', 'close_tab'):
            if getattr(self.run, 'auto_connect', False):
                if str(p['tab_id']) not in self.mine:
                    raise ControlError(f'Tab {p["tab_id"]} is not one Jarvis opened; your own tabs are never driven.',
                                       ErrorCategory.POLICY_DENIED)
                if name == 'switch_tab':
                    self.own_tab = str(p['tab_id'])
                else:
                    self.mine.discard(str(p['tab_id']))
                    if self.own_tab == str(p['tab_id']):
                        self.own_tab = next(iter(self.mine), '')
            self._call(['tab', str(p['tab_id'])] if name == 'switch_tab' else ['tab', 'close', str(p['tab_id'])],
                       acting=True)
            return self._done(action, verified=True)
        if name == 'list_tabs':
            return self._done(action, executed=False, verified=True)
        if name == 'read_page':
            obs = self.read_page(str(p.get('filter', 'all')), p.get('ref'))
            return self._done(action, obs.text, executed=False, verified=True)
        if name == 'find':
            obs = self.read_page('all')
            query = str(p['query']).lower()
            rows = [line.strip() for line in obs.text.splitlines() if query in line.lower() and '[ref_' in line]
            return self._done(action, '\n'.join(rows[:20]) or 'No matches.', executed=False, verified=True)
        if name == 'get_page_text':
            reply = self._call(['read'], acting=False)
            text = str((reply.data or {}).get('content', '')) if isinstance(reply.data, dict) else ''
            return self._done(action, text, executed=False, verified=True)
        if name == 'wait':
            seconds = float(p.get('duration', 1))
            if not 0 <= seconds <= 30:
                raise ControlError('wait duration must be 0-30 seconds.', ErrorCategory.INVALID_ARGUMENTS)
            self._call(['wait', str(int(seconds * 1000))], acting=False, timeout_s=seconds + 15)
            return self._done(action, executed=False, verified=True)
        if name == 'form_input':
            ref = self._ref(str(p.get('ref', '')))
            value = p.get('value')
            if isinstance(value, bool):
                self._call(['check' if value else 'uncheck', ref], acting=True)
                return self._done(action, 'checked' if value else 'unchecked', verified=self._verify_checked(ref, value))
            role = self._role_of(str(p.get('ref', '')))
            command = ['select', ref, str(value)] if role in ('combobox', 'listbox') else ['fill', ref, str(value)]
            self._call(command, acting=True)
            current = self._value(ref)
            return self._done(action, f'{command[0]} done', verified=current == str(value),
                              evidence=f'field reads {current!r}'[:200])
        if name in ('left_click', 'double_click', 'hover'):
            ref = self._ref(str(p.get('ref', '')))
            verb = {'left_click': 'click', 'double_click': 'dblclick', 'hover': 'hover'}[name]
            self._call([verb, ref], acting=True)
            return self._done(action, f'{verb} {p.get("ref")}')
        if name == 'scroll':
            amount = int(p.get('scroll_amount', 3))
            direction = str(p.get('scroll_direction', 'down'))
            if direction not in ('up', 'down', 'left', 'right') or not 1 <= amount <= 10:
                raise ControlError('scroll needs a direction and 1-10 notches.', ErrorCategory.INVALID_ARGUMENTS)
            self._call(['scroll', direction, str(amount * 100)], acting=True)
            return self._done(action, f'scrolled {direction} {amount}')
        if name == 'scroll_to':
            self._call(['scrollintoview', self._ref(str(p.get('ref', '')))], acting=True)
            return self._done(action, verified=True)
        if name == 'type':
            self._call(['keyboard', 'type', str(p['text'])], acting=True)
            return self._done(action)
        if name == 'key':
            text = str(p.get('text', '')).strip()
            if not text:
                raise ControlError('key needs text.', ErrorCategory.INVALID_ARGUMENTS)
            for chord in text.split():
                self._call(['press', '+'.join(k.capitalize() if len(k) > 1 else k for k in chord.split('+'))],
                           acting=True)
            return self._done(action, f'pressed {text}')
        raise ControlError(f'Unsupported browser action {name!r} on agent-browser.', ErrorCategory.UNSUPPORTED)

    def _role_of(self, jref: str) -> str:
        return self.roles.get(jref, '')

    def _value(self, ref: str) -> str:
        try:
            reply = self._call(['get', 'value', ref], acting=False, timeout_s=20)
        except ControlError:
            return ''
        return str((reply.data or {}).get('value', '')) if isinstance(reply.data, dict) else ''

    def _verify_checked(self, ref: str, expected: bool) -> bool:
        try:
            reply = self._call(['is', 'checked', ref], acting=False, timeout_s=20)
        except ControlError:
            return False
        data = reply.data if isinstance(reply.data, dict) else {}
        return bool(data.get('checked', data.get('result'))) is expected


def profile_for(kind: str, settings: Any) -> str:
    """'personal' = the user's signed-in Chrome "Person 1" through auto-connect (config
    control.personal_chrome_profile: 'auto-connect' by default, or a profile name to use a signed-out copy);
    'test' = Jarvis's own persistent profile folder."""
    extra = getattr(settings, 'extra', {}) or {}
    if kind == 'personal':
        return str(extra.get('personal_chrome_profile', AUTO_CONNECT))
    return str(getattr(settings, 'test_profile', APP / '.jarvis-runtime' / 'test-browser-profile'))


def roles(snapshot: str) -> Dict[str, str]:
    """ref_N -> role, for choosing fill or select."""
    found: Dict[str, str] = {}
    for raw in snapshot.splitlines():
        m = LINE.match(raw)
        ref = REF.search(raw)
        if m and ref:
            found['ref_' + ref.group(1)[1:]] = m.group('role')
    return found


def same_site(asked: str, final: str) -> bool:
    """The tab reached a real page: http(s), not about:blank or an error page. Redirects to another site
    (gmail.com -> mail.google.com) are normal, so the host is not compared."""
    return final.startswith(('http://', 'https://')) and not final.startswith('https://chrome-error')
