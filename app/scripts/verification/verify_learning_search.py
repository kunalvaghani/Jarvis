"""Actual public Blender feature search; no user-scene or desktop action."""
import json
from pathlib import Path
import time
from jarvis.actions import Actions

BASE = Path(__file__).resolve().parents[2]

def main():
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    root = BASE/'.jarvis-runtime/learning-search-versioned'/str(time.time_ns())
    root.mkdir(parents=True)
    actions = Actions({'files_root':'managed','_ui_verification':True,'memory':{'enabled':False},
        'brain':{'enabled':False},'apps':{'blender':config['apps']['blender']},
        'knowledge_acquisition':{'enabled':True}},root,lambda *_:None)
    actions.allowed_tools = {'application_inspect','web_search','scrape_web'}
    started = time.monotonic()
    try:
        context = actions.acquisition.prepare('Use Blender to make a cube into a sphere')
        capability = context.get('capabilities',[{}])[0]
        result = {'date':'2026-10-14 IST','scope':'Actual configured executable version, public web search and scrapes through ToolRegistry. Desktop input disabled, no user scene mutation or completion claim.',
            'seconds':time.monotonic()-started,'context':context,'passed':bool(capability.get('sources'))}
        (BASE/'artifacts/reports/learning-search-versioned.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'passed':result['passed'],'seconds':result['seconds'],'environment_version':capability.get('version'),
            'urls':[s['url'] for s in capability.get('sources',[])]}),flush=True)
        raise SystemExit(0 if result['passed'] else 1)
    finally:
        actions.close()

if __name__ == '__main__':main()
