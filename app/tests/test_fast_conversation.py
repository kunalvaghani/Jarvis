"""Fast planning, step-by-step recovery, task queue and natural conversation (2026-10-10)."""
import base64
import io
import json
import threading
import unittest
from unittest.mock import Mock, patch

import requests

from jarvis.commands import Command, parse


class SchedulerSpeedTests(unittest.TestCase):
    def test_cpu_threads_and_long_warm_period_are_validated_and_applied(self):
        from jarvis.gpu_scheduler import settings, install
        self.assertEqual(settings({'warm_seconds': 1800, 'cpu_threads': 12})['cpu_threads'], 12)
        for bad in ({'warm_seconds': 3601}, {'cpu_threads': 65}, {'cpu_threads': True}):
            with self.assertRaises(ValueError):
                settings(bad)
        response = requests.Response(); response.status_code = 200; response._content = b'{}'; response.raw = Mock()
        observed = requests.Response(); observed.status_code = 200; observed._content = b'{"models":[]}'; observed.raw = Mock()
        sent = patch('requests.sessions.Session.post', return_value=response).start()
        patch('requests.sessions.Session.get', return_value=observed).start()
        self.addCleanup(patch.stopall)
        import tempfile
        from jarvis.gpu_scheduler import Registry
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        policy = settings({'enabled': True, 'wait_seconds': 2, 'warm_seconds': 1800, 'cpu_threads': 12})
        patch('jarvis.gpu_scheduler.configured', return_value=policy).start()
        patch('jarvis.gpu_scheduler.Registry', return_value=Registry(directory.name)).start()
        patch('jarvis.gpu_scheduler.memory', return_value={'total_mb': 4096, 'used_mb': 1041}).start()
        client = install(requests.Session(), 'planner'); self.addCleanup(client.close)
        client.post('http://127.0.0.1:11434/api/chat', json={'model': 'qwen3.5:9b', 'messages': [{'role': 'user', 'content': 'x'}],
                                                             'options': {'num_ctx': 8192}})
        payload = sent.call_args.kwargs['json']
        self.assertEqual(payload['options']['num_thread'], 12)  # CPU layers use 12 threads.
        self.assertEqual(payload['keep_alive'], 1800)  # Stays loaded: no ~10 s reload per call.
        self.assertGreater(payload['options']['num_gpu'], 0)  # Split across GPU and CPU.


class PlannerInputTests(unittest.TestCase):
    def test_screenshot_only_when_it_adds_evidence(self):
        from jarvis.step_planning import wants_image
        readable = {'controls': ['Search', 'Home', 'Back', 'Forward', 'Reload', 'Menu']}
        self.assertFalse(wants_image(readable, []))
        self.assertTrue(wants_image(readable, [{'action': 'select'}]))  # Recovery needs pixels.
        self.assertTrue(wants_image({'controls': ['Close']}, []))  # Canvas/game: few readable controls.
        self.assertTrue(wants_image(readable, [], 'always'))
        self.assertFalse(wants_image({'controls': []}, [{'x': 1}], 'never'))

    def test_planner_copy_of_screenshot_is_shrunk_and_text_passes_through(self):
        from PIL import Image
        from jarvis.step_planning import compact_image
        buffer = io.BytesIO(); Image.new('RGB', (1600, 1200), 'white').save(buffer, 'JPEG')
        small = compact_image(base64.b64encode(buffer.getvalue()).decode())
        self.assertEqual(max(Image.open(io.BytesIO(base64.b64decode(small))).size), 1024)
        self.assertEqual(compact_image('frame0'), 'frame0')

    def test_navigation_steps_skip_second_check_and_writes_never_replan_after_uncertainty(self):
        from jarvis.brain import navigation_step, replannable
        from jarvis.tools import ToolRegistry
        specs = ToolRegistry(Mock(config={})).specs
        self.assertTrue(navigation_step({'action': 'browse'}, specs))
        self.assertTrue(navigation_step({'action': 'browser_inspect'}, specs))
        for action in ('select', 'browser_click', 'type_text', 'create_file', 'run_command'):
            self.assertFalse(navigation_step({'action': action}, specs), action)
        self.assertTrue(replannable({'action': 'select'}, specs))
        self.assertTrue(replannable({'action': 'browse'}, specs))
        for action in ('create_file', 'delete_file', 'run_command', 'close_app', 'type_text'):
            self.assertFalse(replannable({'action': action}, specs), action)

    def test_topic_tools_are_offered_only_for_related_requests(self):
        from jarvis.capabilities import relevant_tool
        self.assertFalse(relevant_tool('run_command', 'go to wikipedia and open black holes'))
        self.assertFalse(relevant_tool('delete_file', 'go to wikipedia'))
        self.assertTrue(relevant_tool('delete_file', 'delete notes.txt in Downloads'))
        self.assertTrue(relevant_tool('media_search', 'play lofi on youtube'))
        self.assertTrue(relevant_tool('realtime_query', 'what is the weather in Pune'))
        self.assertTrue(relevant_tool('open', 'anything at all'))  # Core navigation always offered.

    def test_type_text_is_a_bounded_desktop_tool(self):
        from jarvis.desktop_actions import validate_desktop_step
        from jarvis.native_tools import parameter_fields
        from jarvis.tools import TOOL_NAMES
        self.assertIn('type_text', TOOL_NAMES)
        self.assertEqual(parameter_fields('type_text'), {'value', 'expected', 'content'})
        for content in ('', '   ', 'x' * 10001):
            with self.assertRaises(ValueError):
                validate_desktop_step({'action': 'type_text', 'value': 'Notepad', 'content': content})
        validate_desktop_step({'action': 'type_text', 'value': 'Notepad', 'content': 'hello from jarvis'})


