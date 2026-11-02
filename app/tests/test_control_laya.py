"""Laya (local GPU decision model) resolving controls named in words: shortlist, confidence bar, local only."""
import io
import json
import unittest
from unittest import mock

from jarvis.control.pc import laya

CONTROLS = {'d1': ('Button', 'Two'), 'd2': ('Button', 'Plus'), 'd3': ('Button', 'Equals'),
            'd4': ('Button', 'Clear'), 'd5': ('Button', 'Square root'), 'd6': ('Text', 'Display is 0')}


def reply(choice, confidence):
    body = json.dumps({'answers': {'target': {'type': 'choice', 'choice': choice, 'answer_confidence': confidence}}})
    return mock.MagicMock(__enter__=lambda s: io.BytesIO(body.encode()), __exit__=lambda *a: False)


class Resolver(unittest.TestCase):
    def test_shortlist_ranks_by_name_without_a_model(self):
        self.assertEqual(laya.shortlist('the plus button', CONTROLS, 2)[0], 'd2')
        self.assertEqual(laya.shortlist('square root', CONTROLS, 1), ['d5'])

    def test_confident_choice_maps_back_to_the_ref(self):
        sent = []

        def urlopen(request, timeout):
            sent.append(json.loads(request.data))
            first = laya.shortlist('the digit two', CONTROLS).index('d1')
            return reply(f'c{first}', 0.99)
        with mock.patch.object(laya.urllib.request, 'urlopen', urlopen):
            answer = laya.Resolver('http://127.0.0.1:8765/v1/systemone', 'k').choose('the digit two', 'Calculator', CONTROLS)
        self.assertEqual(answer['ref'], 'd1')
        criteria = sent[0]['questions']['target']['criteria']
        self.assertIn('none', criteria)
        self.assertLessEqual(len(criteria), laya.SHORTLIST + 1)  # Laya is only ever asked about a short list

    def test_low_confidence_or_none_never_acts(self):
        for choice, confidence in (('c0', 0.6), ('none', 0.99)):
            with mock.patch.object(laya.urllib.request, 'urlopen', lambda r, timeout: reply(choice, confidence)):
                answer = laya.Resolver('http://127.0.0.1:8765/v1/systemone', 'k').choose('history', 'Calculator', CONTROLS)
            self.assertIsNone(answer['ref'])
            self.assertTrue(answer['candidates'])

    def test_offline_model_is_a_clean_no(self):
        def down(request, timeout):
            raise laya.urllib.error.URLError('refused')
        with mock.patch.object(laya.urllib.request, 'urlopen', down):
            answer = laya.Resolver('http://127.0.0.1:8765/v1/systemone', 'k').choose('two', 'Calculator', CONTROLS)
        self.assertIsNone(answer['ref'])

    def test_screen_text_only_goes_to_this_pc(self):
        with mock.patch.dict('os.environ', {'JARVIS_LAYA_URL': 'https://api.typesafe.ai/v1/systemone'}):
            self.assertIsNone(laya.endpoint())
            self.assertFalse(laya.Resolver(key='k').ready())
        with mock.patch.dict('os.environ', {'JARVIS_LAYA_URL': 'http://127.0.0.1:8765/v1/systemone'}):
            self.assertEqual(laya.endpoint(), 'http://127.0.0.1:8765/v1/systemone')



class JevSwitch(unittest.TestCase):
    def test_jev_backup_needs_free_and_consent(self):
        self.assertFalse(laya.backup_allowed({}))
        self.assertFalse(laya.backup_allowed({'control': {'decision_backup': 'jev', 'decision_cloud_consent': True}}))
        self.assertFalse(laya.backup_allowed({'control': {'decision_backup': 'jev', 'decision_backup_free': True}}))
        self.assertTrue(laya.backup_allowed({'control': {'decision_backup': 'jev', 'decision_backup_free': True,
                                                         'decision_cloud_consent': True}}))

    def test_laya_first_and_jev_only_when_laya_is_unsure_and_allowed(self):
        calls = []

        def urlopen(request, timeout):
            body = json.loads(request.data)
            calls.append('jev' if body.get('model') else 'laya')
            return reply('c0', 0.5 if not body.get('model') else 0.97)
        allowed = {'control': {'decision_backup': 'jev', 'decision_backup_free': True, 'decision_cloud_consent': True}}
        with mock.patch.object(laya.urllib.request, 'urlopen', urlopen), \
                mock.patch.object(laya.Resolver, 'ready', lambda self: True):
            self.assertIsNone(laya.Resolver.resolve('history', 'Calc', CONTROLS, {})['ref'])
            self.assertEqual(calls, ['laya'])  # not allowed: the cloud is never called
            answer = laya.Resolver.resolve('history', 'Calc', CONTROLS, allowed)
        self.assertEqual((answer['why'], calls[-1]), ('jev backup', 'jev'))

    def test_jev_reads_the_whole_window_and_names_its_model(self):
        controls = {f'd{i}': ('Button', f'Item {i}') for i in range(40)}
        sent = []

        def urlopen(request, timeout):
            sent.append(json.loads(request.data))
            return reply('c0', 0.97)
        with mock.patch.object(laya.urllib.request, 'urlopen', urlopen):
            laya.Resolver(key='k', model='jev').choose('item 7', 'App', controls)
        self.assertEqual(sent[0]['model'], 'typesafe/jev-1.13')
        self.assertEqual(len(sent[0]['questions']['target']['criteria']), 41)


if __name__ == '__main__':
    unittest.main()
