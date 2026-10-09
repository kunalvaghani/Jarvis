"""Exact direct requests through the real scoped file and approval tools."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jarvis.actions import Actions
from jarvis.commands import Command


class DirectFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.actions = Actions({'files_root': 'files', 'apps': {}, '_ui_verification': True,
            'memory': {'enabled': False}, 'agent_runtime': {'direct_execution': True}},
            self.folder, Mock())
        self.addCleanup(self.actions.close)
        self.actions._task_folder = Mock(return_value=self.folder)
        self.actions.brain.run = Mock(side_effect=AssertionError('No inference for exact file grammar'))

    def run_task(self, goal):
        return self.actions.execute(Command('task', goal), lambda: False)

    def test_create_and_modify_preserve_unicode_without_inference(self):
        result = self.run_task('create file hello.txt in fixture containing café हिन्दी')
        path = self.folder / 'hello.txt'
        self.assertEqual(path.read_text(encoding='utf-8'), 'café हिन्दी')
        self.assertIn('without model calls', result)
        self.assertEqual(self.actions.task_state.snapshot()['stage'], 'goal_verified')
        self.run_task('modify file hello.txt in fixture: replace café with bonjour')
        self.assertEqual(path.read_text(encoding='utf-8'), 'bonjour हिन्दी')
        self.actions.brain.run.assert_not_called()

    def test_existing_create_is_not_overwritten_or_replayed(self):
        path = self.folder / 'hello.txt'
        path.write_text('existing', encoding='utf-8')
        with self.assertRaises((ValueError, FileExistsError)):
            self.run_task('create file hello.txt in fixture containing replacement')
        self.assertEqual(path.read_text(encoding='utf-8'), 'existing')
        self.actions.brain.run.assert_not_called()

    def test_ambiguous_replacement_issues_no_write(self):
        path = self.folder / 'hello.txt'
        path.write_text('cat cat', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'occur once'):
            self.run_task('modify file hello.txt in fixture: replace cat with dog')
        self.assertEqual(path.read_text(encoding='utf-8'), 'cat cat')
        self.actions.brain.run.assert_not_called()

    def test_delete_keeps_existing_approval_gate(self):
        path = self.folder / 'hello.txt'
        path.write_text('keep me', encoding='utf-8')
        self.actions.approval_handler = Mock(return_value=False)
        self.actions.recycler = Mock()
        with self.assertRaisesRegex(ValueError, 'approval was not given'):
            self.run_task('delete file hello.txt in fixture')
        self.actions.approval_handler.assert_called_once()
        self.actions.recycler.assert_not_called()
        self.assertTrue(path.exists())
        self.actions.brain.run.assert_not_called()

    def test_command_denial_launches_no_process(self):
        self.actions.approval_handler = Mock(return_value=False)
        with patch('jarvis.actions.subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'approval was not given'):
                self.run_task('run command echo fixture')
        launch.assert_not_called()
        self.actions.brain.run.assert_not_called()

    def test_tool_scope_still_blocks_exact_direct_request(self):
        self.actions.allowed_tools = {'select'}
        with self.assertRaisesRegex(ValueError, 'outside the current task scope'):
            self.run_task('create file hello.txt in fixture containing text')
        self.assertFalse((self.folder / 'hello.txt').exists())

    def test_write_exception_does_not_replay_or_call_planner(self):
        path = self.folder / 'hello.txt'
        def partial(folder, name, content, cancelled):
            path.write_text(content, encoding='utf-8')
            raise OSError('response lost after write')
        with patch('jarvis.desktop_tasks.write_new_file', side_effect=partial) as write:
            with self.assertRaisesRegex(OSError, 'response lost'):
                self.run_task('create file hello.txt in fixture containing written once')
        write.assert_called_once()
        self.assertEqual(path.read_text(encoding='utf-8'), 'written once')
        self.actions.brain.run.assert_not_called()
        self.assertIsNotNone(self.actions.task_state.resume_blocker(self.actions.task_state.snapshot()))


if __name__ == '__main__':
    unittest.main()
