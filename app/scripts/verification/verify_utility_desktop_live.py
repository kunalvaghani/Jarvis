"""Supervised native test waits for its own window; never steals other app focus."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
import win32gui
from jarvis.actions import Actions,Desktop
from jarvis.utility_tools import run
from jarvis.utility_profiles import fingerprints

BASE=Path(__file__).resolve().parents[2]


def main():
    hashes=fingerprints(BASE)
    root=BASE/'.jarvis-runtime/utility-desktop-live'/uuid4().hex;root.mkdir(parents=True)
    title='Jarvis utility foreground test '+root.name[:8];marker=root/'activated.txt'
    config=json.loads((BASE/'config/config.json').read_text());config['_ui_verification']=True
    config['files_root']=str(root);config['memory']={**config.get('memory',{}),'enabled':False}
    actions=Actions(config,BASE,lambda *args:None,Desktop())
    actions.approval_handler=lambda kind,detail,stop:kind=='utility_desktop_control' and not stop()
    child=subprocess.Popen([sys.executable,str(BASE/'tests/fixtures/utility_desktop.py'),title,str(marker)],creationflags=subprocess.CREATE_NO_WINDOW)
    row={'id':'desktop_control','passed':False,'date':datetime.now(timezone.utc).isoformat()}
    try:
        deadline=time.monotonic()+180;last_notice=0
        while time.monotonic()<deadline:
            if child.poll() is not None:raise ValueError('Owned test window was closed; no restart or action replay.')
            hwnd=win32gui.FindWindow(title,title)
            if hwnd and Path(str(marker)+'.ready').exists() and win32gui.GetForegroundWindow()==hwnd:break
            if time.monotonic()-last_notice>25:print('Waiting for the owned test window to receive foreground focus.',flush=True);last_notice=time.monotonic()
            time.sleep(.1)
        else:raise ValueError('Owned foreground test timed out; no other window was clicked.')
        if marker.exists():raise ValueError('Fixture button was manually activated before the test; fresh test required.')
        result=run(actions,'desktop_control',root,{'control':'Verify fixture'},lambda:False)
        deadline=time.monotonic()+3
        while not marker.exists() and time.monotonic()<deadline:time.sleep(.05)
        assert marker.read_text()=='activated' and not result['shared_mouse_used']
        if hashes!=fingerprints(BASE):raise ValueError('Source changed during the live test.')
        row.update(passed=True,evidence={'scope':'Actual supervised owned native button; independently read its file effect','activated':True,'shared_mouse_used':False,'automatic_enter':False})
    except Exception as error:row.update(error_type=type(error).__name__,error=str(error)[:600])
    finally:
        actions.close()
        if child.poll() is None:child.terminate()
        child.wait(timeout=3)
        (BASE/'artifacts/reports/utility-desktop-live.json').write_text(json.dumps(row,indent=2)+'\n')
    if row['passed']:
        path=BASE/'artifacts/reports/utility-validation.json';report=json.loads(path.read_text())
        if report['source_hashes']!=hashes:raise ValueError('Base validation is stale; activation withheld.')
        report['skills']=[row if item['id']=='desktop_control' else item for item in report['skills']]
        report['passed']=all(item['passed'] for item in report['skills'])
        path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(row),flush=True)
    return 0 if row['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
