import base64
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw
from jarvis.brain import Brain, validate_plan
from jarvis.brain_worker import Models, SCHEMAS
from jarvis.commands import parse
from jarvis.task_recovery import TaskFailure
from jarvis.tools import ToolRegistry
from jarvis.visual_fallback import VisualFallback, Prepared, VisualOutcome, save_plan, click_point, readiness
from jarvis.visual_worker import perform, point, unchanged, WindowsInput


def pixels(mark=False):
    image = Image.new('RGB', (600, 400), 'white')
    if mark:
        ImageDraw.Draw(image).rectangle((290, 190, 310, 210), fill='black')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return base64.b64encode(output.getvalue()).decode('ascii')


def frame(**extra):
    return {'handle': 42, 'pid': 222, 'rect': [100, 100, 700, 500], 'title': 'Fixture',
            'captured_at': time.time(), 'image': pixels(), **extra}


class InputFixture:
    def __init__(self, capture):
        self.capture = capture
        self.actions = []
        self.focused = (42, 222)
        self.modifiers = False
        self.covered = False
        self.fail = False

    def state(self, handle):
        return {k: self.capture[k] for k in ('handle', 'pid', 'rect', 'title')}

    def foreground(self):
        return self.focused

    def focus(self, handle):
        self.focused = (handle, 222)

    def held_modifiers(self):
        return self.modifiers

    def screenshot(self, capture):
        return self.capture['image']

    def hit(self, x, y):
        return 43 if self.covered else 42

    def click(self, x, y):
        self.actions.append(('click', x, y))
        if self.fail:
            raise OSError('partial input')

    def shortcut(self, keys):
        self.actions.append(('shortcut', keys))

    def type(self, text):
        self.actions.append(('type', text))


class VisualParserTests(unittest.TestCase):
    def test_actual_upstream_parser_accepts_point_and_box(self):
        self.assertEqual(click_point('click(start_box="(500,250)")'), [.5, .25])
        self.assertEqual(click_point('click(start_box="(400,100,600,300)")'), [.5, .2])

    def test_generated_code_and_invalid_coordinates_are_never_evaluated(self):
        for action in ['os.click(start_box="(500,500)")', 'click(500,500)',
                       'click(start_box="(500,500)", other=1)', 'hotkey(key="enter")',
                       'click(start_box=__import__("os").getcwd())',
                       'click(start_box="__import__(\'os\').getcwd()")',
                       'click(start_box="(True,500)")', 'click(start_box="(0,500)")',
                       'click(start_box="(1000,500)")', 'click(start_box="(500,500,400,400)")']:
            with self.subTest(action=action), self.assertRaises((ValueError, SyntaxError)):
                click_point(action)

    def test_normalized_points_use_physical_window_geometry_and_negative_monitor(self):
        self.assertEqual(point(frame(rect=[-1920, 0, 0, 1080]), [.5, .5]), (-960, 540))
        self.assertEqual(point(frame(rect=[0, 0, 3840, 2160]), [.5, .5]), (1920, 1080))
        for xy in ([0, .5], [float('nan'), .5], [.001, .5], [True, .5]):
            with self.subTest(xy=xy), self.assertRaises(ValueError):
                point(frame(), xy)

    def test_small_change_at_target_is_rejected(self):
        self.assertFalse(unchanged(pixels(), pixels(True), [.5, .5]))
        self.assertTrue(unchanged(pixels(), pixels(True), [.1, .1]))


