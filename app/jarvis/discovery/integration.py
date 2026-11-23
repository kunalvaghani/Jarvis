"""Small brain extension points: reviewed source, compiled templates and adapters.

All execution, journal claims, cancellation, approvals, verification and learning
remain in the existing neural dispatcher. No alternate request executor exists here.
"""
from __future__ import annotations

import json
import math
import re
import uuid
import sqlite3
from typing import Any, TYPE_CHECKING
from .catalog import enabled, manifests
from .contracts import Capability, Quantity
from .memory import LabMemory
if TYPE_CHECKING:
    from ..neural.execution import Plan
    from ..neural.dispatcher import Adapter

STATUS = re.compile(r'^\s*(?:jarvis[, ]+)?(?:what can you do in the lab|show lab capabilities|lab status)[?.!\s]*$', re.I)
CONVERT = re.compile(r'^\s*(?:jarvis[, ]+)?lab\s+convert\s+([+-]?(?:\d{1,24}(?:\.\d{0,24})?|\.\d{1,24}))\s+'
                     r'([a-zA-Z][a-zA-Z0-9_/*^ .-]{0,60}?)\s+to\s+([a-zA-Z][a-zA-Z0-9_/*^ .-]{0,60}?)[?\s]*$', re.I)
SCALAR = r'([+-]?(?:\d{1,12}(?:\.\d{0,12})?|\.\d{1,12}))'
DIVIDER = re.compile(r'^\s*(?:jarvis[, ]+)?lab\s+simulate\s+divider\s+' + SCALAR + r'\s+V\s+'
                     + SCALAR + r'\s+ohm\s+' + SCALAR + r'\s+ohm[?.!\s]*$', re.I)


def route_command(command: Any) -> Any:
    """Known Lab text becomes an existing task; unknown requests keep their original route."""
    from ..commands import Command
    if command.kind in ('ask', 'task') and command.extra in ('', 'unparsed') and (
            STATUS.fullmatch(command.value) or CONVERT.fullmatch(command.value) or DIVIDER.fullmatch(command.value)):
        return Command('task', command.value)
    return command


def compile_goal(goal: str, journal: Any, config: Any, graph_version: int = 0) -> Plan | None:
    if not enabled(config):
        return None
    from ..neural.compiler import _const
    from ..neural.execution import Bind, Plan, Step
    if STATUS.fullmatch(goal):
        workflow = 'status'
        inputs = {}
        verifier_inputs = {'report': Bind(step='run', port='report')}
    elif DIVIDER.fullmatch(goal) and enabled(config, 'sim'):
        match = DIVIDER.fullmatch(goal)
        workflow = 'divider'
        # Keep a recognized request in the brain even when its numeric bounds
        # are invalid. The typed adapter rejects it before dispatching a solver;
        # raising here would let the existing compiler fall back to the LLM.
        data = {'supply_v': float(match[1]), 'upper_ohm': float(match[2]), 'lower_ohm': float(match[3])}
        inputs = {'request': _const(journal, data, 'Report')}
        verifier_inputs = {'request': inputs['request'], 'report': Bind(step='run', port='report')}
    else:
        match = CONVERT.fullmatch(goal)
        if not match or not enabled(config, 'sim'):
            return None
        request = Quantity(value=float(match[1]), unit=match[2].strip(), origin='source', source_ref='user-request')
        data = {'quantity': request.model_dump(mode='json'), 'target': match[3].strip()}
        workflow = 'units'
        inputs = {'request': _const(journal, data, 'Report')}
        verifier_inputs = {'request': inputs['request'], 'report': Bind(step='run', port='report')}
    node = {'status': 'discovery.status@v1', 'units': 'discovery.units.convert@v1',
            'divider': 'discovery.electronics.divider@v1'}[workflow]
    if workflow in ('units', 'divider') and enabled(config, 'learning') and graph_version:
        snapshot = journal.graph(graph_version) or {}
        known = {n['node_id'] for n in snapshot.get('neurons', [])}
        learned = [n for n in journal.proposals() if n['node_id'] in known and n['status'] == 'active'
                   and n.get('provider') == 'jarvis.neural.learning'
                   and n.get('source') == 'discovery-qualified:' + node]
        if learned:
            node = learned[-1]['node_id']
    return Plan(goal_id='g-' + uuid.uuid4().hex[:16], goal=goal, workflow='discovery.' + workflow,
                steps=[Step(step_id='run', neuron=node, bind=inputs),
                       Step(step_id='check', neuron=f'discovery.verify.{workflow}@v1', bind=verifier_inputs),
                       Step(step_id='answer', neuron='motor.report@v1',
                            bind={'report': Bind(step='run', port='report'), 'verdict': Bind(step='check', port='verdict')})],
                goal_verifier='check', answer_step='answer', graph_version=graph_version, deadline_s=45)


