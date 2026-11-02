"""The capability graph: neurons joined by typed synapses, versioned in the journal (rustworkx, CPU only).

Wiring rules (ARCHITECTURE.md Phase 1.3):
- A synapse forms only from an explicit output port to an explicit input port of the *same specific* data type.
  Generic types (Text, Status, Answer, ...) never auto-wire, and descriptions are never used to wire anything.
- Nothing auto-wires *into* a destructive or external-write neuron; such links must be declared by a person.
- A Verdict link back to a producer of what the verifier checks is feedback (a repair path); others are dataflow.
- Two-way communication appears as two synapses, each with its own permission.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import rustworkx as rx

from .contracts import GENERIC_TYPES, Neuron, Synapse

NO_AUTO_TARGET = frozenset({'destructive', 'external_write'})
# Synapses a person declared (source, out_port, target, in_port, mode, condition). Kept short on purpose.
DECLARED: Tuple[Tuple[str, str, str, str, str, Optional[str]], ...] = (
    ('route.blender_wireframe@v1', 'wireframe', 'route.blender_live@v1', 'plan', 'conditional', 'user_approved'),
)


def _edge_id(source: str, out_port: str, target: str, in_port: str) -> str:
    return f'{source.split("@")[0]}.{out_port}->{target.split("@")[0]}.{in_port}'


def wire(neurons: Iterable[Neuron]) -> List[Synapse]:
    nodes = [n for n in neurons if n.status != 'denied']
    consumers: Dict[str, List[Tuple[Neuron, str]]] = {}
    for neuron in nodes:
        if neuron.contract != 'explicit' or neuron.side_effect_class in NO_AUTO_TARGET:
            continue
        for port in neuron.inputs:
            if port.type not in GENERIC_TYPES:
                consumers.setdefault(port.type, []).append((neuron, port.name))
    synapses: List[Synapse] = []
    for source in nodes:
        if source.contract != 'explicit':
            continue
        for port in source.outputs:
            for target, in_port in consumers.get(port.type, ()):
                if target.node_id == source.node_id:
                    continue
                # Feedback = a verdict going back to a neuron that makes what this verifier checks (a repair path).
                # A verdict going forward (to report it, or to gate an apply) is ordinary dataflow.
                back = port.type == 'Verdict' and bool(set(target.output_types()) & set(source.input_types()))
                synapses.append(Synapse(
                    edge_id=_edge_id(source.node_id, port.name, target.node_id, in_port), source=source.node_id,
                    target=target.node_id, out_port=port.name, in_port=in_port, data_type=port.type,
                    mode='feedback' if back else 'dataflow',
                    on_event='verification.failed' if back else 'neuron.succeeded',
                    condition='verdict_failed' if back else None,
                    permission=target.privilege))
    by_id = {n.node_id: n for n in nodes}
    for start, out_port, end, in_port, mode, condition in DECLARED:
        if start in by_id and end in by_id:
            kind = next((p.type for p in by_id[start].outputs if p.name == out_port), 'Any')
            synapses.append(Synapse.model_validate({
                'edge_id': _edge_id(start, out_port, end, in_port), 'source': start, 'target': end,
                'out_port': out_port, 'in_port': in_port, 'data_type': kind, 'mode': mode, 'condition': condition,
                'permission': by_id[end].privilege, 'origin': 'declared'}))
    return synapses


class CapabilityGraph:
    def __init__(self, neurons: Iterable[Neuron], version: int = 0) -> None:
        self.neurons: Dict[str, Neuron] = {n.node_id: n for n in neurons}
        self.synapses = wire(self.neurons.values())
        self.version = version
        self.g: rx.PyDiGraph = rx.PyDiGraph(check_cycle=False, multigraph=True)
        self.index: Dict[str, int] = {node_id: self.g.add_node(node_id) for node_id in self.neurons}
        for synapse in self.synapses:
            self.g.add_edge(self.index[synapse.source], self.index[synapse.target], synapse)

    @classmethod
    def from_registry(cls, registry: Any, journal: Any = None) -> 'CapabilityGraph':
        graph = cls(registry.nodes.values())
        if journal is not None:
            graph.version = journal.save_graph(graph.snapshot())
        return graph

    def snapshot(self) -> Dict[str, Any]:
        return {'neurons': [n.model_dump(mode='json') for n in sorted(self.neurons.values(), key=lambda n: n.node_id)],
                'synapses': [s.model_dump(mode='json') for s in sorted(self.synapses, key=lambda s: s.edge_id)]}

    # Queries ------------------------------------------------------------------------------------------------
    def outgoing(self, node_id: str) -> List[Synapse]:
        if node_id not in self.index:
            return []
        return [edge for _, _, edge in self.g.out_edges(self.index[node_id])]

    def incoming(self, node_id: str) -> List[Synapse]:
        if node_id not in self.index:
            return []
        return [edge for _, _, edge in self.g.in_edges(self.index[node_id])]

    def producers(self, data_type: str) -> List[Neuron]:
        return [n for n in self.neurons.values() if data_type in n.output_types()]

    def consumers(self, data_type: str) -> List[Neuron]:
        return [n for n in self.neurons.values() if data_type in n.input_types()]

    def neighbourhood(self, node_ids: Iterable[str], hops: int = 1) -> Tuple[Set[str], List[Synapse]]:
        """The local area around some neurons (what the UI shows by default instead of the whole brain)."""
        seen = {n for n in node_ids if n in self.index}
        frontier = set(seen)
        for _ in range(max(0, hops)):
            nxt: Set[str] = set()
            for node_id in frontier:
                for edge in self.outgoing(node_id) + self.incoming(node_id):
                    nxt.update((edge.source, edge.target))
            frontier = nxt - seen
            seen |= nxt
        return seen, [s for s in self.synapses if s.source in seen and s.target in seen]

    def path(self, start_types: Iterable[str], goal_type: str, allowed: Optional[Set[str]] = None,
             max_hops: int = 6) -> Optional[List[str]]:
        """Shortest chain of neurons turning data we have into the data we need, through explicit contracts only.

        ``allowed`` restricts the search to eligible neurons (the hard gate comes first, always).
        """
        have = set(start_types)
        queue: deque[List[str]] = deque()
        for neuron in self.neurons.values():
            if allowed is not None and neuron.node_id not in allowed:
                continue
            needed = [p.type for p in neuron.inputs if p.required]
            if neuron.contract == 'explicit' and needed and set(needed) <= have:
                queue.append([neuron.node_id])
        seen: Set[str] = set()
        while queue:
            chain = queue.popleft()
            last = self.neurons[chain[-1]]
            if goal_type in last.output_types():
                return list(chain)
            if len(chain) >= max_hops or last.node_id in seen:
                continue
            seen.add(last.node_id)
            for edge in self.outgoing(last.node_id):
                if edge.mode == 'dataflow' and edge.target not in chain and \
                        (allowed is None or edge.target in allowed):
                    queue.append(chain + [edge.target])
        return None

    def stats(self) -> Dict[str, Any]:
        modes: Dict[str, int] = {}
        for synapse in self.synapses:
            modes[synapse.mode] = modes.get(synapse.mode, 0) + 1
        two_way = sum(1 for s in self.synapses if any(t.source == s.target and t.target == s.source
                                                        for t in self.outgoing(s.target)))
        wired = {s.source for s in self.synapses} | {s.target for s in self.synapses}
        return {'version': self.version, 'neurons': len(self.neurons), 'synapses': len(self.synapses),
                'modes': modes, 'two_way_synapses': two_way, 'wired_neurons': len(wired),
                'mean_out_degree': round(len(self.synapses) / max(1, len(wired)), 2)}
