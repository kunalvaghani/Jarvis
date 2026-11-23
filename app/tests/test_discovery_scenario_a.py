"""Workflow invariants and fault injection; fixtures never count as live A proof."""
import json
from unittest.mock import Mock
import pytest
from jarvis.discovery.model.scenario_a import resolve,ScenarioAVehicleState,STAGES
from jarvis.discovery.scenario_journal import StageJournal,NoProgress,UncertainStage
from jarvis.neural.journal import Journal


GOAL='Find a free 2026-regulation F1 car model and simulate active aero with a 2 degree change.'


def test_target_does_not_invent_team_asset_or_carry_other_season():
    target=resolve(GOAL)
    assert target.year==2026 and target.team_or_class=='F1 class'
    assert resolve('Find a 2025 McLaren F1 model and simulate dynamics.').team_or_class=='McLaren'
    assert resolve('Simulate both 2025 and 2026 F1 cars.') is None
    assert resolve('Find a model of a road car.') is None
    with pytest.raises(ValueError):ScenarioAVehicleState.model_validate_json(json.dumps({'invented':'state'}))


def test_parser_upgrade_preserves_source_history_and_refuses_tampered_old_evidence(tmp_path,monkeypatch):
    from jarvis.discovery.scenario_project import invalidate_stale_inspection
    from jarvis.discovery.adapters import asset_inspection,asset_acquisition
    from jarvis.discovery.model.scenario_a import Stage
    import hashlib
    journal=Journal(tmp_path/'brain.sqlite3');store=StageJournal(journal);target=resolve(GOAL)
    try:
        old=store.open(target);body=json.dumps({'parts':[]}).encode();path=tmp_path/'old-inspection.json';path.write_bytes(body)
        child=journal.put({'original_goal':json.dumps({'inspector_sha256':'c'*64})},'Report')
        receipt=journal.put({'worker_sha256':'c'*64,'slot':7,'original_sha256':'b'*64,'relative_file':path.name,
            'sha256':hashlib.sha256(body).hexdigest(),'request_ref':'old-worker-request'},'Report')
        facts={'decision':'ACQUIRED_VISUAL_ASSET','inspection_ref':receipt,'download_ref':'retained-download',
            'geometry_result':{'state_ref':child}}
        refs={stage:journal.put({'facts':facts if stage=='inspect_asset' else {},'files':{}},'Report') for stage in STAGES[:5]}
        old=store.save(old.model_copy(update={'verified_stages':STAGES[:5],'stage_artifacts':refs,'selected_asset':receipt}))
        monkeypatch.setattr(asset_inspection,'worker_hash',lambda:'a'*64)
        monkeypatch.setattr(asset_inspection,'completed_record',lambda *a:{'inspection':json.loads(body),'request_ref':'old-worker-request'})
        monkeypatch.setattr(asset_acquisition,'verify',lambda *a:{'download':{'sha256':'b'*64}})
        path.write_bytes(b'{}')
        with pytest.raises(ValueError,match='historical inspection/source changed'):invalidate_stale_inspection(store,old,tmp_path)
        assert store.open(target).selected_asset==receipt
        path.write_bytes(body)
        current=invalidate_stale_inspection(store,old,tmp_path)
        assert current.verified_stages==STAGES[:4] and current.stage==Stage.inspect_asset
        assert current.selected_asset is None and current.state_revision==old.state_revision+1
        assert path.read_bytes()==body and journal.get(receipt)
        assert current.stage_artifacts=={key:refs[key] for key in STAGES[:4]}
    finally:journal.close()


def test_failed_read_is_bounded_and_never_advances_checkpoint(tmp_path):
    journal=Journal(tmp_path/'brain.sqlite3');store=StageJournal(journal);state=store.open(resolve(GOAL))
    run=Mock(side_effect=ValueError('bad provider response'))
    try:
        for _ in range(2):
            with pytest.raises(ValueError,match='bad provider'):
                store.perform(state,'resolve_target','resolve',{},run,lambda result:None,read_only=True)
        with pytest.raises(NoProgress):
            store.perform(state,'resolve_target','resolve',{},run,lambda result:None,read_only=True)
        assert run.call_count==2
        restored=store.open(resolve(GOAL));assert not restored.verified_stages and restored.state_revision==0
        assert store.episode(state.run_id)[0]['category']=='failed'
    finally:journal.close()


