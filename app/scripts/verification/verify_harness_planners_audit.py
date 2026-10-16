"""Equivalent optional-planner schema copies; no model/provider/action calls."""
import csv,importlib.util,json,platform,statistics,sys,time,tracemalloc
from pathlib import Path
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/30-harness-planners';PRE=BASE/'.jarvis-runtime/jarvis-audit/module30-pre'

def modules():
    from jarvis import harness_worker as after
    spec=importlib.util.spec_from_file_location('jarvis._harness_before',PRE/'jarvis__harness_worker.py');before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    return before,after

def fixture():
    from jarvis.brain_worker import SCHEMAS
    schema=json.loads(json.dumps(SCHEMAS['replan']))
    schema['properties']['steps']['items']['properties']['action']['enum']=[f'fixture_tool_{i}' for i in range(100)]
    return schema

def main():
    before,after=modules();schema=fixture();expected=before.exclusive_proposal_schema(schema,'replan');rows=[]
    candidates=[('before',before)] if '--baseline' in sys.argv else [('before',before),('after',after)]
    for sample in range(25):
        for name,module in candidates:
            tracemalloc.start();start=time.perf_counter_ns()
            for _ in range(50):
                result=module.exclusive_proposal_schema(schema,'replan');assert result==expected
            elapsed=(time.perf_counter_ns()-start)/1e6;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            rows.append(dict(version=name,sample=sample,phase='initial' if sample<5 else 'warm',batch=50,milliseconds=elapsed,peak_python_bytes=peak,external_actions=0))
    prefix='baseline-' if '--baseline' in sys.argv else ''
    with (OUT/(prefix+'benchmarks.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'equivalent':True,'real_external_actions':0,'scope':'50 schema copies per sample;5 initial+20 warm. Identical replan branches and100 synthetic tool names; no model/tool accuracy, TTFT/audio, RSS/VRAM or cold process claim.'}
    for v,_ in candidates:
        warm=[r for r in rows if r['version']==v and r['phase']=='warm'];values=sorted(r['milliseconds'] for r in warm)
        summary[v]={'p50_ms':statistics.median(values),'p95_ms':values[18],'peak_python_bytes':max(r['peak_python_bytes'] for r in warm)}
    (OUT/(prefix+'benchmark-summary.json')).write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
    import psutil
    env={'date':'2026-10-16 IST','python':sys.version,'platform':platform.platform(),'ram_bytes':psutil.virtual_memory().total}
    (OUT/'environment.json').write_text(json.dumps(env,indent=2))
if __name__=='__main__':main()
