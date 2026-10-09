import unittest
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np

from jarvis.commands import Command, parse
from jarvis.speech import Speech, speech_language, spoken_text, speech_parameters, playback_timeout
from jarvis.piper_speech import play_reply


class SpeechTests(unittest.TestCase):
    def test_hinglish_and_hindi_questions_route_to_answers(self):
        self.assertEqual(parse("mujhe batao gravity kya hai"),
                         Command("ask", "mujhe batao gravity kya hai"))
        self.assertEqual(parse("पानी क्यों उबलता है"),
                         Command("ask", "पानी क्यों उबलता है"))

    def test_source_links_are_not_read_aloud(self):
        answer = "यह पानी है [1].\n\nSources:\n[1] Example — https://example.com"
        self.assertEqual(spoken_text(answer), "यह पानी है.")

    def test_voice_follows_script_or_explicit_preference(self):
        self.assertEqual(speech_language("पानी उबलता है"), "hi")
        self.assertEqual(speech_language("Water boils"), "en")
        self.assertEqual(speech_language("Pani kyun ubalta hai"), "hi")
        self.assertEqual(speech_language("Water boils", "hi"), "hi")

    def test_formatting_preserves_link_words_and_sentence_pauses(self):
        self.assertEqual(spoken_text("## Result\n**Ready.**\n- Read [the guide](https://example.com).\n- Use `my_function`."),
                         "Result. Ready. Read the guide. Use my_function.")
        self.assertEqual(spoken_text("Here it is.\n```python\nprint('secret')\n```"),
                         "Here it is. The code is in the transcript.")

    def test_parameters_and_long_answer_timeout_are_bounded(self):
        values = speech_parameters({"length_scale": 99, "noise_scale": "bad", "sentence_silence": float("nan")})
        self.assertEqual(values["length_scale"], 1.5)
        self.assertEqual(values["noise_scale"], .667)
        self.assertEqual(values["sentence_silence"], .18)
        self.assertEqual(playback_timeout("Hi."), 60)
        self.assertEqual(playback_timeout("word " * 1000), 240)

    def test_sentence_audio_starts_before_second_sentence_is_synthesized(self):
        stream = Mock()
        audio = Mock()
        audio.OutputStream.return_value = stream
        voice = Mock()
        chunk = SimpleNamespace(sample_rate=1000, sample_channels=1, audio_float_array=np.ones(100, dtype=np.float32))
        def chunks(*args):
            yield chunk
            self.assertEqual(stream.write.call_count, 1)
            yield chunk
        voice.synthesize.side_effect = chunks
        play_reply(voice, "First. Second.", {"sentence_silence": .2}, audio, np)
        self.assertEqual(stream.write.call_count, 3)
        self.assertEqual(stream.write.call_args_list[1].args[0].shape, (200, 1))
        stream.stop.assert_called_once()
        stream.close.assert_called_once()

    def test_audio_failure_closes_stream_without_retrying(self):
        stream = Mock()
        stream.write.side_effect = OSError("device unavailable")
        audio = Mock()
        audio.OutputStream.return_value = stream
        chunk = SimpleNamespace(sample_rate=1000, sample_channels=1, audio_float_array=np.ones(10, dtype=np.float32))
        voice = Mock()
        voice.synthesize.return_value = iter([chunk])
        with self.assertRaises(OSError):
            play_reply(voice, "Hi.", {}, audio, np)
        voice.synthesize.assert_called_once()
        stream.close.assert_called_once()

    def worker(self):
        events = []
        speech = Speech({"enabled": True}, lambda *args: events.append(args))
        self.addCleanup(speech.close)
        return speech, events

    def test_cancelled_queue_and_shutdown_do_not_launch_voice(self):
        speech, _ = self.worker()
        speech.say("Queued reply")
        speech.cancel()
        with patch("jarvis.speech.subprocess.Popen") as launch:
            speech.start()
            speech.queue.join()
            speech.close()
            speech.say("After shutdown")
            launch.assert_not_called()
        self.assertTrue(speech.queue.empty())

    def test_cancel_during_model_check_cannot_restart_stopped_speech(self):
        speech, _ = self.worker()
        def stop_before_launch(path):
            speech.cancel()
            return True
        with patch.object(Path, "is_file", stop_before_launch), patch("jarvis.speech.subprocess.Popen") as launch:
            speech.say("Hello.")
            speech.start()
            speech.queue.join()
            launch.assert_not_called()

    def test_stalled_voice_is_killed_once_and_not_replayed(self):
        speech, events = self.worker()
        process = Mock()
        process.communicate.side_effect = [subprocess.TimeoutExpired("voice", 60), ("", "")]
        process.poll.return_value = 1
        with patch.object(Path, "is_file", return_value=True), patch("jarvis.speech.subprocess.Popen", return_value=process) as launch:
            speech.say("Hello.")
            speech.start()
            speech.queue.join()
            launch.assert_called_once()
            process.kill.assert_called_once()
        self.assertTrue(any(kind == "repair" for kind, _ in events))
        self.assertFalse(speech.speaking.is_set())

    def test_close_kills_only_owned_voice_and_prevents_future_queueing(self):
        speech, _ = self.worker()
        process = Mock()
        process.poll.return_value = None
        speech.process = process
        speech.close()
        process.kill.assert_called_once()
        speech.say("Do not speak after quit")
        self.assertTrue(speech.queue.empty())


if __name__ == "__main__":
    unittest.main()