class ConversationReuseTests(unittest.TestCase):
    """Each task's planner calls form one growing conversation so the cache is reused."""
    rows = [{'action': 'browse', 'description': 'Open a URL'}, {'action': 'select', 'description': 'Click'}]

    def client(self, calls, name='browse'):
        def post(url, json=None, timeout=None):
            calls.append(json)
            response = Mock()
            response.json.return_value = {'message': {'role': 'assistant', 'content': '', 'tool_calls': [
                {'function': {'name': name, 'arguments': {'value': 'wikipedia.org', 'expected': 'Page open'}}}]},
                'prompt_eval_count': 6000, 'eval_count': 40, 'prompt_eval_duration': 1e9, 'eval_duration': 1e9}
            return response
        return Mock(post=post)

    def test_second_step_extends_the_first_prompt_exactly(self):
        from jarvis.native_tools import plan
        calls = []
        client = self.client(calls)
        first = plan(client, 'qwen3.5:9b', 'Rules.', {'goal': 'open wikipedia', 'tools': self.rows, 'screen': {'controls': ['A']}})
        self.assertFalse(first['inference']['continued'])
        second = plan(client, 'qwen3.5:9b', 'Rules.', {'goal': 'open wikipedia', 'tools': self.rows,
            'conversation': first['conversation'], 'step_number': 2, 'steps_left': 19,
            'last_result': {'action': 'browse', 'verified': True, 'confirmed': True, 'result': 'Opened', 'observation': 'Page'},
            'screen': {'title': 'Wikipedia', 'controls': ['Search Wikipedia']}})
        self.assertTrue(second['inference']['continued'])
        before, after = calls[0]['messages'], calls[1]['messages']
        self.assertEqual(after[:len(before)], before)  # Same prefix: only the new turn is read.
        update = json.loads(after[-1]['content'])
        self.assertEqual(after[-1]['role'], 'tool')
        self.assertEqual(update['screen']['title'], 'Wikipedia')
        self.assertTrue(update['outcome_confirmed'])

    def test_rejected_proposal_feedback_and_fresh_rebuilds(self):
        from jarvis.native_tools import plan
        calls = []
        client = self.client(calls)
        first = plan(client, 'qwen3.5:9b', 'Rules.', {'goal': 'g', 'tools': self.rows})
        plan(client, 'qwen3.5:9b', 'Rules.', {'goal': 'g', 'tools': self.rows, 'conversation': first['conversation'],
                                              'plan_validation_error': 'Already done.'})
        self.assertEqual(json.loads(calls[1]['messages'][-1]['content'])['not_executed'], True)
        other_tools = plan(client, 'qwen3.5:9b', 'Rules.', {'goal': 'g', 'tools': self.rows[:1], 'conversation': first['conversation']})
        self.assertEqual(other_tools['inference']['fresh_reason'], 'tools changed')
        full = {**first['conversation'], 'tokens': 16000}
        self.assertFalse(plan(client, 'qwen3.5:9b', 'Rules.', {'goal': 'g', 'tools': self.rows, 'conversation': full})['inference']['continued'])


