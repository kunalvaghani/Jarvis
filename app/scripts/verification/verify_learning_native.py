"""Actual owned UIA app discovery -> local help -> Brain -> SVG -> verified memory."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[2]

def main(implicit=False):
    import win32api, win32con, win32gui, win32process
    from jarvis.actions import Actions
    from jarvis.commands import Command
    from jarvis.ui_controls import UIControls
    root = BASE/'.jarvis-runtime/learning-native'/str(time.time_ns())
    root.mkdir(parents=True)
    (root/'help.md').write_text('Learning Fixture: use the Create diagram button. A successful click creates diagram.svg and changes its label to Diagram created.', encoding='utf-8')
    original = win32gui.GetForegroundWindow()
    process = subprocess.Popen([sys.executable, '-m', 'scripts.verification.learning_native_fixture', str(root)],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    actions = ui = None
    handle = None
    started = time.monotonic()
    result = {'date': '2026-10-14 IST', 'scope': 'Actual owned native app/version/UIA discovery, configured local help, Brain/ToolRegistry action, independent SVG readback and shared-memory promotion. Authored planner and deterministic oracle, no live LLM or internet claim.'}
    try:
        deadline = time.monotonic()+15
        while not (root/'state.json').exists() and time.monotonic()<deadline:
            time.sleep(.05)
        handle = json.loads((root/'state.json').read_text())['root']
        thread = win32api.GetCurrentThreadId()
        other = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
        attached = ctypes.windll.user32.AttachThreadInput(thread, other, True)
        try:
            win32gui.SetForegroundWindow(handle)
        finally:
            if attached:
                ctypes.windll.user32.AttachThreadInput(thread, other, False)
        desktop = SimpleNamespace(user=SimpleNamespace(GetForegroundWindow=lambda:handle,
            GetWindowThreadProcessId=ctypes.windll.user32.GetWindowThreadProcessId,
            IsWindow=win32gui.IsWindow, IsWindowVisible=win32gui.IsWindowVisible), target=handle)
        import psutil
        actual_executable = psutil.Process(win32process.GetWindowThreadProcessId(handle)[1]).exe()
        actions = Actions({'files_root':'managed','_ui_verification':True,'apps':{
            'LearningFixture': {'executable': actual_executable, 'documentation_file': str(root/'help.md')}},
            'memory':{'enabled':False}, 'knowledge_acquisition':{'enabled':True,'online':False},
            'brain':{'enabled':True,'planner':'authored-fixture','decision':'authored-scope-check','fast_grounding':True,'screen_aware':False}}, root, lambda *_:None, desktop=desktop)
        actions.task_state.read_only = False
        actions.allowed_tools = {'application_inspect','read_file','select'}
        actions._task_folder = lambda name,cancelled:root if Path(name).resolve()==root.resolve() else None
        ui = UIControls(desktop, external_handle=lambda:handle)
        actions._ui = lambda:ui
        class Client:
            def close(self): pass
            def request(self, operation, cancelled, **data):
                if operation == 'plan':
                    assert data['learning_context']['capabilities'][0]['controls']
                    return {'question':'','steps':[{'action':'select','value':'Create diagram','expected':'Diagram created'}]}
                if operation == 'verify':
                    okay = (root/'diagram.svg').is_file() and '<circle ' in (root/'diagram.svg').read_text()
                    return {'verified':okay,'reason':'Independent SVG and fixture event readback'}
                if operation == 'decide':
                    return {'approved': data['step']['value']=='Create diagram', 'choice':'c0', 'reason':'Unique fresh owned-fixture control'}
                raise ValueError('Unexpected operation: '+operation)
        actions.brain.client = Client()
        goal = 'Create a diagram here' if implicit else 'Use LearningFixture to create a diagram'
        reply = actions.execute(Command('task',goal))
        capability = actions.screen.knowledge.capabilities('learningfixture','diagram')[0]
        result.update(passed=(root/'diagram.svg').is_file() and capability['status']=='verified',
            seconds=time.monotonic()-started, reply=reply, capability=capability,
            svg_readback='<circle ' in (root/'diagram.svg').read_text(), state=actions.task_state.snapshot()['status'],
            implicit_current_app=implicit)
    except Exception as exc:
        result.update(passed=False,error_type=type(exc).__name__,error=str(exc))
    finally:
        if actions: actions.close()
        if ui: ui.close()
        if handle and win32gui.IsWindow(handle): win32gui.PostMessage(handle,win32con.WM_CLOSE,0,0)
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
        process.stderr.close()
        if original and win32gui.IsWindow(original):
            try: win32gui.SetForegroundWindow(original)
            except Exception: pass
    name = 'learning-native-current.json' if implicit else 'learning-native.json'
    (BASE/'artifacts/reports'/name).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--implicit-current-app', action='store_true')
    main(parser.parse_args().implicit_current_app)
