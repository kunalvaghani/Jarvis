"""The control layer as Jarvis uses it: one service owning the four routes, called by the planner tools.

Tools (tools.py) pass plain strings; this service turns them into typed Actions, classifies risk from
the target's own label (a click on "Send" or "Delete" is Tier 2 and asks the user first), routes the
action, streams progress to the island and returns compact text the planner can read: the outcome,
its evidence and, after page/window changes, fresh refs. Nothing is retried after input was sent.
"""
from __future__ import annotations

from dataclasses import replace
import json
import re
import threading
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit

from .executor import RouteExecutor
from .input import Input
from .locks import LockManager
from .policy import ApprovalGate, Policy, classify
from .progress import ProgressEvent, Reporting, Sink, emit
from .settings import ControlSettings, load
from .types import Action, ActionResult, CancelToken, ControlError, ErrorCategory, Risk, Route, TargetContext

# Kind "name" [optional state such as focused or value='x'] [ref]: the state must not hide a Submit from risk checks.
ROW = re.compile(r'(\w[\w ]*?) "([^"]*)"(?: [^\[\n]*?)? \[([\w-]+)\]')
WEB_OPS = {'click': 'left_click', 'double_click': 'double_click', 'right_click': 'right_click', 'hover': 'hover',
           'fill': 'form_input', 'select': 'form_input', 'check': 'form_input', 'type': 'type', 'key': 'key',
           'scroll': 'scroll', 'scroll_to': 'scroll_to', 'back': 'navigate', 'forward': 'navigate', 'reload': 'navigate',
           'new_tab': 'new_tab', 'switch_tab': 'switch_tab', 'close_tab': 'close_tab', 'wait': 'wait'}
APP_OPS = {'click', 'invoke', 'set_value', 'toggle', 'select', 'expand', 'collapse', 'scroll', 'focus', 'type', 'key',
           'close_window', 'focus_window', 'save_as'}
# A key chord or a single named key the model may put in value instead of the op name.
CHORD = re.compile(r'(?i)(?:(?:ctrl|control|alt|shift|win)\+)+\w+|enter|return|escape|esc|tab|f\d{1,2}|delete|backspace')
SCREEN_OPS = {'click', 'double_click', 'right_click', 'type', 'scroll', 'locate', 'key', 'screenshot'}
READ_LIMIT = 9000
Approve = Callable[[Action], bool]


def resolve_ref(ref: str, text: str) -> str:
    """A ref, or a label the model used as one ("Clear", "edit"): the unique element with that exact name."""
    found = labels(text)
    if not ref or ref in found:
        return ref
    named = [r for r, (_, name) in found.items() if name.strip().casefold() == ref.strip().casefold()]
    if len(named) == 1:
        return named[0]
    if len(named) > 1:
        raise ControlError(f'"{ref}" matches {len(named)} elements ({", ".join(named[:6])}); use one of these refs.',
                           ErrorCategory.INVALID_ARGUMENTS)
    return ref  # Unknown: the route reports it as stale/not found.


def changes(before: str, after: str, limit: int = 8) -> List[str]:
    """Lines that appeared after an action (refs stripped), e.g. 'Text "Display is 68,315"'."""
    def clean(text: str) -> List[str]:
        return [re.sub(r' \[[\w-]+\]', '', line).strip() for line in text.splitlines()[1:] if line.strip()]
    old = set(clean(before))
    return [line for line in clean(after) if line not in old][:limit]


def infer_op(op: str, args: Mapping[str, Any], ops: Any, with_ref_and_text: str) -> str:
    """The operation, or the one the arguments make unambiguous when the model put something else in value."""
    op = str(op).strip().lower()
    if op in ops:
        return op
    if args.get('ref') and args.get('text'):
        return with_ref_and_text
    if args.get('text'):
        return 'type'
    if args.get('ref'):
        return 'click'
    return op


def notepad_notice(read: str) -> str:
    """The OK ref of Notepad's missing-file notice, when that notice (and nothing riskier) is showing."""
    if not re.search(r'Text "Cannot find the [^"]+ file\."', read):
        return ''
    buttons = [(ref, name) for ref, (kind, name) in labels(read).items() if kind == 'Button' and 'aid=CloseButton' in
               next((line for line in read.splitlines() if f'[{ref}]' in line), '')]
    ok = [ref for ref, name in buttons if name == 'OK']
    return ok[0] if len(ok) == 1 else ''


