"""No-model fast paths for simple PC intents on the agent-desktop backend.

"minimize / maximize / restore / close <app>" and "copy <text> to the clipboard" map straight to one
agent-desktop command, then a fresh read proves the result (window state from ``list-windows``, clipboard
from ``clipboard-get``). Closing is always graceful: the app's own save prompt stays in charge, ``--force`` is
never used. Clipboard writes ask first through Jarvis's approval card. Anything else returns None so the
normal planner handles it.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    image = target.image.lower()

    def listed() -> List[Dict[str, Any]]:
        env = run_(['list-windows'], timeout_s=15)
        return [w for w in (env.data or []) if isinstance(w, dict)] if env.ok else []

    # Window ids from the full list: hosted Store apps (Calculator) answer to their own image name here, while
    # `--app <image>` and `close-app <image>` resolve to ApplicationFrameHost and miss them. A minimized hosted
    # window then reports ApplicationFrameHost as its owner, so after acting it is followed by id (seen live).
    before = [w for w in listed() if str(w.get('app_name', '')).lower() == image or (
        str(w.get('app_name', '')).lower() == 'applicationframehost.exe' and target.store
        and str(w.get('title', '')).lower().startswith(target.name.lower()))]
    if not before:
        return None  # Not open (or not visible to agent-desktop): the planner decides what to say or do.
    ids = {str(w.get('id')) for w in before}
    for window in before:
        wid = str(window.get('id'))
        if op == 'close':  # Graceful: the window's own Close button, so the app's save prompt stays in charge.
            match_ = None
            for label in ('Close', f'Close {window.get("title", "")}'.strip()):  # Store apps: "Close Calculator"
                hit = run_(['find', '--window-id', wid, '--role', 'button', '--name', label, '--exact', '--first'],
                             timeout_s=15)
                match_ = (hit.data or {}).get("match") if hit.ok and isinstance(hit.data, dict) else None
                if match_ and match_.get('ref_id'):
                    break
            if not match_ or not match_.get('ref_id'):
                return None
            env = run_(['click', match_['ref_id']], timeout_s=20)
        else:
            env = run_([op, '--window-id', wid], timeout_s=20)
        if not env.ok and not env.may_have_acted:
            raise to_control_error(env)
        # A possibly delivered failure is never repeated: the fresh read below decides what happened.
    if op == 'close':
        run_(['wait', '--event', 'window-closed', '--window-id', str(before[0].get('id')), '--timeout', '5000'],
             timeout_s=15)
    rows = [w for w in listed() if str(w.get('id')) in ids]
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
