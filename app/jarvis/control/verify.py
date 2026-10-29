"""Post-condition checks (prompt section 8). A click acknowledgement is never success."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from .types import CancelToken, ControlError, ErrorCategory, Expectation

Probe = Callable[..., Any]
Checker = Callable[[Mapping[str, Any], Probe], Tuple[bool, str]]


def _url_equals(params: Mapping[str, Any], probe: Probe) -> Tuple[bool, str]:
    url = probe('url')
    return url == params['url'], f'URL is {url!r}'


def _url_matches(params: Mapping[str, Any], probe: Probe) -> Tuple[bool, str]:
    url = str(probe('url'))
    return re.search(str(params['pattern']), url) is not None, f'URL is {url!r}'


def _value_equals(params: Mapping[str, Any], probe: Probe) -> Tuple[bool, str]:
    value = probe('value', **{k: v for k, v in params.items() if k != 'expected'})
    return value == params['expected'], f'value has length {len(str(value))}'


def _state_equals(params: Mapping[str, Any], probe: Probe) -> Tuple[bool, str]:
    value = probe('state', key=params['key'])
    return value == params['expected'], f'{params["key"]} is {value!r}'


def _changed(params: Mapping[str, Any], probe: Probe) -> Tuple[bool, str]:
    after = probe('signature')
    return after != params['before'], 'observed state changed' if after != params['before'] else 'no change observed'


def _file_exists(params: Mapping[str, Any], probe: Probe) -> Tuple[bool, str]:
    path = Path(params['path'])
    kind = params.get('kind', 'file')
    ok = path.is_dir() if kind == 'dir' else path.is_file()
    return ok, f'{kind} {path.name} {"exists" if ok else "is missing"}'


def _file_contains(params: Mapping[str, Any], probe: Probe) -> Tuple[bool, str]:
    path = Path(params['path'])
    if not path.is_file():
        return False, f'{path.name} is missing'
    text = path.read_text(encoding=params.get('encoding', 'utf-8'), errors='replace')
    expected = str(params['text'])
    ok = (text == expected) if params.get('exact') else expected in text
    return ok, f'{path.name}: {len(text)} chars, sha256 {hashlib.sha256(text.encode()).hexdigest()[:12]}'


def _file_sha256(params: Mapping[str, Any], probe: Probe) -> Tuple[bool, str]:
    path = Path(params['path'])
    if not path.is_file():
        return False, f'{path.name} is missing'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == params['sha256'], f'{path.name} sha256 {digest[:12]}'


class Verifier:
    def __init__(self) -> None:
        self.checkers: Dict[str, Checker] = {}

    def register(self, kind: str, checker: Checker) -> None:
        self.checkers[kind] = checker

    def check(self, expectation: Expectation, probe: Probe) -> Tuple[bool, str]:
        checker = self.checkers.get(expectation.kind)
        if checker is None:
            raise ControlError(f'No verifier for {expectation.kind!r}.', ErrorCategory.UNSUPPORTED)
        try:
            return checker(expectation.params, probe)
        except KeyError as exc:
            raise ControlError(f'Expectation {expectation.kind} is missing {exc.args[0]!r}.',
                               ErrorCategory.INVALID_ARGUMENTS) from None
        except ControlError:
            raise
        except Exception as exc:
            return False, f'verification read failed: {type(exc).__name__}'

    def wait(self, expectation: Expectation, probe: Probe, timeout_s: float,
             cancel: Optional[CancelToken] = None, interval_s: float = .05,
             clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
             event: Optional[Callable[[float], bool]] = None) -> Tuple[bool, str]:
        """Re-check until the expectation holds or the deadline passes. Read-only.

        `event(timeout)` lets a route block on a real change notification (UIA event, DOM
        mutation, navigation) instead of sleeping; the check still decides success.
        """
        deadline = clock() + timeout_s
        ok, evidence = self.check(expectation, probe)
        while not ok:
            if cancel is not None:
                cancel.raise_if_cancelled()
            remaining = deadline - clock()
            if remaining <= 0:
                break
            if event is not None:
                event(min(remaining, 1.0))
            else:
                sleep(min(interval_s, remaining))
            ok, evidence = self.check(expectation, probe)
        return ok, evidence


default_verifier = Verifier()
for _kind, _checker in {'url_equals': _url_equals, 'url_matches': _url_matches, 'value_equals': _value_equals,
                        'state_equals': _state_equals, 'changed': _changed, 'file_exists': _file_exists,
                        'file_contains': _file_contains, 'file_sha256': _file_sha256}.items():
    default_verifier.register(_kind, _checker)
