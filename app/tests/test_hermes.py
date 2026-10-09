from pathlib import Path
import tempfile
import json
from urllib.request import Request, urlopen
import unittest
from unittest.mock import Mock, patch

from jarvis.brain import BrainClient
from jarvis.hermes import HermesClient, readiness, validate_proposal
from jarvis.hermes_ollama import completion, start_provider


class HermesTests(unittest.TestCase):
    def test_owned_provider_supports_sdk_streaming_and_closes_socket(self):
        with patch("jarvis.knowledge_worker.chat", return_value='{"question":"","steps":[]}'):
            server, endpoint = start_provider({}, "local", 10, "rules")
            port = server.server_port
            try:
                request = Request(endpoint + "/chat/completions", data=json.dumps({"stream": True,
                    "messages": [{"role": "user", "content": "task"}]}).encode(), headers={"Content-Type": "application/json"})
                with urlopen(request, timeout=3) as response:
                    body = response.read().decode()
                    self.assertIn("submit_jarvis_plan", body)
                    self.assertIn("[DONE]", body)
            finally:
                server.shutdown()
                server.server_close()
            import socket
            with socket.socket() as probe:
                self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)

    def test_native_provider_uses_runtime_inference_and_tool_correction_history(self):
        generate = Mock(return_value='{"question":"","steps":[]}')
        schema = {"type": "object"}
        result = completion({"messages": [{"role": "system", "content": "upstream identity"},
            {"role": "user", "content": "task context"},
            {"role": "tool", "content": "invalid proposal; revise"}]}, schema, "qwen", 30, Mock(), generate, "Jarvis rules. ")
        options, messages = generate.call_args.args[1:]
        self.assertEqual(options["model"], "qwen")
        self.assertEqual(options["format_schema"], schema)
        self.assertEqual(options["num_gpu"], 0)
        self.assertNotIn("upstream identity", str(messages))
        self.assertIn("invalid proposal; revise", str(messages))
        self.assertEqual(result["choices"][0]["message"]["tool_calls"][0]["function"]["name"], "submit_jarvis_plan")

    def test_native_provider_rejects_non_object_runtime_output(self):
        with self.assertRaisesRegex(ValueError, "invalid proposal object"):
            completion({}, {}, "qwen", 30, Mock(), Mock(return_value="[]"), "")

    def request(self, operation="plan", **extra):
        return {"operation": operation, "tools": [{"action": "open"}], **extra}

    def plan(self, **extra):
        return {"question": "", "steps": [{"action": "open", "value": "calculator",
            "expected": "Calculator window visible"}], **extra}

    def test_rejects_tool_outside_current_catalogue(self):
        proposal = self.plan()
        proposal["steps"][0]["action"] = "run_command"
        with self.assertRaisesRegex(ValueError, "unavailable"):
            validate_proposal(proposal, self.request())

    def test_preserves_desktop_execution_gate(self):
        proposal = self.plan()
        proposal["steps"][0]["value"] = "powershell delete files"
        with self.assertRaisesRegex(ValueError, "explicit direct command"):
            validate_proposal(proposal, self.request())

    def test_replan_completion_cannot_include_action(self):
        with self.assertRaisesRegex(ValueError, "remaining work"):
            validate_proposal(self.plan(done=True, reason="done"), self.request("replan"))

    def test_replan_honors_remaining_budget(self):
        with self.assertRaisesRegex(ValueError, "remaining task budget"):
            validate_proposal(self.plan(done=False, reason="continue"), self.request("replan", steps_left=0))

    def test_invalid_completion_types_rejected(self):
        with self.assertRaisesRegex(ValueError, "status"):
            validate_proposal({"question": "", "steps": [], "done": "true", "reason": "done"}, self.request("replan"))

    def test_empty_success_assessment_allowed_for_independent_verification(self):
        proposal = {"question": "", "steps": [], "done": True, "reason": "Fresh observation confirms goal"}
        self.assertEqual(validate_proposal(proposal, self.request("replan")), proposal)

    def test_empty_non_completion_rejected(self):
        with self.assertRaisesRegex(ValueError, "no plan"):
            validate_proposal({"question": "", "steps": []}, self.request())

    def test_clarification_passes_without_action(self):
        self.assertEqual(validate_proposal({"question": "Which app?", "steps": []}, self.request())["steps"], [])

    def test_cannot_mix_clarification_and_steps(self):
        with self.assertRaisesRegex(ValueError, "either steps"):
            validate_proposal(self.plan(question="Open Calculator"), self.request())

    def test_only_planning_routes_to_hermes_with_memory(self):
        client = BrainClient(Path.cwd(), {"hermes": {"enabled": True}})
        client.memory = Mock()
        client.memory.task_context.return_value = {"name": "Kunal"}
        worker = Mock()
        with patch("jarvis.hermes.HermesClient", return_value=worker), patch.object(client, "_request_once", return_value={"verified": True}) as ordinary:
            client.request("plan", lambda: False, goal="open calculator")
            self.assertEqual(worker.request.call_args.kwargs["memory_context"], {"name": "Kunal"})
            client.request("verify", lambda: False, goal="open calculator")
            ordinary.assert_called_once()
            client.close()
            worker.close.assert_called_once()

    def test_cancelled_request_does_not_launch_worker(self):
        client = HermesClient(Path.cwd(), {})
        with patch("jarvis.brain.subprocess.Popen") as launch:
            with self.assertRaisesRegex(ValueError, "cancelled"):
                client.request("plan", lambda: True, tools=[])
            launch.assert_not_called()

    def test_missing_install_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn("launchers/Setup Jarvis Hermes.cmd", readiness(directory))
            client = HermesClient(directory, {})
            with self.assertRaisesRegex(ValueError, "runtime missing"):
                client.request("plan", lambda: False, tools=[])

    def test_transport_result_is_validated_again(self):
        client = HermesClient(Path.cwd(), {})
        with patch.object(BrainClient, "_request_once", return_value=self.plan()):
            self.assertEqual(client.request("plan", lambda: False, tools=[{"action": "open"}])["backend"], "hermes")
            with self.assertRaisesRegex(ValueError, "unavailable"):
                client.request("plan", lambda: False, tools=[{"action": "browse"}])

    def test_worker_loss_retries_inference_only_once(self):
        client = HermesClient(Path.cwd(), {})
        with patch.object(client, "_request_once", side_effect=[OSError("lost"), OSError("lost")]) as infer, patch.object(client, "close") as close, patch("jarvis.recovery.record"):
            with self.assertRaises(OSError):
                client.request("plan", lambda: False, tools=[])
            self.assertEqual(infer.call_count, 2)
            close.assert_called_once()
