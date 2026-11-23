"""Fault injection tests metadata commits, never an external sandbox effect."""
from pathlib import Path
import pytest
from jarvis.checkpoint_io import write_checkpoint


def test_destination_escape_is_rejected_before_any_write(tmp_path):
    owned=tmp_path/'owned';owned.mkdir()
    with pytest.raises(ValueError,match='escaped'):
        write_checkpoint(tmp_path/'outside.json','new',owned)
    assert not (tmp_path/'outside.json').exists() and not list(owned.iterdir())


def test_demonstration_resume_recovers_sharing_without_granting_consent(tmp_path,monkeypatch):
    from jarvis.demonstration import DemonstrationSession
    session=DemonstrationSession(tmp_path,lambda *a:None)
    replace=Path.replace;injected=[]
    def sharing(source,target):
        if Path(target)==session.path and not injected:
            injected.append(True);error=PermissionError('session sharing denial');error.winerror=32;raise error
        return replace(source,target)
    monkeypatch.setattr(Path,'replace',sharing)
    session._save()
    resumed=DemonstrationSession.resume(tmp_path,session.identifier,lambda *a:None)
    assert injected and resumed.state==session.state
    with pytest.raises(ValueError,match='consent'):resumed.start_hook()


def test_sharing_failure_retries_only_the_unchanged_metadata(tmp_path,monkeypatch):
    target=tmp_path/'state.json';target.write_text('old')
    replace=Path.replace;calls=[]
    def sharing(source,destination):
        calls.append(source.read_text())
        if len(calls)==1:
            error=PermissionError('sharing fixture');error.winerror=32;raise error
        return replace(source,destination)
    monkeypatch.setattr(Path,'replace',sharing)
    write_checkpoint(target,'new',tmp_path)
    assert calls==['new','new'] and target.read_text()=='new'


def test_changed_target_refuses_retry_and_preserves_pending_metadata(tmp_path,monkeypatch):
    target=tmp_path/'state.json';target.write_text('old');calls=[]
    def sharing(source,destination):
        calls.append(1);destination.write_text('other writer')
        error=PermissionError('sharing fixture');error.winerror=32;raise error
    monkeypatch.setattr(Path,'replace',sharing)
    with pytest.raises(PermissionError):write_checkpoint(target,'new',tmp_path)
    assert calls==[1] and target.read_text()=='other writer'
    assert [p.read_text() for p in tmp_path.glob('.jarvis-checkpoint-*')]==['new']


def test_permanent_denial_is_not_retried_or_discarded(tmp_path,monkeypatch):
    target=tmp_path/'state.json';calls=[]
    def denied(*args):calls.append(1);raise PermissionError('no Windows sharing code')
    monkeypatch.setattr(Path,'replace',denied)
    with pytest.raises(PermissionError):write_checkpoint(target,'new',tmp_path)
    assert calls==[1] and not target.exists()
    assert len(list(tmp_path.glob('.jarvis-checkpoint-*')))==1


def test_same_file_concurrent_writers_recover_without_false_foreign_change(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    replace=Path.replace;threads=set();guard=threading.Lock()
    def sharing(source,target):
        identity=threading.get_ident()
        with guard:
            first=identity not in threads
            threads.add(identity)
        if first:
            error=PermissionError('one sharing failure per writer');error.winerror=32;raise error
        return replace(source,target)
    monkeypatch.setattr(Path,'replace',sharing)
    target=tmp_path/'state.json'
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda i:write_checkpoint(target,str(i),tmp_path),range(100)))
    assert len(threads)==5 and target.read_text() in {str(i) for i in range(100)}


def test_deliberation_ledger_oracle_survives_one_sharing_denial(tmp_path,monkeypatch):
    from tests.test_deliberation_audit import test_catalog
    replace=Path.replace;injected=[]
    def sharing(source,target):
        if Path(target).name=='decisions.jsonl' and not injected:
            injected.append(True);error=PermissionError('ledger sharing denial');error.winerror=32;raise error
        return replace(source,target)
    monkeypatch.setattr(Path,'replace',sharing)
    test_catalog(17,tmp_path)
    assert injected


@pytest.mark.parametrize('filename',['Jarvis Memory.json','Jarvis Memory.md'])
def test_fact_store_original_concurrency_oracle_survives_sharing_denial(tmp_path,monkeypatch,filename):
    from unittest.mock import Mock
    from jarvis.memory_curator import MemoryCurator
    from tests.test_memory_audit import test_JRV_16_017_five_writers_twenty_rounds
    curator=MemoryCurator(tmp_path/'vault',model_chat=Mock(return_value={'facts':[]}))
    replace=Path.replace;injected=[]
    def sharing(source,target):
        if Path(target).name==filename and not injected:
            injected.append(True);error=PermissionError('fact sharing denial');error.winerror=32;raise error
        return replace(source,target)
    monkeypatch.setattr(Path,'replace',sharing)
    test_JRV_16_017_five_writers_twenty_rounds(curator)
    assert injected


def test_distinct_metadata_files_do_not_share_one_io_lock(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    barrier=threading.Barrier(2);replace=Path.replace
    def concurrent(source,target):
        barrier.wait(timeout=3)
        return replace(source,target)
    monkeypatch.setattr(Path,'replace',concurrent)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda i:write_checkpoint(tmp_path/f'{i}.json',str(i),tmp_path),range(2)))
    assert [p.read_text() for p in sorted(tmp_path.glob('*.json'))]==['0','1']


@pytest.mark.parametrize('name',['test_context_budget_and_no_automatic_dispatch',
                                'test_retention_shutdown_disable_and_invalid_options'])
def test_experience_operations_survive_one_sharing_denial(name,monkeypatch):
    import os
    import unittest
    from tests.test_experience_memory import ExperienceMemoryTests
    replace=os.replace;injected=[]
    def sharing(source,target):
        if Path(target).name=='Jarvis Experiences.json' and not injected:
            injected.append(True);error=PermissionError('controlled sharing denial');error.winerror=32;raise error
        return replace(source,target)
    monkeypatch.setattr(os,'replace',sharing)
    result=unittest.TestResult();ExperienceMemoryTests(name).run(result)
    assert injected and result.testsRun==1 and result.wasSuccessful(), 'experience fixture failed under one sharing denial'