class VisualWorkerTests(unittest.TestCase):
    def setUp(self):
        self.frame = frame()
        self.backend = InputFixture(self.frame.copy())
        self.request = {'operation': 'click', 'frame': self.frame, 'owner_pid': 111, 'point': [.5, .5]}

    def test_dispatches_once_then_requires_outcome(self):
        result = perform(self.request, self.backend)
        self.assertTrue(result['attempted'])
        self.assertEqual(self.backend.actions, [('click', 400, 300)])
        self.assertIn('verification', result['message'])

    def test_refuses_stale_foreign_covered_resized_or_changed_target(self):
        faults = ['stale', 'foreign', 'covered', 'resize', 'image', 'modifier', 'self']
        for fault in faults:
            self.setUp()
            if fault == 'stale': self.frame['captured_at'] -= 6
            if fault == 'foreign': self.backend.focused = (99, 333)
            if fault == 'covered': self.backend.covered = True
            if fault == 'resize': self.backend.capture['rect'] = [0, 0, 601, 400]
            if fault == 'image': self.backend.capture['image'] = pixels(True)
            if fault == 'modifier': self.backend.modifiers = True
            if fault == 'self': self.request['owner_pid'] = 222
            with self.subTest(fault=fault):
                self.assertFalse(perform(self.request, self.backend)['attempted'])
                self.assertEqual(self.backend.actions, [])

    def test_last_moment_focus_change_and_cancel_stop_input(self):
        self.backend.foreground = Mock(side_effect=[(42,222), (42,222), (99,333)])
        self.assertFalse(perform(self.request, self.backend)['attempted'])
        self.assertEqual(self.backend.actions, [])
        self.setUp()
        self.assertFalse(perform(self.request, self.backend, lambda: True)['attempted'])
        self.assertEqual(self.backend.actions, [])

    def test_partial_input_is_uncertain_and_not_retried(self):
        self.backend.fail = True
        result = perform(self.request, self.backend)
        self.assertTrue(result['attempted'])
        self.assertIn('partial', result['error'])
        self.assertEqual(len(self.backend.actions), 1)

    def test_literal_unicode_field_entry_and_keyboard_allowlist(self):
        result = perform({**self.request, 'operation': 'fill', 'content': 'नमस्ते 🙂'}, self.backend)
        self.assertTrue(result['attempted'])
        self.assertEqual(self.backend.actions, [('shortcut', 'ctrl+a'), ('type', 'नमस्ते 🙂')])
        self.setUp()
        self.assertFalse(perform({**self.request, 'operation': 'shortcut', 'value': 'enter'}, self.backend)['attempted'])
        self.assertEqual(self.backend.actions, [])

    def test_focus_loss_after_selection_stops_typing(self):
        self.backend.foreground = Mock(side_effect=[(42,222)]*3 + [(99,333)])
        result = perform({**self.request, 'operation': 'fill', 'content': 'literal'}, self.backend)
        self.assertTrue(result['attempted'])
        self.assertEqual(self.backend.actions, [('shortcut', 'ctrl+a')])

    def test_windows_shortcut_emits_key_tokens_and_unicode_has_balanced_events(self):
        backend = WindowsInput.__new__(WindowsInput)
        backend.user = Mock()
        emitted = []
        def send(count, events, size):
            emitted.extend((events[i].u.ki.wVk, events[i].u.ki.wScan, events[i].u.ki.dwFlags) for i in range(count))
            return count
        backend.user.SendInput.side_effect = send
        backend.shortcut('ctrl+shift+s')
        self.assertEqual([(v,f) for v,s,f in emitted], [(17,0),(16,0),(83,0),(83,2),(16,2),(17,2)])
        emitted.clear()
        backend.type('🙂')
        self.assertEqual([f for v,s,f in emitted], [4,6,4,6])
        self.assertEqual(emitted[0][1], emitted[1][1])
        self.assertEqual(emitted[2][1], emitted[3][1])

    def test_partial_windows_batch_only_releases_accepted_downs(self):
        for operation in ('shortcut','unicode'):
            backend = WindowsInput.__new__(WindowsInput)
            backend.user = Mock()
            calls = []
            def send(count,events,size):
                calls.append([(events[i].type, events[i].u.ki.dwFlags if events[i].type else events[i].u.mi.dwFlags) for i in range(count)])
                return 1 if len(calls)==1 else count
            backend.user.SendInput.side_effect = send
            with self.subTest(operation=operation), self.assertRaises(OSError):
                if operation=='shortcut': backend.shortcut('ctrl+shift+s')
                else: backend.type('a')
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[1], [(1,6 if operation=='unicode' else 2)])

    def test_physical_mouse_injection_is_rejected_before_input(self):
        backend=WindowsInput.__new__(WindowsInput);backend.user=Mock()
        with self.assertRaisesRegex(ValueError,'Physical mouse injection'):
            backend.inputs(click=True)
        backend.user.SendInput.assert_not_called()


