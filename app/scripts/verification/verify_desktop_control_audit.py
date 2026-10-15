"""Matched preparation-only fallback benchmark; no native desktop work."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
from types import SimpleNamespace

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/13-desktop-control'


def main():
    import jarvis.execution_router as after
    from jarvis.execution_adapters import Prepared
    pre=BASE/'.jarvis-runtime/jarvis-audit/module13-pre/jarvis__execution_router.py'
    spec=importlib.util.spec_from_file_location('jarvis._desktop_before',pre)
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    samples=[];results={};effects=[]
    for version,module in [('before',before),('after',after)]:
        for mode,count in [('cold',5),('warm',20)]:
            for index in range(count):
                created=[];state=[]
                def make_provider(name):
                    class Provider:
                        def __init__(self):created.append(name);self.name=name
                        def prepare(self,*args):return Prepared(lambda:state.append('one'),lambda:state==['one'],True)
                    return Provider
                factories=tuple(make_provider(f'provider-{i}') for i in range(6))
                old=module.PROVIDERS;module.PROVIDERS=factories
                try:
                    tracemalloc.start();start=time.perf_counter()
                    result=module.execute({'operation':'activate','value':'Apply'},None,{'name':'Apply','role':'Button'},None,lambda:None)
                    ms=(time.perf_counter()-start)*1000;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                finally:module.PROVIDERS=old
                assert result['verified'] and state==['one'] and result['provider']=='provider-0'
                assert len(created)==(6 if version=='before' else 1)
                effects.append(state==['one'])
                samples.append(dict(version=version,mode=mode,index=index,ms=ms,peak_python_bytes=peak,providers_created=len(created),fake_dispatches=len(state),real_side_effects=0))
    for version in ('before','after'):
        for mode in ('cold','warm'):
            rows=[r for r in samples if r['version']==version and r['mode']==mode];values=sorted(r['ms'] for r in rows)
            results[version+'_'+mode]=dict(samples=len(values),p50_ms=statistics.median(values),p95_ms=values[-1 if len(values)==5 else 18],peak_python_bytes=max(r['peak_python_bytes'] for r in rows))
    with (OUT/'benchmarks.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
    summary=dict(date='2026-10-15 IST',scope='Same machine/current Prepared/identical synthetic six provider factories; first preparation succeeds; old eager versus current lazy construction plus new validation/UUID.5 fresh per-call fixtures labelled cold and20 repeated fixtures labelled warm, not OS/model cold or real COM/UIA latency. Tracemalloc component allocation only. No network/GPU/screen/model/audio work; TTFT/audio/VRAM not applicable.',results=results,effects_verified=all(effects),real_side_effects=0)
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
