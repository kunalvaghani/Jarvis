"""Owned microphone/model transports, no real recording, hook or desktop input."""
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
import pytest
from jarvis.audio import DecodeJob, Listener, command_text
from jarvis.command_cleanup import CommandCleanup
from jarvis.commands import Command
from jarvis.engine import Engine


def wait_for(condition, seconds=2):
    end = time.monotonic()+seconds
    while not condition() and time.monotonic()<end:
        time.sleep(.005)
    assert condition()


def decode_words(tmp_path, texts, **extra):
    submitted, written, events = [], [], []
    engine = Engine(submitted.append, Mock())
    listener = Listener(tmp_path, None, engine, lambda *a:events.append(a),
        writer=lambda *a:written.append(a), **extra)
    results = iter(texts)
    class Model:
        def transcribe(self, *_args, **_kwargs):
            text = next(results)
            return iter([SimpleNamespace(avg_logprob=0., words=[SimpleNamespace(end=1., word=text)])]), None
    return listener, Model(), submitted, written, events


def test_wake_and_command_fixture(tmp_path):
    listener, model, sent, _, events = decode_words(tmp_path, ['Jarvis open Calculator'])
    listener.jobs.put(DecodeJob(1, 0, None, final=True))
    worker = threading.Thread(target=listener._decode, args=(model,))
    worker.start()
    try:
        wait_for(lambda: bool(sent))
        assert sent == [Command('open', 'calculator')]
    finally:
        listener.stop(); worker.join(2)


def test_JRV_04_004_cleanup_negation(tmp_path):
    request = Mock(side_effect=AssertionError('Protected negation must never reach cleanup model'))
    cleanup = CommandCleanup({'enabled':True}, request=request)
    listener, model, sent, _, _ = decode_words(tmp_path, ['Jarvis do not send that message'], command_cleanup=cleanup)
    listener.jobs.put(DecodeJob(1, 0, None, final=True))
    worker = threading.Thread(target=listener._decode, args=(model,));worker.start()
    try:
        wait_for(lambda: listener.engine.active)
        time.sleep(.03)
        assert not sent
        request.assert_not_called()
    finally:
        listener.stop();worker.join(2)


def test_JRV_04_005_numeric_cleanup_distinction():
    engine = Engine(Mock(), Mock());engine.activate()
    request = Mock(side_effect=lambda text, alternative, *_:alternative)
    cleanup = CommandCleanup({'enabled':True}, request=request)
    fifteen = cleanup.clean('um set timer for fifteen minutes', engine)
    fifty = cleanup.clean('um set timer for fifty minutes', engine)
    assert 'fifteen' in fifteen and 'fifty' in fifty and fifteen != fifty
    assert request.call_count == 2  # proposal selection never invents a number


def test_unknown_name_preserved():
    engine = Engine(Mock(), Mock());engine.activate()
    cleanup = CommandCleanup({'enabled':True}, request=lambda text, alternative, *_:alternative)
    assert cleanup.clean('um open ZéphyrWorks', engine) == 'open ZéphyrWorks'
    # Only name preservation is proved; application clarification is separate.


def test_JRV_04_012_distinct_final_utterances_not_deduped():
    sent = []; engine = Engine(sent.append, Mock())
    engine.feed('Jarvis open Calculator', final=True)
    engine.feed('open Calculator', final=True)
    assert sent == [Command('open','calculator'), Command('open','calculator')]


def capture_fixture(listener, rate=48000, release=True, error=None):
    """Drive production capture through owned fake input blocks and fake VAD."""
    jobs = []
    push = listener.push_to_write
    count = [0]
    def get(**_):
        count[0] += 1
        if count[0] == 2 and release:
            push.active.clear()
        if error:
            raise error
        return np.ones(rate//10, dtype=np.float32)*.02, False, ()
    listener.audio.get = get
    def record(job):
        jobs.append(job); listener.stop_event.set()
    listener.jobs.put = record
    listener._decode = lambda _:None
    stream = Mock()
    stream.__enter__ = Mock(return_value=stream)
    stream.__exit__ = Mock(return_value=False)
    model = Mock()
    model.transcribe.return_value = (iter(()), None)
    model.model = SimpleNamespace(device='fixture', compute_type='fixture')
    with patch('jarvis.whisper_backend.load_model',return_value=model), \
         patch('sounddevice.query_devices',return_value={'default_samplerate':rate,'name':'Owned fake microphone'}), \
         patch('sounddevice.InputStream',return_value=stream), \
         patch('faster_whisper.vad.get_vad_model',return_value=lambda _:np.ones(32)):
        listener.run()
    return jobs, stream


def test_release_final_block_is_resampled(tmp_path):
    push = SimpleNamespace(active=threading.Event(), session=7)
    push.active.set()
    listener = Listener(tmp_path, None, Mock(), Mock(), push_to_write=push)
    jobs, stream = capture_fixture(listener)
    assert len(jobs)==1 and jobs[0].write and jobs[0].final
    assert jobs[0].session==7
    assert len(jobs[0].audio)==3200  # exactly 200 ms at Whisper's 16 kHz
    stream.__exit__.assert_called_once()


@pytest.mark.parametrize('option', [{'silence_seconds':-1}, {'vad_threshold':float('nan')},
    {'partial_interval_seconds':True}, {'device':'invalid'}, {'compute_type':[]}])
def test_JRV_04_029_invalid_whisper_settings(tmp_path, option):
    with pytest.raises(ValueError, match='whisper'):
        Listener(tmp_path, None, Mock(), Mock(), options=option)


def test_capture_failure_never_logs_private_payload(tmp_path):
    events = []
    push = SimpleNamespace(active=threading.Event(), session=0)
    listener = Listener(tmp_path, None, Mock(), lambda *a:events.append(a), push_to_write=push)
    jobs, stream = capture_fixture(listener, error=OSError('FAKE_PRIVATE_DEVICE_PATH'))
    assert not jobs and listener.stop_event.is_set()
    assert 'FAKE_PRIVATE_DEVICE_PATH' not in str(events)
    stream.__exit__.assert_called_once()


def test_decoder_join_is_bounded_and_stalled_worker_visible(tmp_path):
    listener = Listener(tmp_path, None, Mock(), Mock())
    joined = []
    class Worker:
        def __init__(self, *_, **__):pass
        def start(self):pass
        def join(self, timeout=None):joined.append(timeout)
        def is_alive(self):return True
    stream = Mock()
    stream.__enter__ = Mock(side_effect=lambda:listener.stop_event.set())
    stream.__exit__ = Mock(return_value=False)
    model = Mock();model.transcribe.return_value=(iter(()),None)
    with patch('jarvis.whisper_backend.load_model',return_value=model), \
         patch('sounddevice.query_devices',return_value={'default_samplerate':16000,'name':'fixture'}), \
         patch('sounddevice.InputStream',return_value=stream), \
         patch('faster_whisper.vad.get_vad_model',return_value=Mock()), \
         patch('jarvis.audio.threading.Thread',Worker):
        listener.run()
    assert joined == [2.]
    assert listener.health()['error']=='decoder_stalled'


def test_JRV_04_026_duplicate_final_is_not_replayed(tmp_path):
    listener, model, sent, _, _ = decode_words(tmp_path, ['Jarvis open Calculator']*3)
    for utterance in (1,1,2):
        listener.jobs.put(DecodeJob(utterance,0,None,final=True))
    worker=threading.Thread(target=listener._decode,args=(model,));worker.start()
    try:
        wait_for(lambda: len(sent)>=2)
        time.sleep(.03)
        assert sent == [Command('open','calculator')]*2
    finally:
        listener.stop();worker.join(2)
