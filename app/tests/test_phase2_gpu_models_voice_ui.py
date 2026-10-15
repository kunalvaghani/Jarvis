"""Phase 2 contracts and stress fixtures. Live evidence has a separate opt-in gate.

Run from app: python -m pytest tests/test_phase2_gpu_models_voice_ui.py
JARVIS_PHASE2_EVIDENCE selects the live runner's JSON, never fabricated GPU usage.
"""
import collections
import json
import os
from pathlib import Path
import queue
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
import zipfile

import numpy as np
import pytest
import requests

from jarvis import gpu_scheduler as gpu
from jarvis.pcm_ring import PCMBuffer, CaptureQueue
from jarvis.push_to_write import PushToWrite, VK_LCONTROL, VK_LMENU
from jarvis.speech_normalizer import normalize, opening_clause
from jarvis.ui_events import UIEventBuffer


def wait_for(predicate, seconds=2):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        time.sleep(.002)
    assert predicate(), 'bounded fixture wait expired'


def test_priority_torture_between_turns_and_cleanup_cpu_fallback(tmp_path):
    registry = gpu.Registry(tmp_path)
    policy = gpu.settings({'enabled': True, 'wait_seconds': 5})
    owner = gpu.Lease('question', 'qwen3.5:9b', policy, registry)
    owner.acquire()
    order, errors = [], []
    def worker(role):
        lease = gpu.Lease(role, 'qwen3.5:9b', policy, registry)
        try:
            lease.acquire()
            order.append(role)
        except Exception as error:
            errors.append(type(error).__name__)
        finally:lease.close()
    threads = [threading.Thread(target=worker,args=(role,)) for role in ('question','coding','planner')]
    try:
        for thread in threads:thread.start()
        wait_for(lambda: gpu.status(tmp_path).get('pending') == 3)
        helper = gpu.Lease('cleanup','qwen2.5:0.5b',policy,registry)
        assert helper.acquire() is False
        # Running turns finish; only queued admission is reordered.
        assert order == []
    finally:
        owner.close()
        for thread in threads:thread.join(6)
    assert not errors and order == ['planner','coding','question']
    assert all(not thread.is_alive() for thread in threads)
    assert gpu.status(tmp_path)['status'] == 'idle'


@pytest.mark.parametrize('used',[0,1024,2048,3000,3849,4096])
@pytest.mark.parametrize('context',[1024,4096,16384,32768])
def test_estimated_allocation_protects_voice_reserve_and_3850_ceiling(used,context):
    policy=gpu.settings({'enabled':True,'speech_reserve_mb':2048})
    layers=gpu.allocation('qwen3.5:9b',context,policy,{'total_mb':4096,'used_mb':used})
    if layers:
        assert 600+145*layers+.016*context+max(used,2048)+policy['reserve_mb'] <= 3850
    else:
        assert layers == 0


def test_owned_server_environment_does_not_mutate_parent():
    parent={'OLLAMA_MODELS':'fixture-cache','OTHER':'keep'}
    result=gpu.runtime_environment(parent)
    assert parent == {'OLLAMA_MODELS':'fixture-cache','OTHER':'keep'}
    assert result['OLLAMA_FLASH_ATTENTION']=='1' and result['OLLAMA_KV_CACHE_TYPE']=='q8_0'
    assert result['OLLAMA_NUM_PARALLEL']=='1' and result['OLLAMA_MAX_LOADED_MODELS']=='2'
    assert result['OLLAMA_MODELS']=='fixture-cache'


@pytest.mark.parametrize('model,expected',[('qwen3.5:9b',4096),('qwen3.5:0.8b',1024),('qwen2.5:0.5b',1024)])
def test_request_context_caps_include_explicit_oversized_requests(model,expected):
    assert gpu.request_context(model,{'num_ctx':32768},gpu.settings())==expected
    assert gpu.request_context(model,{'num_ctx':512},gpu.settings())==512


