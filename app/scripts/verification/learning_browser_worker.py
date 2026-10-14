"""Isolated headless fixture using production Session methods and transport ABI."""
import json
from pathlib import Path
import sys
import time
from jarvis.browser_worker import Session

def main():
    from playwright.sync_api import sync_playwright
    base = Path(__file__).resolve().parents[2]
    profile = base/'.jarvis-runtime/learning-browser-profiles'/str(time.time_ns())
    session = Session()
    session.driver = sync_playwright().start()
    config = json.loads((base/'config/config.json').read_text(encoding='utf-8'))
    from jarvis.browser import browser_args
    executable = browser_args(config['apps'], 'chrome')[0]
    session.context = session.driver.chromium.launch_persistent_context(str(profile), executable_path=executable, headless=True)
    session.page = session.context.pages[0]
    html = '<html><title>Learning web fixture</title><body><button onclick="this.textContent=\'Slide created\';document.querySelector(\'#result\').textContent=\'Verified fixture slide\'">Create slide</button><p id="result"></p></body></html>'
    def route(request):
        if request.request.url.startswith('https://learning.example/'):
            request.fulfill(status=200,content_type='text/html',body=html)
        else:
            request.abort()
    session.context.route('**/*',route)
    session.page.goto('https://learning.example/')
    try:
        for line in sys.stdin:
            envelope = json.loads(line)
            request = envelope['request']
            if request['operation'] == 'shutdown':
                break
            try:
                result = {'id':envelope['id'],'result':session.perform(request)}
            except Exception as exc:
                result = {'id':envelope['id'],'error':str(exc)}
            print(json.dumps(result),flush=True)
    finally:
        session.close()

if __name__ == '__main__': main()
