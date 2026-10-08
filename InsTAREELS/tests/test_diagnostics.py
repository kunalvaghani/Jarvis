from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from jarvis.diagnostics import service_status


class DiagnosticsTests(unittest.TestCase):
    def check(self, client, required=None, config=None):
        with patch('jarvis.knowledge_worker.session', return_value=client), \
                patch('jarvis.model_selection.required_models', return_value=required or {'qwen3.5:9b'}):
            return service_status(config or {}, Path('.'))

    def test_missing_model_is_reported_without_starting_or_repairing_server(self):
        client = Mock()
        client.get.return_value.json.return_value = {'models': [{'name': 'qwen3.5:9b'}]}
        result = self.check(client, {'qwen3.5:9b', 'qwen3.5:0.8b'})
        self.assertEqual(result['ollama']['status'], 'missing')
        self.assertEqual(result['ollama']['missing_models'], ['qwen3.5:0.8b'])
        client.get.assert_called_once_with('http://127.0.0.1:11434/api/tags', timeout=(3, 5))
        client.post.assert_not_called()
        client.close.assert_called_once()

    def test_connection_failure_is_unavailable_and_error_text_is_not_published(self):
        client = Mock()
        client.get.side_effect = TimeoutError('private credential URL')
        result = self.check(client)
        self.assertEqual(result['ollama']['status'], 'unavailable')
        self.assertEqual(result['ollama']['error_type'], 'TimeoutError')
        self.assertNotIn('private', str(result))
        client.post.assert_not_called()
        client.close.assert_called_once()

    def test_invalid_inventory_cannot_report_ready(self):
        for payload in ({}, [], {'models': None}, {'models': ['bad']}, {'models': [{'name': 3}]}):
            with self.subTest(payload=payload):
                client = Mock()
                client.get.return_value.json.return_value = payload
                self.assertEqual(self.check(client)['ollama']['status'], 'unavailable')

    def test_no_model_features_does_not_connect(self):
        client = Mock()
        with patch('jarvis.knowledge_worker.session', return_value=client), \
                patch('jarvis.model_selection.required_models', return_value=set()):
            result = service_status({}, Path('.'))
        self.assertEqual(result['ollama']['status'], 'disabled')
        client.get.assert_not_called()

    def test_localgithub_uses_local_git_without_hosted_controller_or_credentials(self):
        client = Mock()
        client.get.return_value.json.return_value = {'models': [{'name': 'qwen3.5:9b'}]}
        git = Mock()
        config = {'brain': {'enabled': True, 'coding_backend': 'codex', 'codex_workload_enabled': True}}
        with patch('jarvis.codex_workload.localgithub', return_value=(Mock(), git, Path('LocalGithub'))):
            result = self.check(client, config=config)
        self.assertEqual(result['localgithub']['status'], 'available')
        self.assertFalse(result['localgithub']['hosted_services_checked'])
        git.command.assert_called_once_with(Path('.'), '--version', timeout=10)

    def test_missing_localgithub_and_git_failure_cannot_report_ready(self):
        client = Mock()
        client.get.return_value.json.return_value = {'models': [{'name': 'qwen3.5:9b'}]}
        config = {'brain': {'enabled': True, 'coding_backend': 'codex', 'codex_workload_enabled': True}}
        with patch('jarvis.codex_workload.localgithub', side_effect=FileNotFoundError('private path')):
            result = self.check(client, config=config)
        self.assertEqual(result['localgithub']['status'], 'unavailable')
        self.assertNotIn('private', str(result))


class UIVerificationIsolationTests(unittest.TestCase):
    def test_verifier_entrypoint_does_not_publish_an_inherited_supervisor_heartbeat(self):
        import os
        import subprocess
        import sys
        import uuid
        from pathlib import Path
        base=Path(__file__).resolve().parents[1]
        session='ui-verify-test-'+uuid.uuid4().hex
        heartbeat=base/'.jarvis-runtime'/('heartbeat-'+session+'.json')
        env={**os.environ,'JARVIS_SESSION_ID':session,'JARVIS_AUTOLISTEN':'1',
             'JARVIS_RESUME_TASK':'1','JARVIS_SUPERVISED':'1'}
        result=subprocess.run([sys.executable,str(base/'verify_ui.py')],cwd=base,env=env,
                              capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('without starting microphone',result.stdout)
        self.assertFalse(heartbeat.exists())

    def test_verification_ignores_inherited_runtime_flags_and_preserves_user_state(self):
        import tkinter as tk
        import gc
        import main
        paths = [main.BASE/name for name in ('config.json', 'task_state.json',
                  '.jarvis-runtime/stop', '.jarvis-runtime/repairs.jsonl')]
        before = {path: path.read_bytes() if path.exists() else None for path in paths}
        root = tk.Tk()
        root.withdraw()
        app = None
        try:
            with patch.dict('os.environ', {'JARVIS_UI_VERIFY': '1', 'JARVIS_AUTOLISTEN': '1',
                    'JARVIS_RESUME_TASK': '1', 'JARVIS_SUPERVISED': '1'}), \
                    patch('main.Watchdog.start') as start:
                app = main.App(root)
                root.after(800, root.quit)
                root.mainloop()
                self.assertIsNone(app.listener)
                self.assertEqual(app.actions.generation, 0)
                self.assertIsNone(app.model_recovery.thread)
                start.assert_not_called()
                app.close()
                app = None
            self.assertEqual(before, {path: path.read_bytes() if path.exists() else None for path in paths})
        finally:
            if app is not None:
                app.close()
            try:
                root.destroy()
            except tk.TclError:
                pass
            app = root = None
            gc.collect()


if __name__ == '__main__':
    unittest.main()
