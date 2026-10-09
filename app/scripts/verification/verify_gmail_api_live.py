"""Supervised live API trial; only the approved recipient-free test draft writes."""
from datetime import datetime, timezone
import json
from pathlib import Path

from jarvis.actions import Actions, Desktop
from jarvis.gmail_api import configured, directory
from jarvis.toolkits import execute
from jarvis.tools import ToolRegistry

BASE = Path(__file__).resolve().parents[2]
TEXT = 'Jarvis skill test'


def main():
    if not configured(BASE):raise ValueError('Complete local OAuth before the live trial.')
    checkpoint=directory(BASE)/'live-test-checkpoint.json'
    if checkpoint.exists():
        old=json.loads(checkpoint.read_text())
        if old.get('write_pending'):raise ValueError('Earlier write outcome needs inspection; no test action replayed.')
        if old.get('passed'):raise ValueError('This live trial already passed; no repeated mailbox writes.')
    config=json.loads((BASE/'config/config.json').read_text())
    config['_ui_verification']=True
    config['memory']={**config.get('memory',{}),'enabled':False}
    actions=Actions(config,BASE,lambda *args:None,Desktop())
    report={'date':datetime.now(timezone.utc).isoformat(),'passed':False,
            'scope':'Actual Gmail API via normal Jarvis toolkit dispatcher. Reads and writes only a recipient-free Jarvis skill test draft. No send or private message content in this report.'}
    state={'write_pending':False}
    def approval(kind,detail,stop):
        row=json.loads(detail);args=row['fields']
        return (not stop() and kind in {'gmail_api_draft','gmail_api_update_draft'}
                and args.get('subject')==TEXT and args.get('body')==TEXT and not args.get('to'))
    actions.approval_handler=approval
    def call(name,value='inspect',args=None):
        return json.loads(execute(actions,{'action':name,'value':value,'content':json.dumps(args or {}),'expected':'Verify actual Gmail API response','folder':''},lambda:False))
    def write(name,value,args):
        state.update(write_pending=True,operation=name,draft_id=value)
        checkpoint.write_text(json.dumps(state))
        result=call(name,value,args)
        state.update(write_pending=False,draft_id=result['draft_id'])
        checkpoint.write_text(json.dumps(state))
        return result
    try:
        offered={row['action'] for row in ToolRegistry(actions).catalog('Read Gmail and draft an email')}
        required={'gmail_api_list','gmail_api_read','gmail_api_list_drafts','gmail_api_read_draft','gmail_api_draft','gmail_api_update_draft'}
        assert required<=offered
        report['stage']='find_approved_test'
        search=call('gmail_api_list',args={'query':'in:drafts subject:"Jarvis skill test"','limit':10})
        test_message_ids={item['id'] for item in search['messages']}
        listing=call('gmail_api_list_drafts',args={'limit':10})
        matches=[]
        for item in listing['drafts']:
            if item.get('message',{}).get('id') not in test_message_ids:continue
            draft=call('gmail_api_read_draft',item['id'])
            if draft['subject']==TEXT and draft['body'].strip()==TEXT and not draft['to'] and not draft['cc']:
                matches.append(draft)
        if len(matches)>1:raise ValueError('Multiple matching test drafts; select one explicitly before writing.')
        if matches:
            draft=matches[0];report['existing_test_draft_reused']=True
        else:
            search=call('gmail_api_list',args={'query':'in:drafts subject:"Jarvis skill test"','limit':10})
            if search['messages']:raise ValueError('An existing test draft needs explicit selection; no duplicate created.')
            created=write('gmail_api_draft','new',{'subject':TEXT,'body':TEXT})
            draft=call('gmail_api_read_draft',created['draft_id'])
            report['draft_create_live_verified']=True
        search=call('gmail_api_list',args={'query':'in:drafts subject:"Jarvis skill test"','limit':10})
        message_read=False
        for item in search['messages']:
            message=call('gmail_api_read',item['id'])
            if message['subject']==TEXT and message['body'].strip()==TEXT and not message['to']:
                message_read=True;break
        assert message_read
        updated=write('gmail_api_update_draft',draft['id'],{'subject':TEXT,'body':TEXT,'expected_sha256':draft['sha256']})
        assert updated['subject_verified'] and updated['body_verified'] and not updated['recipient_set'] and not updated['sent']
        report.update(passed=True,configured_tools_offered=True,message_search_and_read_verified=True,
                      draft_list_and_read_verified=True,draft_update_readback_verified=True,recipient_set=False,sent=False)
        state.update(passed=True)
    except Exception as error:
        # Only adapter-controlled errors, never raw Google responses or credentials.
        report.update(error_type=type(error).__name__)
        if isinstance(error,ValueError):report['error']=str(error)[:300]
        print('Live API trial failed; inspect local checkpoint before any new write.',flush=True)
    finally:
        actions.close();checkpoint.write_text(json.dumps(state))
        (BASE/'artifacts/reports/gmail-api-live.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
