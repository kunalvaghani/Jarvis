"""Read-only typed projection of the real registry/dispatcher and scientific references.

The owned descriptors constrain existing code; they cannot register or execute a
new capability, change eligibility, or grant scientific verification.
"""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
from typing import Literal
from pydantic import Field,TypeAdapter,field_validator
from .contracts import StrictModel,Identifier,Capability,RECORD
from .catalog import enabled
from ..neural.contracts import Port

APP=Path(__file__).resolve().parents[2]
OWNED=Path(__file__).with_name('neurons')/'integration.json'


class Descriptor(StrictModel):
    node_id: Identifier
    family: Literal['foundations','components','pendulum','research','optimization','integration','delivery','mechanics','vehicle']
    registration_feature: Literal['enabled','sim','research']
    provider: str=Field(min_length=1,max_length=200)
    inputs: tuple[Port,...]
    outputs: tuple[Port,...]=Field(min_length=1)
    requires: tuple[Identifier,...]=()
    test_ref: str=Field(min_length=1,max_length=300)
    skill_ref: str=Field(min_length=1,max_length=300)
    memory_kinds: tuple[str,...]=Field(min_length=1)
    model_hint: Literal['none','existing_local_router','existing_local_choice']='none'

    @field_validator('memory_kinds')
    @classmethod
    def known_kinds(cls,value):
        if not set(value)<=set(RECORD.json_schema()['discriminator']['mapping']):raise ValueError('unknown scientific memory kind')
        return value

    @field_validator('test_ref','skill_ref')
    @classmethod
    def owned_reference(cls,value,info):
        pattern=r'tests/test_discovery_[a-z_]+\.py' if info.field_name=='test_ref' else r'jarvis/skills/discovery/[a-z][a-z0-9-]*/SKILL\.md'
        if not re.fullmatch(pattern,value):raise ValueError('reference outside the owned tests/skills namespace')
        return value


def descriptors():
    from ..skill_memory import linked
    if any(linked(p) for p in (OWNED,*OWNED.parents)) or OWNED.stat().st_size>100000:raise ValueError('invalid owned descriptor source')
    raw=OWNED.read_bytes()
    rows=TypeAdapter(tuple[Descriptor,...]).validate_json(raw)
    if len({r.node_id for r in rows})!=len(rows):raise ValueError('duplicate Lab descriptor')
    return rows


def _owned_file(relative):
    from ..skill_memory import linked
    p=APP/relative
    if not p.resolve().is_relative_to(APP) or any(linked(x) for x in (p,*p.parents)):raise ValueError('descriptor path escapes owned source')
    return p.read_bytes()


