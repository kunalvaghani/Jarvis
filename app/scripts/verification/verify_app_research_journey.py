"""Real isolated browser DOM -> acquisition -> Brain -> exact click -> oracle."""
import hashlib
import json
from pathlib import Path
import time
from jarvis.actions import Actions
from jarvis.browser_automation import BrowserAutomation
from jarvis.commands import Command
from jarvis.ui_transport import UITransport

BASE = Path(__file__).resolve().parents[2]

def main():
    root = BASE/'.jarvis-runtime/learning-website'/str(time.time_ns())
    root.mkdir(parents=True)
    apps = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))['apps']
    browser = BrowserAutomation(apps, BASE)
    browser.transport = UITransport(BASE,timeout=35,module='scripts.verification.learning_browser_worker')
    actions = Actions({'files_root':'managed','apps':{},'_ui_verification':True,'memory':{'enabled':False},
        'knowledge_acquisition':{'enabled':True,'online':False},
        'brain':{'enabled':True,'planner':'authored-fixture','decision':'authored-scope','screen_aware':False}},root,lambda *_:None)
    actions.task_state.read_only = False
    actions.allowed_tools = {'browser_inspect','browser_click'}
    actions._browser = lambda:browser
    def observe(cancelled):
        data = browser.request('inspect',cancelled)
        return None, {'title':data['title'],'context':data['url'],'controls':data['controls'],
            'signature':hashlib.sha256(json.dumps(data['controls']).encode()).hexdigest()}
    actions.brain.observe = observe
    class Client:
        def close(self):pass
        def request(self,operation,cancelled,**data):
            if operation == 'plan':
                assert data['learning_context']['capabilities'][0]['controls']
                return {'question':'','steps':[{'action':'browser_click','value':'Create slide',
                    'folder':'https://learning.example/','expected':'Fixture slide created'}]}
            if operation == 'decide':return {'approved':True,'choice':'','reason':'Exact owned fixture button'}
            if operation == 'verify':
                raw = browser.request('read_text',cancelled)
                return {'verified':'Verified fixture slide' in raw['text'],'reason':'Independent fresh page text oracle'}
            raise ValueError('Unexpected operation: '+operation)
    actions.brain.client = Client()
    started = time.monotonic()
    result = {'date':'2026-10-16 IST','scope':'Real headless Chrome, existing BrowserSession/BrowserAutomation/UITransport and ToolRegistry, production acquisition/Brain/shared memory, locally intercepted synthetic page. Authored planner and independent DOM oracle; no third-party website, live LLM, account or presentation-export claim.'}
    try:
        reply = actions.execute(Command('task','Use https://learning.example/ to create a presentation slide'))
        capability = actions.screen.knowledge.capabilities('https://learning.example','presentation slide')[0]
        result.update(passed=capability['status']=='verified',seconds=time.monotonic()-started,
            reply=reply,capability=capability,state=actions.task_state.snapshot()['status'])
    except Exception as exc:
        result.update(passed=False,error_type=type(exc).__name__,error=str(exc))
    finally:
        actions.close()
        browser.close()
    (BASE/'artifacts/jarvis-audit/modules/15-app-research/browser-journey.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)

if __name__ == '__main__':main()
