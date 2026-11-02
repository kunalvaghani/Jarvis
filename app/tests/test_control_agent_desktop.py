"""agent-desktop PC backend: envelopes, error/disposition branches, retry discipline, headed gate, shadow, flags."""
import json
import subprocess
import unittest
from pathlib import Path

from jarvis.control.backends import pc_backend, web_backend
from jarvis.control.pc import resolver
from jarvis.control.pc.backend import AgentDesktopExecutor, HeadedGate, kind_of
from jarvis.control.pc.runner import CATEGORIES, Envelope, Runner, Snapshot, parse, to_control_error
from jarvis.control.pc.shadow import READ_COMMANDS, ReadOnlyRunner, ShadowExecutor, controls
from jarvis.control.policy import Policy
from jarvis.control.types import Action, ActionResult, ControlError, ErrorCategory, Observation, Route

FIX = Path(__file__).parent / 'fixtures' / 'agent_desktop'


def fixture(name):
    return (FIX / f'{name}.json').read_text(encoding='utf-8')


def ok(command, data):
    return json.dumps({'version': '2.5', 'ok': True, 'command': command, 'data': data})


def err(command, code, delivery='not_delivered', retry='safe', **extra):
    return json.dumps({'version': '2.5', 'ok': False, 'command': command,
                       'error': {'code': code, 'message': code.lower(), 'disposition': {'delivery': delivery, 'retry': retry},
                                 **extra}})


def acted(command, delivery='delivered_verified'):
    return ok(command, {'disposition': {'delivery': delivery, 'retry': 'unsafe'}, 'steps': []})


class Fake:
    """Scripted agent-desktop: replies per command name, records every argv."""

    def __init__(self, replies):
        self.replies = {k: list(v) if isinstance(v, list) else [v] for k, v in replies.items()}
        self.argv = []

    def __call__(self, argv, **kwargs):
        self.argv.append(argv)
        command = next(a for a in argv[1:] if not a.startswith('--') and a not in ('--session',) and
                       not (argv[argv.index(a) - 1] == '--session'))
        queue = self.replies.get(command) or [err(command, 'INTERNAL', 'delivered_unverified', 'unsafe')]
        out = queue.pop(0) if len(queue) > 1 else queue[0]
        return subprocess.CompletedProcess(argv, 0, out, '')

    def commands(self):
        return [next(a for a in v[1:] if not a.startswith('--')) for v in self.argv]


def executor(replies, gate='deny', policy=None):
    fake = Fake(replies)
    ex = AgentDesktopExecutor(policy or Policy(), Runner(Path('agent-desktop.exe'), run=fake),
                              HeadedGate(gate, lambda q: True), popen=lambda *a, **k: None)
    return ex, fake


def action(name, **params):
    return Action(name, 'test', Route.UIA, params=params)


SNAP = fixture('snapshot')


class Envelopes(unittest.TestCase):
    def test_recorded_envelopes_parse(self):
        self.assertTrue(parse(fixture('launch')).ok)
        snap = Snapshot.model_validate(parse(SNAP).data)
        self.assertEqual([r.role for r in snap.refs()], ['textfield', 'tab', 'button'])
        self.assertTrue(snap.refs()[0].ref_id.startswith('@s1ittgimmq1ziw:e'))
        close = parse(fixture('close'))
        self.assertTrue(close.verified and close.may_have_acted)
        self.assertEqual(parse(fixture('find')).data['match']['role'], 'textfield')

    def test_every_error_code_maps_and_executed_follows_the_disposition(self):
        for code, category in CATEGORIES.items():
            safe = to_control_error(parse(err('click', code)))
            self.assertFalse(safe.executed, code)
            landed = to_control_error(parse(err('click', code, 'delivered_unverified', 'unsafe')))
            self.assertTrue(landed.executed, code)
            if code != 'ACTION_FAILED':
                self.assertEqual(safe.category, category, code)

    def test_action_failed_branches(self):
        verify = parse(err('set-value', 'ACTION_FAILED', 'delivered_unverified', 'unsafe',
                           details={'kind': 'post_action_verification'}))
        self.assertEqual(to_control_error(verify).category, ErrorCategory.VERIFICATION_FAILED)
        blocked = parse(err('click', 'ACTION_FAILED', details={'kind': 'scroll_into_view_unsupported'}))
        self.assertEqual(to_control_error(blocked).category, ErrorCategory.NOT_ACTIONABLE)

    def test_dispositions(self):
        self.assertTrue(parse(acted('click')).verified)
        unverified = parse(acted('click', 'delivered_unverified'))
        self.assertTrue(unverified.delivered and not unverified.verified)
        self.assertFalse(parse(acted('click', 'not_delivered')).delivered)
        self.assertTrue(parse(ok('snapshot', {})).may_have_acted)  # no disposition: never assume nothing happened
        self.assertTrue(parse(err('x', 'STALE_REF')).disposition.safe_to_retry)
        self.assertFalse(parse(err('x', 'STALE_REF', 'delivered_unverified', 'unsafe')).disposition.safe_to_retry)

    def test_unreadable_output_counts_as_maybe_acted(self):
        env = parse('panic: something', 'stderr text')
        self.assertFalse(env.ok)
        self.assertTrue(env.may_have_acted)

    def test_arguments_are_a_list_never_a_shell(self):
        fake = Fake({'click': acted('click')})
        Runner(Path('agent-desktop.exe'), run=fake)(['click', '@s1:e1'])
        self.assertIsInstance(fake.argv[0], list)
        self.assertEqual(fake.argv[0][-1], '@s1:e1')


