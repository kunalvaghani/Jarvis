"""Run the agent-desktop CLI and parse its JSON envelope (v2.5) into typed models.

- Arguments always go as a list: never through a shell, where a bare ``@ref`` is PowerShell splatting.
- Each command prints one envelope ``{version, ok, command, data | error}``. Errors carry ``code``,
  ``disposition {delivery, retry}``, ``suggestion`` and optional ``recovery``/``details``.
- Only ``delivery == not_delivered`` with ``retry == safe`` may be retried. Any other delivery may have landed:
  the caller must re-read the state and decide from that (``Envelope.may_have_acted``).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from ..types import ControlError, ErrorCategory

APP = Path(__file__).resolve().parents[3]
VERSION = '1.0.2'
DEFAULT_BINARY = APP / '.jarvis-runtime' / 'tools' / 'control-backends' / f'agent-desktop-{VERSION}' / 'agent-desktop.exe'
Delivery = Literal['delivered_verified', 'delivered_unverified', 'not_delivered']


class Disposition(BaseModel):
    model_config = ConfigDict(extra='allow')
    delivery: Delivery = 'not_delivered'
    retry: str = 'unsafe'

    @property
    def safe_to_retry(self) -> bool:
        return self.delivery == 'not_delivered' and self.retry == 'safe'


class AgentDesktopError(BaseModel):
    model_config = ConfigDict(extra='allow')
    code: str
    message: str = ''
    suggestion: str = ''
    disposition: Disposition = Field(default_factory=Disposition)
    details: Dict[str, Any] = Field(default_factory=dict)
    recovery: Dict[str, Any] = Field(default_factory=dict)


class Envelope(BaseModel):
    model_config = ConfigDict(extra='allow')
    version: str = ''
    ok: bool
    command: str = ''
    data: Any = None
    error: Optional[AgentDesktopError] = None

    @property
    def disposition(self) -> Optional[Disposition]:
        if self.error is not None:
            return self.error.disposition
        if isinstance(self.data, dict) and isinstance(self.data.get('disposition'), dict):
            return Disposition.model_validate(self.data['disposition'])
        return None

    @property
    def delivered(self) -> bool:
        d = self.disposition
        return d is not None and d.delivery != 'not_delivered'

    @property
    def verified(self) -> bool:
        d = self.disposition
        return d is not None and d.delivery == 'delivered_verified'

    @property
    def may_have_acted(self) -> bool:
        """True unless the tool proved nothing was delivered: never repeat such an action blindly."""
        d = self.disposition
        return d is None or d.delivery != 'not_delivered'


class Ref(BaseModel):
    """One addressable element of a snapshot. ``ref_id`` is qualified: ``@<snapshot_id>:e<N>``."""
    model_config = ConfigDict(extra='allow')
    ref_id: str
    role: str = ''
    name: str = ''
    value: Optional[str] = None
    states: List[str] = Field(default_factory=list)
    role_description: str = ''
    available_actions: List[str] = Field(default_factory=list)


class Snapshot(BaseModel):
    model_config = ConfigDict(extra='allow')
    snapshot_id: str
    app: str = ''
    complete: bool = True
    ref_count: int = 0
    window: Dict[str, Any] = Field(default_factory=dict)
    tree: Dict[str, Any] = Field(default_factory=dict)

    def refs(self) -> List[Ref]:
        found: List[Ref] = []

        def visit(node: Dict[str, Any]) -> None:
            if node.get('ref_id'):
                found.append(Ref.model_validate(node))
            for child in node.get('children') or ():
                if isinstance(child, dict):
                    visit(child)
        visit(self.tree)
        return found


# error.code -> Jarvis category. "executed" is decided from the disposition, not from the code.
CATEGORIES: Dict[str, ErrorCategory] = {
    'PERM_DENIED': ErrorCategory.ELEVATED_TARGET, 'ELEMENT_NOT_FOUND': ErrorCategory.TARGET_NOT_FOUND,
    'STALE_REF': ErrorCategory.STALE_REF, 'AMBIGUOUS_TARGET': ErrorCategory.STALE_REF,
    'SNAPSHOT_NOT_FOUND': ErrorCategory.STALE_REF, 'APP_NOT_FOUND': ErrorCategory.TARGET_NOT_FOUND,
    'WINDOW_NOT_FOUND': ErrorCategory.TARGET_NOT_FOUND, 'ACTION_FAILED': ErrorCategory.VERIFICATION_FAILED,
    'ACTION_NOT_SUPPORTED': ErrorCategory.UNSUPPORTED, 'POLICY_DENIED': ErrorCategory.POLICY_DENIED,
    'APP_UNRESPONSIVE': ErrorCategory.UNCERTAIN, 'TIMEOUT': ErrorCategory.TIMEOUT,
    'INVALID_ARGS': ErrorCategory.INVALID_ARGUMENTS, 'PLATFORM_NOT_SUPPORTED': ErrorCategory.UNSUPPORTED,
    'NOTIFICATION_NOT_FOUND': ErrorCategory.TARGET_NOT_FOUND, 'INTERNAL': ErrorCategory.TOOL_ERROR,
}
REFRESHABLE = frozenset({'STALE_REF', 'AMBIGUOUS_TARGET', 'SNAPSHOT_NOT_FOUND'})
# Desktop UI actions: in a multi-agent session each carries the acting agent's id (its own cursor).
AGENT_COMMANDS = frozenset({'click', 'set-value', 'toggle', 'check', 'uncheck', 'select', 'expand', 'collapse', 'scroll',
                            'scroll-to', 'type', 'press', 'focus', 'clear', 'right-click', 'double-click', 'hover',
                            'drag', 'mouse-click', 'mouse-move', 'mouse-wheel'})


def to_control_error(envelope: Envelope) -> ControlError:
    error = envelope.error
    if error is None:
        return ControlError('agent-desktop reported failure without an error', ErrorCategory.TOOL_ERROR, True)
    category = CATEGORIES.get(error.code, ErrorCategory.TOOL_ERROR)
    if error.code == 'ACTION_FAILED' and error.details.get('kind') != 'post_action_verification' \
            and not envelope.may_have_acted:
        category = ErrorCategory.NOT_ACTIONABLE
    text = f'{error.code}: {error.message}'[:300] + (f' ({error.suggestion[:160]})' if error.suggestion else '')
    return ControlError(text, category, executed=envelope.may_have_acted)


Run = Callable[..., 'subprocess.CompletedProcess[str]']


class Runner:
    """One CLI call per command (the FFI DLL is a later optimisation; see ADAPTER_PLAN.md)."""

    def __init__(self, binary: Optional[Path] = None, session: str = '', headed: bool = False,
                 run: Run = subprocess.run, env: Optional[Dict[str, str]] = None) -> None:
        self.binary = Path(binary or os.environ.get('JARVIS_AGENT_DESKTOP') or DEFAULT_BINARY)
        self.session, self.headed, self._run = session, headed, run
        self.agent_id = ''  # multi-agent cursor session: which Jarvis task this action belongs to
        self.env = env
        self.calls: List[Dict[str, Any]] = []  # bounded per-call log (command, ms, ok, code): never payloads

    def available(self) -> bool:
        return self.binary.is_file()

    def __call__(self, args: Sequence[str], headed: bool = False, timeout_s: float = 30.0) -> Envelope:
        argv = [str(self.binary)]
        if headed:
            argv.append('--headed')
        env = self.env
        if self.session:
            argv += ['--session', self.session]
            # A multi-agent session refuses any desktop action without an agent id (launch, window ops, ...):
            # actions before a task has claimed its own cursor act as the main Jarvis agent.
            agent = self.agent_id or 'jarvis-main'
            if args and str(args[0]) in AGENT_COMMANDS:
                argv += ['--agent-id', agent]
            env = {**(self.env if self.env is not None else os.environ), 'AGENT_DESKTOP_AGENT_ID': agent}
        argv += [str(a) for a in args]
        started = time.perf_counter()
        try:
            done = self._run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace',
                             timeout=timeout_s, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except FileNotFoundError:
            raise ControlError(f'agent-desktop is not installed at {self.binary}; run '
                               'scripts/install_control_backends.ps1.', ErrorCategory.TOOL_ERROR) from None
        except subprocess.TimeoutExpired:
            # The process may have acted before it hung: uncertain, never retried blindly.
            raise ControlError(f'agent-desktop {args[0] if args else ""} timed out after {timeout_s:.0f} s',
                               ErrorCategory.UNCERTAIN, executed=True) from None
        envelope = parse(done.stdout, done.stderr)
        if len(self.calls) < 500:
            self.calls.append({'command': args[0] if args else '', 'ms': round((time.perf_counter() - started) * 1000, 1),
                               'ok': envelope.ok, 'code': envelope.error.code if envelope.error else '',
                               'delivery': envelope.disposition.delivery if envelope.disposition else ''})
        return envelope


def parse(stdout: str, stderr: str = '') -> Envelope:
    text = (stdout or '').strip()
    for candidate in (text, text.splitlines()[-1] if text else ''):  # one envelope; tolerate log lines before it
        try:
            return Envelope.model_validate(json.loads(candidate))
        except (ValueError, TypeError):
            continue
    detail = (stderr or text or 'no output')[-300:]
    return Envelope(ok=False, error=AgentDesktopError(code='INTERNAL', message=f'unreadable output: {detail}',
                                                      disposition=Disposition(delivery='delivered_unverified')))