def test_native_load_pressure_refuses_before_constructor_and_releases(tmp_path):
    registry=gpu.Registry(tmp_path)
    with patch.object(gpu,'configured',return_value=gpu.settings({'enabled':True})),patch.object(gpu,'Registry',return_value=registry),patch.object(gpu,'memory',return_value={'total_mb':4096,'used_mb':2500}):
        with pytest.raises(MemoryError):
            with gpu.native_turn('speech','native/f5',load_mb=2048):
                pytest.fail('unsafe load admitted')
    assert gpu.status(tmp_path)['status']=='idle'


@pytest.mark.parametrize('identity_matches',[True,False])
def test_native_load_evicts_only_identified_owned_cache(tmp_path,identity_matches):
    registry=gpu.Registry(tmp_path)
    resident={'model':'qwen3.5:9b','digest':'owned','context':4096,'size_vram':1024*1048576,'num_gpu':3,'expires_at':time.time()+60}
    with registry.state() as state:state['resident']=resident
    def response(data):
        row=requests.Response();row.status_code=200;row._content=json.dumps(data).encode();row._content_consumed=True;return row
    observed={'name':resident['model'],'digest':'owned' if identity_matches else 'another-client',
              'context_length':4096,'size_vram':resident['size_vram']}
    with patch.object(gpu,'configured',return_value=gpu.settings({'enabled':True})),patch.object(gpu,'Registry',return_value=registry),patch.object(gpu,'memory',side_effect=[{'total_mb':4096,'used_mb':3000},{'total_mb':4096,'used_mb':1000}]),patch('requests.sessions.Session.get',return_value=response({'models':[observed]})),patch('requests.sessions.Session.post',return_value=response({})) as unload:
        if identity_matches:
            with gpu.native_turn('speech','native/f5',load_mb=2048):pass
            assert unload.call_count==1 and unload.call_args.kwargs['json']['keep_alive']==0
        else:
            with pytest.raises(MemoryError):
                with gpu.native_turn('speech','native/f5',load_mb=2048):pass
            unload.assert_not_called()
    assert gpu.status(tmp_path)['status']=='idle'


def test_lazy_whisper_decode_consumes_segments_under_native_lease():
    from contextlib import contextmanager
    from jarvis.whisper_backend import CoordinatedWhisper
    held=[]
    @contextmanager
    def gate(*args,**kwargs):
        held.append(True)
        try:yield
        finally:held.pop()
    def segments():
        assert held
        yield 'decoded'
    wrapped=SimpleNamespace(transcribe=lambda *a,**k:(segments(), 'metadata'))
    with patch.object(gpu,'native_turn',gate):
        result,info=CoordinatedWhisper(wrapped).transcribe(np.zeros(1600,np.float32))
    assert list(result)==['decoded'] and info=='metadata' and held==[]


def test_native_fault_releases_shared_slot_and_queued_stop_cancels(tmp_path):
    registry=gpu.Registry(tmp_path);policy=gpu.settings({'enabled':True,'wait_seconds':2})
    with patch.object(gpu,'configured',return_value=policy),patch.object(gpu,'Registry',return_value=registry):
        with pytest.raises(RuntimeError):
            with gpu.native_turn('speech','native/f5'):
                raise RuntimeError('Synthetic native synthesis failure')
        assert gpu.status(tmp_path)['status']=='idle'
        owner=gpu.Lease('planner','qwen3.5:9b',policy,registry);owner.acquire()
        stopped=threading.Event();stopped.set()
        try:
            with pytest.raises(ValueError,match='cancelled'):
                with gpu.native_turn('recognition','native/whisper',stopped.is_set):pytest.fail('Cancelled inference dispatched')
            assert gpu.status(tmp_path)['active_role']=='planner'
        finally:owner.close()


def test_30b_ram_pressure_selects_installed_9b_without_inference():
    from jarvis.repo_abilities import AbilityForge
    ability=AbilityForge.__new__(AbilityForge)
    ability.model_chat=None;ability.model='qwen3-coder:30b';ability.fallback_model='qwen3.5:9b';ability.memory_margin_gb=2
    tags={'models':[{'name':ability.model,'size':19*2**30},{'name':ability.fallback_model,'size':6*2**30}]}
    with patch('psutil.virtual_memory',return_value=SimpleNamespace(available=10*2**30)),patch('jarvis.repo_abilities.requests.get') as get:
        get.return_value.json.return_value=tags
        assert ability.pick_model()=='qwen3.5:9b'