class Reading(unittest.TestCase):
    def test_window_text_matches_the_legacy_format_and_refs_are_stable(self):
        ex, _ = executor({'snapshot': SNAP})
        first = ex.read_window(920228, 'all')
        self.assertIn('Edit "Text editor" [d1] focused', first.text.replace('Document', 'Edit'))
        self.assertIn('Button "Save" [d2]', first.text)
        self.assertNotIn('Untitled. Unmodified.', first.text)  # offscreen, as legacy hides it
        again = ex.read_window(920228, 'all')
        self.assertEqual(controls(first.text), controls(again.text))
        self.assertEqual(first.scope, 'win-920228')

    def test_kinds_follow_uia_names(self):
        self.assertEqual(kind_of({'role': 'textfield'}), 'Edit')
        self.assertEqual(kind_of({'role': 'tab', 'role_description': 'tab item'}), 'TabItem')
        self.assertEqual(kind_of({'role': 'mystery'}), 'Custom')

    def test_secret_values_are_never_shown(self):
        snap = json.loads(SNAP)
        snap['data']['tree']['children'][0]['children'][0].update(value='hunter2', states=['password'])
        ex, _ = executor({'snapshot': json.dumps(snap)})
        text = ex.read_window(1, 'all').text
        self.assertNotIn('hunter2', text)
        self.assertIn('password', text)


class Acting(unittest.TestCase):
    def read(self, ex):
        ex.read_window(5, 'interactive')
        return 'win-5'

    def test_verified_and_unverified_clicks(self):
        ex, _ = executor({'snapshot': SNAP, 'click': acted('click')})
        result = ex.act(action('click', scope=self.read(ex), ref='d2'))
        self.assertTrue(result.ok and result.verified and result.executed)
        ex, _ = executor({'snapshot': SNAP, 'click': acted('click', 'delivered_unverified')})
        result = ex.act(action('click', scope=self.read(ex), ref='d2'))
        self.assertTrue(result.ok and result.executed and not result.verified)

    def test_stale_ref_refreshes_once_and_retries_only_if_not_delivered(self):
        ex, fake = executor({'snapshot': SNAP, 'click': [err('click', 'STALE_REF'), acted('click')]})
        result = ex.act(action('click', scope=self.read(ex), ref='d2'))
        self.assertTrue(result.ok)
        self.assertEqual(fake.commands().count('click'), 2)
        self.assertEqual(fake.commands().count('snapshot'), 2)

    def test_a_possibly_delivered_failure_is_never_repeated(self):
        ex, fake = executor({'snapshot': SNAP,
                             'click': err('click', 'APP_UNRESPONSIVE', 'delivered_unverified', 'unsafe')})
        result = ex.act(action('click', scope=self.read(ex), ref='d2'))
        self.assertFalse(result.ok)
        self.assertTrue(result.executed)
        self.assertEqual(result.error_category, ErrorCategory.UNCERTAIN)
        self.assertEqual(fake.commands().count('click'), 1)

    def test_unknown_refs_are_stale_without_any_call(self):
        ex, fake = executor({'snapshot': SNAP})
        result = ex.act(action('click', scope='win-5', ref='d9'))
        self.assertEqual(result.error_category, ErrorCategory.STALE_REF)
        self.assertNotIn('click', fake.commands())

    def test_password_fields_are_never_filled(self):
        snap = json.loads(SNAP)
        snap['data']['tree']['children'][0]['children'][0]['states'] = ['password']
        ex, fake = executor({'snapshot': json.dumps(snap)})
        result = ex.act(action('set_value', scope=self.read(ex), ref='d1', value='x'))
        self.assertEqual(result.error_category, ErrorCategory.POLICY_DENIED)
        self.assertNotIn('set-value', fake.commands())

    def test_toggle_with_a_desired_state_is_idempotent(self):
        ex, fake = executor({'snapshot': SNAP, 'check': acted('check')})
        ex.act(action('toggle', scope=self.read(ex), ref='d2', state=1))
        self.assertIn('check', fake.commands())
        self.assertNotIn('toggle', fake.commands())


