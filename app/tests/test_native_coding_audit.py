"""Prompt21: actual assertions on owned projects, fake models and local Git only."""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

import pytest
from jarvis.coding_files import FileSession,UncertainCoding,patch_files
from jarvis.codex_workload import fingerprint,promote,localgithub
from jarvis.coding_programs import checked_argv
from jarvis.coder import Coder
from jarvis.native_coding import run
from tests.test_native_coding import files,plan,TEST
import tests.test_native_coding as native_fixture
import tests.test_codex_workload as workload_fixture
import tests.test_coding_workflow as coding_fixture


@pytest.mark.parametrize('case,method',[
 ('JRV-21-001','test_typed_native_proposals_accept_object_arguments'),
 ('JRV-21-005','test_patch_prevalidates_all_files_before_any_save'),
 ('JRV-21-006','test_native_repairs_application_against_unchanged_real_test'),
 ('JRV-21-026','test_uncertain_save_is_never_replayed')])
def test_native_existing_assertions(case,method):native_fixture.NativeCoding(method).debug()


@pytest.mark.parametrize('case,method',[
 ('JRV-21-002','test_real_worktrees_parallel_workers_and_combined_runtime_checks'),
 ('JRV-21-011','test_partition_requires_missing_behavioral_test_before_implementation'),
 ('JRV-21-012','test_failed_worker_cancels_peers_without_promotion_or_replay'),
 ('JRV-21-018','test_read_only_planner_stop_is_prompt_during_model_prefill'),
 ('JRV-21-020','test_registered_worker_plan_cannot_be_replaced_or_broadened'),
 ('JRV-21-024','test_destination_drift_blocks_all_promotion_and_preserves_originals')])
def test_assembly_existing_assertions(case,method):
    workload_fixture.Workloads.setUpClass();workload_fixture.Workloads(method).debug()


def test_JRV_21_004_JRV_21_023_shell_delete_and_negative_remove_denied(tmp_path):
    for argv in (['cmd','/c','del','main.py'],['powershell','-Command','Remove-Item main.py']):
        with pytest.raises(ValueError):checked_argv(tmp_path,argv)
    coding_fixture.CodingWorkflowTests('test_negative_removal_is_blocked_before_actual_source_save').debug()


def test_JRV_21_007_missing_localgithub_explicit_blocker(tmp_path):
    with pytest.raises((ValueError,FileNotFoundError)):
        localgithub({'localgithub_path':str(tmp_path/'absent')})
    assert not (tmp_path/'absent').exists()