@pytest.mark.parametrize('safe',[True,False])
def test_runtime_voice_fallback_preserves_sentence_only_before_audio_commit(safe):
    from jarvis.speech import Speech
    speech=Speech({'engine':'f5'},Mock())
    speech.worker_engine='f5';speech.outstanding[1]=0;speech.submitted[1]='Keep this sentence intact.'
    speech._event(json.dumps({'id':1,'error':'synthesis_or_output_failure','safe_to_retry':safe}))
    if safe:
        assert speech.queue.get_nowait()==(0,'Keep this sentence intact.')
        assert 'f5' in speech.failed_backends
    else:
        assert speech.queue.empty()  # Uncertain audible speech must never be replayed.
    assert not speech.submitted and not speech.outstanding


@pytest.mark.parametrize('text,expected',[
    ('$12.50','twelve dollars and fifty cents'),('£1.01','one pound and one penny'),
    ('42','forty two'),('3.14','three point one four'),
    ('num_ctx','num ctx'),('loadModel','load Model'),('≤','less than or equal to'),
    ('C:\\Temp\\file.py','C drive slash Temp slash file dot py')])
def test_speech_normalization(text,expected):
    assert normalize(text).strip()==expected


@pytest.mark.parametrize('text',[
    '中文字符。こんにちは。', 'x ≤ 42 × √9', 'https://example.org/a?q=2',
    'Traceback (most recent call last):\nFile "app.py", line 42\nValueError: invalid',
    '| Name | Value |\n| --- | --- |\n| budget | $12.50 |',
    ' '.join(['A word about the system.']*200), 'Bad\udc81 text remains safe.'])
def test_adversarial_f5_input_reaches_bounded_finite_pcm(text):
    from jarvis.f5_speech import render
    voice=SimpleNamespace(jarvis_options={},infer=Mock(return_value=(np.ones(4800,np.float32),24000,None)))
    with patch('jarvis.f5_speech.reference',return_value=('fixture.wav','reference','neutral')),patch('jarvis.f5_speech.chunks',side_effect=lambda value,*a:[value[i:i+150] for i in range(0,len(value),150)]):
        pieces=list(render(voice,{'text':text},threading.Event()))
    assert pieces and all(np.isfinite(audio).all() and abs(audio).max()<=.98 for audio,rate in pieces)
    for call in voice.infer.call_args_list:call.kwargs['gen_text'].encode('utf-8')


def test_lookahead_head_has_eight_words_and_keeps_following_text():
    text='One two three four five six seven eight nine ten eleven twelve.'
    cut=opening_clause(text)
    assert len(text[:cut].split())==8
    from jarvis.speech import Speech
    speech=Speech({'engine':'f5'},Mock());speech._enqueue=Mock()
    speech.stream(text,phase='Conversing')
    speech.say(text)
    assert ' '.join(call.args[0] for call in speech._enqueue.call_args_list)==text


def test_pcm_ring_wrap_reuse_fragmentation_and_shared_ownership():
    from multiprocessing import shared_memory
    ring=PCMBuffer(100)
    try:
        a=ring.put(np.arange(40,dtype=np.float32));b=ring.put(np.arange(50,dtype=np.float32))
        with pytest.raises(BufferError):ring.put(np.ones(11,np.float32))
        attached=shared_memory.SharedMemory(name=ring.shm.name)
        try:assert np.ndarray((100,),np.float32,buffer=attached.buf)[39]==39
        finally:attached.close()
        ring.release(a);ring.release(b)
        assert ring.free==[(0,100)]
        c=ring.put(np.ones(100,np.float32));assert ring.read(c).sum()==100
        ring.release(c)
    finally:ring.close()
    ring.close()