class HeadedInput(unittest.TestCase):
    EMPTY = ok('find', {'match': {'ref_id': '@s1:e1', 'role': 'textfield', 'name': 'Text editor', 'value': ''}})
    FULL = ok('find', {'match': {'ref_id': '@s1:e1', 'role': 'textfield', 'name': 'Text editor', 'value': 'old'}})

    def test_typing_into_an_empty_field_stays_headless(self):
        ex, fake = executor({'find': self.EMPTY, 'set-value': acted('set-value')}, gate='deny')
        result = ex.act(action('type', handle=7, text='hello'))
        self.assertTrue(result.ok and result.verified)
        self.assertFalse(any('--headed' in a for a in fake.argv))

    def test_physical_typing_needs_the_gate_and_is_never_a_fallback(self):
        ex, fake = executor({'find': self.FULL}, gate='deny')
        result = ex.act(action('type', handle=7, text='more'))
        self.assertEqual(result.error_category, ErrorCategory.APPROVAL_DENIED)
        self.assertFalse(any('--headed' in a for a in fake.argv))
        ex, fake = executor({'find': self.FULL, 'type': acted('type', 'delivered_unverified')}, gate='allow')
        self.assertTrue(ex.act(action('type', handle=7, text='more')).ok)
        self.assertTrue(any('--headed' in a for a in fake.argv))

    def test_blocked_shortcuts_stay_blocked(self):
        ex, fake = executor({'press': err('press', 'POLICY_DENIED')}, gate='allow')
        result = ex.act(action('key', handle=7, text='alt+f4'))
        self.assertEqual(result.error_category, ErrorCategory.POLICY_DENIED)
        self.assertFalse(any('--force' in a for a in fake.argv))
        self.assertEqual(fake.commands().count('press'), 1)

    def test_gate_asks_once_per_window(self):
        asked = []
        gate = HeadedGate('ask', lambda q: asked.append(q) or True)
        gate.require('win-1', 'typing')
        gate.require('win-1', 'typing')
        self.assertEqual(len(asked), 1)
        with self.assertRaises(ControlError):
            HeadedGate('ask', None).require('win-2', 'typing')


