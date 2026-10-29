"""Capability-aware route selection with measured per-route, per-app success. No model calls.

Eligibility comes from what the target supports; order comes from measured success and
latency. Vision is a fallback: it leads only when no structured route can see the target.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Tuple

from .types import ControlError, ErrorCategory, Route

BASE_ORDER = (Route.API, Route.BROWSER, Route.UIA, Route.VISION)
KINDS = frozenset({'web', 'native', 'service', 'canvas', 'file'})


@dataclass(frozen=True)
class Intent:
    target_kind: str               # web | native | service | canvas | file
    app: str = ''
    has_api: bool = False          # an authorized API/MCP/COM/file operation does exactly this
    uia_usable: Optional[bool] = None   # None = not yet probed
    a11y_usable: Optional[bool] = None  # browser accessibility tree for the target
    contains_private: bool = False  # screenshots may hold private data

    def __post_init__(self) -> None:
        if self.target_kind not in KINDS:
            raise ControlError(f'Unknown target kind {self.target_kind!r}.', ErrorCategory.INVALID_ARGUMENTS)


class RouteStats:
    """Success counts and latency per (route, app), with a neutral prior for unseen pairs."""

    def __init__(self) -> None:
        self.counts: Dict[Tuple[str, str], List[float]] = {}  # [successes, attempts, latency_ms_sum]
        self.version = 0
        self._lock = threading.Lock()

    def record(self, route: Route, app: str, ok: bool, latency_ms: float) -> None:
        with self._lock:
            row = self.counts.setdefault((route.value, app.lower()), [0.0, 0.0, 0.0])
            row[0] += 1 if ok else 0
            row[1] += 1
            row[2] += max(0.0, latency_ms)
            self.version += 1

    def success(self, route: Route, app: str) -> float:
        row = self.counts.get((route.value, app.lower())) or self.counts.get((route.value, ''))
        return (row[0] + 1) / (row[1] + 2) if row else .5

    def latency(self, route: Route, app: str) -> Optional[float]:
        row = self.counts.get((route.value, app.lower()))
        return row[2] / row[1] if row and row[1] else None

    def save(self, path: Path) -> None:
        rows = [{'route': r, 'app': a, 'successes': s, 'attempts': n, 'latency_ms_sum': t}
                for (r, a), (s, n, t) in sorted(self.counts.items())]
        Path(path).write_text(json.dumps(rows, indent=1), encoding='utf-8')

    @classmethod
    def load(cls, path: Path) -> 'RouteStats':
        stats = cls()
        try:
            rows = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return stats
        for row in rows if isinstance(rows, list) else []:
            try:
                key = (Route(row['route']).value, str(row['app']).lower())
                stats.counts[key] = [float(row['successes']), float(row['attempts']), float(row['latency_ms_sum'])]
            except (KeyError, TypeError, ValueError):
                continue
        return stats


class Router:
    def __init__(self, available: Mapping[Route, bool], stats: Optional[RouteStats] = None,
                 vision_allows_private: bool = True) -> None:
        self.available = dict(available)
        self.stats = stats or RouteStats()
        self.vision_allows_private = vision_allows_private
        self._cache: Dict[Tuple[Intent, int, FrozenSet[Route]], Tuple[Route, ...]] = {}

    def set_available(self, route: Route, ok: bool) -> None:
        self.available[route] = ok
        self._cache.clear()

    def eligible(self, intent: Intent) -> List[Route]:
        routes: List[Route] = []
        if intent.has_api:
            routes.append(Route.API)
        if intent.target_kind == 'web' and intent.a11y_usable is not False:
            routes.append(Route.BROWSER)
        if intent.target_kind in ('native', 'canvas') and intent.uia_usable is not False:
            routes.append(Route.UIA)
        if intent.target_kind in ('web', 'native', 'canvas') and (self.vision_allows_private or not intent.contains_private):
            routes.append(Route.VISION)
        return [route for route in routes if self.available.get(route, False)]

    def candidates(self, intent: Intent) -> Tuple[Route, ...]:
        key = (intent, self.stats.version, frozenset(r for r, ok in self.available.items() if ok))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        routes = self.eligible(intent)
        structured = [route for route in routes if route is not Route.VISION]

        def score(route: Route) -> Tuple[float, int]:
            # Measured success first (2-point buckets so noise does not reorder), then base order.
            return (-round(self.stats.success(route, intent.app) * 50), BASE_ORDER.index(route))

        ordered = tuple(sorted(structured, key=score)) + ((Route.VISION,) if Route.VISION in routes else ())
        if len(self._cache) > 512:
            self._cache.clear()
        self._cache[key] = ordered
        return ordered

    def select(self, intent: Intent) -> Route:
        routes = self.candidates(intent)
        if not routes:
            raise ControlError('No available route can reach this target.', ErrorCategory.UNSUPPORTED)
        return routes[0]

    def next_route(self, intent: Intent, tried: Iterable[Route]) -> Optional[Route]:
        done = set(tried)
        return next((route for route in self.candidates(intent) if route not in done), None)