def test_capture_pcm_queue_preserves_metadata_and_returns_owned_copy():
    capture=CaptureQueue(16000)
    try:
        source=np.arange(1600,dtype=np.float32)
        capture.put_nowait((source,True,('synthetic spoken reference',)))
        source[:]=0
        audio,playing,refs=capture.get_nowait()
        assert audio[-1]==1599 and playing and refs==('synthetic spoken reference',)
    finally:capture.close()


def test_alt_release_injection_failure_forwards_real_keyup_and_clears_state():
    keys=PushToWrite(Mock(),hold_seconds=0,send=Mock(side_effect=OSError('injected failure')))
    try:
        keys.key(VK_LCONTROL,True);keys.key(VK_LMENU,True)
        wait_for(keys.active.is_set)
        assert not keys.key(VK_LMENU,False)
        assert not keys.alt and not keys.active.is_set()
        keys.key(VK_LCONTROL,False)
        assert not keys.ctrl and not keys.combo
    finally:keys.stop()


@pytest.mark.parametrize('sent',[0,1,2,3])
def test_native_alt_mask_checks_sendinput_count(sent):
    user=SimpleNamespace(SendInput=Mock(return_value=sent),keybd_event=Mock())
    with patch('ctypes.WinDLL',return_value=user):
        if sent==3:PushToWrite._send_mask_and_alt_up()
        else:
            with pytest.raises(OSError):PushToWrite._send_mask_and_alt_up()
    assert user.keybd_event.call_count==(0 if sent==3 else 1)


def test_stale_hold_timer_cannot_arm_new_chord():
    keys=PushToWrite(Mock(),hold_seconds=0,send=Mock())
    try:
        keys.ctrl=keys.alt=keys.combo=True;keys.hold_epoch=2
        keys._arm(time.monotonic(),1)
        assert not keys.active.is_set()
        keys._arm(time.monotonic(),2)
        assert keys.active.is_set()
    finally:keys.stop()
    assert not keys.ctrl and not keys.alt and not keys.latched


def test_barge_in_wake_word_and_second_third_command_routes():
    from jarvis.voice_input import VoiceInput
    from jarvis.engine import Engine
    speech=Mock();speech.output_recent.return_value=True;speech.output_references.return_value=('The first answer is still playing.',)
    voice=VoiceInput(speech);submitted=[]
    engine=Engine(submitted.append,Mock())
    assert voice.filter('The first answer is still playing.') is None
    assert voice.filter('open calculator') is None
    for text in ('Jarvis open notepad','Jarvis open calculator','Jarvis volume up'):
        engine.feed(voice.filter(text),final=True)
    assert len(submitted)==3 and speech.interrupt.call_count==3


def test_token_flood_coalesces_and_preserves_cancel_final_and_media():
    buffer=UIEventBuffer()
    text='word '*1000
    for index in range(1,len(text)+1):
        buffer.put(('answer_stream',{'text':text[:index],'phase':'Conversing'}))
        buffer.put(('level',index%100))
    assert buffer.qsize()==2 and buffer.coalesced>=9998
    buffer.put(('media_card',{'service':'spotify','phase':'playing'}))
    buffer.put(('answer_stream',{'text':'','active':False}))
    buffer.put(('answer','Finished.'))
    rows=[]
    while not buffer.empty():rows.append(buffer.get_nowait())
    assert rows[0][1]['text']==text
    assert [r[0] for r in rows][-3:]==['media_card','answer_stream','answer']


def test_ui_draft_replacement_and_verified_phase_remain_ordered():
    buffer=UIEventBuffer()
    for row in [('answer_stream',{'text':'draft','phase':'Generating answer'}),('answer_stream',{'text':'checked','phase':'Generating verified answer'}),('answer_stream',{'phase':'Generating verified answer'}),('answer','checked')]:buffer.put(row)
    rows=[buffer.get_nowait() for _ in range(buffer.qsize())]
    assert rows[0][1]['text']=='draft' and rows[1][1]['text']=='checked' and rows[2][0]=='answer'


