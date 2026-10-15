import unittest
import io
from types import SimpleNamespace
from unittest.mock import Mock, patch
import threading
import tempfile
import wave
from pathlib import Path
import numpy as np
from jarvis.f5_speech import render, number, reference, chunks as split_chunks
from jarvis.speech import Speech


class F5Tests(unittest.TestCase):
    def test_batch_keeps_order_and_preserves_eof(self):
        import queue
        from jarvis.kokoro_speech import queued_batch
        rows = queue.Queue()
        rows.put({'id': 2, 'text': 'continued.', '_epoch': 0})
        rows.put(None)
        merged, batch, held, has_held = queued_batch({'id': 1, 'text': 'First clause,', '_epoch': 0}, rows)
        self.assertEqual(merged['text'], 'First clause, continued.')
        self.assertEqual([row['id'] for row in batch], [1, 2])
        self.assertTrue(has_held)
        self.assertIsNone(held)

    def test_batch_does_not_consume_new_generation_or_oversized_input(self):
        import queue
        from jarvis.kokoro_speech import queued_batch
        for candidate in [{'id': 2, 'text': 'New answer.', '_epoch': 1},
                          {'id': 2, 'text': 'x'*1000, '_epoch': 0}]:
            rows = queue.Queue()
            rows.put(candidate)
            merged, batch, held, has_held = queued_batch({'id': 1, 'text': 'Current.', '_epoch': 0}, rows)
            self.assertEqual(len(batch), 1)
            self.assertIs(held, candidate)
            self.assertTrue(has_held)
    def test_direct_worker_input_cleans_surrogates_before_inference(self):
        voice = SimpleNamespace(jarvis_options={}, infer=Mock(return_value=(np.ones(2400), 24000, None)))
        def infer(**kwargs):
            kwargs['gen_text'].encode('utf-8')
            self.assertEqual(kwargs['gen_text'], 'Gravity pulls objects. More words remain.')
            return np.ones(2400), 24000, None
        voice.infer.side_effect = infer
        with patch('jarvis.f5_speech.reference', return_value=('ref.wav', 'Exact words.', 'neutral')):
            output = list(render(voice, {'text': 'Gravity\udc81 pulls objects. More words remain.'}, threading.Event()))
        self.assertEqual(len(output), 1)

    def setUp(self):
        splitter = patch('jarvis.f5_speech.chunks', side_effect=lambda text, *args: [text])
        splitter.start()
        self.addCleanup(splitter.stop)

    def test_cuda_voice_reserves_gpu_headroom(self):
        import json
        from jarvis.gpu_scheduler import configured, allocation
        config = {'speech': {'engine': 'f5', 'f5': {'device': 'cuda'}}}
        with patch('pathlib.Path.read_text', return_value=json.dumps(config)):
            policy = configured()
        self.assertEqual(policy['speech_reserve_mb'], 2048)
        self.assertEqual(allocation('qwen3.5:9b', 8192, policy, {'total_mb': 4096, 'used_mb': 0}), 5)

    def test_chunks_synthesize_sequentially_with_crossfade(self):
        voice = SimpleNamespace(jarvis_options={}, infer=Mock(return_value=(np.ones(4800), 24000, None)))
        progress = Mock()
        with patch('jarvis.f5_speech.reference', return_value=('ref.wav', 'Exact words.', 'neutral')), patch('jarvis.f5_speech.chunks', return_value=['First.', 'Second.']):
            output = list(render(voice, {'text': 'First. Second.'}, threading.Event(), progress))
        self.assertEqual(voice.infer.call_count, 2)
        self.assertEqual(sum(len(audio) for audio, _ in output), 6000)
        self.assertEqual(progress.call_count, 2)

    def test_first_audio_is_available_before_next_chunk_inference(self):
        voice = SimpleNamespace(jarvis_options={}, infer=Mock(return_value=(np.ones(4800), 24000, None)))
        with patch('jarvis.f5_speech.reference', return_value=('ref.wav', 'Exact words.', 'neutral')), patch('jarvis.f5_speech.chunks', return_value=['First.', 'Second.']):
            output = render(voice, {'text': 'First. Second.'}, threading.Event())
            audio, _ = next(output)
            self.assertTrue(audio.size)
            self.assertEqual(voice.infer.call_count, 1)
            list(output)
            self.assertEqual(voice.infer.call_count, 2)

    def test_reference_duration_and_emotion_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ref.wav'
            with wave.open(str(path), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(b'\0' * 24000 * 2 * 4)
            options = {'reference_audio': str(path), 'reference_text': 'Neutral words.',
                       'references': {'serious': {'reference_audio': str(path), 'reference_text': 'Serious words.'}}}
            self.assertEqual(reference(options, 'Sorry for the delay.')[1:], ('Serious words.', 'serious'))
            options['auto_emotion'] = False
            self.assertEqual(reference(options, 'Sorry for the delay.')[1:], ('Neutral words.', 'neutral'))

    def test_real_chunk_split_preserves_words_and_prefers_punctuation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ref.wav'
            with wave.open(str(path), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(b'\0' * 24000 * 2 * 4)
            text = 'One sentence ends here. Another complete sentence goes here. This is the final line.'
            result = split_chunks(text, path, 'Ten words.', 1.)
            self.assertEqual(' '.join(result), text)
            self.assertTrue(result[0].endswith('.'))
            self.assertGreater(len(result), 1)

    def test_f5_streams_sentences_without_repeating_them(self):
        speech = Speech({'engine': 'f5'}, Mock())
        speech._enqueue = Mock()
        speech.stream('A complete first sentence. Another sentence. ', phase='Conversing')
        speech._enqueue.assert_called_once_with('A complete first sentence.')
        speech.say('A complete first sentence. Another sentence.')
        self.assertEqual(speech._enqueue.call_args.args[0], 'Another sentence.')

    def test_f5_does_not_speak_unverified_research_drafts(self):
        speech = Speech({'engine': 'f5'}, Mock())
        speech._enqueue = Mock()
        speech.stream('A complete speculative draft. More', phase='Generating answer')
        speech._enqueue.assert_not_called()
        speech.stream('The evidence supports this result. More', phase='Generating verified answer')
        speech._enqueue.assert_called_once_with('The evidence supports this result.')

    def test_f5_can_begin_at_a_complete_opening_clause(self):
        speech = Speech({'engine': 'f5'}, Mock())
        speech._enqueue = Mock()
        speech.stream('With the current voice quality settings preserved here, the next words are still arriving', phase='Groq public answer')
        speech._enqueue.assert_called_once_with('With the current voice quality settings preserved here,')

    def test_stop_stream_discards_queued_speech(self):
        speech = Speech({'engine': 'f5'}, Mock())
        speech.stream('A complete first sentence. More', phase='Conversing')
        speech.stream('', active=False, phase='Cancelled · incomplete')
        self.assertTrue(speech.queue.empty())

    def test_f5_uses_isolated_owned_worker(self):
        speech = Speech({'engine': 'f5'}, Mock())
        process = Mock()
        from tests.audit_contract_helpers import ReadyVoiceOutput
        process.stdout = ReadyVoiceOutput()
        process.poll.return_value = None
        with patch('jarvis.speech.subprocess.Popen', return_value=process) as launch:
            self.assertTrue(speech._ensure_kokoro(0))
            argv = launch.call_args.args[0]
            self.assertIn('.venv-f5', argv[0])
            self.assertIn('jarvis.f5_speech', argv)
            speech.closed.set()
            speech._dispose_voice()

    def test_missing_reference_rejected(self):
        with self.assertRaisesRegex(ValueError, 'reference recording'):
            reference({})

    def test_nonfinite_parameters(self):
        self.assertEqual(number({'speed': float('nan')}, 'speed', 1, .85, 1.15), 1)
        self.assertEqual(number({'speed': 9}, 'speed', 1, .85, 1.15), 1.15)

    def test_full_reply_crossfade_without_injected_pauses(self):
        voice = SimpleNamespace(jarvis_options={}, infer=Mock(return_value=(np.ones(2400), 24000, None)))
        with patch('jarvis.f5_speech.reference', return_value=('ref.wav', 'Exact words.', 'serious')):
            result = list(render(voice, {'text': 'Sorry. Let me help.'}, threading.Event()))
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0][0]), 2400)
        self.assertFalse(voice.infer.call_args.kwargs['remove_silence'])
        self.assertEqual(voice.infer.call_args.kwargs['speed'], .97)

    def test_cancel_during_inference_discards_audio(self):
        stop = threading.Event()
        def infer(**kwargs):
            stop.set()
            return np.ones(100), 24000, None
        voice = SimpleNamespace(jarvis_options={}, infer=infer)
        with patch('jarvis.f5_speech.reference', return_value=('ref.wav', 'Exact words.', 'neutral')):
            self.assertEqual(list(render(voice, {'text': 'Hello.'}, stop)), [])

    def test_cancel_preserves_warm_worker_and_close_kills(self):
        speech = Speech({'engine': 'f5'}, Mock())
        speech.process = Mock()
        speech.process.poll.return_value = None
        speech.cancel()
        speech.process.kill.assert_not_called()
        self.assertIn('stop', speech.process.stdin.write.call_args.args[0])
        speech._dispose_voice()

    def test_invalid_generated_audio_fails(self):
        voice = SimpleNamespace(jarvis_options={}, infer=Mock(return_value=(np.array([float('nan')]), 24000, None)))
        with patch('jarvis.f5_speech.reference', return_value=('ref.wav', 'Exact words.', 'neutral')):
            with self.assertRaisesRegex(ValueError, 'invalid audio'):
                list(render(voice, {'text': 'Hello.'}, threading.Event()))


if __name__ == '__main__':
    unittest.main()
