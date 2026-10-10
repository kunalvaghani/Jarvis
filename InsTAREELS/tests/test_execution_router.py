import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.execution_adapters import Prepared, PRIORITY, Unsupported, WindowsMCP, CUA
from jarvis.execution_router import execute, UncertainAction
from jarvis.direct_execution import compile_steps, run
from jarvis.task_state import TaskState


class Clock:
    value = 0.0
    def __call__(self):
        return self.value
    def sleep(self, amount):
        self.value += amount


class RoutingTests(unittest.TestCase):
    def route(self, providers, operation='activate', **kwargs):
        timer = Clock()
        request = {'operation': operation, 'content': 'exact', 'value': 'down'}
        control = {'name': 'Search', 'role': 'Edit' if operation == 'fill_text' else 'Button'}
        return execute(request, None, control, None, kwargs.pop('guard', lambda: None),
                       providers=providers, clock=timer, sleep=timer.sleep, **kwargs)

    def test_requested_order_is_fixed(self):
        # Jarvis's own physical pointer first; accessibility providers follow as fallback.
        self.assertEqual(PRIORITY, ('jarvis-pointer', 'ufo', 'windows-mcp', 'cua', 'open-computer-use', 'agent-s'))

    def test_only_preflight_failures_fall_through(self):
        first = SimpleNamespace(name='ufo', prepare=Mock(side_effect=Unsupported('missing pattern')))
        call = Mock()
        second = SimpleNamespace(name='windows-mcp', prepare=Mock(return_value=Prepared(call, lambda: True, True)))
        last = SimpleNamespace(name='cua', prepare=Mock())
        result = self.route([first, second, last])
        self.assertEqual(result['provider'], 'windows-mcp')
        self.assertEqual(result['attempts'][0]['state'], 'not_dispatched')
        call.assert_called_once()
        last.prepare.assert_not_called()

    def test_partial_failure_never_clicks_again(self):
        call = Mock(side_effect=RuntimeError('response lost'))
        first = SimpleNamespace(name='ufo', prepare=Mock(return_value=Prepared(call)))
        second = SimpleNamespace(name='windows-mcp', prepare=Mock())
        with self.assertRaises(UncertainAction):
            self.route([first, second])
        call.assert_called_once()
        second.prepare.assert_not_called()

    def test_unrelated_state_change_cannot_hide_invoke_exception(self):
        first = SimpleNamespace(name='ufo', prepare=lambda *a: Prepared(Mock(side_effect=RuntimeError('lost'))))
        with self.assertRaises(UncertainAction):
            self.route([first], observe=Mock(side_effect=['before', 'unrelated change']))

    def test_state_change_after_click_is_not_goal_verification(self):
        first = SimpleNamespace(name='ufo', prepare=lambda *a: Prepared(Mock()))
        result = self.route([first], observe=Mock(side_effect=['before', 'timer/focus changed']))
        self.assertTrue(result['observed_change'])
        self.assertFalse(result['verified'])

    def test_quoted_text_preserves_action_words(self):
        steps = compile_steps('fill Search field with "cats then install unknown extension"')
        self.assertEqual(steps[0]['content'], 'cats then install unknown extension')

    def test_after_exception_exact_value_can_be_observed_without_replay(self):
        call = Mock(side_effect=RuntimeError('lost response'))
        first = SimpleNamespace(name='ufo', prepare=lambda *a: Prepared(call, lambda: 'exact', 'exact'))
        second = SimpleNamespace(name='windows-mcp', prepare=Mock())
        result = self.route([first, second], 'fill_text')
        self.assertTrue(result['verified'])
        self.assertIn('dispatch_error', result)
        call.assert_called_once()
        second.prepare.assert_not_called()

    def test_verification_failure_never_falls_through(self):
        call = Mock()
        first = SimpleNamespace(name='ufo', prepare=lambda *a: Prepared(call, lambda: 'wrong', 'exact'))
        second = SimpleNamespace(name='windows-mcp', prepare=Mock())
        result = self.route([first, second], 'fill_text')
        self.assertFalse(result['verified'])
        call.assert_called_once()
        second.prepare.assert_not_called()

    def test_already_present_state_does_not_issue_input(self):
        call = Mock()
        provider = SimpleNamespace(name='ufo', prepare=lambda *a: Prepared(call, lambda: True, True, True, True))
        self.assertTrue(self.route([provider])['verified'])
        call.assert_not_called()

    def test_already_present_state_is_read_again_before_reporting_success(self):
        call = Mock()
        provider = SimpleNamespace(name='ufo', prepare=lambda *a: Prepared(call, lambda: False, True, True, True))
        result = self.route([provider])
        self.assertFalse(result['verified'])
        self.assertFalse(result['dispatched'])
        self.assertIn('no input issued', result['message'])
        call.assert_not_called()

    def test_windows_mcp_menu_can_prepare_invoke_before_dispatch(self):
        invoke = SimpleNamespace(Invoke=Mock(return_value=None))
        def resolve(element, name):
            if name == 'expand_collapse':
                raise Unsupported('no expand pattern')
            self.assertEqual(name, 'invoke')
            return invoke
        with patch('jarvis.execution_adapters.pattern', side_effect=resolve):
            action = WindowsMCP().prepare(None, {'role': 'MenuItem'}, {'operation': 'open_menu'}, None)
        invoke.Invoke.assert_not_called()
        action.call()
        invoke.Invoke.assert_called_once()

    def test_quoted_text_length_is_validated_before_observation(self):
        with self.assertRaisesRegex(ValueError, '10,000'):
            compile_steps('fill Search field with "' + 'x'*10001 + '"')

    def test_scroll_readback_requires_the_requested_direction_and_axis(self):
        native = SimpleNamespace(CurrentHorizontalScrollPercent=50, CurrentVerticalScrollPercent=50, Scroll=Mock())
        with patch('jarvis.execution_adapters.pattern', return_value=native):
            prepared = WindowsMCP().prepare(None, {}, {'operation': 'scroll', 'value': 'down'}, None)
        native.CurrentHorizontalScrollPercent = 80
        self.assertFalse(prepared.read())
        native.CurrentVerticalScrollPercent = 20
        self.assertFalse(prepared.read())
        native.CurrentVerticalScrollPercent = 80
        self.assertTrue(prepared.read())
        native.Scroll.assert_not_called()

    def test_focus_change_cancels_before_dispatch(self):
        call = Mock()
        provider = SimpleNamespace(name='ufo', prepare=lambda *a: Prepared(call))
        guard = Mock(side_effect=[None, ValueError('focus changed')])
        with self.assertRaisesRegex(ValueError, 'focus changed'):
            self.route([provider], guard=guard)
        call.assert_not_called()

    def test_readonly_rejection_does_not_use_other_provider(self):
        first = SimpleNamespace(name='ufo', prepare=Mock(side_effect=ValueError('read-only')))
        second = SimpleNamespace(name='windows-mcp', prepare=Mock())
        with self.assertRaisesRegex(ValueError, 'read-only'):
            self.route([first, second], 'fill_text')
        second.prepare.assert_not_called()

    def test_invalid_or_password_text_never_reaches_provider(self):
        provider = SimpleNamespace(name='ufo', prepare=Mock())
        for control, content in [({'role': 'Edit', 'password': True}, 'secret'), ({'role': 'Edit'}, 'x'*10001), ({'role': 'Button'}, 'text'), ({'role': 'Edit'}, 'bad\x00text')]:
            with self.assertRaises(ValueError):
                execute({'operation': 'fill_text', 'content': content}, None, control, None,
                        lambda: None, providers=[provider])
        provider.prepare.assert_not_called()

    def test_actual_windows_mcp_subset_calls_setvalue_once(self):
        value = SimpleNamespace(CurrentValue='', SetValue=Mock(), CurrentIsReadOnly=False)
        def change(content):
            value.CurrentValue = content
            return None  # Normal comtypes HRESULT success shape.
        value.SetValue.side_effect = change
        with patch('jarvis.execution_adapters.pattern', return_value=value):
            result = self.route([WindowsMCP()], 'fill_text')
        self.assertTrue(result['verified'])
        value.SetValue.assert_called_once_with('exact')