def test_task_telemetry_keeps_initial_reveal_and_final_dag_transition():
    buffer=UIEventBuffer()
    buffer.put(('task_status',{'task_id':'synthetic','active':True,'phase':'Planning','reveal':True}))
    buffer.put(('task_status',{'task_id':'synthetic','active':True,'phase':'Planning','characters':500}))
    buffer.put(('task_status',{'task_id':'synthetic','active':False,'phase':'Verified'}))
    assert buffer.qsize()==2
    assert buffer.get_nowait()[1]['reveal'] is True
    assert buffer.get_nowait()[1]['phase']=='Verified'


def test_mind_dag_refresh_tracks_states_without_waiting_for_checkpoint_io():
    from jarvis.task_state import TaskState
    from jarvis.island_mind import MindView
    state=TaskState.__new__(TaskState);state.lock=threading.RLock()
    state.data={'current':{'task_id':'synthetic','status':'running','dag':{'steps':{'read':{'status':'succeeded'},'plan':{'status':'running'}}}}}
    view=MindView.__new__(MindView);view.header=Mock();view.dag=Mock();view.dag_text=None
    view.draw=Mock();view.describe=Mock()
    cognition=SimpleNamespace(enabled=True,lock=threading.RLock(),snapshot=lambda:{'cycle_hz':4,'cycles':10})
    view.app=SimpleNamespace(actions=SimpleNamespace(task_state=state,cognition=cognition))
    view.refresh();assert 'plan: running' in view.dag.configure.call_args.kwargs['text']
    state.data['current']['dag']['steps']['plan']['status']='succeeded'
    view.refresh();assert 'plan: succeeded' in view.dag.configure.call_args.kwargs['text']
    held=threading.Event();release=threading.Event()
    def checkpoint():
        with state.lock:held.set();release.wait(2)
    thread=threading.Thread(target=checkpoint);thread.start();held.wait(1)
    try:
        at=time.monotonic();view.refresh();assert time.monotonic()-at < .05
        assert state.ui_snapshot() is None
    finally:release.set();thread.join(2)


def test_speech_refuses_contradictory_safe_replay_after_audio_commit():
    from jarvis.speech import Speech
    speech=Speech({'engine':'f5'},Mock());speech.worker_engine='f5'
    speech.outstanding[1]=0;speech.submitted[1]='Already committed.'
    speech._event(json.dumps({'id':1,'audio_ready':True}))
    speech._event(json.dumps({'id':1,'error':'failure','safe_to_retry':True}))
    assert speech.queue.empty() and not speech.audio_committed


def test_shared_pcm_player_preserves_chunk_boundaries_and_reclaims_cancelled_audio():
    from jarvis.kokoro_speech import Player
    player=Player.__new__(Player);player.np=np;player.rate=24000
    player.events=queue.Queue();player.lock=threading.Lock();player.pieces=collections.deque();player.current=None
    player.pcm=PCMBuffer(100)
    try:
        player.add(1,np.ones(20,np.float32)*.2)
        player.add(1,np.ones(30,np.float32)*.3);player.finish(1,50/24000)
        out=np.zeros((60,1),np.float32);player.callback(out,60,None,None)
        assert np.allclose(out[:20],.2) and np.allclose(out[20:50],.3) and not out[50:].any()
        assert player.pcm.free==[(0,100)]
        player.add(2,np.ones(50,np.float32));player.discard({2})
        assert player.pcm.free==[(0,100)]
    finally:player.pcm.close()


def test_silero_silence_is_filtered_before_whisper_decode(tmp_path):
    from jarvis.audio import Listener
    listener=Listener(tmp_path,None,Mock(),Mock())
    count=[0]
    def blocks(**kwargs):
        count[0]+=1
        if count[0]>=5:listener.stop_event.set()
        return np.zeros(1600,np.float32),False,()
    listener.audio.get=blocks
    listener._decode=Mock();listener.jobs.put=Mock()
    model=Mock();model.transcribe.return_value=(iter(()),None)
    model.model=SimpleNamespace(device='cuda',compute_type='int8_float16')
    stream=Mock();stream.__enter__=Mock(return_value=stream);stream.__exit__=Mock(return_value=False)
    with patch('jarvis.whisper_backend.load_model',return_value=model),patch('sounddevice.query_devices',return_value={'default_samplerate':16000,'name':'Synthetic capture'}),patch('sounddevice.InputStream',return_value=stream),patch('faster_whisper.vad.get_vad_model',return_value=lambda _:np.zeros(32)):
        listener.run()
    listener.jobs.put.assert_not_called()
    assert model.transcribe.call_count==1  # Intentional CUDA warmup only.


