"""C1 neurons in the existing brain: scoped file inspection and change planning.

All requests are deterministic templates. No solver, downloader, alternate brain
or executable skill is created. Invalid recognized requests fail inside the brain.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import uuid
from .catalog import enabled
from .contracts import Capability, Quantity, Source
from .memory import LabMemory
from .model.component_graph import ComponentGraph, Project
from .model.parameter_registry import Change, plan
from .model.project_store import save
from .adapters.assets import AssetCandidate, inspect_local, local_bytes

PATH = r'"([^"\r\n]{1,500})"'
SCALAR = r'([+-]?(?:\d{1,12}(?:\.\d{0,12})?|\.\d{1,12}))'
PATTERNS = {
    'project': re.compile(r'^\s*lab inspect project\s+'+PATH+r'\s*$', re.I),
    'asset': re.compile(r'^\s*lab inspect asset\s+'+PATH+r'\s*$', re.I),
    'parameter': re.compile(r'^\s*lab plan parameter\s+'+PATH+r'\s+([a-zA-Z0-9_.:@/-]{1,200})\s+(set|delta)\s+'
                            +SCALAR+r'\s+([a-zA-Z][a-zA-Z0-9_/*^ .-]{0,60})\s*$', re.I),
}
NODES = {'project': 'discovery.components.inspect@v1', 'asset': 'discovery.assets.inspect_local@v1',
         'parameter': 'discovery.parameters.plan@v1'}


def route_command(command):
    from ..commands import Command
    if command.kind in ('ask', 'task') and command.extra in ('', 'unparsed') and any(
            pattern.fullmatch(command.value) for pattern in PATTERNS.values()):
        return Command('task', command.value)
    return command


def neurons(config):
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    if not enabled(config):
        return []
    nodes = []
    for workflow, identity in (*NODES.items(), ('verify', 'discovery.verify.c1@v1')):
        nodes.append(Neuron(node_id=identity, kind='verifier' if workflow == 'verify' else 'skill',
            capability=identity.split('@')[0], provider='jarvis.discovery.c1', contract='explicit',
            inputs=ports(('request:Report', 'report:Report') if workflow == 'verify' else ('request:Report',)),
            outputs=ports(('verdict:Verdict',) if workflow == 'verify' else ('report:Report',)),
            side_effect_class='read_only', privilege='read', runtime='local',
            requirements=('flag:lab.enabled',) + (('flag:lab.sim',) if workflow == 'parameter' else ()),
            resource_cost={'gpu_vram_mb': 0, 'money': 0, 'cpu_s_estimate': 2},
            description='C1 '+workflow+': scoped scientific component and asset integrity; no solver execution',
            source='jarvis/discovery/c1.py', timeout_ms=15_000))
    return nodes


def sources(config, existing):
    return {**existing, 'discovery_c1': lambda: neurons(config)}


def compile_goal(goal, journal, config, graph_version=0):
    if not enabled(config):
        return None
    from ..neural.compiler import _const
    from ..neural.execution import Bind, Plan, Step
    for workflow, pattern in PATTERNS.items():
        match = pattern.fullmatch(goal)
        if not match:
            continue
        # Validation happens in the adapter: malformed paths/units never fall
        # through the generic planner after a recognized intent.
        data = {'workflow': workflow, 'relative_file': match[1]}
        if workflow == 'parameter':
            data.update(parameter_id=match[2], operation=match[3].lower(), value=float(match[4]), unit=match[5].strip())
        request = _const(journal, data, 'Report')
        return Plan(goal_id='g-'+uuid.uuid4().hex[:16], goal=goal, workflow='discovery.c1.'+workflow,
            steps=[Step(step_id='run', neuron=NODES[workflow], bind={'request': request}),
                   Step(step_id='check', neuron='discovery.verify.c1@v1',
                        bind={'request': request, 'report': Bind(step='run', port='report')}),
                   Step(step_id='answer', neuron='motor.report@v1',
                        bind={'report': Bind(step='run', port='report'), 'verdict': Bind(step='check', port='verdict')})],
            goal_verifier='check', answer_step='answer', graph_version=graph_version, deadline_s=45)
    return None


def compute(root, request, journal=None):
    raw = local_bytes(Path(root), request['relative_file'], limit=100_000)
    workflow = request['workflow']
    if workflow == 'asset':
        candidate = AssetCandidate.model_validate_json(raw)
        result = inspect_local(Path(root), candidate)
    else:
        project = Project.model_validate_json(raw)
        if workflow == 'project':
            result = ComponentGraph(project).describe()
        elif workflow == 'parameter':
            change = Change(parameter_id=request['parameter_id'], operation=request['operation'],
                            quantity=Quantity(value=request['value'], unit=request['unit'], origin='source',
                                              source_ref='user-parameter-request'))
            _, proposed = plan(project, change, journal=journal)
            result = proposed.model_dump(mode='json')
        else:
            raise ValueError('unknown C1 workflow')
    return {'workflow': workflow, 'input_sha256': hashlib.sha256(raw).hexdigest(), 'result': result}


def adapters(graph, journal):
    memory = LabMemory(journal)
    memory.migrate()
    for identity in (*NODES.values(), 'discovery.verify.c1@v1'):
        if identity in graph.neurons:
            memory.put(Capability(id=identity, neuron_id=identity, intents=('C1 scoped project/asset integrity',),
                                  golden_ref='tests/test_discovery_components.py',
                                  justification='Registered typed integrity adapter; no physical validation.'))

    def run(neuron, inputs, env):
        if env.cancelled():
            raise ValueError('C1 request cancelled before file read')
        root = Path(env.actions.base)
        result = compute(root, inputs['request'], journal)
        from ..agent_context import scoped
        from datetime import datetime, timezone
        locator = str(scoped(root, inputs['request']['relative_file']))
        source_id = 'c1-input-'+result['input_sha256']+'-'+hashlib.sha256(locator.encode()).hexdigest()[:12]
        if memory.get(source_id) is None:
            memory.put(Source(id=source_id, locator=locator, sha256=result['input_sha256'],
                              retrieved_at=datetime.now(timezone.utc).isoformat(),
                              justification='User-supplied local metadata; origin/accuracy and reuse rights not inferred.'))
        if inputs['request']['workflow'] == 'project':
            # Re-read/hash equality before persistence; never snapshot a different input.
            raw = local_bytes(root, inputs['request']['relative_file'], limit=100_000)
            if hashlib.sha256(raw).hexdigest() != result['input_sha256']:
                raise ValueError('project input changed during inspection')
            save(memory, Project.model_validate_json(raw))
        return {'report': result}

    def verify(neuron, inputs, env):
        problems = []
        try:
            expected = compute(Path(env.actions.base), inputs['request'], journal)
            if inputs['report'] != expected:
                problems.append('report differs from scoped input, units or dependency graph')
        except (ValueError, TypeError, KeyError, OSError, PermissionError):
            problems.append('input changed, invalid schema or unapproved parameter change')
        return {'verdict': {'passed': not problems, 'problems': problems,
                            'evidence': ['scoped input hash, typed graph/asset checks and deterministic replay'] if not problems else []}}

    return {**{identity: run for identity in NODES.values() if identity in graph.neurons},
            **({'discovery.verify.c1@v1': verify} if 'discovery.verify.c1@v1' in graph.neurons else {})}
