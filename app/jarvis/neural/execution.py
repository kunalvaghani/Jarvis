"""The per-goal execution graph: concrete steps compiled from a request, checked against the capability graph.

A step fires one neuron. Its input ports are bound to earlier steps' output ports (dataflow) or to constants
stored as artifacts. Dataflow must be acyclic; the only way back is a bounded repair: a verifier step whose
failed Verdict re-fires a named producer step, at most ``max_attempts`` times. Exactly one step is the goal
verifier: the goal is verified only when that step passes (no invented success).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator
import rustworkx as rx

MAX_STEPS = 40


class Bind(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    step: Optional[str] = None      # bound to that step's output port ...
    port: Optional[str] = None
    const: Optional[str] = None     # ... or to a constant artifact ref

    @model_validator(mode='after')
    def one_source(self) -> 'Bind':
        if (self.step is None) == (self.const is None) or (self.step is not None and not self.port):
            raise ValueError('a binding names either step+port or a constant')
        return self


class Step(BaseModel):
    model_config = ConfigDict(extra='forbid')
    step_id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    neuron: str
    bind: Dict[str, Bind] = Field(default_factory=dict)
    max_attempts: int = Field(default=1, ge=1, le=5)
    repairs: Optional[str] = None   # verifier steps only: the producer step a failed verdict sends back to
    approval_scope: Optional[str] = None
    after: Tuple[str, ...] = ()     # ordering dependencies without data (e.g. apply only after the user saw a plan)


class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    goal_id: str
    goal: str
    workflow: str
    steps: List[Step]
    goal_verifier: str
    answer_step: str
    deadline_s: float = Field(default=900, gt=0, le=7200)
    graph_version: int = 0

    @model_validator(mode='after')
    def well_formed(self) -> 'Plan':
        ids = [s.step_id for s in self.steps]
        if len(ids) != len(set(ids)) or not 0 < len(ids) <= MAX_STEPS:
            raise ValueError('steps must be unique and between 1 and 40')
        known = set(ids)
        for step in self.steps:
            for bind in step.bind.values():
                if bind.step is not None and bind.step not in known:
                    raise ValueError(f'{step.step_id} binds unknown step {bind.step}')
            if step.repairs is not None and step.repairs not in known:
                raise ValueError(f'{step.step_id} repairs unknown step {step.repairs}')
            if any(a not in known for a in step.after):
                raise ValueError(f'{step.step_id} waits for an unknown step')
        if self.goal_verifier not in known or self.answer_step not in known:
            raise ValueError('goal verifier and answer step must be steps of the plan')
        g = rx.PyDiGraph()
        index = {s: g.add_node(s) for s in ids}
        for step in self.steps:
            for parent in self.parents(step):
                g.add_edge(index[parent], index[step.step_id], None)
        if not rx.is_directed_acyclic_graph(g):
            raise ValueError('dataflow between steps must be acyclic (repairs are the only way back)')
        return self

    def step(self, step_id: str) -> Step:
        return next(s for s in self.steps if s.step_id == step_id)

    @staticmethod
    def parents(step: Step) -> List[str]:
        return sorted({b.step for b in step.bind.values() if b.step is not None} | set(step.after))

    def descendants(self, step_id: str) -> List[str]:
        out: set[str] = set()
        frontier = {step_id}
        while frontier:
            nxt = {s.step_id for s in self.steps if set(self.parents(s)) & frontier} - out
            out |= nxt
            frontier = nxt
        return sorted(out)


def check(plan: Plan, graph: Any) -> List[str]:
    """Every neuron exists and every binding joins ports of the same type. Returns problems (empty = valid)."""
    problems: List[str] = []
    for step in plan.steps:
        neuron = graph.neurons.get(step.neuron)
        if neuron is None:
            problems.append(f'{step.step_id}: no neuron {step.neuron}')
            continue
        inputs = {p.name: p for p in neuron.inputs}
        for port, bind in step.bind.items():
            if port not in inputs:
                problems.append(f'{step.step_id}: {step.neuron} has no input port {port}')
                continue
            if bind.step is not None:
                source = graph.neurons.get(plan.step(bind.step).neuron)
                out = {p.name: p.type for p in source.outputs} if source else {}
                if out.get(bind.port or '') != inputs[port].type:
                    problems.append(f'{step.step_id}.{port}: {bind.step}.{bind.port} is {out.get(bind.port or "")}, '
                                    f'needs {inputs[port].type}')
        for port in (p for p in neuron.inputs if p.required):
            if port.name not in step.bind:
                problems.append(f'{step.step_id}: required port {port.name} is unbound')
        if step.repairs is not None and 'Verdict' not in neuron.output_types():
            problems.append(f'{step.step_id}: only a verifier (Verdict output) can repair')
    if graph.neurons.get(plan.step(plan.goal_verifier).neuron) is not None and \
            'Verdict' not in graph.neurons[plan.step(plan.goal_verifier).neuron].output_types():
        problems.append('the goal verifier must output a Verdict')
    return problems


def plan_dict(plan: Plan) -> Dict[str, Any]:
    return plan.model_dump(mode='json')
