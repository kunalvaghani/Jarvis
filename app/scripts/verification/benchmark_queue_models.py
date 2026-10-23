"""Bounded public-prompt probes through existing local GPU leases; never downloads."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
from urllib.request import urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis.command_cleanup import stream_json


def main(output):
    base=Path(__file__).resolve().parents[2]
    config=json.loads((base/'config/config.json').read_text(encoding='utf-8'))
    models=[('context',config.get('context_selector',{}).get('model','qwen3.5:0.8b')),
            ('planner',config.get('brain',{}).get('planner','qwen3.5:9b'))]
    with urlopen('http://127.0.0.1:11434/api/tags',timeout=5) as response:
        installed={m['name'] for m in json.load(response)['models']}
    rows=[]
    for role,model in models:
        row={'role':role,'model':model,'installed':model in installed,'samples':[]}
        if model in installed:
            for _ in range(3):
                start=time.perf_counter()
                try:
                    result=stream_json({'model':model,'stream':True,'think':False,'messages':[
                        {'role':'system','content':'Return exactly the JSON object {"status":"ready"}.'},
                        {'role':'user','content':'Public synthetic queue readiness probe.'}],
                        'format':{'type':'object','properties':{'status':{'type':'string','enum':['ready']}},'required':['status']},
                        'options':{'temperature':0,'num_ctx':1024,'num_predict':24}},90,role=role)
                    sample={'seconds':time.perf_counter()-start,'matched':result=={'status':'ready'}}
                except Exception as exc:
                    sample={'seconds':time.perf_counter()-start,'matched':False,'error_type':type(exc).__name__}
                row['samples'].append(sample)
            row['p50_seconds']=statistics.median(s['seconds'] for s in row['samples'])
            row['p95_seconds']=None
        rows.append(row)
    value={'date':'2026-10-23','scope':'Three local public JSON probes per configured model through existing gpu_scheduler; not classification or task-quality acceptance',
           'models':rows,'cloud_requests':0,'model_downloads':0,'note':'Cold/loading/handoff and lease wait are included; sample size does not support p95.'}
    output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