class NaturalPhrasingTests(unittest.TestCase):
    def test_conversational_openers_become_existing_commands(self):
        self.assertEqual(parse("let's make an email"), Command('task', 'make an email'))
        self.assertEqual(parse("let's watch a video on youtube"), Command('open', 'youtube'))
        self.assertEqual(parse('i want to see a video about cats on youtube'), Command('task', 'open youtube and search for cats'))
        self.assertEqual(parse("let's listen to lofi"), Command('play_media', 'lofi', 'spotify'))
        self.assertEqual(parse('watch lofi beats on youtube'), Command('play_media', 'lofi beats', 'youtube'))
        self.assertEqual(parse('can we open youtube'), Command('open', 'youtube'))

    def test_hedges_and_questions_are_never_turned_into_actions(self):
        for text in ('maybe delete file notes', 'we should delete file notes', 'how about we delete file notes'):
            try:
                kind = parse(text).kind  # A question is fine ...
            except ValueError:
                kind = 'unparsed'  # ... or chat-vs-task classification; never a direct delete.
            self.assertIn(kind, {'ask', 'unparsed'}, text)
        self.assertEqual(parse('can we talk about my day').kind, 'ask')

    def test_queue_and_conversation_controls(self):
        self.assertEqual(parse('goodbye').kind, 'end_conversation')
        self.assertEqual(parse('go to sleep').kind, 'end_conversation')
        self.assertEqual(parse('cancel this task').kind, 'cancel_current')
        self.assertEqual(parse('stop all tasks').kind, 'cancel_all')
        self.assertEqual(parse("what's in the queue").kind, 'queue_status')
        self.assertEqual(parse('what are you working on').kind, 'queue_status')

    def test_chat_or_task_classification(self):
        from jarvis.conversation_intent import quick_kind, model_kind
        self.assertEqual(quick_kind("i'm feeling a bit tired today"), 'chat')
        self.assertEqual(quick_kind('open the downloads folder please'), 'task')
        self.assertIsNone(quick_kind('the weekend was long'))
        self.assertEqual(model_kind('x', {}, request=lambda *a, **k: {'kind': 'task'}), 'task')
        self.assertEqual(model_kind('x', {}, request=lambda *a, **k: {'kind': 'other'}), 'chat')
        def broken(*args, **kwargs):
            raise OSError('model down')
        self.assertEqual(model_kind('x', {}, request=broken), 'chat')  # A reply is harmless; a task is not.


class EngineConversationTests(unittest.TestCase):
    def setUp(self):
        from jarvis.engine import Engine
        self.sent = []
        self.engine = Engine(self.sent.append, lambda *a: None, 600)

    def test_unrecognised_speech_is_tagged_for_classification(self):
        self.engine.feed('jarvis the weekend was long', True)
        self.assertEqual(self.sent, [Command('task', 'the weekend was long', 'unparsed')])

    def test_mid_sentence_jarvis_is_content_during_conversation(self):
        self.engine.feed('jarvis open notepad', True)
        self.engine.feed('tell the team the jarvis call test worked', True)
        self.assertEqual(self.sent[-1].value, 'tell the team the jarvis call test worked')
        self.engine.feed('hey jarvis open calculator', True)
        self.assertEqual(self.sent[-1], Command('open', 'calculator'))

    def test_goodbye_ends_listening_but_is_not_a_cancel(self):
        self.engine.feed('jarvis goodbye', True)
        self.assertEqual(self.sent, [Command('end_conversation')])
        self.assertFalse(self.engine.active)