def test_all_35_pip_emotions_render_and_island_state_sync():
    from PIL import Image
    from jarvis.island_buddy import EMOTIONS,pose_for,paint
    from jarvis.island import Island
    assert len(EMOTIONS)==35
    for emotion in EMOTIONS:
        image=Image.new('RGBA',(160,160))
        paint(image,80,80,60,pose_for(emotion,1.25),1)
        assert image.getbbox() is not None
    app=Mock();app.root.winfo_screenwidth.return_value=1920
    app.desk=SimpleNamespace(view='Overview',has_reply=True,work={'active':False},reply='')
    island=Island(app,Mock())
    island.notify('answer_stream',{'text':'Working','phase':'Conversing'})
    assert island.stream_active
    island.notify('answer','Done');assert not island.stream_active
    media={'service':'spotify','phase':'playing','title':'Synthetic song'}
    island.notify('media_card',media);assert island.media==media


def test_pip_pdf_docx_corrupt_ingestion_and_cited_context(tmp_path):
    from jarvis.documents import Document,Library
    from tests.test_documents import make_pdf
    pdf=make_pdf(tmp_path/'fifty.pdf',[f'Page {i+1}. Aurora budget is 12000 euros. '+('Evidence for Aurora. '*60) for i in range(50)])
    doc=Document.build(pdf)
    assert doc.data['pages']==50 and doc.data['mode']=='graph'
    context=doc.context('What is Aurora budget?')
    assert '12000' in json.dumps(context) and 'page' in json.dumps(context).lower()
    word=tmp_path/'brief.docx'
    with zipfile.ZipFile(word,'w') as archive:
        archive.writestr('word/document.xml','<w:document><w:p><w:t>Aurora budget is 12000 euros for the new website.</w:t></w:p></w:document>')
    assert Document.build(word).data['mode']=='light'
    corrupt=tmp_path/'corrupt.bin';corrupt.write_bytes(b'\x00\xffbroken')
    with pytest.raises(ValueError):Document.build(corrupt)
    library=Library(SimpleNamespace(base=tmp_path),model_chat=Mock())
    try:
        with patch.object(library,'_chat',return_value='The budget is 12000 euros [page 1].') as model:
            answer=library.answer('What is the budget?',doc)
        assert '[page 1]' in answer and '12000' in json.dumps(model.call_args.args[1])
    finally:library.close()


def test_pip_corrupt_drop_is_contained_without_sending_any_file(tmp_path):
    from jarvis.documents import Library
    from jarvis.file_drop import handle
    corrupt=tmp_path/'corrupt.pdf';corrupt.write_bytes(b'not a valid PDF binary')
    actions=SimpleNamespace(base=tmp_path,report=Mock())
    actions.documents=Library(actions)
    try:
        with patch('jarvis.whatsapp.ask',return_value=None):
            result=handle(actions,[str(corrupt)])
        assert result and not actions.documents.session
        phases=[call.args[1]['phase'] for call in actions.report.call_args_list if call.args[0]=='media_card']
        assert 'eating' in phases and 'ready' in phases
    finally:actions.documents.close()


@pytest.mark.parametrize('gate', ['simultaneous_cuda','laya_25','lora_load','legacy_alias','ttfa','live_hotkeys','live_mind_dag'])
def test_live_acceptance_gate(gate):
    evidence=os.environ.get('JARVIS_PHASE2_EVIDENCE')
    if not evidence:pytest.skip('BLOCKED live gate: run scripts.verification.phase2_gpu_voice_probe; fixtures do not certify '+gate)
    result=json.loads(Path(evidence).read_text(encoding='utf-8'))['gates'][gate]
    if result['status']=='blocked':pytest.skip('BLOCKED '+gate+': '+result['reason'])
    assert result['status']=='pass',result
