"""Continuous voice conversation: early final decode, turn-taking, Hinglish, barge-in, acknowledgements, bridges."""
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest

from jarvis.audio import DecodeJob, Listener
from jarvis.commands import Command
from jarvis.conversation_intent import quick_kind
from jarvis.engine import Engine
from jarvis.voice_input import VoiceInput, echo_likely
from jarvis.voice_runtime import endpoint_delay, normalize_intent, response_instruction


class CountingModel:
    """Stands in for Whisper: counts decodes and returns one fixed transcript."""
    def __init__(self, text='Jarvis open calculator'):
        self.calls, self.text = 0, text

    def transcribe(self, audio, **kwargs):
        self.calls += 1
        return iter([SimpleNamespace(avg_logprob=0, words=[SimpleNamespace(end=1, word=self.text)])]), \
            SimpleNamespace(language='en', language_probability=1.)


def decode(jobs, model):
    sent = []
    engine = Engine(sent.append, Mock(), 0)
    engine.activate()
    listener = Listener('unused', None, engine, Mock())
    for job in jobs:
        listener.jobs.put(job)
    worker = threading.Thread(target=listener._decode, args=(model,))
    worker.start()
    deadline = time.monotonic() + 3
    while not sent and time.monotonic() < deadline:
        time.sleep(.01)
    listener.stop()
    worker.join(3)
    return sent, list(listener.decode_metrics)


def test_final_reuses_the_early_decode_when_only_silence_followed():
    audio = np.zeros(16000, np.float32)
    model = CountingModel()
    sent, metrics = decode([DecodeJob(1, 0, audio, speculative=True),
                            DecodeJob(1, 0, np.zeros(24000, np.float32), final=True, reuse=16000)], model)
    assert sent == [Command('open', 'calculator')]
    assert model.calls == 1 and metrics[-1]['reused'] and metrics[0]['speculative']


def test_final_decodes_again_when_speech_followed_the_early_decode():
    model = CountingModel()
    sent, metrics = decode([DecodeJob(1, 0, np.zeros(16000, np.float32), speculative=True),
                            DecodeJob(1, 0, np.zeros(32000, np.float32), final=True, reuse=0)], model)
    assert sent == [Command('open', 'calculator')] and model.calls == 2 and not metrics[-1]['reused']


def test_an_early_decode_alone_never_acts():
    model = CountingModel()
    sent, _ = decode([DecodeJob(1, 0, np.zeros(16000, np.float32), speculative=True)], model)
    assert sent == [] and model.calls == 1


def test_early_jobs_are_not_coalesced_away_by_a_later_partial():
    listener = Listener('unused', None, Engine(Mock(), Mock()), Mock())
    listener.jobs.put(DecodeJob(1, 0, np.zeros(10, np.float32), speculative=True))
    listener.jobs.put(DecodeJob(1, 0, np.zeros(20, np.float32)))
    assert [job.speculative for job in listener.jobs.items] == [True, False]


def test_conversation_turn_taking():
    assert endpoint_delay('conversation', 'open chrome') == .55
    assert endpoint_delay('conversation', '') == .55  # unstable captions do not delay the turn
    for unfinished in ('open chrome and', 'Chrome kholo aur', 'Chrome खोलो और', 'pehle notepad phir'):
        assert endpoint_delay('conversation', unfinished) == 1.8
    assert endpoint_delay('conversation', ' '.join(['word'] * 20)) == .9
    assert endpoint_delay('conversation', writing=True) == 1.8


def test_continuous_conversation_never_falls_asleep_until_told():
    sent = []
    engine = Engine(sent.append, Mock(), 0)
    engine.activate(now=0)
    engine.feed('open notepad', final=True, now=10_000)
    assert engine.active and sent[-1] == Command('open', 'notepad')
    engine.feed('go to sleep', final=True, now=10_001)
    assert not engine.active


@pytest.mark.parametrize('text,expected', [
    ('YouTube kholo', 'open YouTube'), ('यूट्यूब खोलो', 'open YouTube'), ('Spotify band karo', 'close Spotify'),
    ('Arijit Singh ke gaane bajao', 'play Arijit Singh ke gaane'),
    ('python tutorial search karo', 'search for python tutorial'),
    ('Chrome kholo aur python tutorial search karo', 'open Chrome then search for python tutorial'),
    ('Chrome kholo aur mujhe batao', 'Chrome kholo aur mujhe batao'),  # not every part is a command: unchanged
    ('write exactly ouvre Firefox', 'write exactly ouvre Firefox')])
