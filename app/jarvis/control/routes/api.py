"""Route 1: API, MCP, COM and file adapters (doc section 11.1). Preferred whenever an adapter does exactly the job.

An adapter declares its operations, each with a risk tier and typed parameters. The executor
validates arguments, asks for approval before every Tier-2 operation (ApprovalGate), calls the
adapter exactly once and never retries: an exception after a write may have started is reported as
uncertain. Adapters that cannot run (not connected, stale verification) say why, so the router can
pick another route or Jarvis can tell the user the one step that fixes it.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..executor import Health, RouteExecutor
from ..policy import ApprovalGate, Policy
from ..timing import StageTimer
from ..types import Action, ActionResult, ControlError, ErrorCategory, Observation, Risk, Route, ToolContract

TYPES: Mapping[str, Tuple[type, ...]] = {'str': (str,), 'int': (int,), 'bool': (bool,), 'list': (list,), 'dict': (dict,)}
MAX_TEXT = 1_000_000


@dataclass(frozen=True)
class Operation:
    description: str
    risk: Risk = Risk.READ
    params: Mapping[str, str] = field(default_factory=dict)  # name -> type; a trailing '?' marks optional.
    timeout_s: float = 30.0


class ApiAdapter(ABC):
    name: str
    operations: Mapping[str, Operation]

    def unavailable(self) -> Optional[str]:
        """None when usable, otherwise what the user must do (connect, re-verify, install)."""
        return None

    @abstractmethod
    def call(self, operation: str, params: Mapping[str, Any], action: Action) -> Mapping[str, Any]:
        """Do it once. Return a JSON-safe mapping; include 'verified': True only after an independent read-back."""

    def probe(self, what: str, **params: Any) -> Any:
        raise ControlError(f'{self.name} has no probe {what!r}.', ErrorCategory.UNSUPPORTED)


def validate(operation: Operation, params: Mapping[str, Any]) -> Dict[str, Any]:
    known = {name.rstrip('?') for name in operation.params}
    extra = set(params) - known
    if extra:
        raise ControlError(f'Unknown parameter(s): {", ".join(sorted(extra))}.', ErrorCategory.INVALID_ARGUMENTS)
    clean: Dict[str, Any] = {}
    for spec, kind in operation.params.items():
        name, optional = spec.rstrip('?'), spec.endswith('?')
        if name not in params:
            if not optional:
                raise ControlError(f'Missing parameter {name!r}.', ErrorCategory.INVALID_ARGUMENTS)
            continue
        value = params[name]
        if kind not in TYPES:
            raise ControlError(f'Adapter declares unknown type {kind!r}.', ErrorCategory.TOOL_ERROR)
        if not isinstance(value, TYPES[kind]) or (kind == 'int' and isinstance(value, bool)):
            raise ControlError(f'Parameter {name!r} must be {kind}.', ErrorCategory.INVALID_ARGUMENTS)
        clean[name] = value
    return clean


class ApiExecutor(RouteExecutor):
    route = Route.API

    def __init__(self, adapters: Sequence[ApiAdapter] = (), approvals: Optional[ApprovalGate] = None) -> None:
        self.adapters: Dict[str, ApiAdapter] = {}
        self.approvals = approvals or ApprovalGate()
        self._lock = threading.RLock()
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ApiAdapter) -> None:
        if not adapter.name.isidentifier() or adapter.name in self.adapters:
            raise ControlError(f'Adapter name {adapter.name!r} is invalid or already registered.', ErrorCategory.INVALID_ARGUMENTS)
        self.adapters[adapter.name] = adapter

    def _resolve(self, name: str) -> Tuple[ApiAdapter, str, Operation]:
        adapter_name, _, op_name = name.partition('.')
        adapter = self.adapters.get(adapter_name)
        operation = adapter.operations.get(op_name) if adapter is not None else None
        if adapter is None or operation is None:
            raise ControlError(f'No API operation {name!r}.', ErrorCategory.UNSUPPORTED)
        return adapter, op_name, operation

    def capable(self, name: str) -> bool:
        """True when this exact operation exists and its adapter can run now (router Intent.has_api)."""
        try:
            adapter, _, _ = self._resolve(name)
        except ControlError:
            return False
        return adapter.unavailable() is None

    def contracts(self) -> List[ToolContract]:
        rows = []
        for adapter in self.adapters.values():
            for op_name, op in adapter.operations.items():
                schema = {'type': 'object', 'additionalProperties': False,
                          'properties': {n.rstrip('?'): {'type': {'str': 'string', 'int': 'integer', 'bool': 'boolean',
                                                                  'list': 'array', 'dict': 'object'}[t]}
                                         for n, t in op.params.items()},
                          'required': [n for n in op.params if not n.endswith('?')]}
                rows.append(ToolContract(f'{adapter.name}.{op_name}', op.description, Route.API, op.risk, schema,
                                         {'type': 'object'}, (ErrorCategory.INVALID_ARGUMENTS, ErrorCategory.UNSUPPORTED,
                                                              ErrorCategory.APPROVAL_DENIED, ErrorCategory.UNCERTAIN),
                                         op.timeout_s, 'approval' if op.risk >= Risk.CONSEQUENTIAL else 'none'))
        return rows

    # RouteExecutor ------------------------------------------------------------
    def health_check(self) -> Health:
        states = {name: adapter.unavailable() or 'ready' for name, adapter in self.adapters.items()}
        return Health(True, ', '.join(f'{n}: {s}' for n, s in states.items()) or 'no adapters', {'adapters': states})

    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        lines = []
        for adapter in self.adapters.values():
            reason = adapter.unavailable()
            lines.append(f'{adapter.name}: {"ready" if reason is None else "unavailable - " + reason}')
            lines += [f'  {adapter.name}.{n} [tier {int(op.risk)}] {op.description}' for n, op in adapter.operations.items()]
        return Observation(Route.API, 'api', text='\n'.join(lines), untrusted=False)

    def probe(self, what: str, **params: Any) -> Any:
        adapter_name, _, inner = what.partition('.')
        adapter = self.adapters.get(adapter_name)
        if adapter is None or not inner:
            raise ControlError(f'No API probe {what!r}.', ErrorCategory.UNSUPPORTED)
        return adapter.probe(inner, **params)

    def cancel(self) -> None:
        """Adapter calls are single requests; cancellation is checked before each one starts."""

    def close(self) -> None:
        for adapter in self.adapters.values():
            closer = getattr(adapter, 'close', None)
            if callable(closer):
                closer()

    def act(self, action: Action) -> ActionResult:
        timer = StageTimer()
        executed = False
        try:
            with timer.stage('routing'):
                adapter, op_name, operation = self._resolve(action.name)
                reason = adapter.unavailable()
                if reason is not None:
                    raise ControlError(f'{adapter.name} is unavailable: {reason}', ErrorCategory.UNSUPPORTED)
                params = validate(operation, action.params)
                gated = replace(action, risk=max(action.risk, operation.risk), idempotent=False, max_retries=0) \
                    if operation.risk > action.risk else action
            self.approvals.require(gated)  # Tier 2: one decision per action, never cached.
            action.cancel.raise_if_cancelled()
            with self._lock, timer.stage('mcp_dispatch'):
                executed = operation.risk > Risk.READ
                result = dict(adapter.call(op_name, params, action))
        except ControlError as error:
            if executed and not error.executed:
                error = ControlError(str(error), error.category, executed=True)
            return ActionResult.failure(action, error, timings_ms=timer.result())  # PolicyError included.
        except Exception as error:
            # Never retried: a write may have reached the target.
            return ActionResult(action.action_id, False, Route.API, text=f'{type(error).__name__}: {error}'[:300],
                                executed=executed, error_category=ErrorCategory.UNCERTAIN if executed else ErrorCategory.TOOL_ERROR,
                                timings_ms=timer.result())
        verified = bool(result.pop('verified', operation.risk == Risk.READ))
        evidence = str(result.pop('evidence', 'adapter read-back' if verified else ''))
        if action.expectation is not None:
            from ..verify import default_verifier
            with timer.stage('verify'):
                verified, evidence = default_verifier.wait(action.expectation, self.probe, action.timeout_s, action.cancel)
        ok = verified or action.expectation is None
        return ActionResult(action.action_id, ok, Route.API, text=json.dumps(result, ensure_ascii=False, default=str)[:20000],
                            state=result, executed=executed, verified=verified, evidence=evidence,
                            error_category=ErrorCategory.NONE if ok else ErrorCategory.VERIFICATION_FAILED,
                            timings_ms=timer.result())


class FileAdapter(ApiAdapter):
    """Text files inside the policy's approved roots. New files are Tier 1; replacing an existing file is Tier 2.

    Writes are atomic (temporary file + os.replace) and read back by hash. There is no delete: file
    deletion needs the user's explicit approval outside automation (repository rule).
    """
    name = 'files'
    operations = {
        'list': Operation('List a folder inside the approved directory.', Risk.READ, {'path': 'str'}),
        'read_text': Operation('Read a UTF-8 text file (up to 1 MB).', Risk.READ, {'path': 'str'}),
        'sha256': Operation('Hash a file.', Risk.READ, {'path': 'str'}),
        'create_text': Operation('Create a NEW UTF-8 text file; refuses if it exists.', Risk.REVERSIBLE,
                                 {'path': 'str', 'text': 'str'}),
        'replace_text': Operation('Replace an existing text file; needs approval and the hash it had when read.',
                                  Risk.CONSEQUENTIAL, {'path': 'str', 'text': 'str', 'expected_sha256': 'str'}),
    }

    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    def unavailable(self) -> Optional[str]:
        return None if self.policy.allowed_roots else 'no approved directory is configured'

    def call(self, operation: str, params: Mapping[str, Any], action: Action) -> Mapping[str, Any]:
        path = self.policy.confine(str(params['path']))
        if operation == 'list':
            if not path.is_dir():
                raise ControlError(f'{path.name} is not a folder.', ErrorCategory.TARGET_NOT_FOUND)
            rows = sorted(path.iterdir(), key=lambda p: p.name.casefold())[:500]
            return {'entries': [{'name': p.name, 'folder': p.is_dir(), 'bytes': p.stat().st_size if p.is_file() else None}
                                for p in rows]}
        if operation in ('read_text', 'sha256'):
            if not path.is_file():
                raise ControlError(f'{path.name} does not exist.', ErrorCategory.TARGET_NOT_FOUND)
            if operation == 'sha256':
                return {'sha256': _sha256(path)}
            if path.stat().st_size > MAX_TEXT:
                raise ControlError('The file is larger than 1 MB.', ErrorCategory.INVALID_ARGUMENTS)
            return {'text': path.read_text(encoding='utf-8'), 'sha256': _sha256(path), 'untrusted': True}
        text = str(params['text'])
        if len(text.encode('utf-8')) > MAX_TEXT:
            raise ControlError('The text is larger than 1 MB.', ErrorCategory.INVALID_ARGUMENTS)
        if operation == 'create_text':
            if path.exists():
                raise ControlError(f'{path.name} already exists; nothing was overwritten.', ErrorCategory.NOT_ACTIONABLE)
            if not path.parent.is_dir():
                raise ControlError('The parent folder does not exist.', ErrorCategory.TARGET_NOT_FOUND)
        elif not path.is_file() or _sha256(path) != params['expected_sha256']:
            raise ControlError(f'{path.name} changed since it was read (or is missing); read it again first.',
                               ErrorCategory.STALE_REF)
        _atomic_write(path, text, exclusive=operation == 'create_text')
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        if _sha256(path) != digest:
            raise ControlError('The file does not read back as written; inspect it before writing again.',
                               ErrorCategory.VERIFICATION_FAILED, executed=True)
        return {'path': path.name, 'sha256': digest, 'verified': True, 'evidence': 'sha256 read-back'}

    def probe(self, what: str, **params: Any) -> Any:
        path = self.policy.confine(str(params['path']))
        if what == 'exists':
            return path.exists()
        if what == 'sha256':
            return _sha256(path) if path.is_file() else None
        return super().probe(what, **params)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write(path: Path, text: str, exclusive: bool) -> None:
    handle, temporary = tempfile.mkstemp(prefix='.jarvis-', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path)  # Fails if the file appeared meanwhile: never overwrites.
        else:
            os.replace(temporary, path)
            temporary = ''
    except FileExistsError as error:
        raise ControlError(f'{path.name} appeared while writing; nothing was overwritten.',
                           ErrorCategory.NOT_ACTIONABLE) from error
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)  # Only Jarvis's own temporary file.
