"""Real command/API checks with exact test-draft writes and no mailbox replay."""
from jarvis.paths import APP_ROOT, artifact_path
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

from jarvis.actions import Actions,Desktop
from jarvis.brain import BrainClient
from jarvis.commands import parse
from jarvis.gmail_api import API,directory


def main():
    base=Path(__file__).resolve().parents[2]
    write_trial=sys.argv[1:]==['--approved-new-draft']
    existing_update=sys.argv[1:]==['--approved-existing-update']
    may_write=write_trial or existing_update
    text='Jarvis API command test' if write_trial else 'Jarvis skill test'
    updated=text+' updated' if write_trial else text
    checkpoint=directory(base)/('command-test-checkpoint.json' if write_trial else 'command-existing-checkpoint.json')
    if may_write and checkpoint.exists():
        raise ValueError('The live write trial was already started. Inspect its checkpoint; no write replayed.')
    config=json.loads((base/'config/config.json').read_text());config['_ui_verification']=True
    config['memory']={**config.get('memory',{}),'enabled':False}
    actions=Actions(config,base,lambda *args:None,Desktop())
    client=BrainClient(base,config['brain'])
    report={'date':datetime.now(timezone.utc).isoformat(),'passed':False,
            'scope':'Natural command parsing, normal Actions/Brain/API dispatch with no desktop inference. Only an explicitly approved recipient-free test draft may be written. Separate real Qwen text interpretation; no sends or private mailbox evidence.'}
    state={'write_pending':False};calls=[];original=API.call
    def guarded(api,method,path,**kwargs):
        if method!='GET':
            assert may_write and method in ({'POST','PUT'} if write_trial else {'PUT'}) and path.startswith('drafts')
        calls.append((method,path))
        return original(api,method,path,**kwargs)
    def approval(kind,detail,cancelled):
        row=json.loads(detail);fields=row['fields']
        return (may_write and not cancelled() and fields.get('subject')==text and
                fields.get('body') in {text,updated} and not fields.get('to') and
                (kind=='gmail_api_draft' or (kind=='gmail_api_update_draft' and row['id']==state.get('draft_id'))))
    actions.approval_handler=approval
    def task(goal,write=False):
        if write:
            state['write_pending']=True;checkpoint.write_text(json.dumps(state))
        started=time.monotonic()
        answer=actions._execute(parse(goal))
        elapsed=round(time.monotonic()-started,3)
        if write:
            state.update(write_pending=False,draft_id=actions.gmail_last_draft_id)
            checkpoint.write_text(json.dumps(state))
        return answer,elapsed
    try:
        original_state=(base/'.jarvis-runtime/state/task_state.json').read_bytes()
        with patch.object(API,'call',guarded), \
             patch.object(actions.brain,'observe',side_effect=AssertionError('No desktop reads for Gmail')), \
             patch.object(actions.brain.client,'request',side_effect=AssertionError('Exact commands need no inference')):
            if write_trial:
                answer,seconds=task('draft an email with subject "'+text+'" and body "'+text+'" leave the recipient blank',write=True)
                assert 'Draft saved' in answer
                report.update(draft_create_verified=True,draft_create_seconds=seconds)
            answer,seconds=task('read the Gmail draft with subject "'+text+'"')
            assert text in answer and 'To: (blank)' in answer
            report.update(draft_read_verified=True,draft_read_seconds=seconds)
            if existing_update:
                state['draft_id']=actions.gmail_last_draft_id
            answer,seconds=task('read the email with subject "'+text+'"')
            assert text in answer and 'No emails were changed or marked as read' in answer
            report.update(message_body_read_verified=True,message_read_seconds=seconds)
            if may_write:
                answer,seconds=task('update the Gmail draft with subject "'+text+'" to have body "'+updated+'"',write=True)
                assert 'updated and read back' in answer
                answer,_=task('read the Gmail draft with subject "'+text+'"')
                assert updated in answer and 'To: (blank)' in answer
                report.update(draft_update_readback_verified=True,draft_update_seconds=seconds)
            assert (base/'.jarvis-runtime/state/task_state.json').read_bytes()==original_state
        report.update(task_state_preserved=True,screen_inference_used=False,
                      mailbox_writes=sum(method!='GET' for method,_ in calls),sent=False)
        started=time.monotonic()
        request=client.request('gmail_request',lambda:False,
            goal='Draft an email about arranging a meeting tomorrow; leave the recipient blank.')
        assert request['operation']=='draft' and not request['question'] and request['to']==''
        assert request['subject'].strip() and request['body'].strip()
        assert 'meeting' in (request['subject']+' '+request['body']).casefold()
        report.update(passed=True,qwen_text_composition_verified=True,qwen_seconds=round(time.monotonic()-started,3))
        if may_write:
            state.update(passed=True);checkpoint.write_text(json.dumps(state))
    except Exception as error:
        report.update(error_type=type(error).__name__)
    finally:
        client.close();actions.close()
        target='gmail-command-write-live.json' if write_trial else 'gmail-command-existing-update-live.json' if existing_update else 'gmail-command-read-live.json'
        (artifact_path(base, target)).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