def test_uncertain_write_cannot_be_replayed_in_a_fresh_store(tmp_path):
    path=tmp_path/'brain.sqlite3';journal=Journal(path);store=StageJournal(journal);state=store.open(resolve(GOAL))
    run=Mock(side_effect=TimeoutError('worker outcome unknown'))
    with pytest.raises(TimeoutError):store.perform(state,'resolve_target','write',{},run,lambda result:None)
    journal.close();journal=Journal(path);store=StageJournal(journal)
    try:
        with pytest.raises(UncertainStage):store.perform(state,'resolve_target','write',{},run,lambda result:None)
        assert run.call_count==1 and store.open(resolve(GOAL)).stage_status=='uncertain'
    finally:journal.close()


def test_output_verifier_and_order_are_mandatory_and_restart_keeps_evidence(tmp_path):
    journal=Journal(tmp_path/'brain.sqlite3');store=StageJournal(journal);state=store.open(resolve(GOAL))
    try:
        with pytest.raises(ValueError,match='out-of-order'):
            store.perform(state,'simulate','solver',{},lambda:{'passed':True},lambda r:None)
        def verify(result):
            if result['facts']!={'year':2026}:raise ValueError('fabricated completion')
        with pytest.raises(ValueError,match='fabricated'):
            store.perform(state,'resolve_target','resolve',{},lambda:{'stage':'resolve_target','facts':{'passed':True},'files':{}},verify,read_only=True)
        state,out=store.perform(state,'resolve_target','resolve',{},lambda:{'stage':'resolve_target','facts':{'year':2026},'files':{}},verify,read_only=True)
        restored=StageJournal(journal).open(resolve(GOAL))
        assert restored.state_revision==1 and restored.verified_stages==('resolve_target',)
        assert store.episode(state.run_id)[-1]['evidence_changed']
        assert restored.stage_artifacts['resolve_target']==state.stage_artifacts['resolve_target']
    finally:journal.close()


def test_original_exact_request_does_not_silently_authorize_surrogate():
    assert not resolve('Find a 2025 McLaren F1 model and simulate dynamics.').allow_surrogate
    assert resolve(GOAL+' If no exact model is usable, use a labelled surrogate.').allow_surrogate
    assert not resolve(GOAL+' Never use a surrogate.').allow_surrogate
    assert resolve('Find a 2025 F1 car model without simulation.') is None
    assert resolve('lab build a 2026 F1 vehicle and simulate dynamics using a surrogate') is None
    assert resolve('Build a 2026 F1 model, change the front wing by -2 degrees and simulate dynamics.').front_delta_deg==-2.
    assert resolve('Build a 2026 F1 model, lower the front wing by 2 degrees and simulate dynamics.').front_delta_deg==-2.
    assert not resolve(GOAL+" Don't use a surrogate.").allow_surrogate
    assert resolve('Build a 2026 F1 model, change its wing by 0.03 radians and simulate dynamics.') is None
    assert resolve('Build a 2026 F1 model, change its wing by three degrees and simulate dynamics.') is None
    assert resolve('Build a 2026 F1 model and simulate dynamics at 12 m/s2 gravity.') is None
    assert resolve('Build a 2026 F1 model and simulate dynamics at Monza.') is None
    assert not resolve(GOAL+' If no exact model exists, stop.').allow_surrogate
    assert not resolve(GOAL+" Don't use any generic surrogate.").allow_surrogate


def test_procedural_mesh_has_real_manifold_geometry_and_glb_matches_manifest(tmp_path):
    from jarvis.discovery.vehicle_recipe import build
    from jarvis.discovery.vehicle_geometry import build as geometry
    from jarvis.discovery.scenario_checks import glb
    target=resolve(GOAL+' If no exact asset exists use a surrogate.')
    case=build(target,{'limits':{'maximum_wheelbase_m':3.4,'maximum_non_tyre_half_width_m':.95}},['fixture-source'])
    result=geometry(tmp_path,case);manifest=json.loads((tmp_path/'geometry_manifest.json').read_text())
    glb((tmp_path/'asset_or_surrogate.glb').read_bytes(),manifest)
    assert result['checks']['wheel_count']==4 and result['checks']['manifold_components']==11
    changed=bytearray((tmp_path/'asset_or_surrogate.glb').read_bytes());changed[-12:]=b'\0'*12
    with pytest.raises(ValueError):glb(changed,manifest)


