"""Actual independent-cursor checks: owned fixture and fresh public browser profile.

No account writes, camera capture, credentials, physical input or user browser
profiles. Native user-app tests require individually observed safe controls.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

BASE=Path(__file__).resolve().parent


def app_controls(app):
    import psutil
    import win32gui
    import win32process
    from pywinauto import Desktop
    from jarvis.ui_worker import perform
    executable={'camera':'windowscamera.exe','spotify':'spotify.exe'}[app]
    candidates=set()
    for window in Desktop(backend='uia').windows():
        try:
            handles=[window.handle]
            win32gui.EnumChildWindows(window.handle,lambda h,_:handles.append(h),None)
            owned=False
            for handle in handles:
                try: owned=owned or psutil.Process(win32process.GetWindowThreadProcessId(handle)[1]).name().casefold()==executable
                except psutil.Error:pass
            if window.is_visible() and owned:
                candidates.add(win32gui.GetAncestor(window.handle,2))
        except (psutil.Error,OSError):pass
    assert len(candidates)==1,'Expected exactly one visible '+app+' window'
    basic={'handle':next(iter(candidates)),'owner_pid':os.getpid()}
    return basic,perform({'operation':'list',**basic})


def native_app(app):
    import win32gui
    from jarvis.ui_worker import perform
    basic,snapshot=app_controls(app)
    names={'camera':['Switch to video mode','Switch to photo mode'],
           'spotify':['Search','Home']}[app]
    matches=[c for c in snapshot['controls'] if c['name'] in names and c['role']=='Button']
    if app=='camera':assert len(matches)==1,'Camera mode button is not unique'
    else:
        matches=[c for c in matches if c['name']=='Search']
        assert len(matches)==1,'Spotify Search button is not currently accessible'
    control=matches[0];before=win32gui.GetCursorPos()
    receipt=perform({'operation':'activate','control':control,'verb':'click',**basic})
    deadline=time.monotonic()+3
    after=snapshot
    def changed(value):
        if app=='camera':return any(c['name'] in names and c['name']!=control['name'] for c in value['controls'])
        return any(c['role'] in {'Edit','ComboBox'} and c.get('focused') and
                   c['name'].casefold() in {'search','what do you want to play?','search for songs, artists, or podcasts'}
                   for c in value['controls'])
    while time.monotonic()<deadline:
        after=perform({'operation':'list',**basic})
        if changed(after):break
        time.sleep(.1)
    result={'date':datetime.now(timezone.utc).isoformat(),'app':app,'control':control['name'],
        'dispatched_once':receipt['dispatched'],'system_pointer_unchanged':win32gui.GetCursorPos()==before,
        'postcondition_changed':changed(after),'provider':receipt['provider'],
        'scope':'Navigation/mode controls only. No camera photo/video recording, account write or privacy change.'}
    if app=='camera' and result['postcondition_changed']:
        # Distinct restoration, only after observing that the mode actually changed.
        restore=next(c for c in after['controls'] if c['name'] in names and c['name']!=control['name'])
        perform({'operation':'activate','control':restore,'verb':'click',**basic})
        restored=perform({'operation':'list',**basic})
        result['original_mode_restored']=any(c['name']==control['name'] for c in restored['controls'])
        result['restore_pointer_unchanged']=win32gui.GetCursorPos()==before
    result['passed']=result['system_pointer_unchanged'] and result['postcondition_changed'] and result.get('original_mode_restored',True) and result.get('restore_pointer_unchanged',True)
    destination=BASE/('artifacts/independent-cursor-'+app+'-check.json')
    destination.write_text(json.dumps(result,indent=2)+'\n')
    return result


def native():
    import win32gui
    from pywinauto import Desktop
    from jarvis.independent_cursor import CursorCue, activate_point
    from jarvis.ui_worker import perform
    folder=BASE/'.jarvis-runtime/cursor-fixtures'/uuid4().hex;folder.mkdir(parents=True)
    state=folder/'state.json'
    process=subprocess.Popen([sys.executable,str(BASE/'tests/execution_native_fixture.py'),str(state)],
        cwd=BASE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    root=0; result={}
    try:
        deadline=time.monotonic()+10
        while not state.exists() and time.monotonic()<deadline and process.poll() is None:time.sleep(.05)
        assert state.exists(),'The owned native fixture did not start'
        root=json.loads(state.read_text())['handles']['root']
        Desktop(backend='uia').window(handle=root).wrapper_object().set_focus()
        assert win32gui.GetForegroundWindow()==root,'The fixture did not take focus'
        basic={'handle':root,'owner_pid':os.getpid()}
        target=next(c for c in perform({'operation':'list',**basic})['controls'] if c['role']=='Button' and c['name']=='Apply')
        before=win32gui.GetCursorPos()
        # Check the actual OS styles, hit-testing and expiry independently of
        # dispatch. No action is issued inside this first cue.
        with CursorCue(target['rect'],root) as cue:
            import win32con
            style=win32gui.GetWindowLong(cue.handle,win32con.GWL_EXSTYLE)
            result['cue_noactivate']=bool(style & win32con.WS_EX_NOACTIVATE)
            result['cue_clickthrough']=bool(style & win32con.WS_EX_TRANSPARENT)
            result['cue_visible']=bool(win32gui.IsWindowVisible(cue.handle))
            result['cue_kept_foreground']=win32gui.GetForegroundWindow()==root
            result['cue_did_not_move_mouse']=win32gui.GetCursorPos()==before
        result['cue_disposed']=cue.finished.is_set() and cue.handle is None and not cue.thread.is_alive()
        before_clicks=json.loads(state.read_text())['clicks']
        receipt=perform({'operation':'activate','control':target,'verb':'click',**basic})
        deadline=time.monotonic()+1
        while json.loads(state.read_text())['clicks']==before_clicks and time.monotonic()<deadline:time.sleep(.02)
        result['native_activated_once']=json.loads(state.read_text())['clicks']==before_clicks+1
        result['native_pointer_unchanged']=win32gui.GetCursorPos()==before
        result['provider']=receipt['provider']
        target=next(c for c in perform({'operation':'list',**basic})['controls'] if c['role']=='Button')
        rect=target['rect'];x,y=(rect[0]+rect[2])//2,(rect[1]+rect[3])//2
        before_clicks=json.loads(state.read_text())['clicks']
        activate_point(x,y,root)
        deadline=time.monotonic()+1
        while json.loads(state.read_text())['clicks']==before_clicks and time.monotonic()<deadline:time.sleep(.02)
        result['grounded_activated_once']=json.loads(state.read_text())['clicks']==before_clicks+1
        result['grounded_pointer_unchanged']=win32gui.GetCursorPos()==before
        # Model/COM blockage cannot retain the cue: expiry runs on its own thread.
        cue=CursorCue(target['rect'],root);cue.__enter__()
        result['blocked_callback_cue_expired']=cue.finished.wait(1.3) and cue.handle is None
        cue.close()
        result['passed']=all(v is True for k,v in result.items() if k!='provider')
    finally:
        if root and win32gui.IsWindow(root):win32gui.PostMessage(root,0x0010,0,0)
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=3)
        if process.stderr:process.stderr.close()
    return result


def web():
    import win32gui
    from playwright.sync_api import sync_playwright
    from jarvis.browser_worker import Session
    from jarvis.browser_cursor import click
    folder=BASE/'.jarvis-runtime/cursor-fixtures'/uuid4().hex;folder.mkdir(parents=True)
    result=[]
    with sync_playwright() as driver:
        context=driver.chromium.launch_persistent_context(str(folder/'profile'),channel='chrome',headless=False,
            viewport={'width':1280,'height':800},args=['--no-first-run','--force-renderer-accessibility'])
        context.set_default_timeout(5000);context.set_default_navigation_timeout(20000)
        page=context.pages[0];session=Session();session.context=context;session.page=page
        try:
            # A same-page independent DOM readback proves one activation, cleanup
            # and absence of interception, before public-site navigation checks.
            page.set_content('<style>body{background:#101820;color:#e6ffff;font:24px sans-serif;padding:100px}button{font:24px sans-serif;margin:70px;padding:25px 80px;background:#273845;color:white;border:2px solid #00d2e1;border-radius:14px}</style><h1>Jarvis cursor verification fixture</h1><p>The cyan J cue is separate from the system pointer.</p><button aria-label="Count" onclick="this.textContent=String(Number(this.textContent)+1)">0</button>')
            from jarvis.browser_cursor import SHOW,REMOVE
            box=page.get_by_role('button',name='Count').bounding_box();token=uuid4().hex
            page.evaluate(SHOW,{'token':token,'box':box});page.wait_for_timeout(200)
            page.screenshot(path=str(BASE/'artifacts/independent-cursor-browser-fixture.png'))
            page.evaluate(REMOVE,token)
            before=win32gui.GetCursorPos()
            click(page.get_by_role('button',name='Count',exact=True),page)
            result.append({'site':'owned DOM fixture','activated_once':page.get_by_role('button',name='Count').inner_text()=='1',
                'cursor_removed':page.locator('[data-jarvis-cursor]').count()==0,
                'system_pointer_unchanged':win32gui.GetCursorPos()==before})
            for site,url,names in [('YouTube','https://www.youtube.com/',['Guide']),
                                   ('GitHub','https://github.com/python/cpython',['Platform','Go to file']),
                                   ('Spotify web','https://open.spotify.com/',['Browse'])]:
                row={'site':site,'passed':False}
                try:
                    page.goto(url,wait_until='domcontentloaded');page.wait_for_timeout(1800)
                    snapshot=session.inspect()
                    row['available_buttons']=[c['name'] for c in snapshot['controls'] if c['role']=='Button']
                    chosen=None
                    for name in names:
                        candidate=page.get_by_role('button',name=name,exact=True)
                        links=page.get_by_role('link',name=name,exact=True)
                        if candidate.count()+links.count()==1 and candidate.is_visible():chosen=name;break
                    if chosen is None:
                        row['setup_or_target_needed']=True
                        result.append(row);continue
                    # The independently read DOM state is retained only as hashes,
                    # never site/account contents. A changed scene is limited
                    # evidence; selected target/postcondition needs review.
                    before_dom=page.content();before=win32gui.GetCursorPos()
                    if site=='YouTube':before_state=page.locator('tp-yt-app-drawer#guide').evaluate('e=>e.opened')
                    elif site=='GitHub':before_state=page.get_by_role('button',name=chosen,exact=True).get_attribute('aria-expanded')
                    else:before_state={'path':__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(page.url).path,
                        'expanded':page.get_by_role('button',name=chosen,exact=True).get_attribute('aria-expanded')}
                    answer=session.perform({'operation':'click','value':chosen,'url':page.url})
                    page.wait_for_timeout(400)
                    row.update(control=chosen,dispatched_once=True,system_pointer_unchanged=win32gui.GetCursorPos()==before,
                        cursor_removed=page.locator('[data-jarvis-cursor]').count()==0,
                        dom_changed=before_dom!=page.content(),url_path=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(page.url).path,
                        downstream_verified=answer['verified'])
                    if site=='YouTube':after_state=page.locator('tp-yt-app-drawer#guide').evaluate('e=>e.opened')
                    elif site=='GitHub':after_state=page.get_by_role('button',name=chosen,exact=True).get_attribute('aria-expanded')
                    else:after_state={'path':__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(page.url).path,
                        'expanded':page.get_by_role('button',name=chosen,exact=True).get_attribute('aria-expanded')}
                    row['postcondition']={'before':before_state,'after':after_state,'changed':before_state!=after_state}
                    row['passed']=row['system_pointer_unchanged'] and row['cursor_removed'] and row['postcondition']['changed']
                except Exception as exc:
                    row['error_type']=type(exc).__name__
                    row['error']=str(exc)[:1200]
                result.append(row)
        finally:context.close()
    return result


def main():
    record={'date':datetime.now(timezone.utc).isoformat(),
        'scope':'Actual Jarvis pointer-free workers, owned native/DOM fixtures and requested public sites in a fresh separate Chrome profile. DOM changes are observations, not complete task verification.'}
    try:
        record['native']=native()
        if '--web' in sys.argv:record['web']=web()
    except Exception as exc:record['error']=type(exc).__name__+': '+str(exc)
    record['passed']=record.get('native',{}).get('passed',False) and 'error' not in record and all(
        row.get('passed',row.get('activated_once',False) and row.get('cursor_removed',False) and row.get('system_pointer_unchanged',False))
        for row in record.get('web',[]))
    path=BASE/'artifacts/independent-cursor-live-check.json'
    if path.exists():
        history=path.with_name('independent-cursor-live-history.json')
        rows=json.loads(history.read_text()) if history.exists() else []
        rows.append(json.loads(path.read_text()));history.write_text(json.dumps(rows,indent=2)+'\n')
    path.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
    return record['passed']


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--app':
        print(json.dumps(native_app(sys.argv[2]),indent=2))
    elif len(sys.argv)==3 and sys.argv[1]=='--inspect-app':
        basic,snapshot=app_controls(sys.argv[2])
        safe={'Switch to video mode','Switch to photo mode','Switch to video','Switch to photo','Home','Search','Your Library'}
        print(json.dumps({'controls':[c for c in snapshot['controls'] if c['name'] in safe],
                          'roles':[{'name':c['name'],'role':c['role']} for c in snapshot['controls'] if sys.argv[2]=='camera']},indent=2))
    else:raise SystemExit(0 if main() else 1)
