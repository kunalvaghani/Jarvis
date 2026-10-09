"""Isolated visual checks. --desktop uses only an owned disposable window.

The Save As fixture uses a deterministic visual oracle, not an LLM. --model
checks real local vision against rendered fixtures without dispatching input.
Neither check establishes reliability in third-party desktop applications.
"""
from jarvis.paths import APP_ROOT, artifact_path
import argparse
import base64
import ctypes
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

BASE = Path(__file__).resolve().parents[2]


def fixture(folder):
    """Actual disposable Windows UI: titlebar, filename field and Save button."""
    import tkinter as tk
    import win32gui
    from jarvis.skill_memory import atomic
    folder = Path(folder)
    root = tk.Tk()
    root.title('Jarvis owned Save As verification')
    root.geometry('780x300+80+120')
    root.resizable(False, False)
    root.lift()
    root.configure(bg='white')
    tk.Label(root, text='Save As — disposable verification document', font=('Segoe UI',18), bg='white').place(x=25,y=20)
    tk.Label(root, text='File name', font=('Segoe UI',14), bg='white').place(x=25,y=105)
    field = tk.Entry(root, font=('Segoe UI',13))
    field.place(x=140,y=108,width=590,height=35)
    status = tk.Label(root, text='Document is not saved', font=('Segoe UI',14), bg='white')
    status.place(x=25,y=225)
    saved = False

    def state():
        root.update_idletasks()
        handle = win32gui.GetAncestor(root.winfo_id(), 2)
        rect = win32gui.GetWindowRect(handle)
        def center(widget):
            return [(widget.winfo_rootx()+widget.winfo_width()/2-rect[0])/(rect[2]-rect[0]),
                    (widget.winfo_rooty()+widget.winfo_height()/2-rect[1])/(rect[3]-rect[1])]
        atomic(folder/'state.json', json.dumps({'handle':handle,'pid':os.getpid(), 'field':center(field),
            'button':center(button), 'text':field.get(), 'focused':root.focus_get() is field, 'saved':saved}))
        if (folder/'stop').exists():
            root.destroy()
        else:
            root.after(50,state)

    def save():
        nonlocal saved
        path = Path(field.get())
        if path != folder/'notes.txt':
            status.configure(text='Wrong destination — no write')
            return
        path.write_text('Jarvis isolated Save-dialog verification\n', encoding='utf-8')
        saved = True
        status.configure(text='Saved notes.txt — disk result available')
        field.place_forget()
        button.place_forget()

    button = tk.Button(root, text='Save', font=('Segoe UI',16), command=save)
    button.place(x=605,y=170,width=125,height=45)
    root.after(100,state)
    root.after(60000,root.destroy)  # Fixture cannot outlive the bounded check.
    root.mainloop()