class VisualControllerTests(unittest.TestCase):
    def setUp(self):
        self.brain = Mock()
        self.brain.options = {'visual_fallback': {'enabled': True}}
        self.brain.actions.config = {'agent_runtime': {}}
        self.fallback = VisualFallback(self.brain)
        self.frame = frame()
        self.snapshot = {'controls': [], 'visual_only': True}
        self.brain.visual_screen.return_value = self.frame
        self.brain.observe.return_value = (42, self.snapshot)
        self.proposal = {'action': 'click(start_box="(500,500)")', 'target': 'Save', 'role': 'Button',
                         'confidence': .99, 'is_dialog': True, 'password': False}
        self.brain.client.request.return_value = self.proposal
        self.step = {'action': 'handle_dialog', 'value': 'Save', 'expected': 'Saved'}
        self.fallback.input = Mock(return_value={'attempted': True})

    def test_reobserves_after_grounding_and_rejects_changed_scene(self):
        self.brain.visual_screen.side_effect = [self.frame, frame(image=pixels(True))]
        with self.assertRaises(TaskFailure) as caught:
            self.fallback.prepare('Save', self.step, 42, self.snapshot, lambda: False)
        self.assertFalse(caught.exception.attempted)
        self.fallback.input.assert_not_called()

    def test_refuses_uncertain_wrong_password_unsupported_and_dangerous_targets(self):
        for change in [{'confidence': .94}, {'confidence': float('nan')}, {'target': 'Cancel'},
                       {'role': 'unknown'}, {'is_dialog': False}, {'action': 'exec("bad")'}]:
            with self.subTest(change=change), self.assertRaises(TaskFailure):
                self.brain.client.request.return_value = {**self.proposal, **change}
                self.fallback.prepare('Save', self.step, 42, self.snapshot, lambda: False)
        with self.assertRaises(TaskFailure):
            self.fallback.prepare('Upload', {**self.step, 'value': 'Upload'}, 42, self.snapshot, lambda: False)
        self.brain.client.request.return_value = {**self.proposal, 'target': 'Name', 'role': 'Edit', 'password': True}
        with self.assertRaises(TaskFailure):
            self.fallback.prepare('Name', {'action': 'fill_text', 'value': 'Name', 'content': 'hi'}, 42, self.snapshot, lambda: False)
        self.fallback.input.assert_not_called()

    def test_outcome_failure_keeps_one_click_uncertain(self):
        prepared = self.fallback.prepare('Save', self.step, 42, self.snapshot, lambda: False)
        self.brain.client.request.return_value = {'step_verified': False, 'reason': 'dialog unchanged'}
        with self.assertRaises(TaskFailure) as caught:
            self.fallback.execute('Save', prepared, lambda: False)
        self.assertTrue(caught.exception.attempted)
        self.fallback.input.assert_called_once()

    def test_fresh_outcome_checkpoint_has_independent_source(self):
        prepared = self.fallback.prepare('Save', self.step, 42, self.snapshot, lambda: False)
        self.brain.client.request.return_value = {'step_verified': True, 'summary': 'Saved', 'goal_done': False}
        result = self.fallback.execute('Save', prepared, lambda: False)
        self.assertTrue(result.assessment['step_verified'])
        self.assertEqual(self.brain.checkpoint.call_args.kwargs['source'], 'fresh_visual_verifier')

    def test_classifier_cannot_substitute_filename_value_for_field_label(self):
        self.brain.client.request.return_value = {'kind':'save_as','confidence':.99,'filename_label':'notes.txt','confirm_label':'Save'}
        with self.assertRaisesRegex(ValueError,'instead of its field label'):
            self.fallback.dialog_kind(self.frame,self.snapshot,lambda:False)
        self.fallback.input.assert_not_called()

    def test_fill_requires_focus_and_exact_transcription(self):
        prepared = Prepared(42, self.snapshot, self.frame, [.5,.5],
                            {'action':'fill_text', 'value':'Name', 'content':'literal'}, 'Edit')
        for responses, count in [([{'verified':False}], 1),
                                 ([{'verified':True}, {'verified':True, 'observed_text':'wrong'}], 2)]:
            self.fallback.input.reset_mock()
            self.brain.client.request.side_effect = responses
            with self.assertRaises(TaskFailure) as caught:
                self.fallback.execute('Enter literal in Name', prepared, lambda:False)
            self.assertTrue(caught.exception.attempted)
            self.assertEqual(self.fallback.input.call_count, count)

    def test_field_scene_changed_during_focus_check_never_types(self):
        prepared = Prepared(42, self.snapshot, self.frame, [.5,.5],
                            {'action':'fill_text', 'value':'Name', 'content':'literal'}, 'Edit')
        self.brain.client.request.return_value = {'verified':True}
        self.brain.visual_screen.side_effect = [self.frame, frame(image=pixels(True))]
        with self.assertRaises(TaskFailure):
            self.fallback.execute('Enter literal in Name', prepared, lambda:False)
        self.fallback.input.assert_called_once()

    def test_native_first_and_no_visual_replay_of_native_failure(self):
        self.snapshot.update(is_dialog=True, controls=[{'name':'Save', 'role':'Button', 'enabled':True}])
        native = self.brain.actions._ui.return_value
        self.fallback.prepare = Mock()
        self.fallback.named('Save', self.step, lambda:False)
        native._activate.assert_called_once()
        self.fallback.prepare.assert_not_called()
        native._activate.side_effect = ValueError('provider lost after click')
        with self.assertRaises(TaskFailure) as caught:
            self.fallback.named('Save', self.step, lambda:False)
        self.assertTrue(caught.exception.attempted)
        self.fallback.prepare.assert_not_called()

    def test_ambiguous_native_control_is_not_guessed(self):
        self.snapshot.update(is_dialog=True, controls=[{'name':'Save', 'role':'Button', 'enabled':True}]*2)
        with self.assertRaises(TaskFailure) as caught:
            self.fallback.named('Save', self.step, lambda:False)
        self.assertFalse(caught.exception.attempted)
        self.fallback.input.assert_not_called()

    def test_provider_policy_blocks_visual_save_primitive(self):
        with tempfile.TemporaryDirectory() as directory:
            self.brain.actions.base = Path(directory)
            policy = Path(directory) / '.jarvis' / 'policy.json'
            policy.parent.mkdir()
            policy.write_text(json.dumps({'deny_tools':['handle_dialog']}))
            with self.assertRaises(ValueError):
                self.fallback.named('Save', self.step, lambda:False)
        self.fallback.input.assert_not_called()


class SaveDialogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'notes.txt'
        brain = Mock()
        brain.options = {'visual_fallback': {'enabled':True}}
        brain.actions.config = {'agent_runtime':{}}
        brain.actions._task_folder.return_value = self.folder
        self.fallback = VisualFallback(brain)
        self.fallback.observe = Mock(return_value=(42, {'controls':[]}, frame()))
        self.fallback.dialog_kind = Mock(side_effect=[{'kind':'save_as', 'filename_label':'File name', 'confirm_label':'Save'}, {'kind':'none'}])
        self.fallback.named = Mock(side_effect=self.act)
        self.step = {'action':'save_file', 'value':'notes.txt', 'folder':str(self.folder), 'content':''}
        self.writes = True

    def act(self, goal, step, cancelled, pid):
        if step['action'] == 'handle_dialog' and self.writes:
            self.path.write_text('document', encoding='utf-8')

    def save(self, cancelled=lambda:False):
        return self.fallback.save_file('Save document as notes.txt in '+str(self.folder), self.step, cancelled)

    def test_save_requires_named_field_and_independent_stable_disk_readback(self):
        result = self.save()
        self.assertIn('independently read back', result)
        self.assertEqual(self.fallback.named.call_args_list[0].args[1]['content'], str(self.path))
        self.assertEqual(self.fallback.last_saved['size'], len(b'document'))
        self.assertEqual(self.fallback.brain.checkpoint.call_args.kwargs['source'], 'disk_readback')

    def test_disappearing_dialog_alone_is_not_success(self):
        self.writes = False
        with patch('jarvis.visual_fallback.time.monotonic', side_effect=[0, 6]):
            with self.assertRaises(TaskFailure) as caught: self.save()
        self.assertTrue(caught.exception.attempted)
        self.assertIsNone(self.fallback.last_saved)
        self.assertEqual(self.fallback.named.call_count, 2)

    def test_existing_target_approval_and_changed_target_race(self):
        self.path.write_text('old')
        self.fallback.brain.actions._approve.side_effect = lambda *args: self.path.write_text('changed')
        with self.assertRaises(TaskFailure) as caught: self.save()
        self.assertFalse(caught.exception.attempted)
        self.fallback.named.assert_not_called()

    def test_approval_is_for_exact_path(self):
        self.path.write_text('old')
        self.save()
        approval = self.fallback.brain.actions._approve.call_args.args
        self.assertEqual(approval[0], 'overwrite')
        self.assertIn(str(self.path), approval[1])

    def test_changed_target_before_save_never_clicks_save(self):
        def changed(goal, step, cancelled, pid):
            self.path.write_text('unexpected')
        self.fallback.named.side_effect = changed
        with self.assertRaises(TaskFailure) as caught: self.save()
        self.assertTrue(caught.exception.attempted)
        self.fallback.named.assert_called_once()

    def test_unapproved_overwrite_and_unresolved_dialog_never_replays(self):
        for kind in ['overwrite', 'save_as', 'unknown']:
            self.fallback.named.reset_mock()
            self.path.unlink(missing_ok=True)
            self.fallback.dialog_kind.side_effect = [{'kind':'save_as'}, {'kind':kind}]
            with self.subTest(kind=kind), self.assertRaises(TaskFailure): self.save()
            self.assertEqual(self.fallback.named.call_count, 2)

    def test_approved_overwrite_choice_is_followed_by_observation(self):
        self.path.write_text('old')
        self.writes = False
        self.fallback.dialog_kind.side_effect = [{'kind':'save_as'}, {'kind':'overwrite', 'confirm_label':'Yes', 'overwrite_name':'notes.txt'}, {'kind':'none'}]
        def replace(goal, step, cancelled, pid):
            if step['value'] == 'Yes': self.path.write_text('document')
        self.fallback.named.side_effect = replace
        self.save()
        self.assertEqual(self.fallback.named.call_count, 3)
        self.assertEqual(self.fallback.named.call_args.args[1]['value'], 'Yes')

    def test_overwrite_name_must_independently_match_approved_file(self):
        self.path.write_text('old')
        self.writes = False
        self.fallback.dialog_kind.side_effect = [{'kind':'save_as'},
            {'kind':'overwrite','confirm_label':'Yes','overwrite_name':'notes.txt.txt'}]
        with self.assertRaises(TaskFailure): self.save()
        self.assertEqual(self.fallback.named.call_count,2)
        self.assertEqual(self.path.read_text(),'old')

    def test_field_failure_stops_before_save(self):
        self.fallback.named.side_effect = TaskFailure('field not read back', attempted=True)
        with self.assertRaises(TaskFailure): self.save()
        self.fallback.named.assert_called_once()
        self.assertFalse(self.path.exists())

    def test_content_mismatch_and_post_input_cancellation_are_uncertain(self):
        self.step['content'] = 'different'
        with self.assertRaises(TaskFailure) as caught: self.save()
        self.assertTrue(caught.exception.attempted)
        self.assertIsNone(self.fallback.last_saved)
        self.step['content'] = ''
        self.path.unlink()
        self.fallback.dialog_kind.side_effect = [{'kind':'save_as'}, {'kind':'none'}]
        with self.assertRaises(TaskFailure) as caught: self.save(lambda:self.path.exists())
        self.assertTrue(caught.exception.attempted)

    def test_cancel_before_work_never_sends_input_or_requests_approval(self):
        with self.assertRaises(TaskFailure) as caught: self.save(lambda:True)
        self.assertFalse(caught.exception.attempted)
        self.fallback.named.assert_not_called()
        self.fallback.brain.actions._approve.assert_not_called()

    def test_links_and_oversized_files_are_refused(self):
        with patch('jarvis.skill_memory.linked', return_value=True):
            with self.assertRaises(TaskFailure): self.save()
        self.fallback.named.assert_not_called()
        with self.path.open('wb') as out: out.truncate(20*1024*1024+1)
        with self.assertRaises(ValueError): self.fallback.file_state(self.path)


