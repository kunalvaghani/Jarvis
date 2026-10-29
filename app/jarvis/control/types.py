"""Typed action protocol shared by every route (prompt section 7)."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, IntEnum
import threading
import time
from typing import Any, Mapping, Optional, Tuple, Union
import uuid

from .coords import Point, Transform


class Route(str, Enum):
    API = 'api'
    BROWSER = 'browser'
    UIA = 'uia'
    VISION = 'vision'


class Risk(IntEnum):
    READ = 0           # inspect page, read window, get URL
    REVERSIBLE = 1     # navigate, switch tab, type into a harmless field
    CONSEQUENTIAL = 2  # send, submit, purchase, delete, install, change security settings


class ErrorCategory(str, Enum):
    NONE = 'none'
    INVALID_ARGUMENTS = 'invalid_arguments'
    POLICY_DENIED = 'policy_denied'
    APPROVAL_DENIED = 'approval_denied'
    STALE_REF = 'stale_ref'
    TARGET_NOT_FOUND = 'target_not_found'
    NOT_ACTIONABLE = 'not_actionable'
    FOCUS_LOST = 'focus_lost'
    TIMEOUT = 'timeout'
    CANCELLED = 'cancelled'
    VERIFICATION_FAILED = 'verification_failed'
    UNCERTAIN = 'uncertain'
    UNSUPPORTED = 'unsupported'
    TOOL_ERROR = 'tool_error'
    ELEVATED_TARGET = 'elevated_target'
    SECURE_DESKTOP = 'secure_desktop'
    NOT_EXECUTED = 'not_executed'


class ControlError(Exception):
    """A classified failure. `executed` is True when input may already have reached the target."""

    def __init__(self, message: str, category: ErrorCategory, executed: bool = False) -> None:
        super().__init__(message)
        self.category = category
        self.executed = executed


class CancelToken:
    """Cooperative cancellation shared by an action, its route and the emergency stop."""

    def __init__(self, parent: Optional['CancelToken'] = None) -> None:
        self._event = threading.Event()
        self._parent = parent
        self.reason = ''

    def cancel(self, reason: str = 'cancelled') -> None:
        self.reason = self.reason or reason
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set() or (self._parent is not None and self._parent.cancelled)

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            reason = self.reason or (self._parent.reason if self._parent else '') or 'cancelled'
            raise ControlError('Cancelled: ' + reason, ErrorCategory.CANCELLED)

    def child(self) -> 'CancelToken':
        return CancelToken(self)


@dataclass(frozen=True)
class Ref:
    """Route- and scope-bound element reference; stale after navigation or window change."""
    id: str
    route: Route
    scope: str
    generation: int


Target = Union[Ref, Point, None]


@dataclass(frozen=True)
class TargetContext:
    app: str = ''
    window: Optional[int] = None
    tab: str = ''


@dataclass(frozen=True)
class Expectation:
    """Post-condition checked by verify.py; `kind` selects the checker."""
    kind: str
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    name: str
    goal: str
    route: Route
    params: Mapping[str, Any] = field(default_factory=dict)
    target: Target = None
    context: TargetContext = TargetContext()
    risk: Risk = Risk.REVERSIBLE
    expectation: Optional[Expectation] = None
    timeout_s: float = 10.0
    idempotent: bool = False
    max_retries: int = 0
    permission_scope: str = ''
    task_id: str = ''
    project_id: str = ''
    step_id: str = ''
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cancel: CancelToken = field(default_factory=CancelToken, compare=False, repr=False)

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ControlError('Action name is required.', ErrorCategory.INVALID_ARGUMENTS)
        if not 0 < self.timeout_s <= 600:
            raise ControlError('Action timeout must be within (0, 600] seconds.', ErrorCategory.INVALID_ARGUMENTS)
        if not 0 <= self.max_retries <= 3:
            raise ControlError('At most three retries are allowed.', ErrorCategory.INVALID_ARGUMENTS)
        if self.risk is Risk.CONSEQUENTIAL and (self.idempotent or self.max_retries):
            raise ControlError('Consequential actions are never retried automatically.', ErrorCategory.INVALID_ARGUMENTS)

    def with_route(self, route: Route) -> 'Action':
        return replace(self, route=route, target=None)


@dataclass(frozen=True)
class Observation:
    route: Route
    scope: str
    text: str = ''
    refs: Tuple[Ref, ...] = ()
    screenshot: Optional[bytes] = None
    transform: Optional[Transform] = None
    state: Mapping[str, Any] = field(default_factory=dict)
    captured_at: float = field(default_factory=time.monotonic)
    untrusted: bool = True  # Page/window content is data, never instructions.


@dataclass(frozen=True)
class ActionResult:
    action_id: str
    ok: bool
    route: Route
    text: str = ''
    image: Optional[bytes] = None
    state: Mapping[str, Any] = field(default_factory=dict)
    executed: bool = False
    verified: bool = False
    evidence: str = ''
    error_category: ErrorCategory = ErrorCategory.NONE
    timings_ms: Mapping[str, float] = field(default_factory=dict)

    @classmethod
    def failure(cls, action: Action, error: ControlError, **extra: Any) -> 'ActionResult':
        return cls(action.action_id, False, action.route, text=str(error), executed=error.executed,
                   error_category=error.category, **extra)


@dataclass(frozen=True)
class ToolContract:
    """Metadata every control tool carries into the existing Jarvis ToolRegistry."""
    name: str
    description: str
    route: Route
    risk: Risk
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    error_codes: Tuple[ErrorCategory, ...]
    timeout_s: float
    permission: str = 'none'
    capabilities: Tuple[str, ...] = ()
    verifies: str = ''
