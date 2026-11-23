"""Conditional vehicle comparisons and independent checks in the existing brain.

No second planner, scheduler, memory or approval authority. A verified numerical
comparison remains separate from asset/reconstruction/full Test A acceptance.
"""
import hashlib,json,re,uuid
from pathlib import Path
from .catalog import enabled
from .contracts import Capability,RunArtifact,Source
from .memory import LabMemory
from .model.vehicle import VehicleCase,validate_result
from .adapters import chrono

PATTERN=re.compile(r'^\s*lab compare vehicle "([^"\r\n]{1,500})"\s*$',re.I)
NODES={'run':'discovery.vehicle.compare@v1','check':'discovery.verify.vehicle_compare@v1'}


def neurons(config):
    if not enabled(config,'sim'):return []
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    return [Neuron(node_id=node,version=1,kind='verifier' if key=='check' else 'skill',
        capability='discovery.vehicle.'+key,provider='jarvis.discovery.vehicle_flow',contract='explicit',
        inputs=ports(('request:Report',)+(('report:Report',) if key=='check' else ())),
        outputs=ports(('verdict:Verdict',) if key=='check' else ('report:Report',)),
        side_effect_class='read_only',privilege='read',runtime='local',
        requirements=('flag:lab.enabled','flag:lab.sim'),timeout_ms=125000,
        resource_cost={'gpu_vram_mb':0,'money':0,'cpu_s_estimate':100 if key=='run' else 1},
        description='Conditional controlled Chrono vehicle comparison, fixed assumed topology, owned artifacts only; no full Test A promotion',
        source='jarvis/discovery/vehicle_flow.py')
        for key,node in NODES.items()]


def sources(config,previous):
    return {**previous,'discovery_vehicle':lambda:neurons(config)}


def compile_goal(goal,journal,config,graph_version=0):
    match=PATTERN.fullmatch(goal)
    if not enabled(config,'sim') or not match:return None
    from ..neural.compiler import _const
    from ..neural.execution import Bind,Plan,Step
    request=_const(journal,{'relative_file':match[1]},'Report')
    return Plan(goal_id='g-'+uuid.uuid4().hex[:16],goal=goal,workflow='discovery.vehicle.compare',
        steps=[Step(step_id='run',neuron=NODES['run'],bind={'request':request}),
               Step(step_id='check',neuron=NODES['check'],bind={'request':request,'report':Bind(step='run',port='report')}),
               Step(step_id='answer',neuron='motor.report@v1',bind={'report':Bind(step='run',port='report'),
                    'verdict':Bind(step='check',port='verdict')})],goal_verifier='check',answer_step='answer',
        graph_version=graph_version,deadline_s=130)


def adapters(graph,journal):
    memory=LabMemory(journal);memory.migrate()
    with journal.tx() as db:
        db.execute('CREATE TABLE IF NOT EXISTS discovery_vehicle_runs '
                   '(ref TEXT PRIMARY KEY,input_sha256 TEXT,worker_sha256 TEXT,request_ref TEXT)')
    for node in NODES.values():
        if node in graph.neurons:
            memory.put(Capability(id=node,neuron_id=node,intents=('controlled vehicle comparison',),
                golden_ref='tests/test_discovery_vehicle.py',
                justification='Conditional assumed-topology Chrono dynamics; no exact F1 asset or full A acceptance promotion.'))

    def read(inputs,env):
        from .adapters.assets import local_bytes
        raw=local_bytes(Path(env.actions.base),inputs['request']['relative_file'],16000)
        from .vehicle_wire import parse
        case=parse(raw)
        for ref in case.source_refs:
            source=memory.get(ref)
            if not isinstance(source,Source) or not source.sha256:
                raise ValueError('Each source_ref must resolve to an actual retained hashed Source; a supplied URL alone is insufficient')
        return raw,case

    def perform(neuron,inputs,env):
        raw,case=read(inputs,env)
        env.actions.report('brain','Lab vehicle: validating the fixed scenario and source references; baseline/candidate CPU runs are starting.')
        ref,result=chrono.run(case,journal,env.cancelled)
        sha=hashlib.sha256(raw).hexdigest();request_ref=journal.put(case.model_dump(mode='json'),'Report')
        with journal.tx() as db:
            db.execute('INSERT INTO discovery_vehicle_runs VALUES (?,?,?,?)',(ref,sha,result['worker_sha256'],request_ref))
        memory.put(RunArtifact(id='vehicle-'+ref.rsplit('/',1)[-1],locator=ref,
            sha256=hashlib.sha256(journal.get(ref).encode()).hexdigest(),media_type='application/json',
            source_ids=case.source_refs,evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',
            justification='Actual Chrono::Vehicle baseline/candidate outputs under declared surrogate assumptions; no physical or full A validation.'))
        env.actions.report('brain','Lab vehicle: both solver runs completed; independently checking the raw traces, zone modes and unchanged scenario.')
        return {'report':{'run_ref':ref,'input_sha256':sha,'worker_sha256':result['worker_sha256'],
            'native_project':result['native_project'],'metrics':{r['variant']:r['metrics'] for r in result['runs']},
            'limitations':result['limitations'],'physical_validation':False,'full_A_acceptance_passed':False,
            'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS'}}

    def check(neuron,inputs,env):
        problems=[]
        try:
            raw,case=read(inputs,env);sha=hashlib.sha256(raw).hexdigest();public=inputs['report'];ref=public['run_ref']
            receipt=journal.rows('SELECT * FROM discovery_vehicle_runs WHERE ref=?',(ref,))
            if len(receipt)!=1 or receipt[0]['input_sha256']!=sha or receipt[0]['worker_sha256']!=chrono.worker_hash():
                raise ValueError('actual matching current-worker execution receipt required')
            from ..neural.contracts import artifact_ref
            body=journal.get(ref)
            if artifact_ref(body)!=ref:raise ValueError('solver artifact checksum mismatch')
            result=json.loads(body);validate_result(case,result)
            base=Path(env.actions.base).resolve();root=(base/result['native_project']).resolve()
            if not root.is_relative_to(base/'.jarvis-runtime/discovery/vehicle-runs'):
                raise ValueError('native project escaped owned outputs')
            from ...skill_memory import linked
            for name,digest in result['native_sha256'].items():
                if Path(name).name!=name:raise ValueError('native file path invalid')
                path=root/name
                if linked(path) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                    raise ValueError('native solver files changed')
            if (public['native_project']!=result['native_project'] or public['input_sha256']!=sha
                    or public['worker_sha256']!=result['worker_sha256']
                    or public['metrics']!={r['variant']:r['metrics'] for r in result['runs']}
                    or public['physical_validation'] is not False or public['full_A_acceptance_passed'] is not False):
                raise ValueError('published summary differs from actual run')
        except Exception as exc:problems.append(type(exc).__name__+': '+str(exc)[:400])
        env.actions.report('brain','Lab vehicle: '+('conditional comparison verified; full asset/track/top-speed acceptance still required.' if not problems else 'verification failed; the model must correct the reported problem without replaying an uncertain run.'))
        return {'verdict':{'passed':not problems,'problems':problems,
            'evidence':['actual current-worker Chrono receipt, native JSON and independently checked controlled traces'] if not problems else []}}
    return {node:({'run':perform,'check':check}[key]) for key,node in NODES.items() if node in graph.neurons}
