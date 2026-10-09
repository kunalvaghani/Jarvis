"""Send, Trash, label, speak and group: adapter and spoken-command fixtures."""
import base64
from email.parser import BytesParser
from email.policy import default
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.brain import Brain
from jarvis.clarification import TaskClarification
from jarvis.commands import parse
from jarvis.gmail_api import TOOLS, execute, raw_message, run
from jarvis.gmail_workflows import explicit_request, gmail_request, spoken_addresses


def mime(raw):
    return BytesParser(policy=default).parsebytes(base64.urlsafe_b64decode(raw))


class Mailbox:
    """Owned in-memory Gmail: messages with labels, drafts and user labels."""
    def __init__(self):
        self.messages={}
        self.drafts={}
        self.labels=[{'id':'Label_1','name':'Work','type':'user'},{'id':'INBOX','name':'INBOX','type':'system'}]
        self.calls=[];self.fail_send_readback=False;self.next=0
        for index,(sender,subject,body) in enumerate((('Alice <alice@example.test>','Lunch plan','Lunch at noon?\n> old quoted line'),
                                                      ('Bob <bob@example.test>','Invoice','Invoice attached.'),
                                                      ('Alice <alice@example.test>','Trip','Trip photos.'))):
            self.add_message('m'+str(index),sender,subject,body,['INBOX','UNREAD'])
    def add_message(self,message_id,sender,subject,body,labels):
        message=raw_message({'subject':subject,'body':body})
        parsed=mime(message);parsed['From']=sender
        self.messages[message_id]={'raw':parsed,'labels':list(labels)}
    def writes(self):
        return [(method,path) for method,path,_ in self.calls if method!='GET']
    def headers(self,message_id):
        return [{'name':key,'value':str(value)} for key,value in self.messages[message_id]['raw'].items()]
    def view(self,message_id):
        return {'id':message_id,'threadId':'t'+message_id,'labelIds':list(self.messages[message_id]['labels'])}
    def call(self,method,path,missing_ok=False,**kwargs):
        self.calls.append((method,path,kwargs))
        parts=path.split('/')
        if path=='labels':
            if method=='POST':
                row={'id':'Label_'+str(len(self.labels)+1),'name':kwargs['json']['name'],'type':'user'}
                self.labels.append(row);return row
            return {'labels':self.labels}
        if path=='messages':
            query=kwargs['params'].get('q','')
            rows=[key for key,item in self.messages.items() if
                  ('TRASH' in item['labels'])==('in:trash' in query) and
                  ('is:unread' not in query or 'UNREAD' in item['labels']) and
                  ('in:inbox' not in query or 'INBOX' in item['labels']) and
                  ('from:' not in query or query.split('from:')[1].split()[0] in str(item['raw']['From'])) and
                  ('subject:"' not in query or query.split('subject:"')[1].split('"')[0].casefold() in str(item['raw']['Subject']).casefold())]
            rows=sorted(rows,reverse=True)
            limit=kwargs['params']['maxResults']
            return {'messages':[{'id':key} for key in rows[:limit]],**({'nextPageToken':'x'} if len(rows)>limit else {})}
        if path=='messages/send':
            message=mime(kwargs['json']['raw']);message_id='sent'+str(len(self.messages))
            self.messages[message_id]={'raw':message,'labels':['SENT']}
            return {'id':message_id,'labelIds':['SENT']}
        if parts[0]=='messages' and len(parts)==2:
            item=self.messages[parts[1]]
            if kwargs['params']['format']=='metadata':
                headers=self.headers(parts[1])
                if self.fail_send_readback and 'SENT' in item['labels']:headers=[]
                return {**self.view(parts[1]),'payload':{'headers':headers}}
            return {**self.view(parts[1]),'payload':{'headers':self.headers(parts[1]),'mimeType':'text/plain',
                    'body':{'data':base64.urlsafe_b64encode(item['raw'].get_content().encode()).decode()}}}
        if parts[0]=='messages' and len(parts)==3:
            labels=self.messages[parts[1]]['labels']
            if parts[2]=='trash':labels.append('TRASH')
            elif parts[2]=='untrash':labels.remove('TRASH')
            else:
                labels[:]=[label for label in labels if label not in kwargs['json']['removeLabelIds']]
                labels.extend(label for label in kwargs['json']['addLabelIds'] if label not in labels)
            return self.view(parts[1])
        if path=='drafts':
            if method=='POST':
                draft_id='d'+str(len(self.drafts));self.drafts[draft_id]=kwargs['json']['message']['raw'];return {'id':draft_id}
            return {'drafts':[{'id':key} for key in self.drafts]}
        if path=='drafts/send':
            raw=self.drafts.pop(kwargs['json']['id']);message_id='sent'+str(len(self.messages))
            self.messages[message_id]={'raw':mime(raw),'labels':['SENT']}
            return {'id':message_id,'labelIds':['SENT']}
        if parts[0]=='drafts':
            if method=='DELETE':del self.drafts[parts[1]];return {}
            if parts[1] not in self.drafts:
                if missing_ok:return None
                raise ValueError('Gmail API returned HTTP 404')
            return {'id':parts[1],'message':{'raw':self.drafts[parts[1]]}}
        raise AssertionError('Unexpected endpoint: '+method+' '+path)


