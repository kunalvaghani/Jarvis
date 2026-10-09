"""Live send/speak/label/Trash/draft checks through real Jarvis commands.

Only mail created by this run (unique subject tag, sent to the account's own
address) can be approved or changed. Published evidence holds flags and timings,
never addresses, IDs or mail text. No write is replayed after a failure."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from unittest.mock import patch

from jarvis.actions import Actions, Desktop
from jarvis.brain import BrainClient
from jarvis.commands import parse
from jarvis.gmail_api import API, directory
from jarvis.paths import artifact_path


def main():
    base=Path(__file__).resolve().parents[2]
    checkpoint=directory(base)/'actions-live-checkpoint.json'
    if checkpoint.exists() and json.loads(checkpoint.read_text()).get('write_pending'):
        raise ValueError('An earlier live write has an uncertain outcome. Inspect the mailbox first; no write replayed.')
    tag='Jarvis live test '+datetime.now().strftime('%Y%m%d%H%M%S')
    subject,draft_subject,discard_subject=tag,tag+' draft',tag+' discard'
    label='Jarvis Test'
    config=json.loads((base/'config/config.json').read_text());config['_ui_verification']=True
    config['memory']={**config.get('memory',{}),'enabled':False}
    actions=Actions(config,base,lambda *args:None,Desktop())
    client=BrainClient(base,config['brain'])
    direct=API(base)
    me=direct.call('GET','profile')['emailAddress']
    state={'write_pending':False,'drafts':set()};calls=[];original=API.call
    report={'date':datetime.now(timezone.utc).isoformat(),'passed':False,
            'scope':'Real command parsing and Actions/Brain/API dispatch. Writes limited to mail created by this run and sent to the account itself; no other mailbox content approved.'}

    def guarded(api,method,path,**kwargs):
        if method!='GET':
            assert re.fullmatch(r'messages/send|drafts|drafts/send|drafts/[\w-]+|labels|messages/[\w-]+/(?:trash|untrash|modify)',path),path
        calls.append((method,path))
        return original(api,method,path,**kwargs)

    def approval(kind,detail,cancelled):
        row=json.loads(detail);fields=row['fields']
        if cancelled():return False
        if kind in {'gmail_api_send','gmail_api_draft'}:
            return fields.get('subject','').startswith(tag) and fields.get('to','') in {me,''}
        if kind in {'gmail_api_send_draft','gmail_api_delete_draft'}:
            return row['id'] in state['drafts']
        if kind in {'gmail_api_trash','gmail_api_untrash','gmail_api_modify_labels'}:
            preview=fields.get('preview',[])
            return bool(preview) and len(preview)==len(fields['ids']) and all(tag in line for line in preview)
        return False
    actions.approval_handler=approval

    def task(goal,write=False):
        if write:
            state['write_pending']=True;checkpoint.write_text(json.dumps({'write_pending':True,'tag':tag}))
        started=time.monotonic()
        answer=str(actions._execute(parse(goal)))
        if write:
            state['write_pending']=False;checkpoint.write_text(json.dumps({'write_pending':False,'tag':tag}))
        return answer,round(time.monotonic()-started,3)

    def labels_of(text):
        rows=direct.call('GET','messages',params={'q':'subject:"'+text+'" in:anywhere','maxResults':5}).get('messages',[])
        assert len(rows)==1,('expected one message',len(rows))
        return set(direct.call('GET','messages/'+rows[0]['id'],params={'format':'minimal'}).get('labelIds',[]))

    def delivered(text):
        for _ in range(30):
            rows=direct.call('GET','messages',params={'q':'subject:"'+text+'" in:inbox','maxResults':5}).get('messages',[])
            if rows:return
            time.sleep(2)
        raise ValueError('Self-sent test email did not reach the inbox in 60 seconds.')

    timings={}
    try:
        with patch.object(API,'call',guarded), \
             patch.object(actions.brain,'observe',side_effect=AssertionError('No desktop reads for Gmail')), \
             patch.object(actions.brain.client,'request',side_effect=AssertionError('Exact commands need no inference')):
            answer,timings['send']=task('send an email to '+me+' with subject "'+subject+'" and body "Hello from the Jarvis live test."',True)
            assert 'Email sent' in answer;delivered(subject);report['send_verified']=True

            answer,timings['speak']=task('read aloud the email with subject "'+subject+'"')
            assert answer.startswith('Email from') and 'Hello from the Jarvis live test.' in answer;report['speak_verified']=True

            answer,timings['mark_read']=task('mark the first email as read',True)
            assert 'UNREAD' not in labels_of(subject);report['mark_read_verified']=True

            answer,timings['star']=task('star the email with subject "'+subject+'"',True)
            assert 'STARRED' in labels_of(subject);report['star_verified']=True

            answer,timings['label']=task('label the email with subject "'+subject+'" as '+label,True)
            assert 'Labelled 1 email' in answer;report['label_verified']=True

            answer,timings['move']=task('move the email with subject "'+subject+'" to '+label,True)
            assert 'INBOX' not in labels_of(subject);report['move_verified']=True

            answer,timings['list_labels']=task('list my gmail labels')
            assert label in answer;report['list_labels_verified']=True

            answer,timings['group']=task('group my emails by sender')
            assert 'grouped by sender' in answer or 'No matching' in answer;report['group_verified']=True

            answer,timings['trash']=task('delete the email with subject "'+subject+'"',True)
            assert 'TRASH' in labels_of(subject);report['trash_verified']=True

            answer,timings['restore']=task('restore the email with subject "'+subject+'"',True)
            assert 'TRASH' not in labels_of(subject);report['restore_verified']=True

            answer,timings['draft']=task('draft an email to '+me+' with subject "'+draft_subject+'" and body "Draft sent by the Jarvis live test."',True)
            assert 'Draft saved' in answer;state['drafts'].add(actions.gmail_last_draft_id)
            answer,timings['send_draft']=task('send the draft with subject "'+draft_subject+'"',True)
            assert 'sent to' in answer;delivered(draft_subject);report['send_draft_verified']=True

            answer,_=task('draft an email with subject "'+discard_subject+'" and body "Discard me." leave the recipient blank',True)
            state['drafts'].add(actions.gmail_last_draft_id)
            answer,timings['delete_draft']=task('delete the draft with subject "'+discard_subject+'"',True)
            assert 'deleted' in answer;report['delete_draft_verified']=True

            # Clean up: test emails to Trash through Jarvis, the test label directly.
            for text in (subject,draft_subject):task('delete the email with subject "'+text+'"',True)
            report['cleanup_trashed']=True
        for row in direct.call('GET','labels').get('labels',[]):
            if row.get('name')==label and row.get('type')=='user':direct.call('DELETE','labels/'+row['id'])
        report['cleanup_label_removed']=True
        report.update(timings_seconds=timings,mailbox_writes=sum(method!='GET' for method,_ in calls),screen_inference_used=False)

        started=time.monotonic()
        request=client.request('gmail_request',lambda:False,goal='send an email to '+me+' asking whether the test passed')
        assert request['operation']=='send' and request['to']==me and request['subject'].strip() and request['body'].strip()
        request=client.request('gmail_request',lambda:False,goal='move my latest email from the bank to the Finance label')
        assert request['operation']=='label' and request['label'].casefold()=='finance'
        report.update(passed=True,qwen_interpretation_verified=True,qwen_seconds=round(time.monotonic()-started,3))
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error).replace(me,'<account>')[:300],timings_seconds=timings)
    finally:
        client.close();actions.close();direct.close()
        artifact_path(base,'gmail-actions-live.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
