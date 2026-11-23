"""Deterministic Scenario A workflow within the existing neural brain.

Every stage journals its typed inputs, accepted output and evidence delta.
No parallel model planner, database, installer or permission authority.
"""
import csv,hashlib,io,json,time,uuid
from pathlib import Path
from typing import Any,Optional
from ..neural.execution import Plan
from .model.scenario_a import STAGES,resolve,Target,action_arguments,target_query
from .scenario_journal import StageJournal,digest,BlockedStage
from .scenario_checks import verify_stage,compare
from .contracts import Capability,Source
from .memory import LabMemory
from .catalog import enabled

NODES=('discovery.vehicle.scenario@v1','discovery.verify.vehicle_scenario@v1')


def neurons(config):
    if not enabled(config,'sim'):return []
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    return [Neuron(node_id=node,kind='workflow' if i==0 else 'verifier',capability=node.split('@')[0],
        provider='jarvis.discovery.scenario_project',contract='explicit',
        inputs=ports(('request:Report',) if i==0 else ('request:Report','report:Report')),
        outputs=ports(('report:Report',) if i==0 else ('verdict:Verdict',)),
        side_effect_class='local_write' if i==0 else 'read_only',privilege='write' if i==0 else 'read',
        requirements=('flag:lab.enabled','flag:lab.sim','flag:lab.research'),timeout_ms=900000,
        resource_cost={'gpu_vram_mb':0,'money':0,'cpu_s_estimate':110 if i==0 else 2},
        description='Staged licensed vehicle acquisition and conditional simulation; owned project files only; procedural fallback requires explicit permission',
        source='jarvis/discovery/scenario_project.py') for i,node in enumerate(NODES)]


def sources(config,previous):return {**previous,'discovery_scenario_a':lambda:neurons(config)}


def compile_goal(goal:str,journal:Any,config:Any,graph_version:int=0)->Optional[Plan]:
    if not enabled(config,'sim'):return None
    target=resolve(goal)
    if target is None:return None
    from ..neural.compiler import _const
    from ..neural.execution import Bind,Plan,Step
    request=_const(journal,{'goal':goal},'Report')
    return Plan(goal_id='g-'+uuid.uuid4().hex[:16],goal=goal,workflow='discovery.vehicle.scenario',
        graph_version=graph_version,deadline_s=900,
        steps=[Step(step_id='project',neuron=NODES[0],bind={'request':request}),
            Step(step_id='verify_project',neuron=NODES[1],bind={'request':request,'report':Bind(step='project',port='report')}),
            Step(step_id='answer',neuron='motor.report@v1',bind={'report':Bind(step='project',port='report'),'verdict':Bind(step='verify_project',port='verdict')})],
        goal_verifier='verify_project',answer_step='answer')


def write(root,name,value):
    if Path(name).name!=name:raise ValueError('owned leaf filename required')
    body=value if isinstance(value,bytes) else json.dumps(value,indent=2,allow_nan=False).encode()
    path=root/name
    if path.exists():
        if path.read_bytes()!=body:raise ValueError('immutable project artifact differs; no overwrite')
    else:
        with path.open('xb') as stream:stream.write(body)
    return path


