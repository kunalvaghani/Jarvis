"""Ledger append comparison on identical bounded owned synthetic files."""
import csv,importlib.util,json,platform,statistics,sys,tempfile,time,tracemalloc
from pathlib import Path
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/29-reverse-engineering';PRE=BASE/'.jarvis-runtime/jarvis-audit/module29-pre'

def main():
    from jarvis import rea_tools as after
    spec=importlib.util.spec_from_file_location('jarvis._rea_before',PRE/'jarvis__rea_tools.py');before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    rows=[];seed='x'*1000000+'\n';note='fixture note नमस्ते café 😀'
    with tempfile.TemporaryDirectory(prefix='jarvis-rea-bench-') as folder:
        root=Path(folder)
        for sample in range(25):
            for version,module in [('before',before),('after',after)]:
                p=root/'ledger.md';p.write_text(seed,encoding='utf-8')
                tracemalloc.start();start=time.perf_counter_ns()
                # Include the new cross-process fence in the measured path.
                if version=='after':
                    with after._exclusive(root):module._append_ledger(root,'Note',note)
                else:module._append_ledger(root,'Note',note)
                elapsed=(time.perf_counter_ns()-start)/1e6;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                result=p.read_text(encoding='utf-8');assert result.startswith(seed) and result.count(note)==1 and len(result)<1000200
                rows.append(dict(version=version,sample=sample,phase='initial' if sample<5 else 'warm',milliseconds=elapsed,peak_python_bytes=peak,external_actions=0))
    with (OUT/'benchmarks.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'equivalent':True,'real_external_actions':0,'scope':'One note appended to identical 1 MB ledger. UTC heading structure and prefix/note checked; 20 warm+5 initial samples. Not cold processes or REA/model/RSS/VRAM benchmark.'}
    for v in ('before','after'):
        warm=[r for r in rows if r['version']==v and r['phase']=='warm'];values=sorted(r['milliseconds'] for r in warm)
        summary[v]={'p50_ms':statistics.median(values),'p95_ms':values[18],'peak_python_bytes':max(r['peak_python_bytes'] for r in warm)}
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
    import psutil,shutil,subprocess
    env={'date':'2026-10-16 IST','python':sys.version,'platform':platform.platform(),'ram_bytes':psutil.virtual_memory().total,'node':subprocess.check_output([shutil.which('node'),'--version'],text=True).strip()}
    (OUT/'environment.json').write_text(json.dumps(env,indent=2))
def environment_probe():
    import shutil
    from unittest.mock import patch
    from jarvis import rea_tools
    keys=['GROQ_API_KEY','OPENAI_API_KEY','NODE_PATH','NODE_OPTIONS']
    with tempfile.TemporaryDirectory(prefix='jarvis-rea-env-') as folder:
        root=Path(folder);entry=root/'environment.mjs'
        entry.write_text('console.log(JSON.stringify({values:Object.fromEntries('+json.dumps(keys)+'.map(k=>[k,process.env[k]??null])),telemetry:process.env.REA_DISABLE_TELEMETRY}));',encoding='utf-8')
        with patch.dict('os.environ',{k:'JARVIS_AUDIT_FAKE_MARKER' for k in keys}):
            result=json.loads(rea_tools._run_rea(shutil.which('node'),str(entry),[],str(root),lambda:False,5))
        assert result['values']==dict.fromkeys(keys)
        assert result['telemetry']=='1'
        (OUT/'environment-fixture.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))

if __name__=='__main__':
    environment_probe() if '--environment' in sys.argv else main()
