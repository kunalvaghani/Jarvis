"""Scope-bound element references (doc section 2.3).

A ref stays valid in its scope (one tab or one window) until navigation or a window change
invalidates the scope. Refs are never renumbered while valid; numbering keeps increasing so a
stale ref can never silently resolve to a different element. Keys are route-specific node
identities (a DOM node id, a UIA runtime id, a vision box id).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Dict, Hashable, Iterable, Optional, Tuple

from .types import ControlError, ErrorCategory, Ref, Route


def stale_message(ref_id: str) -> str:
    return f'{ref_id} is stale or not found. Re-read the page to get fresh references.'


@dataclass
class _Scope:
    generation: int = 0
    by_key: Dict[Hashable, str] = field(default_factory=dict)
    by_ref: Dict[str, Hashable] = field(default_factory=dict)


class RefRegistry:
    def __init__(self, route: Route, prefix: str = 'ref_') -> None:
        self.route, self.prefix = route, prefix
        self._scopes: Dict[str, _Scope] = {}
        self._next = 0
        self._lock = threading.Lock()

    def assign(self, scope: str, key: Hashable) -> Ref:
        with self._lock:
            state = self._scopes.setdefault(scope, _Scope())
            ref_id = state.by_key.get(key)
            if ref_id is None:
                self._next += 1
                ref_id = f'{self.prefix}{self._next}'
                state.by_key[key] = ref_id
                state.by_ref[ref_id] = key
            return Ref(ref_id, self.route, scope, state.generation)

    def resolve(self, ref: Ref) -> Hashable:
        with self._lock:
            state = self._scopes.get(ref.scope)
            if (ref.route is not self.route or state is None or state.generation != ref.generation
                    or ref.id not in state.by_ref):
                raise ControlError(stale_message(ref.id), ErrorCategory.STALE_REF)
            return state.by_ref[ref.id]

    def lookup(self, scope: str, ref_id: str) -> Ref:
        """Rebuild a Ref from a model-supplied id; fails for unknown or out-of-scope ids."""
        with self._lock:
            state = self._scopes.get(scope)
            if state is None or ref_id not in state.by_ref:
                raise ControlError(stale_message(ref_id), ErrorCategory.STALE_REF)
            return Ref(ref_id, self.route, scope, state.generation)

    def invalidate(self, scope: str) -> int:
        """Navigation or window change: every ref in the scope becomes stale."""
        with self._lock:
            state = self._scopes.setdefault(scope, _Scope())
            state.generation += 1
            state.by_key.clear()
            state.by_ref.clear()
            return state.generation

    def retain(self, scope: str, live_keys: Iterable[Hashable]) -> Tuple[str, ...]:
        """Material DOM/tree change: drop refs whose node vanished, keep the rest unchanged."""
        live = set(live_keys)
        with self._lock:
            state = self._scopes.get(scope)
            if state is None:
                return ()
            gone = tuple(ref for key, ref in state.by_key.items() if key not in live)
            for ref_id in gone:
                del state.by_key[state.by_ref.pop(ref_id)]
            return gone

    def drop(self, scope: str) -> None:
        with self._lock:
            self._scopes.pop(scope, None)

    def generation(self, scope: str) -> Optional[int]:
        state = self._scopes.get(scope)
        return state.generation if state else None
