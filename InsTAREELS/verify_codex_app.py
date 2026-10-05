"""Actual restored local Qwen/Codex app creation and owned Chrome interaction."""
from datetime import datetime, timezone
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import threading
from uuid import uuid4

from jarvis.coder import Coder

BASE=Path(__file__).resolve().parent


def verify(repair_project=None):
    if repair_project:
        project=Path(repair_project).resolve()
        assert project.parent==(BASE/'.jarvis-runtime/codex-code-fixture').resolve()
        assert (project/'index.html').is_file()
    else:
        project=BASE/'.jarvis-runtime/codex-code-fixture'/uuid4().hex;project.mkdir(parents=True)
    options={**json.loads((BASE/'config.json').read_text())['brain'],'coding_backend':'codex'}
    events=[]
    def report(kind,value):
        events.append((kind,value))
        if kind=='brain':print(value,flush=True)
    coder=Coder(SimpleNamespace(base=BASE,report=report),SimpleNamespace(options=options))
    result={'date':datetime.now(timezone.utc).isoformat(),'project':str(project),
        'scope':'Actual Jarvis/Codex/local Qwen app generation, followed by isolated Chrome counter interaction. No user project, external network, or real account action.'}
    try:
        prompt=('Read the current index.html and repair it. Browser testing found Increment never stable because html/body pulse transforms move all controls. '
            'Move continuous animation to a decorative background pseudo-element with pointer-events:none; keep the panel and buttons stable. '
            'Add viewport width=device-width,initial-scale=1. Fix unitless nonzero padding values with px. '
            'Preserve the current heading, #count, #add, #reset, counter logic, inline assets, glass appearance and reduced-motion support. '
            'Use Jarvis Edit after reading fresh source. Do not add features.' if repair_project else
            'Create a small standalone app in index.html titled Jarvis Counter. '
            'Use inline CSS and JavaScript only, no external assets. Show an h1 Jarvis Counter, an integer 0 in id=count, '
            'a button id=add labelled Increment that adds one, and id=reset labelled Reset that resets to zero. '
            'Dark glass style, responsive viewport, a gentle continuous CSS background animation and reduced-motion support. '
            'Use Jarvis Write to save a complete file, under 2000 characters.')
        result['generation']=coder.run(project,prompt,selected=True)
        path=project/'index.html';result['source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(project)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            from playwright.sync_api import sync_playwright,expect
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='chrome',headless=True)
                try:
                    page=browser.new_page(viewport={'width':390,'height':844});errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    from urllib.parse import urlsplit
                    page.route('**/*',lambda route:route.continue_() if urlsplit(route.request.url).hostname=='127.0.0.1' else route.abort())
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    expect(page.get_by_role('heading',name='Jarvis Counter',exact=True)).to_be_visible()
                    page.locator('#add').click();page.locator('#add').click();expect(page.locator('#count')).to_have_text('2')
                    page.locator('#reset').click();expect(page.locator('#count')).to_have_text('0')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'),'Mobile overflow'
                    assert not errors,errors
                    result.update(passed=True,browser_errors=errors,progress_events=sum(k=='task_status' for k,v in events),
                        checked=['actual local Codex file save','visible app heading','increment twice','reset','390px layout','no browser runtime errors'])
                finally:browser.close()
        finally:server.shutdown();server.server_close();thread.join(3)
    except Exception as error:result.update(passed=False,error=str(error))
    target=BASE/'artifacts/codex-app-live-check.json'
    if target.exists():
        history=target.with_name('codex-app-live-history.json');rows=json.loads(history.read_text()) if history.exists() else []
        rows.append(json.loads(target.read_text()));history.write_text(json.dumps(rows,indent=2)+'\n')
    target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
    return result['passed']


if __name__=='__main__':raise SystemExit(0 if verify(sys.argv[1] if len(sys.argv)>1 else None) else 1)
