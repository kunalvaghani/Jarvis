"""Reported email request plus ordinary real-Qwen planning; no action dispatch."""
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
    config['memory']={**config.get('memory',{}),'enabled':False}
    config['_ui_verification']=True
    app=Actions(config,base,lambda *args:None,Desktop())
    client=BrainClient(base,config['brain'])
    report={'date':datetime.now(timezone.utc).isoformat(),
            'scope':'Normal next-step worker; email readiness guard and actual Qwen app-opening proposal. No actions dispatched or email transmitted.',
            'cases':[]}
    try:
        for goal in ('draft an email about me','open chrome'):
            row={'goal':goal,'passed':False};started=time.monotonic()
            try:
                proposal=client.request('next_step',lambda:False,goal=goal,
                    tools=ToolRegistry(app).catalog(goal),completed=[],
                    screen={'title':'Desktop','controls':[]},apps=['chrome'],steps_left=5)
                row['proposal']=proposal
                assert proposal.get('done') is not True
                if goal.startswith('draft'):
                    assert proposal.get('source')=='gmail_readiness' and not proposal['steps'] and proposal['question']
                else:
                    assert len(proposal['steps'])==1
                    assert proposal['steps'][0]['action']=='open' and proposal['steps'][0]['value'].casefold() in {'chrome','google chrome'}
                row['passed']=True
            except Exception as error:
                row.update(error_type=type(error).__name__,error=str(error))
            row['seconds']=round(time.monotonic()-started,3);report['cases'].append(row)
            print(json.dumps(row),flush=True)
    finally:
        client.close();app.close()
        report['passed']=all(row['passed'] for row in report['cases'])
        (base/'artifacts/reports/email-planner-repair.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