class VisualTransportTests(unittest.TestCase):
    def setUp(self):
        self.brain = Mock()
        self.brain.options = {'visual_fallback':{'enabled':True}}
        self.brain.client.base = Path.cwd()
        self.fallback = VisualFallback(self.brain)

    def test_dead_worker_and_invalid_response_never_retry(self):
        for returncode, output in [(1,''), (0,'invalid'), (0,'{}')]:
            process = Mock(returncode=returncode)
            process.communicate.return_value = (output,'')
            with patch('jarvis.visual_fallback.subprocess.Popen', return_value=process) as launch:
                with self.assertRaises(TaskFailure) as caught:
                    self.fallback.input('click', frame(), lambda:False, point=[.5,.5])
            self.assertTrue(caught.exception.attempted)
            launch.assert_called_once()
            process.communicate.assert_called_once()

    def test_explicit_worker_refusal_preserves_no_input_evidence(self):
        process = Mock(returncode=0)
        process.communicate.return_value = (json.dumps({'attempted':False, 'error':'target changed'}),'')
        with patch('jarvis.visual_fallback.subprocess.Popen', return_value=process):
            with self.assertRaises(TaskFailure) as caught:
                self.fallback.input('click', frame(), lambda:False, point=[.5,.5])
        self.assertFalse(caught.exception.attempted)

    def test_cancel_kills_only_owned_worker_without_resubmitting(self):
        process = Mock(returncode=0)
        process.poll.return_value = None
        process.communicate.side_effect = [subprocess.TimeoutExpired('owned',.2), ('','')]
        cancelled = Mock(side_effect=[False,False,True])
        with patch('jarvis.visual_fallback.subprocess.Popen', return_value=process) as launch:
            with self.assertRaises(TaskFailure) as caught:
                self.fallback.input('click', frame(), cancelled, point=[.5,.5])
        self.assertTrue(caught.exception.attempted)
        launch.assert_called_once()
        process.kill.assert_called_once()
        self.assertIsNotNone(process.communicate.call_args_list[0].kwargs['input'])
        self.assertEqual(process.communicate.call_args_list[1].kwargs, {})