class QueueRoutingTests(unittest.TestCase):
    def actions(self):
        import tempfile
        from jarvis.actions import Actions
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        events = []
        actions = Actions({'files_root': 'files', 'apps': {}}, directory.name, lambda *a: events.append(a))
        self.addCleanup(actions.close)
        return actions, events

    def test_unrecognised_chat_goes_to_conversation_and_tasks_to_queue(self):
        actions, _ = self.actions()
        actions.knowledge.submit = Mock()
        with patch('jarvis.conversation_intent.model_kind', return_value='chat'):
            actions._route_unparsed('the weekend was long')
        actions.knowledge.submit.assert_called_once_with('the weekend was long', False)
        self.assertEqual(actions.pending_tasks, [])
        actions._route_unparsed('open the downloads folder please')
        self.assertEqual(len(actions.pending_tasks), 1)

    def test_pending_question_keeps_the_answer_path(self):
        actions, _ = self.actions()
        actions.pending_question = {'time': 0, 'goal': 'make an email', 'question': 'To whom?', 'slot': 'gmail', 'choices': [], 'source': {}}
        with patch.object(actions, '_route_unparsed') as routed:
            try:
                actions.submit(Command('task', 'to test at example dot com', 'unparsed'))
            except Exception:
                pass
        routed.assert_not_called()

    def test_end_conversation_keeps_queued_work(self):
        actions, events = self.actions()
        actions.current_item = (threading.Event(), Command('task', 'open wikipedia'))
        actions.submit(Command('end_conversation'))
        self.assertFalse(actions.current_item[0].is_set())
        self.assertIn(('spoken_reply', "Okay, talk to you later. I'll keep working on 1 task in the background."), events)


class ConversationAnswerTests(unittest.TestCase):
    def test_small_talk_never_searches_and_past_references_are_explicit(self):
        from jarvis.knowledge_worker import SMALL_TALK
        from jarvis.knowledge import PAST_REFERENCE
        self.assertTrue(SMALL_TALK.search('how are you doing today?'))
        self.assertTrue(SMALL_TALK.search("i'm feeling tired today"))
        self.assertFalse(SMALL_TALK.search('what is the weather today'))
        self.assertTrue(PAST_REFERENCE.search('remember the dinner we discussed'))
        self.assertFalse(PAST_REFERENCE.search('what is a good quick dinner idea?'))

    def test_upstream_skill_needs_two_shared_words(self):
        from jarvis.hermes_skills import HermesSkills
        skills = HermesSkills.__new__(HermesSkills)
        skills.rows = [{'name': 'baoyu-article-illustrator', 'description': 'Article illustrations: style and palette.', 'tags': []}]
        self.assertEqual(skills.overlap('go to wikipedia and open the article about black holes', {'name': 'baoyu-article-illustrator'}), 1)
        self.assertGreaterEqual(skills.overlap('make article illustrations with a palette', {'name': 'baoyu-article-illustrator'}), 2)


class DesktopInputTests(unittest.TestCase):
    def test_focus_never_sends_a_keystroke(self):
        from jarvis import window_focus
        user = Mock()
        user.IsIconic.return_value = False
        user.GetForegroundWindow.side_effect = [100, 200, 200]
        user.GetWindowThreadProcessId.return_value = 7
        user.AttachThreadInput.return_value = True
        kernel = Mock(); kernel.GetCurrentThreadId.return_value = 3
        self.assertTrue(window_focus.focus(200, user, kernel))
        user.keybd_event.assert_not_called()  # ALT would switch Notepad/Office into menu-key mode.
        user.AttachThreadInput.assert_any_call(3, 7, True)
        user.AttachThreadInput.assert_any_call(3, 7, False)

    def test_typing_pauses_between_characters(self):
        from jarvis import actions as module
        desktop = module.Desktop.__new__(module.Desktop)
        desktop.user = Mock(); desktop.target = 5
        desktop.user.GetCursorPos.return_value = False
        desktop.user.GetForegroundWindow.return_value = 5
        desktop.user.SendInput.return_value = 2
        with patch.object(module.time, 'sleep') as sleep:
            desktop.type('abc', lambda: False)
        self.assertEqual(sleep.call_count, 3)
        sleep.assert_called_with(module.TYPING_INTERVAL)


if __name__ == '__main__':
    unittest.main()
