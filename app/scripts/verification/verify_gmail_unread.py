"""Exact reported task, live read-only API; published evidence contains no mail."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from unittest.mock import patch

from jarvis.actions import Actions, Desktop
from jarvis.brain import BrainClient
from jarvis.commands import parse
from jarvis.gmail_api import API
from jarvis.tools import ToolRegistry


def main():
    base=Path(__file__).resolve().parents[2]
    config=json.loads((base/'config/config.json').read_text())
    config['_ui_verification']=True
    config['memory']={**config.get('memory',{}),'enabled':False}
    actions=Actions(config,base,lambda *args:None,Desktop())
    actions.approval_handler=lambda *args:False
    client=BrainClient(base,config['brain'])
    report={'date':datetime.now(timezone.utc).isoformat(),'passed':False,
            'scope':'Exact reported task through command parsing, Actions task handling, Brain.run and standard dispatcher; live Gmail metadata only. Separate real Qwen proposal also checked. No mailbox write, screen or microphone.'}
    requests=[];original=API.call
    def readonly(api,method,path,**kwargs):
        assert method=='GET', 'Mailbox writes forbidden by independent live verifier'
        requests.append((method,path,kwargs.get('params',{})))
        return original(api,method,path,**kwargs)
    try:
        goal='find my unread emails'
        original_state=(base/'.jarvis-runtime/state/task_state.json').read_bytes()
        with patch.object(API,'call',readonly), \
             patch.object(actions.brain,'observe',side_effect=AssertionError('Screen should not be used')), \
             patch.object(actions.brain.client,'request',side_effect=AssertionError('Inference should not be used')):
            started=time.monotonic()
            command=parse(goal)
            assert command.kind=='task' and command.value==goal
            answer=actions._execute(command)
            direct_seconds=round(time.monotonic()-started,3)
        assert answer and 'No emails were changed or marked as read' in answer
        observations=actions.brain.tool_observations
        assert len(observations)==1 and observations[0]['action']=='gmail_api_list'
        data=json.loads(observations[0]['result'])
        rows=data['messages']
        assert len(rows)<=5 and all('unread' in row and 'subject' in row and 'from' in row for row in rows)
        assert requests[0][1:] == ('messages',{'maxResults':5,'q':'is:unread'})
        assert all(params.get('format')=='metadata' for _,_,params in requests[1:])
        assert (base/'.jarvis-runtime/state/task_state.json').read_bytes()==original_state
        report.update(direct_task_passed=True,direct_seconds=direct_seconds,metadata_only=True,
                      task_state_preserved=True,mailbox_write_dispatched=False,
                      screen_or_model_used_for_exact_task=False)
        # A complex goal still goes through Qwen; the oracle rejects app search or wrong filters.
        started=time.monotonic()
        proposal=client.request('next_step',lambda:False,
            goal='Find my unread emails from the last seven days using Gmail API. List sender and subject only; do not mark as read or fetch full bodies.',
            tools=ToolRegistry(actions).catalog(goal),completed=[],
            screen={'title':'Desktop','controls':[]},apps=['chrome'],steps_left=5)
        assert not proposal.get('done') and not proposal.get('question') and len(proposal['steps'])==1
        step=proposal['steps'][0]
        assert step['action']=='gmail_api_list'
        args=json.loads(step['content'])
        assert 'is:unread' in args['query'] and 'newer_than:7d' in args['query']
        assert args.get('summaries') is True and 1<=args.get('limit',5)<=10
        report.update(passed=True,qwen_filtered_search_proposal_passed=True,
                      qwen_seconds=round(time.monotonic()-started,3))
    except Exception as error:
        report.update(error_type=type(error).__name__)
    finally:
        client.close();actions.close()
        (base/'artifacts/reports/gmail-unread-live.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
