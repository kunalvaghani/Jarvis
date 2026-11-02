"""No-model fast paths for simple PC intents on the agent-desktop backend.

"minimize / maximize / restore / close <app>" and "copy <text> to the clipboard" map straight to one
agent-desktop command, then a fresh read proves the result (window state from ``list-windows``, clipboard
from ``clipboard-get``). Closing is always graceful: the app's own save prompt stays in charge, ``--force`` is
never used. Clipboard writes ask first through Jarvis's approval card. Anything else returns None so the
normal planner handles it.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional, Tuple

from ..types import ControlError, ErrorCategory
from . import resolver
from .runner import Runner, to_control_error

WINDOW = re.compile(r'^\s*(?:please\s+)?(?P<op>minimi[sz]e|maximi[sz]e|restore|close)\s+(?:the\s+)?(?P<app>[\w .+-]{2,40}?)'
                    r'(?:\s+(?:app|window))?\s*[.!]?\s*$', re.I)
CLIP = re.compile(r'^\s*(?:please\s+)?copy\s+(?:the\s+text\s+)?["\']?(?P<text>[^"\']{1,500}?)["\']?\s+to\s+(?:the\s+|my\s+)?'
                  r'clipboard\s*[.!]?\s*$', re.I)


def match(goal: str) -> Optional[Tuple[str, str]]:
    found = WINDOW.match(goal or '')
    if found:
        return found.group('op').lower().replace('mise', 'mize'), found.group('app').strip()
    found = CLIP.match(goal or '')
    if found:
        return 'clipboard', found.group('text')
    return None


def run(goal: str, approve: Callable[[str, str], bool], runner: Optional[Runner] = None) -> Optional[str]:
    """A verified answer, or None when the goal is not a fast path. Raises ControlError on a failed step."""
    found = match(goal)
    if found is None:
        return None
    op, value = found
    run_ = runner or Runner()
    if op == 'clipboard':
        if not approve('clipboard', f'Put "{value[:80]}" on the clipboard'):
            raise ControlError('The clipboard was not changed (not approved).', ErrorCategory.APPROVAL_DENIED)
        env = run_(['clipboard-set', value], timeout_s=15)
        if not env.ok:
            raise to_control_error(env)
        back = run_(['clipboard-get', '--format', 'text'], timeout_s=15)
        text = str((back.data or {}).get('text', '')) if isinstance(back.data, dict) else ''
        if text != value:
            raise ControlError('The clipboard does not hold the text after copying.', ErrorCategory.VERIFICATION_FAILED,
                               executed=True)
        return f'Copied "{value[:80]}" to the clipboard (checked by reading it back).'
    target = resolver.resolve(value)
    if target is None or not target.image:
        return None  # Not a known app: let the planner work out what was meant.
    image = target.image
    command = {'minimize': ['minimize', '--app', image], 'maximize': ['maximize', '--app', image],
               'restore': ['restore', '--app', image], 'close': ['close-app', image]}[op]
    env = run_(command, timeout_s=30)
    if not env.ok:
        if env.error is not None and env.error.code == 'APP_NOT_FOUND':
            return f'{target.name} is not open.'
        raise to_control_error(env)
    windows = run_(['list-windows', '--app', image], timeout_s=15)
    rows = [w for w in (windows.data or []) if isinstance(w, dict)] if windows.ok else []
    if op == 'close':
        ok = not rows
    elif op == 'minimize':
        ok = bool(rows) and all(w.get('minimized') for w in rows)
    else:
        ok = bool(rows) and not any(w.get('minimized') for w in rows)
    if not ok:
        raise ControlError(f'{op} {target.name}: the window state did not change as expected.',
                           ErrorCategory.VERIFICATION_FAILED, executed=True)
    done = {'minimize': 'Minimized', 'maximize': 'Maximized', 'restore': 'Restored', 'close': 'Closed'}[op]
    return f'{done} {target.name} (checked: the window list shows it).'