def test_hinglish_commands(text, expected):
    assert normalize_intent(text) == expected


@pytest.mark.parametrize('text,kind', [('YouTube kholo', 'task'), ('email bhej do', 'task'), ('गाना बजाओ', 'task'),
                                       ('kaise ho', 'chat'), ('main thak gaya hoon aaj', 'chat'),
                                       ('mujhe ek joke sunao', 'chat'), ('haan bilkul', 'chat')])
def test_hinglish_chat_or_task_needs_no_model(text, kind):
    assert quick_kind(text) == kind


def test_hindi_replies_are_written_in_devanagari_for_the_voice():
    assert 'Devanagari' in response_instruction('auto') and 'Devanagari' in response_instruction('hi')


class FakeSpeech:
    def __init__(self):
        self.interrupted = 0

    def interrupt(self):
        self.interrupted += 1

    def output_recent(self):
        return True


def test_speaker_barge_in_ignores_our_own_voice_and_stops_for_the_user():
    speech, controls = FakeSpeech(), Mock()
    voice = VoiceInput(speech, {'enabled': True, 'audio_mode': 'speakers', 'speaker_barge_in': True},
                       awake=lambda: True, interrupt=controls)
    refs = ('Here are five Blender tutorials you might like for modelling a chair',)
    # Our reply heard back through the speakers, even slightly misheard, neither stops us nor becomes a command.
    assert voice.update('here are five blender tutorial', False, 1, True, refs, 1) is None
    assert voice.update('five blender tutorials you might like', True, 1, True, refs, 2) is None
    assert speech.interrupted == 0 and not controls.called
    # The user talking over us: the voice stops while they are still speaking ...
    assert voice.update('actually open spotify', False, 2, True, refs, 1) is None
    assert speech.interrupted == 1 and not controls.called
    # ... and the finished sentence is the command.
    assert voice.update('actually open spotify', True, 2, True, refs, 1.2) == 'actually open spotify'
    controls.assert_called_once_with('CORRECTION')


def test_speaker_barge_in_stays_off_unless_configured():
    speech = FakeSpeech()
    voice = VoiceInput(speech, {'enabled': True, 'audio_mode': 'speakers'}, awake=lambda: True)
    assert voice.update('actually open spotify', False, 1, True, (), 1) is None
    assert voice.update('actually open spotify', True, 1, True, (), 1) is None
    assert speech.interrupted == 0
    with pytest.raises(ValueError):
        VoiceInput(speech, {'enabled': True, 'speaker_barge_in': 'yes'})


def test_echo_likely_needs_most_words_from_our_reply():
    refs = ('The weather in Mumbai is thirty degrees and sunny',)
    assert echo_likely('weather in mumbai is thirty', refs)
    assert not echo_likely('what about tomorrow in delhi', refs)


def test_mixed_hindi_and_english_get_their_own_phonemes_in_one_hindi_voice():
    from jarvis import kokoro_speech as ks
    calls = {}

    class Voice:
        voices = {'hm_omega': None}
        tokenizer = SimpleNamespace(phonemize=lambda text, lang: f'<{lang}:{text.strip()}>')

        def create(self, text, voice, speed, lang, is_phonemes=False):
            calls.update(text=text, lang=lang, phonemes=is_phonemes)
            return np.ones(10, np.float32), 24000
    ks._cache.clear()
    ks.synthesize(Voice(), 'मैं YouTube खोल रहा हूँ और Python tutorial भी।', {'voice': 'hm_omega'})
    assert calls['phonemes'] and calls['lang'] == 'hi'
    assert '<en-us:YouTube>' in calls['text'] and '<en-us:Python tutorial>' in calls['text']
    assert '<hi:मैं>' in calls['text']


