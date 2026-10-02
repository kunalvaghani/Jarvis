import io
import json
from types import SimpleNamespace
import unittest
import queue
from unittest.mock import Mock, patch
import numpy as np

from jarvis.kokoro_speech import synthesize, speed, SpeedSession, main
from jarvis.speech import Speech


class NaturalVoiceTests(unittest.TestCase):
    def test_warm_worker_is_reused_without_replaying_speech(self):
        speech = Speech({"engine": "kokoro"}, Mock())
        process = speech.process = Mock()
        speech.responses = queue.Queue()
        process.stdin.write.side_effect = lambda _: speech.responses.put('{"done":true}\n')
        with patch.object(speech, "_ensure_kokoro", return_value=True):
            self.assertTrue(speech._kokoro_reply(0, '{"text":"first"}', "first"))
            self.assertTrue(speech._kokoro_reply(0, '{"text":"second"}', "second"))
        self.assertEqual(process.stdin.write.call_count, 2)
        process.kill.assert_not_called()
        process.poll.return_value = None
        speech.cancel()
        process.kill.assert_called_once()
        with patch.object(speech, "_ensure_kokoro", return_value=False):
            self.assertFalse(speech._kokoro_reply(0, '{"text":"stale"}', "stale"))
        self.assertEqual(process.stdin.write.call_count, 2)

    def test_warm_worker_error_is_not_retried(self):
        speech = Speech({"engine": "kokoro"}, Mock())
        speech.process = Mock()
        speech.responses = queue.Queue()
        speech.responses.put('{"error":"device unavailable"}\n')
        with patch.object(speech, "_ensure_kokoro", return_value=True):
            with self.assertRaisesRegex(ValueError, "device unavailable"):
                speech._kokoro_reply(0, '{"text":"reply"}', "reply")
        speech.process.stdin.write.assert_called_once()

    def voice(self):
        return SimpleNamespace(voices={"af_heart": None}, create=Mock(return_value=(np.ones(100, dtype=np.float32), 24000)))

    def test_whole_reply_preserves_phrase_context(self):
        voice = self.voice()
        synthesize(voice, "Hello sir. How can I help you today?", {"voice": "af_heart"})
        voice.create.assert_called_once_with("Hello sir. How can I help you today?", voice="af_heart", speed=1.0, lang="en-us")

    def test_model_speed_bridge_preserves_fractional_pacing(self):
        native = Mock()
        native.get_inputs.return_value = [SimpleNamespace(name="speed", type="tensor(float)")]
        adapter = SpeedSession(native)
        adapter.pacing = .95
        adapter.run(None, {"speed": np.array([0], dtype=np.int32), "input_ids": [1, 2]})
        feed = native.run.call_args.args[1]
        self.assertEqual(feed["speed"].dtype, np.float32)
        self.assertAlmostEqual(float(feed["speed"][0]), .95)
        self.assertEqual(feed["input_ids"], [1, 2])

    def test_continuous_audio_plays_once_without_added_pauses(self):
        voice = self.voice()
        payload = {"text": "A complete reply. Another sentence.", "model": "m", "voices": "v", "voice": "af_heart"}
        with patch("jarvis.kokoro_speech.load_voice", return_value=voice), patch("sys.stdin", io.StringIO(json.dumps(payload))), patch("sounddevice.play") as playback:
            main()
            playback.assert_called_once()
            self.assertTrue(playback.call_args.kwargs["blocking"])
            self.assertEqual(playback.call_args.args[0].size, 100)

    def test_invalid_voice_and_empty_audio_fail_without_fallback(self):
        voice = self.voice()
        with self.assertRaisesRegex(ValueError, "unavailable"):
            synthesize(voice, "hello", {"voice": "missing"})
        voice.create.return_value = (np.array([], dtype=np.float32), 24000)
        with self.assertRaisesRegex(ValueError, "no audio"):
            synthesize(voice, "hello", {})

    def test_bad_speed_is_bounded(self):
        self.assertEqual(speed(float("nan")), 1)
        self.assertEqual(speed(10), 1.2)
        self.assertEqual(speed("bad"), 1)