class AdapterTests(unittest.TestCase):
    def test_send_requires_recipient_approves_once_and_verifies_sent_label(self):
        api=Mailbox();approve=Mock()
        result=run(api,'gmail_api_send','new',{'to':'a@example.test, b@example.test','subject':'Hello','body':'Hi there','cc':'c@example.test'},approve)
        approve.assert_called_once()
        self.assertTrue(result['sent']);self.assertEqual(result['to'],'a@example.test, b@example.test')
        message=api.messages[result['message_id']]['raw']
        self.assertEqual(str(message['Cc']),'c@example.test');self.assertEqual(message.get_content(),'Hi there\n')
        self.assertEqual(api.writes(),[('POST','messages/send')])
        for bad in ({'subject':'s','body':'b'},{'to':'Bob','subject':'s','body':'b'},{'to':'a@example.test\nBcc: x@example.test','subject':'s','body':'b'}):
            with self.assertRaises(ValueError):run(api,'gmail_api_send','new',bad,approve)
        self.assertEqual(len(api.writes()),1)

    def test_unverified_send_is_reported_never_resent(self):
        api=Mailbox();api.fail_send_readback=True
        with self.assertRaisesRegex(ValueError,'No resend'):run(api,'gmail_api_send','new',{'to':'a@example.test','subject':'Hello','body':'Hi'})
        self.assertEqual(api.writes(),[('POST','messages/send')])

    def test_send_and_delete_draft_check_hash_and_recipient(self):
        api=Mailbox()
        api.drafts['d1']=raw_message({'subject':'Ready','body':'Body','to':'a@example.test'})
        api.drafts['d2']=raw_message({'subject':'Blank','body':'Body'})
        sha=run(api,'gmail_api_read_draft','d1',{})['sha256']
        with self.assertRaisesRegex(ValueError,'changed'):run(api,'gmail_api_send_draft','d1',{'expected_sha256':'stale'})
        blank=run(api,'gmail_api_read_draft','d2',{})['sha256']
        with self.assertRaisesRegex(ValueError,'no recipient'):run(api,'gmail_api_send_draft','d2',{'expected_sha256':blank})
        self.assertEqual(api.writes(),[])
        result=run(api,'gmail_api_send_draft','d1',{'expected_sha256':sha})
        self.assertTrue(result['sent']);self.assertNotIn('d1',api.drafts)
        result=run(api,'gmail_api_delete_draft','d2',{'expected_sha256':blank})
        self.assertTrue(result['deleted']);self.assertEqual(api.drafts,{})
        self.assertEqual(api.writes(),[('POST','drafts/send'),('DELETE','drafts/d2')])

    def test_trash_untrash_and_label_verify_every_message(self):
        api=Mailbox()
        result=run(api,'gmail_api_trash','selected',{'ids':['m0','m1'],'preview':['Alice — Lunch plan','Bob — Invoice']})
        self.assertEqual(result['changed'],2);self.assertIn('TRASH',api.messages['m1']['labels'])
        run(api,'gmail_api_untrash','selected',{'ids':['m1']})
        self.assertNotIn('TRASH',api.messages['m1']['labels'])
        result=run(api,'gmail_api_modify_labels','selected',{'ids':['m2'],'add':['work','Receipts'],'remove':['INBOX','UNREAD']})
        self.assertEqual(result['created_labels'],['Receipts'])
        self.assertEqual(set(api.messages['m2']['labels']),{'Label_1','Label_3'})
        with self.assertRaisesRegex(ValueError,'does not exist'):run(api,'gmail_api_modify_labels','selected',{'ids':['m2'],'remove':['Missing']})
        with self.assertRaisesRegex(ValueError,'both'):run(api,'gmail_api_modify_labels','selected',{'ids':['m2'],'add':['Work'],'remove':['work']})
        for bad in ({'ids':[]},{'ids':['m1','m1']},{'ids':['../x']},{'ids':['m'+str(i) for i in range(26)]}):
            with self.assertRaises(ValueError):run(api,'gmail_api_trash','selected',bad)

    def test_denied_or_cancelled_change_writes_nothing(self):
        api=Mailbox()
        def denied():raise ValueError('Denied')
        with self.assertRaisesRegex(ValueError,'Denied'):run(api,'gmail_api_trash','selected',{'ids':['m0']},denied)
        with self.assertRaisesRegex(ValueError,'cancelled'):run(api,'gmail_api_send','new',{'to':'a@example.test','subject':'s','body':'b'},cancelled=lambda:True)
        self.assertEqual(api.writes(),[])

    def test_labels_listing_hides_internal_system_labels(self):
        api=Mailbox();api.labels.append({'id':'SPAM','name':'SPAM','type':'system'})
        names=[row['name'] for row in run(api,'gmail_api_list_labels','labels',{})['labels']]
        self.assertEqual(names,['Work','INBOX'])

    def test_every_write_tool_is_journaled_and_requires_approval(self):
        writes={name for name,data in TOOLS.items() if data[3]}
        from jarvis.gmail_api import WRITES
        self.assertEqual(writes,WRITES)
        with tempfile.TemporaryDirectory() as tmp:
            actions=SimpleNamespace(base=Path(tmp),_approve=Mock())
            step={'action':'gmail_api_trash','value':'selected','content':json.dumps({'ids':['m0']})}
            api=Mock();api.call.side_effect=ValueError('Gmail API result is uncertain')
            with patch('jarvis.gmail_api.configured',return_value=True),patch('jarvis.gmail_api.API',return_value=api):
                with self.assertRaisesRegex(ValueError,'uncertain'):execute(actions,step,lambda:False)
                api.reset_mock()
                with self.assertRaisesRegex(ValueError,'uncertain outcome'):execute(actions,step,lambda:False)
                api.call.assert_not_called()


