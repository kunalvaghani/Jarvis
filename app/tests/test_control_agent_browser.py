"""agent-browser web backend: boundaries + policy on every call, error branches, confirmations, URL policy, shadow."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from jarvis.control.policy import Policy
from jarvis.control.types import Action, ControlError, ErrorCategory, Route
from jarvis.control.web.agent_browser_backend import (DENY, AgentBrowserExecutor, BrowserRunner, parse, render,
                                                      to_error, write_policy)
from jarvis.control.web.shadow import ReadOnlyBrowserRunner

FIX = Path(__file__).parent / 'fixtures' / 'agent_browser'
APP = Path(__file__).resolve().parents[1]


def fixture(name):
    return (FIX / f'{name}.json').read_text(encoding='utf-8')


def ok(data, boundary=None):
    body = {'success': True, 'data': data, 'error': None}
    if boundary:
        body['_boundary'] = {'nonce': 'n', 'origin': boundary}
    return json.dumps(body)


def fail(message):
    return json.dumps({'success': False, 'data': None, 'error': message})


class Fake:
    def __init__(self, replies):
        self.replies = {k: list(v) if isinstance(v, list) else [v] for k, v in replies.items()}
        self.argv = []

    def __call__(self, argv, **kwargs):
        self.argv.append(argv)
        rest = argv[argv.index('--session') + 2:]
        rest = [a for a in rest if a not in ('--headed',)]
        while rest and rest[0] in ('--profile', '--executable-path'):
            rest = rest[2:]
        key = ' '.join(rest[:2]) if rest[:1] in (['tab'], ['get']) else rest[0]
        queue = self.replies.get(key) or self.replies.get(rest[0]) or [fail('unscripted ' + key)]
        out = queue.pop(0) if len(queue) > 1 else queue[0]
        return subprocess.CompletedProcess(argv, 0, out, '')

    def commands(self):
        out = []
        for argv in self.argv:
            rest = argv[argv.index('--session') + 2:]
            rest = [a for a in rest if a != '--headed']
            while rest and rest[0] in ('--profile', '--executable-path'):
                rest = rest[2:]
            out.append(rest[0])
        return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.policy_file = write_policy(Path(self.tmp.name) / 'policy.json')

    def tearDown(self):
        self.tmp.cleanup()

    def executor(self, replies, confirm=None, policy=None):
        fake = Fake({'tab list': ok({'tabs': [{'tabId': 't1', 'title': 'x', 'url': 'https://example.com/', 'active': True}]}),
                     **replies})
        runner = BrowserRunner(Path('agent-browser.exe'), policy_file=self.policy_file, run=fake, headed=False)
        return AgentBrowserExecutor(policy or Policy(), runner, confirm), fake


def act(name, **params):
    return Action(name, 'test', Route.BROWSER, params=params)


class EveryCall(Base):
    def test_boundaries_and_policy_are_on_every_call(self):
        ex, fake = self.executor({'open': fixture('open'), 'get url': fixture('url'), 'snapshot': fixture('snapshot')})
        ex.act(act('navigate', url='https://example.com'))
        ex.act(act('read_page', filter='all'))
        self.assertTrue(fake.argv)
        for argv in fake.argv:
            self.assertIn('--content-boundaries', argv)
            self.assertIn('--action-policy', argv)
            self.assertEqual(argv[argv.index('--action-policy') + 1], str(self.policy_file))
            self.assertIsInstance(argv, list)

    def test_policy_file_denies_script_and_credential_actions_and_confirms_uploads(self):
        body = json.loads(self.policy_file.read_text(encoding='utf-8'))
        for name in ('evaluate', 'cookies_set', 'state_save', 'route', 'credentials_set', 'auth_login'):
            self.assertIn(name, body['deny'])
        self.assertIn('upload', body['confirm'])
        self.assertEqual(set(DENY), set(body['deny']))

    def test_page_content_without_boundaries_is_refused(self):
        ex, _ = self.executor({'snapshot': ok({'snapshot': '- link "x" [ref=e1]'})})
        result = ex.act(act('read_page', filter='all'))
        self.assertFalse(result.ok)
        self.assertEqual(result.error_category, ErrorCategory.POLICY_DENIED)


class Reading(Base):
    def test_snapshot_renders_in_the_legacy_format(self):
        lines = render(json.loads(fixture('snapshot_full'))['data']['snapshot'], refs := {})
        self.assertIn('link "Learn more" [ref_1]', '\n'.join(lines))
        self.assertTrue(any(line.strip().startswith('text "This domain') for line in lines))
        self.assertEqual(refs, {'ref_1': '@e1'})

    def test_states_are_kept(self):
        lines = render('- checkbox "Agree" [checked] [ref=e4]\n- textbox "Name" [ref=e5]', {})
        self.assertEqual(lines[0], 'checkbox "Agree" checked [ref_4]')


class Errors(Base):
    def test_branches(self):
        stale = to_error(parse(fixture('click_error')), acting=True)
        self.assertEqual((stale.category, stale.executed), (ErrorCategory.STALE_REF, False))
        denied = to_error(parse(fail("Action 'evaluate' denied by policy: x")), acting=True)
        self.assertEqual((denied.category, denied.executed), (ErrorCategory.POLICY_DENIED, False))
        unknown = to_error(parse(fail('Target closed unexpectedly')), acting=True)
        self.assertEqual((unknown.category, unknown.executed), (ErrorCategory.UNCERTAIN, True))
        read = to_error(parse(fail('Target closed unexpectedly')), acting=False)
        self.assertFalse(read.executed)
        self.assertFalse(parse('garbage').success)

    def test_a_failed_click_is_uncertain_and_not_repeated(self):
        ex, fake = self.executor({'snapshot': fixture('snapshot'), 'click': fail('Target closed unexpectedly')})
        ex.act(act('read_page'))
        result = ex.act(act('left_click', ref='ref_1'))
        self.assertEqual(result.error_category, ErrorCategory.UNCERTAIN)
        self.assertTrue(result.executed)
        self.assertEqual(fake.commands().count('click'), 1)

    def test_unknown_refs_never_reach_the_browser(self):
        ex, fake = self.executor({})
        result = ex.act(act('left_click', ref='ref_9'))
        self.assertEqual(result.error_category, ErrorCategory.STALE_REF)
        self.assertNotIn('click', fake.commands())


class Confirmations(Base):
    def test_denied_confirmation_does_nothing(self):
        ex, fake = self.executor({'snapshot': fixture('snapshot'), 'click': fixture('confirm_required'),
                                  'deny': ok({'denied': True})}, confirm=lambda q: False)
        ex.act(act('read_page'))
        result = ex.act(act('left_click', ref='ref_1'))
        self.assertEqual(result.error_category, ErrorCategory.APPROVAL_DENIED)
        self.assertIn('deny', fake.commands())
        self.assertNotIn('confirm', fake.commands())

    def test_granted_confirmation_proceeds(self):
        asked = []
        ex, fake = self.executor({'snapshot': fixture('snapshot'), 'click': fixture('confirm_required'),
                                  'confirm': fixture('click')}, confirm=lambda q: asked.append(q) or True)
        ex.act(act('read_page'))
        self.assertTrue(ex.act(act('left_click', ref='ref_1')).ok)
        self.assertEqual(len(asked), 1)
        self.assertIn('confirm', fake.commands())


class UrlPolicy(Base):
    def test_blocked_urls_are_never_opened(self):
        ex, fake = self.executor({}, policy=Policy(blocked_domains=frozenset({'example.com'})))
        result = ex.act(act('navigate', url='https://example.com'))
        self.assertFalse(result.ok)
        self.assertNotIn('open', fake.commands())

    def test_a_redirect_to_a_blocked_site_is_reported(self):
        ex, _ = self.executor({'open': fixture('open'), 'get url': fixture('url')},
                              policy=Policy(blocked_domains=frozenset({'iana.org'})))
        result = ex.act(act('navigate', url='https://example.com'))
        self.assertFalse(result.ok)


class ShadowAndSecrets(unittest.TestCase):
    def test_web_shadow_runner_only_reads(self):
        fake = Fake({})
        runner = ReadOnlyBrowserRunner(Path('agent-browser.exe'), run=fake, headed=False)
        for args in (['click', '@e1'], ['fill', '@e1', 'x'], ['press', 'Enter'], ['upload', '@e1', 'f'],
                     ['eval', '1'], ['cookies', 'get'], ['get', 'cookies']):
            with self.assertRaises(ControlError):
                runner(args)
        self.assertEqual(fake.argv, [])

    def test_no_browser_state_or_keys_are_tracked_by_git(self):
        tracked = subprocess.run(['git', 'ls-files'], cwd=APP, capture_output=True, text=True).stdout.splitlines()
        bad = [f for f in tracked if f.startswith('secrets/') or f.endswith('.key') or 'agent-browser' in f.lower()
               and ('state' in f.lower() or 'auth' in f.lower())]
        self.assertEqual(bad, [])
        ignored = subprocess.run(['git', 'check-ignore', '-q', 'secrets/agent-browser.key'], cwd=APP)
        self.assertEqual(ignored.returncode, 0)

    def test_service_builds_the_selected_web_executor(self):
        from unittest import mock
        from jarvis.control.service import ControlService
        from jarvis.control.settings import ControlSettings
        with mock.patch.dict('os.environ', {'JARVIS_WEB_BACKEND': 'agent_browser'}):
            inner = ControlService(ControlSettings()).browser().inner
        self.assertEqual(type(inner).__name__, 'AgentBrowserExecutor')
        self.assertEqual(inner.run.session, 'jarvis-test')


if __name__ == '__main__':
    unittest.main()


class ReadScope(Base):
    def test_full_reads_keep_page_text_and_only_interactive_reads_compact(self):
        ex, fake = self.executor({'snapshot': fixture('snapshot_full')})
        text = ex.act(act('read_page', filter='all')).text
        self.assertIn('text "This domain is for use', text)
        ex.act(act('read_page', filter='interactive'))
        snaps = [a[a.index('snapshot'):] for a in fake.argv if 'snapshot' in a]
        self.assertEqual(snaps, [['snapshot'], ['snapshot', '-i', '-c']])
