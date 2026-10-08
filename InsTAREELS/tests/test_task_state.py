import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.task_state import TaskState


class TaskStateTests(unittest.TestCase):
    def test_known_failed_checkpoint_commit_retries_without_rewriting_task(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            replace = os.replace
            denied = PermissionError('sharing violation'); denied.winerror = 32
            calls = []
            def commit(source, target):
                calls.append(source)
                if len(calls) < 3:
                    raise denied
                replace(source, target)
            with patch('jarvis.task_state.os.replace', side_effect=commit), patch('jarvis.task_state.time.sleep'):
                state.start('One task only', 'task')
            self.assertEqual(len(set(calls)), 1)
            self.assertEqual(json.loads(state.path.read_text())['current']['goal'], 'One task only')
            self.assertEqual(state.data['history'], [])

    def test_failed_checkpoint_preserves_pending_file_and_never_overwrites_other_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start('Original', 'task')
            denied = PermissionError('access denied'); denied.winerror = 5
            def competing_writer(source, target):
                target.write_text('Other writer', encoding='utf-8')
                raise denied
            with patch('jarvis.task_state.os.replace', side_effect=competing_writer) as replace:
                with self.assertRaises(PermissionError):
                    state.checkpoint('next')
            self.assertEqual(replace.call_count, 1)
            self.assertEqual(state.path.read_text(), 'Other writer')
            pending = list(Path(directory).glob('.jarvis-task-*'))
            self.assertEqual(len(pending), 1)
            self.assertEqual(json.loads(pending[0].read_text())['current']['stage'], 'next')

    def test_unclassified_commit_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            with patch('jarvis.task_state.os.replace', side_effect=PermissionError('unknown')) as replace:
                with self.assertRaises(PermissionError): state.start('Task', 'task')
            self.assertEqual(replace.call_count, 1)
            self.assertEqual(len(list(Path(directory).glob('.jarvis-task-*'))), 1)

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing-violation fixture')
    def test_actual_windows_reader_lock_releases_before_checkpoint_commit_deadline(self):
        import ctypes
        from ctypes import wintypes
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory); state.start('Locked checkpoint fixture', 'task')
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                          ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            kernel.CreateFileW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.CreateFileW(str(state.path), 0x80000000, 3, None, 3, 0, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            def release():
                time.sleep(.12)
                kernel.CloseHandle(handle)
            reader = threading.Thread(target=release); reader.start()
            try:
                state.checkpoint('confirmed')
                self.assertEqual(json.loads(state.path.read_text())['current']['stage'], 'confirmed')
            finally:
                reader.join()

    def test_completed_task_emits_spoken_reply_and_keeps_action_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            events = []
            actions = Actions({"files_root": "files", "apps": {}}, directory, lambda *args: events.append(args))
            actions.brain.run = lambda goal, cancelled: "Finished. Your request is complete."
            try:
                actions.start()
                actions.submit(Command("task", "open calculator"))
                actions.queue.join()
                self.assertIn(("spoken_reply", "Finished. Your request is complete."), events)
                self.assertIn(("action", "Finished. Your request is complete."), events)
            finally:
                actions.close()

    def test_plan_revisions_survive_restart_as_context_not_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start("open two apps", "task")
            remaining = [{"action": "open", "value": "calculator"}]
            done = [{"action": "open", "value": "chrome", "verified": True}]
            state.update_plan(remaining, done, "Chrome verified")
            remaining.clear()
            restarted = TaskState(directory)
            self.assertEqual(restarted.snapshot()["status"], "interrupted")
            self.assertEqual(restarted.snapshot()["plan"]["remaining"][0]["value"], "calculator")
            restarted.start("open two apps", "task")
            self.assertEqual(restarted.previous("open two apps", "task")["plan"]["completed"], done)

    def test_restart_marks_unfinished_task_and_preserves_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start("Create a calculator", "task")
            state.checkpoint("created_draft", target="calculator.py")
            restarted = TaskState(directory)
            current = restarted.snapshot()
            self.assertEqual(current["status"], "interrupted")
            self.assertEqual(current["checkpoints"][0]["target"], "calculator.py")
            restarted.start("Add a UI", "task")
            restarted.finish("completed", "UI added")
            self.assertEqual(restarted.snapshot()["status"], "completed")
            saved = json.loads((Path(directory) / "task_state.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["history"][0]["status"], "interrupted")

    def test_previous_context_only_for_same_unfinished_goal(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start("Open the second video", "task")
            state.checkpoint("verified", action="open", target="YouTube", screen="Chrome")
            state.finish("paused", "The next result was ambiguous")
            state.start("Open the second video", "task")
            prior = state.previous("Open the second video", "task")
            self.assertEqual(prior["checkpoints"][0]["screen"], "Chrome")
            self.assertIsNone(state.previous("A different goal", "task"))

    def test_action_task_records_failure_and_success(self):
        with tempfile.TemporaryDirectory() as directory:
            actions = Actions({"files_root": "files", "apps": {}}, directory, lambda *args: None)
            actions.brain.run = lambda goal, cancelled: "Finished the plan"
            self.assertEqual(actions.execute(Command("task", "open calculator")), "Finished the plan")
            self.assertEqual(actions.task_state.snapshot()["status"], "completed")
            def fail(goal, cancelled):
                raise ValueError("Planner failed")
            actions.brain.run = fail
            with self.assertRaisesRegex(ValueError, "Planner failed"):
                actions.execute(Command("task", "open calculator"))
            current = actions.task_state.snapshot()
            self.assertEqual(current["status"], "failed")
            self.assertEqual(current["result"], "Planner failed")
            def pause(goal, cancelled):
                raise ValueError("Task paused after the last verified action: replanner stopped")
            actions.brain.run = pause
            with self.assertRaisesRegex(ValueError, "Task paused"):
                actions.execute(Command("task", "open calculator"))
            self.assertEqual(actions.task_state.snapshot()["status"], "paused")
            actions.close()


if __name__ == "__main__":
    unittest.main()
