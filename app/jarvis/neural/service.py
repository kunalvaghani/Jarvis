"""The brain service: one per Jarvis process. Builds the registry, graph, router and journal lazily on first use.

Mode ``off``: nothing here is built or called (the hooks return at once). Mode ``shadow``: legacy acts; for each
task the brain records which neurons it would have fired and why, then the tools legacy actually used, so the two
can be compared before the brain is allowed to act. Recording never raises into the task.
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from . import brain_mode

APP = Path(__file__).resolve().parents[2]
_local = threading.local()


class BrainService:
    def __init__(self, config: Any, journal_path: Optional[Path] = None) -> None:
        from .graph import CapabilityGraph
        from .journal import Journal
        from .registry import Registry
        from .router import Router
        self.config = config
        options = (config.get('neural') if isinstance(config, dict) else None) or {}
        path = journal_path or (APP / options['journal'] if options.get('journal') else None)
        self.journal = Journal(path)
        from ..flags import enabled
        if enabled(config, 'lab', 'enabled'):
            from ..discovery.catalog import sources
            from ..discovery.c1 import sources as c1_sources
            from ..discovery.c2 import sources as c2_sources
            from ..discovery.c3 import sources as c3_sources
            from ..discovery.c4 import sources as c4_sources
            from ..discovery.d import sources as d_sources
            from ..discovery.d2 import sources as d2_sources
            from ..discovery.mechanical_flow import sources as mechanics_sources
            all_sources = mechanics_sources(config, d2_sources(config, d_sources(config, c4_sources(config, c3_sources(config, c2_sources(config, c1_sources(config, sources(config))))))))
            from ..discovery.vehicle_flow import sources as vehicle_sources
            from ..discovery.asset_search import sources as asset_sources
            from ..discovery.scenario_project import sources as scenario_sources
            from ..discovery.asset_pipeline import sources as geometry_sources
            self.registry = Registry(self.journal, sources=geometry_sources(config,scenario_sources(config,asset_sources(config,vehicle_sources(config, all_sources))))).refresh()
        else:
            self.registry = Registry(self.journal).refresh()
        self.graph = CapabilityGraph.from_registry(self.registry, self.journal)
        self.router = Router(self.graph, self.journal)
        self.dispatcher = self._dispatcher()
        self._lock = threading.Lock()

    def _dispatcher(self) -> Any:
        from .adapters import adapters_for
        from .dispatcher import Dispatcher
        found = adapters_for(self.graph)
        from ..flags import enabled
        if enabled(self.config, 'lab', 'enabled'):
            from ..discovery.integration import adapters
            found.update(adapters(self.graph, self.journal, self.registry))
            from ..discovery.c1 import adapters as c1_adapters
            found.update(c1_adapters(self.graph, self.journal))
            from ..discovery.c2 import adapters as c2_adapters
            found.update(c2_adapters(self.graph, self.journal))
            from ..discovery.c3 import adapters as c3_adapters
            found.update(c3_adapters(self.graph, self.journal))
            from ..discovery.c4 import adapters as c4_adapters
            found.update(c4_adapters(self.graph, self.journal))
            from ..discovery.d import adapters as d_adapters
            found.update(d_adapters(self.graph, self.journal, self.registry, found))
            from ..discovery.d2 import adapters as d2_adapters
            found.update(d2_adapters(self.graph, self.journal))
            from ..discovery.mechanical_flow import adapters as mechanics_adapters
            found.update(mechanics_adapters(self.graph, self.journal))
            from ..discovery.vehicle_flow import adapters as vehicle_adapters
            found.update(vehicle_adapters(self.graph, self.journal))
            from ..discovery.asset_search import adapters as asset_adapters
            found.update(asset_adapters(self.graph, self.journal))
            from ..discovery.scenario_project import adapters as scenario_adapters
            found.update(scenario_adapters(self.graph,self.journal))
            from ..discovery.asset_pipeline import adapters as geometry_adapters
            found.update(geometry_adapters(self.graph,self.journal))
        return Dispatcher(self.graph, self.journal, found)

    def rebuild(self) -> int:
        """Re-read every source (new tools, MCP tools, approved neurons) and journal a new version if it changed."""
        from .graph import CapabilityGraph
        from .router import Router
        with self._lock:
            self.registry.refresh()
            self.graph = CapabilityGraph.from_registry(self.registry, self.journal)
            self.router = Router(self.graph, self.journal)
            self.dispatcher = self._dispatcher()
            return self.graph.version

    def context(self, goal: str, actions: Any = None) -> Any:
        from .policy import Context
        allowed = getattr(actions, 'allowed_tools', None)
        return Context(goal=goal, config=self.config,
                       allowed_tools=allowed if isinstance(allowed, (set, frozenset)) else None)

    def route(self, goal: str, actions: Any = None) -> Any:
        return self.router.route(goal, self.context(goal, actions))


_services: Dict[int, BrainService] = {}
_services_lock = threading.Lock()


def service_for(actions: Any) -> Optional[BrainService]:
    config = getattr(actions, 'config', {})
    if brain_mode(config) == 'off':
        return None
    with _services_lock:
        found = getattr(actions, '_neural_service', None)
        if found is None:
            found = BrainService(config)
            try:
                actions._neural_service = found
            except AttributeError:
                _services[id(actions)] = found
        return found


def shadow_begin(actions: Any, goal: str) -> Optional[str]:
    """Shadow mode: record the brain's route for this task. Returns the goal id (or None when off/failed)."""
    try:
        if getattr(_local, 'goal', None) is not None:
            return None  # A nested task belongs to the outer goal.
        service = service_for(actions)
        if service is None:
            return None
        goal_id = 'g-' + uuid.uuid4().hex[:16]
        route = service.route(goal, actions)
        service.journal.shadow(goal_id, route.as_dict())
        _local.goal = (service, goal_id)
        return goal_id
    except Exception:
        return None  # Shadow mode must never affect the task.


