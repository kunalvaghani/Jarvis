"""Gate 1: every control-benchmark oracle tells a known-good state from a known-bad one (oracles cannot lie)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

LIVE = Path(__file__).resolve().parents[1] / 'benchmarks' / 'live'
sys.path.insert(0, str(LIVE))

import control_cases as cc  # noqa: E402


class Run:
    def __init__(self, answer='', tools=(), final_page=''):
        self.answer = answer
        self.row = {'tools': list(tools), 'final_page': final_page, 'answer': answer}


class World:
    """Fake readers for one state of the PC."""

    def __init__(self, files=None, dirs=(), processes=(), windows=(), clipboard='', dnd=False, pages=None, media=()):
        self.readers = {'file': lambda p: (files or {}).get(Path(p).name), 'isdir': lambda p: Path(p).name in dirs,
                        'processes': lambda: list(processes), 'windows': lambda: list(windows),
                        'clipboard': lambda: clipboard, 'dnd_on': lambda: dnd,
                        'google_page': lambda url: (pages or {}).get(url, ''), 'media': lambda: list(media),
                        'settle': lambda: 0}

    def __enter__(self):
        self.patch = mock.patch.dict(cc.READERS, self.readers)
        self.patch.start()
        return self

    def __exit__(self, *exc):
        self.patch.stop()


T = Path('D:/t')


class Factories(unittest.TestCase):
    def check(self, oracle, good, bad, run=None, bad_run=None):
        with good:
            self.assertEqual(oracle(run or Run()), [], 'known-good state must pass')
        with bad:
            self.assertTrue(oracle(bad_run or run or Run()), 'known-bad state must fail')

    def test_file_oracles(self):
        self.check(cc.file_equals(T / 'a.txt', 'x\ny'), World({'a.txt': 'x\ny\n'}), World({'a.txt': 'x\n'}))
        self.check(cc.file_equals(T / 'a.txt', 'x'), World({'a.txt': 'x'}), World())
        self.check(cc.file_contains(T / 'b.py', 'p'), World({'b.py': 'p\n'}), World({'b.py': 'q\n'}))
        self.check(cc.file_moved(T / 'o.txt', T / 'n.txt', 'body'), World({'n.txt': 'body\n'}),
                   World({'o.txt': 'body', 'n.txt': 'body'}))
        self.check(cc.folder_exists(T / 'f'), World(dirs=('f',)), World())

    def test_process_and_window_oracles(self):
        self.check(cc.process_running('notepad.exe'), World(processes=('notepad.exe',)), World())
        self.check(cc.process_running('mspaint.exe', False), World(), World(processes=('mspaint.exe',)))
        seen, unseen = Run(), Run()
        seen.seen = {'mspaint.exe'}
        self.check(cc.ran_then_closed('mspaint.exe'), World(), World(), seen, unseen)
        self.check(cc.ran_then_closed('mspaint.exe'), World(), World(processes=('mspaint.exe',)), seen)
        win = (1, 'c18.txt - Notepad', (0, 0, 800, 600), False)
        self.check(cc.window_rect('c18', 800, 600), World(windows=(win,)),
                   World(windows=((1, 'c18.txt - Notepad', (0, 0, 1200, 900), False),)))
        self.check(cc.window_restored('c19'), World(windows=((1, 'c19.txt', (0, 0, 1, 1), False),)),
                   World(windows=((1, 'c19.txt', (0, 0, 1, 1), True),)))

    def test_clipboard_media_and_page_oracles(self):
        self.check(cc.clipboard_is('k'), World(clipboard='k'), World(clipboard='other'))
        playing = {'source': 'Spotify.exe', 'title': 't', 'status': 'playing'}
        paused = {**playing, 'status': 'paused'}
        self.check(cc.media_playing('spotify'), World(media=(playing,)), World(media=(paused,)))
        self.check(cc.media_playing('spotify', False), World(media=(paused,)), World(media=(playing,)))
        url = 'https://mail.google.com/mail/u/0/#drafts'
        self.check(cc.page_shows(url, 'Jarvis bench 1'), World(pages={url: 'row "Jarvis bench 1"'}), World())

    def test_answer_and_read_only_oracles(self):
        self.check(cc.answer_mentions('15'), World(), World(), Run('the sum is 15'), Run('the sum is 16'))
        self.check(cc.no_send, World(), World(), Run(tools=['web_read']), Run(tools=['send_email']))


class Scenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cases  # noqa: F401  (registers CONTROL)
        cls.cases = cases
        cls.control = cases.CONTROL

    def test_at_least_forty_scenarios_with_unique_ids(self):
        ids = [c.cid for c in self.control]
        self.assertGreaterEqual(len(ids), 40)
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_scenario_passes_on_an_empty_world(self):
        """An empty answer, no files, no processes, nothing on the clipboard or pages: every oracle must fail."""
        with World(), mock.patch.object(self.cases, 'calculator_display', lambda: ''), \
                mock.patch.object(cc, '_set_dnd', lambda on: None):
            for case in self.control:
                run = self.cases.Run({'answer': '', 'tools': [], 'final_page': ''}, [], set())
                self.assertTrue(case.oracle(run), f'{case.cid} passed on an empty world')

    def test_scope_rules(self):
        for case in self.control:
            text = case.request.lower()
            if 'gmail' in text and 'draft' in text:
                self.assertIn('do not send', text, case.cid)
            if 'whatsapp' in text or 'discord' in text:
                self.assertRegex(text, r'read only|do not (open or )?send', case.cid)


if __name__ == '__main__':
    unittest.main()