def file_manifest(base,paths):return {p.relative_to(base).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def artifact(journal,state,stage):
    from .acceptance import artifact as load
    return load(journal,state.stage_artifacts[stage])['facts']


def plot_trace(root,report):
    from PIL import Image,ImageDraw
    image=Image.new('RGB',(1000,650),'#101820');draw=ImageDraw.Draw(image)
    draw.text((25,15),'Actual Chrono output: fixed road experiment; not measured F1 performance',fill='white')
    for panel,(label,key) in enumerate([('Speed (m/s)','speed_m_s'),('Mechanical engine energy (J)','mechanical_engine_energy_j')]):
        top=60+panel*290;draw.rectangle((65,top,950,top+240),outline='#53616a')
        maximum=max(row[key] for run in report['runs'] for row in run['samples']) or 1
        draw.text((70,top+5),label+f'; displayed maximum {maximum:.6g}',fill='white')
        for run,color in zip(report['runs'],('#72cde0','#ffbc70')):
            points=[(65+885*row['time_s']/report['inputs']['duration_s'],top+235-210*row[key]/maximum) for row in run['samples']]
            draw.line(points,fill=color,width=2)
    draw.text((70,635),'Blue: baseline; orange: candidate; axes use actual recorded samples',fill='white')
    path=root/'dynamics.png';image.save(path);return path


def actions_for(stage,state,target,base,journal,actions,root,cancelled):
    """Closed stage-action registry: no model-selected shell/code/asset IDs."""
    from .acceptance import artifact as load
    facts={};paths=[]
    previous=lambda name:artifact(journal,state,name)
    if stage=='resolve_target':facts=target.model_dump(mode='json')
    elif stage=='requirements_and_sources':
        from .adapters.fia_sources import acquire
        record=acquire(base,target.year)
        source=Source(id=f"fia-{target.year}-"+record['sha256'],locator=record['url'],sha256=record['sha256'],
            retrieved_at=record['retrieved_at'],author='FIA',license='FIA copyright; source document only',
            justification='Edition-specific official regulations; extracted envelope constraints do not establish complete regulatory compliance.')
        LabMemory(journal).put(source);facts={'regulation':record,'source_refs':[source.id]};paths=[base/record['cached_pdf']]
    elif stage=='discover_assets':
        from ..tools import ToolRegistry
        query=target_query(target)
        step={'action':'discovery_call','value':f'lab assets search "{query}"','content':'','expected':'Read exact-season public asset metadata'}
        # The same registry/compiler/dispatcher and independent source verifier
        # used by ordinary tasks handle this read; this is not operator data.
        try:
            response=json.loads(ToolRegistry(actions).execute(step,cancelled).evidence)
            if response.get('verified') is not True:raise ValueError('asset source child not verified')
            rows=journal.rows('SELECT result_ref FROM outbox WHERE goal_id=? AND node_id=? AND state=?',
                (response['goal_id'],'discovery.assets.search_public@v1','done'))
            if len(rows)!=1:raise ValueError('actual asset-source receipt missing')
            result=load(journal,load(journal,rows[0]['result_ref'])['report'])['result']
            facts={'query':query,'candidates':result['items'],'source_ref':result['source_ref'],
                'payload_sha256':result['payload_sha256'],'source_goal_id':response['goal_id'],'provider_failure':None}
        except Exception as exc:
            if cancelled():raise
            facts={'query':query,'candidates':[],'source_ref':None,'provider_failure':type(exc).__name__+': '+str(exc)[:600]}
    elif stage=='validate_provenance':
        candidates=previous('discover_assets')['candidates'];decisions=[]
        for item in candidates:
            license=item.get('license_declared');name=item['name']
            reason=('missing license declaration' if not license else 'season name mismatch' if str(target.year) not in name
                else 'metadata cannot establish inspected native geometry or exact team engineering identity; binary acquisition not authorized/authenticated by this adapter')
            decisions.append({'uid':item['uid'],'name':name,'license_declared':license,'decision':'NOT_ENGINEERING_QUALIFIED','reason':reason})
        facts={'reviewed_ids':[i['uid'] for i in candidates],'decisions':decisions,'exact_engineering_identity_verified':False}
    elif stage=='inspect_asset':
        if not target.allow_surrogate:
            from .asset_pipeline import run as acquire_geometry
            result=acquire_geometry(actions,journal,target_query(target),target_year=target.year,cancelled=cancelled)
            from .adapters.asset_inspection import verify_inspection
            observed=verify_inspection(base,journal,result['inspection_ref'])
            facts={'decision':'ACQUIRED_VISUAL_ASSET','geometry_acquired':True,'target_year':target.year,
                'original_goal_hash':digest(target.goal),'geometry_result':result,
                'download_ref':observed['receipt']['download_ref'],'inspection_ref':result['inspection_ref'],
                'exact_team_cad':False,'physical_validation':False,
                'reason':'Actual licensed source geometry; engineering identity and hidden mechanics remain separate verification gates.'}
            facts['decision_hash']=digest(facts)
            paths=[write(root,'asset-license-'+facts['decision_hash'][:16]+'.json',facts)]
            return {'stage':stage,'facts':facts,'files':file_manifest(base,paths)}
        facts={'decision':'SURROGATE_REQUIRED','geometry_acquired':False,'target_year':target.year,
            'original_goal_hash':digest(target.goal),'regulation_source_refs':previous('requirements_and_sources')['source_refs'],
            'reason':'No inspected engineering asset is available from the configured bounded source path. This does not claim no such asset exists anywhere.',
            'fallback_scope':'explicit surrogate fallback in the original request; no third-party mesh copied',
            'exact_team_cad':False}
        facts['decision_hash']=digest(facts)
        paths=[write(root,'asset_license.json',{'decision':facts,'reviews':previous('validate_provenance')})]
    elif stage=='generate_parametric_surrogate':
        if previous('inspect_asset')['decision']=='ACQUIRED_VISUAL_ASSET':
            raise BlockedStage('acquired source geometry retained; source-informed mechanical assembly must qualify before vehicle simulation; no procedural substitute was dispatched')
        from .vehicle_recipe import build,uncertainty
        from .vehicle_geometry import build as geometry
        refs=list(previous('requirements_and_sources')['source_refs']);source=previous('discover_assets').get('source_ref')
        if source:refs.append(source)
        case=build(target,previous('requirements_and_sources')['regulation'],refs)
        result=geometry(root,case)
        paths=[root/name for name in result['files']]
        paths.extend([write(root,'solver_configuration.json',case.model_dump(mode='json')),write(root,'uncertainties.json',uncertainty(case))])
        facts={'case':case.model_dump(mode='json'),'manifest':(root/'geometry_manifest.json').relative_to(base).as_posix(),
            'glb':(root/'asset_or_surrogate.glb').relative_to(base).as_posix(),'checks':result['checks']}
    elif stage=='assemble_physical_vehicle':
        from .model.vehicle import VehicleCase
        from .adapters import chrono
        if not chrono.qualification()['runtime_ready']:raise BlockedStage('blocked_requires_qualification: current fixed Chrono worker/environment is unavailable')
        case=VehicleCase.model_validate_json(json.dumps(previous('generate_parametric_surrogate')['case']))
        ref,report=chrono.run(case,journal,cancelled,prepare=True)
        paths=[base/report['native_project']/name for name in report['native_sha256']]
        path=write(root,'physical_model.json',{'prepared_ref':ref,'native_project':report['native_project'],
            'physical_inventory':report['physical_inventory'],'visual_geometry_manifest':previous('generate_parametric_surrogate')['manifest']})
        license_path=chrono.HOME/'licenses/Chrono-10.0.0-LICENSE.txt'
        license_bytes=license_path.read_bytes()
        if hashlib.sha256(license_bytes).hexdigest()!='5f625eb4c9e0ddf86db9d1ed9b6adb5b30296ea81919282b2f38c977136bf079':
            raise ValueError('reviewed upstream BSD license bytes changed')
        paths.extend([path,write(root,'LICENSE-CHRONO.txt',license_bytes)])
        facts={'prepared_ref':ref,'physical_manifest':path.relative_to(base).as_posix(),
            'upstream_license_file':(root/'LICENSE-CHRONO.txt').relative_to(base).as_posix()}
    elif stage=='validate_model':facts={'prepared_ref':previous('assemble_physical_vehicle')['prepared_ref']}
    elif stage=='simulate':
        from .model.vehicle import VehicleCase
        from .adapters import chrono
        case=VehicleCase.model_validate_json(json.dumps(previous('generate_parametric_surrogate')['case']))
        ref,report=chrono.run(case,journal,cancelled,study=True);facts={'study_ref':ref,'slot':report['slot']}
        for child in report['reports'].values():paths.extend(base/child['native_project']/name for name in child['native_sha256'])
    elif stage=='independently_check':
        from .model.vehicle import VehicleCase
        from .vehicle_checks import study
        ref=previous('simulate')['study_ref'];case=VehicleCase.model_validate_json(json.dumps(previous('generate_parametric_surrogate')['case']))
        facts={'study_ref':ref,'verification':study(case,load(journal,ref))}
        paths=[write(root,'verification_report.json',facts)]
    elif stage=='compare':facts=compare(load(journal,previous('simulate')['study_ref']))
    elif stage=='present_evidence':
        report=load(journal,previous('simulate')['study_ref']);primary=report['reports']['primary'];buffer=io.StringIO()
        writer=csv.writer(buffer);writer.writerow(['variant','time_s','x_m','y_m','z_m','speed_m_s','lateral_acceleration_m_s2','mechanical_engine_energy_j','mode','front_flap_angle_deg','maximum_constraint_residual'])
        for run in primary['runs']:
            for row in run['samples']:writer.writerow([run['variant'],row['time_s'],*row['position_m'],row['speed_m_s'],row['lateral_acceleration_m_s2'],row['mechanical_engine_energy_j'],row['mode'],row['front_flap_angle_deg'],row['maximum_constraint_residual']])
        paths=[write(root,'raw_output.csv',buffer.getvalue().encode()),plot_trace(root,primary),
            write(root,'sources.json',{'regulation':previous('requirements_and_sources'),'asset_search':previous('discover_assets')}),
            write(root,'comparison.json',previous('compare')),write(root,'raw_solver_output.json',report),write(root,'episode-through-compare.json',StageJournal(journal).episode(state.run_id))]
        regulation=previous('requirements_and_sources')['regulation']
        text=(f'# {target.year} F1-class conditional surrogate\n\nNot exact {target.team_or_class} engineering CAD. Not physically validated.\n\n'
            f'Source: {regulation["url"]} (issue {regulation["edition"]}, published {regulation["publication_date"]}).\n\n'
            'Geometry: independently checked procedural GLB and native Chrono JSON. No downloaded third-party model is claimed.\n\n'
            'Experiment: identical prescribed controls, flat road, gravity, air and power unit across baseline/candidate. 2026 uses spatial front/rear coefficient modes; coefficients remain unmeasured assumptions.\n\n'
            f'Metrics are maximum observed speed, lateral acceleration and mechanical engine shaft energy in a {primary["inputs"]["duration_s"]:g}-second road test; they are not terminal speed, race-lap performance or fuel/hybrid energy.\n\n'
            'Half-timestep and +/-10% joint aero-envelope trials are retained. Other input intervals are declared but not exhaustively propagated.\n\n'
            '```json\n'+json.dumps(previous('compare'),indent=2)+'\n```\n\n'
            'Replay numerical inputs with the approved fixed Chrono worker through Jarvis; each new execution requires an available invocation/budget slot. '
            'Read-only audit: `python -m jarvis.discovery.scenario_verify --manifest "'+(root/'run_manifest.json').relative_to(base).as_posix()+'"`.\n')
        paths.append(write(root,'report.md',text.encode()))
        all_paths=list(root.iterdir())
        all_files=file_manifest(base,[p for p in all_paths if p.is_file()])
        for ref in state.stage_artifacts.values():all_files.update(load(journal,ref)['files'])
        manifest={'schema_version':1,'run_id':state.run_id,'original_goal':target.goal,'target_year':target.year,
            'representation':'explicit regulation-referenced class surrogate','exact_team_cad':False,'physical_validation':False,
            'operator_provided_solution':False,'solver':'Chrono::Vehicle 10.0.0','study_ref':previous('simulate')['study_ref'],
            'worker_sha256':report['worker_sha256'],'comparison':previous('compare'),'files':all_files}
        paths.append(write(root,'run_manifest.json',manifest));facts={'run_manifest':(root/'run_manifest.json').relative_to(base).as_posix()}
    elif stage=='completed':facts={'status':'CONDITIONAL_SURROGATE_VERIFIED','physical_validation':False,'exact_team_cad':False,
        'run_manifest':previous('present_evidence')['run_manifest'],'report':(root/'report.md').relative_to(base).as_posix()}
    else:raise ValueError('no registered stage action')
    return {'stage':stage,'facts':facts,'files':file_manifest(base,paths)}


def invalidate_stale_inspection(store,state,base):
    """Invalidate derived evidence only after verifying its retained source.

    Original downloads, old states, action traces and files are retained. A
    different qualified parser gets a new action identity; no unknown download
    or same-worker dispatch is repeated.
    """
    if 'inspect_asset' not in state.verified_stages:return state
    facts=artifact(store.journal,state,'inspect_asset')
    if facts.get('decision')!='ACQUIRED_VISUAL_ASSET':return state
    from .adapters import asset_inspection,asset_acquisition
    from .acceptance import artifact as load
    receipt=load(store.journal,facts['inspection_ref'])
    child_state=load(store.journal,facts['geometry_result']['state_ref'])
    child_target=json.loads(child_state['original_goal'])
    if receipt['worker_sha256']==asset_inspection.worker_hash() and child_target.get('inspector_sha256')==asset_inspection.worker_hash():return state
    original=asset_acquisition.verify(base,store.journal,facts['download_ref'])['download']
    record=asset_inspection.completed_record(receipt['slot'],receipt['worker_sha256'])
    from .adapters.assets import local_bytes
    raw=local_bytes(base,receipt['relative_file'],4_000_000)
    if (receipt['original_sha256']!=original['sha256'] or hashlib.sha256(raw).hexdigest()!=receipt['sha256']
            or json.loads(raw)!=record['inspection'] or receipt['request_ref']!=record['request_ref']):
        raise ValueError('historical inspection/source changed; automatic invalidation refused')
    old=store.journal.put(state.model_dump(mode='json'),'Report')
    store.journal.put({'kind':'source_dependency_invalidation','previous_state_ref':old,
        'old_worker_sha256':receipt['worker_sha256'],'new_worker_sha256':asset_inspection.worker_hash(),
        'retained_download_ref':facts['download_ref'],'original_sha256':original['sha256']},'Report')
    index=STAGES.index('inspect_asset');prefix=state.verified_stages[:index]
    return store.save(state.model_copy(update={'verified_stages':prefix,
        'stage_artifacts':{key:state.stage_artifacts[key] for key in prefix},'stage':store.stage_type('inspect_asset'),'stage_status':'pending',
        'state_revision':state.state_revision+1,'selected_asset':None,'source_licenses':(),
        'geometry_manifest':None,'physical_manifest':None,'solver_configuration':None,'validated_metrics':None,
        'evidence_files':(),'uncertainties':(),
        'failures':(*state.failures,'Derived inspection invalidated after parser revision; original/source evidence retained.')}))


def run_project(actions,target,journal,cancelled,task_id=None):
    from ..skill_memory import linked
    store=StageJournal(journal);state=store.open(target);base=Path(actions.base).resolve()
    root=base/'.jarvis-runtime/discovery/scenario-projects'/state.run_id
    if any(linked(p) for p in (root,*root.parents)):raise ValueError('linked project root refused')
    root.mkdir(parents=True,exist_ok=True)
    state=invalidate_stale_inspection(store,state,base)
    # Revalidate retained evidence before resuming any later stage; metadata or
    # a stale "verified" flag alone never skips a stage after restart.
    for stage in state.verified_stages:
        retained=artifact(journal,state,stage)
        from .acceptance import artifact as load
        prefix=state.model_copy(update={'verified_stages':state.verified_stages[:STAGES.index(stage)],
            'stage_artifacts':{k:v for k,v in state.stage_artifacts.items() if STAGES.index(k)<STAGES.index(stage)}})
        verify_stage(stage,load(journal,state.stage_artifacts[stage]),base=base,journal=journal,state=prefix,target=target)
    for stage in STAGES[len(state.verified_stages):]:
        if cancelled():raise ValueError('Scenario A cancelled; verified stage checkpoints retained')
        if task_id:actions.task_state.require_identity(task_id)
        actions.report('brain',f'Scenario A {target.year}: {stage} ({len(state.verified_stages)}/{len(STAGES)} verified stages).')
        args=action_arguments(stage,target,state.stage_artifacts);action='scenario.'+stage
        if stage=='inspect_asset' and not target.allow_surrogate:
            from .adapters import asset_inspection,asset_resources
            permission=asset_resources.applicable(target.year,target_query(target))
            if not asset_inspection.qualification(permission['sha256'] if permission else None)['runtime_ready']:
                raise BlockedStage('current source inspector/profile is not golden-qualified')
            action+='.'+asset_inspection.worker_hash()
        current=state
        def projection(output):
            facts=output['facts']
            if stage=='requirements_and_sources':return {'source_records':tuple(facts['source_refs'])}
            if stage=='discover_assets':return {'candidate_assets':tuple(i['uid'] for i in facts['candidates']),
                'source_records':(*current.source_records,*([facts['source_ref']] if facts.get('source_ref') else []))}
            if stage=='inspect_asset':return {'selected_asset':facts.get('inspection_ref'),'source_licenses':tuple(output['files'])}
            if stage=='generate_parametric_surrogate':return {'geometry_manifest':facts['manifest'],
                'solver_configuration':(root/'solver_configuration.json').relative_to(base).as_posix(),
                'uncertainties':tuple(facts['case']['assumptions'])}
            if stage=='assemble_physical_vehicle':return {'physical_manifest':facts['physical_manifest']}
            if stage=='compare':return {'validated_metrics':journal.put(facts,'Report')}
            if stage=='present_evidence':return {'evidence_files':tuple(output['files'])}
            return {}
        state,_=store.perform(state,stage,action,args,
            lambda:actions_for(stage,current,target,base,journal,actions,root,cancelled),
            lambda output:verify_stage(stage,output,base=base,journal=journal,state=current,target=target),
            read_only=stage in ('resolve_target','requirements_and_sources','discover_assets','validate_provenance','validate_model','independently_check','compare','completed'),project=projection)
        owner=getattr(actions,'task_state',None)
        if owner is not None:owner.checkpoint('scenario_stage_verified',source='independent_stage_verifier',evidence=stage+':'+state.stage_artifacts[stage])
    write(root,'episode.json',store.episode(state.run_id))
    return state


def adapters(graph,journal):
    memory=LabMemory(journal);memory.migrate()
    for node in NODES:
        if node in graph.neurons:memory.put(Capability(id=node,neuron_id=node,intents=('staged conditional vehicle project',),
            golden_ref='tests/test_discovery_scenario_a.py',justification='No scientific promotion from test counts; actual stage evidence is required.'))
    def perform(neuron,inputs,env):
        if set(inputs['request'])!={'goal'}:raise ValueError('Scenario A request accepts only original goal text')
        target=resolve(inputs['request']['goal'])
        if target is None:raise ValueError('ambiguous Scenario A target')
        allowed=getattr(env.actions,'allowed_tools',None)
        if isinstance(allowed,(set,frozenset)) and 'discovery_call' not in allowed:
            raise BlockedStage('Lab execution is not available in this scoped tool context')
        owner=getattr(env.actions,'task_state',None)
        task_id=None
        if owner is not None:
            current=owner.snapshot() or {}
            if owner.running_identity() and current.get('goal')!=target.goal:raise ValueError('different task owns the current checkpoint')
            if not owner.running_identity():owner.start(target.goal,'task')
            task_id=owner.running_identity()
        try:state=run_project(env.actions,target,journal,env.cancelled,task_id)
        except BaseException as exc:
            if owner is not None:owner.finish('paused',str(exc),task_id=task_id)
            if isinstance(exc,BlockedStage):
                from ..neural.dispatcher import Stop
                raise Stop('blocked',str(exc)) from exc
            raise
        from .contracts import RunArtifact
        manifest=Path(env.actions.base)/artifact(journal,state,'completed')['run_manifest']
        memory.put(RunArtifact(id=state.run_id,locator=manifest.relative_to(env.actions.base).as_posix(),
            sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),media_type='application/json',source_ids=state.source_records,
            evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',justification='Numerically checked educational surrogate; not proprietary exact CAD or physical validation.'))
        return {'report':{'state_ref':journal.put(state.model_dump(mode='json'),'Report'),'run_id':state.run_id,
            'task_id':task_id,
            'status':'CONDITIONAL_SURROGATE_VERIFIED','physical_validation':False,
            'result':artifact(journal,state,'completed')}}
    def verify(neuron,inputs,env):
        problems=[]
        try:
            target=resolve(inputs['request']['goal']);store=StageJournal(journal);state=store.load(inputs['report']['state_ref'])
            if state.original_goal!=target.goal or state.verified_stages!=STAGES:raise ValueError('project incomplete or wrong goal')
            for stage in STAGES:
                from .acceptance import artifact as load
                prefix=state.model_copy(update={'verified_stages':state.verified_stages[:STAGES.index(stage)],
                    'stage_artifacts':{k:v for k,v in state.stage_artifacts.items() if STAGES.index(k)<STAGES.index(stage)}})
                verify_stage(stage,load(journal,state.stage_artifacts[stage]),base=env.actions.base,journal=journal,state=prefix,target=target)
            owner=getattr(env.actions,'task_state',None)
            if owner is not None:
                owner.require_identity(inputs['report']['task_id'])
                owner.finish('completed','Conditional surrogate workflow independently verified; physical validation remains false.',task_id=inputs['report']['task_id'])
        except Exception as exc:
            problems.append(type(exc).__name__+': '+str(exc)[:700])
            owner=getattr(env.actions,'task_state',None)
            if owner is not None:owner.finish('paused',problems[-1],task_id=inputs['report'].get('task_id'))
        return {'verdict':{'passed':not problems,'problems':problems,'evidence':['all stage artifacts independently rechecked; conditional surrogate only'] if not problems else []}}
    return {node:({'run':perform,'check':verify}['run' if i==0 else 'check']) for i,node in enumerate(NODES) if node in graph.neurons}