class DirectTests(unittest.TestCase):
    def fixture(self, folder, verified=True):
        rows = [{'name': 'Search', 'role': 'Edit', 'id': [1], 'rect': [1, 1, 2, 2]},
                {'name': 'Enabled', 'role': 'CheckBox', 'id': [2], 'rect': [1, 2, 2, 3]}]
        requests = []
        def runner(request, cancelled):
            requests.append(request)
            if request['operation'] == 'list':
                return {'controls': rows, 'signature': 'fresh', 'title': 'Fixture'}
            return {'message': 'native result', 'provider': 'ufo', 'verified': verified}
        ui = SimpleNamespace(_handle=lambda: 123, runner=runner)
        actions = SimpleNamespace(resume_source=None, _ui=lambda: ui,
            task_state=TaskState(folder), report=Mock(), config={}, brain=Mock())
        actions.task_state.start('fixture', 'task')
        return actions, requests

    def test_whole_request_must_compile_before_any_dispatch(self):
        self.assertIsNone(compile_steps('fill Search field with cats then install unknown extension'))
        self.assertIsNone(compile_steps('open Chrome and analyze this website'))
        self.assertEqual(compile_steps('fill Search field with rock and roll')[0]['content'], 'rock and roll')

    def test_explicit_compound_route_calls_no_brain(self):
        with tempfile.TemporaryDirectory() as folder:
            actions, requests = self.fixture(folder)
            result = run(actions, 'fill Search field with cats then select Enabled', lambda: False)
            self.assertIn('no model calls', result)
            self.assertEqual([r['operation'] for r in requests], ['list', 'fill_text', 'list', 'activate'])
            actions.brain.run.assert_not_called()
            self.assertEqual(actions.task_state.snapshot()['stage'], 'goal_verified')

    def test_unverified_first_action_stops_compound_request(self):
        with tempfile.TemporaryDirectory() as folder:
            actions, requests = self.fixture(folder, False)
            self.assertIn('paused', run(actions, 'fill Search field with cats then select Enabled', lambda: False))
            self.assertEqual([r['operation'] for r in requests], ['list', 'fill_text'])
            self.assertTrue(TaskState.resume_blocker(actions.task_state.snapshot()))

    def test_unknown_intent_returns_without_input(self):
        with tempfile.TemporaryDirectory() as folder:
            actions, requests = self.fixture(folder)
            self.assertIsNone(run(actions, 'make a beautiful poster', lambda: False))
            self.assertEqual(requests, [])

    def test_sensitive_dialog_does_not_bypass_existing_approvals(self):
        with tempfile.TemporaryDirectory() as folder:
            actions, requests = self.fixture(folder)
            result = run(actions, 'click delete', lambda: False)
            self.assertIn('paused', result)
            self.assertEqual([r['operation'] for r in requests], ['list'])

    def test_cancelled_route_issues_no_input(self):
        with tempfile.TemporaryDirectory() as folder:
            actions, requests = self.fixture(folder)
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                run(actions, 'select Enabled', lambda: True)
            self.assertEqual(requests, [])


if __name__ == '__main__':
    unittest.main()
