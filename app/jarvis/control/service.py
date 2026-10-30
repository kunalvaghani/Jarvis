"""The control layer as Jarvis uses it: one service owning the four routes, called by the planner tools.

Tools (tools.py) pass plain strings; this service turns them into typed Actions, classifies risk from
the target's own label (a click on "Send" or "Delete" is Tier 2 and asks the user first), routes the
action, streams progress to the island and returns compact text the planner can read: the outcome,
its evidence and, after page/window changes, fresh refs. Nothing is retried after input was sent.
"""
from __future__ import annotations

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

ROW = re.compile(r'(\w[\w ]*?) "([^"]*)" \[([\w-]+)\]')
WEB_OPS = {'click': 'left_click', 'double_click': 'double_click', 'right_click': 'right_click', 'hover': 'hover',
           'fill': 'form_input', 'select': 'form_input', 'check': 'form_input', 'type': 'type', 'key': 'key',
           'scroll': 'scroll', 'scroll_to': 'scroll_to', 'back': 'navigate', 'forward': 'navigate', 'reload': 'navigate',
           'new_tab': 'new_tab', 'switch_tab': 'switch_tab', 'close_tab': 'close_tab', 'wait': 'wait'}
APP_OPS = {'click', 'invoke', 'set_value', 'toggle', 'select', 'expand', 'collapse', 'scroll', 'focus', 'type', 'key',
           'close_window', 'focus_window'}
SCREEN_OPS = {'click', 'double_click', 'right_click', 'type', 'scroll', 'locate', 'key', 'screenshot'}
READ_LIMIT = 9000
Approve = Callable[[Action], bool]


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
    def web_read(self, cancelled: Callable[[], bool], filter: str = 'interactive', find: str = '', ref: str = '') -> str:
        route = self.browser()
        if find:
            result = route.act(self._action(Route.BROWSER, 'find', {'query': find}, cancelled))
        else:
            params: Dict[str, Any] = {'filter': filter if filter in ('interactive', 'all', 'visible') else 'interactive'}
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
        read = route.act(self._action(Route.BROWSER, 'read_page', {'filter': 'interactive'}, cancelled))
        self.last_web = read.text if read.ok else ''
        return self._report(result, self.last_web)

    def web_act(self, op: str, args: Mapping[str, Any], cancelled: Callable[[], bool]) -> str:
        if op not in WEB_OPS:
            raise ControlError(f'web_act value must be one of {", ".join(sorted(WEB_OPS))}.', ErrorCategory.INVALID_ARGUMENTS)
        route = self.browser()
        name = WEB_OPS[op]
        params: Dict[str, Any] = {}
        ref = str(args.get('ref', ''))
        kind, label = labels(self.last_web).get(ref, ('', ''))
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
            again = route.act(self._action(Route.BROWSER, 'read_page', {'filter': 'interactive'}, cancelled))
            if again.ok:
                self.last_web = read = again.text
        return self._report(result, read, {'target': f'{kind} "{label}"'} if label else None)

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
        return self._report(result, self._read_window(route, handle, 'interactive'), {'window': handle})

    def _read_window(self, route: Reporting, handle: int, filter: str) -> str:
        observation = route.inner.observe(f'win-{handle}', filter=filter)
        self.app_scope, self.last_app = observation.scope, observation.text
        return observation.text

    def app_read(self, window: str, filter: str, cancelled: Callable[[], bool]) -> str:
        route = self.uia()
        params: Dict[str, Any] = {'window': window, 'filter': filter or 'interactive'}
        if window.isdigit():
            params = {'handle': int(window), 'filter': filter or 'interactive'}
        result = route.act(self._action(Route.UIA, 'read_window', params, cancelled, window))
        if result.ok:
            self.app_scope, self.last_app = str(result.state.get('scope', '')), result.text
            route.subtitle = 'Windows apps · ' + (window or 'front window')
        return self._report(replace_text(result), result.text if result.ok else '', {'window': self.app_scope})

    def app_act(self, op: str, args: Mapping[str, Any], cancelled: Callable[[], bool]) -> str:
        if op not in APP_OPS:
            raise ControlError(f'app_act value must be one of {", ".join(sorted(APP_OPS))}.', ErrorCategory.INVALID_ARGUMENTS)
        route = self.uia()
        ref = str(args.get('ref', ''))
        kind, label = labels(self.last_app).get(ref, ('', ''))
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
            try:
                read = self._read_window(route, handle, 'interactive')
            except ControlError:
                read = ''
        return self._report(result, read, {'target': f'{kind} "{label}"'} if label else None)

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


def parse_args(content: str) -> Dict[str, Any]:
    if not content.strip():
        return {}
    try:
        value = json.loads(content)
    except ValueError:
        raise ControlError('content must be a JSON object.', ErrorCategory.INVALID_ARGUMENTS) from None
    if not isinstance(value, dict):
        raise ControlError('content must be a JSON object.', ErrorCategory.INVALID_ARGUMENTS)
    return value


def labels_for_tests(text: str) -> List[Tuple[str, str, str]]:
    return [(m.group(1).strip(), m.group(2), m.group(3)) for m in ROW.finditer(text)]
