"""One public version-specific documentation read through the actual registry."""
import json
from pathlib import Path
import sys
import time
from jarvis.actions import Actions

BASE = Path(__file__).resolve().parents[2]

def main():
    root = BASE/'.jarvis-runtime/learning-public'/str(time.time_ns())
    root.mkdir(parents=True)
    version = f'{sys.version_info.major}.{sys.version_info.minor}'
    url = f'https://docs.python.org/{version}/library/tkinter.html'
    actions = Actions({'files_root':'managed', '_ui_verification':True, 'memory':{'enabled':False},
        'brain':{'enabled':False}, 'apps':{'Python':{'executable':sys.executable,'documentation_url':url}},
        'knowledge_acquisition':{'enabled':True}}, root, lambda *_:None)
    actions.allowed_tools = {'application_inspect','scrape_web','web_search'}
    started = time.monotonic()
    try:
        context = actions.acquisition.prepare('Research Python diagram documentation')
        sources = context.get('capabilities',[{}])[0].get('sources',[])
        result = {'date':'2026-10-14 IST','scope':'Actual registered public documentation retrieval. Version-specific URL selected from Python runtime; document content version not independently parsed. No GUI workflow verification.',
            'seconds':time.monotonic()-started,'context':context,
            'passed':bool(sources) and sources[0]['url']==url and 'tkinter' in sources[0]['excerpt'].casefold()}
        (BASE/'artifacts/reports/learning-public-docs.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'passed':result['passed'],'seconds':result['seconds'],'url':url}),flush=True)
        raise SystemExit(0 if result['passed'] else 1)
    finally:
        actions.close()

if __name__ == '__main__':main()