def fresh_notepad_tab(read: str) -> bool:
    """The selected Notepad tab is a new, unmodified Untitled one and its editor holds no text."""
    selected = re.search(r'TabItem "([^"]*)" \[[\w-]+\][^\n]*\bselected\b', read)
    editor = re.search(r"Document \"Text editor\" \[[\w-]+\](.*)", read)
    return bool(selected and selected.group(1) == 'Untitled. Unmodified.' and editor and "value='" not in editor.group(1))


def field_text(read: str) -> Optional[str]:
    """The focused editor or edit box's text from a read (Notepad shows line breaks as \\r), or None."""
    match = re.search(r"^\s*(?:Document|Edit) \"[^\"]*\" \[[\w-]+\] value='(.*)'(?: \w+)*$", read, re.M)
    if not match:
        return None
    return match.group(1).replace('\\r\\n', '\n').replace('\\r', '\n').replace('\\n', '\n')


def typed_intact(typed: str, shown: str) -> bool:
    def lines(text: str) -> List[str]:
        return [line.rstrip() for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    want, have = '\n'.join(lines(typed)).strip(), '\n'.join(lines(shown))
    return bool(want) and want in have


def labels(text: str) -> Dict[str, Tuple[str, str]]:
    """ref -> (kind, name) from a route's read output."""
    return {m.group(3): (m.group(1).strip(), m.group(2)) for m in ROW.finditer(text)}


class ControlService:
    def __init__(self, settings: Optional[ControlSettings] = None, approve: Optional[Approve] = None,
                 sink: Optional[Sink] = None, policy: Optional[Policy] = None) -> None:
        self.settings = settings or load()
        self.policy = policy or Policy(allowed_roots=self.settings.allowed_roots,
                                       allowed_apps=frozenset(self.settings.allowed_apps))
        self.locks = LockManager()
        self.approvals = ApprovalGate(approve)
        self.sink = sink
        self._lock = threading.RLock()
        self._routes: Dict[str, Reporting] = {}
        self._input: Optional[Input] = None
        self.profile = 'test'
        self.last_web = ''          # Last page read (ref -> label lookup).
        self.last_app = ''          # Last window read.
        self.app_scope = ''         # 'win-<handle>' of the last window read.

    # Routes ----------------------------------------------------------------------
    def _shared_input(self) -> Input:
        if self._input is None:
            self._input = Input(self.locks, 'jarvis-control', use_pointer=False)
        return self._input

    def _route(self, key: str, build: Callable[[], RouteExecutor], subtitle: str) -> Reporting:
        with self._lock:
            if key not in self._routes:
                self._routes[key] = Reporting(build(), self.sink, subtitle)
            return self._routes[key]

    def browser(self, profile: str = '') -> Reporting:
        profile = profile or self.profile
        if profile not in ('test', 'personal'):
            raise ControlError('profile must be test or personal.', ErrorCategory.INVALID_ARGUMENTS)
        if profile != self.profile and 'browser' in self._routes:
            self._routes.pop('browser').close()  # One Jarvis browser at a time; switching profiles restarts it.
        self.profile = profile

        def build() -> RouteExecutor:
            from .routes.browser import BrowserExecutor
            directory = self.settings.personal_profile if profile == 'personal' else self.settings.test_profile
            directory.mkdir(parents=True, exist_ok=True)
            executor = BrowserExecutor(directory, self.policy, self.settings.downloads, headless=self.settings.headless)
            executor.start()
            return executor
        return self._route('browser', build, 'Browser · ' + ('your profile' if profile == 'personal' else 'Jarvis profile'))

    def uia(self) -> Reporting:
        def build() -> RouteExecutor:
            from .routes.uia import UIAExecutor
            return UIAExecutor(self.policy, self._shared_input())
        return self._route('uia', build, 'Windows apps')

    def vision(self) -> Reporting:
        def build() -> RouteExecutor:
            from .routes.vision import OllamaGrounder, VisionExecutor
            chain = [OllamaGrounder(model, self.settings.ollama_url) for model in self.settings.vision_models]
            executor = VisionExecutor(self.policy, self._shared_input(), chain[0], fallbacks=chain[1:])
            executor.progress = self.sink
            return executor
        return self._route('vision', build, 'Vision · on this PC')

    def emergency_stop(self, reason: str = 'stop requested by the user') -> None:
        self.locks.emergency_stop(reason)
        for route in list(self._routes.values()):
            route.cancel()

    def resume(self) -> None:
        self.locks.reset()

    def close(self) -> None:
        with self._lock:
            for route in self._routes.values():
                try:
                    route.close()
                except Exception:
                    pass
            self._routes.clear()

    # Shared ---------------------------------------------------------------------
    def _action(self, route: Route, name: str, params: Mapping[str, Any], cancelled: Callable[[], bool],
                label: str = '', target: Any = None, timeout: float = 30.0, window: Optional[int] = None) -> Action:
        token = CancelToken(signal=cancelled)  # Jarvis's stop reaches long waits and model searches.
        risk = classify(name, label)
        return Action(name, f'{name} {label}'.strip(), route, params=dict(params), target=target, risk=risk,
                      timeout_s=timeout, context=TargetContext(window=window) if window else TargetContext(), cancel=token)

    def _run(self, route: Reporting, action: Action) -> ActionResult:
        try:
            if self.locks.stopped:
                raise ControlError('Emergency stop is active: ' + self.locks.stop_reason, ErrorCategory.CANCELLED)
            if action.risk >= Risk.CONSEQUENTIAL:
                emit(self.sink, ProgressEvent(action.route, 'waiting_approval', action.goal[:60], route.subtitle))
                self.approvals.require(action)  # APPROVAL_DENIED: nothing is sent.
        except ControlError as error:
            emit(self.sink, ProgressEvent(action.route, 'refused', action.goal[:60], route.subtitle, str(error)[:80]))
            return ActionResult.failure(action, error)
        return route.act(action)

    @staticmethod
    def _report(result: ActionResult, read: str = '', extra: Optional[Mapping[str, Any]] = None) -> str:
        row: Dict[str, Any] = {'ok': result.ok, 'verified': result.verified, 'executed': result.executed}
        if result.text:
            row['result'] = result.text[:600]
        if result.evidence:
            row['evidence'] = result.evidence[:200]
        if not result.ok:
            row['error'] = result.error_category.value
            if result.executed:
                row['warning'] = 'Input may have reached the target; inspect before repeating.'
        tabs = result.state.get('tabs') if isinstance(result.state, Mapping) else None
        if tabs:
            row['tabs'] = tabs
        if extra:
            row.update(extra)
        text = json.dumps(row, ensure_ascii=False)
        if read:
            text += '\n' + read[:READ_LIMIT] + ('\n[truncated: use find or a ref to read more]' if len(read) > READ_LIMIT else '')
        return text

    # Browser --------------------------------------------------------------------
    def web_read(self, cancelled: Callable[[], bool], filter: str = 'all', find: str = '', ref: str = '') -> str:
        route = self.browser()
        if find:
            result = route.act(self._action(Route.BROWSER, 'find', {'query': find}, cancelled))
        else:
            params: Dict[str, Any] = {'filter': filter if filter in ('interactive', 'all', 'visible') else 'all'}
            if ref:
                params['ref'] = ref
            result = route.act(self._action(Route.BROWSER, 'read_page', params, cancelled))
        if result.ok:
            self.last_web = result.text
        return self._report(replace_text(result), result.text if result.ok else '')

    def web_open(self, url: str, cancelled: Callable[[], bool], profile: str = '', new_tab: bool = False) -> str:
        route = self.browser(profile)
        host = urlsplit(url if '//' in url else 'https://' + url).hostname or url
        route.subtitle = 'Browser · ' + host
        name, params = ('new_tab', {'url': url}) if new_tab else ('navigate', {'url': url})
        result = self._run(route, self._action(Route.BROWSER, name, params, cancelled, url, timeout=45))
        if not result.ok:
            return self._report(result)
        read = route.act(self._action(Route.BROWSER, 'read_page', {'filter': 'all'}, cancelled))  # Text and controls.
        self.last_web = read.text if read.ok else ''
        return self._report(result, self.last_web)

    def web_act(self, op: str, args: Mapping[str, Any], cancelled: Callable[[], bool]) -> str:
        op = infer_op(op, args, WEB_OPS, 'fill')
        if op not in WEB_OPS:
            raise ControlError(f'web_act value must be one of {", ".join(sorted(WEB_OPS))}.', ErrorCategory.INVALID_ARGUMENTS)
        route = self.browser()
        name = WEB_OPS[op]
        params: Dict[str, Any] = {}
        ref = resolve_ref(str(args.get('ref', '')), self.last_web)
        kind, label = labels(self.last_web).get(ref, ('', ''))
        before = self.last_web
        if ref:
            params['ref'] = ref
        if op in ('fill', 'select'):
            params['value'] = str(args.get('text', ''))
        elif op == 'check':
            params['value'] = bool(args.get('checked', True))
        elif op in ('type', 'key'):
            params['text'] = str(args.get('text', ''))
        elif op == 'scroll':
            params.update(scroll_direction=str(args.get('direction', 'down')), scroll_amount=int(args.get('amount', 3)))
        elif op in ('back', 'forward', 'reload'):
            params['url'] = op
        elif op in ('switch_tab', 'close_tab'):
            params['tab_id'] = str(args.get('tab', ''))
        elif op == 'new_tab':
            params['url'] = str(args.get('url', ''))
        elif op == 'wait':
            params['duration'] = float(args.get('seconds', 1))
        if op in ('click', 'double_click', 'right_click', 'hover', 'fill', 'select', 'check', 'scroll_to') and not ref:
            raise ControlError(f'{op} needs a ref from web_read.', ErrorCategory.INVALID_ARGUMENTS)
        # Pressing Enter in a field can submit a form: judge it by the page's submit buttons too.
        judged = label or (' '.join(n for k, n in labels(self.last_web).values() if k == 'button')
                           if op == 'key' and 'enter' in str(args.get('text', '')).lower() else '')
        action = self._action(Route.BROWSER, name, params, cancelled, judged, timeout=float(args.get('timeout', 20)))
        result = self._run(route, action)
        changed = op not in ('hover', 'wait', 'scroll_to')
        read = ''
        if result.executed and changed:
            again = route.act(self._action(Route.BROWSER, 'read_page', {'filter': 'all'}, cancelled))
            if again.ok:
                self.last_web = read = again.text
        extra: Dict[str, Any] = {'target': f'{kind} "{label}"'} if label else {}
        if read:
            extra['changes'] = changes(before, read) or ['nothing visible changed']
        return self._report(result, read, extra or None)

    # Windows apps -----------------------------------------------------------------
    def app_open(self, app: str, path: str, cancelled: Callable[[], bool]) -> str:
        route = self.uia()
        route.subtitle = 'Windows apps · ' + app
        params: Dict[str, Any] = {'app': app}
        if path:
            params['path'] = path
        result = self._run(route, self._action(Route.UIA, 'launch', params, cancelled, app, timeout=20))
        if not result.ok:
            return self._report(result)
        handle = int(result.state.get('handle', 0))
        extra: Dict[str, Any] = {'window': handle}
        if app.lower() == 'notepad' and not path:
            # Windows 11 Notepad reopens the user's earlier tabs: work only in a new, empty one.
            import time
            read = self._settled_read(route, handle)
            notice = notepad_notice(read)
            if notice:
                # "Cannot find <file>" for a restored tab whose file moved: an information notice with only OK.
                route.inner.act(self._action(Route.UIA, 'invoke', {'scope': self.app_scope, 'ref': notice}, cancelled,
                                             'OK', window=handle))
                extra['dismissed'] = 'Notepad notice about a missing file'
                time.sleep(.5)
            route.inner.act(self._action(Route.UIA, 'key', {'handle': handle, 'text': 'ctrl+n'}, cancelled, window=handle))
            time.sleep(.6)
            read = self._settled_read(route, handle)
            extra['new_tab'] = fresh_notepad_tab(read)
            if not extra['new_tab']:
                extra['warning'] = 'No new empty tab is selected; read the window before typing.'
            return self._report(result, read, extra)
        return self._report(result, self._settled_read(route, handle), extra)

    def _settled_read(self, route: Reporting, handle: int, timeout: float = 6.0) -> str:
        """Read a just-opened window once its content has loaded (UWP apps such as Calculator fill in late)."""
        import time
        deadline, previous, text = time.monotonic() + timeout, None, ''
        while time.monotonic() < deadline:
            text = self._read_window(route, handle, 'all')
            if len(text.splitlines()) >= 4 and text == previous:
                return text
            previous = text
            time.sleep(.4)
        return text

    def _read_window(self, route: Reporting, handle: int, filter: str) -> str:
        observation = route.inner.observe(f'win-{handle}', filter=filter)
        self.app_scope, self.last_app = observation.scope, observation.text
        return observation.text

    def app_read(self, window: str, filter: str, cancelled: Callable[[], bool]) -> str:
        route = self.uia()
        params: Dict[str, Any] = {'window': window, 'filter': filter or 'all'}  # Text too, e.g. Calculator's display.
        if window.isdigit():
            params = {'handle': int(window), 'filter': filter or 'all'}
        result = route.act(self._action(Route.UIA, 'read_window', params, cancelled, window))
        if result.ok:
            self.app_scope, self.last_app = str(result.state.get('scope', '')), result.text
            route.subtitle = 'Windows apps · ' + (window or 'front window')
        return self._report(replace_text(result), result.text if result.ok else '', {'window': self.app_scope})

    def app_act(self, op: str, args: Mapping[str, Any], cancelled: Callable[[], bool]) -> str:
        if str(op).strip().lower() not in APP_OPS and CHORD.fullmatch(str(op).strip()):
            args, op = {**args, 'text': str(op).strip()}, 'key'  # The model put the key chord in value.
        op = infer_op(op, args, APP_OPS, 'set_value')
        if op not in APP_OPS:
            raise ControlError(f'app_act value must be one of {", ".join(sorted(APP_OPS))}.', ErrorCategory.INVALID_ARGUMENTS)
        if op in ('type', 'key') and not str(args.get('text', '')):
            raise ControlError(f'{op} needs text: the words to type, or keys such as "ctrl+s". Nothing was sent.',
                               ErrorCategory.INVALID_ARGUMENTS)
        if op == 'save_as':
            return self._save_as(str(args.get('text', '') or args.get('path', '')), args, cancelled)
        route = self.uia()
        ref = resolve_ref(str(args.get('ref', '')), self.last_app)
        kind, label = labels(self.last_app).get(ref, ('', ''))
        before = self.last_app
        params: Dict[str, Any] = {}
        handle = int(self.app_scope[4:]) if self.app_scope.startswith('win-') else None
        if op in ('type', 'key', 'close_window', 'focus_window'):
            params['handle'] = int(args['window']) if str(args.get('window', '')).isdigit() else handle
            if op in ('type', 'key'):
                params['text'] = str(args.get('text', ''))
            if args.get('expect_title'):
                params['expect_title'] = str(args['expect_title'])
        else:
            if not ref:
                raise ControlError(f'{op} needs a ref from app_read.', ErrorCategory.INVALID_ARGUMENTS)
            params.update(scope=self.app_scope, ref=ref)
            if op == 'set_value':
                params['value'] = str(args.get('text', ''))
            if op == 'scroll':
                params['direction'] = str(args.get('direction', 'down'))
            if op == 'toggle' and 'state' in args:
                params['state'] = int(args['state'])
            if args.get('expect_title'):
                params['expect_title'] = str(args['expect_title'])
        judged = label or (op if op in ('close_window',) else '')
        result = self._run(route, self._action(Route.UIA, op, params, cancelled, judged, window=handle))
        read = ''
        if result.executed and handle and op != 'close_window':
            if op in ('type', 'key', 'set_value'):
                import time
                time.sleep(.3)  # Let the app draw the input before reading it back.
            try:
                read = self._read_window(route, handle, 'all')
            except ControlError:
                read = ''
        extra: Dict[str, Any] = {'target': f'{kind} "{label}"'} if label else {}
        if read:
            extra['changes'] = changes(before, read) or ['nothing visible changed']
        shown = field_text(read) if op == 'type' and result.ok and read else None
        if shown is not None:
            if typed_intact(str(params.get('text', '')), shown):
                result = replace(result, verified=True, evidence='the editor shows the typed text')
            else:
                # Input that did not arrive intact must not look like success.
                result = replace(result, ok=False, verified=False, error_category=ErrorCategory.VERIFICATION_FAILED,
                                 evidence='the editor shows ' + repr(shown[:200]))
                extra['next'] = 'Select all (key ctrl+a) and type the whole text again, or use a fresh tab.'
        return self._report(result, read, extra or None)

    def _save_as(self, path: str, args: Mapping[str, Any], cancelled: Callable[[], bool]) -> str:
        """Save the front document through the app's standard Save As dialog, then prove the file exists."""
        import time
        from pathlib import Path
        target = Path(path.strip().strip('"'))
        if not path.strip() or not target.is_absolute() or not target.suffix:
            raise ControlError('save_as needs text: the full file path, e.g. "D:\\folder\\notes.txt". Nothing was sent.',
                               ErrorCategory.INVALID_ARGUMENTS)
        if not target.parent.is_dir():
            raise ControlError(f'Folder {target.parent} does not exist. Nothing was saved.', ErrorCategory.INVALID_ARGUMENTS)
        if target.exists():
            raise ControlError(f'{target} already exists. Jarvis does not overwrite files without asking; '
                               'ask the user, or choose a new name. Nothing was saved.', ErrorCategory.APPROVAL_DENIED)
        route = self.uia()
        handle = int(args['window']) if str(args.get('window', '')).isdigit() else (
            int(self.app_scope[4:]) if self.app_scope.startswith('win-') else None)
        if handle is None:
            raise ControlError('save_as needs an open app window: use app_open or app_read first.', ErrorCategory.INVALID_ARGUMENTS)
        opened = self._run(route, self._action(Route.UIA, 'key', {'handle': handle, 'text': 'ctrl+shift+s'}, cancelled,
                                               'Save As', window=handle))
        if not opened.ok:
            return self._report(opened)
        field = save = ''
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and not (field and save):
            time.sleep(.4)
            found = labels(self._read_window(route, handle, 'all'))
            field = next((r for r, (kind, name) in found.items() if kind == 'Edit' and name.startswith('File name')), '')
            save = next((r for r, (kind, name) in found.items() if kind == 'Button' and name in ('Save', '&Save')), '')
        if not (field and save):
            raise ControlError('The Save As dialog did not appear in this window. Nothing was saved.', ErrorCategory.TARGET_NOT_FOUND)
        scope = self.app_scope
        typed = self._run(route, self._action(Route.UIA, 'set_value', {'scope': scope, 'ref': field, 'value': str(target)},
                                              cancelled, 'File name', window=handle))
        if not typed.ok:
            return self._report(typed)
        result = self._run(route, self._action(Route.UIA, 'invoke', {'scope': scope, 'ref': save}, cancelled,
                                               f'Save {target.name}', window=handle))
        deadline = time.monotonic() + 6
        while result.ok and not target.exists() and time.monotonic() < deadline:
            time.sleep(.3)
        saved = target.exists()
        read = self._read_window(route, handle, 'all') if result.executed else ''
        row = {'ok': saved, 'verified': saved, 'executed': result.executed,
               'result': f'Saved {target}' if saved else f'{target} was not created',
               'evidence': f'file exists, {target.stat().st_size} bytes' if saved else (result.text or '')[:200]}
        if not saved:
            row['error'] = (result.error_category.value if not result.ok else 'unverified')
        return json.dumps(row, ensure_ascii=False) + ('\n' + read[:READ_LIMIT] if read else '')

    # Screen (vision) ----------------------------------------------------------------
    def screen_act(self, op: str, args: Mapping[str, Any], cancelled: Callable[[], bool]) -> str:
        if op not in SCREEN_OPS:
            raise ControlError(f'screen_act value must be one of {", ".join(sorted(SCREEN_OPS))}.',
                               ErrorCategory.INVALID_ARGUMENTS)
        route = self.vision()
        target = str(args.get('target', ''))
        params: Dict[str, Any] = {k: v for k, v in args.items() if k in ('target', 'label', 'text', 'notches', 'handle')}
        if str(args.get('window', '')).isdigit():
            params['handle'] = int(args['window'])
        if op in ('type', 'key'):
            params['text'] = str(args.get('text', ''))
        result = self._run(route, self._action(Route.VISION, op, params, cancelled, str(args.get('label', '')) or target,
                                               timeout=float(args.get('timeout', 90))))
        extra = {'point': result.state.get('point')} if result.state.get('point') else None
        return self._report(result, '', extra)

    # Connection check ---------------------------------------------------------------
    def check(self) -> str:
        from .health import run, summary
        return summary(run(self.settings, self.sink))


def replace_text(result: ActionResult) -> ActionResult:
    """Reads carry their content separately; keep the JSON head short."""
    from dataclasses import replace
    return replace(result, text='') if result.ok else result


TEXT_OPS = {'type', 'fill', 'set_value', 'save_as'}


def parse_args(content: str, op: str = '') -> Dict[str, Any]:
    if not content.strip():
        return {}
    try:
        value = json.loads(content)
    except ValueError:
        if op.strip().lower() in TEXT_OPS:
            return {'text': content}  # Plain text where an object was expected: it is the text itself.
        raise ControlError('content must be a JSON object.', ErrorCategory.INVALID_ARGUMENTS) from None
    if not isinstance(value, dict):
        raise ControlError('content must be a JSON object.', ErrorCategory.INVALID_ARGUMENTS)
    return value


def labels_for_tests(text: str) -> List[Tuple[str, str, str]]:
    return [(m.group(1).strip(), m.group(2), m.group(3)) for m in ROW.finditer(text)]
