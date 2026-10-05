import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.brain import Brain, BrainClient, validate_plan, normalize_plan, ground_file_scope
from jarvis.brain_worker import Models, SCHEMAS
from jarvis.coder import workspace_coding_request
from jarvis.inference_limits import planning_limits
from jarvis.task_graph import action_budget
from jarvis.task_state import TaskState
from jarvis.task_recovery import action_key
from jarvis.native_tools import plan
from jarvis.step_planning import StepSession
from jarvis.hermes import validate_proposal
from jarvis.harness import validate_harness_proposal
from verify_plan_execution import LENGTHS, fixture, scenario


class PlanExecutionTests(unittest.TestCase):
    def test_ten_full_plans_execute_real_files_in_order_through_twenty_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            for index, length in enumerate(LENGTHS):
                with self.subTest(actions=length):
                    result = fixture(Path(tmp), scenario(index, length))
                    self.assertTrue(result['passed'], result)
                    self.assertEqual(result['completed_actions'], length)

    def test_incremental_twenty_actions_get_final_completion_check_and_no_twenty_first_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = fixture(Path(tmp), scenario(9, 20), incremental=True)
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['completed_actions'], 20)
        self.assertEqual(result['planner_calls'], 21)

    def test_configured_action_budget_and_forward_dependencies(self):
        self.assertEqual(action_budget({}), 20)
        self.assertEqual(action_budget({'max_task_actions': 6}), 6)
        for value in (True, None, 0, 41, '20'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                action_budget({'max_task_actions': value})
        steps = [{'action': 'select', 'value': 'Stage ' + str(i), 'expected': 'Activated',
                  'id': i, 'dep': [i-1] if i else [-1]} for i in range(20)]
        self.assertEqual(validate_plan({'steps': steps}), steps)
        with self.assertRaisesRegex(ValueError, 'budget'):
            validate_plan({'steps': steps}, max_steps=6)
        steps[19]['dep'] = [21]
        with self.assertRaisesRegex(ValueError, 'prerequisite'):
            validate_plan({'steps': steps})

    def test_optional_planner_bridges_allow_twenty_but_keep_remaining_budget(self):
        proposal = {'question': '', 'steps': scenario(9, 20)['steps']}
        request = {'operation': 'plan', 'max_task_actions': 20, 'tools': [{'action': name}
                   for name in ('create_file', 'modify_file', 'read_file')]}
        for validate in (validate_proposal, validate_harness_proposal):
            self.assertEqual(len(validate(proposal, request)['steps']), 20)
            with self.assertRaisesRegex(ValueError, 'budget'):
                validate(proposal, {**request, 'steps_left': 6})

    def test_plain_notes_in_project_folder_do_not_route_to_coder(self):
        self.assertFalse(workspace_coding_request(scenario(8, 15)['goal']))
        self.assertFalse(workspace_coding_request('create notes.txt and modify notes.txt in this folder'))
        self.assertTrue(workspace_coding_request('create tools folder and an alarm.py script'))

    def test_missing_edit_operand_only_copied_from_unique_explicit_user_literal(self):
        step = {'action': 'modify_file', 'value': 'notes.txt', 'content': 'reviewed', 'expected': 'Updated'}
        goal = '1. Modify notes.txt: replace pending with reviewed\n2. Modify notes.txt: replace reviewed with complete'
        self.assertEqual(normalize_plan([step], goal, complete_music=False)[0]['find'], 'pending')
        self.assertNotIn('find', step)
        for ambiguous in (goal + '\n3. Modify notes.txt: replace rejected with reviewed',
                          'Modify different.txt: replace pending with reviewed',
                          'Modify notes.txt: replace pending with other'):
            self.assertNotIn('find', normalize_plan([step], ambiguous)[0])
        self.assertEqual(normalize_plan([{**step, 'find': 'original'}], goal)[0]['find'], 'original')
        self.assertIn('find', SCHEMAS['plan']['properties']['steps']['items']['required'])

    def test_missing_destination_gets_one_read_only_correction_before_dispatch(self):
        actions = Mock()
        brain = Brain(actions, Path('.'), {'max_task_actions': 20})
        brain.client = Mock()
        step = {'action': 'create_file', 'value': 'notes.txt', 'folder': '', 'content': 'pending', 'expected': 'Created'}
        corrected = {'steps': [{**step, 'folder': 'this folder'}]}
        brain.client.request.side_effect = [{'steps': [step]}, corrected]
        self.assertEqual(brain.planning_request('plan', lambda: False, goal='Create notes.txt containing pending in this folder'), corrected)
        self.assertIn('plan_validation_error', brain.client.request.call_args.kwargs)
        actions.execute.assert_not_called()
        brain.client.request.side_effect = None
        brain.client.request.return_value = {'steps': [step]}
        brain.client.request.reset_mock()
        result = brain.planning_request('plan', lambda: False, goal='Create notes.txt')
        self.assertEqual(brain.client.request.call_count, 2)
        with self.assertRaisesRegex(ValueError, 'explicit folder'):
            validate_plan(result)
        actions.execute.assert_not_called()

    def test_stop_during_read_only_correction_prevents_second_request(self):
        actions = Mock()
        brain = Brain(actions, Path('.'), {})
        brain.client = Mock()
        stopped = [False]
        def inference(*args, **kwargs):
            stopped[0] = True
            return {'steps': [{'action': 'create_file', 'folder': ''}]}
        brain.client.request.side_effect = inference
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            brain.planning_request('plan', lambda: stopped[0], goal='Create notes.txt')
        self.assertEqual(brain.client.request.call_count, 1)
        actions.execute.assert_not_called()

    def test_file_read_scope_omission_gets_same_bounded_correction(self):
        actions = Mock()
        brain = Brain(actions, Path('.'), {})
        brain.client = Mock()
        step = {'action': 'read_file', 'value': 'notes.txt', 'folder': '', 'expected': 'Read notes'}
        brain.client.request.side_effect = [{'steps': [step]}, {'steps': [{**step, 'folder': 'this folder'}]}]
        result = brain.planning_request('plan', lambda: False, goal='Read notes.txt in this folder')
        self.assertEqual(result['steps'][0]['folder'], 'this folder')
        self.assertEqual(brain.client.request.call_count, 2)
        actions.execute.assert_not_called()

    def test_unused_read_content_does_not_change_action_identity_or_bypass_repeat_guard(self):
        read = {'action': 'read_file', 'value': 'notes.txt', 'folder': 'this folder', 'content': ''}
        self.assertEqual(action_key(read), action_key({**read, 'content': 'pending'}))
        self.assertNotEqual(action_key(read), action_key({**read, 'folder': 'Downloads'}))
        append = {**read, 'action': 'append_file', 'content': 'one'}
        self.assertNotEqual(action_key(append), action_key({**append, 'content': 'two'}))

    def test_missing_file_scope_inherits_only_explicit_single_destination_literal_list(self):
        case = scenario(9, 20)
        raw = {'steps': [{**step, 'folder': ''} for step in case['steps']]}
        fixed = ground_file_scope(raw, case['goal'])
        self.assertTrue(all(step['folder'] == 'this folder' for step in fixed['steps']))
        self.assertTrue(all(step['folder'] == '' for step in raw['steps']))
        for goal in (case['goal'].replace('in this folder', 'in Documents and this folder'),
                     case['goal'].replace('Read audit7.txt', 'Read audit7.txt in Downloads'),
                     case['goal'] + '\n21. Open Notepad',
                     case['goal'].replace('in this folder', 'in this folder and another directory')):
            self.assertEqual(ground_file_scope(raw, goal), raw)
        for header in ('Work in this folder and Downloads:', 'Work from Documents in this folder:'):
            self.assertEqual(ground_file_scope(raw, header + '\n' + '\n'.join(case['goal'].splitlines()[1:])), raw)
        mixed = {'steps': [{**raw['steps'][0], 'folder': 'Downloads'},
                            {**raw['steps'][0], 'value': 'unnamed.txt'}]}
        self.assertEqual(ground_file_scope(mixed, case['goal']), mixed)

    def test_uncertain_eighth_file_action_is_not_replayed_or_followed_by_ninth(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = fixture(Path(tmp), scenario(9, 20), fault_after=8)
            self.assertEqual(result['state_status'], 'paused', result)
            self.assertEqual(result['completed_actions'], 7)
            self.assertEqual(result['dispatched_actions'], 8)
            self.assertEqual(result['remaining_actions'], 13)
            self.assertTrue(result['failures'][-1]['attempted'])
            self.assertIn('uncertain', result['resume_blocker'])
            self.assertEqual((Path(tmp) / 'audit/audit3.txt').read_text(), 'reviewed')

    def test_stop_after_seventh_verified_action_retains_thirteen_and_sends_no_eighth(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = fixture(Path(tmp), scenario(9, 20), cancel_after=7)
        self.assertEqual(result['state_status'], 'cancelled', result)
        self.assertEqual(result['completed_actions'], 7)
        self.assertEqual(result['dispatched_actions'], 7)
        self.assertEqual(result['remaining_actions'], 13)

    def test_terminal_planner_cannot_dispatch_twenty_first_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = fixture(Path(tmp), scenario(9, 20), incremental=True, extra_at_limit=True)
        self.assertEqual(result['state_status'], 'paused', result)
        self.assertEqual(result['completed_actions'], 20)
        self.assertEqual(result['dispatched_actions'], 20)

    def test_long_goal_retains_exact_tail_and_does_not_resume_a_different_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = TaskState(tmp)
            goal = 'Read the notes in this folder.\n' * 80 + 'Read final.txt'
            state.start(goal, 'task')
            self.assertEqual(state.snapshot()['goal'], goal)
            state.finish('paused', 'Inspect remaining steps')
            state.start(goal, 'task')
            self.assertEqual(state.previous(goal, 'task')['status'], 'paused')
            self.assertIsNone(state.previous(goal + ' not-final.txt', 'task'))

    def test_checkpoint_retains_all_twenty_completed_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = TaskState(tmp)
            state.start('twenty steps', 'task')
            completed = [{'action': 'select', 'value': str(i), 'id': i, 'verified': True} for i in range(20)]
            state.update_plan([], completed)
            reloaded = TaskState(tmp, read_only=True)
            self.assertEqual(reloaded.snapshot()['plan']['completed'], completed)

    def test_native_prompt_keeps_all_completion_identities_with_only_six_detailed_results(self):
        client = Mock()
        client.post.return_value.json.return_value = {'message': {'tool_calls': [
            {'function': {'name': 'jarvis_finish', 'arguments': {'reason': 'All stages verified'}}}]}}
        completed = [{'action': 'select', 'value': 'Stage ' + str(i), 'expected': 'Activated',
                      'id': i, 'verified': True, 'result': 'Observed'} for i in range(20)]
        plan(client, 'qwen3.5:9b', 'Select stages', {'tools': [{'action': 'select'}], 'completed': completed})
        messages = client.post.call_args.kwargs['json']['messages']
        context = json.loads(messages[-1]['content'])
        self.assertEqual([step['id'] for step in context['completed']], list(range(20)))
        self.assertEqual(len([row for row in messages if row['role'] == 'tool']), 6)

    def test_background_prompt_scaffold_keeps_real_completed_count_after_six_actions(self):
        session = StepSession()
        try:
            completed = [{'action': 'select', 'value': str(i)} for i in range(19)]
            session.prepare('Finish twenty stages', completed, {'action': 'select', 'value': '20'}, [], [])
            self.assertEqual(session.consume()['completed_count'], 19)
        finally:
            session.close()

    def test_long_plan_generation_streams_activity_and_preserves_optional_dependency_metadata(self):
        model = Models()
        model.coding_options = {'timeout_seconds': 300}
        with patch('jarvis.brain_worker.chat', return_value='{"question":"","steps":[]}') as chat:
            model.generate('qwen3.5:9b', 'Fixture plan', {}, 'plan')
        settings = chat.call_args.args[1]
        self.assertTrue(settings['stream'])
        self.assertTrue(callable(settings['on_activity']))
        self.assertEqual(settings['num_predict'], 4000)
        self.assertEqual(SCHEMAS['next_step']['properties']['steps']['maxItems'], 1)
        self.assertIn('id', SCHEMAS['plan']['properties']['steps']['items']['properties'])

    def test_streamed_planning_progress_renews_silence_budget_with_total_limit(self):
        for total, error in ((300, False), (90, True)):
            client = BrainClient(Path('.'), {'timeout_seconds': 5, 'max_planning_seconds': total})
            client.timeout_seconds = 35
            client.process = SimpleNamespace(poll=lambda: None, stdin=Mock())
            client.close = Mock()
            client.responses = queue.Queue()
            for event in ({'inference_activity': 'Thinking'}, {'inference_activity': 'Generating answer'}, {'result': {'steps': []}}):
                client.responses.put(json.dumps(event))
            clock = iter([0, 0, 30, 30, 60, 60, 95])
            with patch('jarvis.brain.time.monotonic', side_effect=lambda: next(clock)):
                if error:
                    with self.assertRaisesRegex(ValueError, 'timed out'):
                        client._request_once('plan', lambda: False)
                else:
                    self.assertEqual(client._request_once('plan', lambda: False), {'steps': []})
        self.assertEqual(planning_limits({'timeout_seconds': 300}), (300, 900))


if __name__ == '__main__':
    unittest.main()
