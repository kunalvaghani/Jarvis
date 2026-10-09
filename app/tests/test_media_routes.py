import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jarvis.actions import Actions
from jarvis.commands import Command, parse
from jarvis.engine import Engine
from jarvis import media_ui
from jarvis.ui_controls import UIControls, _category
from test_ui_controls import FakeRunner, control


class MediaRoutesTests(unittest.TestCase):
    def make_ui(self, values, platform='youtube'):
        runner = FakeRunner(values)
        runner.title = 'Demo - YouTube - Google Chrome' if platform == 'youtube' else 'Spotify'
        original = runner.__call__
        def run(request, cancelled):
            result = original(request, cancelled)
            if request['operation'] == 'list':
                result['context'] = json.dumps([r'C:\Apps\chrome.exe' if platform == 'youtube' else r'C:\Apps\Spotify.exe'])
            return result
        ui = UIControls(type('Desktop', (), {'target': None})(), runner=run)
        ui._handle = lambda: 123
        return ui, runner

    def test_play_first_video_bypasses_planner_and_preserves_ordinal(self):
        for text in ['play the first video', 'play first video.', 'open first video', 'select first video on YouTube']:
            self.assertEqual(parse(text), Command('select_context', '1:video', 'select'))
        self.assertEqual(parse('play second video'), Command('select_context', '2:video', 'select'))
        ui, runner = self.make_ui([control('Cats tutorial', 1, 'Hyperlink', [200, 200, 500, 230]),
                                  control('Dogs tutorial', 2, 'Hyperlink', [200, 300, 500, 330])])
        result = ui.execute(parse('play first video'))
        self.assertNotIn('option number', result)
        self.assertEqual(runner.requests[-1]['control']['id'], [1])

    def test_google_video_result_is_selectable_and_duplicates_do_not_change_number(self):
        values = [control('Song (Official Video) YouTube Artist 235.8Cr views', 1, 'Hyperlink', [200, 100, 500, 150]),
                  control('Song (Official Video) by Artist on YouTube. Play on Google. 3:38', 2, 'Button', [200, 155, 500, 190]),
                  control('Other song YouTube Artist', 3, 'Hyperlink', [200, 250, 500, 290])]
        selected = _category(values, 'video', 'Song - Google Search - Chrome')
        self.assertEqual([x['id'] for x in selected], [[1], [3]])

    def test_player_navigation_is_not_counted_as_video(self):
        values = [control('Play (k)', 1), control('Subscribe', 2, 'Hyperlink'),
                  control('Real tutorial', 3, 'Hyperlink', [200, 200, 500, 230])]
        self.assertEqual(_category(values, 'video', 'YouTube'), values[2:])

    def test_media_voice_commands(self):
        examples = {
            'search for robot tutorials on YouTube': Command('media_search', 'robot tutorials', 'youtube'),
            'Spotify search for jazz': Command('media_search', 'jazz', 'spotify'),
            'search for jazz': Command('context_search', 'jazz'),
            'pause on YouTube': Command('media_control', 'pause', 'youtube'),
            'resume the video': Command('media_control', 'play', 'youtube'),
            'next video': Command('media_control', 'next', 'youtube'),
            'rewind 30 seconds on YouTube': Command('media_control', 'seek_-30', 'youtube'),
            'seek to 50 percent on YouTube': Command('media_control', 'position_50', 'youtube'),
            'set volume to 40 percent on YouTube': Command('media_control', 'volume_40', 'youtube'),
            'volume up on YouTube': Command('media_control', 'volume_up', 'youtube'),
            'captions on YouTube': Command('media_control', 'captions', 'youtube'),
            'captions on on YouTube': Command('media_control', 'captions_on', 'youtube'),
            'toggle captions on YouTube': Command('media_control', 'captions', 'youtube'),
            'speed up on YouTube': Command('media_control', 'speed_up', 'youtube'),
            'exit full screen on YouTube': Command('media_control', 'exit_fullscreen', 'youtube'),
            'show queue on Spotify': Command('media_control', 'queue', 'spotify'),
            'show lyrics on Spotify': Command('media_control', 'lyrics', 'spotify'),
            'like this song on Spotify': Command('media_control', 'like', 'spotify'),
            'pause Spotify': Command('spotify_control', 'pause'),
            'play first song on Spotify': Command('select_context', '1:track', 'play'),
            'select second track': Command('select_context', '2:track', 'select'),
            'select option number 1.': Command('choose_control', '1'),
            'full screen': Command('media_control', 'fullscreen', 'youtube'),
            'open Spotify web player': Command('browse', 'spotify', 'chrome'),
        }
        for phrase, expected in examples.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(parse(phrase), expected)

    def test_final_transcript_only_dispatches_once(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.feed('jarvis pause on youtube')
        self.assertEqual(sent, [])
        engine.feed('jarvis pause on youtube', final=True)
        self.assertEqual(sent, [Command('media_control', 'pause', 'youtube')])

    def test_spotify_open_prefers_installed_app_over_site(self):
        with tempfile.TemporaryDirectory() as folder:
            actions = Actions({'files_root': 'files', 'apps': {'spotify': {'shell_id': 'Spotify!App'}}}, folder, lambda *args: None)
            try:
                with patch('jarvis.actions.subprocess.Popen') as launch:
                    self.assertIn('native Spotify', actions.execute(parse('open spotify')))
                launch.assert_called_once_with(['explorer.exe', r'shell:AppsFolder\Spotify!App'], shell=False)
            finally:
                actions.close()

    def test_scoping_requires_real_browser_or_spotify_process(self):
        for path, title in [(r'C:\Apps\notepad.exe', 'YouTube'), (r'C:\Apps\chrome.exe', 'YouTube - Google Search - Google Chrome'),
                            (r'C:\Apps\chrome.exe', 'Spotify - Google Chrome')]:
            self.assertIsNone(media_ui.platform_of({'context': json.dumps([path]), 'title': title}))

    def test_wrong_app_is_not_controlled(self):
        ui, runner = self.make_ui([control('Pause (k)', 1)], 'spotify')
        with patch.object(media_ui, 'find_media_handle', return_value=None):
            with self.assertRaisesRegex(ValueError, 'foreground'):
                media_ui.control(ui, 'youtube', 'pause')
        self.assertEqual([x['operation'] for x in runner.requests], ['list'])

    def test_pause_uses_one_exact_player_control(self):
        ui, runner = self.make_ui([control('Pause (k)', 1), control('Play recommendation', 2)])
        media_ui.control(ui, 'youtube', 'pause')
        self.assertEqual([x['operation'] for x in runner.requests], ['list', 'activate'])
        self.assertEqual(runner.requests[-1]['control']['id'], [1])

    def test_already_paused_does_not_toggle(self):
        ui, runner = self.make_ui([control('Play (k)', 1)])
        self.assertIn('already', media_ui.control(ui, 'youtube', 'pause'))
        self.assertEqual(len(runner.requests), 1)

    def test_duplicate_controls_are_not_guessed(self):
        ui, runner = self.make_ui([control('Pause (k)', 1), control('Pause (k)', 2)])
        with self.assertRaisesRegex(ValueError, 'Multiple'):
            media_ui.control(ui, 'youtube', 'pause')
        self.assertEqual(len(runner.requests), 1)

    def test_search_current_exact_field_and_no_playback(self):
        field = control('Search', 1, 'Edit')
        ui, runner = self.make_ui([field, control('Address and search bar', 2, 'Edit')])
        media_ui.search_current(ui, 'youtube', 'a+b & robots')
        request = runner.requests[-1]
        self.assertEqual(request['operation'], 'media_search_field')
        self.assertEqual(request['content'], 'a+b & robots')
        self.assertEqual(request['control'], field)

    def test_wrong_site_search_returns_before_any_write(self):
        ui, runner = self.make_ui([control('Search', 1, 'Edit')], 'spotify')
        with patch.object(media_ui, 'find_media_handle', return_value=None):
            self.assertIsNone(media_ui.search_current(ui, 'youtube', 'cats'))
        self.assertEqual(len(runner.requests), 1)

    def test_cancelled_controls_do_not_inspect_or_write(self):
        ui, runner = self.make_ui([control('Pause (k)', 1)])
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            media_ui.control(ui, 'youtube', 'pause', lambda: True)
        self.assertEqual(runner.requests, [])

    def test_shortcuts_require_a_player_and_do_not_retry(self):
        ui, runner = self.make_ui([])
        with self.assertRaisesRegex(ValueError, 'player'):
            media_ui.control(ui, 'youtube', 'next')
        ui, runner = self.make_ui([control('Pause (k)', 1)])
        media_ui.control(ui, 'youtube', 'seek_30')
        self.assertEqual(runner.requests[-1]['operation'], 'media_key')
        self.assertEqual(media_ui.key_for('youtube', 'seek_30'), 'lll')
        with self.assertRaisesRegex(ValueError, 'multiples'):
            media_ui.key_for('youtube', 'seek_7')

    def test_frame_steps_require_paused_player(self):
        ui, runner = self.make_ui([control('Pause (k)', 1)])
        with self.assertRaisesRegex(ValueError, 'Pause'):
            media_ui.control(ui, 'youtube', 'next_frame')
        self.assertEqual(len(runner.requests), 1)

    def test_search_setvalue_failure_never_types_or_submits(self):
        element = Mock()
        element.iface_value.CurrentIsReadOnly = False
        element.iface_value.SetValue.side_effect = RuntimeError('uncertain write')
        with self.assertRaisesRegex(RuntimeError, 'uncertain'):
            media_ui.fill_search(element, control('Search', 1, 'Edit'), 'cats', 123)
        element.iface_value.SetValue.assert_called_once_with('cats')
        element.type_keys.assert_not_called()

    def test_search_verifies_exact_text_before_one_submission(self):
        element = Mock()
        element.iface_value.CurrentIsReadOnly = False
        element.iface_value.CurrentValue = 'cats'
        with patch('win32gui.GetForegroundWindow', return_value=123):
            media_ui.fill_search(element, control('Search', 1, 'Edit'), 'cats', 123)
        element.iface_value.SetValue.assert_called_once_with('cats')
        element.type_keys.assert_called_once_with('{ENTER}', set_foreground=False)

    def test_search_focus_change_does_not_submit(self):
        element = Mock()
        element.iface_value.CurrentIsReadOnly = False
        element.iface_value.CurrentValue = 'cats'
        with patch('win32gui.GetForegroundWindow', return_value=999):
            with self.assertRaisesRegex(ValueError, 'Focus changed'):
                media_ui.fill_search(element, control('Search', 1, 'Edit'), 'cats', 123)
        element.type_keys.assert_not_called()

    def test_slider_value_uses_observed_native_range(self):
        element = Mock()
        interface = element.iface_range_value
        interface.CurrentIsReadOnly = False
        interface.CurrentMinimum, interface.CurrentMaximum, interface.CurrentValue = 0, 200, 100
        self.assertIn('50 percent', media_ui.set_range(element, control('Seek', 1, 'Slider'), '50'))
        interface.SetValue.assert_called_once_with(100)

    def test_slider_failure_is_not_replayed(self):
        element = Mock()
        interface = element.iface_range_value
        interface.CurrentIsReadOnly = False
        interface.CurrentMinimum, interface.CurrentMaximum, interface.CurrentValue = 0, 100, 0
        with self.assertRaisesRegex(ValueError, 'not verified'):
            media_ui.set_range(element, control('Volume', 1, 'Slider'), '50')
        interface.SetValue.assert_called_once_with(50)

    def test_catalog_and_checkpoint_retain_media_platform(self):
        from jarvis.brain import validate_plan
        from jarvis.task_recovery import action_key
        from jarvis.tools import ToolRegistry
        actions = Mock()
        step = {'action': 'media_control', 'value': 'pause', 'platform': 'youtube', 'expected': 'Video paused'}
        validate_plan({'steps': [step]})
        ToolRegistry(actions).execute(step, lambda: False)
        actions.execute.assert_called_once_with(Command('media_control', 'pause', 'youtube'), unittest.mock.ANY)
        self.assertNotEqual(action_key(step), action_key({**step, 'platform': 'spotify'}))

    def test_saved_song_is_not_unsaved_by_a_toggle_shortcut(self):
        ui, runner = self.make_ui([control('Remove from your Liked Songs', 1)], 'spotify')
        self.assertIn('already saved', media_ui.control(ui, 'spotify', 'like'))
        self.assertEqual(len(runner.requests), 1)

    def test_media_action_failure_is_not_replayed(self):
        ui, runner = self.make_ui([control('Pause (k)', 1)])
        original = ui.runner
        def run(request, cancelled):
            result = original(request, cancelled)
            if request['operation'] == 'activate':
                raise RuntimeError('uncertain click')
            return result
        ui.runner = run
        with self.assertRaisesRegex(RuntimeError, 'uncertain'):
            media_ui.control(ui, 'youtube', 'pause')
        self.assertEqual([x['operation'] for x in runner.requests], ['list', 'activate'])

    def test_changed_com_apartment_does_not_uninitialize_another_library(self):
        from jarvis import spotify
        error = OSError('COM mode already set')
        error.winerror = -2147417850
        with patch('comtypes.CoInitialize', side_effect=error), patch('comtypes.CoUninitialize') as uninit, patch('pycaw.pycaw.AudioUtilities.GetAllSessions', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'audio session'):
                spotify.volume('50')
        uninit.assert_not_called()

    def test_spotify_track_order_ignores_sidebar_playlists(self):
        track = dict(control('Track one 3:38', 2, 'DataItem', [200, 200, 500, 240]), context='Songs')
        ui, runner = self.make_ui([control('My playlist', 1, 'ListItem'), track], 'spotify')
        ui.execute(parse('play first song on Spotify'))
        self.assertEqual(runner.requests[-1]['control']['id'], [2])
        self.assertEqual(runner.requests[-1]['verb'], 'play')

    def test_background_media_window_is_resolved_before_an_action(self):
        ui, runner = self.make_ui([control('Search', 1, 'Edit')], 'spotify')
        with patch.object(media_ui, 'find_media_handle', return_value=456):
            handle, snapshot = media_ui.snapshot_for(ui, lambda: False, 'youtube')
        self.assertEqual(handle, 456)
        self.assertEqual([x['operation'] for x in runner.requests], ['list', 'list'])
        self.assertEqual(runner.requests[-1]['handle'], 456)


if __name__ == '__main__':
    unittest.main()
