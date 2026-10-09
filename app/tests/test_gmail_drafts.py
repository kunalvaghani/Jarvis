"""Independent Gmail-like DOM fixture; never connects to a real mailbox."""
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock
import requests

from jarvis.gmail_bridge import GmailBridge
from jarvis.gmail_chrome_worker import select_compose,perform
from jarvis.utility_profiles import decorate
from jarvis.native_tools import parse

BASE=Path(__file__).resolve().parent.parent
HTML='''<button aria-label="Compose" onclick="createDraft()">Compose</button>
<div id="old" role="dialog" aria-label="Compose: New Message" style="height:35px">Old minimized draft</div>
<script>
window.created=0;window.sent=0;
window.createDraft=()=>{window.created++;const d=document.createElement('div');
d.setAttribute('role','dialog');d.setAttribute('aria-label','Compose: New Message');
d.style='width:500px;height:500px';d.innerHTML='<input name="to"><input name="subjectbox"><div contenteditable="true" role="textbox" style="height:200px"></div><button onclick="window.sent++">Send</button>';
document.body.append(d);};
</script>'''


class GmailDOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.driver=sync_playwright().start()
        cls.browser=cls.driver.chromium.launch(headless=True,executable_path=json.loads((BASE/'config/config.json').read_text())['apps']['chrome'][0])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.driver.stop()

    def setUp(self):
        self.context=self.browser.new_context()
        self.context.route('**/*',lambda route:route.fulfill(status=200,content_type='text/html',body=HTML))
        self.page=self.context.new_page();self.page.goto('https://mail.google.com/');self.page.bring_to_front()
        self.page.evaluate((BASE/'integrations/gmail-chrome/gmail-content.js').read_text())

    def tearDown(self):self.context.close()

    def call(self,request):return self.page.evaluate('r=>globalThis.__jarvisGmailDrafts.handle(r)',request)

    def test_compose_once_then_subject_body_without_recipient_preserves_old_draft(self):
        result=self.call({'operation':'draft','subject':'Jarvis skill test','body':'Jarvis skill test'})
        self.assertTrue(result['subject_verified'] and result['body_verified'])
        self.assertFalse(result['recipient_set'] or result['sent'] or result['shared_mouse_used'])
        self.assertEqual(self.page.locator('#old').inner_text(),'Old minimized draft')
        self.assertEqual(self.page.locator('input[name=to]').input_value(),'')
        self.assertEqual(self.page.evaluate('window.created'),1)
        with self.assertRaisesRegex(Exception,'expanded draft'):
            self.call({'operation':'draft','subject':'Again','body':'No duplicate'})
        self.assertEqual(self.page.evaluate('window.created'),1)

    def test_optional_recipient_is_exact_and_nothing_is_sent(self):
        result=self.call({'operation':'draft','subject':'Subject','body':'Body','to':'person@example.test'})
        self.assertTrue(result['recipient_set'])
        self.assertEqual(self.page.locator('input[name=to]').input_value(),'person@example.test')
        self.assertEqual(self.page.evaluate('window.sent'),0)
        with self.assertRaisesRegex(Exception,'drafts only'):
            self.call({'operation':'send','subject':'Subject','body':'Body','to':'person@example.test'})
        self.assertEqual(self.page.evaluate('window.sent'),0)

    def test_resume_exact_draft_with_other_drafts_preserves_other_content(self):
        self.page.evaluate('createDraft();createDraft()')
        inspection=self.call({'operation':'inspect'})
        expanded=[d for d in inspection['drafts'] if d['expanded']]
        self.call({'operation':'resume_draft','draft_runtime_id':expanded[0]['runtime_id'],
                   'expected_subject':'','expected_body':'','subject':'Test','body':'Body'})
        self.assertEqual(self.page.locator('input[name=subjectbox]').nth(1).input_value(),'')
        with self.assertRaisesRegex(Exception,'changed'):
            self.call({'operation':'resume_draft','draft_runtime_id':expanded[0]['runtime_id'],
                       'expected_subject':'','expected_body':'','subject':'Overwrite','body':'No'})
        self.assertEqual(self.page.locator('input[name=subjectbox]').nth(0).input_value(),'Test')

    def test_unsupported_attachment_fails_before_compose(self):
        with self.assertRaisesRegex(Exception,'Attachments'):
            self.call({'operation':'draft','subject':'Test','body':'Body','attachments':['private.txt']})
        self.assertEqual(self.page.evaluate('window.created'),0)

    def test_window_guard_cancels_before_creation(self):
        with self.assertRaisesRegex(Exception,'focus changed'):
            self.page.evaluate('r=>globalThis.__jarvisGmailDrafts.handle(r,async()=>{throw new Error("focus changed")})',
                {'operation':'draft','subject':'Test','body':'Body'})
        self.assertEqual(self.page.evaluate('window.created'),0)


class GmailContractTests(unittest.TestCase):
    def test_native_gmail_needs_no_filesystem_folder(self):
        rows=decorate([{'action':'skill_gmail_chrome','description':'Draft'}])
        result=parse({'tool_calls':[{'function':{'name':'skill_gmail_chrome','arguments':{
            'arguments':{'operation':'draft','subject':'Test','body':'Body'},'expected':'Draft visible'}}}]},rows)
        self.assertEqual(result['steps'][0]['folder'],'')
        result=parse({'tool_calls':[{'function':{'name':'skill_gmail_chrome','arguments':{
            'folder':'','arguments':{'operation':'draft','subject':'Test','body':'Body'},'expected':'Draft visible'}}}]},rows)
        self.assertEqual(result['steps'][0]['folder'],'')

    def test_native_expanded_selection_and_exact_identity(self):
        old=Mock();old.rectangle.return_value.height.return_value=55;old.element_info.runtime_id=[1]
        new=Mock();new.rectangle.return_value.height.return_value=500;new.element_info.runtime_id=[2]
        self.assertIs(select_compose([old,new]),new)
        self.assertIs(select_compose([old,new],[1]),old)
        with self.assertRaises(ValueError):select_compose([old,new],[3])

    def test_send_is_rejected_before_any_chrome_lookup(self):
        with self.assertRaisesRegex(ValueError,'sending is not enabled'):perform({'operation':'send'})

    def test_bridge_authentication_and_exactly_once_lease(self):
        bridge=GmailBridge('a'*64)
        session=requests.Session();session.trust_env=False
        errors=[]
        def run():
            try:bridge.call({'operation':'inspect'},timeout=.4)
            except ValueError as error:errors.append(str(error))
        thread=threading.Thread(target=run);thread.start()
        try:
            self.assertEqual(session.get('http://127.0.0.1:29923/job',timeout=1).status_code,403)
            header={'Authorization':'Bearer '+'a'*64}
            first=session.get('http://127.0.0.1:29923/job',headers=header,timeout=1).json()
            self.assertEqual(first['request']['operation'],'inspect')
            self.assertEqual(session.get('http://127.0.0.1:29923/job',headers=header,timeout=1).json(),{})
            self.assertEqual(session.post('http://127.0.0.1:29923/result',headers=header,json={'id':'wrong','result':{}},timeout=1).status_code,400)
            thread.join(timeout=2);self.assertTrue(errors)
        finally:thread.join(timeout=2);session.close();bridge.close()


if __name__=='__main__':unittest.main()
