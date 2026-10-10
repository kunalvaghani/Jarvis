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
    def test_replies_queue_into_one_warm_worker_and_stop_keeps_the_model(self):
        speech = Speech({"engine": "kokoro"}, Mock())
        process = speech.process = Mock()
        process.poll.return_value = None
        with patch.object(speech, "_ensure_kokoro", return_value=True):
            self.assertTrue(speech._kokoro_send(0, {"text": "first"}, "first"))
            self.assertTrue(speech._kokoro_send(0, {"text": "second"}, "second"))  # No waiting in between.
        sent = [json.loads(call.args[0]) for call in process.stdin.write.call_args_list]
        self.assertEqual([row["id"] for row in sent], [1, 2])
        self.assertTrue(speech.speaking.is_set())
        speech._event('{"id": 1, "done": true}')
        self.assertTrue(speech.speaking.is_set())  # The second reply is still playing.
        speech._event('{"id": 2, "done": true}')
        self.assertFalse(speech.speaking.is_set())
        speech._kokoro_send(0, {"text": "third"}, "third") if False else None
        with patch.object(speech, "_ensure_kokoro", return_value=True):
            speech._kokoro_send(0, {"text": "third"}, "third")
        speech.cancel()
        self.assertEqual(json.loads(process.stdin.write.call_args.args[0]), {"stop": True})
        process.kill.assert_not_called()  # The 325 MB model is not reloaded after barge-in.
        self.assertFalse(speech.outstanding)
        with patch.object(speech, "_ensure_kokoro", return_value=False):
            self.assertFalse(speech._kokoro_send(0, {"text": "stale"}, "stale"))

    def test_worker_error_is_reported_and_not_retried(self):
        report = Mock()
        speech = Speech({"engine": "kokoro"}, report)
        speech.process = Mock()
        with patch.object(speech, "_ensure_kokoro", return_value=True):
            speech._kokoro_send(0, {"text": "reply"}, "reply")
        speech._event('{"id": 1, "error": "device unavailable"}')
        report.assert_called_once()
        self.assertIn("device unavailable", report.call_args.args[1])
        speech.process.stdin.write.assert_called_once()
        self.assertFalse(speech.speaking.is_set())

    def test_long_answers_are_never_cut_and_paragraphs_survive(self):
        from jarvis.speech import spoken_text
        long = " ".join("Sentence number %d is here." % i for i in range(400))
        self.assertEqual(spoken_text(long), long)  # Previously cut at 2,500 characters.
        self.assertEqual(spoken_text("One.\n\nTwo."), "One.\n\nTwo.")

    def test_answer_spoken_while_written_is_not_repeated(self):
        speech = Speech({"engine": "kokoro"}, Mock())
        speech.stream("Paris is the capital of France. It sits on the Seine")
        speech.stream("Paris is the capital of France. It sits on the Seine. It is famous for art")
        speech.say("Paris is the capital of France. It sits on the Seine. It is famous for art and food.")
        spoken = [speech.queue.get_nowait()[1] for _ in range(speech.queue.qsize())]
        self.assertEqual(spoken[0], "Paris is the capital of France.")  # Spoken before the answer finished.
        # Everything is spoken exactly once (short sentences may be joined to avoid choppy fragments).
        self.assertEqual(" ".join(spoken), "Paris is the capital of France. It sits on the Seine. It is famous for art and food.")

    def test_replaced_draft_stops_and_final_answer_is_spoken_in_full(self):
        speech = Speech({"engine": "kokoro"}, Mock())
        speech.stream("A first draft sentence here. More")
        speech.stream("")  # The preview was cleared (for example, verifying online).
        speech.say("The verified answer. With sources.")
        spoken = [speech.queue.get_nowait()[1] for _ in range(speech.queue.qsize())]
        self.assertEqual(spoken, ["The verified answer. With sources."])

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
            synthesize(voice, "hello", {"voice": "af_heart"})

    def test_bad_speed_is_bounded(self):
        self.assertEqual(speed(float("nan")), 1)
        self.assertEqual(speed(10), 1.2)
        self.assertEqual(speed("bad"), 1)



class NaturalDeliveryTests(unittest.TestCase):
    def test_plan_pauses_breaths_and_emotion(self):
        import random
        from jarvis.natural_voice import plan
        text = ("Oh nice, that worked! Here is the thing about long builds, which is that they always seem slow. "
                "I am sorry the tests failed though, it happens more often than anyone would like.\n\nWhat next?")
        rows = plan(text, 1.0, random.Random(4))
        self.assertGreater(rows[0].speed, 1.0)  # Excited.
        sorry = next(row for row in rows if "sorry" in row.text)
        self.assertLess(sorry.speed, 1.0)  # Sympathetic, slower.
        self.assertGreaterEqual(sorry.pause_after, .7)  # Paragraph break.
        self.assertTrue(all(.85 <= row.speed <= 1.2 for row in rows))
        self.assertGreaterEqual(rows[-1].pause_after, .42)  # A question gets a longer pause.

    def test_breaths_are_occasional_soft_and_finite(self):
        import random
        from jarvis.natural_voice import plan, breath
        text = " ".join("This sentence has quite a few words in it so a breath may come before it." for _ in range(12))
        rows = plan(text, 1.0, random.Random(2))
        count = sum(row.breath_before for row in rows)
        self.assertTrue(0 < count < len(rows))
        self.assertFalse(any(row.breath_before for row in plan(text, 1.0, random.Random(2), breaths=False)))
        audio = breath(24000, random.Random(1))
        self.assertTrue(np.isfinite(audio).all())
        self.assertLess(float(np.sqrt(np.mean(audio ** 2))), .02)

    def test_voice_blend_and_text_cleanup(self):
        from jarvis.natural_voice import voice_style, tts_text, language_for
        voice = SimpleNamespace(voices={"am_michael": 1, "am_fenrir": 1},
                                get_voice_style=lambda name: np.full(4, 1.0 if name == "am_michael" else 3.0))
        mixed = voice_style(voice, "am_michael:60,am_fenrir:40")
        self.assertTrue(np.allclose(mixed, 1.8))
        self.assertEqual(voice_style(voice, "am_michael"), "am_michael")
        with self.assertRaises(ValueError):
            voice_style(voice, "missing:50,am_michael:50")
        self.assertEqual(language_for("bm_george"), "en-gb")
        self.assertEqual(tts_text("lol that was **funny** 😀 e.g. this"), "ha ha! that was funny for example this")

    def test_player_streams_pieces_gaplessly_and_reports_progress(self):
        import queue as queue_module
        from jarvis import kokoro_speech
        events = queue_module.Queue()
        player = kokoro_speech.Player.__new__(kokoro_speech.Player)
        player.np, player.rate, player.events = np, 10, events
        player.pieces, player.lock, player.current = __import__("collections").deque(), __import__("threading").Lock(), None
        player.add(1, np.ones(3, np.float32))
        player.add(1, np.full(3, 2, np.float32))
        player.finish(1, .6)
        out = np.zeros((8, 1), np.float32)
        player.callback(out, 8, None, None)
        self.assertEqual(out[:, 0].tolist(), [1, 1, 1, 2, 2, 2, 0, 0])  # No gap between pieces.
        rows = [events.get_nowait() for _ in range(events.qsize())]
        self.assertEqual(rows, [{"id": 1, "started": True}, {"id": 1, "done": True, "audio_seconds": .6}])
        player.add(2, np.ones(5, np.float32))
        player.clear()
        player.callback(out, 8, None, None)
        self.assertEqual(out[:, 0].tolist(), [0] * 8)  # Stop clears queued audio at once.