def test_short_phrases_replay_from_the_voice_cache():
    from jarvis import kokoro_speech as ks
    made = []

    class Voice:
        voices = {'am_michael': None}

        def create(self, text, voice, speed, lang, is_phonemes=False):
            made.append(text)
            return np.ones(10, np.float32), 24000
    ks._cache.clear()
    first, _ = ks.synthesize(Voice(), 'On it.', {'voice': 'am_michael', 'speed': 1.0})
    again, _ = ks.synthesize(Voice(), 'On it.', {'voice': 'am_michael', 'speed': 1.0})
    assert made == ['On it.'] and np.array_equal(first, again) and again is not first


def test_first_phrase_is_short_so_audio_starts_early():
    from jarvis.natural_voice import split_phrases
    phrases = [p[0] for p in split_phrases('Sure. That sounds like a long day, so take it easy tonight.')]
    assert phrases[0] == 'Sure.'


def acknowledgement(state, kind='task', spoken_after=False, quiet=False):
    speech = SimpleNamespace(say=Mock(), output_recent=lambda: False, last_said=0.)
    row = {'state': state, 'command': {'kind': kind}}
    app = SimpleNamespace(config={'voice': {'acknowledge_seconds': .05}}, speech=speech,
                          listener=SimpleNamespace(language='en'),
                          actions=SimpleNamespace(ingress=SimpleNamespace(store=SimpleNamespace(get=lambda i: row),
                                                                          quiet=lambda: quiet)))
    import main
    main.App._acknowledge_later(app, 'task-1')
    if spoken_after:
        speech.last_said = time.monotonic()
    time.sleep(.25)
    return speech.say


def test_a_long_task_gets_a_spoken_acknowledgement():
    acknowledgement('RUNNING').assert_called_once_with('On it.')


@pytest.mark.parametrize('case', [dict(state='COMPLETED'), dict(state='RUNNING', kind='ask'),
                                  dict(state='RUNNING', spoken_after=True), dict(state='RUNNING', quiet=True),
                                  dict(state='WAITING_APPROVAL')])
def test_no_acknowledgement_when_done_chatting_already_spoken_quiet_or_waiting(case):
    acknowledgement(**case).assert_not_called()


def test_helper_models_on_cpu_skip_the_gpu_lease_and_stay_loaded():
    from jarvis import command_cleanup
    seen = {}

    def direct(payload, timeout, cancelled):
        seen.update(payload)
        return {'kind': 'chat'}
    policy = {'enabled': True, 'helper_gpu': False}
    with patch('jarvis.gpu_scheduler.configured', return_value=policy), \
            patch('jarvis.gpu_scheduler.Lease', side_effect=AssertionError('no lease for CPU helpers')), \
            patch.object(command_cleanup, '_stream_json', direct):
        assert command_cleanup.stream_json({'model': 'qwen3.5:0.8b', 'keep_alive': '10m', 'options': {'num_gpu': 3}},
                                           3) == {'kind': 'chat'}
    assert seen['keep_alive'] == '10m' and seen['options']['num_gpu'] == 0


def test_queue_lanes_wake_when_work_arrives(tmp_path):
    from dataclasses import asdict
    from jarvis.task_policy import classify
    from jarvis.task_scheduler import ScheduledQueue
    from jarvis.task_store import TaskStore
    store = TaskStore(tmp_path / 'q.sqlite3', capacity=16)
    scheduler = ScheduledQueue(store, {}, recover=False)
    woke = threading.Event()
    original = scheduler.changed.notify_all

    def notify_all():
        woke.set()
        original()
    scheduler.changed.notify_all = notify_all
    command = Command('ask', 'hello')
    identity, _ = store.admit(asdict(command), None)
    store.transition(identity, 'CLASSIFYING')
    scheduler.put_nowait((0, command, threading.Event()), identity, classify(asdict(command)))
    assert woke.is_set()
    assert scheduler.get(timeout=1., lane='legacy')[1] == command


def test_windows_command_catalog_is_verified_once_and_rechecked_when_changed():
    from jarvis import windows_commands as wc
    wc._CATALOG.clear()
    with patch.object(wc, '_verified_catalog', wraps=wc._verified_catalog) as verify:
        first = wc.catalog()
        assert wc.catalog() is first and verify.call_count == 1
        wc._CATALOG['checked'] = -10.  # a second later
        wc._CATALOG['stamp'] = ('changed',)
        wc.catalog()
        assert verify.call_count == 2
