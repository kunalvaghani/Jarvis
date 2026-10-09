import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.gmail_api import execute


class WriteJournalTests(unittest.TestCase):
    def test_uncertain_create_survives_new_caller_and_never_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            actions=SimpleNamespace(base=Path(tmp),_approve=Mock())
            step={'action':'gmail_api_draft','value':'new','content':json.dumps({'subject':'Test','body':'Body'})}
            api=Mock();api.call.side_effect=[{'id':'draft1'},ValueError('Lost readback')]
            with patch('jarvis.gmail_api.configured',return_value=True),patch('jarvis.gmail_api.API',return_value=api):
                with self.assertRaisesRegex(ValueError,'Lost readback'):execute(actions,step,lambda:False)
                marker=next((Path(tmp)/'.jarvis-runtime/gmail-api/writes').glob('*.json'))
                self.assertEqual(json.loads(marker.read_text())['draft_id'],'draft1')
                api.reset_mock();api.call.side_effect=None
                with self.assertRaisesRegex(ValueError,'uncertain outcome'):execute(actions,step,lambda:False)
                api.call.assert_not_called()
                actions._approve.assert_called_once()

    def test_denied_approval_does_not_record_an_uncertain_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            actions=SimpleNamespace(base=Path(tmp),_approve=Mock(side_effect=ValueError('Denied')))
            step={'action':'gmail_api_draft','value':'new','content':json.dumps({'subject':'Test','body':'Body'})}
            api=Mock()
            with patch('jarvis.gmail_api.configured',return_value=True),patch('jarvis.gmail_api.API',return_value=api):
                with self.assertRaisesRegex(ValueError,'Denied'):execute(actions,step,lambda:False)
            api.call.assert_not_called()
            self.assertFalse(list((Path(tmp)/'.jarvis-runtime/gmail-api/writes').glob('*.json')))

    def test_changed_inspection_hash_does_not_bypass_pending_update(self):
        from jarvis.gmail_writes import guard
        with tempfile.TemporaryDirectory() as tmp:
            args={'subject':'Test','body':'Body','expected_sha256':'old'}
            with guard(tmp,'gmail_api_update_draft','draft1',args) as journal:journal.begin()
            with self.assertRaisesRegex(ValueError,'uncertain outcome'):
                with guard(tmp,'gmail_api_update_draft','draft1',{**args,'expected_sha256':'new'}):pass


if __name__=='__main__':unittest.main()