class Launching(unittest.TestCase):
    APPS = {'Spotify': 'SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify', 'Notepad': 'Microsoft.WindowsNotepad_8wekyb3d8bbwe!App',
            'Visual Studio Code': 'Microsoft.VisualStudioCode', 'Discord': 'com.squirrel.Discord.Discord',
            'Blender 5.2': 'D:\\blender-launcher.exe'}

    def test_resolver(self):
        self.assertTrue(resolver.resolve('spotify', self.APPS).store)
        self.assertEqual(resolver.resolve('spotfy', self.APPS).name, 'Spotify')
        self.assertLess(resolver.resolve('spotfy', self.APPS).score, 1)
        self.assertEqual(resolver.resolve('vs code', self.APPS).image, 'Code.exe')
        self.assertEqual(resolver.resolve('paint', self.APPS).target, 'mspaint.exe')
        self.assertEqual(resolver.resolve('blender', self.APPS).target, 'D:\\blender-launcher.exe')
        self.assertIsNone(resolver.resolve('zzqqxx', self.APPS))

    def test_policy_still_decides_which_apps_may_launch(self):
        ex, fake = executor({'list-windows': ok('list-windows', [])},
                            policy=Policy(allowed_apps=frozenset({'notepad.exe'})))
        original = resolver.start_apps
        resolver.start_apps = lambda: self.APPS
        try:
            result = ex.act(action('launch', app='spotify'))
        finally:
            resolver.start_apps = original
        self.assertEqual(result.error_category, ErrorCategory.POLICY_DENIED)
        self.assertNotIn('launch', fake.commands())

    def test_launch_returns_the_new_window(self):
        ex, fake = executor({'list-windows': ok('list-windows', []),
                             'launch': ok('launch', {'app': 'mspaint.exe', 'pid': 1,
                                                     'window': {'id': 'w-4242', 'title': 'Untitled - Paint'}})})
        result = ex.act(action('launch', app='paint'))
        self.assertTrue(result.ok)
        self.assertEqual(result.state['handle'], 4242)


class Shadow(unittest.TestCase):
    def test_read_only_runner_refuses_every_write(self):
        fake = Fake({})
        runner = ReadOnlyRunner(Path('agent-desktop.exe'), run=fake)
        for command in ('click', 'set-value', 'type', 'press', 'launch', 'close-app', 'toggle', 'focus-window',
                        'clipboard-set', 'batch'):
            with self.assertRaises(ControlError):
                runner([command, '@s1:e1'])
        with self.assertRaises(ControlError):
            runner(['snapshot'], headed=True)
        self.assertEqual(fake.argv, [])
        self.assertIn('snapshot', READ_COMMANDS)

    def test_shadow_returns_legacy_results_and_never_acts(self):
        class Legacy:
            route = Route.UIA

            def act(self, a):
                return ActionResult(a.action_id, True, Route.UIA, text='Button "Save" [u3]', state={'scope': 'win-5'},
                                    executed=a.name != 'read_window', verified=True)

            def observe(self, scope=None, **o):
                return Observation(Route.UIA, 'win-5', 'Button "Save" [u3]')

        fake = Fake({'snapshot': SNAP})
        candidate = AgentDesktopExecutor(Policy(), ReadOnlyRunner(Path('agent-desktop.exe'), run=fake))
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'pc.jsonl'
            shadow = ShadowExecutor(Legacy(), candidate, log)
            shadow.observe('win-5')
            result = shadow.act(action('click', scope='win-5', ref='u3'))
            self.assertTrue(result.ok)
            rows = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(set(fake.commands()), {'snapshot'})
        self.assertEqual(rows[0]['named_matched'], 1)
        self.assertTrue(rows[1]['candidate_found_same_target'])
        self.assertNotIn('Save', json.dumps(rows))  # no names in the shadow log


class Flags(unittest.TestCase):
    def test_defaults_and_rollback(self):
        self.assertEqual(pc_backend({}, {}), 'legacy')
        self.assertEqual(pc_backend({'control': {'pc_backend': 'agent_desktop'}}, {}), 'agent_desktop')
        self.assertEqual(pc_backend({'control': {'pc_backend': 'agent_desktop'}}, {'JARVIS_PC_BACKEND': 'legacy'}),
                         'legacy')
        self.assertEqual(pc_backend({'control': {'pc_backend': 'bogus'}}, {}), 'legacy')
        self.assertEqual(web_backend({}, {'JARVIS_WEB_BACKEND': 'shadow'}), 'shadow')

    def test_service_builds_the_selected_executor(self):
        from jarvis.control.service import ControlService
        from jarvis.control.settings import ControlSettings
        from unittest import mock
        for value, kind in (('legacy', 'UIAExecutor'), ('shadow', 'ShadowExecutor'), ('agent_desktop', 'AgentDesktopExecutor')):
            with mock.patch.dict('os.environ', {'JARVIS_PC_BACKEND': value}):
                service = ControlService(ControlSettings())
                self.assertEqual(type(service.uia().inner).__name__, kind)
        with mock.patch.dict('os.environ', {'JARVIS_PC_BACKEND': 'shadow'}):
            inner = ControlService(ControlSettings()).uia().inner
            self.assertIsInstance(inner.candidate.run, ReadOnlyRunner)


