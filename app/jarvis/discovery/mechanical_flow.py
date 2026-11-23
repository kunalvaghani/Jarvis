"""Generic primitive mechanics as two neurons in the existing neural brain."""
import hashlib
import json
from pathlib import Path
import re
import uuid

from .catalog import enabled
from .contracts import Capability,Source,RunArtifact
from .memory import LabMemory
from .model.mechanics import MechanicsCase,validate_result
from .adapters import mechanics

PATTERN=re.compile(r'^\s*lab simulate mechanics "([^"\r\n]{1,500})"\s*$',re.I)
NODES={'run':'discovery.mechanics.primitive@v1','check':'discovery.verify.primitive@v1'}


def neurons(config):
    if not enabled(config,'sim'):return []
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    return [Neuron(node_id=node,kind='verifier' if key=='check' else 'skill',capability=node.split('@')[0],
        provider='jarvis.discovery.mechanical_flow',contract='explicit',
        inputs=ports(('request:Report','report:Report') if key=='check' else ('request:Report',)),
        outputs=ports(('verdict:Verdict',) if key=='check' else ('report:Report',)),
        side_effect_class='read_only',privilege='read',runtime='local',
        requirements=('flag:lab.enabled','flag:lab.sim'),timeout_ms=35000,
        resource_cost={'gpu_vram_mb':0,'money':0,'cpu_s_estimate':20 if key=='run' else 1},
        description='Bounded primitive MuJoCo CPU mechanics; explicit SI inputs; no contacts, external meshes or generated code',
        source='jarvis/discovery/mechanical_flow.py') for key,node in NODES.items()]


def sources(config,existing):return {**existing,'discovery_mechanics':lambda:neurons(config)}


def compile_goal(goal,journal,config,graph_version=0):
    match=PATTERN.fullmatch(goal)
    if not enabled(config,'sim') or not match:return None
    from ..neural.compiler import _const
    from ..neural.execution import Bind,Plan,Step
    request=_const(journal,{'relative_file':match[1]},'Report')
    return Plan(goal_id='g-'+uuid.uuid4().hex[:16],goal=goal,workflow='discovery.mechanics.primitive',
        steps=[Step(step_id='run',neuron=NODES['run'],bind={'request':request}),
               Step(step_id='check',neuron=NODES['check'],bind={'request':request,'report':Bind(step='run',port='report')}),
               Step(step_id='answer',neuron='motor.report@v1',bind={'report':Bind(step='run',port='report'),
                   'verdict':Bind(step='check',port='verdict')})],
        goal_verifier='check',answer_step='answer',graph_version=graph_version,deadline_s=40)


def adapters(graph,journal):
    memory=LabMemory(journal);memory.migrate()
    with journal.tx() as db:
        db.execute('CREATE TABLE IF NOT EXISTS discovery_primitive_runs '
                   '(ref TEXT PRIMARY KEY,input_sha256 TEXT,worker_sha256 TEXT,request_ref TEXT)')
    for node in NODES.values():
        if node in graph.neurons:
            memory.put(Capability(id=node,neuron_id=node,intents=('primitive rigid mechanics',),
                golden_ref='tests/test_discovery_mechanics.py',
                justification='Canonical solver checks are separate from end-to-end autonomous or physical validation.'))

    def perform(neuron,inputs,env):
        if not mechanics.qualification()['runtime_ready']:
            raise ValueError('Current mechanics worker needs approved canonical qualification')
        from .adapters.assets import local_bytes
        raw=local_bytes(Path(env.actions.base),inputs['request']['relative_file'],32000)
        case=MechanicsCase.model_validate_json(raw)
        ref,report=mechanics.run(case,journal=journal,cancelled=env.cancelled)
        digest=hashlib.sha256(raw).hexdigest()
        request_ref=journal.put(case.model_dump(mode='json'),'Report')
        with journal.tx() as db:
            db.execute('INSERT INTO discovery_primitive_runs VALUES (?,?,?,?)',
                       (ref,digest,report['worker_sha256'],request_ref))
        source_id='primitive-input-'+digest
        memory.put(Source(id=source_id,locator=inputs['request']['relative_file'],sha256=digest,
            justification='Explicit input-file assumptions, not independently measured properties or verified source claims.'))
        memory.put(RunArtifact(id='primitive-'+ref.rsplit('/',1)[-1],locator=ref,
            sha256=hashlib.sha256(journal.get(ref).encode()).hexdigest(),media_type='application/json',
            source_ids=(source_id,),evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',
            justification='Actual CPU MuJoCo trajectory and editable MJCF; no contact, stress or physical validation.'))
        return {'report':{'run_ref':ref,'input_sha256':digest,'solver':'mujoco','version':'3.17.0',
            'worker_sha256':report['worker_sha256'],'sample_count':len(report['samples']),
            'final':report['samples'][-1],'native_mjcf':report['mjcf'],'contacts_modeled':False,
            'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS','physical_validation':False}}

    def check(neuron,inputs,env):
        problems=[]
        try:
            from .adapters.assets import local_bytes
            raw=local_bytes(Path(env.actions.base),inputs['request']['relative_file'],32000)
            digest=hashlib.sha256(raw).hexdigest();case=MechanicsCase.model_validate_json(raw)
            public=inputs['report'];ref=public['run_ref']
            receipt=journal.rows('SELECT * FROM discovery_primitive_runs WHERE ref=?',(ref,))
            if not receipt or receipt[0]['input_sha256']!=digest:raise ValueError('actual matching execution receipt required')
            if receipt[0]['worker_sha256']!=mechanics.environment()['worker_sha256']:raise ValueError('worker changed')
            from ..neural.contracts import artifact_ref
            body=journal.get(ref)
            if artifact_ref(body)!=ref:raise ValueError('solver artifact checksum changed')
            report=json.loads(body);validate_result(case,report)
            if (public['native_mjcf']!=report['mjcf'] or public['final']!=report['samples'][-1]
                    or public['input_sha256']!=digest or public['physical_validation'] is not False):
                raise ValueError('published report differs from actual solver artifact')
        except Exception:problems.append('independent input, trajectory or solver-receipt verification failed')
        return {'verdict':{'passed':not problems,'problems':problems,
            'evidence':['actual MuJoCo receipt and finite SI trajectory; current worker qualified against analytic goldens; no physical validation'] if not problems else []}}
    return {node:({'run':perform,'check':check}[key]) for key,node in NODES.items() if node in graph.neurons}
