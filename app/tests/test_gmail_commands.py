import base64
from email.parser import BytesParser
from email.policy import default
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.brain import Brain
from jarvis.brain_worker import Models, SCHEMAS
from jarvis.commands import parse
from jarvis.gmail_api import run, raw_message
from jarvis.gmail_workflows import gmail_request, validate_request, run_gmail
from jarvis.clarification import TaskClarification


class Mailbox:
    def __init__(self):
        self.raw=raw_message({'subject':'Original','body':'Original body','to':'kept@example.test'})
        self.calls=[];self.ambiguous=False;self.race=False
    def call(self,method,path,**kwargs):
        self.calls.append((method,path,kwargs))
        message=BytesParser(policy=default).parsebytes(base64.urlsafe_b64decode(self.raw))
        headers=[{'name':key,'value':str(value)} for key,value in message.items()]
        if method in {'POST','PUT'}:
            self.raw=kwargs['json']['message']['raw'];return {'id':'draft1'}
        if path=='drafts':
            return {'drafts':[{'id':'draft1'},{'id':'draft2'}] if self.ambiguous else [{'id':'draft1'}]}
        if path.startswith('drafts/'):
            current=self.raw
            if self.race and len([c for c in self.calls if c[1]=='drafts/draft1'])>=2:
                current=raw_message({'subject':'Original','body':'Changed elsewhere','to':'kept@example.test'})
            return {'id':path.split('/')[-1],'message':{'raw':current}}
        if path=='messages':return {'messages':[{'id':'message1'}]}
        if path=='messages/message1':
            if kwargs['params']['format']=='metadata':return {'id':'message1','payload':{'headers':headers},'labelIds':['UNREAD']}
            return {'id':'message1','payload':{'headers':headers,'mimeType':'text/plain',
                'body':{'data':base64.urlsafe_b64encode(message.get_content().encode()).decode()}}}
        raise AssertionError('Unexpected endpoint: '+path)