def test_neural_route_is_staged_and_flags_off_are_unchanged(tmp_path):
    from jarvis.neural.service import BrainService
    from jarvis.neural.compiler import compile_goal
    on={'neural':{'mode':'act'},'lab':{'enabled':True,'sim':True,'research':True}}
    s=BrainService(on,tmp_path/'brain.sqlite3')
    try:
        plan=compile_goal(GOAL,s.journal,on,s.graph.version)
        assert plan.workflow=='discovery.vehicle.scenario' and plan.goal_verifier=='verify_project'
        assert plan.steps[0].neuron=='discovery.vehicle.scenario@v1'
        assert compile_goal(GOAL,s.journal,{'lab':{'enabled':False}},s.graph.version) is None
    finally:s.journal.close()


def test_surrogate_scope_record_is_noncredential_metadata_and_preserves_secret_guard(tmp_path):
    from jarvis.discovery.scenario_project import actions_for
    from jarvis.discovery.scenario_journal import digest
    from jarvis.neural.journal import SecretPayload
    from types import SimpleNamespace
    target=resolve(GOAL+' If no exact model is available use a surrogate.')
    journal=Journal(tmp_path/'brain.sqlite3');store=StageJournal(journal);state=store.open(target)
    try:
        previous=journal.put({'facts':{'source_refs':['actual-regulation-source']}},'Report')
        reviews=journal.put({'facts':{'decisions':[]}},'Report')
        state=state.model_copy(update={'stage_artifacts':{'requirements_and_sources':previous,'validate_provenance':reviews}})
        out=actions_for('inspect_asset',state,target,tmp_path,journal,SimpleNamespace(),tmp_path,lambda:False)
        journal.put(out,'Report')
        assert out['facts']['decision_hash']==digest({k:v for k,v in out['facts'].items() if k!='decision_hash'})
        with pytest.raises(SecretPayload):journal.put({'Authorization':'Bearer abcdefghijklmnopqrstuvwxyz'},'Report')
    finally:journal.close()


def test_missing_license_and_random_mesh_name_never_become_exact_engineering(tmp_path):
    from jarvis.discovery.scenario_project import actions_for
    from types import SimpleNamespace
    journal=Journal(tmp_path/'brain.sqlite3');store=StageJournal(journal);target=resolve(GOAL);state=store.open(target)
    try:
        candidates=[{'uid':'a'*32,'name':'Random 2026 race car','license_declared':None},
            {'uid':'b'*32,'name':'Exact 2026 F1 car (unverified seller name)','license_declared':{'label':'CC Attribution'}}]
        ref=journal.put({'facts':{'candidates':candidates}},'Report');state=state.model_copy(update={'stage_artifacts':{'discover_assets':ref}})
        result=actions_for('validate_provenance',state,target,tmp_path,journal,SimpleNamespace(),tmp_path,lambda:False)
        assert not result['facts']['exact_engineering_identity_verified']
        assert all(row['decision']=='NOT_ENGINEERING_QUALIFIED' for row in result['facts']['decisions'])
        assert result['facts']['decisions'][0]['reason']=='missing license declaration'
    finally:journal.close()


def test_full_vehicle_route_invokes_registered_acquisition_logic_without_substitution(tmp_path,monkeypatch):
    from jarvis.discovery import scenario_project,asset_pipeline
    from jarvis.discovery.adapters import asset_inspection
    from types import SimpleNamespace
    target=resolve('Find a 2025 McLaren F1 model and simulate dynamics.')
    journal=Journal(tmp_path/'brain.sqlite3');state=StageJournal(journal).open(target);calls=[]
    def acquire(actions,store,query,**kwargs):
        calls.append((query,kwargs['target_year']))
        return {'inspection_ref':'actual-inspection-fixture','status':'ACQUIRED_GEOMETRY_ONLY'}
    monkeypatch.setattr(asset_pipeline,'run',acquire)
    monkeypatch.setattr(asset_inspection,'verify_inspection',lambda *a:{'receipt':{'download_ref':'actual-download-fixture'}})
    try:
        root=tmp_path/'.jarvis-runtime/discovery/scenario-projects'/state.run_id;root.mkdir(parents=True)
        result=scenario_project.actions_for('inspect_asset',state,target,tmp_path,journal,SimpleNamespace(),root,lambda:False)
        assert calls==[('2025 McLaren F1 model',2025)]
        assert result['facts']['decision']=='ACQUIRED_VISUAL_ASSET' and result['facts']['geometry_acquired'] is True
        assert result['facts']['exact_team_cad'] is False
        from jarvis.discovery.scenario_checks import verify_stage
        verify_stage('inspect_asset',result,base=tmp_path,journal=journal,state=state,target=target)
        node=scenario_project.neurons({'lab':{'enabled':True,'sim':True,'research':True}})[0]
        assert node.side_effect_class=='local_write' and node.privilege=='write' and node.gated
    finally:journal.close()


