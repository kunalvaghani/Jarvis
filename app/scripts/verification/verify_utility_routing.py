"""Natural-language local Qwen selection, actual Jarvis dispatch and fixed oracles."""
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from uuid import uuid4
from PIL import Image
from jarvis.actions import Actions,Desktop
from jarvis.tools import ToolRegistry
from jarvis.native_tools import plan
from jarvis.knowledge_worker import session

BASE=Path(__file__).resolve().parents[2]


def main():
    root=BASE/'.jarvis-runtime/utility-routing'/uuid4().hex;root.mkdir(parents=True)
    (root/'sales.csv').write_text('name,amount\nA,10\nB,20\nC,\n')
    (root/'settings.yaml').write_text('enabled: true\n')
    Image.new('RGB',(700,150),'white').save(root/'image.png')
    config=json.loads((BASE/'config/config.json').read_text());config['files_root']=str(root)
    config['_ui_verification']=True;config['memory']={**config.get('memory',{}),'enabled':False}
    actions=Actions(config,BASE,lambda *args:None,Desktop())
    actions.approval_handler=lambda kind,detail,stop:kind=='utility_image_process' and str(root) in json.loads(detail)['project'] and not stop()
    report={'date':datetime.now(timezone.utc).isoformat(),'scope':'Actual Qwen native proposals over the normal discovered catalogue, Jarvis Brain dispatcher, independent data/file oracles, then completion proposals. No voice/UI end-to-end claim.','cases':[]}
    cases=[('Check whether this machine has available memory and disk space for a build. Project folder: '+str(root),'skill_system_diagnostics'),
           ('Check sales.csv for missing data in folder '+str(root),'skill_csv_profile'),
           ('Check whether settings.yaml has valid syntax in folder '+str(root),'skill_config_validate'),
           ('Prepare image.png as a smaller JPEG named small.jpg, 350 pixels wide, in folder '+str(root),'skill_image_process')]
    registry=ToolRegistry(actions)
    try:
        with session() as client:
            client.gpu_role='planner'
            for goal,expected_tool in cases:
                row={'goal':goal.replace(str(root),'<owned project>'),'passed':False};report['cases'].append(row);started=time.monotonic()
                completed=[];chosen=[]
                try:
                    for turn in range(4):
                        catalog=registry.catalog(goal)
                        proposal=plan(client,'qwen3.5:9b','You are Jarvis. Select the most suitable offered tool for the user goal. Follow its current typed schema and when/how guidance. Do not invent results. After verified success, propose finish.',
                            {'goal':goal,'tools':catalog,'completed':completed,'project_folder':str(root)}, {'timeout_seconds':180,'num_predict':1200})
                        if proposal.get('done'):
                            if not completed or expected_tool not in chosen:raise AssertionError('Completion before the required actual operation.')
                            row['completion_proposed']=True;break
                        if proposal.get('question'):raise AssertionError('Essential information was already supplied: '+proposal['question'])
                        step=proposal['steps'][0];chosen.append(step['action'])
                        result=actions.brain.dispatch(step,lambda:False)
                        if step['action']==expected_tool:
                            data=json.loads(result.evidence)
                            if expected_tool=='skill_system_diagnostics':assert data['ram_available_bytes']>0 and data['disk_free_bytes']>0
                            elif expected_tool=='skill_csv_profile':assert data['rows']==3 and data['nulls']['amount']==1
                            elif expected_tool=='skill_config_validate':assert data['valid'] and not data['schema_verified']
                            else:assert Image.open(root/'small.jpg').size==(350,75) and Image.open(root/'image.png').size==(700,150)
                            row['independent_oracle_passed']=True
                        completed.append({**step,'verified':True,'result':result.evidence})
                    assert row.get('independent_oracle_passed') and row.get('completion_proposed')
                    row['passed']=True
                except Exception as error:row.update(error_type=type(error).__name__,error=str(error)[:1000])
                row['chosen']=chosen;row['seconds']=round(time.monotonic()-started,3)
                print(json.dumps(row),flush=True)
    finally:
        actions.close();report['passed']=all(row['passed'] for row in report['cases'])
        (BASE/'artifacts/reports/utility-routing.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
