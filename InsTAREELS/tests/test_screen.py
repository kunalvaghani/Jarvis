import unittest
from unittest.mock import Mock
from unittest.mock import patch
import json
import threading
import subprocess
import sys
import base64
import io

from jarvis.knowledge import Knowledge, wants_screen
from jarvis.knowledge_worker import answer_from_screen


class ScreenTests(unittest.TestCase):
    def test_optional_ocr_failure_preserves_image_for_vision(self):
        from PIL import Image
        from jarvis.screen_worker import capture
        for error in (subprocess.TimeoutExpired("tesseract", 12), OSError("OCR unavailable")):
            with self.subTest(error=error), patch("jarvis.screen_worker.choose_window", return_value=0), \
                 patch("PIL.ImageGrab.grab", return_value=Image.new("RGB", (320, 200), "blue")), \
                 patch("jarvis.screen_worker.shutil.which", return_value=sys.executable), \
                 patch("jarvis.screen_worker.subprocess.run", side_effect=error):
                screen = capture()
                self.assertEqual(screen["ocr"], "")
                self.assertEqual(Image.open(io.BytesIO(base64.b64decode(screen["image"]))).size, (320, 200))

    def test_screen_questions_in_english_hinglish_and_hindi(self):
        self.assertTrue(wants_screen("What is happening on my screen?"))
        self.assertTrue(wants_screen("Screen pe kya dikh raha hai?"))
        self.assertTrue(wants_screen("What does this error mean?"))
        self.assertTrue(wants_screen("स्क्रीन पर क्या है?"))
        self.assertFalse(wants_screen("Why is the sky blue?"))

    def test_question_keeps_external_window_handle(self):
        worker = Knowledge({}, lambda *args: None)
        worker.screen_handle = lambda: 1234
        worker.submit("What is this?")
        _, _, _, use_screen, handle, _ = worker.queue.get_nowait()
        self.assertTrue(use_screen)
        self.assertEqual(handle, 1234)

    def test_vision_request_uses_local_model_and_image(self):
        response = Mock()
        response.json.return_value = {"message": {"content": "A blue dialog."}}
        client = Mock()
        client.post.return_value = response
        screen = {"title": "Test", "ocr": "blue dialog", "image": "aGVsbG8="}
        result = answer_from_screen(client, {"screen_model": "qwen3-vl:4b"},
                                    "What is this?", [], screen, "Be concise.")
        self.assertEqual(result["answer"], "A blue dialog.")
        url, = client.post.call_args.args
        self.assertEqual(url, "http://127.0.0.1:11434/api/chat")
        payload = client.post.call_args.kwargs["json"]
        self.assertEqual(payload["messages"][-1]["images"], ["aGVsbG8="])
        self.assertEqual(payload["options"]["num_gpu"], 0)

    def test_screen_snapshot_reaches_question_worker(self):
        received = []
        answered = threading.Event()
        events = []
        class Process:
            returncode = 0
            def __init__(self, module):
                self.module = module
            def communicate(self, input=None, **_kwargs):
                received.append((self.module, json.loads(input)))
                if self.module == "jarvis.screen_worker":
                    return json.dumps({"title": "Test", "image": "aGVsbG8=", "ocr": "Hello"}), ""
                return json.dumps({"answer": "Hello is visible."}), ""
            def poll(self):
                return 0
        def report(kind, value):
            events.append(kind)
            if kind == "answer":
                answered.set()
        worker = Knowledge({}, report)
        worker.screen_handle = lambda: 4321
        def infer(request, cancelled):
            received.append(("jarvis.knowledge_worker", request))
            return {"answer": "Hello is visible."}
        with patch("jarvis.knowledge.subprocess.Popen", side_effect=lambda command, **_kw: Process(command[2])), \
                patch("jarvis.knowledge.time.sleep"), patch.object(worker.client, "request", side_effect=infer):
            worker.start()
            try:
                worker.submit("What is this?")
                self.assertTrue(answered.wait(2))
            finally:
                worker.close()
                worker.thread.join(2)
        self.assertIn("screen_capture", events)
        self.assertIn("screen_capture_done", events)
        self.assertLess(events.index("screen_capture"), events.index("screen_capture_done"))
        self.assertEqual(received[0][1]["handle"], 4321)
        self.assertEqual(received[1][1]["screen"]["image"], "aGVsbG8=")


if __name__ == "__main__":
    unittest.main()