if __name__ == '__main__':
    unittest.main()


class FastPaths(unittest.TestCase):
    def test_matching(self):
        from jarvis.control.pc.fast_paths import match
        self.assertEqual(match('minimise Spotify'), ('minimize', 'Spotify'))
        self.assertEqual(match('Maximize the VS Code window'), ('maximize', 'VS Code'))
        self.assertEqual(match('copy hello world to the clipboard'), ('clipboard', 'hello world'))
        self.assertIsNone(match('open spotify and play jazz'))

    def test_window_op_is_verified_by_a_fresh_read(self):
        from jarvis.control.pc import fast_paths
        minimized = ok('list-windows', [{'id': 'w-1', 'title': 'Spotify', 'minimized': True}])
        fake = Fake({'minimize': acted('minimize'), 'list-windows': minimized})
        with unittest.mock.patch.object(resolver, 'start_apps', lambda: Launching.APPS):
            answer = fast_paths.run('minimize spotify', lambda k, d: True, Runner(Path('a.exe'), run=fake))
        self.assertIn('Minimized Spotify', answer)
        still = ok('list-windows', [{'id': 'w-1', 'title': 'Spotify', 'minimized': False}])
        fake = Fake({'minimize': acted('minimize', 'delivered_unverified'), 'list-windows': still})
        with unittest.mock.patch.object(resolver, 'start_apps', lambda: Launching.APPS):
            with self.assertRaises(ControlError):
                fast_paths.run('minimize spotify', lambda k, d: True, Runner(Path('a.exe'), run=fake))

    def test_close_is_graceful_and_clipboard_asks_first(self):
        from jarvis.control.pc import fast_paths
        fake = Fake({'close-app': acted('close-app'), 'list-windows': ok('list-windows', [])})
        with unittest.mock.patch.object(resolver, 'start_apps', lambda: Launching.APPS):
            self.assertIn('Closed', fast_paths.run('close notepad', lambda k, d: True, Runner(Path('a.exe'), run=fake)))
        self.assertFalse(any('--force' in a for a in fake.argv))
        fake = Fake({})
        with self.assertRaises(ControlError):
            fast_paths.run('copy secret to the clipboard', lambda k, d: False, Runner(Path('a.exe'), run=fake))
        self.assertEqual(fake.argv, [])
        fake = Fake({'clipboard-set': acted('clipboard-set'), 'clipboard-get': ok('clipboard-get', {'type': 'text', 'text': 'abc'})})
        self.assertIn('Copied', fast_paths.run('copy abc to the clipboard', lambda k, d: True,
                                              Runner(Path('a.exe'), run=fake)))


class Faults(unittest.TestCase):
    def test_a_hung_agent_desktop_is_uncertain_and_never_retried(self):
        calls = []

        def hang(argv, **kwargs):
            calls.append(argv)
            raise subprocess.TimeoutExpired(argv, 1)
        ex = AgentDesktopExecutor(Policy(), Runner(Path('a.exe'), run=hang))
        ex.scopes['win-5'] = __import__('jarvis.control.pc.backend', fromlist=['_Scope'])._Scope(5)
        from jarvis.control.pc.runner import Ref
        ex.scopes['win-5'].by_ref['d1'] = Ref(ref_id='@s1:e1', role='button', name='OK')
        result = ex.act(action('click', scope='win-5', ref='d1'))
        self.assertEqual(result.error_category, ErrorCategory.UNCERTAIN)
        self.assertTrue(result.executed)
        self.assertEqual(len(calls), 1)

    def test_missing_binary_and_crashed_process(self):
        def missing(argv, **kwargs):
            raise FileNotFoundError(argv[0])
        with self.assertRaises(ControlError) as caught:
            Runner(Path('nope.exe'), run=missing)(['status'])
        self.assertEqual(caught.exception.category, ErrorCategory.TOOL_ERROR)
        crashed = Runner(Path('a.exe'), run=lambda argv, **k: subprocess.CompletedProcess(argv, -1073741819, '', 'boom'))
        env = crashed(['click', '@s1:e1'])
        self.assertFalse(env.ok)
        self.assertTrue(env.may_have_acted)  # a crash mid-action is never treated as "nothing happened"


import unittest.mock  # noqa: E402