def adapters(graph: Any, journal: Any, registry: Any = None) -> dict[str, Adapter]:
    memory = LabMemory(journal)
    memory.migrate()
    for m in manifests():
        if m.node_id not in graph.neurons:
            continue
        memory.put(Capability(id=m.node_id, neuron_id=m.node_id, intents=m.intents,
                              golden_ref=m.golden_test, justification='Registered foundation; scientific verification tracked separately.'))

    def status_text(config):
        from ..neural.policy import Context, eligibility
        rows = memory.list('Capability', limit=200)  # 52+ capabilities; the default 50 dropped the last ones
        rows = [r for r in rows if r.neuron_id in graph.neurons]
        available = [(r, graph.neurons[r.neuron_id]) for r in rows]
        return ('Lab foundations: ' + '; '.join(f'{r.neuron_id}: {r.verification}, '
                + ('eligible' if eligibility(n, Context(config=config)).eligible else 'disabled') for r, n in available) +
                '. Numeric solvers and scientific acceptance remain unverified. Evidence: INSUFFICIENT_EVIDENCE.')

    def status(neuron, inputs, env):
        return {'report': status_text(env.config)}

    def verify_status(neuron, inputs, env):
        ok = inputs.get('report') == status_text(env.config)
        return {'verdict': {'passed': ok, 'problems': [] if ok else ['capability description differs from brain/memory'],
                            'evidence': ['capability records and registered neuron ids checked'] if ok else []}}

    def convert_units(neuron, inputs, env):
        from .model.units import convert
        from ..neural.dispatcher import NotStarted
        from ..neural.contracts import digest
        if env.cancelled():
            raise NotStarted('unit conversion cancelled before execution')
        request = inputs['request']
        try:
            quantity = Quantity.model_validate_json(json.dumps(request['quantity']))
            output = convert(quantity, request['target'], journal=journal)
        except (ValueError, RuntimeError, KeyError) as exc:
            raise NotStarted(str(exc)) from None
        return {'report': {'quantity': output.model_dump(mode='json'), 'request_digest': digest(request),
                           'evidence_status': 'MODEL_CONSISTENT',
                           'justification': 'Deterministic dimensional conversion; no physical validation claim.'}}

    def verify_units(neuron, inputs, env):
        from .model.units import convert
        from ..neural.contracts import digest
        request, report = inputs['request'], inputs['report']
        problems = []
        try:
            original = Quantity.model_validate_json(json.dumps(request['quantity']))
            result = Quantity.model_validate_json(json.dumps(report['quantity']))
            expected = convert(original, request['target'], journal=journal)
            back = convert(result, original.unit, journal=journal)
            if report['request_digest'] != digest(request) or report['evidence_status'] != 'MODEL_CONSISTENT':
                problems.append('result provenance differs from the request')
            if not math.isclose(back.value, original.value, rel_tol=1e-10, abs_tol=1e-10):
                problems.append('unit conversion failed round-trip consistency')
            if result.unit != expected.unit or not math.isclose(result.value, expected.value, rel_tol=1e-12, abs_tol=1e-12):
                problems.append('result does not use the requested target unit')
        except (ValueError, TypeError, KeyError, RuntimeError):
            problems.append('malformed or dimensionally incompatible unit result')
        return {'verdict': {'passed': not problems, 'problems': problems,
                            'evidence': ['Pint dimensions, finite scalar and round-trip consistency checked'] if not problems else []}}

    def simulate_divider(neuron, inputs, env):
        from .adapters.divider import DividerInput
        from .adapters.ngspice import solve
        from ..neural.contracts import digest
        request = DividerInput.model_validate_json(json.dumps(inputs['request']))
        result, ref = solve(request, journal=journal, cancelled=env.cancelled)
        return {'report': {**result, 'solver_ref': ref, 'request_digest': digest(inputs['request'])}}

    def verify_divider(neuron, inputs, env):
        from .adapters.divider import DividerInput, DividerVectors, verify
        from .adapters.ngspice import environment, IMAGE
        from ..neural.contracts import digest
        problems = []
        try:
            request, report = inputs['request'], inputs['report']
            original = DividerInput.model_validate_json(json.dumps(request))
            result = json.loads(journal.get(report['solver_ref']))
            rows = journal.rows('SELECT worker_sha256,image_id FROM discovery_solver_runs WHERE ref=?', (report['solver_ref'],))
            state = environment()
            if (not rows or rows[0]['image_id'] != IMAGE or not state['ready']
                    or rows[0]['worker_sha256'] != state['worker_sha256']):
                problems.append('missing or changed actual sandbox solver receipt')
            if ({k: v for k, v in report.items() if k not in ('solver_ref', 'request_digest')} != result
                    or result['input'] != request or report['request_digest'] != digest(request)
                    or result['evidence_status'] != 'SIMULATION_PASSED_WITH_ASSUMPTIONS'):
                problems.append('solver result/request provenance mismatch')
            vectors = DividerVectors.model_validate_json(json.dumps(result['vectors']))
            checked = verify(original, vectors)
            problems.extend(checked.problems)
            if checked.netlist_sha256 != result['netlist_sha256']:
                problems.append('netlist digest mismatch')
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
            problems.append('invalid or missing solver evidence')
        return {'verdict': {'passed': not problems, 'problems': problems,
                            'evidence': ['actual sandbox receipt; independent Ohm/Kirchhoff checks'] if not problems else []}}

    handlers = dict(status=status, verify_status=verify_status, convert_units=convert_units, verify_units=verify_units,
                    simulate_divider=simulate_divider, verify_divider=verify_divider)
    found = {m.node_id: handlers[m.entrypoint] for m in manifests() if m.node_id in graph.neurons}
    for n in graph.neurons.values():
        if (n.provider == 'jarvis.neural.learning' and n.source in (
                'discovery-qualified:discovery.units.convert@v1', 'discovery-qualified:discovery.electronics.divider@v1')
                and registry is not None):
            def qualified(neuron, inputs, env):
                from .learning import LearningGate
                from ..neural.dispatcher import NotStarted
                if not LearningGate(memory, registry, env.config).recheck(neuron.node_id):
                    raise NotStarted('learned adapter golden evidence regressed; capability retired')
                return (simulate_divider if neuron.source.endswith('discovery.electronics.divider@v1')
                        else convert_units)(neuron, inputs, env)
            found[n.node_id] = qualified
    return found
