"""Independent validators for deterministic Scenario A stage artifacts."""
import hashlib,json,struct
from pathlib import Path
from .model.scenario_a import STAGES
from .model.vehicle import VehicleCase


def files(base,manifest):
    from .adapters.assets import local_bytes
    for path,sha in manifest.items():
        if not path.startswith(('.jarvis-runtime/discovery/scenario-projects/',
            '.jarvis-runtime/discovery/vehicle-runs/','.jarvis-runtime/discovery/official-sources/')):
            raise ValueError('stage artifact outside owned scientific output roots')
        raw=local_bytes(Path(base),path,10_000_000)
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('stage artifact hash changed: '+path)


def glb(raw,manifest):
    magic,version,size=struct.unpack_from('<4sII',raw)
    if magic!=b'glTF' or version!=2 or size!=len(raw):raise ValueError('invalid actual GLB')
    length,kind=struct.unpack_from('<I4s',raw,12)
    if kind!=b'JSON':raise ValueError('GLB JSON chunk missing')
    doc=json.loads(raw[20:20+length]);offset=20+length
    n,kind=struct.unpack_from('<I4s',raw,offset)
    if kind!=b'BIN\0' or offset+8+n!=len(raw):raise ValueError('GLB binary chunk missing')
    binary=raw[offset+8:];items=manifest['components']
    if len(doc['meshes'])!=len(items):raise ValueError('mesh/component topology differs')
    for mesh,item in zip(doc['meshes'],items):
        if mesh['name']!=item['component_id']:raise ValueError('unstable visual component identity')
        primitive=mesh['primitives'][0]
        for field,expected,width,fmt in [('POSITION',item['vertices'],3,'f'),('indices',[[i] for t in item['triangles'] for i in t],1,'I')]:
            index=primitive['attributes'][field] if field=='POSITION' else primitive['indices']
            accessor=doc['accessors'][index];view=doc['bufferViews'][accessor['bufferView']]
            if accessor['count']!=len(expected):raise ValueError('actual mesh accessor count differs')
            start=view.get('byteOffset',0)
            values=[struct.unpack_from('<'+fmt*width,binary,start+i*width*4) for i in range(len(expected))]
            if any(abs(a-b)>1e-6 for actual,wanted in zip(values,expected) for a,b in zip(actual,wanted)):
                raise ValueError('actual mesh coordinates/indices differ from authoring manifest')


def compare(study):
    primary=study['reports']['primary'];a,b=primary['runs'];deltas={key:b['metrics'][key]-value for key,value in a['metrics'].items()}
    envelope={key:[min(study['reports'][name]['runs'][1]['metrics'][key] for name in ('aero_low','primary','aero_high')),
                   max(study['reports'][name]['runs'][1]['metrics'][key] for name in ('aero_low','primary','aero_high'))] for key in deltas}
    return {'baseline':a['metrics'],'candidate':b['metrics'],'candidate_minus_baseline':deltas,
        'assumed_aero_envelope_candidate_ranges':envelope,'scenario_sha256':primary['scenario_sha256'],
        'speed_scope':f"maximum observed in the fixed {primary['inputs']['duration_s']:g}-second road test, not terminal or lap speed",
        'energy_scope':'mechanical engine shaft energy only; fuel/hybrid losses unsupported',
        'physical_validation':False}


