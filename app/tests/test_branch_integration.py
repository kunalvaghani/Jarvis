"""Regression coverage for features reconciled during branch consolidation."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from jarvis.natural_voice import tts_text
from jarvis.repo_abilities import memory_refusal
from jarvis.speech import Speech, spoken_text


@pytest.mark.parametrize(('text', 'expected'), [
    ('It costs $12.50.', 'twelve dollars and fifty cents'),
    ('Charge is 25%.', 'twenty-five percent'),
    ('x²', 'squared'),
    ('Open report.pdf', 'report dot pdf'),
])
def test_merged_voice_normalization(text, expected):
    assert expected in tts_text(text)


def test_traceback_and_table_are_spoken_without_frames_or_markup():
    text = ('Traceback (most recent call last):\n'
            '  File "private.py", line 2, in run\n'
            '    raise ValueError("bad input")\n'
            'ValueError: bad input\n'
            '| Item | State |\n| --- | --- |\n| Voice | Ready |')
    cleaned = spoken_text(text)
    assert 'Value Error' in cleaned and 'bad input' in cleaned
    assert 'Voice, Ready.' in cleaned
    assert 'private.py' not in cleaned and '|' not in cleaned


@pytest.mark.parametrize('confirmed', [False, True])
def test_f5_fallback_requires_worker_confirmation(confirmed):
    speech = Speech({'engine': 'f5'}, Mock())
    speech.process = Mock()
    speech.worker_engine = 'f5'
    with patch.object(speech, '_ensure_kokoro', return_value=True):
        speech._kokoro_send(0, {'text': 'Reply.'}, 'Reply.')
    import json
    speech._event(json.dumps({'id': 1, 'error': 'fixture failure', 'safe_to_retry': confirmed}))
    assert speech.queue.qsize() == int(confirmed)
    assert not speech.outstanding


def test_audio_progress_prevents_replay_even_with_retry_flag():
    speech = Speech({'engine': 'f5'}, Mock())
    speech.process = Mock()
    speech.worker_engine = 'f5'
    with patch.object(speech, '_ensure_kokoro', return_value=True):
        speech._kokoro_send(0, {'text': 'Reply.'}, 'Reply.')
    speech._event('{"id":1,"started":true}')
    speech._event('{"id":1,"error":"fixture failure","safe_to_retry":true}')
    assert speech.queue.empty()


def test_memory_fallback_detection_checks_http_body_without_reclassifying_other_failures():
    error = RuntimeError('HTTP 500')
    error.response = SimpleNamespace(text='model requires more system memory')
    assert memory_refusal(error)
    assert not memory_refusal(RuntimeError('connection refused'))
