"""Prompt08 fault boundaries, using isolated registries and fake transports."""
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests
from jarvis import gpu_scheduler as gpu


def test_unchanged_registry_poll_does_not_write(tmp_path):
    registry=gpu.Registry(tmp_path)
    with registry.state():pass
    with patch('jarvis.gpu_scheduler.replace_state',wraps=gpu.replace_state) as replace:
        for _ in range(5):
            with registry.state():pass
    replace.assert_not_called()


def test_driver_probe_exception_does_not_leak_admission(tmp_path):
    registry=gpu.Registry(tmp_path)
    with patch('requests.sessions.Session.post') as post,patch('jarvis.gpu_scheduler.Registry',return_value=registry),\
         patch('jarvis.gpu_scheduler.configured',return_value=gpu.settings({'enabled':True})),\
         patch('jarvis.gpu_scheduler.memory',side_effect=RuntimeError('driver probe failed')):
        client=gpu.install(requests.Session())
        try:
            with pytest.raises(RuntimeError):client.post('http://127.0.0.1:11434/api/chat',json={'model':'qwen3.5:9b'})
            assert json.loads(registry.path.read_text())['active'] is None
            post.assert_not_called()
        finally:client.close()


@pytest.mark.parametrize('state',[
    {'active':None,'pending':[{'priority':10000}]},
    {'active':{'pid':-1},'pending':[]},
    {'active':None,'pending':[],'resident':{'expires_at':'invalid'}},
])
def test_malformed_lease_state_is_rejected_before_liveness_or_write(tmp_path,state):
    registry=gpu.Registry(tmp_path,live=lambda _:True)
    text=json.dumps(state);registry.path.write_text(text)
    with pytest.raises(ValueError):
        with registry.state():pass
    assert registry.path.read_text()==text


def test_oversized_lease_state_is_rejected(tmp_path):
    registry=gpu.Registry(tmp_path)
    text=json.dumps({'active':None,'pending':[],'payload':'x'*200001});registry.path.write_text(text)
    with pytest.raises(ValueError):
        with registry.state():pass
    assert registry.path.read_text()==text


def test_unknown_resource_reading_defers_learning():
    from jarvis.self_evolution import SelfEvolution
    engine=SelfEvolution.__new__(SelfEvolution)
    engine.options={'min_available_mb':2048,'max_cpu_percent':85}
    with patch('psutil.virtual_memory',side_effect=OSError('no reading')):
        assert engine._resources_ok() is False


def test_low_ram_does_not_select_an_unfittable_fallback():
    from jarvis.repo_abilities import AbilityForge as Forge
    forge=Forge.__new__(Forge)
    forge.model_chat=None;forge.model='qwen3-coder:30b';forge.fallback_model='qwen3.5:9b';forge.memory_margin_gb=2
    with patch('psutil.virtual_memory',return_value=SimpleNamespace(available=512*1024**2)),\
         patch('jarvis.repo_abilities.requests.get') as get:
        get.return_value.json.return_value={'models':[{'name':forge.model,'size':18*1024**3},
                                                    {'name':forge.fallback_model,'size':7*1024**3}]}
        with pytest.raises(ValueError):forge.pick_model()


def test_twenty_percent_estimate_error_fits_even_with_small_configured_reserve():
    policy=gpu.settings({'enabled':True,'speech_reserve_mb':1024,'reserve_mb':128})
    hardware={'total_mb':4096,'used_mb':0}
    layers=gpu.allocation('qwen3.5:9b',32768,policy,hardware)
    estimate=600+145*layers+.016*32768
    assert estimate*1.2+policy['speech_reserve_mb']<=4096


def run_existing(method):
    from tests.test_gpu_scheduler import GPUSchedulerTests
    GPUSchedulerTests(method).debug()


EXISTING={
    4:'test_priority_is_shared_across_actual_processes',
    5:'test_stream_retains_slot_until_close_then_releases_once',
    8:'test_transport_failure_releases_without_retry',
    9:'test_cancelled_waiter_leaves_active_owner_untouched',
    13:'test_transport_failure_releases_without_retry',
    14:'test_queue_deadline_does_not_dispatch_or_clear_active_work',
    16:'test_default_idle_helper_never_takes_foreground_slot',
    18:'test_native_transport_cancellation_prevents_inference',
    19:'test_actual_crashed_owner_is_reaped_without_replaying_work',
    24:'test_changed_cache_identity_never_unloads_the_shared_model',
    25:'test_codex_refuses_low_vram_before_any_inference',
    30:'test_response_close_failure_still_releases_slot',
}


