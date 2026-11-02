"""Routing: hard eligibility first, then soft preference among what is left. Explains every choice.

Stimulus -> response without extra model calls: the request is matched by the same deterministic matchers the
fixed routes use (calculator, site question, small program or edit, web app, live Blender, wireframe), tools are
ranked by the existing ``capabilities.rank_tools`` (reused, not rebuilt), then each candidate passes the hard gate
(``policy.eligibility``). Preference is a Beta-Bernoulli mean over *verified* outcomes in this task context, plus
the retrieval rank. Learning can reorder eligible routes; it can never make an ineligible one eligible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .graph import CapabilityGraph
from .policy import Context, Eligibility, eligibility

WIREFRAME = re.compile(r'\bwire\s*-?\s*frame|\bblock\s*-?\s*out\b|\b(?:plan|design)\b[^.]*\bfirst\b', re.I)
PRIOR = (1.0, 1.0)  # Beta prior: no evidence = 0.5


def task_context(goal: str) -> str:
    """A coarse, privacy-free bucket for statistics (no request text is stored as a key)."""
    from ..capabilities import intents
    found = sorted(intents(goal))
    return '+'.join(found[:3]) or 'general'


def deterministic_routes(goal: str) -> List[Tuple[str, str]]:
    """(route neuron, why) for every fixed route whose matcher accepts the request."""
    rows: List[Tuple[str, str]] = []
    checks: List[Tuple[str, Callable[[str], Any], str]] = []
    from .. import blender_live, fast_routes, small_edit, small_program, web_app
    checks += [('route.calculator@v1', fast_routes.calculation, 'arithmetic the calculator can type'),
               ('route.web_question@v1', fast_routes.site_question, 'a question about one named site'),
               ('route.small_edit@v1', small_edit.matches_edit, 'a small edit of one named Python file'),
               ('route.small_program@v1', small_program.matches, 'one print-only Python file'),
               ('route.web_app@v1', web_app.matches, 'one animated web page or browser app'),
               ('route.blender_live@v1', blender_live.live_request, 'a clear live Blender model')]
    for node_id, matcher, why in checks:
        try:
            if matcher(goal):
                rows.append((node_id, why))
        except Exception:  # A matcher bug must not break routing; the route simply does not match.
            continue
    if re.search(r'\bblender\b', goal, re.I) and WIREFRAME.search(goal):
        rows.insert(0, ('route.blender_wireframe@v1', 'the user asked to see a wireframe plan first'))
    return rows


@dataclass
class Candidate:
    node_id: str
    why: str
    rank: int
    gate: Eligibility
    preference: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {'node': self.node_id, 'why': self.why, 'rank': self.rank, 'eligible': self.gate.eligible,
                'needs_approval': self.gate.needs_approval, 'blocked_by': self.gate.reasons,
                'preference': round(self.preference, 3), 'evidence': self.evidence}


@dataclass
class Route:
    goal: str
    context: str
    graph_version: int
    chosen: List[Candidate]
    skipped: List[Candidate]
    fallback: str
    ms: float

    def as_dict(self) -> Dict[str, Any]:
        return {'context': self.context, 'graph_version': self.graph_version, 'fallback': self.fallback,
                'chosen': [c.as_dict() for c in self.chosen], 'skipped': [c.as_dict() for c in self.skipped],
                'ms': round(self.ms, 2)}


def preference(stats: Dict[str, Dict[str, Any]], node_id: str, rank: int) -> Tuple[float, Dict[str, Any]]:
    row = stats.get(node_id)
    ok, bad = (row['successes'], row['failures']) if row else (0, 0)
    mean = (ok + PRIOR[0]) / (ok + bad + PRIOR[0] + PRIOR[1])
    lat = sorted(row['latencies']) if row and row.get('latencies') else []
    p50 = lat[len(lat) // 2] if lat else None
    fit = 1.0 / (1 + rank)  # retrieval order still matters when there is no evidence yet
    latency_penalty = min(0.2, (p50 or 0) / 600.0)  # seconds; ten minutes or more costs the full 0.2
    return mean + 0.5 * fit - latency_penalty, {'verified_ok': ok, 'verified_failed': bad, 'p50_s': p50}


class Router:
    def __init__(self, graph: CapabilityGraph, journal: Any = None) -> None:
        self.graph, self.journal = graph, journal

    def route(self, goal: str, ctx: Context, specs: Optional[Dict[str, Any]] = None, limit: int = 8) -> Route:
        started = time.perf_counter()
        context = task_context(goal)
        from .policy import goal_refusal
        if goal and goal_refusal(goal):  # Off limits: nothing is eligible, and nothing is ranked.
            return Route(goal, context, self.graph.version, [], [], 'refuse', (time.perf_counter() - started) * 1000)
        from .learning import mode
        learned = self.journal is not None and mode(ctx.config) == 'on'  # off/shadow: retrieval order and priors only
        stats = {r['node_id']: r for r in self.journal.stats(context)} if learned else {}
        named: List[Tuple[str, str]] = deterministic_routes(goal)
        if specs is None:
            from ..tools import SPECS
            specs = {s.name: s for s in SPECS}
        from ..capabilities import rank_tools
        try:
            ranked = rank_tools(specs, goal, set(ctx.allowed_tools) if ctx.allowed_tools is not None else None,
                                None, limit)
        except Exception:
            ranked = []
        named += [(f'tool.{name}@v1', 'ranked by tool retrieval') for name in ranked]
        candidates: List[Candidate] = []
        seen = set()
        for rank, (node_id, why) in enumerate(named):
            neuron = self.graph.neurons.get(node_id)
            if neuron is None or node_id in seen:
                continue
            seen.add(node_id)
            gate = eligibility(neuron, ctx)
            score, evidence = preference(stats, node_id, rank) if gate.eligible else (0.0, {})
            candidates.append(Candidate(node_id, why, rank, gate, score, evidence))
        chosen = sorted((c for c in candidates if c.gate.eligible), key=lambda c: (-c.preference, c.rank))
        skipped = [c for c in candidates if not c.gate.eligible]
        fallback = 'none' if chosen else 'cortex.planner.legacy@v1'
        refused = any('even with your approval' in r for c in skipped for r in c.gate.reasons)
        if refused:
            fallback = 'refuse'
        return Route(goal, context, self.graph.version, chosen, skipped, fallback,
                     (time.perf_counter() - started) * 1000)
