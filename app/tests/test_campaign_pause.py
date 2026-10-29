"""Real persistence and guarded entry points; no live models or application trials."""
from dataclasses import asdict
import json
import queue
import threading
from types import SimpleNamespace
from unittest.mock import Mock,patch

import pytest
from jarvis import campaign_pause
from jarvis.commands import Command
from jarvis.task_store import TaskStore
from jarvis.task_scheduler import ScheduledQueue


def record(base,protected):
    path=campaign_pause.marker(base);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'schema_version':1,'status':'PAUSED_BY_USER','checkpoint':'fixture',
        'protected_roots':[str(protected.resolve())],'logical_task_ids':['a'*32]}),encoding='utf-8')
    return path


def test_guard_blocks_campaign_before_model_write_or_engine_and_allows_new_features(tmp_path,monkeypatch):
    monkeypatch.setattr(campaign_pause,'BASE',tmp_path)
    protected=tmp_path/'saved-apps';protected.mkdir();source=protected/'main.py';source.write_text('retained = True\n')
    record(tmp_path,protected)
    normal=tmp_path/'new-feature';normal.mkdir()
    from jarvis.coder import Coder
    from jarvis.native_coding import run,infer
    from jarvis.coding_cloud_routes import CodingRoutes
    coder=Coder(SimpleNamespace(base=tmp_path),SimpleNamespace(options={}))
    with patch('jarvis.engineering_judgment.engine_for',side_effect=AssertionError('No engine before guard')):
        with pytest.raises(campaign_pause.CampaignPaused):coder.run(protected,'old repair')
    with pytest.raises(campaign_pause.CampaignPaused):run(coder,protected,'old repair')
    with pytest.raises(campaign_pause.CampaignPaused):infer([],{},lambda:False,0,lambda *a:None,protected/'run')
    route=CodingRoutes.__new__(CodingRoutes)
    with pytest.raises(campaign_pause.CampaignPaused):route.complete([],{},
        {'native_cloud_task_id':'a'*32},normal,lambda:False,0)
    with patch('jarvis.engineering_judgment.engine_for',return_value=None),patch.object(coder,'_dispatch',return_value='normal feature accepted'):
        assert coder.run(normal,'new independent feature')=='normal feature accepted'
    assert source.read_text()=='retained = True\n'


def test_pause_persists_over_restart_dependency_completion_and_resume_queue(tmp_path):
    path=tmp_path/'campaign.sqlite3';store=TaskStore(path)
    observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True,'battery_low':False}
    scheduler=ScheduledQueue(store,observe=observe)
    parent=scheduler.put_nowait((0,Command('jarvis_status','parent'),threading.Event()))
    child=scheduler.put_nowait((0,Command('jarvis_status','child'),threading.Event()),overrides={'dependencies':[parent]})
    dependencies=store.get(child)['spec']['dependencies']
    store.setting('autonomous_repair_pause',{'status':'PAUSED_BY_USER','checkpoint':'fixture'})
    scheduler.control('resume_queue')
    with pytest.raises(queue.Empty):scheduler.get(timeout=0,lane='background')
    store.transition(parent,'RUNNING');store.transition(parent,'VERIFYING');store.transition(parent,'COMPLETED')
    scheduler.graph.publish(parent);scheduler.close();store.db.close()
    store=TaskStore(path);scheduler=ScheduledQueue(store,observe=observe);scheduler.restore(1)
    try:
        assert campaign_pause.queue_paused(store)
        assert store.get(child)['spec']['dependencies']==dependencies
        with pytest.raises(queue.Empty):scheduler.get(timeout=0,lane='background')
        other=TaskStore(tmp_path/'normal.sqlite3');normal=ScheduledQueue(other,observe=observe)
        try:
            normal.put_nowait((0,Command('jarvis_status','ordinary command'),threading.Event()))
            assert normal.get(timeout=0,lane='background')[1].value=='ordinary command'
            normal.outcome('COMPLETED','mocked ordinary command');normal.task_done()
        finally:normal.close();other.db.close()
    finally:scheduler.close();store.db.close()


