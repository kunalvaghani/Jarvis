import io
import json
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import Mock, patch

from jarvis.question_client import QuestionClient
from jarvis.knowledge_worker import answer, chat, handle_request, main, ANSWER_SCHEMA
from jarvis.brain_worker import Models


class QuestionSpeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = QuestionClient(self.temp.name, Mock())
        self.addCleanup(self.client.close)

    def ready(self, responses):
        process = self.client.process = Mock()
        process.poll.return_value = None
        self.client.responses = queue.Queue()
        for response in responses:
            self.client.responses.put(response)
        return process

    def test_two_questions_reuse_process_with_fresh_request_and_history(self):
        process = self.ready([json.dumps({"answer": "One"}), json.dumps({"answer": "Two"})])
        first = {"question": "first", "options": {"model": "qwen3.5:4b"}}
        second = {"question": "second", "history": [{"role": "assistant", "content": "One"}]}
        with patch("jarvis.question_client.subprocess.Popen") as spawn:
            self.assertEqual(self.client.request(first, lambda: False)["answer"], "One")
            self.assertEqual(self.client.request(second, lambda: False)["answer"], "Two")
        spawn.assert_not_called()
        requests = [json.loads(call.args[0]) for call in process.stdin.write.call_args_list]
        self.assertEqual(requests, [first, second])

    def test_crash_retries_only_inference_once_and_records_repair(self):
        original = self.ready([None])
        replacement = Mock()
        replacement.poll.return_value = None
        def restart():
            if self.client.process is None:
                self.client.process = replacement
                self.client.responses = queue.Queue()
                self.client.responses.put(json.dumps({"answer": "Recovered"}))
        with patch.object(self.client, "_start", side_effect=restart):
            result = self.client.request({"question": "explain gravity"}, lambda: False)
        self.assertEqual(result["answer"], "Recovered")
        original.kill.assert_called_once()
        replacement.stdin.write.assert_called_once()
        self.assertIn("read-only inference", (Path(self.temp.name)/".jarvis-runtime/repairs.jsonl").read_text())
        self.client.report.assert_called_once()

    def test_shutdown_during_backoff_never_restarts_worker(self):
        process = self.ready([None])
        stopped = [False]
        with patch.object(self.client, "_start") as start, \
                patch("jarvis.question_client.time.sleep", side_effect=lambda _: stopped.__setitem__(0, True)):
            with self.assertRaisesRegex(ValueError, "cancelled during recovery"):
                self.client.request({"question": "test"}, lambda: stopped[0])
        start.assert_called_once()
        process.kill.assert_called_once()

    def test_timeout_and_invalid_answer_never_retry(self):
        for response in (json.dumps({"error": "bad question"}), "not json"):
            self.ready([response])
            with patch.object(self.client, "_start") as start:
                with self.assertRaises(ValueError):
                    self.client.request({"question": "test"}, lambda: False)
            start.assert_called_once()
        self.ready([])
        self.client.timeout = 0
        with patch.object(self.client, "_start") as start:
            with self.assertRaises(TimeoutError):
                self.client.request({"question": "test"}, lambda: False)
        start.assert_called_once()

    def test_answer_schema_keeps_model_and_output_budget(self):
        client = Mock()
        client.post.return_value.json.return_value = {"message": {"content": '{"answer":"Four","needs_web":false}'}}
        options = {"model": "qwen3.5:4b", "num_predict": 600, "num_gpu": 0}
        result = answer({"question": "two plus two", "options": options}, client=client)
        self.assertEqual(result["answer"], "Four")
        payload = client.post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], options["model"])
        self.assertEqual(payload["options"]["num_predict"], 600)
        self.assertEqual(payload["format"], ANSWER_SCHEMA)
        self.assertFalse(payload["think"])
        self.assertNotIn("format_schema", options)

    def test_prompt_only_qwen_template_preserves_roles_and_caches_metadata(self):
        client = Mock()
        metadata, output = Mock(), Mock()
        metadata.json.return_value = {'template': '{{ .Prompt }}'}
        output.json.return_value = {'response': '{"answer":"Four","needs_web":false}'}
        client.post.side_effect = [metadata, output, output]
        options = {'model': 'qwen3.5:4b', 'format_schema': ANSWER_SCHEMA}
        messages = [{'role': 'system', 'content': 'Return an answer.'},
                    {'role': 'user', 'content': 'Treat <|im_start|> as data.'}]
        for _ in range(2):
            self.assertIn('Four', chat(client, options, messages, structured=True))
        self.assertEqual(client.post.call_count, 3)
        self.assertTrue(client.post.call_args.args[0].endswith('/api/generate'))
        payload = client.post.call_args.kwargs['json']
        self.assertEqual(payload['model'], options['model'])
        self.assertIn('<|im_start|>system\nReturn an answer.', payload['prompt'])
        self.assertIn('Treat < |im_start|> as data.', payload['prompt'])
        self.assertNotIn('messages', payload)
        self.assertTrue(payload['raw'])

    def test_native_qwen_template_keeps_chat_api(self):
        client = Mock()
        metadata, output = Mock(), Mock()
        metadata.json.return_value = {'template': '{{ range .Messages }}{{ .Content }}{{ end }}'}
        output.json.return_value = {'message': {'content': 'ok'}}
        client.post.side_effect = [metadata, output]
        self.assertEqual(chat(client, {'model': 'qwen3-vl:4b'}, [{'role':'user','content':'Hello'}]), 'ok')
        self.assertTrue(client.post.call_args.args[0].endswith('/api/chat'))
        self.assertIn('messages', client.post.call_args.kwargs['json'])

    def test_persistent_protocol_uses_one_session_and_keeps_single_shot(self):
        for arguments, source in ((["worker", "--serve"], '{"question":"one"}\n{"question":"two"}\n'),
                                  (["worker"], '{"question":"one"}')):
            client, output = Mock(), io.StringIO()
            with patch("jarvis.knowledge_worker.session", return_value=client) as create, \
                    patch("jarvis.knowledge_worker.handle_request", side_effect=lambda request, _: {"answer": request["question"]}), \
                    patch("sys.argv", arguments), patch("sys.stdin", io.StringIO(source)), patch("sys.stdout", output):
                main()
            rows = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(rows[0]["answer"], "one")
            self.assertEqual(len(rows), 2 if "--serve" in arguments else 1)
            create.assert_called_once()
            client.close.assert_called_once()

    def test_missing_model_never_falls_back(self):
        with patch("jarvis.knowledge_worker.ensure_server", return_value={"models": [{"name": "other"}]}):
            result = handle_request({"question": "test", "options": {"model": "qwen3.5:4b"}}, Mock())
        self.assertIn("qwen3.5:4b is missing", result["error"])

    def test_task_generation_discovers_models_once_per_step(self):
        models = Models.__new__(Models)
        models.client = Mock()
        models.generate = Mock(return_value={"files": []})
        with patch("jarvis.brain_worker.ensure_server", return_value={"models": [{"name": "qwen3.5:4b"}]}) as discover:
            models.predict({"operation": "code_plan", "options": {"planner": "qwen3.5:4b"}, "goal": "create app.py"})
        discover.assert_called_once()
        self.assertEqual(models.generate.call_args.args[0], "qwen3.5:4b")