class SpokenCommandTests(unittest.TestCase):
    def fixture(self,approved=True):
        actions=SimpleNamespace(config={},report=Mock())
        brain=Brain(actions,Path('.'),{'enabled':True,'incremental_planning':True,'screen_aware':True,'planner':'unused'})
        api=Mailbox();self.approvals=[]
        def approve():
            self.approvals.append(True)
            if not approved:raise ValueError('Approval denied')
        brain.dispatch=Mock(side_effect=lambda step,cancelled:SimpleNamespace(evidence=json.dumps(
            run(api,step['action'],step['value'],json.loads(step['content']),approve,cancelled))))
        brain.observe=Mock(side_effect=AssertionError('No desktop observation for mail'))
        brain.client.request=Mock(side_effect=AssertionError('Exact request should not need inference'))
        return brain,api

    def offered(self):
        # Deferred discovery returns catalogue-style rows too; the cap of 12 must not hide tools.
        rows=[{'action':name} for name in TOOLS]
        catalog=patch('jarvis.gmail_workflows.ToolRegistry.catalog',return_value=rows[:12])
        search=patch('jarvis.gmail_workflows.ToolRegistry.search',return_value=rows)
        class Both:
            def __enter__(self):catalog.start();search.start()
            def __exit__(self,*error):search.stop();catalog.stop()
        return Both()

    def test_spoken_commands_route_to_gmail_tasks(self):
        for goal in ('speak my latest email','read aloud the first email','read my latest email aloud','tell me my unread emails',
                     'send an email to a@example.test with subject "Hi" and body "Hello"','send the draft with subject Ready',
                     'delete the latest email','delete all emails from bob@example.test','restore the email with subject Invoice',
                     'mark the first email as read','archive the latest email','star the second email',
                     'move the latest email to Work','label the first email as Receipts','group my emails by sender',
                     'list my gmail labels','delete the draft with subject Ready'):
            with self.subTest(goal=goal):
                self.assertTrue(gmail_request(goal));self.assertEqual(parse(goal).kind,'task')
                self.assertIsNotNone(explicit_request(goal))
        for goal in ('move the file to downloads','delete notes.txt','tell me a joke','sort the list in python','say hello'):
            self.assertFalse(gmail_request(goal))

    def test_spoken_address_is_restored(self):
        self.assertEqual(spoken_addresses('send an email to kaushik.adi at gmail dot com about lunch'),
                         'send an email to kaushik.adi@gmail.com about lunch')
        self.assertEqual(spoken_addresses('meet at noon'),'meet at noon')

    def test_send_literal_email_with_one_approval(self):
        brain,api=self.fixture()
        with self.offered():answer=brain.run('send an email to a@example.test with subject "Hi" and body "Hello there"',lambda:False)
        self.assertIn('Email sent to a@example.test',answer)
        self.assertEqual(api.writes(),[('POST','messages/send')]);self.assertEqual(self.approvals,[True])

    def test_natural_send_composes_but_never_invents_recipient(self):
        brain,api=self.fixture()
        brain.client.request=Mock(return_value={'operation':'send','query':'','target':'','reference':'','subject':'Lunch',
            'body':'Shall we have lunch tomorrow?','to':'kaushik.adi@gmail.com','label':'','fields':['subject','body','to'],'question':''})
        with self.offered():answer=brain.run('send an email to kaushik.adi at gmail dot com asking about lunch tomorrow',lambda:False)
        self.assertIn('Email sent to kaushik.adi@gmail.com',answer)
        brain.client.request.return_value={**brain.client.request.return_value,'to':'bob@example.test'}
        with self.offered(),self.assertRaisesRegex(TaskClarification,'exact recipient'):brain.run('send an email to Bob about lunch',lambda:False)
        self.assertEqual(api.writes(),[('POST','messages/send')])

    def test_delete_latest_then_restore_by_subject(self):
        brain,api=self.fixture()
        with self.offered():
            answer=brain.run('delete the latest email',lambda:False)
            self.assertIn('Moved 1 email to Trash',answer);self.assertIn('Alice — Trip',answer)
            self.assertIn('TRASH',api.messages['m2']['labels'])
            answer=brain.run('restore the email with subject Trip',lambda:False)
        self.assertIn('Restored 1 email',answer);self.assertNotIn('TRASH',api.messages['m2']['labels'])

    def test_bulk_sender_trash_uses_one_approval_with_preview(self):
        brain,api=self.fixture()
        with self.offered():answer=brain.run('delete all emails from alice@example.test',lambda:False)
        self.assertIn('Moved 2 emails to Trash',answer);self.assertEqual(self.approvals,[True])
        step=[c.args[0] for c in brain.dispatch.call_args_list if c.args[0]['action']=='gmail_api_trash'][0]
        self.assertEqual(json.loads(step['content'])['preview'],['Alice — Trip','Alice — Lunch plan'])
        self.assertNotIn('TRASH',api.messages['m1']['labels'])

    def test_mark_archive_star_move_and_label(self):
        brain,api=self.fixture()
        with self.offered():
            brain.run('list my emails',lambda:False)
            self.assertIn('as read',brain.run('mark the first email as read',lambda:False))
            self.assertNotIn('UNREAD',api.messages['m2']['labels'])
            brain.run('star the second email',lambda:False);self.assertIn('STARRED',api.messages['m1']['labels'])
            self.assertIn('Archived',brain.run('archive the latest email',lambda:False))
            self.assertNotIn('INBOX',api.messages['m2']['labels'])
            answer=brain.run('move the latest email to Work',lambda:False)
            self.assertIn('Moved 1 email to "Work"',answer)
            self.assertEqual(api.messages['m1']['labels'],['UNREAD','STARRED','Label_1'])
            answer=brain.run('label the latest email as Receipts',lambda:False)
        self.assertIn('Created the new label "Receipts"',answer)
        self.assertIn('INBOX',api.messages['m0']['labels'])

    def test_speak_reads_sender_name_and_body_without_quoted_reply(self):
        brain,api=self.fixture()
        with self.offered():
            summary=brain.run('tell me my unread emails',lambda:False)
            self.assertIn('First, from Alice: Trip.',summary)
            answer=brain.run('read aloud the third email',lambda:False)
        self.assertTrue(answer.startswith('Email from Alice. Subject: Lunch plan.'))
        self.assertIn('Lunch at noon?',answer);self.assertNotIn('old quoted line',answer)
        self.assertNotIn('marked as read',answer)
        self.assertEqual(api.writes(),[])

    def test_group_by_sender_and_list_labels_are_read_only(self):
        brain,api=self.fixture()
        with self.offered():
            answer=brain.run('group my emails by sender',lambda:False)
            self.assertIn('Alice (2): Trip; Lunch plan',answer);self.assertIn('Bob (1): Invoice',answer)
            self.assertIn('Work',brain.run('list my gmail labels',lambda:False))
        self.assertEqual(api.writes(),[])

    def test_send_and_delete_draft_by_subject(self):
        brain,api=self.fixture()
        api.drafts['d1']=raw_message({'subject':'Ready','body':'Body','to':'a@example.test'})
        api.drafts['d2']=raw_message({'subject':'Old','body':'Body'})
        with self.offered():
            self.assertIn('sent to a@example.test',brain.run('send the draft with subject "Ready"',lambda:False))
            self.assertIn('deleted',brain.run('delete the draft with subject "Old"',lambda:False))
        self.assertEqual(api.drafts,{})

    def test_denied_approval_and_unlisted_ordinals_never_mutate(self):
        brain,api=self.fixture(approved=False)
        with self.offered():
            with self.assertRaisesRegex(ValueError,'denied'):brain.run('delete the latest email',lambda:False)
            brain.actions.gmail_message_results=[]
            with self.assertRaisesRegex(TaskClarification,'List your emails first'):brain.run('delete the third email',lambda:False)
            with self.assertRaisesRegex(ValueError,'denied'):brain.run('send an email to a@example.test with subject "Hi" and body "Yo"',lambda:False)
        self.assertEqual(api.writes(),[])

    def test_interpreter_label_and_operation_must_match_the_spoken_request(self):
        from jarvis.gmail_workflows import validate_request
        base={'operation':'label','query':'in:inbox','target':'','reference':'latest','subject':'','body':'','to':'',
              'label':'Finance','fields':[],'question':''}
        with self.assertRaisesRegex(TaskClarification,'exact label'):validate_request(base,'label my latest email as work stuff')
        with self.assertRaises(ValueError):validate_request({**base,'operation':'trash'},'read my latest email')
        self.assertEqual(validate_request({**base,'label':'trash'},'move my latest email to trash')['operation'],'trash')


if __name__=='__main__':unittest.main()
