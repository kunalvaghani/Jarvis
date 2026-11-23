"""General research-to-import subtask through the existing stage controller.

An acquired mesh is not a mechanical assembly. This module deliberately stops
at an independently checked geometric inventory, without claiming physics or A.
"""
import hashlib
import json
from pathlib import Path
from .model.asset_pipeline import Target,Request,Workflow
from .scenario_journal import StageJournal,BlockedStage
from .adapters import asset_discovery,asset_rights,asset_acquisition,asset_inspection
from .acceptance import artifact
from .catalog import enabled

NODES=('discovery.assets.acquire_geometry@v1','discovery.verify.acquired_geometry@v1')


def neurons(config):
    if not enabled(config,'sim'):return []
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    return [Neuron(node_id=node,kind='workflow' if i==0 else 'verifier',capability=node.split('@')[0],
        provider='jarvis.discovery.asset_pipeline',contract='explicit',
        inputs=ports(('request:Report',) if i==0 else ('request:Report','report:Report')),
        outputs=ports(('report:Report',) if i==0 else ('verdict:Verdict',)),
        side_effect_class='local_write' if i==0 else 'read_only',privilege='write' if i==0 else 'read',
        runtime='network' if i==0 else 'local',privacy='public_data_only',
        requirements=('flag:lab.enabled','flag:lab.sim','flag:lab.research'),timeout_ms=240000,
        resource_cost={'money':0,'gpu_vram_mb':0,'cpu_s_estimate':35 if i==0 else 1},
        description='Rights-bound original model acquisition and geometric inspection only; no physical validation or Scenario A promotion',
        source='jarvis/discovery/asset_pipeline.py') for i,node in enumerate(NODES)]


def sources(config,previous):return {**previous,'discovery_asset_geometry':lambda:neurons(config)}


def adapters(graph,journal):
    from .memory import LabMemory
    from .contracts import Capability
    memory=LabMemory(journal);memory.migrate()
    for node in NODES:
        if node in graph.neurons:memory.put(Capability(id=node,neuron_id=node,
            intents=('acquire an original licensed model and inspect geometric parts',),
            golden_ref='tests/test_discovery_asset_pipeline.py',
            justification='Adapter/controller boundary tests and separate parser goldens; autonomous acquired-asset end-to-end qualification still unmet.'))
    def perform(neuron,inputs,env):
        request=Request.model_validate_json(json.dumps(inputs['request']))
        from ..task_state import TaskState
        from .vehicle_assurance import asset_query_error
        task=getattr(env.actions,'task_state',None)
        goal=(task.snapshot() or {}).get('goal','') if isinstance(task,TaskState) else ''
        problem=asset_query_error(env.actions.config,goal,request.query,catalog_search=True)
        if problem:raise ValueError(problem)
        return {'report':run(env.actions,journal,request.query,target_year=request.target_year,cancelled=env.cancelled)}
    def verify(neuron,inputs,env):
        problems=[]
        try:
            request=Request.model_validate_json(json.dumps(inputs['request']));report=inputs['report']
            state=Workflow.state_type.model_validate_json(json.dumps(artifact(journal,report['state_ref'])))
            saved_target=Workflow.resolve(state.original_goal)
            if (saved_target.query!=request.query or saved_target.target_year!=request.target_year or tuple(state.verified_stages)!=Workflow.stages):
                raise ValueError('acquired-geometry checkpoint is incomplete or for another target')
            if saved_target.resource_grant_sha256:
                from .adapters.asset_resources import grant
                grant(saved_target.resource_grant_sha256)
            if saved_target.inspector_sha256!=asset_inspection.worker_hash():raise ValueError('geometry workflow inspector revision differs')
            if report['run_id']!=state.run_id:raise ValueError('published workflow identity differs')
            rows=journal.rows('SELECT stage,result_ref FROM discovery_scenario_actions WHERE run_id=? AND category=?',(state.run_id,'verified'))
            if {row['stage']:row['result_ref'] for row in rows}!=state.stage_artifacts or len(rows)!=len(Workflow.stages):
                raise ValueError('no matching verified stage admissions for this checkpoint')
            if report['status']!='ACQUIRED_GEOMETRY_ONLY' or report['physical_validation'] is not False or report['full_scenario_a_passed'] is not False:
                raise ValueError('geometry result cannot promote scientific claims')
            observed=asset_inspection.verify_inspection(env.actions.base,journal,state.inspection_ref)
            acquired=asset_acquisition.verify(env.actions.base,journal,state.download_ref)
            if (observed['receipt']['download_ref']!=state.download_ref
                    or acquired['download']['acquisition_ref']!=state.acquisition_ref):raise ValueError('asset lineage differs')
            if report['inspection_ref']!=state.inspection_ref or report['part_count']!=observed['receipt']['part_count']:
                raise ValueError('published geometric inventory differs')
        except Exception as exc:problems.append(type(exc).__name__+': acquired-geometry evidence did not verify')
        return {'verdict':{'passed':not problems,'problems':problems,
            'evidence':['Original bytes, per-file rights and geometric inventory only; no mechanical/physical validation.'] if not problems else []}}
    return {node:perform if node==NODES[0] else verify for node in NODES if node in graph.neurons}


