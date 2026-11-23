"""Versioned component assembly and explicit physics dependencies, not a planner.

Uses the existing rustworkx dependency. Assembly membership does not imply a
physics dependency: every invalidation edge must be explicitly declared.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal
import rustworkx as rx
from pydantic import Field, model_validator
from ..contracts import Component, Identifier, Parameter, Scenario, StrictModel


class ParameterBinding(StrictModel):
    component_id: Identifier
    path: str = Field(pattern=r'^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,5}$', max_length=160)
    parameter: Parameter
    mutable: bool = False

    @model_validator(mode='after')
    def bounded_edit(self):
        if self.mutable and (self.parameter.lower is None or self.parameter.upper is None):
            raise ValueError('a mutable parameter needs explicit lower and upper bounds')
        return self


class Computation(StrictModel):
    id: Identifier
    component_id: Identifier
    kind: Literal['geometry', 'mass_inertia', 'mesh', 'aero', 'mechanics', 'electronics',
                  'thermal', 'visualization', 'metric']


class Dependency(StrictModel):
    source: Identifier
    target: Identifier


class Project(StrictModel):
    schema_version: Literal[1] = 1
    id: Identifier
    revision: int = Field(default=1, ge=1)
    components: tuple[Component, ...] = Field(min_length=1, max_length=500)
    parameters: tuple[ParameterBinding, ...] = Field(default=(), max_length=1000)
    computations: tuple[Computation, ...] = Field(default=(), max_length=1000)
    dependencies: tuple[Dependency, ...] = Field(default=(), max_length=5000)
    scenario: Scenario

    @model_validator(mode='after')
    def consistent(self):
        ComponentGraph(self)
        return self


def fingerprint(value) -> str:
    body = value.model_dump(mode='json') if hasattr(value, 'model_dump') else value
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class ComponentGraph:
    def __init__(self, project: Project):
        self.project = project
        components = {c.id: c for c in project.components}
        if len(components) != len(project.components):
            raise ValueError('duplicate component id')
        assembly = rx.PyDiGraph(check_cycle=True)
        indices = {identity: assembly.add_node(identity) for identity in sorted(components)}
        try:
            for c in project.components:
                if c.parent_id is not None:
                    if c.parent_id not in components or c.parent_id == c.id:
                        raise ValueError('dangling or self parent')
                    assembly.add_edge(indices[c.parent_id], indices[c.id], None)
        except rx.DAGWouldCycle as exc:
            raise ValueError('component assembly contains a cycle') from exc
        self.graph = rx.PyDiGraph(check_cycle=True)
        self.nodes = {}
        scenario_ids = [project.scenario.id, *(p.id for p in project.scenario.parameters)]
        identities = [*components, *(b.parameter.id for b in project.parameters),
                      *(c.id for c in project.computations), *scenario_ids]
        if len(identities) != len(set(identities)):
            raise ValueError('identity collision across component, design, scenario or computation')
        bindings = set()
        for binding in project.parameters:
            if binding.component_id not in components:
                raise ValueError('parameter belongs to a missing component')
            key = (binding.component_id, binding.path)
            if key in bindings:
                raise ValueError('duplicate semantic parameter path')
            bindings.add(key)
            self._add(binding.parameter.id)
        for step in project.computations:
            if step.component_id not in components:
                raise ValueError('computation belongs to a missing component')
            self._add(step.id)
        seen = set()
        parameter_ids = {b.parameter.id for b in project.parameters}
        try:
            for edge in project.dependencies:
                if edge.source not in self.nodes or edge.target not in self.nodes:
                    raise ValueError('dangling computation dependency')
                if edge.target in parameter_ids:
                    raise ValueError('derived work cannot overwrite an input parameter')
                pair = (edge.source, edge.target)
                if pair in seen:
                    raise ValueError('duplicate dependency')
                seen.add(pair)
                self.graph.add_edge(self.nodes[edge.source], self.nodes[edge.target], None)
        except rx.DAGWouldCycle as exc:
            raise ValueError('physics dependency cycle') from exc

    def _add(self, identity):
        if identity in self.nodes:
            raise ValueError('duplicate parameter/computation id')
        self.nodes[identity] = self.graph.add_node(identity)

    def affected(self, parameter_id: str) -> tuple[str, ...]:
        if parameter_id not in {b.parameter.id for b in self.project.parameters}:
            raise ValueError('unknown design parameter')
        descendants = rx.descendants(self.graph, self.nodes[parameter_id])
        # Stable lexicographic Kahn order for the impacted subgraph only.
        identities = {self.graph[i] for i in descendants}
        incoming = {identity: 0 for identity in identities}
        followers = {identity: [] for identity in identities}
        for edge in self.project.dependencies:
            if edge.source in identities and edge.target in identities:
                incoming[edge.target] += 1
                followers[edge.source].append(edge.target)
        result = []
        while incoming:
            ready = sorted(n for n, degree in incoming.items() if degree == 0)
            if not ready:
                raise ValueError('invalid dependency cycle')
            for node in ready:
                result.append(node)
                del incoming[node]
                for target in followers[node]:
                    incoming[target] -= 1
        return tuple(result)

    def describe(self):
        return {'project_id': self.project.id, 'revision': self.project.revision,
                'project_sha256': fingerprint(self.project), 'scenario_sha256': fingerprint(self.project.scenario),
                'components': [{'id': c.id, 'parent_id': c.parent_id, 'reality_class': c.reality_class,
                                'unknown_mass': c.mass.value is None, 'missing': list(c.missing)}
                               for c in self.project.components],
                'parameters': [{'id': b.parameter.id, 'component_id': b.component_id, 'path': b.path,
                                'mutable': b.mutable, 'affected': list(self.affected(b.parameter.id))}
                               for b in self.project.parameters],
                'dependency_count': len(self.project.dependencies), 'solver_executed': False,
                'evidence_status': 'MODEL_CONSISTENT',
                'justification': 'Assembly and explicit dependency integrity checked; supplied claims are not independently validated.'}