def desktop_check():
    import win32gui
    from jarvis.brain import Brain
    from jarvis.visual_fallback import VisualFallback
    with tempfile.TemporaryDirectory(prefix='jarvis-visual-') as temporary:
        folder = Path(temporary)
        child = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--fixture',str(folder)],
            cwd=BASE, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            deadline = time.monotonic()+10
            while not (folder/'state.json').is_file():
                if child.poll() is not None or time.monotonic()>deadline:
                    raise ValueError('Owned verification window did not start.')
                time.sleep(.1)
            def current():
                return json.loads((folder/'state.json').read_text(encoding='utf-8'))
            handle = current()['handle']
            # The disposable fixture is the only window this script focuses or operates.
            if win32gui.GetForegroundWindow() != handle:
                try:
                    win32gui.SetForegroundWindow(handle)
                except Exception as exc:
                    raise ValueError('Windows refused fixture focus; selected=' + str(handle) +
                        ', foreground=' + str(win32gui.GetForegroundWindow()) + ', visible=' +
                        str(bool(win32gui.IsWindowVisible(handle))) + ': ' + str(exc)) from exc
            time.sleep(.2)
            checkpoints, calls = [], []
            snapshot = {'controls':[], 'visual_only':True, 'is_dialog':False}
            actions = SimpleNamespace(config={}, base=folder, report=lambda *a:None,
                _task_folder=lambda value,cancel:folder,
                _approve=lambda *a:(_ for _ in ()).throw(ValueError('Unexpected overwrite')))
            brain = SimpleNamespace(options={'visual_fallback':{'enabled':True}}, actions=actions,
                checkpoint=lambda stage,**data:checkpoints.append({'stage':stage,**data}),
                observe=lambda cancel:(handle,snapshot), visual_context=Brain.visual_context)
            def request(operation, cancel, **data):
                calls.append(operation)
                s = current()
                if operation == 'visual_dialog':
                    return {'kind':'none' if s['saved'] else 'save_as','confidence':1.0,
                            'filename_label':'File name','confirm_label':'Save'}
                if operation == 'visual_ground':
                    xy = s['field' if data['step']['action']=='fill_text' else 'button']
                    return {'action':f'click(start_box="({xy[0]*1000},{xy[1]*1000})")',
                        'target':data['step']['value'],'role':'Edit' if data['step']['action']=='fill_text' else 'Button',
                        'confidence':1.0,'is_dialog':True,'password':False}
                if operation == 'visual_field':
                    return {'verified':s['focused'] if data.get('focused_only') else s['text']==data['step']['content'],
                            'observed_text':s['text']}
                if operation == 'visual':
                    return {'step_verified':s['saved'],'goal_done':False,'summary':'Owned fixture reports saved'}
                raise ValueError('Unexpected model operation '+operation)
            brain.client = SimpleNamespace(base=BASE,request=request)
            brain.visual_screen = lambda target,snap,cancel,strict=False:Brain.visual_screen(brain,target,snap,cancel,strict)
            brain.screen = Brain.screen
            fallback = VisualFallback(brain)
            start = time.monotonic()
            result = fallback.save_file('Save document as notes.txt in '+str(folder),
                {'action':'save_file','value':'notes.txt','folder':str(folder),'content':''},lambda:False)
            assert (folder/'notes.txt').read_text(encoding='utf-8') == 'Jarvis isolated Save-dialog verification\n'
            return {'passed':True,'seconds':round(time.monotonic()-start,3),
                'scope':'Actual Windows capture, guarded click, Unicode field replacement and Save input in an owned Tk fixture; deterministic visual oracle, no LLM',
                'result':result,'checkpoints':checkpoints,'oracle_operations':calls,
                'bytes':fallback.last_saved['size'],'sha256':fallback.last_saved['sha256']}
        finally:
            (folder/'stop').touch()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            # No actions are sent to the previously foreground application.


