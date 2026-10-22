"""Deterministic orchestration tests; no physical audio or language-accuracy claims."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from jarvis.audio import DecodeJob, Listener
from jarvis.engine import Engine
from jarvis.speech import Speech, speech_language
from jarvis.ui_events import UIEventBuffer
from jarvis.voice_input import VoiceInput
from jarvis.voice_registry import piper_voices
from jarvis.voice_runtime import (Stabilizer, ResponseReports, detect_language,
    endpoint_delay, interruption_kind, normalize_intent, response_instruction, LanguageTracker)
from jarvis.whisper_backend import settings


def test_revision_reconstructs_corrected_hypothesis_and_resets_per_utterance():
    s = Stabilizer()
    first = s.update('session', 1, 'open Chrome')
    second = s.update('session', 1, 'open Firefox')
    assert first['state'] == 'PROVISIONAL'
    assert second['stable'] == 'open'
    assert first['text'][:second['replace_from']] + second['replacement'] == second['text']
    final = s.update('session', 1, 'open Firefox', True)
    assert final['state'] == 'FINAL' and final['stable'] == final['text']
    assert s.update('session', 2, 'new turn')['revision'] == 1


@pytest.mark.parametrize('text', ['jarvis open chrome then delete old.txt',
    'jarvis open notepad and write exactly SECRET', 'jarvis cancel all tasks',
    'jarvis go to sleep', 'jarvis run command echo hello'])
def test_partial_never_dispatches_any_effect(text):
    submit = Mock()
    engine = Engine(submit, Mock())
    engine.feed(text)
    submit.assert_not_called()


def test_adaptive_endpoint_preserves_hesitation_and_writing():
    assert endpoint_delay('fast', 'open chrome', True) == .5
    assert endpoint_delay('balanced', 'open chrome and', True) >= 1.8
    assert endpoint_delay('fast', writing=True) >= 1.8
    assert endpoint_delay('balanced') >= 1.1
    assert endpoint_delay('careful', 'open chrome', True) == 1.4


@pytest.mark.parametrize('text,language', [('मुझे Chrome खोलो', 'hi'),
    ('મારું ફોલ્ડર ખોલ', 'gu'), ('ouvre Chrome et cherche vidéos', 'fr'),
    ('Chrome kholo aur search karo', 'hi'), ('mara downloads ma latest PDF open kar', 'gu')])
def test_lightweight_language_features(text, language):
    assert detect_language(text) == language
    assert speech_language(text) == language


def test_ambiguous_language_retains_context_and_high_confidence_switches():
    assert detect_language('Chrome', 'fr', .3, previous='gu') == 'gu'
    assert detect_language('Chrome', 'fr', .95, previous='gu') == 'fr'


@pytest.mark.parametrize('text,expected', [('Chrome kholo', 'open Chrome'),
    ('ouvre Firefox', 'open Firefox'), ('Chrome ખોલ', 'open Chrome'),
    ('write exactly ouvre Firefox', 'write exactly ouvre Firefox'),
    ('ouvre Chrome et cherche Python', 'ouvre Chrome et cherche Python')])
def test_whole_command_normalization_preserves_literals(text, expected):
    assert normalize_intent(text) == expected


@pytest.mark.parametrize('text,expected', [('stop talking', 'STOP'), ('cancel that task', 'CANCEL'),
    ('No I meant Firefox', 'CORRECTION'), ('instead open Spotify', 'REPLACEMENT'),
    ('what about the second one', 'FOLLOW-UP'), ('and also volume up', 'CONTINUATION'),
    ('hold on', 'PAUSE'), ('continue where you stopped', 'RESUME')])
def test_interruption_categories(text, expected):
    assert interruption_kind(text) == expected


def test_headphone_duplex_cancels_only_after_final_and_rejects_echo():
    speech = Speech({'enabled': True, 'engine': 'kokoro'}, Mock())
    interrupt = Mock()
    voice = VoiceInput(speech, {'enabled': True, 'audio_mode': 'headphones'},
        awake=lambda: True, interrupt=interrupt)
    refs = ('Here are five Blender tutorials',)
    assert voice.update('Here are five Blender tutorials', True, 1, True, refs, 2) is None
    assert voice.update('instead open Spotify', False, 2, True, refs, 1) is None
    interrupt.assert_not_called()
    assert voice.update('instead open Spotify', True, 2, True, refs, 1) == 'instead open spotify'
    interrupt.assert_called_once_with('REPLACEMENT')
    voice.update('instead open Spotify', True, 2, True, refs, 1)
    interrupt.assert_called_once()


def test_speaker_and_sleep_policies_keep_wake_gate():
    speech = Speech({'engine': 'kokoro'}, Mock())
    for awake, mode in [(True, 'speakers'), (False, 'headphones')]:
        voice = VoiceInput(speech, {'enabled': True, 'audio_mode': mode}, awake=lambda: awake)
        assert voice.update('open Spotify', True, 1, True, (), 1) is None


def test_stop_during_generation_and_resume_are_speech_controls_only():
    speech = Speech({'engine': 'kokoro'}, Mock())
    interrupt = Mock()
    voice = VoiceInput(speech, awake=lambda: True, interrupt=interrupt, responding=lambda: True)
    # A loudspeaker configuration still requires a wake word during output.
    assert voice.update('jarvis stop talking', True, 1, False, (), 1) is None
    interrupt.assert_called_with('STOP')
    assert voice.update('jarvis continue where you stopped', True, 2, False, (), 1) is None
    interrupt.assert_called_with('RESUME')


def test_canceled_worker_and_already_queued_response_are_fenced():
    generation = [0]
    pending = []
    class UI:
        def report(self, *args):
            raise AssertionError('expected scoped event')
        def report_scoped(self, kind, value, guard):
            pending.append((kind, value, guard))
    reports = ResponseReports(UI().report, lambda: generation[0])
    reports.bind(0)
    reports('answer', 'old')
    generation[0] += 1
    assert not pending[0][2]()
    reports('answer', 'late old')
    assert len(pending) == 1
    reports.bind(1)
    reports('answer', 'current')
    assert pending[-1][2]()


def test_scoped_stream_coalesces_and_final_is_ordered():
    events = UIEventBuffer()
    guard = lambda: True
    guard.voice_key = ('worker', 1)
    for i in range(1000):
        events.put(('response_guard', ('answer_stream', {'phase': 'Conversing', 'text': 'x' * i}, guard)))
    events.put(('response_guard', ('answer', 'final', guard)))
    assert events.qsize() == 2
    assert events.get_nowait()[1][1]['text'] == 'x' * 999
    assert events.get_nowait()[1][1] == 'final'


def test_installed_voice_registry_requires_metadata_and_model(tmp_path):
    (tmp_path / 'fr_test.onnx').write_bytes(b'owned fixture')
    metadata = tmp_path / 'fr_test.onnx.json'
    metadata.write_text(json.dumps({'language': {'code': 'fr_FR'}}))
    (tmp_path / 'gu_missing.onnx.json').write_text(json.dumps({'language': {'code': 'gu_IN'}}))
    (tmp_path / 'malformed.onnx.json').write_text('bad')
    assert piper_voices(tmp_path) == {'fr': tmp_path / 'fr_test.onnx'}


@pytest.mark.parametrize('options', [{'frame_ms': 0}, {'endpoint_mode': 'instant'},
    {'streaming_enabled': 'yes'}, {'max_utterance_seconds': float('nan')}])
def test_invalid_capture_configuration_is_rejected(options):
    with pytest.raises(ValueError):
        settings(options)


def test_forced_response_languages_are_supported_without_model_calls():
    for language in ('en', 'hi', 'gu', 'fr'):
        assert 'Respond' in response_instruction(language)
        assert speech_language('technical Python', language) == language


def test_language_hysteresis_rejects_one_metadata_flip():
    tracker = LanguageTracker(confirmations=2)
    assert tracker.update('Chrome', 'fr', .9) == 'en'
    assert tracker.update('Chrome', 'en', .9) == 'en'
    assert tracker.update('Chrome', 'fr', .9) == 'en'
    assert tracker.update('Chrome', 'fr', .9) == 'fr'
    assert tracker.update('મારું ફોલ્ડર') == 'gu'


def test_language_preference_only_changes_on_committed_speech():
    events, sent = [], []
    engine = Engine(sent.append, lambda *args: events.append(args))
    engine.feed('jarvis answer in french')
    assert not sent and not any(kind == 'voice_language' for kind, _ in events)
    engine.feed('jarvis answer in french', final=True)
    assert ('voice_language', 'fr') in events
    assert not sent


def test_native_script_wake_and_intent_use_existing_schema():
    sent = []
    engine = Engine(sent.append, Mock())
    engine.feed('જાર્વિસ Chrome ખોલ', final=True)
    assert sent[0].kind == 'open' and sent[0].value == 'chrome'
    engine.feed('જાર્વિસ Chrome ખોલ', final=True)
    assert len(sent) == 2 and sent[1] == sent[0]


def test_scoped_phase_only_updates_preserve_text_and_draft_barrier():
    queue = UIEventBuffer()
    guard = lambda: True
    guard.voice_key = ('worker', 1)
    for message in ({'phase': 'Conversing', 'text': 'first draft'}, {'phase': 'Conversing'}):
        queue.put(('response_guard', ('answer_stream', message, guard)))
    queue.put(('response_guard', ('answer_stream', {'phase': 'Conversing', 'text': 'replacement'}, guard)))
    assert queue.qsize() == 2
    assert queue.get_nowait()[1][1]['text'] == 'first draft'
    assert queue.get_nowait()[1][1]['text'] == 'replacement'


def test_missing_gujarati_voice_never_submits_to_english_backend():
    import threading
    import time
    events = []
    speech = Speech({'engine': 'piper', 'language': 'gu'}, lambda *a: events.append(a))
    speech._kokoro_send = Mock()
    speech.say('મારું ફોલ્ડર')
    speech.say('મારું ફોલ્ડર')
    thread = threading.Thread(target=speech._serve_queue)
    thread.start()
    try:
        deadline = time.monotonic() + 2
        while speech.queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(.01)
        assert speech.queue.unfinished_tasks == 0
        assert len([e for e in events if e[0] == 'warning']) == 1
        speech._kokoro_send.assert_not_called()
        assert speech.process is None
    finally:
        speech.closed.set()
        thread.join(2)


def test_native_transcript_view_revises_suffix_and_styles_provisional_words():
    import tkinter as tk
    from jarvis.island_desk import IslandDesk
    root = tk.Tk()
    root.withdraw()
    try:
        desk = IslandDesk.__new__(IslandDesk)
        desk.overview = tk.Text(root)
        s = Stabilizer()
        desk.notify('voice_transcript', s.update('session', 1, 'open Chrome'))
        desk.notify('voice_transcript', s.update('session', 1, 'open Firefox'))
        assert desk.overview.get('1.0', 'end-1c') == 'open Firefox'
        assert 'provisional' not in desk.overview.tag_names('1.1')
        assert 'provisional' in desk.overview.tag_names('1.8')
        desk.notify('voice_transcript', s.update('session', 1, 'open Firefox', True))
        assert not desk.overview.tag_ranges('provisional')
    finally:
        root.destroy()


def test_question_canceled_during_preparation_keeps_original_generation():
    from jarvis.knowledge import Knowledge
    knowledge = Knowledge({}, Mock())
    knowledge.prepare_context = lambda _question: knowledge.cancel()
    knowledge.submit('public synthetic question')
    assert knowledge.generation == 1
    assert knowledge.queue.get_nowait()[0] == 0
    knowledge.client.close()


def test_canceled_intent_classifier_cannot_submit_new_work():
    import threading
    from unittest.mock import patch
    from jarvis.actions import Actions
    actions = Actions.__new__(Actions)
    actions.generation, actions.closed, actions.config = 0, threading.Event(), {}
    actions.submit = Mock()
    def classify(*args):
        actions.generation = 1
        return 'chat'
    with patch('jarvis.conversation_intent.quick_kind', return_value=None), patch('jarvis.conversation_intent.model_kind', side_effect=classify):
        actions._route_unparsed('synthetic ambiguous request', 0)
    actions.submit.assert_not_called()


@pytest.mark.parametrize('options', [{'enabled': 'false'}, {'barge_in': 1}, {'audio_mode': 'auto'}, []])
def test_duplex_configuration_does_not_accept_truthy_nonbooleans(options):
    with pytest.raises(ValueError):
        VoiceInput(Mock(), options)


def test_kokoro_registry_discovers_existing_french_style_vectors(tmp_path):
    import numpy as np
    from jarvis.voice_registry import kokoro_voices
    from jarvis.natural_voice import language_for
    (tmp_path / 'kokoro-v1.0.onnx').write_bytes(b'fixture')
    with (tmp_path / 'voices-v1.0.bin').open('wb') as stream:
        np.savez(stream, am_michael=np.zeros(2), ff_siwis=np.ones(2))
    assert kokoro_voices(tmp_path)['fr'] == ('ff_siwis',)
    assert language_for('ff_siwis') == 'fr-fr'
    assert language_for('am_michael') == 'en-us'


def test_french_routes_to_its_installed_kokoro_voice_without_english_normalization():
    from unittest.mock import patch
    speech = Speech({'engine': 'piper', 'language': 'fr'}, Mock())
    speech.say('Bonjour, comment allez-vous ?')
    def send(*args, **kwargs):
        speech.closed.set()
        return True
    speech._kokoro_send = Mock(side_effect=send)
    with patch('jarvis.voice_registry.kokoro_voices', return_value={'fr': ('ff_siwis',)}), patch('jarvis.voice_registry.piper_voices', return_value={}), patch('jarvis.speech.Path.is_file', return_value=True):
        speech._serve_queue()
    payload = speech._kokoro_send.call_args.args[1]
    assert payload['voice'] == 'ff_siwis' and not payload['natural']


def test_decode_loops_are_not_usable_final_commands():
    from jarvis.voice_runtime import repetitive_hypothesis
    assert repetitive_hypothesis('ব' * 80)
    assert repetitive_hypothesis('open open open open open open open')
    assert not repetitive_hypothesis('write exactly hello hello hello')


def test_repetitive_final_decode_never_reaches_engine_or_writer(tmp_path):
    import threading
    from tests.test_voice_stt_audit import decode_words, wait_for
    listener, model, submitted, written, events = decode_words(tmp_path,
        ['jarvis open open open open open open open'])
    listener.jobs.put(DecodeJob(1, 0, None, final=True))
    worker = threading.Thread(target=listener._decode, args=(model,))
    worker.start()
    try:
        wait_for(lambda: any(kind == 'warning' for kind, _ in events))
        assert not submitted and not written
    finally:
        listener.stop()
        worker.join(2)