def test_missing_joints_and_nonphysical_inertia_fail_independently():
    from jarvis.discovery.vehicle_checks import inventory
    data={'body_count':10,'joint_count':0,'body_masses_kg':[1.]*10,'mass_kg':10.,
        'inertia_matrices_kg_m2':[[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]]*10}
    with pytest.raises(ValueError,match='joints'):inventory(data)
    data['joint_count']=20;data['inertia_matrices_kg_m2'][0]=[[1.,2.,0.],[2.,1.,0.],[0.,0.,1.]]
    with pytest.raises(ValueError,match='positive definite'):inventory(data)


def test_fabricated_completion_without_prior_evidence_is_rejected(tmp_path):
    from jarvis.discovery.scenario_checks import verify_stage
    journal=Journal(tmp_path/'brain.sqlite3');store=StageJournal(journal);target=resolve(GOAL);state=store.open(target)
    try:
        output={'stage':'completed','facts':{'status':'PASS','physical_validation':False,'exact_team_cad':False},'files':{}}
        with pytest.raises(ValueError,match='completion before'):
            verify_stage('completed',output,base=tmp_path,journal=journal,state=state,target=target)
    finally:journal.close()


def test_solver_admission_failure_starts_nothing_and_does_not_charge_estimated_cpu(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import chrono
    from tests.test_discovery_vehicle import case
    from jarvis import repo_acquisition
    journal=Journal(tmp_path/'brain.sqlite3');command=Mock(side_effect=AssertionError('no command admitted'))
    monkeypatch.setattr(repo_acquisition,'command',command)
    monkeypatch.setattr(chrono,'reserve',Mock(side_effect=PermissionError('grant exhausted')))
    try:
        with pytest.raises(PermissionError):chrono.run(case(),journal)
        assert not command.mock_calls
        row=journal.rows('SELECT cpu_s,state FROM discovery_budget')[0]
        assert row=={'cpu_s':0.,'state':'done'}
    finally:journal.close()


def test_corrupt_golden_receipt_degrades_without_execution(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import chrono
    home=tmp_path/'tool';home.mkdir();prefix=tmp_path/'env';prefix.mkdir()
    (prefix/'python.exe').write_bytes(b'not executed');(home/'install-result.json').write_text('{}')
    (home/'canonical-00.json').write_text('{invalid')
    monkeypatch.setattr(chrono,'HOME',home);monkeypatch.setattr(chrono,'PREFIX',prefix)
    result=chrono.qualification()
    assert not result['runtime_ready'] and any('unreadable' in p for p in result['problems'])


def test_official_edition_discovery_rejects_wrong_hosts_future_dates_and_wrong_seasons():
    from jarvis.discovery.adapters.fia_sources import edition,allowed
    raw=b'''<a href="https://evil.example/a.pdf">FIA 2026 F1 Technical Regulations Issue 99 Published on 01.01.26</a>
    <a href="/system/files/documents/a.pdf">FIA 2026 F1 Technical Regulations Issue 2 Published on 01.01.26</a>
    <a href="/system/files/documents/future.pdf">FIA 2026 F1 Technical Regulations Issue 3 Published on 01.01.99</a>'''
    assert edition(raw,2026)['edition']==2
    with pytest.raises(ValueError):edition(raw,2025)
    assert not allowed('https://www.fia.com:444/system/files/documents/a.pdf')
    assert not allowed('https://www.fia.com/system/files/documents/a.pdf?token=x')


def test_regulation_season_is_not_publication_or_copyright_year(monkeypatch):
    from jarvis.discovery.adapters.fia_sources import edition,extract,document_season
    from types import SimpleNamespace
    raw=b'''<a href="/system/files/documents/next.pdf">FIA 2026 F1 Technical Regulations Issue 15 Published on 10.12.2025</a>
    <a href="/system/files/documents/current.pdf">FIA 2025 Formula 1 Technical Regulations Issue 3 Published on 07.04.25</a>'''
    assert edition(raw,2025)['url'].endswith('/current.pdf')
    assert document_season('2026 Formula 1 Regulations: Technical Regulations copyright 2025')==2026
    page=SimpleNamespace(extract_text=lambda:'2026 Formula 1 Technical Regulations copyright 2025')
    monkeypatch.setattr('pypdf.PdfReader',lambda _:SimpleNamespace(is_encrypted=False,pages=[page]*5))
    with pytest.raises(ValueError,match='wrong regulation PDF identity'):extract(b'%PDF fixture',2025)
