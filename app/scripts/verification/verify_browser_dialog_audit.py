"""One controlled headless dialog journey; no user profile or real submission."""
import json
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))


def main():
    from playwright.sync_api import sync_playwright
    from jarvis.browser_worker import Session
    chrome=next(p for p in (Path('C:/Program Files/Google/Chrome/Application/chrome.exe'),Path('C:/Program Files (x86)/Google/Chrome/Application/chrome.exe')) if p.is_file())
    with sync_playwright() as driver:
        browser=driver.chromium.launch(headless=True,executable_path=str(chrome))
        try:
            context=browser.new_context()
            context.route('**/*',lambda r:r.fulfill(status=200,content_type='text/html',body='<h1>Owned fixture</h1>'))
            page=context.new_page();page.goto('https://fixture.example/dialog')
            page.set_content('<script>window.submits=0</script><button onclick="if(confirm(\'Proceed with synthetic submit?\'))window.submits++">Continue</button>')
            session=Session();session.page=page;session.context=context;session.open=lambda _:None
            # No dialog handler: Playwright's default is dismissal, never acceptance.
            result=session.perform({'operation':'click','value':'Continue','url':page.url})
            assert page.evaluate('window.submits')==0 and result['verified'] is False
            assert result['owned'] and result['untrusted']
            context.close()
        finally:browser.close()
    proof=dict(date='2026-10-15 IST',status='PASS',synthetic_submits=0,generic_click_goal_verified=False,user_profile_used=False,live_site_used=False,
        scope='Actual installed headless Chrome, isolated context/intercepted fixture; default JS confirm dismissal observed. Not general transaction, login, dialog authorization or no-autosave proof.')
    (BASE/'artifacts/jarvis-audit/modules/14-browser-playwright/dialog-fixture.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof,indent=2))


if __name__=='__main__':main()
