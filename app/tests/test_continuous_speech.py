"""Speech stays one continuous reply: gaps between sentences are still part of the answer (2026-10-20).

Before, `output_recent` was false whenever no sentence was being synthesized or played, for example while the
next sentence was still rendering or being written. Room noise or the speaker's own tail heard in that gap was
accepted as a command without the wake word, and every new command cancels the remaining speech.
"""
import time
from unittest.mock import Mock

from jarvis.speech import Speech
from jarvis.voice_input import VoiceInput


def speech():
    voice = Speech({'engine': 'kokoro', 'enabled': True}, Mock())
    voice.cancel = Mock(wraps=voice.cancel)
    return voice


def test_idle_voice_does_not_protect_the_microphone():
    assert speech().output_recent() is False


def test_queued_next_sentence_keeps_the_reply_protected():
    voice = speech()
    voice.queue.put_nowait((voice.generation, 'And here is the second sentence.'))
    assert voice.output_recent() is True


def test_sentence_still_synthesizing_keeps_the_reply_protected():
    voice = speech()
    voice.outstanding[1] = voice.generation
    assert voice.output_recent() is True


def test_answer_still_being_written_keeps_the_reply_protected_then_expires():
    voice = speech()
    voice.stream('Playing Finding Her on Spotify now and', active=True)
    assert voice.queue.empty()  # no complete sentence yet: protection comes from the stream window
    assert voice.output_recent() is True
    voice.stream_until = time.monotonic() - 0.1
    assert voice.output_recent() is False


def test_gap_noise_without_wake_word_does_not_cancel_the_reply():
    voice = speech()
    voice.queue.put_nowait((voice.generation, 'The rest of the answer.'))
    assert VoiceInput(voice).filter('hmm okay') is None
    voice.cancel.assert_not_called()
    assert not voice.queue.empty()


def test_wake_word_still_interrupts_mid_reply():
    voice = speech()
    voice.queue.put_nowait((voice.generation, 'The rest of the answer.'))
    assert VoiceInput(voice).filter('jarvis stop') == 'jarvis stop'
    assert voice.queue.empty()  # interrupted on request


def test_cancel_clears_the_stream_window():
    voice = speech()
    voice.stream('First sentence of an answer is here', active=True)
    voice.cancel()
    assert voice.output_recent() is False