class VisualIntegrationTests(unittest.TestCase):
    def loop(self):
        actions = Mock()
        actions.apps = {}
        actions.pending_open = actions.last_created = actions.last_modified = actions.last_deleted = actions.last_command = None
        brain = Brain(actions,Path.cwd(),{'enabled':True,'planner':'planner','decision':'decision',
                                        'visual_fallback':{'enabled':True}})
        brain.client = Mock()
        snap = {'title':'Fixture','controls':[],'context':'fixture','signature':'fixture','is_dialog':False}
        brain.observe = Mock(return_value=(42,snap))
        return actions,brain,snap

    def test_task_loop_routes_missing_control_and_requires_final_goal_check(self):
        actions,brain,snap = self.loop()
        outcome = VisualOutcome(42,snap,{**frame(),'summary':'Pressed Save'}, {'step_verified':True},'visual checked')
        brain.visual_fallback.prepare = Mock(return_value=Prepared(42,snap,frame(),[.5,.5],{'action':'select','value':'Save'},'Button'))
        brain.visual_fallback.execute = Mock(return_value=outcome)
        brain.client.request.return_value = {'verified':True}
        result = brain.run('Click Save',lambda:False)
        self.assertIn('Finished',result)
        brain.visual_fallback.execute.assert_called_once()
        actions._ui.return_value._activate.assert_not_called()
        self.assertEqual([c.args[0] for c in brain.client.request.call_args_list], ['verify'])

    def test_task_loop_keeps_matching_native_control_and_never_replays_failure(self):
        actions,brain,snap = self.loop()
        snap['controls'] = [{'name':'Save','role':'Button','id':[1],'rect':[0,0,50,30]}]
        brain.client.request.side_effect = [{'approved':True,'choice':'c0'},{'verified':True},{'verified':True}]
        brain.visual_fallback.prepare = Mock()
        with patch('jarvis.brain.time.sleep'):
            self.assertIn('Finished',brain.run('Click Save',lambda:False))
        actions._ui.return_value._activate.assert_called_once()
        brain.visual_fallback.prepare.assert_not_called()
        actions._ui.return_value._activate.side_effect = ValueError('uncertain native failure')
        brain.client.request.side_effect = [{'approved':True,'choice':'c0'}]
        with self.assertRaisesRegex(ValueError,'uncertain native failure'):
            brain.run('Click Save',lambda:False)
        brain.visual_fallback.prepare.assert_not_called()

    def test_nonmodal_native_button_does_not_bypass_dialog_observation(self):
        actions,brain,snap = self.loop()
        snap['controls'] = [{'name':'Save','role':'Button','id':[1],'rect':[0,0,50,30]}]
        brain.visual_fallback.prepare = Mock(side_effect=TaskFailure('No dialog',attempted=False))
        with self.assertRaisesRegex(ValueError,'Task paused'):
            brain.run('Click Save in the dialog',lambda:False)
        brain.visual_fallback.prepare.assert_called_once()
        actions._ui.return_value._activate.assert_not_called()

    def test_readiness_checks_reviewed_component_not_a_live_desktop_task(self):
        self.assertIsNone(readiness(Path(__file__).resolve().parents[1]))
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base/'runtime_manifest.json').write_text(json.dumps({'visual_interaction':{'component_sha256_lf':'wrong'}}))
            path = base/'jarvis/_vendor/ui_tars_action_parser.py'
            path.parent.mkdir(parents=True)
            path.write_text('pass\n')
            self.assertIn('checksum',readiness(base))

    def test_startup_repairs_owned_vendored_source_from_known_snapshot(self):
        from jarvis.launcher import preflight
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base/'config.json').write_text(json.dumps({'apps':{},'whisper':{},'model_path':'models'}))
            (base/'main.py').write_text('pass\n')
            source = base/'jarvis/_vendor/parser.py'
            source.parent.mkdir(parents=True)
            source.write_text('pass\n')
            preflight(base)
            source.write_text('def invalid(\n')
            preflight(base)
            self.assertEqual(source.read_text(),'pass\n')
            self.assertEqual(len(list((base/'.jarvis-runtime/damaged').iterdir())),1)

    def test_save_command_has_explicit_destination_and_runtime_tool(self):
        goal = 'Save document as notes.txt in Documents'
        self.assertEqual(parse(goal).kind, 'task')
        plan = save_plan(goal)
        self.assertEqual(validate_plan(plan)[0]['action'], 'save_file')
        self.assertIsNone(save_plan('Save it somewhere'))
        disabled = Mock(config={'brain':{'visual_fallback':{'enabled':False}}})
        self.assertNotIn('save_file', {row['action'] for row in ToolRegistry(disabled).catalog(goal)})
        disabled.config['brain']['visual_fallback']['enabled'] = True
        self.assertIn('save_file', {row['action'] for row in ToolRegistry(disabled).catalog(goal)})

    def test_new_vision_operations_use_configured_local_model_and_schema(self):
        models = Models.__new__(Models)
        models.client = Mock()
        responses = {
            'visual_ground':{'point':[500,500],'target':'Save','role':'Button','confidence':.99,'is_dialog':True,'password':False,'reason':'shown'},
            'visual_field':{'verified':True,'observed_text':'literal','reason':'transcribed'},
            'visual_dialog':{'kind':'save_as','confidence':.99,'filename_label':'File name','confirm_label':'Save','overwrite_name':'','reason':'shown'}}
        with patch('jarvis.brain_worker.ensure_server', return_value={'models':[{'name':'qwen3-vl:4b'}]}):
            for operation, result in responses.items():
                models.client.post.return_value.json.return_value = {'message':{'content':json.dumps(result)}}
                actual = models.predict({'operation':operation, 'options':{'screen_model':'qwen3-vl:4b'},
                    'goal':'Save', 'step':{'action':'handle_dialog','value':'Save'}, 'screen':frame()})
                self.assertEqual(actual['reason'], result['reason'])
                body = models.client.post.call_args.kwargs['json']
                self.assertEqual(body['model'], 'qwen3-vl:4b')
                self.assertEqual(body['format'], SCHEMAS[operation])
                if operation == 'visual_ground':
                    self.assertEqual(click_point(actual['action']), [.5,.5])

    def test_save_tool_refuses_outside_task_and_read_only_scope(self):
        actions = Mock()
        with self.assertRaisesRegex(ValueError, 'current explicitly authorized'):
            ToolRegistry(actions).execute({'action':'save_file','value':'notes.txt'}, lambda:False)

    def test_save_tool_dispatches_once_inside_authorized_task(self):
        from jarvis.task_state import TaskState
        with tempfile.TemporaryDirectory() as directory:
            actions = Mock()
            actions.task_state = TaskState(directory)
            actions.task_state.start('Save document as notes.txt in Documents','task')
            step = {'action':'save_file','value':'notes.txt','folder':'Documents','content':''}
            actions.brain.visual_fallback.save_file.return_value = 'disk checked'
            self.assertEqual(ToolRegistry(actions).execute(step,lambda:False).evidence,'disk checked')
            actions.brain.validate_remaining.assert_called_once_with([step],actions.task_state.snapshot()['goal'])
            actions.brain.visual_fallback.save_file.assert_called_once()
            actions.execute.assert_not_called()
        actions.allowed_tools = {'read_file'}
        with self.assertRaisesRegex(ValueError, 'outside'):
            ToolRegistry(actions).execute({'action':'save_file','value':'notes.txt'}, lambda:False)


if __name__ == '__main__':
    unittest.main()
