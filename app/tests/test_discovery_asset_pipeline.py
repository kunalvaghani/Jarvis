"""Asset-pipeline boundary tests; fixtures never count as live acquisition."""
from pathlib import Path
import runpy
import json
import shutil
import subprocess
import pytest


@pytest.fixture(autouse=True)
def isolate_production_asset_grants(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import asset_resources
    monkeypatch.setattr(asset_resources,'HOME',tmp_path/'no-production-asset-grants')


def test_full_a_resource_approval_is_exact_scoped_and_nonrefundable(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import asset_resources as resources
    from jarvis.neural.journal import Journal
    from jarvis.discovery.sandbox.budget import Budget,BudgetExceeded
    import hashlib
    home=tmp_path/'permissions';home.mkdir();plan=tmp_path/'plan.md';plan.write_text('reviewed fixture plan')
    monkeypatch.setattr(resources,'HOME',home);monkeypatch.setattr(resources,'PLAN',plan)
    assert resources.applicable(2025,'2025 F1 fixture') is None
    record={'scope':resources.SCOPE,'approved':True,'maximum_asset_bytes':100_000_000,'project_disk_bytes':500_000_000,
        'maximum_transfer_pairs':4,'maximum_parser_input_bytes':100_000_000,'parser_memory_bytes':2*1024**3,'parser_cpu_seconds':60,
        'plan_sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),'paid_usage':False,'source_scripts_allowed':False}
    (home/'authorization.json').write_text(json.dumps(record))
    permission=resources.applicable(2025,'2025 F1 fixture');assert permission['maximum_asset_bytes']==100_000_000
    assert resources.applicable(2025,'unrelated drone') is None
    for i in range(4):assert resources.reserve_pair(permission['sha256'],'fixture-'+str(i))==i
    with pytest.raises(PermissionError,match='exhausted'):resources.reserve_pair(permission['sha256'],'not-an-extension')
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        base=Budget(journal);base.reserve('retained',cpu_s=0,disk_bytes=49_000_000);base.settle('retained',uncertain=True)
        resources.budget(journal,permission['sha256']).reserve('scoped',cpu_s=0,disk_bytes=100_000_000)
        with pytest.raises(BudgetExceeded):base.reserve('unrelated',cpu_s=0,disk_bytes=1)
        assert journal.rows("SELECT disk_bytes FROM discovery_budget WHERE id='retained'")==[{'disk_bytes':49_000_000.0}]
    finally:journal.close()
    plan.write_text('changed plan')
    with pytest.raises(PermissionError,match='reviewed plan'):resources.grant(permission['sha256'])


def test_browser_tab_membership_can_change_during_observation():
    from jarvis.control.routes.browser import BrowserExecutor
    from types import SimpleNamespace
    executor=BrowserExecutor.__new__(BrowserExecutor);executor.active='one';executor.changes=[]
    class Page:
        url='https://example.com/public'
        def title(self):
            executor.tabs['new']=SimpleNamespace(id='new',page=self)
            return 'public research'
    executor.tabs={'one':SimpleNamespace(id='one',page=Page())}
    assert executor.browser_state()['tabs']==[{'tab_id':'one','title':'public research','url':'https://example.com/public','active':True}]
    assert 'new' in executor.tabs


def test_download_format_rows_never_merge_different_formats_or_sizes():
    from jarvis.discovery.adapters.asset_browser_download import download_option
    assert download_option([{'text':'DOWNLOAD'},{'text':'.glb 18.5 MB DOWNLOAD'}])=={
        'format':'glb','declared_bytes':18_500_000,'supported':True}
    assert download_option([{'text':'.blend 128MB DOWNLOAD'}])['supported'] is False
    assert download_option([{'text':'.glb 20MB DOWNLOAD .gltf 96MB DOWNLOAD'}]) is None
    assert download_option([{'text':'.glb 9000GB DOWNLOAD'}]) is None


@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows file creation-time contract')
def test_downloads_known_folder_resolves_without_home_environment(monkeypatch):
    from jarvis.discovery.adapters import browser_handoff as handoff
    monkeypatch.setattr(handoff,'DOWNLOADS',None)
    for name in ('HOME','USERPROFILE','HOMEDRIVE','HOMEPATH'):monkeypatch.delenv(name,raising=False)
    folder=handoff.downloads_folder()
    assert folder.is_absolute() and folder.is_dir()


@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows file creation-time contract')
def test_owned_browser_file_reconciliation_rejects_ambiguous_stale_changed_and_unrelated_files(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import browser_handoff as handoff,asset_resources as resources
    from types import SimpleNamespace
    from io import BytesIO
    import hashlib,os
    uid='a'*32;scope='f'*64;downloads=tmp_path/'Downloads';downloads.mkdir()
    monkeypatch.setattr(handoff,'DOWNLOADS',downloads)
    monkeypatch.setattr(resources,'grant',lambda *a:{})
    home=tmp_path/'grant';(home/'transfer-pairs').mkdir(parents=True);monkeypatch.setattr(resources,'HOME',home)
    folder=tmp_path/'.jarvis-runtime/discovery/browser-handoffs';folder.mkdir(parents=True)
    claim=folder/(uid+'.json');claim.write_text(json.dumps({'uid':uid,'request_ref':'owned-click',
        'resource_grant_sha256':scope,'maximum_bytes':10000}))
    (home/'transfer-pairs/slot-00.json').write_text(json.dumps({'grant_sha256':scope,'request_ref':'owned-click'}))
    asset=SimpleNamespace(candidate_id='sketchfab:'+uid,source_url='https://sketchfab.com/3d-models/fixture-car-'+uid,maximum_bytes=10000)
    options=[(1000,'glb','ref_1')]
    # An unrelated file is never a fallback, even with matching size/timing.
    (downloads/'unrelated.glb').write_bytes(b'x'*1000)
    assert handoff.find(tmp_path,asset,'Fixture Car',options,scope) is None
    path=downloads/'fixture_car.glb';path.write_bytes(b'x'*1000)
    receipt=handoff.find(tmp_path,asset,'Fixture Car',options,scope)
    assert receipt and receipt['source_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    handoff.verify(tmp_path,asset,receipt)
    sink=BytesIO();assert handoff.copy(tmp_path,receipt,10000,sink)['bytes']==1000
    assert sink.getvalue()==path.read_bytes()
    other=downloads/'fixture-car.glb';other.write_bytes(b'x'*1000)
    assert handoff.find(tmp_path,asset,'Fixture Car',options,scope) is None
    assert handoff.find(tmp_path,asset,'Different Car',options,scope) is None
    path.write_bytes(b'y'*1000)
    with pytest.raises(ValueError,match='source changed'):handoff.copy(tmp_path,receipt,10000,BytesIO())
    changed=dict(receipt);changed['source_identity']={**receipt['source_identity'],'created_ns':0}
    with pytest.raises(ValueError,match='creation/size'):handoff.verify(tmp_path,asset,changed)


def test_uncertain_format_handoff_survives_fresh_journal_without_another_click(tmp_path):
    from jarvis.discovery.adapters.asset_browser_download import resolve,DownloadUnavailable
    from jarvis.neural.journal import Journal
    from types import SimpleNamespace
    uid='a'*32;source='https://sketchfab.com/3d-models/test-'+uid;clicks=[];link_available=[False]
    class Registry:
        def __init__(self,actions):pass
        def execute(self,step,cancelled):
            return SimpleNamespace(call_id='fixture-read',evidence='Button "Download" [ref_1]')
    class Route:
        def __init__(self):self.inner=self
        def probe(self,what,**kwargs):
            if what=='url':return source
            if what=='asset_download_option':return {'contexts':[{'text':'.glb 1 KB Download'}]}
            if what=='asset_download_link' and link_available[0]:return {'kind':'archive','url':'https://media.sketchfab.com/models/'+uid+'/archives/model.glb?sig=fixture'}
            return {}
        def capture_model_download(self,*args):
            clicks.append(True)
            raise ValueError('injected uncertain result')
    route=Route();actions=SimpleNamespace(base=tmp_path,control=lambda:SimpleNamespace(browser=lambda p:route))
    asset=SimpleNamespace(provider='sketchfab',candidate_id='sketchfab:'+uid,source_url=source,maximum_bytes=1000,evidence_ref='fixture-rights')
    # Real source rights are tested independently; this fixture exercises only
    # the durable, pre-click boundary across different task Journals.
    from unittest.mock import patch
    with patch('jarvis.discovery.acceptance.artifact',return_value={}):
        for attempt in range(2):
            journal=Journal(tmp_path/('brain-'+str(attempt)+'.sqlite3'))
            try:
                with pytest.raises(ValueError,match='injected uncertain' if attempt==0 else 'no repeat click'):
                    resolve(actions,journal,asset,registry_factory=Registry)
            finally:journal.close()
        link_available[0]=True
        journal=Journal(tmp_path/'brain-readonly-reconciliation.sqlite3')
        try:
            recovered=resolve(actions,journal,asset,registry_factory=Registry)
            assert recovered['file_format']=='glb'
            assert recovered['url'].startswith('https://media.sketchfab.com/models/'+uid+'/archives/')
        finally:journal.close()
    assert len(clicks)==1
    assert json.loads((tmp_path/'.jarvis-runtime/discovery/browser-handoffs'/ (uid+'.json')).read_text())['state'].startswith('claimed-before')


def test_private_download_href_is_bound_to_selected_model_and_not_publicly_exported():
    from jarvis.control.web.agent_browser_backend import AgentBrowserExecutor,Reply
    from jarvis.control.policy import Policy
    uid='a'*32;page='https://sketchfab.com/3d-models/test-'+uid
    signed='https://media.sketchfab.com/models/'+uid+'/archives/model.zip?token=private-example'
    executor=AgentBrowserExecutor(Policy(),runner=lambda *a:None)
    executor.own_tab='owned';executor._own_tab=lambda:False;executor._final_url=lambda:page
    executor._ref=lambda ref:ref
    executor._call=lambda *a,**k:Reply(success=True,data={'url':signed})
    result=executor.probe('asset_download_link',uid=uid,ref='ref_1')
    assert result=={'kind':'archive','url':signed,'source_url':page}
    executor._call=lambda *a,**k:Reply(success=True,data={'url':signed.replace('model.zip','model.glb')})
    assert executor.probe('asset_download_link',uid=uid,ref='ref_1')['url'].split('?')[0].endswith('.glb')
    from jarvis.control.types import ControlError
    with pytest.raises(ControlError):executor.probe('asset_download_link',uid='b'*32,ref='ref_1')
    executor._call=lambda *a,**k:Reply(success=True,data={'url':signed.replace('/archives/model.zip','/files/model_file.binz')})
    assert executor.probe('asset_download_link',uid=uid,ref='ref_1')['kind']=='unavailable'


def test_official_archive_resolver_keeps_signed_url_ephemeral(tmp_path):
    from jarvis.discovery.adapters.asset_browser_download import resolve,DownloadUnavailable
    from jarvis.neural.journal import Journal
    from types import SimpleNamespace
    uid='a'*32;source='https://sketchfab.com/3d-models/test-'+uid
    signed='https://media.sketchfab.com/models/'+uid+'/archives/model.zip?token=private-example'
    calls=[];available=[True]
    class Registry:
        def __init__(self,actions):pass
        def execute(self,step,cancelled):
            calls.append(step)
            return SimpleNamespace(call_id='actual-fixture-'+str(len(calls)),evidence='Link "Download glTF ZIP" [ref_1]')
    class Route:
        def probe(self,what,**kwargs):
            if what=='url':return source
            assert kwargs=={'uid':uid,'ref':'ref_1'}
            return {'kind':'archive','url':signed} if available[0] else {'kind':'unavailable'}
    route=Route();actions=SimpleNamespace(control=lambda:SimpleNamespace(browser=lambda profile:route))
    asset=SimpleNamespace(provider='sketchfab',candidate_id='sketchfab:'+uid,source_url=source,maximum_bytes=20_000_000)
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        result=resolve(actions,journal,asset,registry_factory=Registry)
        assert result['url']==signed
        body=journal.get(result['receipt_ref'])
        assert 'private-example' not in body and 'token=' not in body
        assert [step['action'] for step in calls]==['web_open','web_read']
        available[0]=False
        with pytest.raises(DownloadUnavailable,match='retained browser evidence'):resolve(actions,journal,asset,registry_factory=Registry)
        assert all(step['action']!='web_act' for step in calls)
    finally:journal.close()


def test_download_dialog_opener_is_not_replayed_and_login_controls_are_never_clicked(tmp_path):
    from jarvis.discovery.adapters.asset_browser_download import resolve,DownloadUnavailable
    from jarvis.neural.journal import Journal
    from types import SimpleNamespace
    uid='a'*32;source='https://sketchfab.com/3d-models/test-'+uid;calls=[];opened=[False]
    class Registry:
        def __init__(self,actions):pass
        def execute(self,step,cancelled):
            calls.append(step)
            if step['action']=='web_act':opened[0]=True;raise RuntimeError('fixture lost click reply')
            evidence=('Dialog "Log in to download"\nButton "Log in" [ref_2]' if opened[0] else 'Button "\ue094 Download 3D Model" [ref_1]')
            return SimpleNamespace(call_id='fixture-'+str(len(calls)),evidence=evidence)
    route=SimpleNamespace(probe=lambda what,**kwargs:source)
    actions=SimpleNamespace(control=lambda:SimpleNamespace(browser=lambda profile:route))
    asset=SimpleNamespace(provider='sketchfab',candidate_id='sketchfab:'+uid,source_url=source,maximum_bytes=20_000_000)
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        with pytest.raises(DownloadUnavailable):resolve(actions,journal,asset,registry_factory=Registry)
        clicks=[step for step in calls if step['action']=='web_act']
        assert len(clicks)==1 and json.loads(clicks[0]['content'])=={'ref':'ref_1'}
        diagnostic=json.loads(journal.rows("SELECT body FROM artifacts WHERE data_type='Report'")[0]['body'])
        assert diagnostic['login_required_in_dialog'] and diagnostic['dialog_observed']
        assert diagnostic['download_dialog_opener_acknowledged'] is False
    finally:journal.close()


def test_unconfigured_personal_browser_prefers_connected_extension_and_preserves_rollback(tmp_path,monkeypatch):
    from jarvis.control.service import ControlService
    from jarvis.control.settings import ControlSettings
    from jarvis.control.web import extension_runner,agent_browser_backend
    from jarvis.control.routes import browser
    from jarvis.control.policy import Policy
    probes=[]
    class Linked:
        binary=tmp_path/'fixed-host.py';auto_connect=True
        def available(self):probes.append('extension');return True
    class Legacy:
        from jarvis.control.types import Route
        route=Route.BROWSER
        def __init__(self,*a,**k):pass
        def start(self):pass
        def close(self):pass
    monkeypatch.delenv('JARVIS_WEB_BACKEND',raising=False)
    monkeypatch.setattr(extension_runner,'ExtensionRunner',Linked)
    monkeypatch.setattr(browser,'BrowserExecutor',Legacy)
    # BrowserRunner's file/proc integration is not part of this selector test.
    monkeypatch.setattr(agent_browser_backend,'BrowserRunner',lambda *a,**k:None)
    policy=Policy(allowed_roots=(tmp_path,))
    for extra,expected in [({},agent_browser_backend.AgentBrowserExecutor),({'web_backend':'legacy'},Legacy)]:
        settings=ControlSettings(allowed_roots=(tmp_path,),test_profile=tmp_path/'test',personal_profile=tmp_path/'personal',extra=extra)
        service=ControlService(settings,lambda a:False,lambda e:None,policy)
        try:assert isinstance(service.browser('personal').inner,expected)
        finally:service.close()
    assert probes==['extension','extension']


def test_fingerprint_covers_extension_and_main_entrypoint(tmp_path):
    root=Path(__file__).resolve().parents[2]
    fingerprint=runpy.run_path(str(root/'docs/lab/run_checks.py'))['source_fingerprint']
    helpers=tmp_path/'docs/lab';helpers.mkdir(parents=True)
    for name in ('run_checks.py','qualify_ah_mechanics.py','summarize_ah_regression.py'):(helpers/name).write_text('# fixture')
    source=tmp_path/'app/browser_extension/jarvis/background.js';source.parent.mkdir(parents=True)
    source.write_text('const revision=1;');entry=tmp_path/'app/main.py';entry.write_text('# entry v1')
    before=fingerprint(tmp_path)
    source.write_text('const revision=2;');changed=fingerprint(tmp_path)
    assert changed!=before
    entry.write_text('# entry v2');assert fingerprint(tmp_path)!=changed


def test_owned_inspection_process_has_a_real_committed_memory_cap():
    import os,sys
    if os.name!='nt':pytest.skip('Windows Job Object qualification; no unverified platform fallback')
    from jarvis.repo_acquisition import command
    script="try:\n bytearray(128*1024*1024)\n print('unbounded')\nexcept MemoryError:\n print('memory_limited')\n"
    usage={}
    raw=command([sys.executable,'-I','-B','-c',script],timeout=10,limit=1000,
        resource_limits={'memory_bytes':64*1024*1024,'cpu_seconds':2},usage=usage)
    assert raw.strip()==b'memory_limited'
    assert 0<usage['peak_process_committed_bytes']<=64*1024*1024


def test_inspector_preflight_rejects_external_resources_cycles_and_oversized_resources():
    from jarvis.discovery.adapters import asset_inspection_worker as worker
    import base64
    helper=runpy.run_path(str(Path(__file__).resolve().parents[2]/'docs/lab/qualify_asset_inspector.py'))
    cube,external=helper['cases']()
    with pytest.raises(worker.Rejected,match='EXTERNAL_OR_ESCAPING_RESOURCE'):worker.inspect(external)
    doc=json.loads(base64.b64decode(external['body']));doc['nodes'][0]['children']=[0]
    with pytest.raises(worker.Rejected,match='INVALID_NODE_GRAPH'):
        worker.gltf_preflight(json.dumps(doc).encode(),'gltf','canonical.gltf',{})
    cube['resources']={'oversized.bin':'x'*28_000_001}
    with pytest.raises(worker.Rejected,match='INPUT_BYTE_LIMIT'):worker.inspect(cube)


def test_inspector_qualification_rechecks_retained_results_and_dispatch_identity(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import asset_inspection as adapter
    monkeypatch.setattr(adapter.mechanics,'SETUP',tmp_path)
    folder=tmp_path/'invocations';folder.mkdir()
    result={'status':'REJECTED','code':'EXTERNAL_OR_ESCAPING_RESOURCE','cpu_s':.01}
    import hashlib
    digest=hashlib.sha256(json.dumps(result,separators=(',',':')).encode()).hexdigest()
    record={'slot':7,'worker_sha256':'a'*64,'request_ref':'request-one','inspection':result,'result_sha256':digest}
    target=folder/'inspection-result-7.json';target.write_text(json.dumps(record))
    ledger=folder/'slot-07.json';ledger.write_text(json.dumps({'worker_sha256':'a'*64,'request_ref':'request-one','operation':'asset_inspection'}))
    assert adapter.completed_record(7,'a'*64)==record
    record['inspection']['code']='FORGED';target.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='result changed'):adapter.completed_record(7,'a'*64)
    record['inspection']=result.copy();record['request_ref']='other';target.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='dispatch ledger'):adapter.completed_record(7,'a'*64)


def test_dense_geometric_fragments_are_explicit_aggregates_not_invented_mechanical_parts():
    from jarvis.discovery.adapters.asset_inspection_worker import groups
    vertices=[];faces=[]
    for i in range(501):
        base=len(vertices);vertices.extend([(i*3,0,0),(i*3+1,0,0),(i*3,1,0)])
        faces.append([base,base+1,base+2])
    metadata={};result=groups(vertices,faces,metadata)
    assert metadata=={'connected_regions':501,'aggregated':True}
    assert result==[list(range(501))]
    metadata={};result=groups(vertices[:6],faces[:2],metadata)
    assert metadata=={'connected_regions':2,'aggregated':False} and result==[[0],[1]]
    metadata={};result=groups(vertices[:6],faces[:2],metadata,limit=1)
    assert metadata=={'connected_regions':2,'aggregated':True} and result==[[0,1]]


def test_parser_qualification_does_not_claim_when_unavailable_cancelled_or_exhausted(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import asset_inspection as adapter
    monkeypatch.setattr(adapter.mechanics,'SETUP',tmp_path)
    monkeypatch.setattr(adapter,'qualification',lambda *a:{'runtime_ready':False})
    monkeypatch.setattr(adapter,'worker_hash',lambda:'a'*64)
    state={'ready':False,'used_slots':0}
    monkeypatch.setattr(adapter.mechanics,'environment',lambda:state)
    with pytest.raises(ValueError,match='environment unavailable'):adapter.ensure_qualified(None)
    state['ready']=True
    with pytest.raises(ValueError,match='cancelled'):adapter.ensure_qualified(None,cancelled=lambda:True)
    state['used_slots']=49
    with pytest.raises(PermissionError,match='two approved'):adapter.ensure_qualified(None)
    assert not list(tmp_path.glob('*.claim'))


def test_parser_qualification_uncertain_claim_never_dispatches_again(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import asset_inspection as adapter
    from jarvis.neural.journal import Journal
    monkeypatch.setattr(adapter.mechanics,'SETUP',tmp_path)
    monkeypatch.setattr(adapter,'qualification',lambda *a:{'runtime_ready':False})
    monkeypatch.setattr(adapter,'worker_hash',lambda:'a'*64)
    monkeypatch.setattr(adapter.mechanics,'environment',lambda:{'ready':True,'used_slots':0})
    calls=[]
    def fail(*a,**k):
        calls.append(True)
        raise ValueError('injected uncertain worker')
    monkeypatch.setattr(adapter,'invoke',fail)
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        with pytest.raises(ValueError,match='uncertain worker'):adapter.ensure_qualified(journal)
        with pytest.raises(FileExistsError):adapter.ensure_qualified(journal)
        assert len(calls)==1
        assert len(list(tmp_path.glob('*.claim')))==1
    finally:journal.close()


def test_inspection_reconciles_lost_publication_and_reuses_without_dispatch(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import asset_inspection as adapter
    from jarvis.neural.journal import Journal
    import hashlib
    sha='d'*64;calls=[]
    original=b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'
    file=tmp_path/'original.obj';file.write_bytes(original)
    download={'relative_file':'original.obj','sha256':hashlib.sha256(original).hexdigest(),'file_format':'obj','acquisition_ref':'admission-fixture'}
    monkeypatch.setattr(adapter,'verified_download',lambda *a:{'download':download})
    monkeypatch.setattr(adapter,'worker_hash',lambda:sha)
    monkeypatch.setattr(adapter,'qualification',lambda *a:{'runtime_ready':True})
    setup=tmp_path/'setup';folder=setup/'invocations';folder.mkdir(parents=True)
    monkeypatch.setattr(adapter.mechanics,'SETUP',setup)
    def invoke(payload,journal,**kwargs):
        calls.append(payload)
        request=journal.put({'source_sha256':payload['source_sha256'],'entrypoint':payload['entrypoint'],'context':kwargs['context']},'Report')
        result={'parser':'trimesh','version':'5.2.0','source_sha256':payload['source_sha256'],'physical_validation':False,
            'original_modified':False,'cpu_s':.01,'units_resolved':False,'parts':[{'component_id':'fixture-triangle',
            'mass_kg':None,'inertia_kg_m2':None,'joints_verified':False,'bounds':[[0,0,0],[1,1,0]],
            'preview_vertices':[[0,0,0],[1,0,0],[0,1,0]],'preview_triangles':[[0,1,2]]}]}
        digest=hashlib.sha256(json.dumps(result,separators=(',',':')).encode()).hexdigest()
        record={'inspection':result,'worker_sha256':sha,'request_ref':request,'slot':0,'result_sha256':digest}
        (folder/'slot-00.json').write_text(json.dumps({'worker_sha256':sha,'request_ref':request,'operation':'asset_inspection'}))
        (folder/'inspection-result-0.json').write_text(json.dumps(record))
        return record
    monkeypatch.setattr(adapter,'invoke',invoke)
    publish=adapter.publish_inspection
    monkeypatch.setattr(adapter,'publish_inspection',lambda *a:(_ for _ in ()).throw(ValueError('injected lost publication')))
    journal=Journal(tmp_path/'brain.sqlite3')
    from jarvis.discovery.adapters import asset_rights
    permission_ref=journal.put({},'Report')
    from types import SimpleNamespace
    monkeypatch.setattr(asset_rights,'verify',lambda *a:(SimpleNamespace(maximum_bytes=20_000_000,evidence_ref=permission_ref),{}))
    try:
        with pytest.raises(ValueError,match='lost publication'):adapter.inspect_download(tmp_path,journal,'download-fixture')
    finally:journal.close()
    monkeypatch.setattr(adapter,'publish_inspection',publish)
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        ref,receipt=adapter.inspect_download(tmp_path,journal,'download-fixture')
        assert len(calls)==1 and receipt['part_count']==1
        assert adapter.inspect_download(tmp_path,journal,'download-fixture')==(ref,receipt)
        assert len(calls)==1
        mismatched_ref=journal.put({'resource_grant_sha256':'f'*64},'Report')
        monkeypatch.setattr(asset_rights,'verify',lambda *a:(SimpleNamespace(maximum_bytes=20_000_000,evidence_ref=mismatched_ref),{}))
        with pytest.raises(ValueError,match='resource profile differs'):adapter.verify_inspection(tmp_path,journal,ref)
        monkeypatch.setattr(asset_rights,'verify',lambda *a:(SimpleNamespace(maximum_bytes=20_000_000,evidence_ref=permission_ref),{}))
        (tmp_path/receipt['relative_file']).write_text('{}')
        with pytest.raises(ValueError,match='output changed'):adapter.verify_inspection(tmp_path,journal,ref)
        assert len(calls)==1
    finally:journal.close()


def test_actual_extension_link_probe_is_owned_bounded_and_inert():
    node=shutil.which('node')
    if not node:pytest.skip('Existing Node runtime unavailable; no install authorized')
    source=Path(__file__).resolve().parents[1]/'browser_extension/jarvis/background.js'
    script=r'''
const vm=require('vm'),fs=require('fs'),assert=require('assert');
const event={addListener(){}};const tabs=new Map();let reads=0,networkListener=null;const cancellations=[];
const chrome={storage:{session:{get:async()=>({jarvisTabs:[]}),set:async()=>{}}},
 runtime:{connectNative:()=>({onMessage:event,onDisconnect:event,postMessage(){}}),onStartup:event,onInstalled:event,getManifest:()=>({version:'fixture'})},
 alarms:{create(){},onAlarm:event},tabGroups:{query:async()=>[{id:1,windowId:1}],get:async()=>({windowId:1}),update:async()=>{}},
 tabs:{onRemoved:event,query:async()=>[...tabs.values()],create:async(o)=>{const t={id:8,windowId:1,groupId:1,status:'complete',url:o.url||'about:blank'};tabs.set(8,t);return t},
 group:async()=>1,update:async(id,o)=>Object.assign(tabs.get(id),o),get:async(id)=>tabs.get(id)},
 debugger:{onDetach:event,onEvent:{addListener(fn){networkListener=fn}},attach:async()=>{},sendCommand:async(target,method,p)=>{
   if(method==='Runtime.evaluate'){reads++;return {result:{value:vm.runInContext(p.expression,context)}}}
   if(method==='Network.getResponseBody')return {body:JSON.stringify({gltf:{url:'https://media.sketchfab.com/models/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/archives/model.zip?sig=fixture',size:10000},
      source:{url:'https://media.sketchfab.com/models/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/archives/source.zip?sig=fixture',size:90000}}),base64Encoded:false};
   if(method==='Page.captureScreenshot')return {data:'fixture-jpeg-base64'};
   if(method==='Browser.cancelDownload'){cancellations.push(p.guid);return {}}return {};
 }}};
const anchors=Array.from({length:300},(_,i)=>({href:'https://example.com/model/'+i,innerText:'part '+i}));
anchors.unshift({href:'javascript:alert(1)'},{href:'https://user:pass@example.com/private'},
 {href:'https://example.com/download?X-Amz-Signature=never-export'});
const context=vm.createContext({chrome,URL,console,setTimeout:fn=>fn(),document:{querySelectorAll:()=>anchors}});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
(async()=>{
 await assert.rejects(()=>vm.runInContext("run(['get','links'],'fixture')",context),/no Jarvis tab/);
 assert.equal(reads,0);
 await vm.runInContext("run(['open','https://example.com/research'],'fixture')",context);
 const result=await vm.runInContext("run(['get','links'],'fixture')",context);
 assert.equal(result.links.length,200);assert.equal(result.links[0].url,'https://example.com/model/0');
 assert(!JSON.stringify(result).includes('user:pass'));assert.equal(reads,1);
 await assert.rejects(()=>vm.runInContext("run(['get','model_screenshot','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'],'fixture')",context),/selected official model/);
 tabs.get(8).url='https://sketchfab.com/3d-models/test-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
 const shot=await vm.runInContext("run(['get','model_screenshot','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'],'fixture')",context);
 assert.equal(shot.data,'fixture-jpeg-base64');assert.equal(shot.format,'jpeg');
 await vm.runInContext("run(['get','model_download_watch','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'],'fixture')",context);
 networkListener({tabId:8},'Network.responseReceived',{requestId:'selected',response:{url:'https://sketchfab.com/i/models/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/download',mimeType:'application/json',status:200}});
 networkListener({tabId:8},'Network.loadingFinished',{requestId:'selected',encodedDataLength:200});
 const formats=await vm.runInContext("run(['get','model_download_metadata','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'],'fixture')",context);
 assert.equal(formats.candidates.length,1);assert.equal(formats.candidates[0].size,10000);assert.equal(formats.candidates[0].format,'zip');
 const exhausted=await vm.runInContext("run(['get','model_download_metadata','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'],'fixture')",context);
 assert.equal(exhausted.candidates.length,0);
 vm.runInContext("onNode=async()=>({format:'glb',size:1000});mouse=async()=>{}",context);
 await assert.rejects(()=>vm.runInContext("run(['model_download','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','e1','999'],'fixture')",context),/exceeds the admitted byte cap/);
 vm.runInContext("mouse=async()=>{chrome.debugger.fakeDownloadEvent();}",context);
 chrome.debugger.fakeDownloadEvent=()=>{
   networkListener({tabId:8},'Page.downloadWillBegin',{guid:'other-model',url:'https://media.sketchfab.com/models/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/archives/a.glb'});
   networkListener({tabId:8},'Page.downloadWillBegin',{guid:'owned-guid',url:'https://media.sketchfab.com/models/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/archives/a.glb?sig=fixture'});
 };
 const handoff=await vm.runInContext("run(['model_download','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','e1','1000'],'fixture')",context);
 assert.deepEqual(cancellations,['owned-guid']);assert.equal(handoff.browser_cancel_acknowledged,true);assert.equal(handoff.format,'glb');
 chrome.debugger.fakeDownloadEvent=()=>{
   networkListener({tabId:9},'Page.windowOpen',{url:'https://media.sketchfab.com/models/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/archives/unowned.glb'});
   networkListener({tabId:8},'Page.windowOpen',{url:'https://media.sketchfab.com/models/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/archives/other.glb'});
   networkListener({tabId:8},'Page.windowOpen',{url:'https://media.sketchfab.com/models/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/archives/popup.glb?sig=fixture'});
 };
 const popup=await vm.runInContext("run(['model_download','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','e1','1000'],'fixture')",context);
 assert(popup.url.includes('/popup.glb'));assert.equal(popup.handoff_event,'Page.windowOpen');
 assert.equal(popup.browser_cancel_acknowledged,false);assert.equal(popup.browser_bytes_measured,false);
 assert.deepEqual(cancellations,['owned-guid']);
 assert(!JSON.parse(fs.readFileSync(process.argv[2],'utf8')).permissions.includes('downloads'));
 console.log('owned public-link contract passed');
})().catch(e=>{console.error(e.name);process.exitCode=1});
'''
    result=subprocess.run([node,'-e',script,str(source),str(source.with_name('manifest.json'))],capture_output=True,text=True,timeout=10)
    assert result.returncode==0 and result.stdout.strip()=='owned public-link contract passed'


def test_browser_link_observation_rejects_navigation_and_filters_unsafe_hrefs():
    from jarvis.control.web.agent_browser_backend import AgentBrowserExecutor,Reply
    from jarvis.control.policy import Policy
    from jarvis.control.types import ControlError
    from unittest.mock import Mock
    executor=AgentBrowserExecutor(Policy(),Mock())
    executor.run.auto_connect=False
    executor._final_url=Mock(return_value='https://example.com/research')
    executor._call=Mock(return_value=Reply(success=True,data={'url':'https://example.com/research','links':[
        {'url':'javascript:alert(1)'},{'url':'https://user:pass@example.com/'},
        {'url':'https://example.com/download?token=never-export'}, {'url':'https://example.com/model','text':'actual source'}]}))
    assert executor.probe('links')=={'url':'https://example.com/research','links':[{'url':'https://example.com/model','text':'actual source'}]}
    executor._final_url=Mock(side_effect=['https://example.com/research','https://example.com/changed'])
    with pytest.raises(ControlError,match='changed'):executor.probe('links')


def test_download_transport_pins_dns_and_never_follows_unadmitted_redirects():
    from jarvis.discovery.adapters.asset_transport import address,stream,TransferError
    from io import BytesIO
    def public(*args,**kw):return [(None,None,None,None,('93.184.216.34',443))]
    assert address('https://assets.example/model.glb',{'assets.example'},public)[1]=='93.184.216.34'
    with pytest.raises(TransferError):address('https://assets.example/a',{'assets.example'},lambda *a,**k:[(None,None,None,None,('127.0.0.1',443))])
    with pytest.raises(TransferError):address('https://assets.example/a',{'assets.example'},lambda *a,**k:[(None,None,None,None,('224.0.0.1',443))])
    from jarvis.discovery.adapters.asset_transport import public_address
    assert public_address('64:ff9b::5db8:d822')
    assert not public_address('64:ff9b::7f00:1') and not public_address('64:ff9b::a00:1')
    class Response:
        status=302
        def getheader(self,key,default=None):return 'https://unadmitted.example/secret' if key=='Location' else default
    calls=[]
    class Connection:
        def __init__(self,host,ip,timeout):calls.append((host,ip))
        def request(self,method,path,headers):assert 'Authorization' not in headers and method=='GET'
        def getresponse(self):return Response()
        def close(self):pass
    with pytest.raises(TransferError,match='admitted HTTPS'):stream('https://assets.example/a',{'assets.example'},100,BytesIO(),resolver=public,connection=Connection)
    assert calls==[('assets.example','93.184.216.34')]


def test_download_partial_and_oversized_results_never_become_complete():
    from jarvis.discovery.adapters.asset_transport import stream,TransferError
    from io import BytesIO
    class Response:
        status=200
        def __init__(self):self.body=BytesIO(b'abcde')
        def getheader(self,key,default=None):return '6' if key=='Content-Length' else default
        def read(self,n):return self.body.read(n)
    class Connection:
        def __init__(self,*a):pass
        def request(self,*a,**k):pass
        def getresponse(self):return Response()
        def close(self):pass
    resolver=lambda *a,**k:[(None,None,None,None,('93.184.216.34',443))]
    partial=BytesIO()
    with pytest.raises(TransferError,match='incomplete'):stream('https://assets.example/a',{'assets.example'},10,partial,resolver=resolver,connection=Connection)
    assert partial.getvalue()==b'abcde'
    with pytest.raises(TransferError,match='declared download size'):stream('https://assets.example/a',{'assets.example'},4,BytesIO(),resolver=resolver,connection=Connection)


def test_archive_rejects_traversal_scripts_symlinks_and_case_collisions():
    from jarvis.discovery.adapters.asset_files import archive_inventory
    from io import BytesIO
    import zipfile,stat
    def archive(names):
        body=BytesIO()
        with zipfile.ZipFile(body,'w') as z:
            for name in names:z.writestr(name,b'fixture')
        return body.getvalue()
    for names in [['../escape.obj'],['C:/escape.obj'],['CON.obj'],['model.py'],['A.obj','a.obj']]:
        with pytest.raises(ValueError):archive_inventory(archive(names))
    link=zipfile.ZipInfo('model.obj');link.external_attr=(stat.S_IFLNK|0o777)<<16
    with pytest.raises(ValueError,match='linked'):archive_inventory(archive([link]))
    good=archive_inventory(archive(['model.obj','LICENSE.txt']))
    assert len(good['entries'])==2 and not good['extracted'] and not good['code_executed']


def test_browser_research_reconciles_once_and_never_accepts_stale_page():
    from jarvis.discovery.adapters.browser_research import research,public_asset_link
    from types import SimpleNamespace
    from urllib.parse import urlencode
    calls=[]
    class Registry:
        def __init__(self,actions):pass
        def execute(self,step,cancelled):
            calls.append(step)
            data=({'ok':False,'executed':True} if step['action']=='web_open' else
                  {'kind':'browser_links','url':'https://www.bing.com/search?'+urlencode({'q':'2025 Formula 1 model'}),
                   'links':[{'url':'https://github.com/author/model?token=never-retain','text':'author model'}],'content_is_untrusted':True})
            return SimpleNamespace(call_id='fixture-only',evidence=json.dumps(data))
    result=research(SimpleNamespace(),'2025 Formula 1 model',registry_factory=Registry)
    assert result['status']=='OBSERVED' and len(calls)==2
    assert result['candidates'][0]['url']=='https://github.com/author/model'
    assert not result['candidates'][0]['identity_verified']
    assert research(SimpleNamespace(),'2026 Formula 1 model',registry_factory=Registry)['status']=='BLOCKED_BROWSER_RESEARCH'
    assert public_asset_link('https://github.com.evil.example/model') is None
    assert public_asset_link('javascript:alert(1)') is None


def test_provider_read_budget_and_source_cache_survive_fresh_client(tmp_path):
    from jarvis.discovery.adapters.provider_metadata import MetadataClient,load
    from jarvis.neural.journal import Journal
    calls=[]
    def fetch(url,hosts,cap,sink,**kwargs):calls.append(url);sink.write(b'{"items":[]}')
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        client=MetadataClient(tmp_path,journal,'fixture-project',fetcher=fetch)
        ref,data=client.get('github','https://api.github.com/search/repositories?q=mechanism')
        fresh=MetadataClient(tmp_path,journal,'fixture-project',fetcher=fetch)
        assert fresh.get('github','https://api.github.com/search/repositories?q=mechanism')==(ref,data)
        assert len(calls)==1 and load(tmp_path,journal,ref)[1]=={'items':[]}
        for i in range(11):fresh.get('github','https://api.github.com/search/repositories?q=object'+str(i))
        with pytest.raises(ValueError,match='exhausted'):MetadataClient(tmp_path,journal,'fixture-project',fetcher=fetch).get('github','https://api.github.com/repos/a/b')
        assert len(calls)==12
    finally:journal.close()


def test_transfer_requires_real_bytes_reuses_completed_record_and_rejects_tampering(tmp_path):
    from jarvis.discovery.adapters.provider_metadata import MetadataClient
    from jarvis.discovery.adapters.asset_rights import issue
    from jarvis.discovery.adapters.asset_acquisition import transfer,verify
    from jarvis.neural.journal import Journal
    import base64,hashlib
    model=b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n';revision='b'*40
    document=json.dumps({'version':1,'assets':[{'path':'part.obj','license':'CC0-1.0','creator':'Fixture artist','title':'Mechanical part'}]}).encode()
    blob=lambda raw:hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    tree={'tree':[{'path':'part.obj','type':'blob','mode':'100644','sha':blob(model),'size':len(model)}]}
    rights={'type':'file','path':'ASSET_LICENSES.json','size':len(document),'sha':blob(document),'encoding':'base64','content':base64.b64encode(document).decode()}
    def metadata(url,hosts,cap,sink,**kw):sink.write(json.dumps(tree if '/git/trees/' in url else rights).encode())
    journal=Journal(tmp_path/'brain.sqlite3');calls=[]
    try:
        client=MetadataClient(tmp_path,journal,'transfer-fixture',fetcher=metadata)
        tr,_=client.get('github','https://api.github.com/repos/artist/models/git/trees/'+revision)
        rr,_=client.get('github','https://api.github.com/repos/artist/models/contents/ASSET_LICENSES.json?ref='+revision)
        admission,_=issue(tmp_path,journal,{'rule':'github-asset-manifest-v1','owner':'artist','repo':'models','revision':revision,'path':'part.obj','tree_ref':tr,'rights_ref':rr})
        def download(url,hosts,cap,sink,**kw):
            calls.append(url);sink.write(model)
            return {'bytes':len(model),'final_host':'raw.githubusercontent.com','redirects':0,'etag':''}
        ref,result=transfer(tmp_path,journal,admission,fetcher=download)
        assert result['download']['sha256']==hashlib.sha256(model).hexdigest()
        assert transfer(tmp_path,journal,admission,fetcher=download)==(ref,result) and len(calls)==1
        path=tmp_path/result['download']['relative_file'];path.write_bytes(b'not the original')
        with pytest.raises(ValueError):verify(tmp_path,journal,ref)
        assert len(calls)==1
    finally:journal.close()


def test_metadata_endpoint_cannot_smuggle_an_unlicensed_model_download():
    from jarvis.discovery.adapters.provider_metadata import endpoint
    for path in ['/repos/a/b/contents/model.glb','/repos/a/b/zipball/main','/repos/a/b/git/blobs/'+'a'*40,
                 '/repos/a/b/contents/..%2fmodel.glb']:
        with pytest.raises(ValueError):endpoint('github','https://api.github.com'+path)
    assert endpoint('github','https://api.github.com/repos/a/b/contents/ASSET_LICENSES.json').hostname=='api.github.com'
    with pytest.raises(ValueError):endpoint('sketchfab','https://api.sketchfab.com/v3/models/'+'a'*32+'/download')


def test_sketchfab_license_identity_accepts_canonical_uri_and_rejects_conflicting_id(tmp_path):
    from jarvis.discovery.adapters.provider_metadata import MetadataClient
    from jarvis.discovery.adapters.asset_rights import issue,verify
    from jarvis.neural.journal import Journal
    uid='a'*32;license_id='b'*32
    declared={'uri':'https://api.sketchfab.com/v3/licenses/'+license_id,'url':'http://creativecommons.org/licenses/by/4.0/'}
    model={'uid':uid,'name':'2025 McLaren F1 concept','license':declared,'user':{'username':'Fixture artist'},
        'viewerUrl':'https://sketchfab.com/3d-models/test-'+uid,'isDownloadable':True}
    def fetch(url,hosts,cap,sink,**kwargs):sink.write(json.dumps({'results':[declared]} if url.endswith('/licenses') else model).encode())
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        client=MetadataClient(tmp_path,journal,'uri-license-fixture',fetcher=fetch)
        license_ref,_=client.get('sketchfab','https://api.sketchfab.com/v3/licenses')
        model_ref,_=client.get('sketchfab','https://api.sketchfab.com/v3/models/'+uid)
        proof={'rule':'sketchfab-license-v1','uid':uid,'model_ref':model_ref,'licenses_ref':license_ref}
        ref,availability=issue(tmp_path,journal,proof,target_year=2025)
        asset,_=verify(tmp_path,journal,ref)
        assert asset.license_spdx=='CC-BY-4.0' and asset.identity_status=='author_declared_concept'
        assert availability['download_status']=='BLOCKED_PROVIDER_AUTHENTICATION'
        from jarvis.discovery.adapters import asset_rights
        real_load=asset_rights.load
        def conflicting(base,store,ref):
            record,data=real_load(base,store,ref)
            if ref==model_ref:data={**data,'license':{**data['license'],'uid':'c'*32}}
            return record,data
        from unittest.mock import patch
        with patch.object(asset_rights,'load',conflicting):
            with pytest.raises(ValueError,match='contradicts'):issue(tmp_path,journal,proof,target_year=2025)
    finally:journal.close()


def test_general_discovery_uses_observed_repository_and_per_asset_proof(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import asset_discovery as discovery
    from jarvis.discovery.adapters.provider_metadata import MetadataClient
    from jarvis.discovery.adapters.asset_rights import verify
    from jarvis.neural.journal import Journal
    from types import SimpleNamespace
    import base64,hashlib
    revision='c'*40
    model=b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'
    manifest=json.dumps({'version':1,'assets':[{'path':'hinge.obj','creator':'Fixture engineer','license':'CC0-1.0','title':'Example hinge'}]}).encode()
    blob=lambda raw:hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    calls=[]
    def fetch(url,hosts,cap,sink,**kwargs):
        calls.append(url)
        if 'sketchfab' in url:data={'results':[]}
        elif '/commits/' in url:data={'sha':revision}
        elif '/git/trees/' in url:data={'tree':[{'path':'hinge.obj','type':'blob','mode':'100644','sha':blob(model),'size':len(model)},
                                                           {'path':'ASSET_LICENSES.json','type':'blob','mode':'100644'}]}
        elif '/contents/' in url:data={'type':'file','path':'ASSET_LICENSES.json','size':len(manifest),'sha':blob(manifest),'encoding':'base64','content':base64.b64encode(manifest).decode()}
        else:data={'default_branch':'main'}
        sink.write(json.dumps(data).encode())
    monkeypatch.setattr(discovery,'research',lambda *a,**k:{'status':'OBSERVED','candidates':[{'url':'https://github.com/example/hinges','provider':'github.com'}]})
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        client=MetadataClient(tmp_path,journal,'general-hinge-fixture',fetcher=fetch)
        result=discovery.discover(SimpleNamespace(base=tmp_path),journal,'general-hinge-fixture','mechanical hinge model',client=client)
        assert result['original_files_acquired']==0 and result['engineering_identity_verified'] is False
        assert len(result['qualified_rights'])==1
        asset,availability=verify(tmp_path,journal,result['qualified_rights'][0]['acquisition_ref'])
        assert asset.creator=='Fixture engineer' and availability['download_url'].endswith('/hinge.obj')
        before=len(calls)
        again=discovery.discover(SimpleNamespace(base=tmp_path),journal,'general-hinge-fixture','mechanical hinge model',
            client=MetadataClient(tmp_path,journal,'general-hinge-fixture',fetcher=fetch))
        assert again['qualified_rights']==result['qualified_rights'] and len(calls)==before
    finally:journal.close()


def test_rejected_browser_license_falls_back_to_downloadable_catalog(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import asset_discovery as discovery
    from jarvis.discovery.adapters.provider_metadata import MetadataClient
    from jarvis.discovery.adapters.asset_rights import verify
    from jarvis.neural.journal import Journal
    from types import SimpleNamespace
    bad='a'*32;good='b'*32;cc='c'*32;nc='d'*32;calls=[]
    def license(uid,url):return {'uri':'https://api.sketchfab.com/v3/licenses/'+uid,'url':url}
    licensed=license(cc,'http://creativecommons.org/licenses/by/4.0/')
    restricted=license(nc,'http://creativecommons.org/licenses/by-nc-sa/4.0/')
    def fetch(url,hosts,cap,sink,**kwargs):
        calls.append(url)
        if url.endswith('/licenses'):data={'results':[licensed,restricted]}
        elif '/v3/search?' in url:data={'results':[{'uid':'e'*32,'name':'2026 F1 outdated/inaccurate'}, {'uid':good,'name':'2026 F1 concept'}]}
        elif '/v3/models/' in url:
            uid=url.rsplit('/',1)[1]
            data={'uid':uid,'name':'2026 F1 concept','license':restricted if uid==bad else licensed,
                'user':{'username':'Fixture artist'},'viewerUrl':'https://sketchfab.com/3d-models/test-'+uid,'isDownloadable':True}
        else:data={'items':[]}
        sink.write(json.dumps(data).encode())
    monkeypatch.setattr(discovery,'research',lambda *a,**k:{'status':'OBSERVED','candidates':[{'provider':'sketchfab.com','url':'https://sketchfab.com/3d-models/test-'+bad}]})
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        result=discovery.discover(SimpleNamespace(base=tmp_path),journal,'fallback-fixture','2026 F1 class model',target_year=2026,
            client=MetadataClient(tmp_path,journal,'fallback-fixture',fetcher=fetch))
        assert len(result['qualified_rights'])==1
        asset,_=verify(tmp_path,journal,result['qualified_rights'][0]['acquisition_ref'])
        assert asset.candidate_id=='sketchfab:'+good and asset.license_spdx=='CC-BY-4.0'
        assert any(row.get('candidate')==bad for row in result['blocked_candidates'])
        assert calls.index('https://api.sketchfab.com/v3/models/'+bad)<next(i for i,url in enumerate(calls) if '/v3/search?' in url)
        assert not any(url.endswith('/'+'e'*32) for url in calls)
        assert any(row['reason']=='AUTHOR_MARKED_OUTDATED_OR_INACCURATE' for row in result['blocked_candidates'])
        from urllib.parse import urlsplit,parse_qs
        search_url=next(url for url in calls if '/v3/search?' in url)
        assert parse_qs(urlsplit(search_url).query)['q']==['2026 F1 model']
    finally:journal.close()


def test_general_discovery_stops_after_cancel_and_retains_actionable_blockers(tmp_path,monkeypatch):
    from jarvis.discovery.adapters import asset_discovery as discovery
    from jarvis.neural.journal import Journal
    from types import SimpleNamespace
    monkeypatch.setattr(discovery,'research',lambda *a,**k:{'status':'BLOCKED_BROWSER_RESEARCH','candidates':[]})
    stopped=[False];calls=[]
    class Client:
        def get(self,provider,url):calls.append(provider);stopped[0]=True;return 'fixture',{'results':[]}
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        with pytest.raises(discovery.ResearchCancelled):
            discovery.discover(SimpleNamespace(base=tmp_path),journal,'cancel-fixture','mechanical hinge model',client=Client(),cancelled=lambda:stopped[0])
        assert calls==['sketchfab']
        class Exhausted:
            def get(self,*a):raise ValueError('provider allowance exhausted: untrusted text never retained')
        result=discovery.discover(SimpleNamespace(base=tmp_path),journal,'quota-fixture','mechanical hinge model',client=Exhausted())
        assert len(result['blocked_candidates'])==2
        assert all(row['reason']=='PROJECT_METADATA_ALLOWANCE_EXHAUSTED' for row in result['blocked_candidates'])
        assert 'untrusted text' not in json.dumps(result)
    finally:journal.close()


def test_asset_subtask_reuses_existing_controller_and_fresh_session_checkpoint(tmp_path,monkeypatch):
    from jarvis.discovery import asset_pipeline as pipeline
    from jarvis.neural.journal import Journal
    from types import SimpleNamespace
    from jarvis.discovery.scenario_journal import StageJournal
    from jarvis.discovery.model.asset_pipeline import Workflow
    counts={'research':0,'transfer':0,'inspect':0};events=[]
    def research(*args,**kwargs):
        counts['research']+=1
        return {'query':'mechanical hinge model','target_year':None,'qualified_rights':[{'acquisition_ref':'rights-fixture'}]}
    monkeypatch.setattr(pipeline.asset_discovery,'discover',research)
    monkeypatch.setattr(pipeline.asset_rights,'verify',lambda *a:(SimpleNamespace(file_format='glb',maximum_bytes=500),{'download_url':'https://example.com/fixture.glb'}))
    def transfer(*args,**kwargs):counts['transfer']+=1;return 'download-fixture',{}
    monkeypatch.setattr(pipeline.asset_acquisition,'transfer',transfer)
    monkeypatch.setattr(pipeline.asset_acquisition,'verify',lambda *a:{'download':{'acquisition_ref':'rights-fixture'}})
    def inspect(*args,**kwargs):counts['inspect']+=1;return 'inspection-fixture',{}
    monkeypatch.setattr(pipeline.asset_inspection,'inspect_download',inspect)
    monkeypatch.setattr(pipeline.asset_inspection,'verify_inspection',lambda *a:{'receipt':{'download_ref':'download-fixture','part_count':1}})
    monkeypatch.setattr(pipeline.asset_inspection,'qualification',lambda *a:{'runtime_ready':True})
    monkeypatch.setattr(pipeline.asset_inspection,'worker_hash',lambda:'a'*64)
    from jarvis.discovery import geometry_preview
    monkeypatch.setattr(geometry_preview,'build',lambda *a,**k:{'relative_file':'fixture-preview.png','scope':'fixture, not live geometry'})
    actions=SimpleNamespace(base=tmp_path,report=lambda *a:events.append(a))
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        first=pipeline.run(actions,journal,'mechanical hinge model')
        assert first['status']=='ACQUIRED_GEOMETRY_ONLY' and not first['full_scenario_a_passed']
        episode=StageJournal(journal,workflow=Workflow()).episode(first['run_id'])
        assert len(episode)==5 and all(row['category']=='verified' for row in episode)
    finally:journal.close()
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        assert pipeline.run(actions,journal,'mechanical hinge model')==first
        assert counts=={'research':1,'transfer':1,'inspect':1}
    finally:journal.close()


def test_mesh_diagnostic_is_from_actual_vertices_and_never_overwrites_changed_output(tmp_path):
    from jarvis.discovery.geometry_preview import build
    from types import SimpleNamespace
    import hashlib
    folder=tmp_path/'imports';folder.mkdir()
    observed={'receipt':{'relative_file':'imports/inspection.json','sha256':'a'*64,'original_sha256':'b'*64},
        'inspection':{'units':'m','parts':[{'component_id':'triangle','bounds':[[0,0,0],[1,1,0]],
            'preview_vertices':[[0,0,0],[1,0,0],[0,1,0]],'preview_triangles':[[0,1,2]]}]}}
    asset=SimpleNamespace(creator='Analytic fixture',license_spdx='CC0-1.0',source_url='https://example.com/fixture')
    receipt=build(tmp_path,observed,asset);raw=(tmp_path/receipt['relative_file']).read_bytes()
    assert raw.startswith(b'\x89PNG\r\n\x1a\n') and hashlib.sha256(raw).hexdigest()==receipt['sha256']
    assert receipt['original_sha256']=='b'*64 and receipt['inspection_sha256']=='a'*64
    assert build(tmp_path,observed,asset)==receipt
    observed['inspection']['parts'][0]['preview_vertices'][2]=[.8,1,0]
    with pytest.raises(ValueError,match='diagnostic differs'):build(tmp_path,observed,asset)


def test_stage_controller_reconciles_uncertain_effect_without_replaying_it(tmp_path):
    from jarvis.discovery.scenario_journal import StageJournal
    from jarvis.discovery.model.asset_pipeline import Workflow,Target
    from jarvis.neural.journal import Journal
    counts={'effect':0,'observe':0}
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        controller=StageJournal(journal,workflow=Workflow());state=controller.open(Target(query='mechanical hinge model'))
        def effect():counts['effect']+=1;raise ValueError('injected lost reply')
        with pytest.raises(ValueError,match='lost reply'):
            controller.perform(state,'research','fixture-effect',{},effect,lambda output:None)
        state=controller.open(Target(query='mechanical hinge model'))
        def observe():counts['observe']+=1;return {'stage':'research','facts':{'readback':True},'files':{}}
        state,_=controller.perform(state,'research','fixture-effect',{},effect,lambda output:None,reconcile=observe)
        assert state.verified_stages==('research',) and counts=={'effect':1,'observe':1}
        assert controller.episode(state.run_id)[-1]['retry_reason']=='read-only reconciliation of uncertain effect'
    finally:journal.close()


def test_asset_rights_are_rederived_from_per_file_evidence_not_repository_flags(tmp_path):
    from jarvis.discovery.adapters.provider_metadata import MetadataClient
    from jarvis.discovery.adapters.asset_rights import issue,verify,named_year
    from jarvis.neural.journal import Journal
    import base64,hashlib
    model=b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n';revision='a'*40
    document=json.dumps({'version':1,'assets':[{'path':'F1_2025.obj','license':'CC0-1.0','creator':'Fixture artist',
        'title':'2025 F1 test mesh','year':2025,'identity_status':'author_declared_concept'}]}).encode()
    def blob(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    tree={'tree':[{'path':'F1_2025.obj','type':'blob','mode':'100644','sha':blob(model),'size':len(model)}]}
    rights={'type':'file','path':'ASSET_LICENSES.json','size':len(document),'sha':blob(document),
        'encoding':'base64','content':base64.b64encode(document).decode()}
    def fetch(url,hosts,cap,sink,**kwargs):sink.write(json.dumps(tree if '/git/trees/' in url else rights).encode())
    journal=Journal(tmp_path/'brain.sqlite3')
    try:
        client=MetadataClient(tmp_path,journal,'rights-fixture',fetcher=fetch)
        tree_ref,_=client.get('github','https://api.github.com/repos/artist/models/git/trees/'+revision)
        rights_ref,_=client.get('github','https://api.github.com/repos/artist/models/contents/ASSET_LICENSES.json?ref='+revision)
        proof={'rule':'github-asset-manifest-v1','owner':'artist','repo':'models','revision':revision,
            'path':'F1_2025.obj','tree_ref':tree_ref,'rights_ref':rights_ref}
        ref,availability=issue(tmp_path,journal,proof,target_year=2025)
        asset,_=verify(tmp_path,journal,ref)
        assert asset.license_spdx=='CC0-1.0' and availability['download_url'].endswith('/F1_2025.obj')
        with pytest.raises(ValueError,match='required object year'):issue(tmp_path,journal,proof,target_year=2026)
        changed=asset.model_dump(mode='json');changed['license_spdx']='MIT'
        with pytest.raises(ValueError,match='differs'):verify(tmp_path,journal,journal.put(changed,'Report'))
        with pytest.raises(ValueError,match='another asset'):issue(tmp_path,journal,{**proof,'rule':'github-reuse-sidecar-v1'})
        assert named_year('2026 F1 regulations copyright 2025') is None
        assert named_year('car_2025-11-06.obj') is None
        assert named_year('F1_2025.obj')==2025 and named_year('2025-2026 F1') is None
    finally:journal.close()