def verify_stage(stage,value,*,base,journal,state,target):
    from .acceptance import artifact
    if set(value)!={'stage','facts','files'} or value['stage']!=stage:raise ValueError('wrong or extra stage response fields')
    facts=value['facts'];files(base,value['files'])
    prior={key:artifact(journal,ref)['facts'] for key,ref in state.stage_artifacts.items()}
    if stage=='resolve_target':
        if facts!=target.model_dump(mode='json'):raise ValueError('resolved target changes original request')
    elif stage=='requirements_and_sources':
        from .adapters.fia_sources import allowed,extract,edition
        r=facts['regulation']
        if r['year']!=target.year or not allowed(r['url']) or len(r['sha256'])!=64 or not r['publication_date']:
            raise ValueError('missing official edition/provenance')
        raw=(Path(base)/r['cached_pdf']).read_bytes()
        index=(Path(base)/'.jarvis-runtime/discovery/official-sources'/(r['index_sha256']+'.html')).read_bytes()
        if hashlib.sha256(index).hexdigest()!=r['index_sha256']:
            raise ValueError('captured official source index hash differs')
        selected=edition(index,target.year)
        if any(selected[key]!=r[key] for key in ('year','url','title','edition','publication_date')):
            raise ValueError('regulation edition does not match requested season in captured source index')
        if hashlib.sha256(raw).hexdigest()!=r['sha256'] or extract(raw,target.year)['limits']!=r['limits']:
            raise ValueError('regulation source fields do not match captured bytes')
    elif stage=='discover_assets':
        from .model.scenario_a import target_query
        if facts['query']!=target_query(target):raise ValueError('source search changed target identity')
        if not facts.get('source_ref') and not facts.get('provider_failure'):raise ValueError('no actual source outcome')
        if facts.get('source_ref'):
            from .memory import LabMemory
            source=LabMemory(journal).get(facts['source_ref'])
            if source is None or source.sha256!=facts['payload_sha256']:raise ValueError('actual asset source receipt missing')
    elif stage=='validate_provenance':
        candidates=prior['discover_assets']['candidates']
        if facts['reviewed_ids']!=[item['uid'] for item in candidates] or facts['exact_engineering_identity_verified'] is not False:
            raise ValueError('asset provenance/identity overclaim')
        if any(not row.get('reason') for row in facts['decisions']):raise ValueError('asset rejection lacks rationale')
    elif stage=='inspect_asset':
        if facts['decision']=='ACQUIRED_VISUAL_ASSET':
            from .adapters.asset_inspection import verify_inspection
            observed=verify_inspection(base,journal,facts['inspection_ref'])
            if (facts['geometry_acquired'] is not True or facts['target_year']!=target.year
                    or facts['exact_team_cad'] is not False or facts['physical_validation'] is not False
                    or observed['receipt']['download_ref']!=facts['download_ref']):
                raise ValueError('acquired geometry lineage or claim differs')
        elif facts['decision']!='SURROGATE_REQUIRED' or facts['geometry_acquired'] is not False or not target.allow_surrogate:
            raise ValueError('unapproved or unsupported asset substitution')
        from .scenario_journal import digest
        if facts['decision_hash']!=digest({k:v for k,v in facts.items() if k!='decision_hash'}):raise ValueError('surrogate decision hash differs')
    elif stage=='generate_parametric_surrogate':
        from .vehicle_geometry import validate
        case=VehicleCase.model_validate_json(json.dumps(facts['case']));manifest=json.loads((Path(base)/facts['manifest']).read_text())
        if case.year!=target.year:raise ValueError('wrong geometry season')
        validate(manifest['components'],case);glb((Path(base)/facts['glb']).read_bytes(),manifest)
        limit=prior['requirements_and_sources']['regulation']['limits']
        if case.wheelbase_m>limit['maximum_wheelbase_m']:raise ValueError('wheelbase exceeds sourced season envelope')
        if any(abs(p[1])>limit['maximum_non_tyre_half_width_m'] for item in manifest['components'] if item['kind']!='wheel' for p in item['vertices']):
            raise ValueError('non-tire geometry exceeds sourced width envelope')
    elif stage in ('assemble_physical_vehicle','validate_model'):
        from .vehicle_checks import validate_prepared,native
        case=VehicleCase.model_validate_json(json.dumps(prior['generate_parametric_surrogate']['case']))
        report=artifact(journal,facts['prepared_ref']);validate_prepared(case,report);native(base,report)
        license_file=facts.get('upstream_license_file') or prior['assemble_physical_vehicle']['upstream_license_file']
        if hashlib.sha256((Path(base)/license_file).read_bytes()).hexdigest()!='5f625eb4c9e0ddf86db9d1ed9b6adb5b30296ea81919282b2f38c977136bf079':
            raise ValueError('borrowed native JSON templates lack retained upstream license')
    elif stage in ('simulate','independently_check'):
        from .vehicle_checks import study,native
        from .adapters.chrono import worker_hash,HOME
        report=artifact(journal,facts['study_ref'])
        if report['worker_sha256']!=worker_hash():raise ValueError('solver worker version changed')
        receipt=json.loads((HOME/'invocations'/f"slot-{report['slot']:02}.json").read_text())
        if receipt['request_ref']!=report['input_ref'] or receipt['worker_sha256']!=report['worker_sha256']:
            raise ValueError('actual solver admission receipt missing')
        completion=json.loads((HOME/'invocations'/f"result-{report['slot']:02}.json").read_text())
        if completion['result_ref']!=facts['study_ref'] or completion['request_ref']!=report['input_ref']:
            raise ValueError('actual solver completion receipt missing')
        case=VehicleCase.model_validate_json(json.dumps(prior['generate_parametric_surrogate']['case']))
        if stage=='independently_check' and facts['verification']!=study(case,report):raise ValueError('numerical check differs from actual trace')
        for child in report['reports'].values():native(base,child)
    elif stage=='compare':
        report=artifact(journal,prior['simulate']['study_ref'])
        if facts!=compare(report):raise ValueError('comparison numbers differ from actual solver output')
    elif stage=='present_evidence':
        manifest=json.loads((Path(base)/facts['run_manifest']).read_text())
        files(base,manifest['files'])
        if manifest['original_goal']!=target.goal or manifest['operator_provided_solution'] is not False or manifest['physical_validation'] is not False:
            raise ValueError('evidence identity/origin overclaim')
        if manifest['comparison']!=prior['compare']:raise ValueError('published evidence differs from computed comparison')
    elif stage=='completed':
        if state.verified_stages!=STAGES[:-1] or facts['physical_validation'] is not False or facts['exact_team_cad'] is not False:
            raise ValueError('completion before every acceptance predicate')
    else:raise ValueError('stage has no verifier')
