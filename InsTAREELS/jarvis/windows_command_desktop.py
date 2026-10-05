"""Fresh-window adapters for the pinned Python recipes, inside the UI worker."""
import os
import re
import time
import json


def matches_app(executable,title,app):
    name=executable.replace('\\','/').rsplit('/',1)[-1].casefold().removesuffix('.exe')
    if app=='youtube':
        from .media_ui import platform_of
        return platform_of({'context':json.dumps([executable]),'title':title})=='youtube'
    if app=='browser':return name in {'chrome','msedge','firefox','brave','opera'}
    return not app or name==app


def perform(request, window, signature):
    import pyautogui as pg
    import win32gui
    import win32process
    import psutil
    from pywinauto import Desktop
    from .windows_commands import prepare, interpret
    prepared=prepare(request['ids'],request['bindings'])
    hwnd=request['handle']
    pid=win32process.GetWindowThreadProcessId(hwnd)[1]
    if request.get('signature')!=signature or request.get('target_pid')!=pid:
        raise ValueError('Destination identity or controls changed before recipe dispatch.')
    executable=psutil.Process(pid).exe()
    foreground=win32gui.GetForegroundWindow()
    if foreground!=hwnd and win32process.GetWindowThreadProcessId(foreground)[1]!=request['owner_pid']:
        raise ValueError('Another application took focus; no input issued.')
    window.set_focus()
    def guard(row):
        if not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1]!=pid or win32gui.GetForegroundWindow()!=hwnd:
            raise ValueError('Destination closed or focus changed; no further input issued.')
        app=row.get('app')
        if not matches_app(executable,window.window_text(),app):
            raise ValueError('This command requires '+app+'; current app is '+executable+'.')
        if app in {'youtube','blender','unrealeditor'}:
            focused=[c for c in window.descendants(control_type='Edit') if c.has_keyboard_focus()]
            if focused:raise ValueError('A text editor has focus; focus the player/viewport first.')
    held_keys=set(); held_buttons=set()
    class BoundMouse:
        def __getattr__(self,name):
            target=getattr(pg,name)
            def call(*args,**kwargs):
                guard(prepared[current[0]][0])
                rect=window.rectangle()
                if name in {'click','rightClick','doubleClick','middleClick','tripleClick','moveTo','dragTo','pixel','pixelMatchesColor'} and args:
                    point=args[0] if len(args)==1 else args[:2]
                    if len(point)!=2 or any(type(n) is not int for n in point) or not (rect.left<=point[0]<rect.right and rect.top<=point[1]<rect.bottom):
                        raise ValueError('Coordinates must be inside the bound current window.')
                if name in {'moveRel','dragRel'}:
                    x,y=pg.position(); dx,dy=args[:2]
                    if not(rect.left<=x+dx<rect.right and rect.top<=y+dy<rect.bottom):
                        raise ValueError('Relative pointer target leaves the bound window.')
                if name in {'click','rightClick','doubleClick','middleClick','tripleClick','mouseDown','dragRel'} and not args:
                    x,y=pg.position()
                    if not(rect.left<=x<rect.right and rect.top<=y<rect.bottom):
                        raise ValueError('Pointer is outside the bound window.')
                if name=='screenshot':
                    # Explicit output path; never store screenshots in the repository by default.
                    if kwargs.get('region'):
                        x,y,w,h=kwargs['region']
                        if min(w,h)<=0 or not(rect.left<=x and rect.top<=y and x+w<=rect.right and y+h<=rect.bottom):
                            raise ValueError('Screenshot region must stay within the destination window.')
                if name in {'locateOnScreen'}:
                    matches=list(pg.locateAllOnScreen(*args,**kwargs))
                    if len(matches)!=1:raise ValueError('Reference image must have exactly one visible match.')
                    return matches[0]
                if name=='keyDown':held_keys.add(args[0])
                if name=='mouseDown':held_buttons.add(kwargs.get('button','left'))
                if name=='keyUp':held_keys.discard(args[0])
                if name=='mouseUp':held_buttons.discard(kwargs.get('button','left'))
                return target(*args,**kwargs)
            return call
    class BoundWindow:
        def __init__(self,wrapper):self.wrapper=wrapper
        def __getattr__(self,name):
            if getattr(self.wrapper.element_info,'is_password',False):raise ValueError('Password controls are excluded.')
            if name=='child_window':
                def child(**kwargs):
                    # Resolve a unique fresh child, never choose the first Edit or Save by default.
                    choices=[c for c in window.descendants(control_type=kwargs.get('control_type')) if c.is_visible() and c.is_enabled() and (not kwargs.get('title') or c.window_text()==kwargs['title'])]
                    if len(choices)!=1:raise ValueError('The requested accessible child is not unique.')
                    return BoundWindow(choices[0])
                return child
            if name=='print_control_identifiers':
                return lambda: '\n'.join(c.window_text()[:100] for c in window.descendants()[:100])
            if name=='wait':
                def wait(state,timeout=10):
                    if state!='visible':raise ValueError('Only visible-window waits are supported.')
                    end=time.monotonic()+min(10,timeout)
                    while not self.wrapper.is_visible():
                        if time.monotonic()>=end:raise ValueError('Window did not become visible.')
                        time.sleep(.05)
                    return 'Window visible.'
                return wait
            return getattr(self.wrapper,name)
    class BoundDesktop:
        def __init__(self,**kwargs):pass
        def windows(self):return [w.window_text()[:200] for w in Desktop(backend='uia').windows()[:100]]
        def window(self,**kwargs):
            pattern=kwargs.get('title_re')
            if pattern and (len(pattern)>200 or not re.fullmatch(pattern,window.window_text())):
                raise ValueError('The bound window does not match the requested title.')
            return BoundWindow(window)
    # Every recipe is executed once; exceptions propagate with no fallback/replay.
    current=[0]; env={'pg':BoundMouse(),'Desktop':BoundDesktop,'w':BoundWindow(window),'print':lambda v:v}
    messages=[]
    try:
        for index,item in enumerate(prepared):
            current[0]=index
            result=interpret([item],env,guard)
            messages.append(result['message'])
    finally:
        # Held modifiers/buttons cannot survive a failed snippet or Stop.
        for key in held_keys:pg.keyUp(key)
        for button in held_buttons:pg.mouseUp(button=button)
    return {'message':'\n'.join(messages)[:12000],'verified':all(r['readonly'] for r,_ in prepared)}
