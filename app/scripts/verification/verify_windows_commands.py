"""Owned files, headless DOM and native-window checks; no user app commands run."""
import ctypes
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

from jarvis.windows_commands import catalog,prepare,powershell,execute,run_ps


def main():
    base=Path(__file__).resolve().parents[2]
    root=base/'.jarvis-runtime/windows-command-fixture'/str(time.time_ns())
    root.mkdir(parents=True)
    record={'date':datetime.now(timezone.utc).isoformat(),'passed':False,
            'scope':'All 493 recipe compilation checks, owned ASCII files, headless DOM and owned Win32 fixture. No emails, system shutdowns, user files, installed Office/apps or microphone tasks tested.'}
    def approval(kind,detail,cancelled):
        if cancelled():raise ValueError('Stopped')
        # Permit only fixture paths/text in this local verification, not arbitrary catalog effects.
        for row in json.loads(detail):
            if row['id'] not in {140,142,143,145,146,153,464,468,475,476,477}:
                raise ValueError('Unexpected fixture approval ID')
            for key,value in row['parameters'].items():
                if key.startswith('path') and not Path(value).resolve().is_relative_to(root.resolve()):
                    raise ValueError('Fixture path escaped')
    actions=SimpleNamespace(_approve=approval,report=lambda *_:None)
    checks=[];native=None;handle=None;ui=None;browser=None;automation_browser=None
    import win32gui,win32con,win32api,win32process
    original=win32gui.GetForegroundWindow()
    try:
        # Parse all PowerShell examples without executing them.
        codes=[r['command'] for r in catalog() if r['type']=='PS']
        encoded=__import__('base64').b64encode(json.dumps(codes).encode()).decode()
        script="$codes=ConvertFrom-Json ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"'))); $total=0; foreach ($c in $codes) {$t=$null;$e=$null;[Management.Automation.Language.Parser]::ParseInput($c,[ref]$t,[ref]$e)|Out-Null;if($e.Count){throw $e[0].Message};$total++};Write-Output $total"
        parsed=run_ps(script,lambda:False)
        assert '238' in parsed
        checks.append({'name':'238 original PowerShell recipes parse','passed':True})
        # Compile all recipes; tested interpreter coverage lives in test_windows_commands.
        from tests.test_windows_commands import ReferenceTests
        suite=__import__('unittest').defaultTestLoader.loadTestsFromTestCase(ReferenceTests)
        result=__import__('unittest').TextTestRunner(stream=sys.stderr,verbosity=0).run(suite)
        assert result.wasSuccessful()
        checks.append({'name':'493 recipe coverage plus parameter/Stop/uncertainty unit tests','tests':result.testsRun,'passed':True})
        directory=root/'files'; source=directory/'source.txt'; copied=directory/'copy.txt'
        def run(ident,params):return execute(actions,[ident],params)
        run(134,{'path1':str(directory)});assert directory.is_dir()
        run(135,{'path1':str(source)});assert source.exists()
        run(140,{'path1':str(source),'text1':'old fixture'})
        assert source.read_text().strip()=='old fixture'
        run(141,{'path1':str(source),'text1':'second line'})
        run(142,{'path1':str(source),'text1':'old','text2':'new'})
        assert source.read_text().splitlines()[:2]==['new fixture','second line']
        run(143,{'path1':str(source),'path2':str(copied)});assert copied.read_bytes()==source.read_bytes()
        moved=directory/'moved.txt';run(145,{'path1':str(copied),'path2':str(moved)});assert moved.exists() and not copied.exists()
        run(146,{'path1':str(moved),'name':'renamed.txt'});assert (directory/'renamed.txt').exists()
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        assert digest.casefold() in run(154,{'path1':str(source)}).casefold()
        assert 'new fixture' in run(137,{'path1':str(source)})
        checks.append({'name':'10 actual file operations and independent disk/hash observations','passed':True})
        # Real Playwright DOM, entirely headless and local in memory.
        from jarvis.browser_worker import Session
        from playwright.sync_api import sync_playwright
        browser=Session();browser.driver=sync_playwright().start()
        automation_browser=browser.driver.chromium.launch(channel='chrome',headless=True)
        browser.context=automation_browser.new_context()
        browser.page=browser.context.new_page()
        browser.page.set_default_timeout(5000)
        browser.page.set_content('<label>Email<input aria-label="Email"></label><label>Country<select aria-label="Country"><option value="IN">India</option><option value="US">USA</option></select></label><label><input type="checkbox">Subscribe</label><h1>Fixture heading</h1><button onclick="this.textContent=\'Done\'">Continue</button>')
        class OwnedBrowser:
            last_url='about:blank'
            def request(self,operation,cancelled,**kwargs):return browser.perform({'operation':operation,**kwargs})
        actions._browser=lambda:OwnedBrowser()
        run(470,{'arg1':'Email','arg2':'fixture@example.org'});assert browser.page.get_by_label('Email').input_value()=='fixture@example.org'
        run(474,{'arg1':'Country','arg2':'US'});assert browser.page.get_by_label('Country').input_value()=='US'
        run(475,{'arg1':'Subscribe'});assert browser.page.get_by_role('checkbox').is_checked()
        run(476,{'arg1':'Subscribe'});assert not browser.page.get_by_role('checkbox').is_checked()
        assert 'Fixture heading' in run(479,{})
        run(468,{'arg1':'Continue'});assert browser.page.get_by_role('button',name='Done').count()==1
        checks.append({'name':'6 actual local headless DOM commands; field/dropdown/checkbox/text/click readback','passed':True})
        # Fresh native Win32 target, actual UIA click_input and event-log confirmation.
        state=root/'native.json'
        native=subprocess.Popen([sys.executable,str(base/'tests/plan_native_fixture.py'),str(state)],cwd=base,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        end=time.monotonic()+10
        while not state.exists() and time.monotonic()<end:time.sleep(.05)
        handle=json.loads(state.read_text())['root']
        thread=win32api.GetCurrentThreadId();fg=win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
        attached=ctypes.windll.user32.AttachThreadInput(thread,fg,True)
        try:win32gui.SetForegroundWindow(handle)
        finally:
            if attached:ctypes.windll.user32.AttachThreadInput(thread,fg,False)
        from jarvis.ui_controls import UIControls
        desktop=SimpleNamespace(user=SimpleNamespace(GetForegroundWindow=win32gui.GetForegroundWindow,
            GetWindowThreadProcessId=ctypes.windll.user32.GetWindowThreadProcessId,IsWindow=win32gui.IsWindow,
            IsWindowVisible=win32gui.IsWindowVisible),target=handle)
        ui=UIControls(desktop,external_handle=lambda:handle);actions._ui=lambda:ui
        run(464,{'arg1':'Stage 01'})
        assert json.loads(state.read_text())['completed']==[1]
        run(464,{'arg1':'Stage 02'})
        assert json.loads(state.read_text())['completed']==[1,2]
        # A closed destination is rejected before a third click.
        win32gui.PostMessage(handle,win32con.WM_CLOSE,0,0);native.wait(timeout=5)
        try:run(464,{'arg1':'Stage 03'})
        except ValueError:pass
        else:raise AssertionError('Closed destination was not rejected')
        checks.append({'name':'2 real native button activations, event order and closed-app rejection','passed':True})
        record['passed']=True
    except Exception as exc:record.update(error_type=type(exc).__name__,error=str(exc)[:1000])
    finally:
        if automation_browser:automation_browser.close()
        if browser:browser.close()
        if ui:ui.close()
        if handle and win32gui.IsWindow(handle):win32gui.PostMessage(handle,win32con.WM_CLOSE,0,0)
        if native and native.poll() is None:
            try:native.wait(timeout=3)
            except subprocess.TimeoutExpired:native.kill();native.wait(timeout=2)
        if original and win32gui.IsWindow(original):
            try:win32gui.SetForegroundWindow(original)
            except Exception:pass
        record['checks']=checks
        target=base/'artifacts/reports/windows-command-live-check.json'
        if target.exists():
            history=target.with_name('windows-command-live-history.json')
            old=json.loads(history.read_text()) if history.exists() else []
            old.append(json.loads(target.read_text()));history.write_text(json.dumps(old,indent=2)+'\n')
        target.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2),flush=True)
    raise SystemExit(0 if record['passed'] else 1)


if __name__=='__main__':main()
