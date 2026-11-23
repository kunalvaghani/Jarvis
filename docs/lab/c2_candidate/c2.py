"""C2 fixed mechanical slice: SciPy dynamics -> approved native Blender rig -> readback.

The existing brain owns routing, approvals, outbox, cancellation and Journal.
This module never downloads a solver or enables a UI/app/paid integration.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
import uuid
from jarvis.discovery.catalog import enabled
from jarvis.discovery.contracts import Capability, Component, Experiment, Parameter, Quantity, Representations, RunArtifact, Source
from jarvis.discovery.memory import LabMemory
from jarvis.discovery.adapters.assets import local_bytes
from jarvis.discovery.model.pendulum import Pendulum, solve, independent_checks, sha

REQUEST=re.compile(r'^\s*lab\s+(simulate|build)\s+pendulum\s+"([^"\r\n]{1,500})"\s*$',re.I)
NODES={'solve':'discovery.mechanics.pendulum@v1','math':'discovery.verify.pendulum@v1',
       'build':'discovery.geometry.pendulum@v1','native':'discovery.verify.pendulum_native@v1'}


def route_command(command):
    from jarvis.commands import Command
    if command.kind in ('task','ask') and command.extra in ('','unparsed') and REQUEST.fullmatch(command.value):
        return Command('task',command.value)
    return command


def neurons(config):
    from jarvis.neural.contracts import Neuron
    from jarvis.neural.registry import ports
    if not enabled(config):return []
    found=[]
    for key,identity in NODES.items():
        found.append(Neuron(node_id=identity,kind='verifier' if key in ('math','native') else 'skill',
            capability=identity.split('@')[0],provider='jarvis.discovery.c2',contract='explicit',
            inputs=ports(('request:Report',) if key=='solve' else ('request:Report','run:Report') if key=='math' else
                         ('run:Report','verdict:Verdict') if key=='build' else ('run:Report','native:Report')),
            outputs=ports(('verdict:Verdict',) if key in ('math','native') else ('report:Report',)),
            side_effect_class='local_write' if key=='build' else 'read_only',privilege='write' if key=='build' else 'read',
            runtime='local',requirements=('flag:lab.enabled','flag:lab.sim'),timeout_ms=120000,
            resource_cost={'gpu_vram_mb':0,'money':0,'cpu_s_estimate':60 if key=='build' else 5},
            source='jarvis/discovery/c2.py',description='Fixed C2 pendulum '+key+'; conditional model, no hardware'))
    return found


def sources(config,existing):return {**existing,'discovery_c2':lambda:neurons(config)}


def compile_goal(goal,journal,config,graph_version=0):
    match=REQUEST.fullmatch(goal)
    if not enabled(config) or not match:return None
    from jarvis.neural.compiler import _const
    from jarvis.neural.execution import Bind,Plan,Step
    request=_const(journal,{'relative_file':match[2]},'Report')
    steps=[Step(step_id='solve',neuron=NODES['solve'],bind={'request':request}),
           Step(step_id='math',neuron=NODES['math'],bind={'request':request,'run':Bind(step='solve',port='report')})]
    if match[1].lower()=='build':
        steps.extend([Step(step_id='build',neuron=NODES['build'],bind={'run':Bind(step='solve',port='report'),'verdict':Bind(step='math',port='verdict')}),
                      Step(step_id='native',neuron=NODES['native'],bind={'run':Bind(step='solve',port='report'),'native':Bind(step='build',port='report')})])
        verifier,producer='native','build'
    else:verifier,producer='math','solve'
    steps.append(Step(step_id='answer',neuron='motor.report@v1',bind={'report':Bind(step=producer,port='report'),'verdict':Bind(step=verifier,port='verdict')}))
    return Plan(goal_id='g-'+uuid.uuid4().hex[:16],goal=goal,workflow='discovery.c2.'+match[1].lower(),steps=steps,
                goal_verifier=verifier,answer_step='answer',graph_version=graph_version,deadline_s=300)


def code_hash():
    from jarvis.discovery.model import pendulum
    return hashlib.sha256(Path(pendulum.__file__).read_bytes()).hexdigest()


def adapters(graph,journal):
    memory=LabMemory(journal);memory.migrate()
    for identity in NODES.values():
        if identity in graph.neurons:
            memory.put(Capability(id=identity,neuron_id=identity,intents=('bounded rigid pendulum',),
                                  golden_ref='tests/test_discovery_pendulum.py',
                                  justification='Static trusted adapter; scientific credibility is scoped per run.'))

    def actual(report):
        rows=journal.rows('SELECT code_sha256 FROM discovery_pendulum_runs WHERE ref=?',(report['run_ref'],))
        if not rows or rows[0]['code_sha256']!=code_hash():raise ValueError('missing or changed actual solver receipt')
        result=json.loads(journal.get(report['run_ref']))
        return Pendulum.model_validate_json(json.dumps(result['model'])),result

    def run(neuron,inputs,env):
        from jarvis.discovery.sandbox.local_trials import reserve
        from jarvis.discovery.sandbox.budget import Budget
        if env.cancelled():raise ValueError('cancelled before input read')
        raw=local_bytes(Path(env.actions.base),inputs['request']['relative_file'],limit=16000)
        spec=Pendulum.model_validate_json(raw)
        request_ref=journal.put({'file':inputs['request']['relative_file'],'sha256':hashlib.sha256(raw).hexdigest(),
                                 'model':spec.model_dump(mode='json')},data_type='Report')
        reserve('scipy-pendulum',request_ref)
        budget=Budget(journal);reservation='pendulum-'+uuid.uuid4().hex
        budget.reserve(reservation,cpu_s=5,disk_bytes=500000)
        try:
            result=solve(spec,cancelled=env.cancelled);result['input_sha256']=hashlib.sha256(raw).hexdigest()
            result['relative_file']=inputs['request']['relative_file']
            ref=journal.put(result,data_type='Report')
            with journal.tx() as db:
                db.execute('CREATE TABLE IF NOT EXISTS discovery_pendulum_runs (ref TEXT PRIMARY KEY,code_sha256 TEXT NOT NULL)')
                db.execute('INSERT OR IGNORE INTO discovery_pendulum_runs VALUES (?,?)',(ref,code_hash()))
            identity='pendulum-'+uuid.uuid4().hex[:16]
            source_id=identity+'-input';memory.put(Source(id=source_id,locator=inputs['request']['relative_file'],
                sha256=result['input_sha256'],justification='User-supplied ideal-model inputs, not measured hardware.'))
            artifact=identity+'-numeric';memory.put(RunArtifact(id=artifact,locator=ref,
                sha256=hashlib.sha256(journal.get(ref).encode()).hexdigest(),media_type='application/json',source_ids=(source_id,),
                evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',justification='SciPy output with independent model checks.'))
            metrics={name:Quantity(value=value,unit='s',origin='solver',source_ref=ref) if value is not None else Quantity(unit='s')
                     for name,value in result['metrics'].items() if name in ('measured_period_s','undamped_period_reference_s')}
            memory.put(Experiment(id=identity,design_sha256=result['design_sha256'],scenario_sha256=result['scenario_sha256'],
                solver=result['solver'],solver_version=result['solver_version'],metrics=metrics,artifact_ids=(artifact,),
                evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',justification='Ideal rigid pendulum; no physical validation.'))
            budget.settle(reservation,cpu_s=result['cpu_s'],disk_bytes=len(journal.get(ref).encode()))
            return {'report':{'run_ref':ref,'experiment_id':identity,'model':result['model'],'metrics':result['metrics'],
                              'solver':result['solver'],'solver_version':result['solver_version'],
                              'evidence_status':result['evidence_status'],'assumptions':result['assumptions']}}
        except BaseException:budget.settle(reservation,uncertain=True);raise

    def verify_math(neuron,inputs,env):
        problems=[]
        try:
            spec,result=actual(inputs['run']);metrics=independent_checks(spec,result)
            raw=local_bytes(Path(env.actions.base),inputs['request']['relative_file'],limit=16000)
            if hashlib.sha256(raw).hexdigest()!=result['input_sha256'] or metrics!=inputs['run']['metrics']:
                problems.append('source/metric provenance differs')
        except Exception:problems.append('independent numerical or provenance check failed')
        return {'verdict':{'passed':not problems,'problems':problems,'evidence':['rigid constraint, ODE, energy, nonlinear period'] if not problems else []}}

    def build(neuron,inputs,env):
        from jarvis.discovery.adapters.blender_pendulum import native
        if inputs['verdict'].get('passed') is not True:raise ValueError('numeric model did not verify')
        spec,result=actual(inputs['run'])
        current=local_bytes(Path(env.actions.base),result['relative_file'],limit=16000)
        if hashlib.sha256(current).hexdigest()!=result['input_sha256']:
            raise ValueError('model file changed while awaiting approval; no native files created')
        root=Path(env.actions.base)/'.jarvis-runtime/discovery/experiments'
        from jarvis.skill_memory import linked
        if any(linked(p) for p in (root,*root.parents)):raise ValueError('linked experiment root')
        root.mkdir(parents=True,exist_ok=True)
        folder=root/inputs['run']['experiment_id'];folder.mkdir(exist_ok=False)
        output=folder/'pendulum.blend'
        (folder/'model.json').write_text(spec.model_dump_json(indent=2),encoding='utf-8')
        (folder/'numeric.json').write_text(json.dumps(result,allow_nan=False),encoding='utf-8')
        with (folder/'trajectory.csv').open('x',newline='',encoding='utf-8') as handle:
            writer=csv.DictWriter(handle,fieldnames=['t_s','theta_rad','omega_rad_s','x_m','z_m']);writer.writeheader();writer.writerows(result['samples'])
        ids={name:str(uuid.uuid5(uuid.NAMESPACE_URL,spec.project_id+':'+name)) for name in ('anchor','rod','bob')}
        request={'operation':'create','output':str(output),'run':result,'component_ids':ids}
        from jarvis.discovery.adapters import blender_pendulum
        (folder/'build_source.py').write_bytes(blender_pendulum.TEMPLATE.read_bytes())
        rig={'component_ids':ids,'joint':'revolute about Y','native_hinge':'anchor->bob','bob_mass_kg':spec.mass_kg,
             'inertia_about_pivot_kg_m2':result['metrics']['inertia_about_pivot_kg_m2'],
             'native_bob_mode':'kinematic; motion from SciPy','connector_mass_assumption':'ideal massless',
             'authoritative_numeric_solver':result['solver'],'bullet_dynamics_tested':False}
        (folder/'rig.json').write_text(json.dumps(rig,indent=2),encoding='utf-8')
        observed=native(env.actions,request,journal=journal,cancelled=env.cancelled)
        return {'report':{'directory':str(folder),'run_ref':inputs['run']['run_ref'],'experiment_id':inputs['run']['experiment_id'],
                          'component_ids':ids,'created':observed,'metrics':result['metrics'],
                          'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS',
                          'justification':'Native rig/animation displays actual SciPy trace; no Bullet or physical validation.'}}

    def verify_native(neuron,inputs,env):
        from jarvis.discovery.adapters.blender_pendulum import native
        problems=[]
        try:
            report=inputs['native'];spec,result=actual(inputs['run']);folder=Path(report['directory'])
            observed=native(env.actions,{'operation':'inspect','output':str(folder/'pendulum.blend'),
                'run':result,'component_ids':report['component_ids']},journal=journal,cancelled=env.cancelled)
            if (observed['model_sha256']!=sha(result['model']) or observed['trajectory_sha256']!=sha(result['samples'])
                    or {p['component_id'] for p in observed['parts']}!=set(report['component_ids'].values())):
                problems.append('native source/trajectory/component identity differs')
            from PIL import Image
            with Image.open(folder/'pendulum.png') as image:
                if image.size!=(480,480):raise ValueError('render size differs')
                image.verify()
            artifacts=[]
            for filename in ('pendulum.blend','pendulum.obj','pendulum.png','model.json','numeric.json','trajectory.csv','rig.json','build_source.py'):
                path=folder/filename
                if not path.is_file() or path.stat().st_size>16000000:raise ValueError('native artifact missing/oversized')
                identity=report['experiment_id']+'-'+filename.replace('.','-')
                memory.put(RunArtifact(id=identity,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),locator=str(path),
                    media_type='image/png' if filename.endswith('.png') else 'application/octet-stream',
                    evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',justification='Actual owned native/numeric output; no physical validation.'))
                artifacts.append(identity)
            for name,identity in report['component_ids'].items():
                old=memory.get(identity);revision=old.revision+1 if old else 1
                mass=Quantity(value=spec.mass_kg,unit='kg',origin='source',source_ref=inputs['run']['run_ref']) if name=='bob' else Quantity(unit='kg')
                memory.put(Component(id=identity,revision=revision,name='Pendulum '+name,reality_class='P1',mass=mass,
                    missing=('material/strength not modeled',),representations=Representations(native=str(folder/'pendulum.blend'),
                     visual=str(folder/'pendulum.obj'),functional=str(folder/'rig.json'),physical=str(folder/'model.json'))))
            previous=memory.get(report['experiment_id'])
            memory.put(Experiment(**{**previous.model_dump(), 'revision':previous.revision+1,
                                     'artifact_ids':tuple((*previous.artifact_ids,*artifacts))}))
        except Exception:problems.append('native independent readback or output verification failed')
        return {'verdict':{'passed':not problems,'problems':problems,'evidence':['fresh Blender readback; manifold mesh; native hinge/mass; solver-driven positions; real PNG and file hashes'] if not problems else []}}

    return {identity:handler for identity,handler in ((NODES['solve'],run),(NODES['math'],verify_math),(NODES['build'],build),(NODES['native'],verify_native)) if identity in graph.neurons}
