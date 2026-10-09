"""Twenty actual native UI actions via Brain, ToolRegistry and guarded UIControls."""
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace


def main():
    import win32api, win32con, win32gui, win32process
    from jarvis.brain import Brain
    from jarvis.task_state import TaskState
    from jarvis.ui_controls import UIControls
    base = Path(__file__).resolve().parents[2]
    previous = base / 'artifacts/reports/plan-native-live-check.json'
    history_path = previous.with_name('plan-native-live-check-history.json')
    if previous.exists():
        history = json.loads(history_path.read_text()) if history_path.exists() else []
        history.append(json.loads(previous.read_text()))
        history_path.write_text(json.dumps(history, indent=2)+'\n', encoding='utf-8')
    root = base / '.jarvis-runtime/plan-native-fixture' / str(time.time_ns())
    root.mkdir(parents=True)
    state_file = root / 'state.json'
    original = win32gui.GetForegroundWindow()
    process = subprocess.Popen([sys.executable, str(base / 'tests/plan_native_fixture.py'), str(state_file)],
        cwd=base, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    record = {'date': datetime.now(timezone.utc).isoformat(), 'passed': False,
              'scope': 'Owned Win32 fixture, full Brain execution loop, actual fresh-control activation, independent window-event order. Authored plan and deterministic result verifier; no LLM or microphone claim.'}
    ui, handle = None, None
    try:
        deadline = time.monotonic()+10
        while not state_file.exists() and time.monotonic()<deadline and process.poll() is None:
            time.sleep(.05)
        handle = json.loads(state_file.read_text())['root']
        foreground_thread = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
        thread = win32api.GetCurrentThreadId()
        attached = ctypes.windll.user32.AttachThreadInput(thread, foreground_thread, True)
        try:
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(handle)
        finally:
            if attached:
                ctypes.windll.user32.AttachThreadInput(thread, foreground_thread, False)
        if win32gui.GetForegroundWindow() != handle:
            raise RuntimeError('Owned fixture did not take foreground; no input dispatched')
        desktop = SimpleNamespace(user=SimpleNamespace(GetForegroundWindow=lambda: handle,
            GetWindowThreadProcessId=ctypes.windll.user32.GetWindowThreadProcessId,
            IsWindow=win32gui.IsWindow, IsWindowVisible=win32gui.IsWindowVisible), target=handle)
        ui = UIControls(desktop, external_handle=lambda: handle)
        steps = [{'action': 'select', 'value': f'Stage {i:02d}', 'expected': f'Stage {i:02d} done',
                  'id': i-1, 'dep': [i-2] if i>1 else [-1]} for i in range(1, 21)]
        goal = 'In the fixture activate these stages in exact order:\n' + '\n'.join(f'{i}. select Stage {i:02d}' for i in range(1, 21))
        state = TaskState(root)
        state.start(goal, 'task')
        actions = SimpleNamespace(base=root, config={}, apps={}, _ui=lambda: ui, task_state=state,
            report=lambda *_: None, skills=None, memory=None, live_app=None, resume_source=None, pending_open=None,
            last_created=None, last_modified=None, last_deleted=None, last_command=None,
            allowed_tools={'select'})
        brain = Brain(actions, root, {'enabled': True, 'planner': 'authored-fixture-plan', 'decision': 'fresh-unique-control',
                                      'fast_grounding': True, 'task_recovery': True, 'max_task_actions': 20})
        class Client:
            def request(self, operation, cancelled, **data):
                if operation == 'plan':
                    return {'question': '', 'steps': steps}
                if operation == 'verify':
                    actual = json.loads(state_file.read_text())['completed']
                    wanted = 20 if data['step']['action'] == 'goal' else data['step']['id']+1
                    return {'verified': actual == list(range(1, wanted+1)), 'reason': 'Independent fixture event list exact order'}
                raise AssertionError('Unexpected model request: '+operation)
        brain.client = Client()
        started = time.monotonic()
        record['reply'] = brain.run(goal, lambda: False)
        actual = json.loads(state_file.read_text())['completed']
        record.update(completed=actual, seconds=round(time.monotonic()-started, 3),
                      completed_checkpoints=len(state.snapshot()['plan']['completed']),
                      passed=actual==list(range(1, 21)) and len(state.snapshot()['plan']['completed'])==20
                             and record['reply'].startswith('Finished.'))
    except Exception as exc:
        record.update(error_type=type(exc).__name__, error=str(exc)[:700])
    finally:
        if ui:
            ui.close()
        if handle and win32gui.IsWindow(handle):
            win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        process.stderr.close()
        if original and win32gui.IsWindow(original):
            try:
                win32gui.SetForegroundWindow(original)
            except Exception:
                pass
        (base / 'artifacts/reports/plan-native-live-check.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(record, indent=2), flush=True)
    raise SystemExit(0 if record['passed'] else 1)


if __name__ == '__main__':
    main()
