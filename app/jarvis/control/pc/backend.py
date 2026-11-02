"""AgentDesktopExecutor: the UI Automation route re-implemented on agent-desktop, same contract as UIAExecutor.

ControlService talks to it exactly as to ``routes.uia.UIAExecutor``: ``observe('win-<handle>')`` returns lines
``Kind "name" [ref] extras`` and ``act`` takes the same action names (launch, read_window, click/invoke,
set_value, toggle, select, expand, collapse, scroll, focus, type, key, close_window, focus_window,
list_windows). Window handles are agent-desktop window ids without the ``w-`` prefix (both are the HWND).

Rules (docs/control/ADAPTER_PLAN.md):
- Semantic headless actions first. Physical input (``--headed``: type, key, focus) passes ``HeadedGate``:
  ``allow`` (the user permitted it, e.g. benchmarks), ``ask`` (one approval per window), or ``deny``.
  A headless failure is never retried headed. ``--force`` is never used: blocked shortcuts stay blocked.
- Retry only when the envelope says ``not_delivered`` + ``retry: safe`` (stale refs: one fresh snapshot, the
  same element by role and name, one retry). Any other failure after delivery is reported, never repeated.
- An action is verified only by a delivered_verified disposition or a fresh read; ``ok`` alone proves nothing.
- Snapshots and window text stay on this PC; nothing here sends them anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..executor import Health, RouteExecutor
from ..policy import Policy
from ..types import Action, ActionResult, ControlError, ErrorCategory, Observation, Ref as JarvisRef, Route
from . import resolver
from .runner import REFRESHABLE, Envelope, Ref, Runner, Snapshot, to_control_error

KINDS = {'textfield': 'Edit', 'button': 'Button', 'tab': 'TabItem', 'checkbox': 'CheckBox', 'combobox': 'ComboBox',
         'link': 'Hyperlink', 'menuitem': 'MenuItem', 'listitem': 'ListItem', 'radiobutton': 'RadioButton',
         'slider': 'Slider', 'treeitem': 'TreeItem', 'text': 'Text', 'statictext': 'Text', 'group': 'Group',
         'window': 'Window', 'scrollarea': 'Pane', 'list': 'List', 'menu': 'Menu', 'menubar': 'MenuBar',
         'toolbar': 'ToolBar', 'image': 'Image', 'cell': 'DataItem', 'table': 'DataGrid', 'tree': 'Tree',
         'disclosure': 'TreeItem', 'splitbutton': 'SplitButton', 'document': 'Document', 'spinbutton': 'Spinner'}
SECRET_STATES = frozenset({'password', 'protected', 'secure'})
HEADED_OPS = frozenset({'type', 'key', 'focus'})
WRITE_COMMANDS = frozenset({'click', 'set-value', 'toggle', 'check', 'uncheck', 'select', 'expand', 'collapse', 'scroll',
                            'type', 'press', 'focus', 'focus-window', 'close-app', 'launch', 'clear', 'scroll-to'})


def kind_of(node: Dict[str, Any]) -> str:
    described = str(node.get('role_description') or '').strip()
    if described:
        joined = ''.join(w.capitalize() for w in described.replace('_', ' ').split())
        if joined in ('TabItem', 'Document', 'Pane', 'Edit', 'Button', 'CheckBox', 'ListItem', 'MenuItem', 'Hyperlink',
                      'ComboBox', 'RadioButton', 'Slider', 'TreeItem', 'Text', 'Group', 'Window', 'SplitButton',
                      'DataItem', 'Spinner', 'Image', 'MenuBar', 'Menu', 'ToolBar', 'List', 'Tree', 'Tab'):
            return joined
    return KINDS.get(str(node.get('role') or '').lower(), 'Custom')


@dataclass
class HeadedGate:
    """Physical input (cursor/keyboard/foreground) is a separate permission from semantic UI Automation."""
    mode: str = 'ask'                                  # allow | ask | deny
    confirm: Optional[Callable[[str], bool]] = None    # asks the user, e.g. through the island card
    granted: Set[str] = field(default_factory=set)

    def require(self, scope: str, why: str) -> None:
        if self.mode == 'allow' or scope in self.granted:
            return
        if self.mode == 'ask' and self.confirm is not None:
            try:
                ok = self.confirm(f'Use the real keyboard and mouse in this window ({why})?') is True
            except Exception:
                ok = False
            if ok:
                self.granted.add(scope)
                return
        raise ControlError(f'{why} needs the real keyboard or mouse, which was not permitted; nothing was sent. '
                           'Prefer set_value for text.', ErrorCategory.APPROVAL_DENIED)


@dataclass
class _Scope:
    handle: int
    snapshot_id: str = ''
    app: str = ''  # process image the window belonged to, to find its replacement window
    by_ref: Dict[str, Ref] = field(default_factory=dict)        # Jarvis ref -> agent-desktop ref
    identity: Dict[Tuple[str, str, int], str] = field(default_factory=dict)  # (role, name, nth) -> Jarvis ref
    counter: int = 0


class AgentDesktopExecutor(RouteExecutor):
    route = Route.UIA  # Same route identity: ControlService and the planner need no change.

    def __init__(self, policy: Policy, runner: Optional[Runner] = None, headed: Optional[HeadedGate] = None,
                 settle_ms: int = 8000, popen: Callable[..., Any] = subprocess.Popen) -> None:
        self.policy, self.run = policy, runner or Runner()
        self.headed = headed or HeadedGate()
        self.settle_ms, self._popen = settle_ms, popen
        self.scopes: Dict[str, _Scope] = {}
        self.launched: List[int] = []
        self._lock = threading.RLock()

    # Lifecycle ----------------------------------------------------------------------
    def health_check(self) -> Health:
        if not self.run.available():
            return Health(False, f'agent-desktop missing at {self.run.binary}')
        env = self.run(['status'], timeout_s=10)
        granted = isinstance(env.data, dict) and env.data.get('permissions', {}).get('accessibility', {}).get('state') == 'granted'
        return Health(env.ok and granted, 'agent-desktop ready' if env.ok and granted else 'accessibility unavailable')

    def cancel(self) -> None:
        return None  # Each command is a short process with its own deadline.

    def close(self) -> None:
        if self.run.session:
            try:
                self.run(['session', 'end', self.run.session], timeout_s=10)
            except ControlError:
                pass

    def start_session(self, task_id: str) -> None:
        """One traced session per task: the trace (redacted by agent-desktop) is the verifier's evidence."""
        name = f'jarvis-{task_id or "task"}'[:120]
        env = self.run(['session', 'start', '--name', name], timeout_s=10)
        if env.ok and isinstance(env.data, dict) and env.data.get('session_id'):
            self.close()
            self.run.session = str(env.data['session_id'])

    # Reading --------------------------------------------------------------------------
    def _check(self, env: Envelope) -> Envelope:
        if not env.ok:
            raise to_control_error(env)
        return env

    def windows(self, app: str = '') -> List[Dict[str, Any]]:
        env = self._check(self.run(['list-windows'] + (['--app', app] if app else []), timeout_s=15))
        return [w for w in (env.data or []) if isinstance(w, dict)]

    def read_window(self, handle: int, filter: str = 'interactive') -> Observation:
        if filter not in ('interactive', 'all'):
            raise ControlError('filter must be interactive or all.', ErrorCategory.INVALID_ARGUMENTS)
        args = ['snapshot', '--window-id', f'w-{handle}', '--compact', '--timeout-ms', str(self.settle_ms)]
        if filter == 'interactive':
            args.append('-i')
        env = self.run(args, timeout_s=self.settle_ms / 1000 + 15)
        if not env.ok and env.error is not None and env.error.code == 'WINDOW_NOT_FOUND':
            raise ControlError('The window was closed.', ErrorCategory.STALE_REF)
        snap = Snapshot.model_validate(self._check(env).data)
        scope = f'win-{handle}'
        with self._lock:
            state = self.scopes.setdefault(scope, _Scope(handle))
            state.snapshot_id, state.by_ref = snap.snapshot_id, {}
            state.app = state.app or snap.app
            lines: List[str] = []
            refs: List[JarvisRef] = []
            seen: Dict[Tuple[str, str], int] = {}

            def visit(node: Dict[str, Any], indent: int) -> None:
                if len(lines) > 4000:
                    return
                states = [str(s) for s in node.get('states') or ()]
                kind, name = kind_of(node), str(node.get('name') or '').strip()
                shown = indent
                if 'offscreen' not in states and (node.get('ref_id') or (filter == 'all' and name)):
                    if node.get('ref_id'):
                        key = (str(node.get('role')), name)
                        nth = seen.get(key, 0)
                        seen[key] = nth + 1
                        ident = (key[0], key[1], nth)
                        jref = state.identity.get(ident)
                        if jref is None:
                            state.counter += 1
                            jref = f'd{state.counter}'
                            state.identity[ident] = jref
                        state.by_ref[jref] = Ref.model_validate(node)
                        refs.append(JarvisRef(jref, Route.UIA, scope, 0))
                        lines.append(f'{"  " * indent}{kind} "{name[:150]}" [{jref}]' + self._extras(node, states))
                    else:
                        lines.append(f'{"  " * indent}{kind} "{name[:150]}"')
                    shown = indent + 1
                for child in node.get('children') or ():
                    if isinstance(child, dict):
                        visit(child, shown)
            visit(snap.tree, 0)
        warnings = [] if snap.complete else ['The window was read only partly (it was still loading); read it again.']
        title = str((snap.window or {}).get('title', ''))
        return Observation(Route.UIA, scope, '\n'.join(lines), tuple(refs),
                           state={'title': title, 'handle': handle, 'warnings': warnings, 'complete': snap.complete,
                                  'snapshot_id': snap.snapshot_id, 'app': snap.app})

    @staticmethod
    def _extras(node: Dict[str, Any], states: List[str]) -> str:
        extras = []
        secret = bool(SECRET_STATES & set(states))
        value = node.get('value')
        if value not in (None, '') and not secret:
            extras.append(f'value={str(value)[:120]!r}')
        if 'checked' in states:
            extras.append('on')
        if 'selected' in states:
            extras.append('selected')
        if 'disabled' in states:
            extras.append('disabled')
        if 'focused' in states:
            extras.append('focused')
        if secret:
            extras.append('password')
        return (' ' + ' '.join(extras)) if extras else ''

    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        if scope and scope.startswith('win-'):
            return self.read_window(int(scope[4:]), options.get('filter', 'interactive'))
        handle = options.get('handle') or self._find_window(str(options.get('window', '')))
        return self.read_window(int(handle), options.get('filter', 'interactive'))

    def _find_window(self, query: str) -> int:
        rows = self.windows()
        if query:
            rows = [w for w in rows if query.lower() in str(w.get('title', '')).lower()
                    or query.lower() in str(w.get('app_name', '')).lower()]
        focused = [w for w in rows if w.get('is_focused')]
        chosen = (focused or rows)[:1]
        if not chosen:
            raise ControlError(f'No window matches {query!r}.', ErrorCategory.TARGET_NOT_FOUND)
        return int(str(chosen[0]['id'])[2:])

    def probe(self, what: str, **params: Any) -> Any:
        if what == 'window_title':
            handle = int(params['handle'])
            for w in self.windows():
                if str(w.get('id')) == f'w-{handle}':
                    return str(w.get('title', ''))
            raise ControlError('The window was closed.', ErrorCategory.STALE_REF)
        if what == 'windows':
            return [str(w.get('title', '')) for w in self.windows()]
        ref = self._ref(str(params.get('scope', '')), str(params.get('ref', '')))
        prop = {'value': 'value', 'name': 'title'}.get(what)
        if prop:
            env = self._check(self.run(['get', ref.ref_id, '--property', prop], timeout_s=15))
            return (env.data or {}).get('value') if isinstance(env.data, dict) else env.data
        flag = {'toggle': 'checked', 'selected': 'selected', 'expanded': 'expanded'}.get(what)
        if flag:
            env = self._check(self.run(['is', ref.ref_id, '--property', flag], timeout_s=15))
            result = (env.data or {}).get('result') if isinstance(env.data, dict) else None
            return int(bool(result)) if what != 'selected' else bool(result)
        raise ControlError(f'Unknown probe {what!r}.', ErrorCategory.UNSUPPORTED)

    # Acting ---------------------------------------------------------------------------
    def _ref(self, scope: str, jref: str) -> Ref:
        state = self.scopes.get(scope)
        if state is None or jref not in state.by_ref:
            raise ControlError(f'{jref} is stale or not found. Re-read the window to get fresh references.',
                               ErrorCategory.STALE_REF)
        return state.by_ref[jref]

    def _refresh(self, scope: str, jref: str) -> Optional[Ref]:
        """After STALE_REF/AMBIGUOUS_TARGET: re-read and find the same element (same role, name and position)."""
        state = self.scopes.get(scope)
        if state is None:
            return None
        ident = next((i for i, r in state.identity.items() if r == jref), None)
        self.read_window(state.handle, 'interactive')
        if ident is None or state.identity.get(ident) != jref:
            return None
        return state.by_ref.get(jref)

    def _ref_action(self, scope: str, jref: str, command: List[str], headed: bool = False) -> Envelope:
        """Run a ref action; refresh a stale ref once, and retry only if nothing was delivered."""
        ref = self._ref(scope, jref)
        env = self.run([command[0], ref.ref_id] + command[1:], headed=headed, timeout_s=30)
        if not env.ok and env.error is not None and env.error.code in REFRESHABLE and \
                env.error.disposition.safe_to_retry:
            fresh = self._refresh(scope, jref)
            if fresh is not None:
                env = self.run([command[0], fresh.ref_id] + command[1:], headed=headed, timeout_s=30)
        return env

    def act(self, action: Action) -> ActionResult:
        started = time.perf_counter()
        try:
            with self._lock:
                result = self._dispatch(action)
        except ControlError as error:
            return ActionResult.failure(action, error, timings_ms={'total': (time.perf_counter() - started) * 1000})
        except Exception as error:  # Unknown failure after a command may have run: uncertain, never success.
            return ActionResult(action.action_id, False, Route.UIA, text=f'{type(error).__name__}: {error}'[:300],
                                executed=True, error_category=ErrorCategory.UNCERTAIN)
        return result

    def _done(self, action: Action, text: str, env: Optional[Envelope] = None, executed: bool = True,
              verified: Optional[bool] = None, evidence: str = '', **state: Any) -> ActionResult:
        if env is not None:
            executed = env.delivered or executed
            verified = env.verified if verified is None else verified
            evidence = evidence or (f'agent-desktop: {env.disposition.delivery}' if env.disposition else '')
        return ActionResult(action.action_id, True, Route.UIA, text=text, executed=executed,
                            verified=bool(verified), evidence=evidence, state=state)

    def _dispatch(self, action: Action) -> ActionResult:
        name, p = action.name, action.params
        action.cancel.raise_if_cancelled()
        if action.task_id and not self.run.session:
            self.start_session(action.task_id)
        if name == 'launch':
            handle, title = self.launch(str(p['app']), str(p.get('path', '')), action.timeout_s)
            return self._done(action, f'Opened {title}', verified=True, evidence='window appeared', handle=handle,
                              title=title)
        if name == 'list_windows':
            rows = [f'{str(w.get("title", ""))[:80]} | {w.get("app_name", "")} | handle {str(w.get("id", ""))[2:]}'
                    for w in self.windows()]
            return self._done(action, '\n'.join(rows), executed=False, verified=True)
        if name in ('click_named', 'menu_path'):
            handle = self._live_handle(int(p.get('handle') or action.context.window or 0))
            if name == 'click_named':
                return self._click_named(action, handle, str(p['name']), str(p.get('role', '')))
            return self._menu_path(action, handle, [str(n) for n in p['names']])
        if name in ('read_window', 'focus_window', 'type', 'key', 'close_window'):
            handle = int(p.get('handle') or action.context.window or self._find_window(str(p.get('window', ''))))
            handle = self._live_handle(handle)
            scope = f'win-{handle}'
            if name == 'read_window':
                obs = self.read_window(handle, str(p.get('filter', 'interactive')))
                return self._done(action, obs.text, executed=False, verified=True, scope=obs.scope,
                                  warnings=obs.state['warnings'])
            self._title_guard(handle, str(p.get('expect_title', '')))
            if name == 'focus_window':
                env = self._check(self.run(['focus-window', '--window-id', f'w-{handle}'], timeout_s=15))
                return self._done(action, 'Window focused', env, executed=False, verified=True)
            if name == 'close_window':
                return self._close_window(action, handle)
            if name == 'type':
                return self._type(action, handle, str(p['text']))
            self.headed.require(scope, f'pressing {p["text"]}')
            env = self._press(str(p['text']), handle)
            if not env.ok:
                raise to_control_error(env)  # A blocked shortcut stays blocked: --force is never used.
            return self._done(action, f'key sent: {p["text"]}', env)
        scope = str(p.get('scope') or (f'win-{action.context.window}' if action.context.window else ''))
        jref = str(p.get('ref', ''))
        if not scope or not jref:
            raise ControlError('This action needs a ref from a window read.', ErrorCategory.INVALID_ARGUMENTS)
        target = self._ref(scope, jref)
        label = f'{kind_of(target.model_dump())} "{target.name[:80]}"'
        if 'disabled' in target.states:
            raise ControlError(f'{label} is disabled.', ErrorCategory.NOT_ACTIONABLE)
        if name in ('click', 'invoke'):
            env = self._ref_action(scope, jref, ['click'])
        elif name == 'set_value':
            if SECRET_STATES & set(target.states):
                raise ControlError('Password fields are never filled automatically.', ErrorCategory.POLICY_DENIED)
            env = self._ref_action(scope, jref, ['set-value', str(p['value'])])
        elif name == 'toggle':
            desired = p.get('state')
            command = ['toggle'] if desired is None else (['check'] if int(desired) == 1 else ['uncheck'])
            env = self._ref_action(scope, jref, command)
        elif name in ('select', 'expand', 'collapse'):
            env = self._ref_action(scope, jref, ['click' if name == 'select' else name])
        elif name == 'scroll':
            direction = str(p.get('direction', 'down'))
            if direction not in ('up', 'down', 'left', 'right'):
                raise ControlError('scroll direction must be up, down, left or right.', ErrorCategory.INVALID_ARGUMENTS)
            env = self._ref_action(scope, jref, ['scroll', '--direction', direction, '--amount', '3'])
        elif name == 'focus':
            self.headed.require(scope, 'moving keyboard focus')
            env = self._ref_action(scope, jref, ['focus'], headed=True)
        else:
            raise ControlError(f'Unsupported action {name!r}.', ErrorCategory.UNSUPPORTED)
        if not env.ok:
            raise to_control_error(env)
        surfaces = (env.data or {}).get('surfaces') if isinstance(env.data, dict) else None
        verb = {'click': 'Invoked', 'invoke': 'Invoked', 'set_value': 'Set', 'toggle': 'Toggled'}.get(name, name)
        return self._done(action, f'{verb} {label}', env, **({'surfaces': surfaces} if surfaces else {}))

    def _type(self, action: Action, handle: int, text: str) -> ActionResult:
        """Typing into the window's editor: set-value when the field is empty (headless, verified), else headed."""
        found = self._check(self.run(['find', '--window-id', f'w-{handle}', '--role', 'textfield', '--first'],
                                     timeout_s=20))
        match = (found.data or {}).get('match') if isinstance(found.data, dict) else None
        if not match or not match.get('ref_id'):
            return self._keystrokes(action, handle, text)  # e.g. Calculator: typing is key presses, as legacy did
        if SECRET_STATES & set(match.get('states') or ()):
            raise ControlError('Password fields are never filled automatically.', ErrorCategory.POLICY_DENIED)
        if not str(match.get('value') or ''):
            env = self.run(['set-value', match['ref_id'], text], timeout_s=30)
            if env.ok:
                return self._done(action, f'typed into "{str(match.get("name", ""))[:60]}"', env)
            if env.may_have_acted:
                raise to_control_error(env)
        self.headed.require(f'win-{handle}', 'typing with the keyboard')
        env = self.run(['type', match['ref_id'], text], headed=True, timeout_s=30 + len(text) * 0.05)
        if not env.ok:
            raise to_control_error(env)
        return self._done(action, f'type sent to "{str(match.get("name", ""))[:60]}"', env)

    KEYS = {' ': 'space', '\n': 'return', '=': 'return'}  # agent-desktop key names: a-z, 0-9 and named keys

    BUTTONS = {**{str(d): n for d, n in enumerate(('Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                                                  'Eight', 'Nine'))},
               '+': 'Plus', '-': 'Minus', '*': 'Multiply by', 'x': 'Multiply by', '/': 'Divide by', '=': 'Equals',
               '.': 'Decimal separator', '%': 'Percent'}

    def _buttons(self, handle: int, text: str) -> Optional[List[str]]:
        """Refs of the window's own buttons for each character (Calculator), or None if any is missing."""
        env = self.run(['snapshot', '--window-id', f'w-{handle}', '-i', '--compact', '--timeout-ms', str(self.settle_ms)],
                       timeout_s=self.settle_ms / 1000 + 15)
        if not env.ok:
            return None
        named = {r.name.strip().lower(): r.ref_id for r in Snapshot.model_validate(env.data).refs()
                 if r.role == 'button' and 'offscreen' not in r.states}
        refs = []
        for char in text.replace(' ', ''):
            name = self.BUTTONS.get(char.lower())
            if name is None or name.lower() not in named:
                return None
            refs.append(named[name.lower()])
        return refs

    def _keystrokes(self, action: Action, handle: int, text: str) -> ActionResult:
        """A window with no text field (Calculator): click its own buttons for each character (headless, works in
        the background); only if it has no such buttons, send key presses (physical, behind the headed gate; one
        key at a time, never retried after a delivered key)."""
        buttons = self._buttons(handle, text)
        if buttons:
            for count, ref in enumerate(buttons):
                action.cancel.raise_if_cancelled()
                env = self.run(['click', ref], timeout_s=20)
                if not env.ok:
                    error = to_control_error(env)
                    error.executed = error.executed or count > 0
                    raise error
            return self._done(action, f'clicked {len(buttons)} buttons for {text!r}', executed=True, verified=False,
                              evidence='buttons pressed headless; read the window to confirm')
        keys = []
        for char in text:
            if char.isalnum() and char.isascii():
                keys.append(char.lower() if not char.isupper() else 'shift+' + char.lower())
            elif char in self.KEYS:
                keys.append(self.KEYS[char])
            else:
                raise ControlError(f'Cannot type {char!r} as a key press; use set_value on a field.',
                                   ErrorCategory.INVALID_ARGUMENTS)
        if len(keys) > 200:
            raise ControlError('Too much text to send as key presses.', ErrorCategory.INVALID_ARGUMENTS)
        self.headed.require(f'win-{handle}', 'typing with the keyboard')
        sent = 0
        for key in keys:
            action.cancel.raise_if_cancelled()
            env = self._press(key, handle)
            if not env.ok:
                error = to_control_error(env)
                error.executed = error.executed or sent > 0
                raise error
            sent += 1
        return self._done(action, f'typed {len(keys)} keys', executed=True, verified=False,
                          evidence='key presses delivered; read the window to confirm')

    def _find(self, handle: int, name: str, role: str = '', surface: str = '') -> Optional[str]:
        args = ['find', '--name', name, '--exact', '--first']
        if surface:
            app = str(getattr(self.scopes.get(f'win-{handle}'), 'app', '') or '')
            args += ['--surface', surface] + (['--app', app] if app else [])
        else:
            args += ['--window-id', f'w-{handle}']
        if role:
            args += ['--role', role]
        env = self.run(args, timeout_s=15)
        match = (env.data or {}).get('match') if env.ok and isinstance(env.data, dict) else None
        return str(match['ref_id']) if match and match.get('ref_id') else None

    def _click_named(self, action: Action, handle: int, name: str, role: str = '') -> ActionResult:
        """Activate a control by its exact name without moving the mouse (e.g. Notepad's "Add New Tab")."""
        ref = self._find(handle, name, role)
        if ref is None:
            raise ControlError(f'No control named "{name}" in this window.', ErrorCategory.TARGET_NOT_FOUND)
        env = self.run(['click', ref], timeout_s=20)
        if not env.ok:
            raise to_control_error(env)
        return self._done(action, f'Invoked "{name}"', env)

    def _menu_path(self, action: Action, handle: int, names: List[str]) -> ActionResult:
        """File > Save as, headless: the first item is in the window, the rest in the menu it opens."""
        if not names:
            raise ControlError('menu_path needs names.', ErrorCategory.INVALID_ARGUMENTS)
        ref = self._find(handle, names[0], 'menuitem') or self._find(handle, names[0])
        if ref is None:
            raise ControlError(f'No menu "{names[0]}" in this window.', ErrorCategory.TARGET_NOT_FOUND)
        env = self.run(['click', ref], timeout_s=20)
        if not env.ok:
            raise to_control_error(env)
        for count, name in enumerate(names[1:], 1):
            ref = None
            deadline = time.monotonic() + 4
            while ref is None and time.monotonic() < deadline:
                ref = self._find(handle, name, surface='menu') or self._find(handle, name)
                if ref is None:
                    time.sleep(.2)
            if ref is None:
                raise ControlError(f'Menu item "{name}" did not appear; the menu may still be open.',
                                   ErrorCategory.TARGET_NOT_FOUND, executed=True)
            env = self.run(['click', ref], timeout_s=20)
            if not env.ok:
                error = to_control_error(env)
                error.executed = True
                raise error
        return self._done(action, 'Chose ' + ' > '.join(names), env)

    def _live_handle(self, handle: int) -> int:
        """The window may have been replaced (Windows 11 Notepad makes a new window for a new tab). If the handle is
        gone, use the same app's current window: nothing was sent to the old one, so this is safe."""
        try:
            rows = self.windows()
        except ControlError:
            return handle  # cannot tell: keep the handle; the action itself reports a missing window
        if not rows or any(str(w.get('id')) == f'w-{handle}' for w in rows):
            return handle
        known = self.scopes.get(f'win-{handle}')
        app = str(getattr(known, 'app', '') or '')
        same = [w for w in rows if app and str(w.get('app_name', '')).lower() == app.lower()]
        focused = [w for w in same if w.get('is_focused')]
        chosen = (focused or same)[:1]
        if not chosen:
            raise ControlError('The window was closed.', ErrorCategory.STALE_REF)
        new = int(str(chosen[0]['id'])[2:])
        if known is not None:
            self.scopes[f'win-{new}'] = known
            known.handle = new
        return new

    def _press(self, key: str, handle: int) -> Envelope:
        """Physical key press into one window. `press --window-id` resolves the app by process name, which misses
        hosted Store apps (Calculator); so the window is focused by its id and the key goes to the foreground."""
        env = self.run(['press', key, '--window-id', f'w-{handle}'], headed=True, timeout_s=20)
        if env.ok or env.error is None or env.error.code != 'APP_NOT_FOUND' or env.may_have_acted:
            return env
        focused = self.run(['focus-window', '--window-id', f'w-{handle}'], timeout_s=15)
        if not focused.ok:
            return focused
        return self.run(['press', key], headed=True, timeout_s=20)

    def _close_window(self, action: Action, handle: int) -> ActionResult:
        match = None
        title = str(self.probe('window_title', handle=handle))
        for label in ('Close', f'Close {title}'.strip()):  # Store apps name it "Close Calculator"
            found = self.run(['find', '--window-id', f'w-{handle}', '--role', 'button', '--name', label, '--exact',
                              '--first'], timeout_s=15)
            match = (found.data or {}).get('match') if found.ok and isinstance(found.data, dict) else None
            if match and match.get('ref_id'):
                break
        if not match or not match.get('ref_id'):
            raise ControlError('This window has no Close button to press.', ErrorCategory.UNSUPPORTED)
        env = self.run(['click', match['ref_id']], timeout_s=20)
        if not env.ok:
            raise to_control_error(env)
        return self._done(action, 'Asked the window to close', env)

    def _title_guard(self, handle: int, expected: str) -> None:
        if not expected:
            return
        title = str(self.probe('window_title', handle=handle))
        if expected.lower() not in title.lower():
            raise ControlError(f'The window is now "{title[:60]}", not "{expected[:60]}". Nothing was sent.',
                               ErrorCategory.FOCUS_LOST)

    def launch(self, app: str, path: str = '', timeout_s: float = 20.0) -> Tuple[int, str]:
        target = resolver.resolve(app)
        if target is None:
            near = resolver.candidates(app)
            raise ControlError(f'No installed app matches {app!r}' + (f'; did you mean {", ".join(near)}?' if near else '.'),
                               ErrorCategory.TARGET_NOT_FOUND)
        image = target.image or target.target
        self.policy.check_app(image)
        argument = str(self.policy.confine(path)) if path else ''
        existing = self.windows(target.image) if target.image else []
        before = {str(w.get('id')) for w in existing}
        attached: Optional[Dict[str, Any]] = None
        if existing and not argument:
            # Already open and no file to open: use its window. `launch` would only attach after waiting out its
            # whole timeout (15 s measured on Notepad).
            chosen = next((w for w in existing if w.get('is_focused')), existing[0])
            return int(str(chosen['id'])[2:]), str(chosen.get('title', ''))
        if target.store:
            # Store apps have no exe path; the shell starts them, agent-desktop then finds the window.
            self._popen(['explorer.exe', *target.args], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        else:
            # Bound the launch below our own process deadline (its default is 30 s): the window is found below.
            args = ['launch', target.target, '--timeout', str(int(min(timeout_s, 15) * 1000))] + \
                ([f'--arg={argument}'] if argument else [])
            env = self.run(args, timeout_s=timeout_s + 10)
            if not env.ok and not (env.error is not None and env.error.code == 'TIMEOUT'):
                raise to_control_error(env)  # a launch TIMEOUT means "no window yet": look for it below
            window = (env.data or {}).get('window') if env.ok and isinstance(env.data, dict) else None
            if window and window.get('id'):
                if str(window['id']) not in before:
                    self.launched.append(int(str(window['id'])[2:]))
                    return int(str(window['id'])[2:]), str(window.get('title', ''))
                attached = window
        attached = attached or next((w for w in existing if w.get('is_focused')), existing[0] if existing else None)
        # A running single-window app (e.g. Windows 11 Notepad) reuses its window: wait briefly for a new one,
        # then use the one it attached to, as the legacy route does.
        deadline = time.monotonic() + (min(4.0, timeout_s) if attached else timeout_s)
        while time.monotonic() < deadline:
            rows = [w for w in self.windows(target.image) if str(w.get('id')) not in before and w.get('visible', True)]
            if rows:
                self.launched.append(int(str(rows[0]['id'])[2:]))
                return int(str(rows[0]['id'])[2:]), str(rows[0].get('title', ''))
            self.run(['wait', '--event', 'window-opened', '--app', target.image or app, '--timeout', '1500'],
                     timeout_s=10)
        if attached is not None:
            return int(str(attached['id'])[2:]), str(attached.get('title', ''))
        raise ControlError(f'{target.name} did not show a window within {timeout_s:.0f} s.', ErrorCategory.TIMEOUT)
