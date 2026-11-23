"""Unit-checked bounded changes, with immutable scenario and explicit invalidation."""
from __future__ import annotations

from typing import Literal
from ..contracts import Identifier, Parameter, Quantity, StrictModel
from .component_graph import ComponentGraph, Project, fingerprint
from .units import convert


class Change(StrictModel):
    parameter_id: Identifier
    operation: Literal['set', 'delta']
    quantity: Quantity


class ChangePlan(StrictModel):
    baseline_sha256: str
    candidate_sha256: str
    scenario_sha256: str
    before: Parameter
    after: Parameter
    invalidated: tuple[str, ...]
    disposition: Literal['PLANNED_NOT_EXECUTED'] = 'PLANNED_NOT_EXECUTED'
    evidence_status: Literal['MODEL_CONSISTENT'] = 'MODEL_CONSISTENT'


def plan(project: Project, change: Change, *, journal=None) -> tuple[Project, ChangePlan]:
    graph = ComponentGraph(project)
    binding = next((b for b in project.parameters if b.parameter.id == change.parameter_id), None)
    if binding is None:
        raise ValueError('unknown design parameter; scenario changes need a separate scenario branch')
    if not binding.mutable:
        raise PermissionError('parameter is not approved as mutable')
    before = binding.parameter
    if change.quantity.value is None:
        raise ValueError('a parameter change requires a known value')
    if change.operation == 'delta' and before.quantity.value is None:
        raise ValueError('cannot increment an unknown baseline')
    converted = convert(change.quantity, before.quantity.unit, journal=journal)
    value = converted.value
    if change.operation == 'delta':
        zero = Quantity(value=0.0, unit=change.quantity.unit, origin='deterministic', source_ref='affine-delta-origin')
        origin = convert(zero, before.quantity.unit, journal=journal)
        value = before.quantity.value + converted.value - origin.value
    quantity = Quantity(value=value, unit=before.quantity.unit, origin='source', source_ref=change.quantity.source_ref)
    after = Parameter(**{**before.model_dump(), 'revision': before.revision+1, 'quantity': quantity})
    replaced = tuple(type(b)(**{**b.model_dump(), 'parameter': after}) if b is binding else b for b in project.parameters)
    candidate = Project(**{**project.model_dump(), 'revision': project.revision+1, 'parameters': replaced,
                           'components': project.components, 'computations': project.computations,
                           'dependencies': project.dependencies, 'scenario': project.scenario})
    return candidate, ChangePlan(baseline_sha256=fingerprint(project), candidate_sha256=fingerprint(candidate),
                                 scenario_sha256=fingerprint(project.scenario), before=before, after=after,
                                 invalidated=graph.affected(change.parameter_id))