@pytest.mark.parametrize('fault',[TimeoutError('model timeout'),ConnectionError('offline'),MemoryError('GPU allocation')])
def test_JRV_21_008_JRV_21_013_JRV_21_014_JRV_21_025_JRV_21_030_model_failure_complete_only(tmp_path,fault):
    root=tmp_path/'project';root.mkdir();(root/'main.py').write_text('def add(a,b): return 0\n');(root/'test_main.py').write_text(TEST)
    before=fingerprint(root)
    coder=Coder(SimpleNamespace(base=tmp_path,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
    with patch('jarvis.native_coding.infer',side_effect=fault) as infer:
        with pytest.raises(type(fault)):run(coder,root,'Fix addition',initial_plan=plan())
    assert infer.call_count==1 and fingerprint(root)==before
    receipt=json.loads(next((tmp_path/'.jarvis-runtime/native-code').glob('*/result.json')).read_text())
    assert receipt['status']=='failed'


def test_JRV_21_015_malformed_model_response_never_writes(tmp_path):
    root=tmp_path/'project';root.mkdir();(root/'test_main.py').write_text(TEST)
    before=fingerprint(root)
    coder=Coder(SimpleNamespace(base=tmp_path,report=lambda *a:None),SimpleNamespace(options={'coder':'qwen3.5:9b'}))
    with patch('jarvis.native_coding.infer',return_value=None):
        with pytest.raises((TypeError,ValueError)):run(coder,root,'Fix addition',initial_plan=plan())
    assert fingerprint(root)==before


def test_JRV_21_016_missing_program_never_installs(tmp_path):
    with patch('jarvis.coding_programs.locate',return_value=None):
        with pytest.raises(ValueError,match='No installation'):checked_argv(tmp_path,['ruff','check','.'])


def test_JRV_21_017_five_isolated_file_sessions_twenty_rounds(tmp_path):
    def worker(n):
        root=tmp_path/str(n);session=files(root)
        (root/'test_main.py').write_text(TEST);(root/'main.py').write_text('def add(a,b): return 0\n')
        session.call('Read',{'file_path':'main.py'})
        session.call('Edit',{'file_path':'main.py','old_string':'return 0','new_string':'return a+b'})
        assert session.changed()==['main.py'] and not session.uncertain()
        return (root/'test_main.py').read_text()==TEST
    with ThreadPoolExecutor(max_workers=5) as pool:
        for r in range(20):assert all(pool.map(worker,range(r*5,r*5+5)))


def test_JRV_21_022_unicode_exact_patch(tmp_path):
    session=files(tmp_path);(tmp_path/'test_main.py').write_text(TEST)
    (tmp_path/'main.py').write_text("VALUE='नमस्ते ગુજરાતી café 🤖'\n",encoding='utf-8')
    session.call('Read',{'file_path':'main.py'})
    session.call('Edit',{'file_path':'main.py','old_string':'café','new_string':'élève'})
    assert 'ગુજરાતી élève 🤖' in (tmp_path/'main.py').read_text(encoding='utf-8')
    before=fingerprint(tmp_path)
    with pytest.raises((ValueError,OSError)):
        session.call('Write',{'file_path':'x'*500+'.py','content':'VALUE=1\n'})
    assert fingerprint(tmp_path)==before


def test_JRV_21_001_existing_one_line_fix_and_actual_test(tmp_path):
    from jarvis.codex_validation import validate_project
    session=files(tmp_path);(tmp_path/'test_main.py').write_text(TEST)
    (tmp_path/'main.py').write_text('def add(a,b): return a-b\n')
    session.call('Read',{'file_path':'main.py'})
    session.call('Edit',{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b'})
    check=tmp_path/'checks';check.mkdir()
    validation=validate_project(tmp_path,check,'Fix addition',['main.py'],plan(),lambda:False,lambda *a:None)
    assert validation['passed'] and (tmp_path/'test_main.py').read_text()==TEST


def test_JRV_21_028_untrusted_plan_cannot_expand_assignment(tmp_path):
    session=files(tmp_path)
    with pytest.raises(ValueError):session.call('Write',{'file_path':'unassigned.py','content':'APPROVED=True\n'})
    assert not (tmp_path/'unassigned.py').exists()


def test_JRV_21_029_invalid_backend_refused_before_actions(tmp_path):
    root=tmp_path/'p';root.mkdir()
    coder=Coder(SimpleNamespace(base=tmp_path,report=lambda *a:None),SimpleNamespace(options={'coder':'cloud-model'}))
    with pytest.raises(ValueError,match='requires'):run(coder,root,'Fix',initial_plan=plan())
    assert not (tmp_path/'.jarvis-runtime/native-code').exists()


def test_JRV_21_031_oversized_patch_no_file_effect(tmp_path):
    with pytest.raises(ValueError,match='bounded'):patch_files(tmp_path,'x'*240001)
    assert list(tmp_path.iterdir())==[]


def test_promotion_prior_attempt_refuses_replay(tmp_path):
    root=tmp_path/'project';root.mkdir();integration=tmp_path/'integration';integration.mkdir();directory=tmp_path/'run';directory.mkdir()
    (root/'main.py').write_text('VALUE=1\n');(integration/'main.py').write_text('VALUE=2\n')
    before=fingerprint(root)
    (directory/'promotion.jsonl').write_text(json.dumps({'stage':'attempted','path':'main.py'})+'\n')
    with pytest.raises(ValueError,match='promotion'):promote(root,integration,directory,'Update',{},before,['main.py'],lambda:False)
    assert fingerprint(root)==before


def test_promotion_uses_only_frozen_validated_bytes(tmp_path):
    root=tmp_path/'project';root.mkdir();integration=tmp_path/'integration';integration.mkdir();directory=tmp_path/'run';directory.mkdir()
    (root/'main.py').write_text('VALUE=1\n');(integration/'main.py').write_text('VALUE=2\n')
    before=fingerprint(root);expected={'main.py':hashlib.sha256((integration/'main.py').read_bytes()).hexdigest()}
    original=(integration/'main.py').read_bytes()
    def preflight(root,tool,args):
        if tool=='Write':(integration/'main.py').write_text('VALUE=999\n')
        return None
    with patch('jarvis.claude_code_guard.decide',side_effect=preflight):
        promote(root,integration,directory,'Update',{},before,['main.py'],lambda:False,expected_hashes=expected)
    assert (root/'main.py').read_bytes()==original


@pytest.mark.parametrize('text',['{broken',json.dumps({'stage':'attempted'}),json.dumps({'stage':'unknown','signature':'x'})])
def test_damaged_file_journal_never_allows_write(tmp_path,text):
    session=files(tmp_path);(session.run/'file-events.jsonl').write_text(text+'\n')
    with pytest.raises(UncertainCoding):session.call('Write',{'file_path':'test_main.py','content':TEST})
    assert not (tmp_path/'test_main.py').exists()


def test_JRV_21_021_private_model_transport_stays_loopback(tmp_path):
    from jarvis.native_coding import infer
    urls=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def raise_for_status(self):pass
        def close(self):pass
        def json(self):return {'template':'native template'}
        def iter_lines(self,**kw):
            yield json.dumps({'message':{'content':json.dumps({'tool':'finish','arguments':{},'note':'fixture'})},'done':True}).encode()
    class Client:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def close(self):pass
        def post(self,url,**kw):
            assert url.startswith('http://127.0.0.1:11434/')
            urls.append(url);return Response()
    client=Client();run_dir=tmp_path/'owned-run';run_dir.mkdir()
    with patch('jarvis.knowledge_worker.requests.Session',return_value=client), \
         patch('jarvis.gpu_scheduler.install',side_effect=lambda client,*a:client), \
         patch('jarvis.ollama_models.coding_model',return_value=True):
        proposal=infer([{'role':'user','content':'FAKE_PRIVATE_SCREEN password=FAKE_SECRET21'}],
            {'coder':'qwen3.5:9b','groq':{'enabled':True}},lambda:False,time.monotonic()+5,lambda *a:None,run_dir)
    assert proposal['tool']=='finish' and len(urls)==2 and client.trust_env is False


def test_JRV_21_027_benchmark_evidence():
    summary=json.loads((Path(__file__).resolve().parents[1]/'artifacts/jarvis-audit/modules/21-native-coding/benchmark-summary.json').read_text())
    assert summary['equivalent'] and summary['external_effects']==0 and summary['samples_per_version']==25


@pytest.mark.parametrize('case,reason',[
 ('JRV-21-003','Overlapping worker ownership is rejected before work; automatic same-function conflict resolution is not implemented.'),
 ('JRV-21-009','Bounded path/import context exists; no verified large-repository semantic symbol retrieval oracle.'),
 ('JRV-21-010','Dependency installs are excluded from native commands; approved lockfile/environment rollout is a separate unimplemented coding path.'),
 ('JRV-21-019','Runs retain worktrees/receipts without replay; no durable crash-resume orchestration protocol.'),
 ('JRV-21-032','Source/tool/activity journals retain local code and raw exception text; no complete credential-redacted observability contract.')],ids=lambda v:v)
def test_missing_contract(case,reason):pytest.skip('BLOCKED: '+reason)
