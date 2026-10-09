"""Live animated-site trial: application source is written only by Jarvis/Codex."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time
from types import SimpleNamespace
import uuid
from jarvis.coder import Coder

BASE=Path(__file__).resolve().parents[2]


def verify(client_date=None):
    project=BASE/'.jarvis-runtime/codex-workload-fixture'/uuid.uuid4().hex;project.mkdir(parents=True)
    options=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))['brain']
    options.update(codex_workload_enabled=True,max_coding_seconds=3600,codex_max_repairs=3)
    started=time.monotonic();events=[]
    def report(kind,value):
        events.append((kind,value))
        if kind=='brain' or (kind=='task_status' and any(s in value.get('phase','') for s in ('Planning','Correcting','Checking','issues','repair','ended'))):
            print(json.dumps({'kind':kind,'value':value}),flush=True)
    coder=Coder(SimpleNamespace(base=BASE,report=report),SimpleNamespace(options=options))
    record={'date':datetime.now(timezone.utc).isoformat(),'project':str(project),
            'scope':'Actual Jarvis workload planner, separate Codex/local Qwen sessions, LocalGithub Git assembly, per-worker tests and final animated browser interaction. No manually authored application source.'}
    if client_date:record['client_date']=client_date
    stop_file=project.parent/(project.name+'-stop.json')
    record['stop_file']=str(stop_file)
    goal=('Build an animated responsive plain HTML/CSS/JavaScript website named Orbit Studio. '
        'Use index.html, styles.css and app.js, no external resources or dependencies. '
        'Dark purple glass panels, moving luminous orb .orb, subtle entrance animations and responsive cards. '
        'Include h1 Orbit Studio, three feature cards and button #theme initially labelled Light mode. '
        'Click #theme toggles its visible button text between Light mode and Dark mode, and toggles the page light/dark theme. Keep the button stationary for reliable clicks. '
        'Split markup, styles and JS behavior into balanced workloads, each verified by Jarvis actual Chrome component tests. '
        'Agree exact selectors/classes and filenames before coding. Markup checks actual controls and .orb presence; '
        'style checks actual advancing animation and responsive rendering; JS checks actual theme toggle behavior in Chrome against that markup. '
        'Use a final browser check: text #theme "Light mode", click #theme, text #theme "Dark mode", click #theme, text #theme "Light mode". '
        'Include animation_selectors:[".orb"] in the final browser check. No backend or framework needed. '
        'Keep each source file under 6000 characters. Jarvis supplies the component tests; do not author test files or Node mocks.')
    try:
        record['response']=coder.run(project,goal,cancelled=stop_file.exists,selected=True)
        candidates=[p for p in (BASE/'.jarvis-runtime/codex-workloads').glob('*/receipt.json')
                    if json.loads(p.read_text(encoding='utf-8')).get('project')==str(project)]
        receipt=json.loads(candidates[-1].read_text(encoding='utf-8'))
        assert receipt['status']=='passed' and len(receipt['workers'])>=2,'No completed multi-session assembly'
        browser=next(c for c in receipt['validation']['checks'] if c['kind']=='browser')
        assert '".orb"' in browser['output'],'Rendered advancing animation not verified'
        record.update(passed=True,workers=receipt['workers'],checks=receipt['validation']['checks'],review=str(candidates[-1].parent))
        screenshots=list(candidates[-1].parent.glob('combined-check/check-workspace-*/browser-check.png'))
        if not screenshots:
            for result in (BASE/'.jarvis-runtime/codex-code').glob('*/result.json'):
                data=json.loads(result.read_text(encoding='utf-8'))
                if data.get('project')==str(candidates[-1].parent/'integration') and data.get('functional_behavior_verified'):
                    screenshots.extend(result.parent.glob('check-workspace-*/browser-check.png'))
        if screenshots:
            destination=BASE/'artifacts/media/codex-workload-live.png';shutil.copyfile(screenshots[-1],destination)
            record['screenshot']='artifacts/media/codex-workload-live.png'
            desktop=screenshots[-1].with_name('browser-check-desktop.png')
            if desktop.exists():
                destination=BASE/'artifacts/media/codex-workload-live-desktop.png';shutil.copyfile(desktop,destination)
                record['desktop_screenshot']='artifacts/media/codex-workload-live-desktop.png'
    except Exception as error:record.update(passed=False,error=str(error))
    record.update(seconds=round(time.monotonic()-started,3),progress_events=sum(k=='task_status' for k,v in events))
    path=BASE/'artifacts/reports/codex-workload-live-check.json'
    if path.exists():
        history=path.with_name('codex-workload-live-history.json');rows=json.loads(history.read_text()) if history.exists() else []
        rows.append(json.loads(path.read_text()));history.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in record.items() if k not in {'workers','checks'}},indent=2),flush=True)
    return record['passed']


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--client-date')
    arguments=parser.parse_args()
    raise SystemExit(0 if verify(arguments.client_date) else 1)
