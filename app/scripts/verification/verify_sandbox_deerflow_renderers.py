"""Remaining installed offline recipes, sequential synthetic fixtures; no downloads or accounts."""
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/28-sandbox-deerflow'


def main():
    from jarvis.deerflow_media import execute
    from jarvis.deerflow_sandbox import IMAGE
    from jarvis.repo_sandbox import RepositorySandbox
    runtime=RepositorySandbox(IMAGE)
    expected=json.loads((BASE/'config/runtime_manifest.json').read_text())['optional_deerflow']['sandbox']['tested_image_id']
    image=json.loads(runtime.cli(['image','inspect',IMAGE]))[0];assert image['Id']==expected
    specs={'poster':{'title':'Synthetic fixture','text':'Local audit'},'pdf':{'title':'Synthetic fixture','text':'Observed total: 7.'},
        'slides':{'slides':[{'title':'Synthetic fixture','text':'Observed total: 7.'}]},'video':{'title':'Synthetic fixture','text':'Local audit','duration':1},
        'music':{'duration':1},'narration':{'text':'This is a synthetic local audit fixture.','voice':'am_michael'}}
    rows=[]
    for kind,spec in specs.items():
        started=time.perf_counter()
        try:
            result=json.loads(execute(SimpleNamespace(base=BASE),{'value':kind,'content':json.dumps(spec)},lambda:False))
            state=json.loads((Path(result['artifact_directory'])/'state.json').read_text())
            assert state['status']=='closed' and runtime.cli(['ps','-aq','--filter','id='+state['container_id']]).strip()==b''
            rows.append({'kind':kind,'status':'PASS','seconds':time.perf_counter()-started,'result':result,'cleaned':True})
        except Exception as exc:
            rows.append({'kind':kind,'status':'FAIL','error_type':type(exc).__name__,'error':str(exc)[:400],'seconds':time.perf_counter()-started})
        (OUT/'renderer-fixtures.json').write_text(json.dumps({'date':'2026-10-16 IST','image':image['Id'],
            'scope':'Sequential owned offline synthetic jobs; no image pull, account/API, shared-engine restart or GPU. Format proof levels are recorded, not general content quality.', 'rows':rows},indent=2),encoding='utf-8')
    assert all(r['status']=='PASS' for r in rows),[(r['kind'],r['status']) for r in rows]
    print(json.dumps({'additional_recipes':len(rows),'passed':len(rows),'plus_prior_chart':1,'cleanup':'all owned jobs removed'}))


if __name__=='__main__':main()
