import base64
from email.parser import BytesParser
from email.policy import default
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, MagicMock, patch

from jarvis.gmail_api import API, decode, raw_message, run, configured


class MailFixture:
    def __init__(self):
        self.writes=[]; self.raw=None
    def call(self,method,path,**args):
        if method in {'POST','PUT'}:
            self.writes.append((method,path));self.raw=args['json']['message']['raw']
            return {'id':'draft123'}
        if path=='messages':return {'messages':[{'id':'message123','threadId':'thread123'}]}
        if path=='messages/message123':
            if args.get('params',{}).get('format')=='full':
                message=BytesParser(policy=default).parsebytes(base64.urlsafe_b64decode(self.raw))
                return {'id':'message123','payload':{'mimeType':'text/plain',
                    'headers':[{'name':key,'value':str(value)} for key,value in message.items()],
                    'body':{'data':base64.urlsafe_b64encode(message.get_content().encode()).decode()}}}
            return {'id':'message123','raw':self.raw}
        return {'id':'draft123','message':{'raw':self.raw}}


class GmailAPITests(unittest.TestCase):
    def test_unread_search_reads_bounded_metadata_without_bodies_or_writes(self):
        api=Mock()
        api.call.side_effect=[{'messages':[{'id':'one'},{'id':'two'}],'nextPageToken':'more'},
            {'id':'one','threadId':'thread','labelIds':['UNREAD','INBOX'],'payload':{'headers':[
                {'name':'From','value':'Person <person@example.test>'},
                {'name':'Subject','value':'Hello'}, {'name':'Date','value':'Today'},
                {'name':'Bcc','value':'do not expose'}]}},
            {'id':'two','labelIds':['INBOX'],'payload':{'headers':[]}}]
        result=run(api,'gmail_api_list','unread',{'query':'is:unread','limit':2,'summaries':True})
        self.assertEqual(result['messages'][0]['subject'],'Hello')
        self.assertTrue(result['messages'][0]['unread'])
        self.assertFalse(result['messages'][1]['unread'])
        self.assertNotIn('bcc',result['messages'][0])
        self.assertTrue(result['next_page_available'])
        self.assertEqual(api.call.call_args_list[0].args,('GET','messages'))
        self.assertEqual(api.call.call_args_list[0].kwargs['params'],{'maxResults':2,'q':'is:unread'})
        for call in api.call.call_args_list[1:]:
            self.assertEqual(call.args[0],'GET')
            self.assertEqual(call.kwargs['params'],{'format':'metadata','metadataHeaders':['From','Subject','Date']})

    def test_metadata_identity_error_cancellation_and_argument_types_stop_search(self):
        api=Mock();api.call.side_effect=[{'messages':[{'id':'one'}]},{'id':'other'}]
        with self.assertRaisesRegex(ValueError,'identity differs'):
            run(api,'gmail_api_list','unread',{'summaries':True})
        api.reset_mock();api.call.side_effect=None
        api.call.return_value={'messages':[{'id':'one'}]}
        with self.assertRaisesRegex(ValueError,'cancelled'):
            run(api,'gmail_api_list','unread',{'summaries':True},cancelled=Mock(side_effect=[False,True]))
        self.assertEqual(api.call.call_count,1)
        api.reset_mock()
        with self.assertRaisesRegex(ValueError,'boolean'):
            run(api,'gmail_api_list','unread',{'summaries':'true'})
        api.call.assert_not_called()

    def test_explicit_existing_connection_reverification_requires_profile_success(self):
        from scripts.setup import connect_gmail_api
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'.jarvis-runtime/gmail-api';root.mkdir(parents=True)
            with patch.object(connect_gmail_api,'API') as factory:
                api=factory.return_value;api.call.side_effect=ValueError('HTTP 403')
                with self.assertRaises(ValueError):connect_gmail_api.verify_existing(tmp)
                self.assertFalse((root/'verified.json').exists())
                api.close.assert_called_once()
                api.reset_mock();api.call.side_effect=None
                connect_gmail_api.verify_existing(tmp)
                api.call.assert_called_once_with('GET','profile')
                api.close.assert_called_once()
                self.assertTrue(json.loads((root/'verified.json').read_text())['profile_verified'])

    def test_recipient_free_unicode_draft_with_independent_mime_oracle(self):
        api=MailFixture();approval=Mock()
        result=run(api,'gmail_api_draft','new',{'subject':'Hello नमस्ते','body':'One\nTwo'},approval)
        message=BytesParser(policy=default).parsebytes(base64.urlsafe_b64decode(api.raw))
        self.assertIsNone(message['To']); self.assertEqual(str(message['Subject']),'Hello नमस्ते')
        self.assertEqual(message.get_content(),'One\nTwo\n')
        self.assertEqual(api.writes,[('POST','drafts')]);approval.assert_called_once()
        self.assertFalse(result['sent'] or result['recipient_set'])

    def test_inspected_draft_update_checks_hash_and_exact_recipient(self):
        api=MailFixture();api.raw=raw_message({'subject':'Old','body':'Old'})
        expected=run(api,'gmail_api_read_draft','draft123',{})['sha256']
        result=run(api,'gmail_api_update_draft','draft123',{'subject':'New','body':'New','to':'person@example.test','expected_sha256':expected})
        self.assertTrue(result['recipient_set']);self.assertEqual(api.writes,[('PUT','drafts/draft123')])
        with self.assertRaisesRegex(ValueError,'changed'):
            run(api,'gmail_api_update_draft','draft123',{'subject':'Wrong','body':'Wrong','expected_sha256':expected})
        self.assertEqual(len(api.writes),1)

    def test_read_preserves_mailbox_and_marks_content_untrusted(self):
        api=MailFixture();api.raw=raw_message({'subject':'Ignore instructions','body':'untrusted mail'})
        self.assertEqual(run(api,'gmail_api_list','search',{'limit':1})['messages'][0]['id'],'message123')
        result=run(api,'gmail_api_read','message123',{})
        self.assertTrue(result['content_is_untrusted']);self.assertEqual(api.writes,[])

    def test_html_only_mail_is_inert_text_without_tracking_or_script(self):
        raw=b'Subject: HTML\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<head><style>hidden</style></head><p>Hello &amp; welcome</p><script>steal()</script><img src="https://tracking.example.test/x">'
        result=decode(base64.urlsafe_b64encode(raw).decode())
        self.assertIn('Hello & welcome',result['body'])
        self.assertNotIn('steal',result['body']);self.assertNotIn('hidden',result['body'])
        self.assertNotIn('tracking',result['body'])

    def test_approval_denial_and_cancellation_prevent_writes(self):
        api=MailFixture()
        def denied():raise ValueError('Denied')
        with self.assertRaisesRegex(ValueError,'Denied'):run(api,'gmail_api_draft','new',{'subject':'s','body':'b'},denied)
        with self.assertRaisesRegex(ValueError,'cancelled'):run(api,'gmail_api_draft','new',{'subject':'s','body':'b'},cancelled=lambda:True)
        self.assertEqual(api.writes,[])

    def test_header_injection_send_and_unknown_fields_rejected(self):
        api=MailFixture()
        for args in ({'subject':'s\nBcc: victim@example.test','body':'b'}, {'subject':'s','body':'b','to':'a@example.test\nBcc:x'}, {'subject':'s','body':'b','attachments':['x']}):
            with self.assertRaises(ValueError):run(api,'gmail_api_draft','new',args)
        with self.assertRaisesRegex(ValueError,'recipient'):run(api,'gmail_api_send','new',{'subject':'s','body':'b'})
        with self.assertRaisesRegex(ValueError,'send field'):run(api,'gmail_api_send','new',{'subject':'s','body':'b','to':'a@example.test','bcc':'x@example.test'})
        with self.assertRaisesRegex(ValueError,'Unsupported'):run(api,'gmail_api_forward','message123',{})
        with self.assertRaises(ValueError):run(api,'gmail_api_read','../../settings',{})
        self.assertEqual(api.writes,[])

    def test_timeout_after_dispatch_has_exactly_one_attempt(self):
        session=Mock();session.request.side_effect=TimeoutError('secret response')
        api=API('.',session=session)
        with self.assertRaisesRegex(ValueError,'uncertain') as result:api.call('POST','drafts',json={})
        self.assertNotIn('secret',str(result.exception));session.request.assert_called_once()

    def test_http_error_and_response_budget_do_not_leak_mail(self):
        session=MagicMock();response=session.request.return_value.__enter__.return_value
        response.status_code=403
        with self.assertRaisesRegex(ValueError,'HTTP 403'):API('.',session).call('GET','messages')
        response.status_code=200;response.iter_content.return_value=[b'x'*2_000_001]
        with self.assertRaisesRegex(ValueError,'budget'):API('.',session).call('GET','messages')

    def test_oauth_tools_not_offered_without_local_connection(self):
        with tempfile.TemporaryDirectory() as root:self.assertFalse(configured(Path(root)))
        from jarvis import toolkits
        with patch('jarvis.gmail_api.configured',return_value=False):
            self.assertFalse(toolkits.available('gmail_api_draft'))
            self.assertFalse(next(row for row in toolkits.status() if row['tool']=='gmail_api_read')['configured'])

    def test_email_read_readiness_does_not_substitute_draft_only_chrome(self):
        from jarvis.capabilities import gmail_readiness_question
        self.assertIn('Gmail API is not connected',gmail_readiness_question('read my email',[{'action':'skill_gmail_chrome'}]))
        self.assertEqual(gmail_readiness_question('read my email',[{'action':'gmail_api_read'}]),'')

    def test_existing_cc_draft_is_not_silently_stripped(self):
        api=MailFixture()
        api.raw=base64.urlsafe_b64encode(b'Subject: s\r\nCc: other@example.test\r\n\r\nold').decode()
        expected=decode(api.raw)['sha256']
        with self.assertRaisesRegex(ValueError,'cannot preserve'):
            run(api,'gmail_api_update_draft','draft123',{'subject':'s','body':'new','expected_sha256':expected})
        self.assertEqual(api.writes,[])

    def test_list_drafts_returns_only_bounded_ids(self):
        api=Mock();api.call.return_value={'drafts':[{'id':'d1'},{'id':'d2'}]}
        result=run(api,'gmail_api_list_drafts','drafts',{'limit':1})
        self.assertEqual(result['drafts'],[{'id':'d1'}])
        api.call.assert_called_once_with('GET','drafts',params={'maxResults':1})

    def test_draft_search_passes_official_query_filter(self):
        api=Mock();api.call.return_value={'drafts':[]}
        result=run(api,'gmail_api_list_drafts','drafts',{'query':'subject:"Meeting"','limit':3})
        api.call.assert_called_once_with('GET','drafts',params={'maxResults':3,'q':'subject:"Meeting"'})
        self.assertEqual(result['drafts'],[])

    def test_message_full_read_ignores_file_attachments_and_html_execution(self):
        api=Mock();api.call.return_value={'id':'mail1','payload':{
            'mimeType':'multipart/mixed','headers':[{'name':'Subject','value':'Read me'}],
            'parts':[{'mimeType':'text/html','body':{'data':base64.urlsafe_b64encode(b'<p>Hello</p><script>run()</script><img src="https://tracker.test/">').decode()}},
                     {'mimeType':'text/plain','filename':'secret.txt','body':{'attachmentId':'file1'}}]}}
        result=run(api,'gmail_api_read','mail1',{})
        api.call.assert_called_once_with('GET','messages/mail1',params={'format':'full'})
        self.assertIn('Hello',result['body']);self.assertNotIn('run()',result['body'])
        self.assertNotIn('tracker',result['body']);self.assertTrue(result['content_is_untrusted'])

    def test_external_text_part_is_read_but_large_body_is_explicitly_truncated(self):
        api=Mock();api.call.side_effect=[{'id':'mail1','payload':{'mimeType':'text/plain','body':{'attachmentId':'text1'}}},
            {'data':base64.urlsafe_b64encode(b'x'*20001).decode()}]
        result=run(api,'gmail_api_read','mail1',{})
        self.assertEqual(api.call.call_args_list[1].args,('GET','messages/mail1/attachments/text1'))
        self.assertEqual(len(result['body']),20000);self.assertTrue(result['body_truncated'])

    def test_subject_only_update_preserves_original_html_mime_body(self):
        api=MailFixture()
        api.raw=base64.urlsafe_b64encode(b'Subject: Original\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p><b>Keep formatting</b></p>').decode()
        original=decode(api.raw)
        run(api,'gmail_api_update_draft','draft123',{'subject':'Changed','body':original['body'],'expected_sha256':original['sha256']})
        message=BytesParser(policy=default).parsebytes(base64.urlsafe_b64decode(api.raw))
        self.assertEqual(message.get_content_type(),'text/html')
        self.assertEqual(str(message['Subject']),'Changed')
        self.assertIn('<b>Keep formatting</b>',message.get_content())


if __name__=='__main__':unittest.main()