def inventory(graph,registry,adapters,memory,context):
    from ..neural.policy import eligibility
    from .memory_graph import qualification
    rows=descriptors();lookup={d.node_id:d for d in rows};issues=[];nodes=[]
    expected={d.node_id for d in rows if enabled(context.config,d.registration_feature)}
    actual={identity for identity in graph.neurons if identity.startswith('discovery.')}
    learned={}
    for identity in actual-lookup.keys():
        node=graph.neurons[identity]
        base=node.source.removeprefix('discovery-qualified:')
        if node.provider=='jarvis.neural.learning' and base in lookup:
            learned[identity]=lookup[base].model_copy(update={'node_id':identity,'requires':(base,)})
        else:issues.append({'code':'unmapped_neuron','id':identity})
    for identity in sorted(expected-actual):issues.append({'code':'missing_neuron','id':identity})
    for identity in sorted(actual-expected-learned.keys()):
        if identity in lookup:issues.append({'code':'unexpected_registration','id':identity})
    for identity in sorted(actual):
        node=graph.neurons[identity];d=learned.get(identity) or lookup.get(identity);cap=memory.get(identity)
        if not isinstance(cap,Capability) or cap.neuron_id!=identity:issues.append({'code':'missing_capability_record','id':identity})
        else:issues.extend(qualification(memory,registry,cap))
        handler=adapters.get(identity);ready=callable(handler)
        if not ready:issues.append({'code':'missing_handler','id':identity})
        deps=()
        if d:
            deps=d.requires
            if (node.contract!='explicit' or node.inputs!=d.inputs or node.outputs!=d.outputs
                    or (identity not in learned and node.provider!=d.provider)):
                issues.append({'code':'contract_drift','id':identity})
            if 'flag:lab.enabled' not in node.requirements or node.side_effect_class=='unknown':
                issues.append({'code':'unclassified_or_unguarded','id':identity})
            for dep in deps:
                if dep not in graph.neurons:issues.append({'code':'dangling_dependency','id':identity,'target':dep})
            try:
                # A test path is a reference to a check, never evidence that it ran.
                test_hash=hashlib.sha256(_owned_file(d.test_ref)).hexdigest()
                skill_hash=hashlib.sha256(_owned_file(d.skill_ref)).hexdigest()
            except Exception:
                issues.append({'code':'missing_owned_test_or_skill','id':identity});test_hash=skill_hash=None
        else:test_hash=skill_hash=None
        gate=eligibility(node,context)
        nodes.append({'node_id':identity,'version':node.version,'provider':node.provider,'contract':node.contract,
            'inputs':[p.model_dump() for p in node.inputs],'outputs':[p.model_dump() for p in node.outputs],
            'requires':list(deps),'status':node.status,'verification':cap.verification if isinstance(cap,Capability) else 'UNVERIFIED',
            'eligible':gate.eligible,'needs_approval':gate.needs_approval,'eligibility_reasons':gate.reasons,
            'handler_present':ready,'entrypoint':None if not ready else handler.__module__+':'+handler.__qualname__,
            'model_hint':d.model_hint if d else 'none','memory_kinds':list(d.memory_kinds) if d else [],
            'test_ref':d.test_ref if d else None,'test_sha256':test_hash,'skill_ref':d.skill_ref if d else None,'skill_sha256':skill_hash})
    import rustworkx as rx
    g=rx.PyDiGraph();indices={n['node_id']:g.add_node(n['node_id']) for n in nodes}
    for row in nodes:
        for target in row['requires']:
            if target in indices:g.add_edge(indices[row['node_id']],indices[target],None)
    if not rx.is_directed_acyclic_graph(g):issues.append({'code':'capability_dependency_cycle','id':'discovery'})
    for edge in graph.synapses:
        if edge.source.startswith('discovery.') or edge.target.startswith('discovery.'):
            source,target=graph.neurons.get(edge.source),graph.neurons.get(edge.target)
            if (source is None or target is None or not any(p.name==edge.out_port and p.type==edge.data_type for p in source.outputs)
                    or not any(p.name==edge.in_port and p.type==edge.data_type for p in target.inputs)):
                issues.append({'code':'synapse_endpoint_or_type','id':edge.edge_id})
    if registry.errors:issues.append({'code':'registry_errors','id':'registry','count':len(registry.errors)})
    return {'passed':not issues,'issues':issues,'nodes':nodes,'registered_count':len(actual),
            'descriptor_sha256':hashlib.sha256(OWNED.read_bytes()).hexdigest(),'qualification_scope':'contracts and retained proof, not physical validation'}


def diff(previous,current):
    before={n['node_id']:n for n in (previous or {}).get('nodes',[])};after={n['node_id']:n for n in current['nodes']}
    return {'added':sorted(after.keys()-before.keys()),'removed':sorted(before.keys()-after.keys()),
            'changed':sorted(k for k in before.keys()&after.keys() if before[k]!=after[k])}


def template_check(journal,config,graph):
    """Compile owned examples, check types/DAGs, execute nothing and read no files."""
    from ..neural.compiler import compile_goal
    from ..neural.execution import check
    commands=['lab status','lab convert 1 km to m','lab simulate divider 10 V 1000 ohm 1000 ohm',
        'Find a 2026 F1 car model and simulate vehicle dynamics; if no exact model exists, use a labelled surrogate.',
        'lab inspect project "fixture.json"','lab inspect asset "fixture.json"','lab plan parameter "fixture.json" length set 1 m',
        'lab simulate pendulum "fixture.json"','lab build pendulum "fixture.json"',
        'lab simulate mechanics "fixture.json"',
        'lab compare vehicle "fixture.json"','lab assets search "fixture model"',
        'lab assets inspect "'+('a'*32)+'"',
        'lab research "clocks"','lab lookup doi "10.1126/science.1192720"','lab review hypotheses "fixture.json"',
        'lab hypothesize "fixture"','lab hypothesize quick "fixture"','lab theory dilation "fixture.json"',
        'lab optimize "fixture.json"',*[f'lab optimize {op} "study-'+('a'*32)+'"' for op in ('step','status','pause','resume','cancel','queue')],
        'lab audit integration','lab memory wire',
        'lab export report "fixture.json"','lab export table "fixture.json"','lab export inspect "delivery-'+('a'*64)+'"',
        'lab source drive "fixture"','lab source drive-id "fixture_id_12345"','lab portal read "https://example.org/paper"',
        'lab read long "fixture.json"','lab background "optical clocks"','lab background doc "fixture.json"','lab choose "fixture.json"',
        *['lab jobs '+op+' "study-'+('a'*32)+'"' for op in ('queue','status','pause','resume','cancel')]]
    checked=[];issues=[]
    for command in commands:
        plan=compile_goal(command,journal,config,graph.version)
        # Templates intentionally absent when their flags are off.
        if plan is None:continue
        problems=check(plan,graph);checked.append(plan.workflow)
        if problems:issues.append({'code':'compiled_template_dependency','id':plan.workflow,'count':len(problems)})
    return {'passed':not issues,'issues':issues,'workflows':checked,'execution':'none'}