def model_check():
    from PIL import Image, ImageDraw, ImageFont
    from jarvis.brain import BrainClient
    from jarvis.visual_fallback import click_point
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    options = {**config['brain'], 'harness':{'enabled':False}, 'hermes':{'enabled':False}}
    client = BrainClient(BASE,options)
    client.timeout_seconds = 240
    image = Image.new('RGB',(900,500),'#f5f5f5')
    draw = ImageDraw.Draw(image)
    fontpath = Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'segoeui.ttf'
    font = ImageFont.truetype(str(fontpath),24)
    draw.text((40,30),'Save As',font=font,fill='black')
    draw.text((40,125),'File name:',font=font,fill='black')
    draw.rectangle((200,115,810,175),fill='white',outline='#777777',width=2)
    draw.text((215,130),'notes.txt',font=font,fill='black')
    draw.rectangle((640,360,810,430),fill='#1269ca')
    draw.text((695,378),'Save',font=font,fill='white')
    artifacts = BASE/'artifacts'
    artifacts.mkdir(exist_ok=True)
    image.save(artifacts/'visual-save-fixture.png')
    data = io.BytesIO()
    image.save(data,format='JPEG',quality=78)
    screen = {'title':'Synthetic Save As fixture','controls':[],'ocr':'',
              'image':base64.b64encode(data.getvalue()).decode('ascii')}
    rows = []
    try:
        for operation,step in [('visual_ground',{'action':'handle_dialog','value':'Save','expected':'Save button activated'}),
                               ('visual_field',{'action':'fill_text','value':'File name','content':'notes.txt','expected':'Exact filename visible'}),
                               ('visual_dialog',{}),
                               ('visual_field',{'action':'fill_text','value':'File name','content':'wrong.txt','expected':'Exact filename visible'})]:
            start = time.monotonic()
            if operation == 'visual_dialog':
                result = client.request(operation,lambda:False,screen=screen)
            else:
                result = client.request(operation,lambda:False,goal='Save document as notes.txt',step=step,screen=screen)
            if operation == 'visual_ground':
                try:
                    xy = click_point(result['action'])
                    passed = (result.get('confidence',0)>=.95 and result.get('target')=='Save' and
                              result.get('is_dialog') is True and result.get('role')=='Button' and
                              640/900<xy[0]<810/900 and 360/500<xy[1]<430/500)
                except (ValueError,SyntaxError,KeyError) as exc:
                    result['validation_error'] = str(exc)
                    passed = False
            elif operation == 'visual_dialog':
                passed = (result.get('kind')=='save_as' and result.get('confidence',0)>=.95
                          and result.get('confirm_label')=='Save' and result.get('filename_label').rstrip(':').casefold()=='file name'
                          and not result.get('overwrite_name'))
            else:
                passed = (result.get('observed_text')=='notes.txt' and
                          (step['content']!='notes.txt' or result.get('verified') is True))
            rows.append({'operation':operation,'requested_content':step.get('content',''),
                         'seconds':round(time.monotonic()-start,3), 'passed':passed,'response':result})
        return {'passed':all(row['passed'] for row in rows),'model':options['screen_model'],
            'scope':'Real local vision on a rendered synthetic fixture; coordinates parsed but never dispatched; no live third-party app task', 'turns':rows}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture')
    parser.add_argument('--desktop',action='store_true')
    parser.add_argument('--model',action='store_true')
    args = parser.parse_args()
    if args.fixture:
        fixture(args.fixture)
        return 0
    from tests import test_visual_fallback
    results = {'at':datetime.now(timezone.utc).isoformat(), 'scope':'Isolated fixtures only; configured vault is not written',
               'upstream':'UI-TARS parse_action at 582f3a7ea5d285ee8ed9e2e84048d1ab01453c49'}
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_visual_fallback)
    report = unittest.TextTestRunner(stream=sys.stderr).run(suite)
    results['regression'] = {'passed':report.wasSuccessful(),'tests':report.testsRun}
    for name,enabled,check in [('desktop',args.desktop,desktop_check),('local_model',args.model,model_check)]:
        if enabled:
            print('Starting '+name+' check',flush=True)
            try: results[name] = check()
            except Exception as exc: results[name] = {'passed':False,'error':str(exc)}
        else:
            results[name] = {'run':False}
    results['passed'] = all(value.get('passed',True) for value in results.values() if isinstance(value,dict))
    output = artifact_path(BASE, 'visual-fallback-check.json' if args.desktop or args.model else 'visual-fallback-regression-check.json')
    if output.is_file():
        previous = json.loads(output.read_text(encoding='utf-8'))
        if not args.desktop and previous.get('desktop',{}).get('passed') is False:
            results['desktop'] = {'run':False,'last_attempt_at':previous['at'],'last_attempt':previous['desktop']}
        if not previous.get('passed',False):
            initial = output.parent/'visual-fallback-check-initial-failure.json'
            if not initial.is_file():
                initial.write_text(json.dumps(previous,indent=2)+'\n',encoding='utf-8')
            with (output.parent/'visual-fallback-check-failures.jsonl').open('a',encoding='utf-8') as history:
                history.write(json.dumps(previous)+'\n')
    output.write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,indent=2))
    return 0 if results['passed'] else 1


if __name__ == '__main__':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError,OSError):
        pass
    raise SystemExit(main())