def run(actions,journal,query,*,target_year=None,cancelled=lambda:False):
    from .adapters.asset_resources import applicable
    request=Request(query=query,target_year=target_year)
    permission=applicable(target_year,query)
    target=Target(query=query,target_year=target_year,resource_grant_sha256=permission['sha256'] if permission else None,
        inspector_sha256=asset_inspection.worker_hash())
    controller=StageJournal(journal,workflow=Workflow())
    state=controller.open(target);base=Path(actions.base)
    # Stable across process restarts and workflow implementation revisions.
    project_id='asset-'+hashlib.sha256(json.dumps(request.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()[:32]

    def response(stage,**facts):return {'stage':stage,'facts':facts,'files':{}}
    def notify(stage):
        if cancelled():raise BlockedStage('asset subtask cancelled; retained checkpoint')
        actions.report('brain','Lab asset subtask: '+stage+'; geometry completion does not establish physics.')

    for stage in Workflow.stages[len(state.verified_stages):]:
        notify(stage)
        if stage=='research':
            def operation():
                result=asset_discovery.discover(actions,journal,project_id,target.query,target_year=target.target_year,cancelled=cancelled)
                return response(stage,research_ref=journal.put(result,'Report'))
            def verify(output):
                result=artifact(journal,output['facts']['research_ref'])
                if result['query']!=target.query or result['target_year']!=target.target_year:raise ValueError('research target differs')
                if not result['qualified_rights']:raise BlockedStage('no per-file rights qualified; provider/browser blockers retained in research evidence')
                for item in result['qualified_rights']:asset_rights.verify(base,journal,item['acquisition_ref'])
            project=lambda output:{'research_ref':output['facts']['research_ref']}
            reconcile=None;read_only=True
        elif stage=='select':
            def operation():
                result=artifact(journal,state.research_ref)
                choices=[]
                for item in result['qualified_rights']:
                    asset,availability=asset_rights.verify(base,journal,item['acquisition_ref'])
                    available=availability.get('download_url') or (asset.provider=='sketchfab' and availability.get('downloadable_declared') is True)
                    if available and asset.file_format in ('glb','gltf','obj','stl','zip'):
                        choices.append((asset.file_format!='glb',asset.file_format!='gltf',asset.maximum_bytes,item['acquisition_ref']))
                if not choices:raise BlockedStage('qualified rights exist, but no lawful downloadable file with a supported importer is available')
                return response(stage,acquisition_ref=sorted(choices)[0][-1])
            def verify(output):
                ref=output['facts']['acquisition_ref'];result=artifact(journal,state.research_ref)
                if ref not in [item['acquisition_ref'] for item in result['qualified_rights']]:raise ValueError('selection was not discovered')
                asset,availability=asset_rights.verify(base,journal,ref)
                if not availability.get('download_url') and not (asset.provider=='sketchfab' and availability.get('downloadable_declared') is True):
                    raise ValueError('selected source has no lawful transfer resolver')
            project=lambda output:{'acquisition_ref':output['facts']['acquisition_ref']}
            reconcile=None;read_only=True
        elif stage=='acquire':
            def operation():
                ref,_=asset_acquisition.transfer(base,journal,state.acquisition_ref,cancelled=cancelled,actions=actions)
                return response(stage,download_ref=ref)
            def verify(output):
                result=asset_acquisition.verify(base,journal,output['facts']['download_ref'])
                if result['download']['acquisition_ref']!=state.acquisition_ref:raise ValueError('download source differs')
            def reconcile():
                rows=journal.rows('SELECT result_ref FROM discovery_asset_transfers WHERE acquisition_ref=? AND state=?',(state.acquisition_ref,'complete'))
                if len(rows)!=1:raise BlockedStage('no independently completed transfer to reconcile; no new download dispatched')
                return response(stage,download_ref=rows[0]['result_ref'])
            project=lambda output:{'download_ref':output['facts']['download_ref']}
            read_only=False
        elif stage=='inspect':
            def operation():
                ref,_=asset_inspection.inspect_download(base,journal,state.download_ref,cancelled=cancelled)
                observed=asset_inspection.verify_inspection(base,journal,ref)
                from .geometry_preview import build
                asset,_=asset_rights.verify(base,journal,state.acquisition_ref)
                preview=build(base,observed,asset,journal=journal,grant_sha=target.resource_grant_sha256)
                actions.report('media_card',{'service':'discovery','phase':'done','title':'Imported source geometry',
                    'subtitle':'Decimated geometric diagnostic; no verified rig or physics',
                    'image':(base/preview['relative_file']).as_uri()})
                return response(stage,inspection_ref=ref,geometry_preview=preview)
            def verify(output):
                result=asset_inspection.verify_inspection(base,journal,output['facts']['inspection_ref'])
                if result['receipt']['download_ref']!=state.download_ref:raise ValueError('inspection source differs')
                if 'geometry_preview' in output['facts']:
                    from .geometry_preview import build
                    asset,_=asset_rights.verify(base,journal,state.acquisition_ref)
                    if build(base,result,asset,journal=journal,grant_sha=target.resource_grant_sha256)!=output['facts']['geometry_preview']:raise ValueError('source diagnostic differs')
            def reconcile():
                rows=journal.rows('SELECT result_ref FROM discovery_asset_inspections WHERE download_ref=? AND worker_sha256=? AND state=?',
                    (state.download_ref,asset_inspection.worker_hash(),'complete'))
                if len(rows)!=1:raise BlockedStage('no completed inspection publication to reconcile; no parser replay')
                return response(stage,inspection_ref=rows[0]['result_ref'])
            project=lambda output:{'inspection_ref':output['facts']['inspection_ref']}
            read_only=False
        else:
            def operation():return response(stage,inspection_ref=state.inspection_ref,scope='ACQUIRED_GEOMETRY_ONLY',physical_validation=False,full_scenario_a_passed=False)
            def verify(output):
                asset_inspection.verify_inspection(base,journal,state.inspection_ref)
                if output['facts'].get('scope')!='ACQUIRED_GEOMETRY_ONLY' or output['facts'].get('physical_validation') is not False:
                    raise ValueError('asset subtask cannot promote physical claims')
            project=lambda output:{};reconcile=None;read_only=True
        action='asset_pipeline.'+stage
        if stage=='inspect':
            if not asset_inspection.qualification(target.resource_grant_sha256)['runtime_ready']:
                raise BlockedStage('current inspector/profile requires golden qualification before dispatch')
            # A newly qualified fixed parser is a distinct registered alternative,
            # not a replay of a rejected/uncertain earlier parser. The inner
            # dispatch ledger still forbids repeating an unknown same-source call.
            action+='.'+asset_inspection.worker_hash()
        state,_=controller.perform(state,stage,action,{'target':target.model_dump(mode='json'),'prior':state.stage_artifacts},
            operation,verify,read_only=read_only,project=project,reconcile=reconcile)
    # Fresh-session reuse still verifies the original and retained parser output.
    observed=asset_inspection.verify_inspection(base,journal,state.inspection_ref)
    return {'state_ref':journal.put(state.model_dump(mode='json'),'Report'),'run_id':state.run_id,
        'status':'ACQUIRED_GEOMETRY_ONLY','inspection_ref':state.inspection_ref,
        'part_count':observed['receipt']['part_count'],'physical_validation':False,'full_scenario_a_passed':False}
