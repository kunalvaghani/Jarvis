import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from jarvis.runtime_health import RuntimeHealth


class RuntimeHealthTests(unittest.TestCase):
    def app(self):
        worker = SimpleNamespace(thread=Mock())
        worker.thread.is_alive.return_value = True
        return SimpleNamespace(listening_requested=True,
            listener=SimpleNamespace(thread=worker.thread, decoder=worker.thread, last_audio=99),
            actions=SimpleNamespace(thread=worker.thread, knowledge=worker), speech=worker)

    def test_health_reports_capture_and_answer_latency_without_content(self):
        now = [100.0]; health = RuntimeHealth(lambda: now[0])
        health.observe('state', 'Loading Whisper on GPU…')
        health.observe('thinking', 'PRIVATE_PROMPT')
        health.observe('final', 'PRIVATE_RECORDING')
        health.observe('answer_stream', {'phase': 'Generating answer', 'text': 'PRIVATE_ANSWER'})
        now[0] = 102.5
        row = health.snapshot(self.app())
        self.assertEqual(row['answer']['active_seconds'], 2.5)
        self.assertEqual(row['audio']['last_block_age_seconds'], 3.5)
        self.assertTrue(row['audio']['decoder_alive'])
        self.assertNotIn('PRIVATE_', json.dumps(row))
        health.observe('answer', 'PRIVATE_ANSWER')
        self.assertEqual(health.snapshot(self.app())['answer']['last_duration_seconds'], 2.5)
        health.observe('thinking', 'PRIVATE_PROMPT')
        now[0] = 105
        health.observe('answer_stream', {'phase': 'Cancelled · incomplete', 'active': False})
        row = health.snapshot(self.app())
        self.assertIsNone(row['answer']['active_seconds'])
        self.assertEqual(row['answer']['last_duration_seconds'], 2.5)

    def test_unknown_remote_phases_and_errors_never_enter_metadata(self):
        health = RuntimeHealth()
        health.observe('answer_stream', {'phase': 'SECRET_URL', 'text': 'SECRET'})
        health.observe('fatal', 'SECRET_PATH')
        health.observe('answer_error', 'SECRET_KEY')
        row = health.snapshot(self.app())
        self.assertNotIn('SECRET', json.dumps(row))
        self.assertEqual(row['audio']['phase'], 'failed')
        self.assertEqual(row['answer']['phase'], 'failed')

    def test_off_and_unstarted_workers_remain_explicit(self):
        app = self.app(); app.listener = None; app.listening_requested = False
        app.actions.thread.is_alive.return_value = False
        row = RuntimeHealth().snapshot(app)
        self.assertFalse(row['audio']['capture_alive'])
        self.assertIsNone(row['audio']['last_block_age_seconds'])
        self.assertFalse(row['workers']['actions'])
