import json
from pathlib import Path
import socket
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.audio import DecodeJob, Listener
from jarvis.command_cleanup import CommandCleanup, allowed_edit, propose, settings
from jarvis.commands import Command
from jarvis.engine import Engine
from jarvis.model_selection import required_models
from jarvis.model_recovery import ModelRecovery


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(Mock(), Mock())
        self.engine.activate()
        self.events = Mock()
        self.request = Mock(side_effect=lambda text, alternative, *_: alternative)
        self.clock = [100.0]
        self.cleanup = CommandCleanup({"enabled": True}, self.events, self.request, lambda: self.clock[0])

    def test_known_spacing_hesitation_and_typo_edits(self):
        for source, target in (("hey jarvis um open note pad", "hey jarvis open notepad"),
                               ("jarvis opne calculator", "jarvis open calculator"),
                               ("please launch spot ify", "please launch spotify"),
                               ("open you tube", "open youtube"),
                               ("uh what is gravity", "what is gravity")):
            with self.subTest(source=source):
                self.assertEqual(self.cleanup.clean(source, self.engine), target)

    def test_clear_commands_have_no_inference_cost(self):
        self.assertEqual(self.cleanup.clean("open chrome", self.engine), "open chrome")
        self.request.assert_not_called()

    def test_protected_content_is_exact_and_never_sent_to_model(self):
        for text in ("um write um open note pad", "um send Maya 25 dollars", "um open C:\\Notes.txt",
                     "um search for you tube", "um don't open chrome", "um open chrome then close spotify",
                     "um run echo hello", "um delete file notes", "um set volume to 37", "um type hello",
                     "um open chrome without spotify", 'um open "Note Pad"', "um create file notes.txt",
                     "um stop listening", "um cancel", "um go to sleep"):
            # Search words are literal content; no alias substitutions there.
            if text == "um search for you tube":
                self.assertEqual(allowed_edit(text), "search for you tube")
                continue
            with self.subTest(text=text):
                self.assertEqual(self.cleanup.clean(text, self.engine), text)
        self.request.assert_not_called()

    def test_no_new_actions_or_changed_targets_are_accepted(self):
        for candidate in ("open chrome", "open notepad then delete files", "open notepad 2", "open notepad please",
                          "launch notepad", {"text": "open notepad"}, None):
            self.request.side_effect = None
            self.request.return_value = candidate
            with self.subTest(candidate=candidate):
                self.assertEqual(self.cleanup.clean("open note pad", self.engine), "open note pad")

    def test_original_choice_is_respected(self):
        self.request.side_effect = lambda text, *_: text
        self.assertEqual(self.cleanup.clean("open note pad", self.engine), "open note pad")

    def test_disabled_and_overlong_bypass(self):
        self.cleanup.options["enabled"] = False
        self.cleanup.clean("open note pad", self.engine)
        self.cleanup.options["enabled"] = True
        self.cleanup.clean("um " + "word " * 100, self.engine)
        self.request.assert_not_called()

    def test_committed_or_dictation_state_never_rewrites(self):
        for field, value in (("done", {0: "open chrome"}), ("suppressed", True)):
            old = getattr(self.engine, field)
            setattr(self.engine, field, value)
            self.assertEqual(self.cleanup.clean("open note pad", self.engine), "open note pad")
            setattr(self.engine, field, old)
        self.request.assert_not_called()

    def test_sleeping_engine_requires_existing_wake_word(self):
        self.engine.active = False
        self.cleanup.clean("um open note pad", self.engine)
        self.request.assert_not_called()
        self.assertEqual(self.cleanup.clean("jarvis um open note pad", self.engine), "jarvis open notepad")

    def test_timeout_falls_back_and_backoff_recovers_without_replay(self):
        self.request.side_effect = TimeoutError()
        self.assertEqual(self.cleanup.clean("open note pad", self.engine), "open note pad")
        self.clock[0] = 129
        self.cleanup.clean("open note pad", self.engine)
        self.assertEqual(self.request.call_count, 1)
        self.clock[0] = 131
        self.request.side_effect = lambda text, alternative, *_: alternative
        self.assertEqual(self.cleanup.clean("open note pad", self.engine), "open notepad")
        self.assertEqual(self.request.call_count, 2)
        self.engine.submit.assert_not_called()

    def test_cancellation_prevents_requests_and_post_inference_edits(self):
        self.cleanup.clean("open note pad", self.engine, lambda: True)
        self.request.assert_not_called()
        stopped = [False]
        def stop(*args):
            stopped[0] = True
            return "open notepad"
        self.request.side_effect = stop
        self.assertEqual(self.cleanup.clean("open note pad", self.engine, lambda: stopped[0]), "open note pad")
        self.events.assert_not_called()

    def test_invalid_settings_fail_preflight(self):
        for value in ([], {"enabled": "yes"}, {"model": ""}, {"timeout_seconds": 60},
                      {"timeout_seconds": float("nan")}, {"backoff_seconds": 0}, {"max_characters": True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                settings(value)

    def test_model_is_declared_only_when_enabled(self):
        self.assertEqual(required_models({"command_cleanup": {"enabled": True}}), {"qwen2.5:0.5b"})
        self.assertEqual(required_models({"command_cleanup": {"enabled": False}}), set())

    def test_existing_model_recovery_identifies_cleanup_model(self):
        recovery = ModelRecovery(Path.cwd(), {"command_cleanup": {"enabled": True}}, Mock(), lambda: False)
        recovery.client = Mock()
        recovery.client.get.return_value.json.return_value = {"models": []}
        self.assertFalse(recovery.healthy())
        self.assertEqual(recovery.missing, ["qwen2.5:0.5b"])
        recovery.closing = lambda: True
        self.assertFalse(recovery.repair())


class CleanupTransportTests(unittest.TestCase):
    def setUp(self):
        # These checks isolate HTTP framing/deadlines. GPU admission has its own
        # process/fault suite and must not consume this transport's fake clock.
        disabled=patch('jarvis.gpu_scheduler.configured',return_value={'enabled':False})
        disabled.start();self.addCleanup(disabled.stop)

    def connection(self, events):
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 200
        wire = b"".join(json.dumps(event).encode() + b"\n" for event in events)
        response.read.side_effect = [bytes([byte]) for byte in wire] + [b""]
        return connection

    def test_stream_assembles_json_and_closes_owned_connection(self):
        conn = self.connection([{"message": {"content": '{"choice":"'}},
                                {"message": {"content": 'cleaned"}'}, "done": True}])
        with patch("jarvis.command_cleanup.http.client.HTTPConnection", return_value=conn):
            self.assertEqual(propose("open note pad", "open notepad", settings()), "open notepad")
        payload = json.loads(conn.request.call_args.kwargs["body"])
        self.assertNotIn("tools", payload)
        self.assertEqual(payload["options"]["num_gpu"], 0)
        conn.close.assert_called_once()

    def test_timeout_closes_connection_and_does_not_retry(self):
        conn = self.connection([])
        conn.getresponse.side_effect = socket.timeout()
        with patch("jarvis.command_cleanup.http.client.HTTPConnection", return_value=conn), self.assertRaises(socket.timeout):
            propose("open note pad", "open notepad", settings())
        conn.request.assert_called_once()
        conn.close.assert_called_once()

    def test_eof_malformed_model_failure_and_invalid_shape_raise(self):
        for events in ([], [{"error": "model missing"}], [{"message": {"content": '[]'}, "done": True}],
                       [{"message": {"content": '{"text":"x","action":"delete"}'}, "done": True}]):
            conn = self.connection(events)
            with self.subTest(events=events), patch("jarvis.command_cleanup.http.client.HTTPConnection", return_value=conn), self.assertRaises(ValueError):
                propose("open note pad", "open notepad", settings())
            conn.close.assert_called_once()

    def test_deadline_and_cancel_close_request(self):
        conn = self.connection([])
        with patch("jarvis.command_cleanup.http.client.HTTPConnection", return_value=conn), patch(
                "jarvis.command_cleanup.time.monotonic", side_effect=[0, .1, 3]), self.assertRaises(TimeoutError):
            propose("open note pad", "open notepad", settings())
        conn.close.assert_called_once()
        conn = self.connection([])
        with patch("jarvis.command_cleanup.http.client.HTTPConnection", return_value=conn):
            self.assertEqual(propose("open note pad", "open notepad", settings(), lambda: True), "open note pad")
        conn.connect.assert_not_called()
        conn.close.assert_called_once()


class CleanupListenerTests(unittest.TestCase):
    def run_decode(self, cleanup, final=True, gate=None):
        sent, events = [], []
        engine = Engine(sent.append, lambda *args: None)
        listener = Listener("unused", None, engine, lambda *args: events.append(args),
                            input_filter=gate, command_cleanup=cleanup)
        class Model:
            def transcribe(self, *_args, **_kwargs):
                return iter([SimpleNamespace(avg_logprob=0, words=[SimpleNamespace(
                    end=1, word="Jarvis open note pad")])]), None
        listener.jobs.put(DecodeJob(1, 0, None, final=final))
        thread = threading.Thread(target=listener._decode, args=(Model(),))
        thread.start()
        deadline = time.monotonic()+2
        while not events and time.monotonic() < deadline:
            time.sleep(.005)
        return listener, thread, sent, events

    def finish(self, listener, thread):
        listener.stop()
        thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_final_cleanup_feeds_engine_and_keeps_raw_transcript(self):
        cleanup = CommandCleanup({"enabled": True}, request=lambda text, alternative, *_: alternative)
        listener, thread, sent, events = self.run_decode(cleanup)
        deadline = time.monotonic()+2
        while not sent and time.monotonic() < deadline:
            time.sleep(.005)
        self.finish(listener, thread)
        self.assertEqual(sent, [Command("open", "notepad")])
        self.assertIn(("final", "Jarvis open note pad"), events)

    def test_partial_never_calls_cleanup(self):
        cleanup = Mock()
        listener, thread, sent, events = self.run_decode(cleanup, final=False)
        self.finish(listener, thread)
        cleanup.clean.assert_not_called()

    def test_echo_gate_rejects_before_cleanup(self):
        cleanup = Mock()
        listener, thread, sent, events = self.run_decode(cleanup, gate=lambda *_: None)
        self.finish(listener, thread)
        cleanup.clean.assert_not_called()
        self.assertEqual(sent, [])

    def test_stop_during_cleanup_does_not_submit_action(self):
        entered, release = threading.Event(), threading.Event()
        def request(text, alternative, *_):
            entered.set()
            release.wait(2)
            return alternative
        cleanup = CommandCleanup({"enabled": True}, request=request)
        listener, thread, sent, events = self.run_decode(cleanup)
        self.assertTrue(entered.wait(2))
        listener.stop()
        release.set()
        self.finish(listener, thread)
        self.assertEqual(sent, [])

    def test_failed_cleanup_keeps_microphone_and_original_routing(self):
        cleanup = CommandCleanup({"enabled": True}, request=Mock(side_effect=ValueError("bad JSON")))
        listener, thread, sent, events = self.run_decode(cleanup)
        deadline = time.monotonic()+2
        while not sent and time.monotonic() < deadline:
            time.sleep(.005)
        self.assertFalse(listener.stop_event.is_set())
        self.finish(listener, thread)
        self.assertEqual(sent, [Command("open", "note pad")])
        self.assertFalse(any(kind == "fatal" for kind, _ in events))


if __name__ == "__main__":
    unittest.main()