class GmailCommandTests(unittest.TestCase):
    def fixture(self,approved=True):
        actions=SimpleNamespace(config={},report=Mock())
        brain=Brain(actions,Path('.'),{'enabled':True,'incremental_planning':True,'screen_aware':True,'planner':'unused'})
        api=Mailbox()
        def approve():
            if not approved:raise ValueError('Draft approval denied')
        brain.dispatch=Mock(side_effect=lambda step,cancelled:SimpleNamespace(evidence=json.dumps(
            run(api,step['action'],step['value'],json.loads(step['content']),approve,cancelled))))
        brain.observe=Mock(side_effect=AssertionError('No desktop observation for mail'))
        brain.client.request=Mock(side_effect=AssertionError('Exact request should not need inference'))
        return brain,api
    def offered(self):
        return patch('jarvis.gmail_workflows.ToolRegistry.catalog',return_value=[{'action':name} for name in
            ('gmail_api_list','gmail_api_read','gmail_api_list_drafts','gmail_api_read_draft','gmail_api_draft','gmail_api_update_draft')])

    def test_reported_smart_quote_draft_copies_exact_content_and_blank_recipient(self):
        brain,api=self.fixture()
        goal="draft an email with subject ‘meeting tomorrow' and body ‘can we meet tomorrow at 3 pm?' leave the recipient blank"
        self.assertEqual(parse(goal).kind,'task')
        with self.offered():answer=brain.run(goal,lambda:False)
        message=BytesParser(policy=default).parsebytes(base64.urlsafe_b64decode(api.raw))
        self.assertEqual(str(message['Subject']),'meeting tomorrow')
        self.assertEqual(message.get_content(),'can we meet tomorrow at 3 pm?\n')
        self.assertIsNone(message['To'])
        self.assertIn('Draft saved',answer)
        self.assertEqual([(method,path) for method,path,_ in api.calls if method!='GET'],[('POST','drafts')])
        brain.client.request.assert_not_called();brain.observe.assert_not_called()

    def test_read_latest_and_list_selection_use_observed_ids_and_full_body(self):
        brain,api=self.fixture()
        with self.offered():
            answer=brain.run('read my latest email',lambda:False)
            self.assertIn('Original body',answer)
            answer=brain.run('read the first email',lambda:False)
            self.assertIn('kept@example.test',answer)
        self.assertTrue(all(method=='GET' for method,_,_ in api.calls))
        self.assertEqual(api.calls[0][2]['params'],{'maxResults':1,'q':'in:inbox'})
        brain.client.request.assert_not_called();brain.observe.assert_not_called()

    def test_partial_draft_update_preserves_unspecified_subject_and_recipient(self):
        brain,api=self.fixture()
        with self.offered():answer=brain.run('update the Gmail draft with subject "Original" to have body "Replacement body"',lambda:False)
        message=BytesParser(policy=default).parsebytes(base64.urlsafe_b64decode(api.raw))
        self.assertEqual(str(message['Subject']),'Original')
        self.assertEqual(str(message['To']),'kept@example.test')
        self.assertEqual(message.get_content(),'Replacement body\n')
        self.assertIn('updated and read back',answer)
        self.assertEqual(api.calls[0][2]['params']['q'],'subject:"Original"')
        self.assertEqual([(method,path) for method,path,_ in api.calls if method!='GET'],[('PUT','drafts/draft1')])

    def test_ambiguity_race_and_approval_denial_never_mutate_or_retry(self):
        for kind in ('ambiguous','race','denied'):
            with self.subTest(kind=kind):
                brain,api=self.fixture(approved=kind!='denied')
                api.ambiguous=kind=='ambiguous';api.race=kind=='race'
                original=api.raw
                with self.offered(),self.assertRaises(ValueError):
                    brain.run('update the Gmail draft with subject "Original" to have body "Replacement body"',lambda:False)
                self.assertEqual(api.raw,original)
                self.assertFalse(any(method!='GET' for method,_,_ in api.calls))

    def test_unsupported_and_non_email_requests_never_use_mail_api(self):
        brain,api=self.fixture()
        for goal in ('reply to my latest email','forward the first email'):
            with self.offered(),self.assertRaisesRegex(TaskClarification,'Replying and forwarding'):brain.run(goal,lambda:False)
        # Under-specified writes ask a question instead of guessing recipients or messages.
        brain.client.request=Mock(return_value={'operation':'send','query':'','target':'','reference':'','subject':'Hi',
            'body':'Hello','to':'','label':'','fields':[],'question':''})
        with self.offered(),self.assertRaisesRegex(TaskClarification,'exact email address'):brain.run('send an email',lambda:False)
        brain.client.request=Mock(return_value={'operation':'trash','query':'','target':'','reference':'','subject':'',
            'body':'','to':'','label':'','fields':[],'question':''})
        with self.offered(),self.assertRaisesRegex(TaskClarification,'Which emails'):brain.run('delete my emails',lambda:False)
        self.assertEqual(api.calls,[])
        for goal in ('write a Python script to read Gmail','read file email.py in Downloads',
                     'write a specification for an email app','write email.py in Testcodes','read draft.py'):
            self.assertFalse(gmail_request(goal))

    def test_generated_address_and_operation_changes_are_rejected_before_dispatch(self):
        base={'operation':'draft','query':'','target':'','reference':'','subject':'Meeting',
              'body':'Generated meeting request','to':'madeup@example.test','fields':['subject','body','to'],'question':''}
        with self.assertRaises(TaskClarification):validate_request(base,'write an email to Bob asking for a meeting')
        with self.assertRaises(ValueError):validate_request({**base,'to':''},'read my latest email')

    def test_configured_smtp_keeps_generic_send_and_named_gmail_uses_gmail(self):
        brain,api=self.fixture()
        with patch('jarvis.gmail_workflows.ToolRegistry.catalog',return_value=[{'action':'send_email'}]), \
             patch('jarvis.gmail_workflows.ToolRegistry.search',return_value=[]):
            self.assertIsNone(run_gmail(brain,'send an email',lambda:False))
            with self.assertRaisesRegex(TaskClarification,'not available'):run_gmail(brain,'send a Gmail email',lambda:False)
        brain.dispatch.assert_not_called();brain.client.request.assert_not_called()
        self.assertEqual(api.calls,[])

    def test_natural_composition_uses_one_text_interpretation_then_api_only(self):
        brain,api=self.fixture()
        brain.client.request=Mock(return_value={'operation':'draft','query':'','target':'','reference':'',
            'subject':'Meeting','body':'Can we arrange a meeting?','to':'','fields':['subject','body'],'question':''})
        with self.offered():answer=brain.run('write an email asking for a meeting',lambda:False)
        self.assertIn('Draft saved',answer)
        brain.client.request.assert_called_once_with('gmail_request',unittest.mock.ANY,goal='write an email asking for a meeting')
        brain.observe.assert_not_called()
        self.assertEqual(len([c for c in api.calls if c[0]=='POST']),1)

    def test_gmail_interpreter_schema_and_model_have_no_desktop_context(self):
        models=Models.__new__(Models);models.client=Mock();models.generate=Mock(return_value={})
        with patch('jarvis.brain_worker.ensure_server',return_value={'models':[{'name':'local-qwen'}]}):
            models.predict({'operation':'gmail_request','options':{'planner':'local-qwen'},'goal':'write an email about me','images':['not used']})
        self.assertEqual(models.generate.call_args.args[0],'local-qwen')
        self.assertEqual(models.generate.call_args.args[2],{'goal':'write an email about me'})
        self.assertNotIn('id',SCHEMAS['gmail_request']['properties'])

    def test_literal_clause_words_and_speech_punctuation_are_preserved(self):
        from jarvis.gmail_workflows import explicit_request
        parsed=explicit_request('Draft an email with subject "Subject and body examples" and body "Can we meet?" Leave the recipient blank.')
        self.assertEqual(parsed['subject'],'Subject and body examples')
        self.assertEqual(parsed['body'],'Can we meet?')
        self.assertIsNone(explicit_request('draft an email with subject "Hello" and body "Hi" to person@example.test'))


if __name__=='__main__':unittest.main()