def test_paused_ingress_never_classifies_restored_received_tasks(tmp_path):
    from jarvis.task_ingress import TaskIngress
    store=TaskStore(tmp_path/'inbox.sqlite3')
    task,_=store.admit(asdict(Command('task','old campaign work')))
    store.setting('autonomous_repair_pause',{'status':'PAUSED_BY_USER'})
    ingress=TaskIngress.__new__(TaskIngress);ingress.store=store;ingress.closed=threading.Event()
    ingress.buffer=Mock();ingress.buffer.get.side_effect=AssertionError('Paused inbox must not classify')
    thread=threading.Thread(target=ingress._run);thread.start()
    ingress.closed.wait(.04);ingress.closed.set();thread.join(1)
    try:
        assert not thread.is_alive();ingress.buffer.get.assert_not_called()
        assert store.get(task)['state']=='RECEIVED'
    finally:store.db.close()


def test_pause_metadata_corruption_refuses_execution_without_rewriting_checkpoint(tmp_path):
    path=record(tmp_path,tmp_path/'protected');path.write_text('{broken',encoding='utf-8')
    with pytest.raises(campaign_pause.CampaignPaused):campaign_pause.assert_allowed(whole_campaign=True,base=tmp_path)
    assert path.read_text()=='{broken'


def test_live_campaign_entry_refuses_before_source_intake_or_directory_creation(tmp_path,monkeypatch):
    from scripts.verification import verify_autonomous_repair
    monkeypatch.setattr(campaign_pause,'BASE',tmp_path)
    record(tmp_path,tmp_path/'protected')
    monkeypatch.setattr('sys.argv',['verify_autonomous_repair.py','--case','2'])
    with patch.object(verify_autonomous_repair,'source_manifest',side_effect=AssertionError('Guard must run before intake')):
        with pytest.raises(campaign_pause.CampaignPaused):verify_autonomous_repair.main()
    assert not (tmp_path/'.jarvis-runtime/autonomous-repair/projects').exists()


def test_checkpoint_readback_detects_archive_damage_and_later_upgrade_without_restoring(tmp_path):
    import hashlib,zipfile
    from jarvis.workload_state import save_checkpoint
    checkpoint=tmp_path/'checkpoint';checkpoint.mkdir();base=tmp_path/'app';base.mkdir()
    source=base/'interface.py';source.write_bytes(b'original interface\n')
    bundle=checkpoint/'source.zip'
    with zipfile.ZipFile(bundle,'w') as archive:archive.writestr('interface.py',source.read_bytes())
    manifest=checkpoint/'manifest.json';manifest.write_text(json.dumps({'files':[
        {'path':'interface.py','sha256':campaign_pause.fingerprint(source)}]}))
    save_checkpoint(checkpoint,{'status':'PAUSED_BY_USER','pause_checkpoint_schema':1,
        'archives':[{'archive':bundle.name,'manifest':manifest.name,'entries':1,
            'sha256':campaign_pause.fingerprint(bundle),'manifest_sha256':campaign_pause.fingerprint(manifest)}],
        'critical_files':{'interface.py':campaign_pause.fingerprint(source)},'frozen_files':[]})
    assert campaign_pause.verify_checkpoint(checkpoint,compare_current=True,base=base)['status']=='PASS'
    source.write_bytes(b'later feature upgrade\n')
    result=campaign_pause.verify_checkpoint(checkpoint,compare_current=True,base=base)
    assert result['status']=='REVIEW_REQUIRED' and result['restored_files']==0
    assert source.read_bytes()==b'later feature upgrade\n'
    with bundle.open('ab') as stream:stream.write(b'damaged archive')
    with pytest.raises(ValueError,match='fingerprint mismatch'):campaign_pause.verify_checkpoint(checkpoint)