def shadow_tool(actions: Any, tool: Any) -> None:
    current = getattr(_local, 'goal', None)
    if current is None:
        return
    try:
        current[0].journal.shadow_actual(current[1], str(tool)[:80])
    except Exception:
        pass


def shadow_end(goal_id: Optional[str], outcome: str) -> None:
    current = getattr(_local, 'goal', None)
    if current is None or goal_id is None or current[1] != goal_id:
        return
    _local.goal = None
    try:
        current[0].journal.shadow_outcome(goal_id, outcome)
        from .lifecycle import tick
        tick(current[0])
    except Exception:
        pass


def approver(actions: Any, cancelled: Any) -> Any:
    """The brain asks through Jarvis's own approval card; no answer, a cancel or an error all mean no."""
    def approve(scope: str, summary: str) -> bool:
        ask = getattr(actions, '_approve', None)
        if ask is None:
            return False
        try:
            ask('brain', f'{scope}. {summary}', cancelled)
            return True
        except Exception:
            return False
    return approve


def act(actions: Any, goal: str, cancelled: Any) -> Optional[str]:
    """Mode on: run the goal through the brain when a workflow fits; None means "legacy, please".

    A verified goal returns its answer. Anything else raises with the stop reason, exactly like a legacy failure,
    so nothing upstream can mistake an unverified result for success.
    """
    config = getattr(actions, 'config', {})
    try:  # Nothing has acted yet: any problem here means "legacy, please", never a broken task.
        if brain_mode(config) != 'on' or getattr(_local, 'goal', None) is not None:
            return None
        service = service_for(actions)
        if service is None:
            return None
        from .compiler import compile_goal
        from .dispatcher import Env
        plan = compile_goal(goal, service.journal, config, service.graph.version)
    except Exception:
        return None
    if plan is None:
        return None
    # From here on the brain may act, so its errors propagate: falling back now could repeat a side effect.
    _local.goal = (service, plan.goal_id)
    try:
        outcome = service.dispatcher.run(plan, Env(actions=actions, cancelled=cancelled,
                                                   approve=approver(actions, cancelled), config=config))
    finally:
        _local.goal = None
    from .lifecycle import tick
    tick(service)  # every few goals: grow learned neurons from verified chains, retire failing learned ones
    if outcome.verified:
        return str(outcome.answer)
    raise ValueError(f'The brain stopped ({outcome.state}): {outcome.stop_reason}')