@pytest.mark.parametrize('number',range(1,33),ids=lambda n:f'JRV-08-{n:03d}')
def test_catalog(number,tmp_path):
    if number in (2,12):
        if number==2:
            from tests.test_phase2_gpu_models_voice_ui import test_native_fault_releases_shared_slot_and_queued_stop_cancels
            test_native_fault_releases_shared_slot_and_queued_stop_cancels(tmp_path)
            return
        pytest.skip('BLOCKED: forcible interruption of stuck native CUDA kernels requires a separate owned-process live fault test; cooperative shared leases are covered by Phase 2 fixtures.')
    if number in EXISTING:
        run_existing(EXISTING[number]);return
    if number in (1,10):
        root=Path(__file__).resolve().parents[1]/'artifacts/jarvis-audit/modules/08-gpu-scheduler'
        cold=json.loads((root/'native-cold-observation.json').read_text())
        warm=json.loads((root/'native-local.json').read_text())
        assert cold['status']==warm['status']=='PASS' and cold['initial_gpu_cold']
        assert cold['prior_resident_names']==[] and cold['samples'][0]['metrics']['load_duration']>0
        assert len(warm['samples'])==3 and all(s['ttft_seconds']>0 for s in warm['samples'])
        assert 0<max(cold['sampled_peak_gpu_used_mb'],warm['sampled_peak_gpu_used_mb'])<=4096
        assert warm['lease_readback']=={'active':None,'pending':0}
    elif number==3:
        test_low_ram_does_not_select_an_unfittable_fallback()
        assert gpu.allocation('qwen3-coder:30b',16384,gpu.settings(),{'total_mb':4096,'used_mb':0})==0
    elif number==6:
        test_twenty_percent_estimate_error_fits_even_with_small_configured_reserve()
        for context in (4096,8192,16384,32768,65536):
            policy=gpu.settings();layers=gpu.allocation('qwen3.5:9b',context,policy,{'total_mb':4096,'used_mb':1041})
            if layers:assert (600+145*layers+.016*context)*1.2+1041<=4096
    elif number==7:
        from jarvis.self_evolution import SelfEvolution
        engine=SelfEvolution.__new__(SelfEvolution);engine.options={'min_available_mb':3072,'max_cpu_percent':85}
        with patch('psutil.virtual_memory',return_value=SimpleNamespace(available=512*1024**2)):
            assert engine._resources_ok() is False
        test_unknown_resource_reading_defers_learning()
    elif number==11:
        with patch('jarvis.gpu_scheduler.subprocess.run',side_effect=FileNotFoundError()):assert gpu.memory() is None
        assert gpu.allocation('qwen3.5:9b',4096,gpu.settings(),None)==0
    elif number==15:
        test_malformed_lease_state_is_rejected_before_liveness_or_write(tmp_path,{'active':{'pid':-1},'pending':[]})
    elif number==17:
        registry=gpu.Registry(tmp_path);lock=threading.Lock();active=[0];peak=[0]
        def turn(index):
            lease=gpu.Lease('question','fixture',gpu.settings({'wait_seconds':5}),registry)
            try:
                assert lease.acquire()
                with lock:active[0]+=1;peak[0]=max(peak[0],active[0])
                time.sleep(.001)
                with lock:active[0]-=1
            finally:lease.close()
        with ThreadPoolExecutor(max_workers=5) as pool:
            for _ in range(20):list(pool.map(turn,range(5)))
        assert peak[0]==1 and active[0]==0
        state=json.loads(registry.path.read_text());assert state['active'] is None and state['pending']==[]
    elif number in (20,28):
        lease=gpu.Lease('background','fixture',gpu.settings(),gpu.Registry(tmp_path))
        forged={**lease.row,'priority':10000,'approval':True}
        test_malformed_lease_state_is_rejected_before_liveness_or_write(tmp_path,{'active':None,'pending':[forged]})
    elif number==21:
        with pytest.raises(ValueError):gpu.Lease('planner','gsk_'+'a'*36,gpu.settings(),gpu.Registry(tmp_path))
        registry=gpu.Registry(tmp_path)
        registry.event(stage='dispatch',role='planner',model='fixture',prompt='PRIVATE_SENTINEL',num_gpu='PRIVATE_SENTINEL')
        assert 'PRIVATE_SENTINEL' not in (tmp_path/'events.jsonl').read_text()
        assert not registry.path.exists()
    elif number==22:
        text='हिन्दी ગુજરાતી français 😀 '+('x'*500)
        with pytest.raises(ValueError):gpu.Lease('planner',text,gpu.settings(),gpu.Registry(tmp_path))
        assert not (tmp_path/'state.json').exists()
    elif number==23:
        cancelled=gpu.Lease('planner','fixture',gpu.settings(),gpu.Registry(tmp_path),cancelled=lambda:True)
        with pytest.raises(ValueError,match='cancelled'):cancelled.acquire()
        assert json.loads((tmp_path/'state.json').read_text())['active'] is None
    elif number==26:
        lease=gpu.Lease('planner','fixture',gpu.settings(),gpu.Registry(tmp_path))
        try:
            assert lease.acquire()
            with pytest.raises(ValueError,match='already admitted'):lease.acquire()
            assert json.loads((tmp_path/'state.json').read_text())['active']['token']==lease.row['token']
        finally:lease.close()
        assert json.loads((tmp_path/'state.json').read_text())['active'] is None
    elif number==27:
        import csv
        with (Path(__file__).resolve().parents[1]/'artifacts/jarvis-audit/modules/08-gpu-scheduler/benchmarks.csv').open() as file:rows=list(csv.DictReader(file))
        for version in ('before','after'):
            assert sum(r['version']==version and r['mode']=='cold_read' for r in rows)==5
            assert sum(r['version']==version and r['mode']=='warm_read' for r in rows)==20
        assert sum(int(r['atomic_promotions']) for r in rows if r['version']=='after')==0
    elif number==29:
        with pytest.raises(ValueError):gpu.settings({'unknown':'forged'})
        with pytest.raises(ValueError):gpu.Lease('invented','fixture',gpu.settings(),gpu.Registry(tmp_path))
    elif number==31:
        test_oversized_lease_state_is_rejected(tmp_path)
    elif number==32:
        lease=gpu.Lease('planner','fixture',gpu.settings(),gpu.Registry(tmp_path))
        try:assert lease.acquire()
        finally:lease.close()
        rows=[json.loads(s) for s in (tmp_path/'events.jsonl').read_text().splitlines()]
        assert rows[0]['trace_id']==lease.row['token'] and rows[0]['stage']=='admitted'
        test_driver_probe_exception_does_not_leak_admission(tmp_path/'driver')
    else:pytest.fail(f'unmapped {number}')
