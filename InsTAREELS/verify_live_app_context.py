"""Own Win32 app: observe controls, direct follow-up input, then closure guards."""
from datetime import datetime,timezone
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock


def main():
    import win32con,win32gui
    from jarvis.live_app_context import LiveAppContext
    from jarvis.ui_controls import UIControls
    from jarvis.commands import Command
    from jarvis.ui_worker import perform
    from jarvis.direct_execution import run
    from jarvis.task_state import TaskState
    base=Path(__file__).resolve().parent
    folder=base/'.jarvis-runtime/live-app-fixture'/str(time.time_ns())
    folder.mkdir(parents=True)
    state_file=folder/'state.json'
    original=win32gui.GetForegroundWindow()
    process=subprocess.Popen([sys.executable,str(base/'tests/execution_native_fixture.py'),str(state_file)],
        cwd=base,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    result={'date':datetime.now(timezone.utc).isoformat(),
        'scope':'Actual owned Win32 fixture, accessible controls, two direct follow-up tasks and close/stale-target guards. No user-app input, private desktop capture, microphone or model inference.', 'passed':False}
    ui=None
    handle=0
    try:
        deadline=time.monotonic()+10
        while not state_file.exists() and time.monotonic()<deadline and process.poll() is None:
            time.sleep(.05)
        handles=json.loads(state_file.read_text())['handles']
        handle=handles['root']
        # Focus only the owned fixture, without synthetic keys or clicks.
        import win32api,win32process
        current_thread=win32api.GetCurrentThreadId()
        foreground_thread=win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
        attached=bool(ctypes.windll.user32.AttachThreadInput(current_thread,foreground_thread,True))
        try:
            win32gui.ShowWindow(handle,win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(handle)
        finally:
            if attached:ctypes.windll.user32.AttachThreadInput(current_thread,foreground_thread,False)
        if win32gui.GetForegroundWindow()!=handle:
            raise RuntimeError('Owned fixture did not take focus; no input issued')
        context=LiveAppContext(foreground=lambda:handle)
        desktop=SimpleNamespace(user=SimpleNamespace(GetForegroundWindow=lambda:handle,
            GetWindowThreadProcessId=ctypes.windll.user32.GetWindowThreadProcessId,
            IsWindow=win32gui.IsWindow,IsWindowVisible=win32gui.IsWindowVisible),target=handle)
        ui=UIControls(desktop,external_handle=lambda:handle)
        ui.live_app=context
        observed=context.refresh(ui)
        result['initial_controls']=[row['name'] for row in observed['current']['controls']]
        assert 'Apply' in result['initial_controls'] and observed['current']['status']=='open'
        stale=next(row for row in ui.runner({'operation':'list','handle':handle,'owner_pid':os.getpid()},lambda:False)['controls'] if row['name']=='Apply')
        ui.execute(Command('click_control','Apply'))
        changed=context.refresh(ui)
        result['updated_controls']=[row['name'] for row in changed['current']['controls']]
        assert 'Applied 1' in result['updated_controls']
        brain=Mock()
        brain.run.side_effect=AssertionError('Direct task called planner')
        actions=SimpleNamespace(_ui=lambda:ui,task_state=TaskState(folder),config={},report=Mock(),
            brain=brain,resume_source=None)
        actions.task_state.start('click Applied 1','task')
        result['followup']=run(actions,'click Applied 1',lambda:False)
        result['generic_click_result_scope']='Dispatch recorded; generic label change is not proof of an arbitrary application goal. Independent fixture counter confirms the requested click.'
        final=context.refresh(ui)
        assert any(row['name']=='Applied 2' for row in final['current']['controls'])
        result['direct_model_calls']=brain.run.call_count
        result['click_count']=json.loads(state_file.read_text())['clicks']
        assert result['click_count']==2
        win32gui.PostMessage(handle,win32con.WM_CLOSE,0,0)
        process.wait(timeout=5)
        closed=context.snapshot()['current']
        result['closed_status']=closed['status']
        result['closed_controls']=closed['controls']
        assert closed['status']=='closed' and closed['controls']==[]
        try:
            ui.execute(Command('click_control','Applied 2'))
        except ValueError:
            result['closed_followup_blocked']=True
        else:
            raise AssertionError('Closed app allowed UI input')
        try:
            perform({'operation':'activate','handle':handle,'owner_pid':os.getpid(),'control':stale,'verb':'click'})
        except ValueError as exc:
            result['stale_target_blocked']='closed' in str(exc)
        else:
            raise AssertionError('Old control allowed UI input')
        result['passed']=result['stale_target_blocked'] and result['closed_followup_blocked']
    finally:
        if ui:ui.close()
        if handle and win32gui.IsWindow(handle):
            win32gui.PostMessage(handle,win32con.WM_CLOSE,0,0)
        if process.poll() is None:
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        process.stderr.close()
        if original and win32gui.IsWindow(original):
            try:win32gui.SetForegroundWindow(original)
            except Exception:pass
        (base/'artifacts/live-app-context-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
