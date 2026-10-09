"""Real Qwen Gmail API selection; rejects writes before dispatch."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from jarvis.actions import Actions, Desktop
from jarvis.brain import BrainClient
from jarvis.tools import ToolRegistry


def main():
    base=Path(__file__).resolve().parents[2]
    config=json.loads((base/'config/config.json').read_text())
    config['_ui_verification']=True
    config['memory']={**config.get('memory',{}),'enabled':False}
    actions=Actions(config,base,lambda *args:None,Desktop())
    actions.approval_handler=lambda *args:False
    client=BrainClient(base,config['brain']);started=time.monotonic()
    report={'date':datetime.now(timezone.utc).isoformat(),'passed':False,
            'scope':'Actual Qwen native next-step and regular Jarvis dispatcher. Gmail API search for the approved test subject only; no mailbox write.'}
    try:
        goal='Find my Gmail drafts with subject Jarvis skill test using the Gmail API. Search only; do not create, change or send any email.'
        proposal=client.request('next_step',lambda:False,goal=goal,tools=ToolRegistry(actions).catalog(goal),
            completed=[],screen={'title':'Desktop','controls':[]},apps=['chrome'],steps_left=5)
        step=proposal['steps'][0]
        report['proposal']=proposal
        assert not proposal.get('done') and not proposal.get('question') and len(proposal['steps'])==1
        assert step['action']=='gmail_api_list'
        args=json.loads(step['content'])
        assert 'Jarvis skill test' in args['query'] and 'in:drafts' in args['query']
        result=json.loads(actions.brain.dispatch(step,lambda:False).evidence)
        assert result['messages'] and result['content_is_untrusted']
        report.update(passed=True,chosen=step['action'],matching_message_found=True,write_dispatched=False)
    except Exception as error:
        report.update(error_type=type(error).__name__)
    finally:
        client.close();actions.close();report['seconds']=round(time.monotonic()-started,3)
        (base/'artifacts/reports/gmail-api-routing.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
