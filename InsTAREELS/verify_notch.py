"""Exercise the real UI off-screen and render labelled fixture layouts, without capture."""
import json
import os
from pathlib import Path
import threading
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageChops
from main import App
from jarvis.island import font, render_island, Morph
from jarvis.ui_preview import export_preview


def keyed(image, background='#181c23'):
    result = Image.new('RGB', image.size, background)
    masks = [channel.point([0 if value==key else 255 for value in range(256)])
             for channel,key in zip(image.convert('RGB').split(),(255,0,255))]
    mask = ImageChops.lighter(masks[0],ImageChops.lighter(masks[1],masks[2]))
    result.paste(image,(0,0),mask)
    return result


def native_fixture(root, path):
    """Print only the verifier's own window; never sample the desktop DC."""
    import ctypes
    from ctypes import wintypes
    import win32gui
    import win32ui
    hwnd = win32gui.GetAncestor(root.winfo_id(),2)
    width,height = root.winfo_width(),root.winfo_height()
    handle = win32gui.GetWindowDC(hwnd)
    dc = win32ui.CreateDCFromHandle(handle)
    target = dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(dc,width,height)
    original = target.SelectObject(bitmap)
    try:
        user = ctypes.WinDLL('user32')
        user.PrintWindow.argtypes = (wintypes.HWND,wintypes.HDC,wintypes.UINT)
        user.PrintWindow.restype = wintypes.BOOL
        if not user.PrintWindow(hwnd,target.GetSafeHdc(),2):
            raise RuntimeError('Own-window fixture rendering failed')
        Image.frombuffer('RGB',(width,height),bitmap.GetBitmapBits(True),'raw','BGRX',0,1).save(path)
    finally:
        target.SelectObject(original)
        win32gui.DeleteObject(bitmap.GetHandle())
        target.DeleteDC()
        dc.DeleteDC()
        win32gui.ReleaseDC(hwnd,handle)


def main():
    previous = os.environ.get('JARVIS_UI_VERIFY')
    os.environ['JARVIS_UI_VERIFY'] = '1'
    output = Path('artifacts')
    root = tk.Tk(); root.withdraw()
    app = None
    results = {'date':'2026-10-04', 'kind':'off-screen UI regression and rendered fixtures',
               'live_voice_or_external_actions':False, 'views':[]}
    samples = []
    try:
        app = App(root)
        for callback in root.tk.call('after','info'):
            root.after_cancel(callback)
        app.config.setdefault('ui', {})['reduced_motion'] = True
        root.geometry('402x40+20000+20000'); root.deiconify()

        def scene(name, view='Overview', status='STANDBY', features=False):
            app.desk.show(view)
            app.island.features_open = features
            app.island.expand(True)
            for _ in range(3):
                app.island.tick(status)
                root.update()
            if app.listener is not None:
                raise AssertionError('Preview started microphone capture')
            if app.panel.winfo_toplevel() != root:
                raise AssertionError('Feature escaped the island')
            for widget in (app.preview, app.command_entry if view=='Console' else app.preview):
                if widget.winfo_ismapped() and widget.winfo_rooty()+widget.winfo_height() > app.panel.winfo_rooty()+app.panel.winfo_height():
                    raise AssertionError('Primary input clipped in '+view)
            path = output/('jarvis-notch-'+name+'.png')
            export_preview(app,path)
            raw = Image.open(path).convert('RGB')
            keyed(raw).save(path)
            samples.append((name, keyed(raw)))
            results['views'].append({'view':name, 'size':list(raw.size), 'single_window':True})

        scene('compose')
        app.preview.insert(0,'Glass input is readable')
        root.update()
        native_fixture(root,output/'notch-native-input-fixture.png')
        results['native_input_fixture'] = 'Own off-screen window only; authored text'
        app.preview.delete(0,'end')
        app.question.set('Write a Python function that adds two numbers.')
        app.desk.notify('answer','```python\ndef add(a, b):\n    return a + b\n```\n\nThis function returns the sum of its two arguments.\n\n' +
            'Example: add(12, 8) returns 20.\n'*14)
        scene('answer', status='SPEAKING')
        app.desk.notify('task_status',{'phase':'Writing calculator.py','target':'D:/Example/calculator.py',
            'active':True,'preview':'def add(a, b):\n    return a + b','characters':42,'outcome':'Draft in progress'})
        scene('task', status='WORKING')
        app.question.set('')
        scene('games','Games','WORKING',True)
        app.desk.draw_game()
        scene('games','Games','WORKING',True)
        samples.pop(-2); results['views'].pop(-2)
        scene('settings','Settings',features=True)
        app.show_command_prompt()
        scene('console','Console',features=True)
        ready, answer = threading.Event(), {}
        app.desk.add_approval(('delete','D:/Example/review-me.txt',answer,ready,lambda:False))
        scene('approval','Approval','ATTENTION',True)
        if ready.is_set():
            raise AssertionError('Preview approved an action')
        app.desk.cancel_approvals()
        if not ready.is_set() or answer['approved']:
            raise AssertionError('Close did not safely deny the fixture approval')
        if any(child.winfo_class()=='Toplevel' for child in root.winfo_children()):
            raise AssertionError('Extra feature window found')
        app.hide_panel()
        app.island.tick('STANDBY')
        if app.panel.state()!='withdrawn':
            raise AssertionError('Collapse left feature content visible')
        results['collapse_safety'] = True

        board = Image.new('RGB',(1500,2070),'#181c23')
        draw = ImageDraw.Draw(board)
        draw.text((48,30),'JARVIS / ONE EXPANDING NOTCH',font=font(28,True),fill='#eeeeee')
        draw.text((48,77),'Rendered native widget layouts · sample content · 2026-10-04 · no desktop capture',font=font(16),fill='#a4aab5')
        for index,(name,picture) in enumerate(samples):
            x,y = 48+(index%2)*730, 143+(index//2)*470
            draw.text((x,y),name.capitalize(),font=font(18,True),fill='#becbe3')
            picture.thumbnail((680,425),Image.Resampling.LANCZOS)
            board.paste(picture,(x,y+32))
        board.save(output/'jarvis-notch-preview.png')

        frames, motion = [], Morph()
        for index in range(100):
            now = index/30
            target = (402,40) if now < .5 or now > 2.6 else (614,144) if now < 1.3 else (614,460)
            motion.set_target(target,now)
            width,height = (round(n) for n in motion.sample(now))
            frame = Image.new('RGB',(740,560),'#181c23')
            draw = ImageDraw.Draw(frame)
            draw.text((24,20),'Rendered geometry animation · sample states',font=font(14),fill='#a4aab5')
            frame.paste(keyed(render_island(width,height,'WORKING' if now>1.3 and now<2.6 else 'STANDBY',
                now,expanded=height>100)),((740-width)//2,64))
            frames.append(frame)
        frames[0].save(output/'jarvis-notch-motion.gif',save_all=True,append_images=frames[1:],duration=33,loop=0,disposal=2)
        results['passed'] = True
        (output/'notch-ui-check.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(results,indent=2))
    finally:
        if app:
            app.close()
        else:
            root.destroy()
        if previous is None:
            os.environ.pop('JARVIS_UI_VERIFY',None)
        else:
            os.environ['JARVIS_UI_VERIFY'] = previous


if __name__ == '__main__':
    main()
