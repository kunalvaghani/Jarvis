import threading
import unittest
from types import SimpleNamespace

from jarvis.audio import DecodeJob, DecodeQueue, Listener, TranscriptAssembler, command_text
from jarvis.commands import Command
from jarvis.engine import Engine


class WhisperTests(unittest.TestCase):
    def test_punctuation_preserves_filenames_and_negations(self):
        self.assertEqual(command_text("Hey Jarvis, create a file called notes.txt."), "hey jarvis create a file called notes.txt")
        self.assertEqual(command_text("Hey Jarvis, create a file called Notes. Text."), "hey jarvis create a file called notes.text")
        self.assertEqual(command_text("Jarvis, don’t delete file notes.txt!"), "jarvis don't delete file notes.txt")

    def test_formatted_whisper_sentence_executes_correct_commands(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.feed(command_text("Hey Jarvis, open Notepad, then create a file called notes.txt."), final=True)
        self.assertEqual(sent, [Command("open", "notepad"), Command("create", "notes.txt")])

    def test_queue_coalesces_only_superseded_partial_hypotheses(self):
        jobs = DecodeQueue()
        jobs.put(DecodeJob(1, 0, "old"))
        jobs.put(DecodeJob(1, 0, "new"))
        jobs.put(DecodeJob(1, 0, "final", final=True))
        jobs.put(DecodeJob(2, 0, "next"))
        self.assertEqual(jobs.get().audio, "final")
        self.assertEqual(jobs.get().audio, "next")

    def test_rollovers_are_not_dropped(self):
        jobs = DecodeQueue()
        jobs.put(DecodeJob(1, 0, "boundary", rollover=True))
        jobs.put(DecodeJob(1, 16, "next"))
        self.assertTrue(jobs.get().rollover)

    def test_queue_overload_stops_instead_of_losing_final_commands(self):
        jobs = DecodeQueue(limit=1)
        jobs.put(DecodeJob(1, 0, "final", final=True))
        with self.assertRaises(RuntimeError):
            jobs.put(DecodeJob(2, 0, "next", final=True))

    def test_rolling_audio_preserves_transcript_without_overlap_duplicates(self):
        assembler = TranscriptAssembler()
        first = assembler.merge(DecodeJob(1, 0, None, rollover=True), [(1, "Jarvis"), (17, "write"), (19, "hello")])
        self.assertEqual(first, "Jarvis write hello")
        second = assembler.merge(DecodeJob(1, 16, None), [(1, "write"), (3, "hello"), (4, "world")])
        self.assertEqual(second, "Jarvis write hello world")
        self.assertEqual(assembler.merge(DecodeJob(2, 0, None), [(1, "new")]), "new")

    def test_decoder_consumes_generator_and_filters_low_confidence(self):
        events, sent = [], []
        engine = Engine(sent.append, lambda *args: None)
        listener = Listener("unused", None, engine, lambda *args: events.append(args))
        done = threading.Event()
        class Model:
            def transcribe(self, audio, **kwargs):
                def segments():
                    yield SimpleNamespace(no_speech_prob=0.9, avg_logprob=-2, words=[SimpleNamespace(end=1, word="delete file notes")])
                    yield SimpleNamespace(no_speech_prob=0.01, avg_logprob=-0.1, words=[SimpleNamespace(end=2, word="Hey Jarvis, open Notepad.")])
                    done.set()
                return segments(), None
        listener.jobs.put(DecodeJob(1, 0, None, final=True))
        worker = threading.Thread(target=listener._decode, args=(Model(),))
        worker.start()
        self.assertTrue(done.wait(2))
        # Stop after the completed result has been delivered, not mid-generator.
        import time
        deadline = time.monotonic() + 2
        while not sent and time.monotonic() < deadline:
            time.sleep(0.01)
        listener.stop()
        worker.join(2)
        self.assertEqual(sent, [Command("open", "notepad")])

    def test_cancellation_during_inference_discards_result(self):
        sent = []
        listener = Listener("unused", None, Engine(sent.append, lambda *args: None), lambda *args: None)
        class Model:
            def transcribe(self, audio, **kwargs):
                listener.stop()
                return iter([SimpleNamespace(no_speech_prob=0, avg_logprob=0,
                    words=[SimpleNamespace(end=1, word="Jarvis delete file notes")])]), None
        listener.jobs.put(DecodeJob(1, 0, None, final=True))
        listener._decode(Model())
        self.assertEqual(sent, [])

    def test_high_no_speech_score_does_not_discard_confident_words(self):
        sent = []
        listener = Listener("unused", None, Engine(sent.append, lambda *args: None), lambda *args: None)
        class RunningModel:
            def transcribe(self, audio, **kwargs):
                return iter([SimpleNamespace(no_speech_prob=0.9, avg_logprob=-0.1,
                    words=[SimpleNamespace(end=1, word="Jarvis open Notepad")])]), None
        listener.jobs.put(DecodeJob(1, 0, None, final=True))
        worker = threading.Thread(target=listener._decode, args=(RunningModel(),))
        worker.start()
        import time
        deadline = time.monotonic() + 2
        while not sent and time.monotonic() < deadline:
            time.sleep(.01)
        listener.stop()
        worker.join(2)
        self.assertEqual(sent, [Command("open", "notepad")])

    def test_assistant_playback_is_not_routed_as_a_command(self):
        sent = []
        listener = Listener("unused", None, Engine(sent.append, lambda *args: None),
                            lambda *args: None, muted=lambda: True)
        decoded = threading.Event()
        class Model:
            def transcribe(self, audio, **kwargs):
                def segments():
                    yield SimpleNamespace(no_speech_prob=0, avg_logprob=0,
                        words=[SimpleNamespace(end=1, word="Jarvis open Notepad")])
                    decoded.set()
                return segments(), None
        listener.jobs.put(DecodeJob(1, 0, None, final=True))
        worker = threading.Thread(target=listener._decode, args=(Model(),))
        worker.start()
        self.assertTrue(decoded.wait(2))
        import time
        time.sleep(.05)
        listener.stop()
        worker.join(2)
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
